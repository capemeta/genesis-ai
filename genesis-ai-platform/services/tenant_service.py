"""
租户业务逻辑层
"""
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from sqlalchemy import select
from uuid import UUID

from core.base_service import BaseService
from models.tenant import Tenant
from models.user import User
from schemas.tenant import TenantCreate, TenantUpdate


class TenantService(BaseService[Tenant, TenantCreate, TenantUpdate]):
    """
    租户服务
    
    扩展功能：
    - 租户名称唯一性校验
    
    注意：租户表没有 tenant_id 字段（因为它本身就是租户），
    BaseService 会自动处理这种情况（通过 hasattr 检查）
    """
    
    async def create(self, data: TenantCreate, current_user: User = None) -> Tenant:
        """
        创建租户（添加名称唯一性校验）
        """
        # 检查名称是否已存在
        existing_tenant_stmt = select(self.model).where(self.model.name == data.name)
        existing_tenant = await self.db.scalar(existing_tenant_stmt)
        
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"租户名称 '{data.name}' 已存在"
            )
        
        # 调用父类的 create 方法（自动处理审计字段）
        return await super().create(data, current_user)
    
    async def update(
        self,
        resource_id: UUID,
        data: TenantUpdate,
        current_user: User = None
    ) -> Tenant:
        """
        更新租户（添加名称唯一性校验）
        """
        # 检查名称是否已存在（排除当前租户）
        if data.name:
            existing_tenant_stmt = select(self.model).where(
                self.model.name == data.name,
                self.model.id != resource_id
            )
            existing_tenant = await self.db.scalar(existing_tenant_stmt)
            
            if existing_tenant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"租户名称 '{data.name}' 已存在"
                )
        
        # 调用父类的 update 方法（自动处理审计字段）
        return await super().update(resource_id, data, current_user)
