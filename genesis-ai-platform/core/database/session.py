"""
数据库连接管理
使用 SQLAlchemy 2.0 异步引擎
"""
import logging
from typing import AsyncGenerator

# 任何使用本模块的进程（API / Celery worker）都统一不打印 SQL 的 INFO，只保留 WARN+
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from redis.asyncio import Redis, ConnectionPool
from core.config import settings

logger = logging.getLogger(__name__)


# 创建异步引擎
engine: AsyncEngine = create_async_engine(
    settings.get_database_url(),
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # 连接前检查连接是否有效
)

# 创建会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 异步模式必须设置为 False
    autoflush=False,
    autocommit=False,
)


# Redis 连接池和客户端
redis_pool: ConnectionPool | None = None
redis_client: Redis | None = None


class Base(DeclarativeBase):
    """SQLAlchemy 基础模型类"""
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取异步数据库会话
    用于 FastAPI 依赖注入
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def get_redis_pool() -> ConnectionPool:
    """
    获取 Redis 连接池（单例、进程级）。
    同一 Worker 进程内多任务应复用该池，不要每任务调用 close_redis()。
    """
    global redis_pool
    if redis_pool is None:
        redis_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=100,  # 增加到 100（从 50 增加）
        )
    return redis_pool


async def get_redis() -> Redis:
    """
    获取 Redis 客户端
    用于 FastAPI 依赖注入
    """
    global redis_client
    if redis_client is None:
        pool = get_redis_pool()
        redis_client = Redis(connection_pool=pool)
    return redis_client


def get_redis_client() -> Redis:
    """
    获取 Redis 客户端（同步获取）。
    使用全局连接池，返回的客户端为异步接口。
    
    适用场景：
    - FastAPI 中间件 / API 路由（长驻进程，event loop 固定）
    - 定时清理任务（asyncio.run 中调用，但无需跨 loop 复用）
    
    注意：Celery 任务中请使用 create_task_redis_client()，避免 event loop 冲突。
    """
    pool = get_redis_pool()
    return Redis(connection_pool=pool)


def create_task_session_maker():
    """
    为 Celery 任务创建独立的数据库引擎和 session maker。
    
    为什么需要独立引擎？
    ---
    Celery 任务使用 asyncio.run()，每次调用都会创建新的 event loop。
    全局 engine 连接池中的数据库连接（asyncpg）绑定在旧 event loop 上，
    新 loop 中复用这些连接会触发：
    - "Future attached to a different loop"
    - "Event loop is closed"
    
    而 engine.dispose() 在关闭旧连接时也会因旧 loop 已关闭而产生 ERROR 日志。
    
    独立引擎的优势：
    ---
    - 连接在当前 event loop 上创建，不存在跨 loop 问题
    - dispose 时关闭的是当前 loop 上的连接，不会报错
    - 与 create_task_redis_client() 模式一致
    - 兼容所有 Celery pool 模式（prefork / solo / threads / gevent / eventlet）
    
    生命周期管理：
    ---
    1. 在 asyncio.run() 内部调用此函数创建引擎和 session maker
    2. 将 session_maker 传递给业务函数使用
    3. 任务结束时调用 await close_task_db_engine(engine) 关闭引擎
    4. 务必放在 finally 块中，避免连接泄漏
    
    Returns:
        tuple[AsyncEngine, async_sessionmaker]: (引擎, session 工厂)
    
    用法::
    
        async def _run():
            task_engine, task_sm = create_task_session_maker()
            try:
                await do_work(task_sm)
            finally:
                await close_task_db_engine(task_engine)
        asyncio.run(_run())
    """
    # 任务侧强制关闭 SQLAlchemy echo，避免 worker 在 INFO 级别输出 SQL 文本
    task_engine = create_async_engine(
        settings.get_database_url(),
        echo=False,
        pool_size=5,          # 任务级别不需要大池
        max_overflow=3,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    task_sm = async_sessionmaker(
        task_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return task_engine, task_sm


async def close_task_db_engine(task_engine: AsyncEngine) -> None:
    """
    关闭 Celery 任务专用的数据库引擎，同时释放其连接池中的所有连接。
    
    必须与 create_task_session_maker() 配对使用，否则连接池会泄漏。
    由于连接和引擎都在同一个 event loop 上创建，
    dispose() 可以正常关闭连接，不会产生 "Event loop is closed" 错误。
    """
    if task_engine is None:
        return
    try:
        await task_engine.dispose()
    except Exception as e:
        logger.warning(f"关闭任务数据库引擎失败: {e}")


async def init_db() -> None:
    """初始化数据库（创建所有表）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库连接"""
    await engine.dispose()


async def close_redis() -> None:
    """
    关闭 Redis 连接与连接池（进程级）。
    建议仅在 Worker 关闭或测试 teardown 时调用，不要在每次任务 finally 中调用，
    否则会每任务重建连接池，无法复用连接，且增加延迟。
    """
    global redis_client, redis_pool
    if redis_client:
        await redis_client.close()
        redis_client = None
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None


def create_task_redis_client() -> Redis:
    """
    为 Celery 任务创建独立的 Redis 客户端（含私有连接池）。
    
    为什么需要独立客户端？
    ---
    Celery 任务使用 asyncio.run()，每次都会创建新的 event loop。
    而全局连接池中的连接绑定在旧 event loop 上，在新 loop 中使用会抛出
    "Future attached to a different loop" / "Event loop is closed" 错误。
    
    生命周期管理：
    ---
    1. 在 asyncio.run() 内部调用此函数创建客户端
    2. 任务结束时调用 await close_task_redis_client(client) 关闭客户端和连接池
    3. 务必放在 finally 块中，避免连接泄漏
    
    用法::
    
        async def _run():
            redis_client = create_task_redis_client()
            try:
                await do_work(redis_client)
            finally:
                await close_task_redis_client(redis_client)
        asyncio.run(_run())
    """
    pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=10,
    )
    return Redis(connection_pool=pool)


async def close_task_redis_client(client: Redis) -> None:
    """
    关闭 Celery 任务专用的 Redis 客户端，同时断开其私有连接池。
    
    必须与 create_task_redis_client() 配对使用，否则连接池会泄漏。
    """
    if client is None:
        return
    try:
        pool = client.connection_pool
        await client.aclose()
        # 断开私有连接池中的所有连接
        if pool is not None:
            await pool.disconnect()
    except Exception as e:
        logger.warning(f"关闭任务 Redis 客户端失败: {e}")
