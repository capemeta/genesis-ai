from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.chunk import Chunk
from models.kb_doc_parse_attempt import KBDocParseAttempt
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.user import User
from core.model_platform.kb_model_resolver import validate_kb_runtime_models
from rag.search_units import delete_search_projections_for_chunk_ids
from rag.ingestion.tasks.common import (
    add_log,
    build_effective_config,
    cleanup_derived_documents_for_kb_doc,
    finalize_latest_attempt,
    reset_kb_doc_runtime,
    set_runtime_stage,
    upsert_kb_doc_runtime,
)

logger = logging.getLogger(__name__)


def dispatch_pipeline_signature(signature) -> str:
    """派发已准备好的任务签名。"""
    logger.info(
        "派发任务签名: task=%s, task_id=%s, queue=%s",
        getattr(signature, "task", None),
        signature.options.get("task_id"),
        signature.options.get("queue"),
    )
    async_result = signature.apply_async()
    return str(async_result.id)


def build_parse_pipeline_signature(kb_doc_id: UUID):
    """构造统一解析任务签名，并预先冻结任务 ID。"""
    from rag.ingestion.tasks.parse_task import parse_document_task

    signature = parse_document_task.s(str(kb_doc_id))
    signature.set(queue="parse")
    signature.freeze()
    return signature


def dispatch_parse_pipeline(signature) -> str:
    """派发已准备好的解析任务签名。"""
    return dispatch_pipeline_signature(signature)


def build_chunk_pipeline_signature(
    kb_doc_id: UUID,
    raw_text: str,
    metadata: dict[str, Any],
    *,
    chunk_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    **kwargs,
):
    """构造从 chunk 阶段继续执行的统一任务签名。"""
    from rag.ingestion.tasks.chunk_task import chunk_document_task

    signature = chunk_document_task.s(
        str(kb_doc_id),
        raw_text,
        metadata,
        chunk_strategy=chunk_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        **kwargs,
    )
    signature.set(queue="chunk")
    signature.freeze()
    return signature


async def prepare_parse_pipeline_submission(
    db: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    *,
    reset_chunk_count: bool = True,
    effective_config: dict[str, Any] | None = None,
):
    """统一准备 parse -> chunk -> enhance -> train 任务链的入队状态。"""
    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_doc.kb_id)
    )
    kb = kb_result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在，无法启动解析任务",
        )

    runtime_model_snapshot = await validate_kb_runtime_models(db, kb=kb)
    signature = build_parse_pipeline_signature(kb_doc.id)
    task_id = str(signature.options.get("task_id") or "")
    now = datetime.utcnow()

    kb_doc.parse_status = "queued"
    kb_doc.parse_error = None
    kb_doc.parse_progress = 0
    kb_doc.parse_started_at = None
    kb_doc.parse_ended_at = None
    kb_doc.parse_duration_milliseconds = 0
    kb_doc.updated_at = now
    set_runtime_stage(kb_doc, "queued")
    if reset_chunk_count:
        kb_doc.chunk_count = 0

    kb_doc.task_id = task_id
    await reset_kb_doc_runtime(
        db,
        kb_doc,
        pipeline_task_id=task_id,
        effective_config=effective_config or build_effective_config(
            kb_doc,
            extra={"runtime_models": runtime_model_snapshot},
            kb=kb,
        ),
    )
    return signature


