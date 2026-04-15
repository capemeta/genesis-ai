"""
角色服务
提供角色的增删改查和权限管理
"""
from typing import List, Tuple, Optional
from uuid import UUID
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from core.base_service import BaseService
from core.config.constants import SUPER_ADMIN_ROLE
from models.role import Role
from models.permission import Permission
from models.user import User
from schemas.role import RoleCreate, RoleUpdate


class RoleService(BaseService[Role, RoleCreate, RoleUpdate]):
    """
    角色服务
    
    功能：
    - 角色列表查询（支持搜索）
    - 角色详情获取（包含权限信息）
    - 角色创建
    - 角色更新
    - 角色删除（校验用户关联）
    - 角色权限分配
    - 角色权限查询
    - 用户角色查询（用于认证）
    """
    
    def __init__(self, db: AsyncSession):
        """
        初始化角色服务
        
        Args:
            db: 数据库会话
        """
        super().__init__(model=Role, db=db, resource_name="role")
    
    async def get_assignable_roles(
        self,
        tenant_id: UUID,
        current_user: User
    ) -> List[Role]:
        """
        获取用户可分配的角色列表
        
        过滤条件：
        - 未删除的角色（del_flag = '0'）
        - 已启用的角色（status = '0'）
        - 如果当前用户不是超级管理员，过滤掉超级管理员角色
        
        Args:
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            可分配的角色列表
        """
        # 基础查询条件：未删除 + 已启用
        conditions = [
            Role.del_flag == "0",  # 未删除
            Role.status == "0",    # 已启用
            or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None))  # 租户隔离
        ]
        
        # 检查当前用户是否是超级管理员
        current_user_roles = await self.get_user_role_codes(current_user.id, tenant_id)
        is_super_admin = SUPER_ADMIN_ROLE in current_user_roles
        
        # 如果不是超级管理员，过滤掉超级管理员角色
        if not is_super_admin:
            conditions.append(Role.code != SUPER_ADMIN_ROLE)
        
        # 查询数据
        stmt = (
            select(Role)
            .where(*conditions)
            .order_by(Role.sort_order.asc(), Role.created_at.asc())
        )
        
        result = await self.db.execute(stmt)
        roles = result.scalars().all()
        
        return list(roles)
    
    async def get_assignable_roles_paginated(
        self,
        tenant_id: UUID,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Tuple[List[Role], int]:
        """
        获取用户可分配的角色列表（分页）
        
        过滤条件：
        - 未删除的角色（del_flag = '0'）
        - 已启用的角色（status = '0'）
        - 如果当前用户不是超级管理员，过滤掉超级管理员角色
        
        Args:
            tenant_id: 租户ID
            current_user: 当前用户
            page: 页码（从1开始）
            page_size: 每页数量
            search: 搜索关键词（角色名称、角色编码）
            
        Returns:
            (角色列表, 总数)
        """
        # 基础查询条件：未删除 + 已启用
        conditions = [
            Role.del_flag == "0",  # 未删除
            Role.status == "0",    # 已启用
            or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None))  # 租户隔离
        ]
        
        # 检查当前用户是否是超级管理员
        current_user_roles = await self.get_user_role_codes(current_user.id, tenant_id)
        is_super_admin = SUPER_ADMIN_ROLE in current_user_roles
        
        # 如果不是超级管理员，过滤掉超级管理员角色
        if not is_super_admin:
            conditions.append(Role.code != SUPER_ADMIN_ROLE)
        
        # 搜索条件
        if search:
            conditions.append(
                or_(
                    Role.code.ilike(f"%{search}%"),
                    Role.name.ilike(f"%{search}%")
                )
            )
        
        # 查询总数
        count_stmt = select(func.count()).select_from(Role).where(*conditions)
        total = await self.db.scalar(count_stmt) or 0
        
        # 查询数据（分页）
        offset = (page - 1) * page_size
        stmt = (
            select(Role)
            .where(*conditions)
            .order_by(Role.sort_order.asc(), Role.created_at.asc())
            .limit(page_size)
            .offset(offset)
        )
        
        result = await self.db.execute(stmt)
        roles = result.scalars().all()
        
        return list(roles), total
    
    async def get_user_role_codes(
        self,
        user_id: UUID,
        tenant_id: UUID
    ) -> List[str]:
        """
        获取用户的角色代码列表（用于认证和权限判断）
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            角色代码列表
        """
        from models.user_roles import user_roles
        
        stmt = (
            select(Role.code)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user_id)
        )
        
        result = await self.db.execute(stmt)
        role_codes = result.scalars().all()
        
        return list(role_codes)
    
    async def list_roles(
        self,
        tenant_id: UUID,
        search: Optional[str] = None
    ) -> Tuple[List[Role], int]:
        """
        获取角色列表
        
        Args:
            tenant_id: 租户ID
            search: 搜索关键词（角色代码、名称）
            
        Returns:
            (角色列表, 总数)
        """
        # 基础查询条件：租户隔离（包含全局角色）+ 未删除
        conditions = [
            or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None)),
            Role.del_flag == "0"  # 只查询未删除的角色
        ]
        
        # 搜索条件
        if search:
            conditions.append(
                or_(
                    Role.code.ilike(f"%{search}%"),
                    Role.name.ilike(f"%{search}%")
                )
            )
        
        # 查询总数
        count_stmt = select(func.count()).select_from(Role).where(*conditions)
        total = await self.db.scalar(count_stmt) or 0
        
        # 查询数据
        stmt = (
            select(Role)
            .where(*conditions)
            .order_by(Role.sort_order.asc(), Role.created_at.asc())
        )
        
        result = await self.db.execute(stmt)
        roles = result.scalars().all()
        
        return list(roles), total
    
    async def get_role(
        self,
        role_id: UUID,
        tenant_id: UUID
    ) -> Role:
        """
        获取角色详情
        
        Args:
            role_id: 角色ID
            tenant_id: 租户ID
            
        Returns:
            角色实体
        """
        stmt = select(Role).where(
            Role.id == role_id,
            or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None)),
            Role.del_flag == "0"  # 只查询未删除的角色
        )
        
        result = await self.db.execute(stmt)
        role = result.scalar_one_or_none()
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="角色不存在"
            )
        
        return role

    
    async def create_role(
        self,
        data: RoleCreate,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> Role:
        """
        创建角色
        
        Args:
            data: 创建数据
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            创建的角色
        """
        # 检查角色代码是否已存在（包括已删除的）
        existing_role = await self.db.scalar(
            select(Role).where(
                Role.code == data.code,
                Role.tenant_id == tenant_id,
                Role.del_flag == "0"  # 只检查未删除的
            )
        )
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="角色编码已存在"
            )
        
        # 创建角色对象
        role = Role(
            tenant_id=tenant_id,
            code=data.code,
            name=data.name,
            description=data.description,
            status=data.status,
            del_flag="0",  # 新建时默认未删除
            sort_order=data.sort_order,
            is_system=False
        )
        
        # 设置审计字段
        if current_user:
            role.created_by_id = current_user.id
            role.created_by_name = current_user.nickname or current_user.username
            role.updated_by_id = current_user.id
            role.updated_by_name = current_user.nickname or current_user.username
        
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        
        return role
    
    async def update_role(
        self,
        role_id: UUID,
        data: RoleUpdate,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> Role:
        """
        更新角色
        
        Args:
            role_id: 角色ID
            data: 更新数据
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            更新后的角色
        """
        # 获取角色
        role = await self.get_role(role_id, tenant_id)
        
        # 超级管理员角色不可修改
        if role.code == SUPER_ADMIN_ROLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="超级管理员角色不可修改"
            )
        
        # 系统角色不可修改
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="系统角色不可修改"
            )
        
        # 更新字段
        if data.code is not None:
            # 检查角色代码是否已被其他角色使用
            if data.code != role.code:
                existing_role = await self.db.scalar(
                    select(Role).where(
                        Role.code == data.code,
                        Role.tenant_id == tenant_id,
                        Role.id != role_id,
                        Role.del_flag == "0"
                    )
                )
                if existing_role:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="角色代码已存在"
                    )
            role.code = data.code
        if data.name is not None:
            role.name = data.name
        if data.description is not None:
            role.description = data.description
        if data.status is not None:
            role.status = data.status
        if data.sort_order is not None:
            role.sort_order = data.sort_order
        
        # 更新审计字段
        if current_user:
            role.updated_by_id = current_user.id
            role.updated_by_name = current_user.nickname or current_user.username
        
        await self.db.commit()
        await self.db.refresh(role)
        
        return role

    
    async def delete_role(
        self,
        role_id: UUID,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> bool:
        """
        删除角色（逻辑删除）
        
        Args:
            role_id: 角色ID
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            是否成功
        """
        # 获取角色
        role = await self.get_role(role_id, tenant_id)
        
        # 超级管理员角色不可删除
        if role.code == SUPER_ADMIN_ROLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="超级管理员角色不可删除"
            )
        
        # 系统角色不可删除
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="系统角色不可删除"
            )
        
        # 检查是否有用户关联
        from models.user_roles import user_roles
        user_count = await self.db.scalar(
            select(func.count()).select_from(user_roles).where(
                user_roles.c.role_id == role_id
            )
        ) or 0
        
        if user_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该角色下存在 {user_count} 个用户，无法删除"
            )
        
        # 删除角色权限关联
        from models.role_permissions import role_permissions
        await self.db.execute(
            delete(role_permissions).where(role_permissions.c.role_id == role_id)
        )
        
        # 逻辑删除：设置 del_flag = '1'
        role.del_flag = "1"
        
        # 更新审计字段
        if current_user:
            role.updated_by_id = current_user.id
            role.updated_by_name = current_user.nickname or current_user.username
        
        await self.db.commit()
        
        return True
    
    async def assign_permissions(
        self,
        role_id: UUID,
        permission_ids: List[UUID],
        tenant_id: UUID
    ) -> bool:
        """
        为角色分配权限
        
        Args:
            role_id: 角色ID
            permission_ids: 权限ID列表
            tenant_id: 租户ID
            
        Returns:
            是否成功
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 验证角色存在
        role = await self.get_role(role_id, tenant_id)
        
        # 超级管理员角色不可修改权限
        if role.code == SUPER_ADMIN_ROLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="超级管理员角色不可修改权限"
            )
        
        # 系统角色不可修改权限
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="系统角色不可修改权限"
            )
        
        # 验证权限存在
        perm_stmt = select(Permission).where(
            Permission.id.in_(permission_ids),
            or_(Permission.tenant_id == tenant_id, Permission.tenant_id.is_(None))
        )
        perm_result = await self.db.execute(perm_stmt)
        permissions = perm_result.scalars().all()
        
        if len(permissions) != len(permission_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="部分权限不存在"
            )
        
        # 删除旧的权限关联
        from models.role_permissions import role_permissions
        await self.db.execute(
            delete(role_permissions).where(role_permissions.c.role_id == role_id)
        )
        
        # 创建新的权限关联
        for permission_id in permission_ids:
            await self.db.execute(
                role_permissions.insert().values(
                    role_id=role_id,
                    permission_id=permission_id,
                    tenant_id=tenant_id
                )
            )
        
        await self.db.commit()
        
        # 🔥 角色权限变更后，清除租户所有用户的权限缓存
        try:
            from core.security.permission_cache import permission_cache
            
            # 清除租户所有用户的权限缓存
            await permission_cache.delete_tenant_all_permissions(tenant_id)
            logger.info(f"清除租户所有用户权限缓存: tenant_id={tenant_id}, role_id={role_id}")
        except Exception as e:
            logger.error(f"清除租户权限缓存失败: {e}", exc_info=True)
            # 即使清除失败，也继续返回成功（权限已更新）
        
        return True
    
    async def get_role_permissions(
        self,
        role_id: UUID,
        tenant_id: UUID
    ) -> List[Permission]:
        """
        获取角色权限列表
        
        Args:
            role_id: 角色ID
            tenant_id: 租户ID
            
        Returns:
            权限列表
        """
        from models.role_permissions import role_permissions
        
        stmt = (
            select(Permission)
            .join(role_permissions, role_permissions.c.permission_id == Permission.id)
            .where(role_permissions.c.role_id == role_id)
        )
        
        result = await self.db.execute(stmt)
        permissions = result.scalars().all()
        
        return list(permissions)

    async def get_role_users(
        self,
        role_id: UUID,
        tenant_id: UUID,
        search: Optional[str] = None
    ) -> Tuple[List[User], int]:
        """
        获取角色的用户列表
        
        Args:
            role_id: 角色ID
            tenant_id: 租户ID
            search: 搜索关键词（用户名、昵称、邮箱）
            
        Returns:
            (用户列表, 总数)
        """
        from models.user_roles import user_roles
        
        # 基础查询条件
        conditions = [
            user_roles.c.role_id == role_id,
            User.tenant_id == tenant_id,
        ]
        
        # 搜索条件
        if search:
            conditions.append(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.nickname.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        # 查询总数
        count_stmt = (
            select(func.count())
            .select_from(User)
            .join(user_roles, user_roles.c.user_id == User.id)
            .where(*conditions)
        )
        total = await self.db.scalar(count_stmt) or 0
        
        # 查询数据
        stmt = (
            select(User)
            .join(user_roles, user_roles.c.user_id == User.id)
            .where(*conditions)
            .order_by(User.created_at.desc())
        )
        
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        
        return list(users), total

    async def get_available_users(
        self,
        role_id: UUID,
        tenant_id: UUID,
        search: Optional[str] = None
    ) -> Tuple[List[User], int]:
        """
        获取可分配的用户列表（未分配该角色的用户）
        
        Args:
            role_id: 角色ID
            tenant_id: 租户ID
            search: 搜索关键词（用户名、昵称、邮箱）
            
        Returns:
            (用户列表, 总数)
        """
        from models.user_roles import user_roles
        
        # 基础查询条件：租户内的用户，且未分配该角色
        conditions = [
            User.tenant_id == tenant_id,
            ~User.id.in_(
                select(user_roles.c.user_id).where(user_roles.c.role_id == role_id)
            )
        ]
        
        # 搜索条件
        if search:
            conditions.append(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.nickname.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        # 查询总数
        count_stmt = select(func.count()).select_from(User).where(*conditions)
        total = await self.db.scalar(count_stmt) or 0
        
        # 查询数据
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
        )
        
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        
        return list(users), total

    async def assign_users(
        self,
        role_id: UUID,
        user_ids: List[UUID],
        tenant_id: UUID
    ) -> bool:
        """
        为角色分配用户
        
        Args:
            role_id: 角色ID
            user_ids: 用户ID列表
            tenant_id: 租户ID
            
        Returns:
            是否成功
        """
        # 验证角色存在
        role = await self.get_role(role_id, tenant_id)
        
        # 验证用户存在
        user_stmt = select(User).where(
            User.id.in_(user_ids),
            User.tenant_id == tenant_id
        )
        user_result = await self.db.execute(user_stmt)
        users = user_result.scalars().all()
        
        if len(users) != len(user_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="部分用户不存在"
            )
        
        # 创建用户-角色关联
        from models.user_roles import user_roles
        for user_id in user_ids:
            # 检查是否已关联
            existing = await self.db.scalar(
                select(user_roles).where(
                    user_roles.c.user_id == user_id,
                    user_roles.c.role_id == role_id
                )
            )
            if not existing:
                await self.db.execute(
                    user_roles.insert().values(
                        user_id=user_id,
                        role_id=role_id,
                        tenant_id=tenant_id
                    )
                )
        
        await self.db.commit()
        
        return True

    async def remove_user(
        self,
        role_id: UUID,
        user_id: UUID,
        tenant_id: UUID
    ) -> bool:
        """
        取消用户的角色
        
        Args:
            role_id: 角色ID
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            是否成功
        """
        # 验证角色存在
        await self.get_role(role_id, tenant_id)
        
        # 验证用户存在
        user = await self.db.scalar(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id
            )
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 删除用户-角色关联
        from models.user_roles import user_roles
        await self.db.execute(
            delete(user_roles).where(
                user_roles.c.user_id == user_id,
                user_roles.c.role_id == role_id
            )
        )
        
        await self.db.commit()
        
        return True

