"""
Celery 定时任务
Worker 启动时自动加载项目根目录 .env，与主应用共用同一套配置（含 TESSERACT_HOME 等）。
"""
from pathlib import Path
from dotenv import load_dotenv
import os
import sys

# Windows 上必须使用 spawn 启动方式，确保子进程能正确导入项目模块
# Linux/macOS 默认使用 fork，无需特殊处理
if sys.platform == 'win32':
    import multiprocessing
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass  # 已设置过则忽略

# 最先加载 .env，保证后续 imports 和任务内都能读到环境变量/ .env 配置
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 限制 BLAS 线程，避免在 Windows + 多 Celery 进程/线程下触发 OpenBLAS 内存分配失败
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import logging
from celery import Celery
from celery import signals

# SQLAlchemy 只输出 WARN 及以上，避免 task 中打印每条 SQL
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
from celery.schedules import crontab
import asyncio
from tasks.cleanup_sessions import run_cleanup_tasks

from core.config import settings
from core.logging_config import (
    LOG_CATEGORY_TASK,
    LOG_CATEGORY_WEB_SYNC,
    init_logging,
    reset_log_category,
    set_log_category,
)

# Celery 主进程 / worker 子进程统一走任务日志目录
init_logging("task")

# 创建 Celery 应用
celery_app = Celery(
    "genesis-ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# 配置
# Broker 连接重试：Redis 不可用时 Worker 会按间隔递增重试。
# - None：无限重试。Redis 恢复后 Worker 会自动连上，无需重启 Celery（适合 Redis 临时维护/重启）。
# - 整数（如 100）：重试 N 次后 Worker 退出，需手动或由进程管理器重启。
celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=["json", "msgpack"],
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=True,
    broker_connection_max_retries=None,  # 无限重试，Redis 恢复后自动重连，无需重启 Celery
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
)

# 任务路由配置（将任务分配到不同的队列）
celery_app.conf.task_routes = {
    # RAG 数据接入流程任务路由
    # 解析任务 → parse 队列（CPU 密集）
    "rag.ingestion.tasks.parse_document_task": {"queue": "parse"},
    
    # 分块任务 → chunk 队列（CPU 密集）
    "rag.ingestion.tasks.chunk_document_task": {"queue": "chunk"},
    
    # 增强任务 → enhance 队列（I/O 密集）
    "rag.ingestion.tasks.enhance_chunks_task": {"queue": "enhance"},
    
    # 训练任务 → train 队列（I/O 密集）
    "rag.ingestion.tasks.train_document_task": {"queue": "train"},
    "rag.ingestion.tasks.vectorize_segments_task": {"queue": "train"},
    # 网页同步执行任务 → web_sync 队列（I/O 密集）
    "tasks.web_sync.execute_web_sync_run_task": {"queue": "web_sync"},
    # 动态分发任务当前也复用 web_sync 队列，减少额外 worker 运维复杂度
    "tasks.web_sync.dispatch_due_web_sync_jobs_task": {"queue": "web_sync"},
    # 网页版本清理任务放 default，低频后台维护
    "tasks.web_sync.cleanup_web_page_versions_task": {"queue": "default"},
    
    # 定时清理任务 → default 队列
    "tasks.celery_tasks.cleanup_sessions_task": {"queue": "default"},
    "tasks.celery_tasks.cleanup_revoked_tokens_task": {"queue": "default"},
    "tasks.celery_tasks.cleanup_zombie_tasks_task": {"queue": "default"},
}

# 默认队列
celery_app.conf.task_default_queue = "default"

# 注册任务
celery_app.autodiscover_tasks(['tasks'])


@signals.setup_logging.connect
def _setup_celery_logging(**_: object) -> None:
    """拦截 Celery 默认日志初始化，统一复用项目日志配置。"""
    init_logging("task")


@signals.task_prerun.connect
def _set_task_log_category(task=None, **_: object) -> None:
    """任务执行前写入日志分类上下文。"""
    if task is None:
        return

    task_name = str(getattr(task, "name", "") or "")
    category = LOG_CATEGORY_WEB_SYNC if task_name.startswith("tasks.web_sync.") else LOG_CATEGORY_TASK
    token = set_log_category(category)

    request = getattr(task, "request", None)
    if request is not None:
        setattr(request, "_genesis_log_category_token", token)


@signals.task_postrun.connect
def _reset_task_log_category(task=None, **_: object) -> None:
    """任务结束后恢复日志上下文，避免串分类。"""
    if task is None:
        return

    request = getattr(task, "request", None)
    token = getattr(request, "_genesis_log_category_token", None) if request is not None else None
    if token is None:
        return

    reset_log_category(token)
    delattr(request, "_genesis_log_category_token")


