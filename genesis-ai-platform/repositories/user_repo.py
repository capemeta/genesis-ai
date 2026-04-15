"""
用户 Repository
"""
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User
from repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """用户数据访问层"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_email(self, email: str) -> User | None:
        """根据邮箱获取用户"""
        stmt = select(User).where(
            func.lower(User.email) == email.lower(),
            User.del_flag == "0",
            User.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> User | None:
        """根据用户名获取用户"""
        stmt = select(User).where(
            func.lower(User.username) == username.lower(),
            User.del_flag == "0",
            User.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_by_username_or_email(self, identifier: str) -> list[User]:
        """根据用户名或邮箱获取匹配用户列表"""
        stmt = select(User).where(
            User.del_flag == "0",
            User.deleted_at.is_(None),
            or_(
                func.lower(User.username) == identifier.lower(),
                func.lower(User.email) == identifier.lower(),
            )
        )
        stmt = stmt.order_by(User.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        """根据用户名或邮箱获取单个用户"""
        users = await self.list_by_username_or_email(identifier)
        if len(users) > 1:
            return None
        return users[0] if users else None
    
    async def get_by_tenant(
        self,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """获取租户下的所有用户"""
        return await self.get_multi(skip=skip, limit=limit, tenant_id=tenant_id)
    
    async def count_by_tenant(self, tenant_id: UUID) -> int:
        """统计租户下的用户数"""
        return await self.count(tenant_id=tenant_id)
    
    async def exists_by_email(self, email: str) -> bool:
        """检查邮箱是否已存在"""
        user = await self.get_by_email(email)
        return user is not None
    
    async def exists_by_username(self, username: str) -> bool:
        """检查用户名是否已存在"""
        user = await self.get_by_username(username)
        return user is not None