async def prepare_chunk_pipeline_submission(
    db: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    *,
    raw_text: str,
    metadata: dict[str, Any],
    chunk_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    reset_chunk_count: bool = False,
    effective_config: dict[str, Any] | None = None,
    chunk_task_kwargs: dict[str, Any] | None = None,
):
    """统一准备从 chunk 阶段续跑的任务链入队状态。"""
    signature = build_chunk_pipeline_signature(
        kb_doc.id,
        raw_text,
        metadata,
        chunk_strategy=chunk_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        **(chunk_task_kwargs or {}),
    )
    task_id = str(signature.options.get("task_id") or "")
    now = datetime.utcnow()

    kb_doc.parse_status = "queued"
    kb_doc.parse_error = None
    kb_doc.parse_progress = 0
    kb_doc.parse_started_at = None
    kb_doc.parse_ended_at = None
    kb_doc.parse_duration_milliseconds = 0
    kb_doc.updated_at = now
    set_runtime_stage(kb_doc, "queued")
    if reset_chunk_count:
        kb_doc.chunk_count = 0

    kb_doc.task_id = task_id
    await reset_kb_doc_runtime(
        db,
        kb_doc,
        pipeline_task_id=task_id,
        effective_config=effective_config or build_effective_config(kb_doc),
    )
    return signature


