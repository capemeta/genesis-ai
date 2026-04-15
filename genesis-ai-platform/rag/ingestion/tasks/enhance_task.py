"""
分块增强任务

整合状态管理和日志记录
I/O 密集型任务，使用异步实现高并发
"""

import asyncio
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime

import redis.exceptions as redis_exc
from sqlalchemy import select

from core.config import settings
from tasks.celery_tasks import celery_app
from core.database.session import create_task_redis_client, close_task_redis_client, create_task_session_maker, close_task_db_engine
from models.knowledge_base_document import KnowledgeBaseDocument
from models.knowledge_base import KnowledgeBase
from models.chunk import Chunk
from rag.ingestion.enhancers import (
    EnhancerFactory,
    build_enhancer_runtime_config,
    decide_chunk_enhancement,
    normalize_enhancement_config,
)
from .common import (
    add_log,
    build_effective_config,
    check_cancel,
    mark_cancelled,
    mark_failed,
    set_runtime_stage,
    sync_latest_attempt_snapshot,
    upsert_kb_doc_runtime,
)
import logging

logger = logging.getLogger(__name__)


@celery_app.task(
    name="rag.ingestion.tasks.enhance_chunks_task",
    bind=True,
    max_retries=3,
    soft_time_limit=600,
    time_limit=660,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
)
def enhance_chunks_task(
    self,
    kb_doc_id: str,
    segment_ids: List[str],
    enhancer_config: Dict[str, Any] | None = None
):
    """
    分块增强任务（整合状态管理）
    
    I/O 密集型任务，使用异步实现高并发
    
    Args:
        kb_doc_id: 知识库文档 ID
        segment_ids: 分块 ID 列表
        enhancer_config: 增强器配置
    
    部署示例：
        celery -A tasks worker -Q enhance --pool=gevent --concurrency=50
    """
    logger.info(f"[EnhanceTask] 开始增强: {kb_doc_id}, 分块数: {len(segment_ids)}")
    
    # 使用 asyncio.run 运行异步代码
    async def _run_enhance():
        # 为当前 event loop 创建独立的数据库引擎和 Redis 客户端
        task_engine, task_sm = create_task_session_maker()
        redis_client = create_task_redis_client()
        try:
            await _do_enhance_chunks(
                UUID(kb_doc_id),
                segment_ids,
                enhancer_config,
                redis_client,
                task_sm
            )
        finally:
            await close_task_redis_client(redis_client)
            await close_task_db_engine(task_engine)
    
    try:
        asyncio.run(_run_enhance())
        logger.info(f"[EnhanceTask] 增强完成: {kb_doc_id}")
        return {"status": "success", "kb_doc_id": kb_doc_id}
        
    except Exception as e:
        logger.error(f"[EnhanceTask] 增强失败: {kb_doc_id}, 错误: {str(e)}", exc_info=True)
        # 重试次数达上限则标记文档失败
        if self.request.retries >= self.max_retries:
            logger.error(f"[EnhanceTask] 增强重试次数已达上限: kb_doc_id={kb_doc_id}")

            async def _mark_failed():
                # mark_failed 只做 DB 操作，独立引擎避免跨 loop 问题
                me, ms = create_task_session_maker()
                try:
                    async with ms() as session:
                        stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id == UUID(kb_doc_id))
                        result = await session.execute(stmt)
                        kb_doc = result.scalar_one_or_none()
                        if kb_doc:
                            await mark_failed(session, kb_doc, f"增强失败（已重试 {self.max_retries} 次）: {str(e)}")
                            await session.commit()
                finally:
                    await close_task_db_engine(me)

            try:
                asyncio.run(_mark_failed())
            except Exception as mark_err:
                logger.error(f"[EnhanceTask] 标记失败状态也失败了: {mark_err}")
            return {"status": "failed", "kb_doc_id": kb_doc_id, "error": str(e)}
        # Redis/网络超时给予更长 countdown，便于服务恢复后重试
        is_timeout = isinstance(e, (redis_exc.TimeoutError, redis_exc.ConnectionError, TimeoutError))
        countdown = min(60, 10 * (2 ** self.request.retries)) if is_timeout else (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)


