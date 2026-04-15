"""
用户服务
提供用户的增删改查和角色管理
"""
from collections import defaultdict
from typing import List, Tuple, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from core.base_service import BaseService
from core.security.crypto import get_password_hash
from core.security.token_store import SessionService
from models.user import User
from models.role import Role
from models.organization import Organization
from models.user_roles import user_roles
from schemas.user import UserCreate, UserUpdate, UserListItem, UserRead


class UserService(BaseService[User, UserCreate, UserUpdate]):
    """
    用户服务
    
    功能：
    - 用户列表查询（支持搜索、状态过滤、组织过滤）
    - 用户详情获取（包含角色信息）
    - 用户创建（密码哈希、审计字段）
    - 用户更新（密码可选更新）
    - 用户删除（硬删除，校验关联数据）
    - 用户角色分配
    - 用户角色查询
    - 密码重置（管理员操作）
    """
    
    def __init__(self, db: AsyncSession):
        """
        初始化用户服务
        
        Args:
            db: 数据库会话
        """
        super().__init__(model=User, db=db, resource_name="user")

    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        """
        统一清洗可选文本字段

        规则：
        - 去除首尾空白
        - 空字符串落库为 None，避免后续唯一性和展示逻辑混乱
        """
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    async def _ensure_username_available(
        self,
        username: str,
        exclude_user_id: Optional[UUID] = None,
    ) -> None:
        """校验用户名是否可用（全局唯一）"""
        conditions = [
            User.del_flag == "0",
            User.deleted_at.is_(None),
            func.lower(User.username) == username.lower(),
        ]
        if exclude_user_id:
            conditions.append(User.id != exclude_user_id)

        existing_user = await self.db.scalar(select(User).where(*conditions))
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在",
            )

    async def _ensure_email_available(
        self,
        email: Optional[str],
        exclude_user_id: Optional[UUID] = None,
    ) -> None:
        """校验邮箱是否可用（全局唯一）"""
        normalized_email = self._normalize_optional_text(email)
        if not normalized_email:
            return

        conditions = [
            User.del_flag == "0",
            User.deleted_at.is_(None),
            func.lower(User.email) == normalized_email.lower(),
        ]
        if exclude_user_id:
            conditions.append(User.id != exclude_user_id)

        existing_email = await self.db.scalar(select(User).where(*conditions))
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用",
            )

    async def _ensure_phone_available(
        self,
        phone: Optional[str],
        exclude_user_id: Optional[UUID] = None,
    ) -> None:
        """校验手机号是否可用（全局唯一）"""
        normalized_phone = self._normalize_optional_text(phone)
        if not normalized_phone:
            return

        conditions = [
            User.del_flag == "0",
            User.deleted_at.is_(None),
            User.phone == normalized_phone,
        ]
        if exclude_user_id:
            conditions.append(User.id != exclude_user_id)

        existing_phone = await self.db.scalar(select(User).where(*conditions))
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手机号已被使用",
            )

    async def _build_user_list_items(
        self,
        users: list[User],
    ) -> list[UserListItem]:
        """
        批量组装用户列表项

        说明：
        - 角色和组织信息统一在 service 层组装，避免 API 层出现 N+1 查询和业务拼装逻辑
        - 当前场景数据量不大，但仍按批量查询处理，便于后续扩展
        """
        if not users:
            return []

        user_ids = [user.id for user in users]
        organization_ids = {
            user.organization_id
            for user in users
            if user.organization_id is not None
        }

        role_name_map: dict[UUID, list[str]] = defaultdict(list)
        role_stmt = (
            select(user_roles.c.user_id, Role.name)
            .join(Role, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id.in_(user_ids))
        )
        role_result = await self.db.execute(role_stmt)
        for row in role_result.all():
            role_name_map[row.user_id].append(row.name)

        organization_name_map: dict[UUID, str] = {}
        if organization_ids:
            org_stmt = select(Organization.id, Organization.name).where(
                Organization.id.in_(organization_ids)
            )
            org_result = await self.db.execute(org_stmt)
            organization_name_map = {
                row.id: row.name
                for row in org_result.all()
            }

        return [
            UserListItem(
                id=user.id,
                username=user.username,
                nickname=user.nickname,
                email=user.email,
                phone=user.phone,
                job_title=user.job_title,
                employee_no=user.employee_no,
                bio=user.bio,
                status=user.status,
                organization_id=user.organization_id,
                organization_name=organization_name_map.get(user.organization_id) if user.organization_id else None,
                role_names=role_name_map.get(user.id, []),
                last_login_at=user.last_login_at,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in users
        ]

    async def _get_organization_name(
        self,
        organization_id: Optional[UUID],
    ) -> Optional[str]:
        """获取组织名称"""
        if not organization_id:
            return None
        organization = await self.db.scalar(
            select(Organization).where(Organization.id == organization_id)
        )
        return organization.name if organization else None
    
    async def list_users(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[UUID] = None
    ) -> Tuple[List[User], int]:
        """
        获取用户列表（分页）
        
        Args:
            tenant_id: 租户ID
            page: 页码
            page_size: 每页数量
            search: 搜索关键词（用户名、昵称、邮箱）
            status: 状态过滤
            organization_id: 组织ID过滤
            
        Returns:
            (用户列表, 总数)
        """
        # 基础查询条件（排除已删除的用户）
        conditions = [
            User.tenant_id == tenant_id,
            User.del_flag == "0",
            User.deleted_at.is_(None),
        ]
        
        # 搜索条件
        if search:
            conditions.append(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.nickname.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    User.phone.ilike(f"%{search}%"),
                )
            )
        
        # 状态过滤
        if status:
            conditions.append(User.status == status)
        
        # 组织过滤
        if organization_id:
            conditions.append(User.organization_id == organization_id)
        
        # 查询总数
        count_stmt = select(func.count()).select_from(User).where(*conditions)
        total = await self.db.scalar(count_stmt) or 0
        
        # 查询数据
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        
        return list(users), total

    async def list_user_items(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[UUID] = None,
    ) -> Tuple[list[UserListItem], int]:
        """获取可直接返回给前端的用户列表数据"""
        users, total = await self.list_users(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            search=search,
            status=status,
            organization_id=organization_id,
        )
        items = await self._build_user_list_items(users)
        return items, total

    
    async def get_user_with_roles(
        self,
        user_id: UUID,
        tenant_id: UUID
    ) -> User:
        """
        获取用户详情（包含角色信息）
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            用户实体（包含角色列表）
        """
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.del_flag == "0",
            User.deleted_at.is_(None),
        )
        
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 查询用户角色
        from models.user_roles import user_roles
        from sqlalchemy import select as sql_select
        role_stmt = (
            select(Role)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user_id)
        )
        role_result = await self.db.execute(role_stmt)
        roles = role_result.scalars().all()
        
        # 设置运行时角色缓存，避免触发 ORM 映射
        user.__dict__["_roles"] = [role.code for role in roles]
        
        return user

    async def get_user_detail(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> UserRead:
        """
        获取用户详情响应

        说明：
        - 由 service 统一组装详情数据，避免 API 层处理角色与组织信息
        - 当前返回字段面向管理后台详情页使用
        """
        user = await self.get_user_with_roles(user_id, tenant_id)
        roles = await self.get_user_roles(user_id, tenant_id)
        organization_name = await self._get_organization_name(user.organization_id)

        return UserRead(
            id=user.id,
            tenant_id=user.tenant_id,
            organization_id=user.organization_id,
            organization_name=organization_name,
            username=user.username,
            nickname=user.nickname,
            email=user.email,
            phone=user.phone,
            avatar_url=user.avatar_url,
            job_title=user.job_title,
            employee_no=user.employee_no,
            bio=user.bio,
            status=user.status,
            role_names=[role.name for role in roles],
            email_verified_at=user.email_verified_at,
            phone_verified_at=user.phone_verified_at,
            failed_login_count=user.failed_login_count,
            locked_until=user.locked_until,
            last_login_at=user.last_login_at,
            last_login_ip=user.last_login_ip,
            last_active_at=user.last_active_at,
            password_changed_at=user.password_changed_at,
            activated_at=user.activated_at,
            created_by_id=user.created_by_id,
            created_by_name=user.created_by_name,
            updated_by_id=user.updated_by_id,
            updated_by_name=user.updated_by_name,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    
    async def create_user(
        self,
        data: UserCreate,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> User:
        """
        创建用户（包含角色分配）
        
        Args:
            data: 创建数据（包含 role_ids）
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            创建的用户
        """
        await self._ensure_username_available(data.username)
        await self._ensure_email_available(data.email)
        await self._ensure_phone_available(data.phone)
        
        # 验证角色存在（仅当 role_ids 不为空时）
        if data.role_ids:
            role_stmt = select(Role).where(
                Role.id.in_(data.role_ids),
                or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None))
            )
            role_result = await self.db.execute(role_stmt)
            roles = role_result.scalars().all()
            
            if len(roles) != len(data.role_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="部分角色不存在"
                )
        
        # 创建用户对象
        user = User(
            tenant_id=tenant_id,
            username=data.username.strip(),
            nickname=data.nickname.strip(),
            password_hash=get_password_hash(data.password),
            email=self._normalize_optional_text(data.email),
            phone=self._normalize_optional_text(data.phone),
            job_title=self._normalize_optional_text(data.job_title),
            employee_no=self._normalize_optional_text(data.employee_no),
            bio=self._normalize_optional_text(data.bio),
            organization_id=data.organization_id,
            status=data.status or "active"
        )
        
        # 设置审计字段
        if current_user:
            user.created_by_id = current_user.id
            user.created_by_name = current_user.nickname or current_user.username
            user.updated_by_id = current_user.id
            user.updated_by_name = current_user.nickname or current_user.username
        
        self.db.add(user)
        await self.db.flush()  # 获取用户ID，但不提交事务
        
        # 分配角色
        if data.role_ids:
            from models.user_roles import user_roles
            for role_id in data.role_ids:
                await self.db.execute(
                    user_roles.insert().values(
                        user_id=user.id,
                        role_id=role_id,
                        tenant_id=tenant_id
                    )
                )
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user

    async def reset_password(
        self,
        user_id: UUID,
        new_password: str,
        tenant_id: UUID,
        session_service: SessionService,
        current_user: Optional[User] = None
    ) -> tuple[User, int]:
        """
        重置用户密码（管理员操作）
        
        Args:
            user_id: 用户ID
            new_password: 新密码
            tenant_id: 租户ID
            session_service: 会话服务，用于重置密码后撤销已有会话
            current_user: 当前用户（操作者）
            
        Returns:
            (更新后的用户, 撤销的会话数量)
        """
        # 获取用户
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.del_flag == "0",
            User.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 更新密码
        user.password_hash = get_password_hash(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        
        # 更新审计字段
        if current_user:
            user.updated_by_id = current_user.id
            user.updated_by_name = current_user.nickname or current_user.username
        
        await self.db.commit()
        await self.db.refresh(user)

        # 重置密码后强制用户重新登录，避免旧会话继续使用
        revoked_count = await session_service.revoke_all_user_sessions(user.id)

        return user, revoked_count

    
    async def update_user(
        self,
        user_id: UUID,
        data: UserUpdate,
        tenant_id: UUID,
        current_user: Optional[User] = None
    ) -> User:
        """
        更新用户（包含角色分配）
        
        Args:
            user_id: 用户ID
            data: 更新数据（包含 role_ids）
            tenant_id: 租户ID
            current_user: 当前用户
            
        Returns:
            更新后的用户
        """
        # 获取用户
        user = await self.get_user_with_roles(user_id, tenant_id)
        
        # 验证角色存在（仅当 role_ids 不为空时）
        if data.role_ids:
            role_stmt = select(Role).where(
                Role.id.in_(data.role_ids),
                or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None))
            )
            role_result = await self.db.execute(role_stmt)
            roles = role_result.scalars().all()
            
            if len(roles) != len(data.role_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="部分角色不存在"
                )
        
        # 更新字段
        if data.nickname is not None:
            user.nickname = data.nickname.strip()
        if data.email is not None:
            normalized_email = self._normalize_optional_text(data.email)
            current_email = self._normalize_optional_text(user.email)
            if normalized_email != current_email:
                await self._ensure_email_available(normalized_email, exclude_user_id=user_id)
            user.email = normalized_email
        if data.phone is not None:
            normalized_phone = self._normalize_optional_text(data.phone)
            current_phone = self._normalize_optional_text(user.phone)
            if normalized_phone != current_phone:
                await self._ensure_phone_available(normalized_phone, exclude_user_id=user_id)
            user.phone = normalized_phone
        if data.job_title is not None:
            user.job_title = self._normalize_optional_text(data.job_title)
        if data.employee_no is not None:
            user.employee_no = self._normalize_optional_text(data.employee_no)
        if data.bio is not None:
            user.bio = self._normalize_optional_text(data.bio)
        if data.organization_id is not None:
            user.organization_id = data.organization_id
        if data.status is not None:
            user.status = data.status
        if data.password is not None:
            # 管理员可以直接重置密码
            user.password_hash = get_password_hash(data.password)
            user.password_changed_at = datetime.now(timezone.utc)
        
        # 更新审计字段
        if current_user:
            user.updated_by_id = current_user.id
            user.updated_by_name = current_user.nickname or current_user.username
        
        # 更新角色关联
        # 删除旧的角色关联
        await self.db.execute(
            delete(user_roles).where(user_roles.c.user_id == user_id)
        )
        
        # 创建新的角色关联
        if data.role_ids:
            for role_id in data.role_ids:
                await self.db.execute(
                    user_roles.insert().values(
                        user_id=user_id,
                        role_id=role_id,
                        tenant_id=tenant_id
                    )
                )
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def delete_user(
        self,
        user_id: UUID,
        tenant_id: UUID
    ) -> bool:
        """
        删除用户（逻辑删除）
        
        同时删除用户的角色关联数据，保持数据一致性
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            是否成功
        """
        # 获取用户
        user = await self.get_user_with_roles(user_id, tenant_id)
        
        # 检查是否是系统管理员
        if user.username == "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除系统管理员"
            )
        
        # 删除用户的角色关联
        await self.db.execute(
            delete(user_roles).where(user_roles.c.user_id == user_id)
        )
        
        # 逻辑删除：设置 del_flag = '1'
        user.del_flag = "1"
        user.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        return True
    
    async def assign_roles(
        self,
        user_id: UUID,
        role_ids: List[UUID],
        tenant_id: UUID
    ) -> bool:
        """
        为用户分配角色
        
        Args:
            user_id: 用户ID
            role_ids: 角色ID列表（空列表表示清除所有角色）
            tenant_id: 租户ID
            
        Returns:
            是否成功
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 验证用户存在
        user = await self.get_user_with_roles(user_id, tenant_id)
        
        # 验证角色存在（仅当 role_ids 不为空时）
        if role_ids:
            role_stmt = select(Role).where(
                Role.id.in_(role_ids),
                or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None))
            )
            role_result = await self.db.execute(role_stmt)
            roles = role_result.scalars().all()
            
            if len(roles) != len(role_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="部分角色不存在"
                )
        
        # 删除旧的角色关联
        from models.user_roles import user_roles
        await self.db.execute(
            delete(user_roles).where(user_roles.c.user_id == user_id)
        )
        
        # 创建新的角色关联
        for role_id in role_ids:
            await self.db.execute(
                user_roles.insert().values(
                    user_id=user_id,
                    role_id=role_id,
                    tenant_id=tenant_id
                )
            )
        
        await self.db.commit()
        
        # 🔥 角色变更后，清除权限缓存并撤销用户所有 Session
        try:
            from core.security.permission_cache import permission_cache
            from core.security.token_store import SessionStore, SessionService
            from core.database import get_redis
            
            # 清除用户权限缓存
            await permission_cache.delete_permissions(user_id, tenant_id)
            logger.info(f"清除用户权限缓存: user_id={user_id}, tenant_id={tenant_id}")
            
            # 撤销用户所有 Session（强制重新登录以获取最新权限）
            redis = await get_redis()
            session_store = SessionStore(redis)
            session_service = SessionService(session_store)
            revoked_count = await session_service.revoke_all_user_sessions(user_id)
            logger.info(f"撤销用户所有 Session: user_id={user_id}, revoked_count={revoked_count}")
        except Exception as e:
            logger.error(f"清除权限缓存或撤销 Session 失败: {e}", exc_info=True)
            # 即使清除失败，也继续返回成功（角色已更新）
        
        return True
    
    async def get_user_roles(
        self,
        user_id: UUID,
        tenant_id: UUID
    ) -> List[Role]:
        """
        获取用户角色列表
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            角色列表
        """
        stmt = (
            select(Role)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user_id)
        )
        
        result = await self.db.execute(stmt)
        roles = result.scalars().all()
        
        return list(roles)