class KBDocumentParseService:
    """知识库文档解析编排服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def reparse_documents(
        self,
        kb_document_ids: list[UUID],
        current_user: User,
        redis: Redis,
    ) -> dict[str, Any]:
        """重新提交知识库文档解析任务。"""
        if not kb_document_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择至少一个文档",
            )

        kb_docs = await self._load_kb_docs(kb_document_ids, current_user)
        if len(kb_docs) != len(kb_document_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="部分文档不存在或无权访问",
            )

        skipped_docs: list[dict[str, str]] = []
        submitted_docs: list[dict[str, str]] = []
        pending_signatures = []

        for kb_doc in kb_docs:
            if await self._recover_orphaned_parse_task(
                redis,
                kb_doc,
                recover_reason="检测到上一次解析任务已失联，系统已自动恢复状态，可重新发起解析",
            ):
                await self.db.flush()

            if kb_doc.parse_status == "processing":
                logger.warning("文档 %s 正在解析中，跳过", kb_doc.id)
                skipped_docs.append({
                    "id": str(kb_doc.id),
                    "name": kb_doc.document.name if kb_doc.document else "未知",
                    "reason": "文档正在解析中",
                })
                continue

            if kb_doc.parse_status == "cancelling":
                logger.warning("文档 %s 正在取消中，跳过", kb_doc.id)
                skipped_docs.append({
                    "id": str(kb_doc.id),
                    "name": kb_doc.document.name if kb_doc.document else "未知",
                    "reason": "文档正在取消中，请稍后再试",
                })
                continue

            submit_key = f"parsing:submit:{kb_doc.id}"
            if await redis.exists(submit_key):
                logger.warning("文档 %s 请求过于频繁，跳过", kb_doc.id)
                skipped_docs.append({
                    "id": str(kb_doc.id),
                    "name": kb_doc.document.name if kb_doc.document else "未知",
                    "reason": "请求过于频繁，请稍后再试",
                })
                continue

            await redis.setex(submit_key, 5, "1")
            await redis.delete(f"parsing:cancel:{kb_doc.id}")

            # 重新解析前先显式清理旧检索投影，避免先删 chunk 后无法定位旧 search_unit。
            existing_chunk_rows = await self.db.execute(
                select(Chunk.id).where(Chunk.kb_doc_id == kb_doc.id)
            )
            existing_chunk_ids = [int(chunk_id) for chunk_id in existing_chunk_rows.scalars().all()]
            await delete_search_projections_for_chunk_ids(self.db, existing_chunk_ids)
            await self.db.execute(
                sql_delete(Chunk).where(Chunk.kb_doc_id == kb_doc.id)
            )
            latest_attempt_stmt = (
                select(KBDocParseAttempt.id)
                .where(KBDocParseAttempt.kb_doc_id == kb_doc.id)
                .limit(1)
            )
            latest_attempt_result = await self.db.execute(latest_attempt_stmt)
            has_previous_attempt = latest_attempt_result.scalar_one_or_none() is not None

            if has_previous_attempt:
                await add_log(
                    self.db,
                    kb_doc,
                    step="REPARSE",
                    message="用户触发重新解析，旧分块已清理",
                    status="interrupted",
                )
                await finalize_latest_attempt(
                    self.db,
                    kb_doc.id,
                    final_status="interrupted",
                )

            signature = await prepare_parse_pipeline_submission(
                self.db,
                kb_doc,
                reset_chunk_count=True,
                effective_config=build_effective_config(kb_doc),
            )
            pending_signatures.append(signature)

            submitted_docs.append({
                "id": str(kb_doc.id),
                "name": kb_doc.document.name if kb_doc.document else "未知",
                "task_id": str(signature.options.get("task_id") or ""),
            })
            logger.info(
                "准备解析任务提交: kb_doc_id=%s, task_id=%s",
                kb_doc.id,
                signature.options.get("task_id"),
            )

        await self.db.commit()
        for signature in pending_signatures:
            dispatch_parse_pipeline(signature)

        response_data = {
            "submitted_count": len(submitted_docs),
            "skipped_count": len(skipped_docs),
            "submitted_docs": submitted_docs,
            "skipped_docs": skipped_docs,
        }

        if not submitted_docs:
            return {
                "success": False,
                "message": "所有文档都被跳过，未提交任何解析任务",
                "data": response_data,
            }

        message = f"已成功触发 {len(submitted_docs)} 个文档的重新解析任务"
        if skipped_docs:
            message += f"，跳过 {len(skipped_docs)} 个文档"

        return {
            "success": True,
            "message": message,
            "data": response_data,
        }

    async def cancel_parse(
        self,
        kb_document_ids: list[UUID],
        current_user: User,
        redis: Redis,
    ) -> dict[str, Any]:
        """取消知识库文档解析任务。"""
        if not kb_document_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择至少一个文档",
            )

        kb_docs = await self._load_kb_docs(kb_document_ids, current_user)
        if not kb_docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在",
            )

        from tasks.celery_tasks import celery_app

        immediate_cancelled = 0
        graceful_cancelling = 0
        skipped = 0

        for kb_doc in kb_docs:
            if kb_doc.parse_status in ("pending", "queued"):
                old_task_id = kb_doc.task_id
                if kb_doc.task_id:
                    celery_app.control.revoke(kb_doc.task_id, terminate=False)

                await redis.setex(f"parsing:cancel:{kb_doc.id}", 3600, "1")

                kb_doc.parse_status = "cancelled"
                kb_doc.parse_error = "任务已取消（未开始执行）"
                kb_doc.task_id = None
                kb_doc.parse_ended_at = datetime.utcnow()
                kb_doc.updated_at = datetime.utcnow()
                set_runtime_stage(kb_doc, "cancelled")
                await add_log(
                    self.db,
                    kb_doc,
                    step="CANCEL",
                    message="任务已取消（未开始执行）",
                    status="cancelled",
                )
                await finalize_latest_attempt(
                    self.db,
                    kb_doc.id,
                    final_status="cancelled",
                )
                await upsert_kb_doc_runtime(
                    self.db,
                    kb_doc,
                    pipeline_task_id=None,
                    stats={"chunk_count": int(kb_doc.chunk_count or 0)},
                    error_detail={
                        "status": "cancelled",
                        "message": kb_doc.parse_error,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                )

                immediate_cancelled += 1
                logger.info("立即取消任务: kb_doc_id=%s, task_id=%s", kb_doc.id, old_task_id)
                continue

            if kb_doc.parse_status in ("processing", "cancelling"):
                if await self._recover_orphaned_parse_task(
                    redis,
                    kb_doc,
                    recover_reason="检测到解析 Worker 已离线，已直接完成取消",
                ):
                    immediate_cancelled += 1
                    logger.info("自动收敛取消状态: kb_doc_id=%s", kb_doc.id)
                    continue

                if kb_doc.task_id:
                    celery_app.control.revoke(kb_doc.task_id, terminate=False)

                await redis.setex(f"parsing:cancel:{kb_doc.id}", 3600, "1")

                kb_doc.parse_status = "cancelling"
                kb_doc.parse_error = "任务取消中，等待 Worker 响应..."
                kb_doc.updated_at = datetime.utcnow()
                set_runtime_stage(kb_doc, "cancelling")
                await add_log(
                    self.db,
                    kb_doc,
                    step="CANCEL",
                    message="用户请求取消解析任务，等待 Worker 响应",
                    status="cancelling",
                )
                await upsert_kb_doc_runtime(
                    self.db,
                    kb_doc,
                    pipeline_task_id=kb_doc.task_id,
                    stats={"chunk_count": int(kb_doc.chunk_count or 0)},
                    error_detail={
                        "status": "cancelling",
                        "message": kb_doc.parse_error,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                )

                graceful_cancelling += 1
                logger.info("优雅取消任务: kb_doc_id=%s, task_id=%s", kb_doc.id, kb_doc.task_id)
                continue

            skipped += 1
            logger.warning("跳过取消任务: kb_doc_id=%s, status=%s", kb_doc.id, kb_doc.parse_status)

        await self.db.commit()

        messages: list[str] = []
        if immediate_cancelled > 0:
            messages.append(f"{immediate_cancelled} 个任务已立即取消")
        if graceful_cancelling > 0:
            messages.append(f"{graceful_cancelling} 个任务正在优雅取消中")
        if skipped > 0:
            messages.append(f"{skipped} 个任务无法取消（状态不符）")

        return {
            "success": True,
            "message": "，".join(messages) if messages else "没有任务被取消",
            "data": {
                "immediate_cancelled": immediate_cancelled,
                "graceful_cancelling": graceful_cancelling,
                "skipped": skipped,
                "note": "processing 状态的任务将在下一个检查点停止（通常几秒内）",
            },
        }

    async def _load_kb_docs(
        self,
        kb_document_ids: list[UUID],
        current_user: User,
    ) -> list[KnowledgeBaseDocument]:
        """加载当前用户有权限操作的知识库文档。"""
        stmt = (
            select(KnowledgeBaseDocument)
            .where(
                KnowledgeBaseDocument.id.in_(kb_document_ids),
                KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
            )
            .options(selectinload(KnowledgeBaseDocument.document))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _recover_orphaned_parse_task(
        self,
        redis: Redis,
        kb_doc: KnowledgeBaseDocument,
        *,
        recover_reason: str,
    ) -> bool:
        """检测已失联的解析任务，并直接收敛到最终状态。"""
        if kb_doc.parse_status not in ("processing", "cancelling"):
            return False

        if await redis.exists(f"parsing:lock:{kb_doc.id}"):
            return False

        final_status = "cancelled" if kb_doc.parse_status == "cancelling" else "failed"
        final_chunk_count = 0 if final_status == "cancelled" else int(kb_doc.chunk_count or 0)

        # 没有解析锁时，说明当前没有 Worker 真正在处理这条任务，可以安全收敛状态。
        if final_status == "cancelled":
            await cleanup_derived_documents_for_kb_doc(self.db, kb_doc)
            kb_doc.chunk_count = 0
            await redis.setex(f"parsing:cancel:{kb_doc.id}", 3600, "1")

        kb_doc.parse_status = final_status
        kb_doc.task_id = None
        kb_doc.parse_error = recover_reason
        kb_doc.parse_ended_at = datetime.utcnow()
        kb_doc.updated_at = datetime.utcnow()
        set_runtime_stage(kb_doc, final_status)
        await upsert_kb_doc_runtime(
            self.db,
            kb_doc,
            pipeline_task_id=None,
            stats={"chunk_count": final_chunk_count},
            error_detail={
                "status": final_status,
                "message": recover_reason,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        await add_log(
            self.db,
            kb_doc,
            step="RECOVER",
            message=recover_reason,
            status=final_status,
        )
        await finalize_latest_attempt(
            self.db,
            kb_doc.id,
            final_status=final_status,
            error_msg=recover_reason if final_status == "failed" else None,
        )

        logger.warning(
            "检测到失联解析任务，已自动收敛状态: kb_doc_id=%s, status=%s",
            kb_doc.id,
            final_status,
        )
        return True