async def _do_enhance_chunks(
    kb_doc_id: UUID,
    segment_ids: List[str],
    enhancer_config: Dict[str, Any] | None = None,
    redis_client = None,
    session_maker = None
):
    """实际的增强逻辑
    
    Args:
        kb_doc_id: 文档 ID
        segment_ids: 分块 ID 列表
        enhancer_config: 增强配置
        redis_client: Redis 客户端（必须在当前 event loop 中创建）
        session_maker: 数据库 session 工厂（必须在当前 event loop 中创建）
    """
    async with session_maker() as session:
        try:
            # 1. 获取文档信息
            stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id == kb_doc_id)
            result = await session.execute(stmt)
            kb_doc = result.scalar_one_or_none()
            
            if not kb_doc:
                logger.error(f"[EnhanceTask] KnowledgeBaseDocument {kb_doc_id} 不存在")
                return

            kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_doc.kb_id)
            kb_result = await session.execute(kb_stmt)
            kb = kb_result.scalar_one_or_none()
            effective_config = build_effective_config(
                kb_doc,
                {
                    "enhancer_config": enhancer_config or {},
                },
                kb=kb,
            )
            effective_enhancement_config = normalize_enhancement_config(
                dict(effective_config.get("effective_enhancement_config") or {})
            )
            
            # 检查取消标志
            if await check_cancel(redis_client, kb_doc_id):
                logger.info(f"[EnhanceTask] 文档 {kb_doc_id} 收到取消请求，停止增强")
                await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                return
            
            # 2. 更新状态
            set_runtime_stage(kb_doc, "enhancing")
            await add_log(session, kb_doc, "ENHANCE", f"开始增强 {len(segment_ids)} 个分块...", "processing")
            await sync_latest_attempt_snapshot(
                session,
                kb_doc,
                runtime_stage="enhancing",
                config_snapshot=effective_config,
                stats={"chunk_count": len(segment_ids)},
            )
            await upsert_kb_doc_runtime(
                session,
                kb_doc,
                pipeline_task_id=kb_doc.task_id,
                effective_config=effective_config,
                stats={"chunk_count": len(segment_ids)},
            )
            await session.commit()
            
            # 3. 加载分块数据并进行 selector 筛选
            chunks = await _load_chunks_async(segment_ids, session_maker)
            selected_chunks: list[dict[str, Any]] = []
            skipped_count = 0
            capability_stats = {"summary": 0, "keywords": 0, "questions": 0}

            for chunk in chunks:
                decision = decide_chunk_enhancement(
                    chunk=chunk,
                    enhancement_config=effective_enhancement_config,
                    kb_type=str((kb.type if kb else "") or ""),
                )
                chunk["enhancement_decision"] = {
                    "should_enhance": decision.should_enhance,
                    "enable_summary": decision.enable_summary,
                    "enable_keywords": decision.enable_keywords,
                    "enable_questions": decision.enable_questions,
                    "reason_code": decision.reason_code,
                    "reason_detail": decision.reason_detail,
                }
                if not decision.should_enhance:
                    skipped_count += 1
                    continue
                if decision.enable_summary:
                    capability_stats["summary"] += 1
                if decision.enable_keywords:
                    capability_stats["keywords"] += 1
                if decision.enable_questions:
                    capability_stats["questions"] += 1
                chunk["enhancer_runtime_config"] = build_enhancer_runtime_config(
                    enhancement_config=effective_enhancement_config,
                    decision=decision,
                )
                selected_chunks.append(chunk)

            logger.info(
                "[EnhanceTask] selector 完成: total=%s, selected=%s, skipped=%s",
                len(chunks),
                len(selected_chunks),
                skipped_count,
            )

            if not selected_chunks:
                await add_log(session, kb_doc, "ENHANCE", "未命中可增强分块，跳过增强阶段", "done")
                set_runtime_stage(kb_doc, "indexing")
                await upsert_kb_doc_runtime(
                    session,
                    kb_doc,
                    pipeline_task_id=kb_doc.task_id,
                    enhance_context={
                        "selected_chunk_count": 0,
                        "skipped_chunk_count": len(chunks),
                        "capability_stats": capability_stats,
                    },
                )
                await session.commit()
                from .train_task import train_document_task
                train_document_task.delay(str(kb_doc_id), segment_ids)
                return
            
            # 4. 并发增强所有入选分块
            # 注意：LLMExecutor 会使用任务级 session_maker，避免 Celery 多次 asyncio.run()
            # 复用全局 SQLAlchemy 异步连接池导致 event loop 绑定错误。
            task_enhance_concurrency = max(
                1,
                min(int(settings.RAG_LLM_CONCURRENCY or 10), 8, len(selected_chunks)),
            )
            enhance_semaphore = asyncio.Semaphore(task_enhance_concurrency)

            async def enhance_single_chunk(c):
                async with enhance_semaphore:
                    enhanced = c.copy()
                    enhancers = EnhancerFactory.create_enhancers(
                        c.get("enhancer_runtime_config") or {},
                        llm_session_maker=session_maker,
                    )
                    for enhancer in enhancers:
                        enhanced = await enhancer.enhance(enhanced)
                    return enhanced

            logger.info(
                "[EnhanceTask] 开始 LLM 增强: selected=%s, concurrency=%s",
                len(selected_chunks),
                task_enhance_concurrency,
            )
            enhanced_chunks = await asyncio.gather(
                *(enhance_single_chunk(chunk) for chunk in selected_chunks)
            )
            
            # 🔧 增强完成后再次检查取消标志（增强可能耗时较长）
            if await check_cancel(redis_client, kb_doc_id):
                logger.info(f"[EnhanceTask] 文档 {kb_doc_id} 增强后收到取消请求，停止处理")
                await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                return
            
            # 5. 保存增强结果
            logger.info(f"[EnhanceTask] 保存增强结果: {len(enhanced_chunks)} 个")
            await _save_enhanced_chunks_async(segment_ids, enhanced_chunks, session_maker)
            
            # 6. 更新状态
            kb_doc.updated_at = datetime.now()
            await add_log(session, kb_doc, "ENHANCE", f"增强完成，处理 {len(enhanced_chunks)} 个分块", "done")
            set_runtime_stage(kb_doc, "indexing")
            await sync_latest_attempt_snapshot(
                session,
                kb_doc,
                runtime_stage="indexing",
                stats={
                    "chunk_count": len(enhanced_chunks),
                    "enhanced_chunk_count": len(enhanced_chunks),
                },
            )
            await upsert_kb_doc_runtime(
                session,
                kb_doc,
                pipeline_task_id=kb_doc.task_id,
                enhance_context={
                    "enhanced_chunk_count": len(enhanced_chunks),
                    "selected_chunk_count": len(selected_chunks),
                    "skipped_chunk_count": skipped_count,
                    "capability_stats": capability_stats,
                },
                stats={"chunk_count": len(enhanced_chunks)},
                error_detail={},
            )
            await session.commit()
            
            # 7. 触发训练任务
            logger.info(f"[EnhanceTask] 触发训练任务: {kb_doc_id}")
            from .train_task import train_document_task
            train_document_task.delay(str(kb_doc_id), segment_ids)
                
        except Exception as e:
            logger.exception(f"[EnhanceTask] 增强失败: {kb_doc_id}, 错误: {str(e)}")
            await session.rollback()
            raise
        finally:
            # LLM 并发控制已经统一下沉到 executor，任务层不再重复占用租约。
            pass