# 定时任务配置
celery_app.conf.beat_schedule = {
    # 每小时清理一次孤儿 session
    "cleanup-orphan-sessions": {
        "task": "tasks.celery_tasks.cleanup_sessions_task",
        "schedule": crontab(minute=0),  # 每小时的第 0 分钟
    },
    # 每天凌晨 3 点清理已过期的撤销 token
    "cleanup-revoked-tokens": {
        "task": "tasks.celery_tasks.cleanup_revoked_tokens_task",
        "schedule": crontab(hour=3, minute=0),  # 每天 03:00
    },
    # 每 10 分钟清理一次僵尸解析任务
    "cleanup-zombie-parsing-tasks": {
        "task": "tasks.celery_tasks.cleanup_zombie_tasks_task",
        "schedule": crontab(minute="*/10"),  # 每 10 分钟
    },
    # 每天凌晨 2 点清理已删除超过 30 天的文档
    "cleanup-deleted-documents": {
        "task": "tasks.celery_tasks.cleanup_deleted_documents_task",
        "schedule": crontab(hour=2, minute=0),  # 每天 02:00
        "kwargs": {"days": 30},  # 清理超过 30 天的文档
    },
    # 每天凌晨 4 点清理临时文件
    "cleanup-temp-files": {
        "task": "tasks.celery_tasks.cleanup_temp_files_task",
        "schedule": crontab(hour=4, minute=0),  # 每天 04:00
        "kwargs": {"days": 7},  # 清理超过 7 天的临时文件
    },
    # 每分钟分发一次到期网页同步规则（动态调度）
    "dispatch-due-web-sync-jobs": {
        "task": "tasks.web_sync.dispatch_due_web_sync_jobs_task",
        "schedule": crontab(minute="*"),
        "kwargs": {"batch_size": 100},
    },
}

# 按 .env 配置动态启用网页版本清理任务
if settings.WEB_SYNC_CLEANUP_ENABLED:
    celery_app.conf.beat_schedule["cleanup-web-page-versions"] = {
        "task": "tasks.web_sync.cleanup_web_page_versions_task",
        "schedule": crontab(
            hour=int(settings.WEB_SYNC_CLEANUP_CRON_HOUR),
            minute=int(settings.WEB_SYNC_CLEANUP_CRON_MINUTE),
        ),
        "kwargs": {
            "max_versions_per_page": int(settings.WEB_SYNC_CLEANUP_MAX_VERSIONS_PER_PAGE),
            "retention_days": int(settings.WEB_SYNC_CLEANUP_RETENTION_DAYS),
            "page_batch_size": int(settings.WEB_SYNC_CLEANUP_PAGE_BATCH_SIZE),
        },
    }


@celery_app.task(name="tasks.celery_tasks.cleanup_sessions_task")
def cleanup_sessions_task():
    """清理孤儿 session 的 Celery 任务"""
    async def _run():
        from core.database.session import create_task_redis_client, close_task_redis_client
        redis_client = create_task_redis_client()
        try:
            return await run_cleanup_tasks(redis_client)
        finally:
            await close_task_redis_client(redis_client)
    
    return asyncio.run(_run())


@celery_app.task(name="tasks.celery_tasks.cleanup_revoked_tokens_task")
def cleanup_revoked_tokens_task():
    """清理已过期撤销 token 的 Celery 任务"""
    async def _run():
        from core.database.session import create_task_redis_client, close_task_redis_client
        from tasks.cleanup_sessions import cleanup_expired_revoked_tokens
        redis_client = create_task_redis_client()
        try:
            return await cleanup_expired_revoked_tokens(redis_client)
        finally:
            await close_task_redis_client(redis_client)
            
    return asyncio.run(_run())


@celery_app.task(name="tasks.celery_tasks.cleanup_zombie_tasks_task")
def cleanup_zombie_tasks_task():
    """清理僵尸解析任务的 Celery 任务"""
    async def _run():
        from core.database.session import (
            create_task_redis_client, close_task_redis_client,
            create_task_session_maker, close_task_db_engine,
        )
        from tasks.cleanup_zombie_tasks import run_zombie_cleanup_tasks
        task_engine, task_sm = create_task_session_maker()
        redis_client = create_task_redis_client()
        try:
            return await run_zombie_cleanup_tasks(redis_client, task_sm)
        finally:
            await close_task_redis_client(redis_client)
            await close_task_db_engine(task_engine)
            
    return asyncio.run(_run())


@celery_app.task(name="tasks.celery_tasks.cleanup_deleted_documents_task")
def cleanup_deleted_documents_task(days: int = 30):
    """清理已删除文档的 Celery 任务（仅操作数据库，无需 Redis）"""
    async def _run():
        from core.database.session import create_task_session_maker, close_task_db_engine
        from tasks.cleanup_tasks import run_cleanup_deleted_documents
        task_engine, task_sm = create_task_session_maker()
        try:
            return await run_cleanup_deleted_documents(task_sm, days)
        finally:
            await close_task_db_engine(task_engine)
            
    return asyncio.run(_run())


@celery_app.task(name="tasks.celery_tasks.cleanup_temp_files_task")
def cleanup_temp_files_task(days: int = 7):
    """清理临时文件的 Celery 任务（仅操作数据库，无需 Redis）"""
    async def _run():
        from core.database.session import create_task_session_maker, close_task_db_engine
        from tasks.cleanup_tasks import run_cleanup_temp_files
        task_engine, task_sm = create_task_session_maker()
        try:
            return await run_cleanup_temp_files(task_sm, days)
        finally:
            await close_task_db_engine(task_engine)
            
    return asyncio.run(_run())


# 显式导入任务模块以完成注册，放在文件末尾避免循环导入
# 导入 RAG 数据接入流程任务
_is_beat_process = any(arg == "beat" for arg in sys.argv)
# 网页同步任务在 beat / worker 两侧都需要注册
import tasks.web_sync_tasks
if not _is_beat_process:
    import rag.ingestion.tasks.parse_task
    import rag.ingestion.tasks.chunk_task
    import rag.ingestion.tasks.enhance_task
    import rag.ingestion.tasks.train_task
