"""
文档训练任务（向量化、摘要等）

整合状态管理和日志记录
I/O 密集型任务，使用异步实现高并发
"""

import asyncio
from typing import List, Dict, Any
from uuid import UUID

import redis.exceptions as redis_exc
from sqlalchemy import select, text

from tasks.celery_tasks import celery_app
from core.database.session import create_task_redis_client, close_task_redis_client, create_task_session_maker, close_task_db_engine
from models.chunk import Chunk
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from rag.lexical import SearchUnitLexicalIndexService
from rag.search_units import build_search_units_for_chunks, delete_search_projections_for_chunk_ids
from rag.vectorization import SearchUnitEmbeddingService
from .common import (
    add_log,
    build_effective_config,
    check_cancel,
    mark_cancelled,
    mark_completed,
    mark_failed,
    set_runtime_stage,
    sync_latest_attempt_snapshot,
    upsert_kb_doc_runtime,
)
import logging

logger = logging.getLogger(__name__)


@celery_app.task(
    name="rag.ingestion.tasks.train_document_task",
    bind=True,
    max_retries=3,
    soft_time_limit=600,
    time_limit=660,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
)
def train_document_task(
    self,
    kb_doc_id: str,
    segment_ids: List[str],
    enable_kg: bool = False
):
    """
    训练任务（整合状态管理）：向量化、摘要、提取问题、提取关键词
    
    I/O 密集型任务，使用异步实现高并发
    
    Args:
        kb_doc_id: 知识库文档 ID
        segment_ids: 分块 ID 列表
        enable_kg: 是否启用知识图谱
    
    部署示例：
        celery -A tasks worker -Q train --pool=gevent --concurrency=100
    """
    logger.info(f"[TrainTask] 开始训练: {kb_doc_id}, 分块数: {len(segment_ids)}")
    
    # 使用 asyncio.run 运行异步代码
    async def _run_train():
        # 为当前 event loop 创建独立的数据库引擎和 Redis 客户端
        task_engine, task_sm = create_task_session_maker()
        redis_client = create_task_redis_client()
        try:
            await _do_train_document(
                UUID(kb_doc_id),
                segment_ids,
                enable_kg,
                redis_client,
                task_sm
            )
        finally:
            await close_task_redis_client(redis_client)
            await close_task_db_engine(task_engine)
    
    try:
        asyncio.run(_run_train())
        logger.info(f"[TrainTask] 训练完成: {kb_doc_id}")
        return {"status": "success", "kb_doc_id": kb_doc_id}
        
    except Exception as e:
        logger.error(f"[TrainTask] 训练失败: {kb_doc_id}, 错误: {str(e)}", exc_info=True)
        # 重试次数达上限则标记文档失败
        if self.request.retries >= self.max_retries:
            logger.error(f"[TrainTask] 训练重试次数已达上限: kb_doc_id={kb_doc_id}")

            async def _mark_failed():
                # mark_failed 只做 DB 操作，独立引擎避免跨 loop 问题
                me, ms = create_task_session_maker()
                try:
                    async with ms() as session:
                        stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id == UUID(kb_doc_id))
                        result = await session.execute(stmt)
                        kb_doc = result.scalar_one_or_none()
                        if kb_doc:
                            await mark_failed(session, kb_doc, f"训练失败（已重试 {self.max_retries} 次）: {str(e)}")
                            await session.commit()
                finally:
                    await close_task_db_engine(me)

            try:
                asyncio.run(_mark_failed())
            except Exception as mark_err:
                logger.error(f"[TrainTask] 标记失败状态也失败了: {mark_err}")
            return {"status": "failed", "kb_doc_id": kb_doc_id, "error": str(e)}
        # Redis/网络超时给予更长 countdown，便于服务恢复后重试
        is_timeout = isinstance(e, (redis_exc.TimeoutError, redis_exc.ConnectionError, TimeoutError))
        countdown = min(60, 10 * (2 ** self.request.retries)) if is_timeout else (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)