async def _load_chunks_async(segment_ids: List[str], session_maker) -> List[Dict[str, Any]]:
    """
    异步加载分块数据
    
    Args:
        segment_ids: 分块 ID 列表
        session_maker: 数据库 session 工厂
    """
    if not segment_ids:
        return []
        
    logger.info(f"[EnhanceTask] 加载分块: {len(segment_ids)} 个")
    
    chunks_data = []
    async with session_maker() as session:
        # 将字符串 ID 转换为整数 ID (Chunk 表的主键是 int)
        # 注意：这里假设 segment_ids 传过来的是字符串形式的 int
        # 如果 segment_ids 是 UUID，则需要调整逻辑，但在 chunk_task 中我们看到 id 是 int
        try:
            int_ids = [int(sid) for sid in segment_ids]
            stmt = select(Chunk).where(Chunk.id.in_(int_ids))
            result = await session.execute(stmt)
            chunks = result.scalars().all()
            
            # 保持顺序
            chunk_map = {c.id: c for c in chunks}
            
            for sid in int_ids:
                if sid in chunk_map:
                    c = chunk_map[sid]
                    chunks_data.append({
                        "id": str(c.id),
                        "tenant_id": str(c.tenant_id),
                        "kb_id": str(c.kb_id),
                        "kb_doc_id": str(c.kb_doc_id),
                        "content": c.content,
                        "text": c.content,
                        "metadata": dict(c.metadata_info or {}),
                        "metadata_info": dict(c.metadata_info or {}),
                        "chunk_type": c.chunk_type,
                        "type": c.chunk_type,
                        "text_length": int(c.text_length or len(c.content or "")),
                        "source_type": c.source_type,
                        "display_enabled": bool(c.display_enabled),
                    })
        except ValueError:
            logger.error(f"[EnhanceTask] segment_ids 包含非整数 ID: {segment_ids}")
            return []
            
    return chunks_data


async def _save_enhanced_chunks_async(
    segment_ids: List[str],
    enhanced_chunks: List[Dict[str, Any]],
    session_maker = None
):
    """
    异步保存增强结果
    
    Args:
        segment_ids: 分块 ID 列表
        enhanced_chunks: 增强后的分块数据
        session_maker: 数据库 session 工厂
    """
    if not enhanced_chunks:
        return

    logger.info(f"[EnhanceTask] 保存增强结果: {len(enhanced_chunks)} 个")
    
    async with session_maker() as session:
        try:
            for chunk_data in enhanced_chunks:
                # 确保有 ID
                if "id" not in chunk_data:
                    continue
                    
                chunk_id = int(chunk_data["id"])
                
                # 现在的 chunk_data 可能是增强后的，结构可能不同
                # 至少应该包含 metadata 更新
                new_metadata = dict(chunk_data.get("metadata") or {})
                
                # 执行更新
                # 注意：这里我们主要更新 metadata_info，因为增强主要是改 metadata (如增加 summary, tags, qa)
                # 如果增强器修改了 content (text)，也应该更新
                update_values = {"metadata_info": new_metadata}
                
                if "text" in chunk_data:
                     update_values["content"] = chunk_data["text"]
                     
                if "summary" in chunk_data:
                     update_values["summary"] = chunk_data["summary"]
                
                from sqlalchemy import update
                stmt = update(Chunk).where(Chunk.id == chunk_id).values(**update_values)
                await session.execute(stmt)
                
            await session.commit()
        except Exception as e:
            logger.error(f"[EnhanceTask] 保存增强结果失败: {str(e)}")
            await session.rollback()
            raise
