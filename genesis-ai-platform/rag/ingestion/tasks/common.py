"""
RAG 分块任务的公共工具函数

包含：
- 进度定义
- 日志记录
- 取消检查（Redis 取消标志）
- 状态标记
- 分布式锁（Redis Lock + 续期）

Redis 使用约定：
- Celery 任务内通过 create_task_redis_client() 获取独立客户端（含私有连接池），
  任务结束后必须调用 close_task_redis_client() 关闭。
- FastAPI / 中间件等长驻进程使用 get_redis_client()（全局连接池复用）。
- 取消键：parsing:cancel:{kb_doc_id}；锁键：parsing:lock:{kb_doc_id}。
- Redis 异常由任务层捕获并触发 Celery 重试（ConnectionError/TimeoutError + backoff）。

数据库使用约定：
- Celery 任务内通过 create_task_session_maker() 创建独立引擎 + session 工厂，
  任务结束后必须调用 close_task_db_engine() 关闭引擎。
- FastAPI / 中间件等长驻进程使用全局 async_session_maker（全局引擎连接池复用）。
- 原因：asyncio.run() 每次创建新 event loop，全局引擎连接池中的连接绑定在旧 loop 上，
  在新 loop 中复用会触发 "Future attached to a different loop" 错误。
"""

import re
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, cast
from uuid import UUID
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import delete as sql_delete, select
import redis.asyncio as redis

from models.kb_doc_parse_attempt import KBDocParseAttempt
from models.knowledge_base_document import KnowledgeBaseDocument
from models.kb_doc_runtime import KBDocRuntime
from core.config import settings
from rag.config.effective import build_effective_config
from rag.utils.token_utils import count_mixed_units, is_chunk_safe

logger = logging.getLogger(__name__)
_ATTEMPT_FIELD_UNSET = object()
# 定义解析步骤对应的进度百分比
STEP_PROGRESS = {
    "INIT": 5,      # 初始化：5%
    "LOAD": 15,     # 加载文件：15%
    "PARSE": 50,    # 解析文本：50%
    "CHUNK": 75,    # 分块：75%
    "ENHANCE": 85,  # 增强：85%
    "TRAIN": 95,    # 训练：95%
    "FINISH": 100,  # 完成：100%
    "ERROR": 0,     # 错误：保持当前进度
    "CANCEL": 0,    # 取消：保持当前进度
}


