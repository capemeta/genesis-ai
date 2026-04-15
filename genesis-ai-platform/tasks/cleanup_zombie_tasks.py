"""
僵尸任务清理
定期清理长时间处于 processing 状态的文档解析任务
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, func
from models.knowledge_base_document import KnowledgeBaseDocument
from rag.ingestion.tasks.common import cleanup_derived_documents_for_kb_doc

logger = logging.getLogger(__name__)


async def cleanup_zombie_parsing_tasks(redis_client, session_maker, timeout_minutes: int = 30):
    """
    清理僵尸解析任务（超级保守策略）
    
    僵尸任务的判定条件（必须同时满足）：
    1. parse_status = 'processing'
    2. updated_at 超过指定时间（默认 30 分钟）
    3. 没有持有分布式锁（说明任务已经不在执行）
    4. parse_started_at 不为空（说明任务已经开始执行，不是在队列中等待）
    
    为什么需要第 4 个条件？
    - 任务提交时：parse_status = 'processing', parse_started_at = None
    - 任务开始时：parse_status = 'processing', parse_started_at = 当前时间
    - 如果任务在队列中等待 30 分钟，parse_started_at 仍然是 None
    - 这样可以避免误杀正在队列中等待的任务
    
    这种情况通常发生在：
    - Worker 进程崩溃
    - 服务器断电
    - 任务被强制 Kill
    - 网络中断导致任务挂起
    
    Args:
        timeout_minutes: 超时时间（分钟），默认 30 分钟
    
    Returns:
        dict: 清理结果统计
    """
    cleaned_count = 0
    skipped_count = 0
    waiting_count = 0
    
    try:
        # 使用调用方传入的 session_maker（在 Celery 任务中为独立引擎）
        async with session_maker() as session:
            # 计算超时时间点
            timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            
            # 查询僵尸任务候选
            # 🔧 同时检查 processing 和 cancelling 状态
            # cancelling 状态如果超时，说明 Worker 没有响应取消请求（可能已崩溃）
            from sqlalchemy import or_
            stmt = select(KnowledgeBaseDocument).where(
                or_(
                    KnowledgeBaseDocument.parse_status == "processing",
                    KnowledgeBaseDocument.parse_status == "cancelling",
                ),
                KnowledgeBaseDocument.updated_at < timeout_threshold
            )
            
            result = await session.execute(stmt)
            zombie_candidates = result.scalars().all()
            
            if not zombie_candidates:
                logger.info("No zombie parsing tasks found")
                return {
                    "cleaned": 0,
                    "skipped": 0,
                    "waiting": 0,
                    "timeout_minutes": timeout_minutes
                }
            
            # 🔧 逐个检查每个候选任务
            zombie_ids = []
            for task in zombie_candidates:
                # 条件 1：检查是否有锁（任务是否正在执行）
                lock_key = f"parsing:lock:{task.id}"
                lock_exists = await redis_client.exists(lock_key)
                
                if lock_exists:
                    # 任务仍在执行（持有锁），跳过
                    skipped_count += 1
                    age_minutes = (datetime.now(timezone.utc) - task.updated_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
                    logger.info(
                        f"Skipped task {task.id} (still has lock, "
                        f"age={age_minutes:.1f} minutes)"
                    )
                    continue
                
                # 条件 2：检查 parse_started_at 是否为空
                if task.parse_started_at is None:
                    # 任务还在队列中等待，没有开始执行
                    waiting_count += 1
                    age_minutes = (datetime.now(timezone.utc) - task.updated_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
                    logger.info(
                        f"Skipped task {task.id} (waiting in queue, "
                        f"age={age_minutes:.1f} minutes, "
                        f"parse_started_at=None)"
                    )
                    continue
                
                # 条件 3：检查 parse_started_at 是否超时
                # 使用 parse_started_at 而不是 updated_at 来判断超时
                # 这样可以更准确地反映任务真正执行的时间
                started_at = task.parse_started_at.replace(tzinfo=timezone.utc)
                age_since_start = (datetime.now(timezone.utc) - started_at).total_seconds() / 60
                
                if age_since_start < timeout_minutes:
                    # 任务开始执行的时间还不到超时时间，跳过
                    skipped_count += 1
                    logger.info(
                        f"Skipped task {task.id} (started recently, "
                        f"age_since_start={age_since_start:.1f} minutes)"
                    )
                    continue
                
                # 通过所有检查，确认为僵尸任务
                zombie_ids.append(task.id)
                logger.warning(
                    f"Identified zombie task: "
                    f"kb_doc_id={task.id}, "
                    f"file_name={task.file_name}, "
                    f"age_since_start={age_since_start:.1f} minutes, "
                    f"parse_started_at={task.parse_started_at}, "
                    f"no_lock=True"
                )
            
            if not zombie_ids:
                logger.info(
                    f"No real zombie tasks found: "
                    f"skipped={skipped_count} (still running), "
                    f"waiting={waiting_count} (in queue)"
                )
                return {
                    "cleaned": 0,
                    "skipped": skipped_count,
                    "waiting": waiting_count,
                    "timeout_minutes": timeout_minutes
                }
            
            # 🔧 分别处理 processing 和 cancelling 状态的僵尸任务
            # cancelling 超时应标记为 cancelled（取消成功但 Worker 未响应）
            # processing 超时应标记为 failed（任务异常）
            cancelling_zombie_ids = [
                t.id for t in zombie_candidates
                if t.id in zombie_ids and t.parse_status == "cancelling"
            ]
            processing_zombie_ids = [
                t_id for t_id in zombie_ids if t_id not in cancelling_zombie_ids
            ]
            
            if processing_zombie_ids:
                update_stmt = (
                    update(KnowledgeBaseDocument)
                    .where(KnowledgeBaseDocument.id.in_(processing_zombie_ids))
                    .values(
                        parse_status="failed",
                        parse_error=f"任务超时（超过 {timeout_minutes} 分钟未完成），可能由于 Worker 崩溃或进程被强制终止",
                        task_id=None,
                        updated_at=func.now()
                    )
                )
                await session.execute(update_stmt)
            
            if cancelling_zombie_ids:
                for task in zombie_candidates:
                    if task.id not in cancelling_zombie_ids:
                        continue
                    await cleanup_derived_documents_for_kb_doc(session, task)
                    task.parse_status = "cancelled"
                    task.parse_error = f"取消超时（Worker 未响应，超过 {timeout_minutes} 分钟），已强制标记为已取消"
                    task.task_id = None
                    task.updated_at = datetime.now(timezone.utc)
                    cancel_key = f"parsing:cancel:{task.id}"
                    await redis_client.delete(cancel_key)
            
            await session.commit()
            
            cleaned_count = len(zombie_ids)
            
            logger.info(
                f"Zombie parsing task cleanup completed: "
                f"cleaned={cleaned_count}, "
                f"skipped={skipped_count}, "
                f"waiting={waiting_count}, "
                f"timeout_minutes={timeout_minutes}"
            )
            
            return {
                "cleaned": cleaned_count,
                "skipped": skipped_count,
                "waiting": waiting_count,
                "timeout_minutes": timeout_minutes,
                "zombie_tasks": [
                    {
                        "kb_doc_id": str(task.id),
                        "file_name": task.file_name,
                        "age_since_start": round(
                            (datetime.now(timezone.utc) - task.parse_started_at.replace(tzinfo=timezone.utc)).total_seconds() / 60,
                            1
                        )
                    }
                    for task in zombie_candidates
                    if task.id in zombie_ids
                ]
            }
            
    except Exception as e:
        logger.error(f"Zombie parsing task cleanup failed: {e}", exc_info=True)
        raise


async def cleanup_stuck_embedding_tasks(timeout_minutes: int = 60):
    """
    清理卡住的向量生成任务
    
    如果未来有向量生成任务，可以使用此函数清理
    目前预留接口
    
    Args:
        timeout_minutes: 超时时间（分钟），默认 60 分钟
    
    Returns:
        dict: 清理结果统计
    """
    # TODO: 实现向量生成任务的僵尸清理
    logger.info("Embedding task cleanup not implemented yet")
    return {"cleaned": 0, "timeout_minutes": timeout_minutes}


async def run_zombie_cleanup_tasks(redis_client, session_maker):
    """运行所有僵尸任务清理"""
    logger.info("Starting zombie task cleanup...")
    
    # 清理僵尸解析任务（30 分钟超时）
    result1 = await cleanup_zombie_parsing_tasks(redis_client, session_maker, timeout_minutes=30)
    
    # 清理卡住的向量生成任务（60 分钟超时）
    result2 = await cleanup_stuck_embedding_tasks(timeout_minutes=60)
    
    logger.info("All zombie task cleanup completed")
    
    return {
        "parsing_tasks": result1,
        "embedding_tasks": result2
    }


if __name__ == "__main__":
    # 测试运行
    async def _test_run():
        from core.database.session import (
            create_task_redis_client, close_task_redis_client,
            create_task_session_maker, close_task_db_engine,
        )
        task_engine, task_sm = create_task_session_maker()
        redis_client = create_task_redis_client()
        try:
            result = await run_zombie_cleanup_tasks(redis_client, task_sm)
            print(f"Cleanup result: {result}")
        finally:
            await close_task_redis_client(redis_client)
            await close_task_db_engine(task_engine)
            
    asyncio.run(_test_run())
