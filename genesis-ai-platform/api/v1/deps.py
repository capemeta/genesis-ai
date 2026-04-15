"""
API v1 依赖注入
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_async_session

# 从 core.security 导入认证依赖
from core.security import (
    get_current_user,
    get_current_active_user,
    get_current_superuser,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async for session in get_async_session():
        yield session


# 导出认证依赖供其他模块使用
__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "get_current_superuser",
]