async def _do_train_document(
    kb_doc_id: UUID,
    segment_ids: List[str],
    enable_kg: bool = False,
    redis_client = None,
    session_maker = None
):
    """实际的训练逻辑
    
    Args:
        kb_doc_id: 文档 ID
        segment_ids: 分块 ID 列表
        enable_kg: 是否启用知识图谱
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
                logger.error(f"[TrainTask] KnowledgeBaseDocument {kb_doc_id} 不存在")
                return

            kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_doc.kb_id)
            kb_result = await session.execute(kb_stmt)
            kb = kb_result.scalar_one_or_none()
            
            # 检查取消标志
            if await check_cancel(redis_client, kb_doc_id):
                logger.info(f"[TrainTask] 文档 {kb_doc_id} 收到取消请求，停止训练")
                await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                return
            
            # 2. 更新状态
            set_runtime_stage(kb_doc, "indexing")
            await add_log(session, kb_doc, "TRAIN", f"开始向量化 {len(segment_ids)} 个分块...", "processing")
            await sync_latest_attempt_snapshot(
                session,
                kb_doc,
                runtime_stage="indexing",
                config_snapshot=build_effective_config(
                    kb_doc,
                    {
                        "enable_kg": enable_kg,
                    },
                ),
                stats={"chunk_count": len(segment_ids)},
            )
            await upsert_kb_doc_runtime(
                session,
                kb_doc,
                pipeline_task_id=kb_doc.task_id,
                effective_config=build_effective_config(
                    kb_doc,
                    {
                        "enable_kg": enable_kg,
                    },
                ),
                stats={"chunk_count": len(segment_ids)},
            )
            await session.commit()
            
            rebuild_summary = await _rebuild_search_units_async(
                session=session,
                kb_doc=kb_doc,
                kb=kb,
                segment_ids=segment_ids,
            )
            # 检索投影重建需要先提交，后续独立 session 的向量化/全文索引子任务
            # 才能读取到这批最新的 search_unit，避免索引写到旧 search_unit_id 上。
            await session.commit()
            logger.info(
                "[TrainTask] 检索投影已提交，准备启动索引子任务: kb_doc_id=%s, search_unit_count=%s",
                kb_doc_id,
                int(rebuild_summary.get("search_unit_count") or 0),
            )
            
            # 3. 基础训练任务（并发执行）
            tasks = [
                _vectorize_segments_with_isolated_session_async(
                    session_maker=session_maker,
                    kb=kb,
                    segment_ids=segment_ids,
                    redis_client=redis_client,
                ),
                _build_lexical_indexes_with_isolated_session_async(
                    session_maker=session_maker,
                    segment_ids=segment_ids,
                ),
            ]
            
            # 4. 如果启用知识图谱，添加知识图谱构建任务
            if enable_kg:
                logger.info(f"[TrainTask] 启用知识图谱构建")
                # TODO: 添加知识图谱构建任务
                # tasks.append(_build_knowledge_graph_async(kb_doc_id, segment_ids))
            
            # 5. 并发执行所有任务
            results = await asyncio.gather(*tasks)
            vector_result = results[0] if results else {}
            lexical_result = results[1] if len(results) > 1 else {}
            logger.info(
                "[TrainTask] 并发子任务完成: kb_doc_id=%s, vectorized=%s, lexical_indexed=%s",
                kb_doc_id,
                int(vector_result.get("vectorized_count") or 0),
                int(lexical_result.get("indexed_count") or 0),
            )
            await _log_search_projection_consistency(
                session=session,
                kb_doc_id=kb_doc_id,
            )
            
            # 🔧 向量化可能耗时较长，完成后做最终取消检查
            if await check_cancel(redis_client, kb_doc_id):
                logger.info(f"[TrainTask] 文档 {kb_doc_id} 训练后收到取消请求，停止处理")
                await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                return
            
            # 🔧 刷新 kb_doc 的 DB 状态，防止使用过期的内存缓存
            # 场景：用户在向量化期间点了取消 → API 更新 DB 为 cancelling
            # 但 task 的 kb_doc 对象还是旧的 "processing"，mark_completed 检测不到
            await session.refresh(kb_doc)
            logger.info("[TrainTask] 文档状态刷新完成，准备进入 finalizing: kb_doc_id=%s", kb_doc_id)
            
            # 6. 更新状态为完成
            logger.info(f"[TrainTask] 训练完成: {kb_doc_id}")
            set_runtime_stage(kb_doc, "finalizing")
            await sync_latest_attempt_snapshot(
                session,
                kb_doc,
                runtime_stage="finalizing",
                stats={
                    "chunk_count": len(segment_ids),
                    "vectorized_count": int(vector_result.get("vectorized_count") or 0),
                    "lexical_indexed_count": int(lexical_result.get("indexed_count") or 0),
                    "search_unit_count": int(rebuild_summary.get("search_unit_count") or 0),
                },
            )
            await upsert_kb_doc_runtime(
                session,
                kb_doc,
                pipeline_task_id=kb_doc.task_id,
                summary_context={
                    "vectorized_count": int(vector_result.get("vectorized_count") or 0),
                    "vector_cache_hit_count": int(vector_result.get("cache_hit_count") or 0),
                    "vector_cache_miss_count": int(vector_result.get("cache_miss_count") or 0),
                    "vector_model_name": vector_result.get("model_name"),
                    "lexical_indexed_count": int(lexical_result.get("indexed_count") or 0),
                    "search_unit_count": int(rebuild_summary.get("search_unit_count") or 0),
                },
                stats={"chunk_count": len(segment_ids)},
                error_detail={},
            )
            logger.info("[TrainTask] finalizing 运行态写入完成: kb_doc_id=%s", kb_doc_id)
            await mark_completed(session, kb_doc, f"所有处理步骤已完成，共处理 {len(segment_ids)} 个分块")
            logger.info("[TrainTask] mark_completed 完成，准备提交事务: kb_doc_id=%s", kb_doc_id)
            await session.commit()
            logger.info("[TrainTask] 事务提交完成: kb_doc_id=%s", kb_doc_id)
            
            # 清理取消标志（如果存在）
            cancel_key = f"parsing:cancel:{kb_doc_id}"
            await redis_client.delete(cancel_key)
            logger.info("[TrainTask] 取消标记清理完成: kb_doc_id=%s", kb_doc_id)
            
        except Exception as e:
            logger.exception(f"[TrainTask] 训练失败: {kb_doc_id}, 错误: {str(e)}")
            await session.rollback()
            raise


async def _vectorize_segments_async(
    *,
    session,
    kb: KnowledgeBase | None,
    segment_ids: List[str],
    redis_client,
) -> Dict[str, Any]:
    """
    基于 search_unit 的异步向量化实现。
    """
    logger.info(f"[VectorizeTask] 开始向量化: {len(segment_ids)} 个分块")
    if kb is None:
        raise RuntimeError("知识库不存在，无法执行向量化")

    try:
        chunk_ids = [int(item) for item in segment_ids]
    except ValueError as exc:
        raise RuntimeError("segment_ids 中包含非法 chunk id，无法执行向量化") from exc

    service = SearchUnitEmbeddingService(session, redis_client=redis_client)
    result = await service.build_vectors_for_chunk_ids(kb=kb, chunk_ids=chunk_ids)
    logger.info(
        "[VectorizeTask] 向量化完成: vectorized=%s, cache_hit=%s, cache_miss=%s",
        result.get("vectorized_count"),
        result.get("cache_hit_count"),
        result.get("cache_miss_count"),
    )
    return result


async def _vectorize_segments_with_isolated_session_async(
    *,
    session_maker,
    kb: KnowledgeBase | None,
    segment_ids: List[str],
    redis_client,
) -> Dict[str, Any]:
    """为向量化创建独立数据库会话，避免与其他并发子任务共享 AsyncSession。"""
    async with session_maker() as isolated_session:
        result = await _vectorize_segments_async(
            session=isolated_session,
            kb=kb,
            segment_ids=segment_ids,
            redis_client=redis_client,
        )
        await isolated_session.commit()
        return result


async def _build_lexical_indexes_async(
    *,
    session,
    segment_ids: List[str],
) -> Dict[str, Any]:
    """基于 search_unit 的全文索引构建。"""
    logger.info(f"[LexicalTask] 开始构建全文索引: {len(segment_ids)} 个分块")
    try:
        chunk_ids = [int(item) for item in segment_ids]
    except ValueError as exc:
        raise RuntimeError("segment_ids 中包含非法 chunk id，无法执行全文索引构建") from exc

    service = SearchUnitLexicalIndexService(session)
    result = await service.build_indexes_for_chunk_ids(chunk_ids=chunk_ids)
    logger.info(
        "[LexicalTask] 全文索引构建完成: indexed=%s",
        result.get("indexed_count"),
    )
    return result


async def _build_lexical_indexes_with_isolated_session_async(
    *,
    session_maker,
    segment_ids: List[str],
) -> Dict[str, Any]:
    """为全文索引构建创建独立数据库会话，避免并发共享 AsyncSession。"""
    async with session_maker() as isolated_session:
        result = await _build_lexical_indexes_async(
            session=isolated_session,
            segment_ids=segment_ids,
        )
        await isolated_session.commit()
        return result


async def _rebuild_search_units_async(
    *,
    session,
    kb_doc: KnowledgeBaseDocument,
    kb: KnowledgeBase | None,
    segment_ids: List[str],
) -> Dict[str, Any]:
    """增强完成后按 chunk 删旧重建检索投影。"""
    if not segment_ids:
        return {"chunk_count": 0, "search_unit_count": 0}

    try:
        chunk_ids = [int(item) for item in segment_ids]
    except ValueError:
        logger.warning("[TrainTask] segment_ids 含非法 chunk id，跳过检索投影重建: %s", segment_ids)
        return {"chunk_count": 0, "search_unit_count": 0}

    stmt = (
        select(Chunk)
        .where(Chunk.id.in_(chunk_ids))
        .order_by(Chunk.id.asc())
    )
    result = await session.execute(stmt)
    chunks = list(result.scalars().all())
    if not chunks:
        return {"chunk_count": 0, "search_unit_count": 0}

    await delete_search_projections_for_chunk_ids(session, chunk_ids)
    new_search_units = build_search_units_for_chunks(
        chunks=chunks,
        kb_type=str((kb.type if kb else "") or ""),
        retrieval_config=dict((kb.retrieval_config or {}) if kb else {}),
        kb_doc_summary=str(kb_doc.summary or "").strip() or None,
    )
    if new_search_units:
        session.add_all(new_search_units)
        await session.flush()

    logger.info(
        "[TrainTask] 检索投影重建完成: chunk_count=%s, search_unit_count=%s",
        len(chunks),
        len(new_search_units),
    )
    return {
        "chunk_count": len(chunks),
        "search_unit_count": len(new_search_units),
    }


async def _log_search_projection_consistency(
    *,
    session,
    kb_doc_id: UUID,
) -> None:
    """记录训练后 search_unit / 向量索引 / 全文索引的一致性摘要。"""
    stmt = text(
        """
        SELECT
            COUNT(*)::bigint AS search_unit_count,
            COUNT(vec.id)::bigint AS vector_count,
            COUNT(lex.id)::bigint AS lexical_count
        FROM chunk_search_units su
        LEFT JOIN pg_chunk_search_unit_vectors vec
            ON vec.search_unit_id = su.id
           AND vec.is_active = true
        LEFT JOIN pg_chunk_search_unit_lexical_indexes lex
            ON lex.search_unit_id = su.id
           AND lex.is_active = true
        WHERE su.kb_doc_id = CAST(:kb_doc_id AS uuid)
          AND su.is_active = true
        """
    )
    result = await session.execute(stmt, {"kb_doc_id": str(kb_doc_id)})
    row = result.mappings().first()
    if not row:
        logger.warning("[TrainTask] 检索投影一致性检查无结果: kb_doc_id=%s", kb_doc_id)
        return

    search_unit_count = int(row.get("search_unit_count") or 0)
    vector_count = int(row.get("vector_count") or 0)
    lexical_count = int(row.get("lexical_count") or 0)
    logger.info(
        "[TrainTask] 检索投影一致性检查: kb_doc_id=%s, search_units=%s, vectors=%s, lexicals=%s",
        kb_doc_id,
        search_unit_count,
        vector_count,
        lexical_count,
    )
    if vector_count != search_unit_count or lexical_count != search_unit_count:
        logger.warning(
            "[TrainTask] 检索投影数量不一致: kb_doc_id=%s, search_units=%s, vectors=%s, lexicals=%s",
            kb_doc_id,
            search_unit_count,
            vector_count,
            lexical_count,
        )


# 保留旧的同步任务作为备用（可选）
@celery_app.task(
    name="rag.ingestion.tasks.vectorize_segments_task",
    bind=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=360,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
)
def vectorize_segments_task(self, segment_ids: List[str]):
    """
    向量化任务（同步版本，备用）

    注意：这是同步版本，性能较差，仅作为备用
    推荐使用 train_document_task 中的异步版本
    """
    logger.info(f"[VectorizeTask] 开始向量化（同步版本）: {len(segment_ids)} 个分块, retry={self.request.retries}")

    async def _run():
        task_engine, task_sm = create_task_session_maker()
        redis_client = create_task_redis_client()
        try:
            async with task_sm() as session:
                kb = await _load_kb_for_segment_ids(session, segment_ids)
                return await _vectorize_segments_async(
                    session=session,
                    kb=kb,
                    segment_ids=segment_ids,
                    redis_client=redis_client,
                )
        finally:
            await close_task_redis_client(redis_client)
            await close_task_db_engine(task_engine)

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[VectorizeTask] 向量化失败: {str(e)}", exc_info=True)
        if self.request.retries >= self.max_retries:
            raise
        is_timeout = isinstance(e, (redis_exc.TimeoutError, redis_exc.ConnectionError, TimeoutError))
        countdown = min(60, 10 * (2 ** self.request.retries)) if is_timeout else (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)


async def _load_kb_for_segment_ids(session, segment_ids: List[str]) -> KnowledgeBase | None:
    """根据 chunk id 推导所属知识库，仅供备用同步任务使用。"""
    try:
        chunk_ids = [int(item) for item in segment_ids]
    except ValueError:
        return None
    if not chunk_ids:
        return None

    chunk_stmt = (
        select(Chunk)
        .where(Chunk.id.in_(chunk_ids))
        .order_by(Chunk.id.asc())
        .limit(1)
    )
    chunk_result = await session.execute(chunk_stmt)
    chunk = chunk_result.scalar_one_or_none()
    if chunk is None:
        return None

    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == chunk.kb_id)
    kb_result = await session.execute(kb_stmt)
    return kb_result.scalar_one_or_none()