async def add_log(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    step: str,
    message: str,
    status: str = "done"
):
    """
    添加解析步骤日志（支持多次尝试）。

    注意：日志写入使用独立 session + 独立事务，只更新日志字段。
    这样可以避免两类问题：
    1. 日志提交时误提交业务 session 中尚未准备提交的数据
    2. 重 CPU / 长耗时阶段持有业务事务，导致连接长时间占用

    Args:
        session: 数据库会话
        kb_doc: 知识库文档对象
        step: 步骤名称（INIT, LOAD, PARSE, CHUNK, ENHANCE, TRAIN, FINISH, ERROR, CANCEL）
        message: 日志消息
        status: 状态（done, processing, error, cancelled）

    数据会写入 kb_doc_parse_attempts.logs_json。
    """
    now = datetime.now()
    log_entry = {
        "step": step,
        "message": message,
        "time": now.isoformat(),
        "status": status,
    }

    log_session_maker = _create_isolated_session_maker(session)
    async with log_session_maker() as log_session:
        attempt = await _get_latest_attempt(log_session, kb_doc.id)

        if step == "INIT":
            # 同一个 task_id 的重复执行视为同一次 attempt，
            # 避免 worker 重投或 retry 时把一次用户触发拆成多条历史记录。
            if (
                attempt
                and attempt.ended_at is None
                and kb_doc.task_id
                and attempt.task_id == kb_doc.task_id
            ):
                attempt.logs_json = list(attempt.logs_json or []) + [log_entry]
                attempt.status = "processing"
                attempt.runtime_stage = kb_doc.runtime_stage
                attempt.updated_at = now
            else:
                if attempt and attempt.ended_at is None:
                    attempt.logs_json = list(attempt.logs_json or []) + [{
                        "step": "INIT",
                        "message": "新的解析任务已启动，当前 attempt 被中断",
                        "time": now.isoformat(),
                        "status": "interrupted",
                    }]
                    attempt.status = "interrupted"
                    attempt.ended_at = now
                    attempt.updated_at = now

                next_attempt_no = 1 if attempt is None else int(attempt.attempt_no) + 1
                attempt = KBDocParseAttempt(
                    kb_doc_id=kb_doc.id,
                    tenant_id=kb_doc.tenant_id,
                    kb_id=kb_doc.kb_id,
                    document_id=kb_doc.document_id,
                    attempt_no=next_attempt_no,
                    task_id=kb_doc.task_id,
                    trigger_source="system",
                    status="processing",
                    runtime_stage=kb_doc.runtime_stage,
                    config_snapshot=build_effective_config(kb_doc),
                    logs_json=[log_entry],
                    started_at=now,
                )
                log_session.add(attempt)
        else:
            if attempt is None:
                attempt = KBDocParseAttempt(
                    kb_doc_id=kb_doc.id,
                    tenant_id=kb_doc.tenant_id,
                    kb_id=kb_doc.kb_id,
                    document_id=kb_doc.document_id,
                    attempt_no=1,
                    task_id=kb_doc.task_id,
                    trigger_source="system",
                    status="processing",
                    runtime_stage=kb_doc.runtime_stage,
                    config_snapshot=build_effective_config(kb_doc),
                    logs_json=[],
                    started_at=now,
                )
                log_session.add(attempt)

            attempt.logs_json = list(attempt.logs_json or []) + [log_entry]
            if status in {"processing", "cancelling"}:
                attempt.status = status
            attempt.runtime_stage = kb_doc.runtime_stage
            attempt.task_id = kb_doc.task_id
            attempt.updated_at = now

        await log_session.commit()

    progress = STEP_PROGRESS.get(step, kb_doc.parse_progress)
    if progress > 0:
        kb_doc.parse_progress = progress


