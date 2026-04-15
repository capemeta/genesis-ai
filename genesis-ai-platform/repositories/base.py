"""
基础 Repository
提供通用的 CRUD 操作
"""
from typing import Generic, TypeVar, Type, Any
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import Base


ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """基础 Repository 类"""
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get(self, id: UUID) -> ModelType | None:
        """根据 ID 获取单条记录"""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[ModelType]:
        """获取多条记录"""
        stmt = select(self.model)
        
        # 应用过滤条件
        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def count(self, **filters: Any) -> int:
        """统计记录数"""
        stmt = select(func.count()).select_from(self.model)
        
        # 应用过滤条件
        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(stmt)
        return result.scalar_one()
    
    async def create(self, obj: ModelType) -> ModelType:
        """创建记录"""
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
    
    async def update(self, obj: ModelType) -> ModelType:
        """更新记录"""
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
    
    async def delete(self, id: UUID) -> bool:
        """删除记录"""
        obj = await self.get(id)
        if obj:
            await self.session.delete(obj)
            await self.session.commit()
            return True
        return False