async def _get_latest_attempt(
    session: AsyncSession,
    kb_doc_id: UUID,
) -> Optional[KBDocParseAttempt]:
    result = await session.execute(
        select(KBDocParseAttempt)
        .where(KBDocParseAttempt.kb_doc_id == kb_doc_id)
        .order_by(KBDocParseAttempt.attempt_no.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def serialize_parse_attempt(attempt: KBDocParseAttempt) -> dict[str, Any]:
    """将 attempt 记录转换为前端沿用的 parsing_logs 结构。"""
    return {
        "attempt": attempt.attempt_no,
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "ended_at": attempt.ended_at.isoformat() if attempt.ended_at else None,
        "status": attempt.status,
        "error": attempt.error_message,
        "duration_ms": attempt.duration_ms,
        "logs": list(attempt.logs_json or []),
    }


async def load_recent_parse_attempt_logs(
    session: AsyncSession,
    kb_doc_ids: list[UUID],
    *,
    per_doc_limit: int = 5,
) -> dict[UUID, list[dict[str, Any]]]:
    """批量加载最近若干次 attempt，并转换为旧 parsing_logs 响应结构。"""
    if not kb_doc_ids:
        return {}

    result = await session.execute(
        select(KBDocParseAttempt)
        .where(KBDocParseAttempt.kb_doc_id.in_(kb_doc_ids))
        .order_by(KBDocParseAttempt.kb_doc_id, KBDocParseAttempt.attempt_no.desc())
    )

    logs_map: dict[UUID, list[dict[str, Any]]] = {}
    for attempt in result.scalars().all():
        items = logs_map.setdefault(attempt.kb_doc_id, [])
        if len(items) >= per_doc_limit:
            continue
        items.append(serialize_parse_attempt(attempt))

    # 前端按数组最后一项视为最新一次，因此这里统一转为按 attempt_no 升序返回。
    for kb_doc_id in list(logs_map.keys()):
        logs_map[kb_doc_id].reverse()
    return logs_map


def _create_isolated_session_maker(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """基于当前业务 session 绑定的引擎创建独立日志 session。"""
    bind = session.bind
    if bind is None:
        raise RuntimeError("当前 session 未绑定数据库引擎，无法创建独立日志事务")
    return async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


async def finalize_latest_attempt(
    session: AsyncSession,
    kb_doc_id: UUID,
    *,
    final_status: str,
    error_msg: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """独立事务收口最新 attempt，避免旧对象回写覆盖新日志。"""
    log_session_maker = _create_isolated_session_maker(session)
    async with log_session_maker() as log_session:
        attempt = await _get_latest_attempt(log_session, kb_doc_id)
        if attempt is None:
            raise ValueError(f"KnowledgeBaseDocument {kb_doc_id} 不存在，无法更新尝试状态")
        now = datetime.now()
        attempt.ended_at = now
        attempt.status = final_status
        attempt.error_message = error_msg
        if duration_ms is not None:
            attempt.duration_ms = duration_ms
        attempt.runtime_stage = final_status
        attempt.updated_at = now
        await log_session.commit()


async def sync_latest_attempt_snapshot(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    *,
    trigger_source: Any = _ATTEMPT_FIELD_UNSET,
    status: Any = _ATTEMPT_FIELD_UNSET,
    runtime_stage: Any = _ATTEMPT_FIELD_UNSET,
    task_id: Any = _ATTEMPT_FIELD_UNSET,
    error_message: Any = _ATTEMPT_FIELD_UNSET,
    parse_strategy: Any = _ATTEMPT_FIELD_UNSET,
    parser: Any = _ATTEMPT_FIELD_UNSET,
    effective_parser: Any = _ATTEMPT_FIELD_UNSET,
    chunk_strategy: Any = _ATTEMPT_FIELD_UNSET,
    config_snapshot: Optional[Dict[str, Any]] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> None:
    """同步最新 attempt 的结构化快照，供排障与追踪使用。"""
    log_session_maker = _create_isolated_session_maker(session)
    now = datetime.now()

    async with log_session_maker() as log_session:
        attempt = await _get_latest_attempt(log_session, kb_doc.id)
        if attempt is None:
            attempt = KBDocParseAttempt(
                kb_doc_id=kb_doc.id,
                tenant_id=kb_doc.tenant_id,
                kb_id=kb_doc.kb_id,
                document_id=kb_doc.document_id,
                attempt_no=1,
                task_id=kb_doc.task_id,
                trigger_source="system",
                status="processing",
                runtime_stage=kb_doc.runtime_stage,
                config_snapshot=build_effective_config(kb_doc),
                logs_json=[],
                started_at=now,
            )
            log_session.add(attempt)

        if trigger_source is not _ATTEMPT_FIELD_UNSET:
            attempt.trigger_source = trigger_source
        if status is not _ATTEMPT_FIELD_UNSET:
            attempt.status = status
        if runtime_stage is not _ATTEMPT_FIELD_UNSET:
            attempt.runtime_stage = runtime_stage
        if task_id is not _ATTEMPT_FIELD_UNSET:
            attempt.task_id = task_id
        if error_message is not _ATTEMPT_FIELD_UNSET:
            attempt.error_message = error_message
        if parse_strategy is not _ATTEMPT_FIELD_UNSET:
            attempt.parse_strategy = parse_strategy
        if parser is not _ATTEMPT_FIELD_UNSET:
            attempt.parser = parser
        if effective_parser is not _ATTEMPT_FIELD_UNSET:
            attempt.effective_parser = effective_parser
        if chunk_strategy is not _ATTEMPT_FIELD_UNSET:
            attempt.chunk_strategy = chunk_strategy
        if config_snapshot:
            attempt.config_snapshot = _merge_runtime_dict(attempt.config_snapshot, config_snapshot)
        if stats:
            attempt.stats = _merge_runtime_dict(attempt.stats, stats)

        attempt.updated_at = now
        await log_session.commit()



async def check_cancel(redis_client: redis.Redis, kb_doc_id: UUID) -> bool:
    """
    检查是否收到取消请求

    Args:
        redis_client: Redis 客户端
        kb_doc_id: 知识库文档 ID

    Returns:
        bool: 是否收到取消请求
    """
    cancel_key = f"parsing:cancel:{kb_doc_id}"
    return await redis_client.exists(cancel_key)


def set_runtime_stage(kb_doc: KnowledgeBaseDocument, stage: Optional[str]) -> None:
    """同步更新主表运行阶段。"""
    kb_doc.runtime_stage = stage
    kb_doc.runtime_updated_at = datetime.now()


def _merge_runtime_dict(base: Optional[Dict[str, Any]], incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """运行态 JSON 采用浅合并，避免覆盖无关阶段字段。"""
    merged = dict(base or {})
    if incoming:
        merged.update(incoming)
    return merged


async def upsert_kb_doc_runtime(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    *,
    pipeline_task_id: Optional[str] = None,
    effective_config: Optional[Dict[str, Any]] = None,
    parse_context: Optional[Dict[str, Any]] = None,
    chunk_context: Optional[Dict[str, Any]] = None,
    enhance_context: Optional[Dict[str, Any]] = None,
    tag_context: Optional[Dict[str, Any]] = None,
    summary_context: Optional[Dict[str, Any]] = None,
    stats: Optional[Dict[str, Any]] = None,
    error_detail: Optional[Dict[str, Any]] = None,
) -> KBDocRuntime:
    """latest-only 运行态写入。"""
    result = await session.execute(
        select(KBDocRuntime).where(KBDocRuntime.kb_doc_id == kb_doc.id)
    )
    runtime = result.scalar_one_or_none()
    now = datetime.now()

    if runtime is None:
        runtime = KBDocRuntime(
            kb_doc_id=kb_doc.id,
            tenant_id=kb_doc.tenant_id,
            kb_id=kb_doc.kb_id,
            document_id=kb_doc.document_id,
        )
        session.add(runtime)

    if pipeline_task_id is not None:
        runtime.pipeline_task_id = pipeline_task_id

    runtime.effective_config = _merge_runtime_dict(runtime.effective_config, effective_config)
    runtime.parse_context = _merge_runtime_dict(runtime.parse_context, parse_context)
    runtime.chunk_context = _merge_runtime_dict(runtime.chunk_context, chunk_context)
    runtime.enhance_context = _merge_runtime_dict(runtime.enhance_context, enhance_context)
    runtime.tag_context = _merge_runtime_dict(runtime.tag_context, tag_context)
    runtime.summary_context = _merge_runtime_dict(runtime.summary_context, summary_context)
    runtime.stats = _merge_runtime_dict(runtime.stats, stats)
    runtime.error_detail = _merge_runtime_dict(runtime.error_detail, error_detail)
    runtime.updated_at = now
    kb_doc.runtime_updated_at = now

    await session.flush()
    return runtime


async def reset_kb_doc_runtime(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    *,
    pipeline_task_id: Optional[str] = None,
    effective_config: Optional[Dict[str, Any]] = None,
) -> KBDocRuntime:
    """重置 latest-only 运行态，确保新任务不会继承旧上下文。"""
    result = await session.execute(
        select(KBDocRuntime).where(KBDocRuntime.kb_doc_id == kb_doc.id)
    )
    runtime = result.scalar_one_or_none()
    now = datetime.now()

    if runtime is None:
        runtime = KBDocRuntime(
            kb_doc_id=kb_doc.id,
            tenant_id=kb_doc.tenant_id,
            kb_id=kb_doc.kb_id,
            document_id=kb_doc.document_id,
        )
        session.add(runtime)

    runtime.pipeline_task_id = pipeline_task_id
    runtime.effective_config = dict(effective_config or {})
    runtime.parse_context = {}
    runtime.chunk_context = {}
    runtime.enhance_context = {}
    runtime.tag_context = {}
    runtime.summary_context = {}
    runtime.stats = {}
    runtime.error_detail = {}
    runtime.updated_at = now
    kb_doc.runtime_updated_at = now

    await session.flush()
    return runtime


async def cleanup_derived_documents_for_kb_doc(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
) -> None:
    """
    清理知识库文档的衍生文档引用。

    当前主要处理 markdown_document_id：
    - 删除衍生 Document 记录（若存在）
    - 清空 knowledge_base_documents.markdown_document_id 引用
    """
    if not kb_doc.markdown_document_id:
        return

    from models.document import Document

    derived_doc_id = kb_doc.markdown_document_id
    await session.execute(
        sql_delete(Document).where(Document.id == derived_doc_id)
    )
    kb_doc.markdown_document_id = None
    kb_doc.updated_at = datetime.now()
    await session.flush()


async def mark_cancelled(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    redis_client: redis.Redis,
    kb_doc_id: UUID
):
    """
    标记任务为已取消

    包含清理逻辑：
    - 删除已产生的分片数据（Chunk 表）
    - 重置 chunk_count
    - 更新状态和日志
    - 清理 Redis 取消标志

    Args:
        session: 数据库会话
        kb_doc: 知识库文档对象
        redis_client: Redis 客户端
        kb_doc_id: 知识库文档 ID
    """
    # 🔧 清理已产生的分片数据（防止取消后留下脏数据）
    # 场景：chunk_task 已提交分片到 DB，但后续的 enhance/train 检测到取消
    from sqlalchemy import delete as sql_delete
    from models.chunk import Chunk

    del_result = await session.execute(
        sql_delete(Chunk).where(Chunk.kb_doc_id == kb_doc_id)
    )
    deleted_chunks = cast(Any, del_result).rowcount
    if deleted_chunks > 0:
        logger.info(f"[mark_cancelled] 清理文档 {kb_doc_id} 的 {deleted_chunks} 个分片")

    kb_doc.parse_status = "cancelled"
    kb_doc.task_id = None
    kb_doc.parse_error = "任务已由用户取消"
    kb_doc.chunk_count = 0  # 🔧 重置分片计数
    kb_doc.parse_ended_at = datetime.now()
    kb_doc.updated_at = datetime.now()
    set_runtime_stage(kb_doc, "cancelled")
    await upsert_kb_doc_runtime(
        session,
        kb_doc,
        pipeline_task_id=None,
        stats={"chunk_count": 0},
        error_detail={
            "status": "cancelled",
            "message": kb_doc.parse_error,
            "updated_at": datetime.now().isoformat(),
        },
    )

    cancel_msg = "收到取消请求，停止处理"
    if deleted_chunks > 0:
        cancel_msg += f"，已清理 {deleted_chunks} 个分片"
    await add_log(session, kb_doc, "CANCEL", cancel_msg, "cancelled")
    await sync_latest_attempt_snapshot(
        session,
        kb_doc,
        status="cancelled",
        runtime_stage="cancelled",
        task_id=None,
        error_message=kb_doc.parse_error,
        stats={"chunk_count": 0},
    )
    await finalize_latest_attempt(
        session,
        kb_doc.id,
        final_status="cancelled",
    )

    await upsert_kb_doc_runtime(
        session,
        kb_doc,
        pipeline_task_id=None,
        stats={"chunk_count": int(kb_doc.chunk_count or 0)},
    )

    await session.commit()

    # 清理取消标志
    cancel_key = f"parsing:cancel:{kb_doc_id}"
    await redis_client.delete(cancel_key)


async def mark_failed(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    error_msg: str
):
    """
    标记任务失败

    Args:
        session: 数据库会话
        kb_doc: 知识库文档对象
        error_msg: 错误消息
    """
    kb_doc.parse_status = "failed"
    kb_doc.parse_error = error_msg
    kb_doc.task_id = None
    kb_doc.parse_ended_at = datetime.now()
    kb_doc.updated_at = datetime.now()
    set_runtime_stage(kb_doc, "failed")
    await upsert_kb_doc_runtime(
        session,
        kb_doc,
        pipeline_task_id=None,
        error_detail={
            "status": "failed",
            "message": error_msg,
            "updated_at": datetime.now().isoformat(),
        },
    )

    await add_log(session, kb_doc, "ERROR", f"发生错误: {error_msg}", "error")
    await sync_latest_attempt_snapshot(
        session,
        kb_doc,
        status="failed",
        runtime_stage="failed",
        task_id=None,
        error_message=error_msg,
    )
    await finalize_latest_attempt(
        session,
        kb_doc.id,
        final_status="failed",
        error_msg=error_msg,
    )


async def mark_completed(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    message: str = "所有处理步骤已完成"
):
    """
    标记任务完成

    Args:
        session: 数据库会话
        kb_doc: 知识库文档对象
        message: 完成消息
    """
    # 🔧 修复：如果状态是 cancelling，说明用户已经请求取消，不要改为 completed
    if kb_doc.parse_status == "cancelling":
        logger.warning(f"文档 {kb_doc.id} 状态为 cancelling，改为 cancelled 而不是 completed")

        # 🔧 清理已产生的分片数据（任务链可能已经走到最后一步，分片数据已全量入库）
        from sqlalchemy import delete as sql_delete
        from models.chunk import Chunk

        del_result = await session.execute(
            sql_delete(Chunk).where(Chunk.kb_doc_id == kb_doc.id)
        )
        deleted_chunks = cast(Any, del_result).rowcount
        if deleted_chunks > 0:
            logger.info(f"[mark_completed→cancelled] 清理文档 {kb_doc.id} 的 {deleted_chunks} 个分片")

        kb_doc.parse_status = "cancelled"
        kb_doc.task_id = None
        set_runtime_stage(kb_doc, "cancelled")
        kb_doc.parse_error = "任务已取消（完成前收到取消请求）"
        kb_doc.chunk_count = 0  # 🔧 重置分片计数
        cancel_msg = "任务完成前收到取消请求"
        if deleted_chunks > 0:
            cancel_msg += f"，已清理 {deleted_chunks} 个分片"
        await add_log(session, kb_doc, "CANCEL", cancel_msg, "cancelled")
        await sync_latest_attempt_snapshot(
            session,
            kb_doc,
            status="cancelled",
            runtime_stage="cancelled",
            task_id=None,
            error_message=kb_doc.parse_error,
            stats={"chunk_count": 0},
        )
        await finalize_latest_attempt(
            session,
            kb_doc.id,
            final_status="cancelled",
            duration_ms=kb_doc.parse_duration_milliseconds,
        )
    else:
        kb_doc.parse_status = "completed"
        kb_doc.parse_error = None
        kb_doc.task_id = None
        set_runtime_stage(kb_doc, "completed")
        await add_log(session, kb_doc, "FINISH", message, "done")
        await sync_latest_attempt_snapshot(
            session,
            kb_doc,
            status="completed",
            runtime_stage="completed",
            task_id=None,
            error_message=None,
            stats={
                "chunk_count": int(kb_doc.chunk_count or 0),
                "parse_duration_milliseconds": kb_doc.parse_duration_milliseconds,
            },
        )
        await finalize_latest_attempt(
            session,
            kb_doc.id,
            final_status="completed",
            duration_ms=kb_doc.parse_duration_milliseconds,
        )

    kb_doc.parse_ended_at = datetime.now()
    kb_doc.updated_at = datetime.now()

    await upsert_kb_doc_runtime(
        session,
        kb_doc,
        pipeline_task_id=None,
        stats={
            "chunk_count": int(kb_doc.chunk_count or 0),
            "parse_duration_milliseconds": kb_doc.parse_duration_milliseconds,
        },
        error_detail={},
    )


@asynccontextmanager
async def document_lock(kb_doc_id: UUID, redis_client: redis.Redis, timeout: int = 720):
    """
    文档解析分布式锁（带心跳续期机制）

    防止同一文档被多个 Worker 并发解析

    Args:
        kb_doc_id: 知识库文档 ID
        redis_client: Redis 客户端
        timeout: 锁超时时间（秒），默认 12 分钟

    Raises:
        ValueError: 如果文档正在被其他任务解析
    """
    lock_key = f"parsing:lock:{kb_doc_id}"

    # 创建 Redis 锁
    lock = redis_client.lock(
        lock_key,
        timeout=timeout,
        blocking_timeout=0
    )

    # 尝试获取锁
    acquired = await lock.acquire(blocking=False)

    if not acquired:
        ttl = await redis_client.ttl(lock_key)
        logger.warning(f"文档 {kb_doc_id} 正在被其他任务解析，跳过 (锁剩余时间: {ttl}秒)")
        raise ValueError(f"文档 {kb_doc_id} 正在被其他任务解析，请稍后重试")

    # 启动锁续期任务
    stop_renew = asyncio.Event()
    renewal_count = 0
    max_renewals = 10

    async def renew_lock_periodically():
        """定期续期锁（每 5 分钟续期一次，延长 10 分钟）"""
        nonlocal renewal_count

        try:
            while not stop_renew.is_set() and renewal_count < max_renewals:
                try:
                    await asyncio.wait_for(stop_renew.wait(), timeout=300)
                    break
                except asyncio.TimeoutError:
                    pass

                # 验证锁所有权
                try:
                    lock_value = await redis_client.get(lock_key)
                    lock_token = lock.local.token
                    if isinstance(lock_token, str):
                        lock_token = lock_token.encode('utf-8')
                    if isinstance(lock_value, str):
                        lock_value = lock_value.encode('utf-8')

                    if lock_value != lock_token:
                        logger.error(f"文档 {kb_doc_id} 锁所有权已变更，停止续期")
                        break

                    # 续期锁
                    await lock.extend(600)
                    renewal_count += 1
                    logger.info(f"文档 {kb_doc_id} 解析锁续期成功 (第 {renewal_count}/{max_renewals} 次)")

                except Exception as e:
                    logger.error(f"文档 {kb_doc_id} 解析锁续期失败: {e}")
                    break

        except asyncio.CancelledError:
            logger.debug(f"文档 {kb_doc_id} 续期任务被取消")
            raise
        except Exception as e:
            logger.error(f"文档 {kb_doc_id} 锁续期任务异常: {e}", exc_info=True)

    renew_task = asyncio.create_task(renew_lock_periodically())

    try:
        logger.info(f"获取文档 {kb_doc_id} 解析锁成功")
        yield
    finally:
        # 停止续期任务
        if renew_task and not renew_task.done():
            stop_renew.set()
            try:
                await asyncio.wait_for(renew_task, timeout=1.0)
            except asyncio.TimeoutError:
                renew_task.cancel()
                try:
                    await renew_task
                except asyncio.CancelledError:
                    pass

        # 释放锁
        try:
            await lock.release()
            logger.info(f"释放文档 {kb_doc_id} 解析锁 (共续期 {renewal_count} 次)")
        except Exception as e:
            logger.warning(f"释放锁失败（可能已超时）: {e}")
