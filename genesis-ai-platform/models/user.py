"""
用户模型
完全匹配数据库 schema，兼容 fastapi-users
"""
from uuid import UUID
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, List
from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base
from core.config.constants import UserStatus, SUPER_ADMIN_ROLE

if TYPE_CHECKING:
    from models.tenant import Tenant


class User(Base):
    """
    用户表
    完全按照 docker/postgresql/init-schema.sql 中的定义
    兼容 fastapi-users（通过字段映射）
    """
    __tablename__ = "users"
    
    # 租户关联
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属租户ID，实现强隔离",
    )
    
    # 组织关联
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID，组织架构挂载",
    )
    
    # 登录凭证
    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="登录账号（用户名），全局唯一",
    )
    nickname: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="显示姓名（昵称），用于界面展示",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码哈希，使用Argon2/Bcrypt加密",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="邮箱，用于找回密码/通知，全局唯一",
    )
    
    # 联系方式
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="手机号，备用联系方式，全局唯一",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="头像地址，存储图标或SeaweedFS/S3路径",
    )
    job_title: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="职位，用于通讯录展示、协作和智能体 persona 引用",
    )
    employee_no: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="员工编号，组织内部标识，通常由管理员维护",
    )
    bio: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="个人简介，用于资料展示与个性化上下文",
    )
    
    # 用户偏好设置：方案B，使用 users.settings(JSONB) 存储 language/timezone 等扩展信息
    settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="用户偏好设置(JSONB)，用于语言/时区/展示等配置",
    )
    
    # 状态管理
    status: Mapped[str] = mapped_column(
        String(20),
        default=UserStatus.ACTIVE.value,
        nullable=False,
        comment="状态：active-正常，disabled-禁用，locked-锁定",
    )
    
    # 删除标志：0-正常，1-删除
    del_flag: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        default="0",
        comment="删除标志：0-正常，1-删除（逻辑删除）",
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="邮箱验证时间，NULL表示未验证",
    )
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="手机验证时间，NULL表示未验证",
    )
    failed_login_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="连续登录失败次数，用于风控和自动锁定",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="锁定截止时间，NULL表示未锁定",
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近一次修改密码时间",
    )
    
    # 审计信息
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间，用于审计",
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="最后登录IP，用于安全审计",
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近活跃时间，用于设备与活跃分析",
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="首次激活时间，用于邀请制或首次登录闭环",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="逻辑删除时间，配合部分唯一索引与审计",
    )
    
    # 审计字段
    created_by_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="创建人ID",
    )
    created_by_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="创建人名称",
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        comment="修改人ID",
    )
    updated_by_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="修改人名称",
    )
    
    # 运行时角色集合（非数据库字段，从 session 或数据库动态加载）
    _roles: ClassVar[List[str] | None] = None
    
    # 运行时权限集合（非数据库字段，从 session 或数据库动态加载）
    _permissions: ClassVar[List[str] | None] = None
    
    @property
    def roles(self) -> List[str]:
        """
        获取用户角色代码集合
        
        优先使用缓存的角色列表，如果没有则返回空列表
        实际角色需要在登录或权限检查时从数据库加载并设置
        """
        cached_roles = self.__dict__.get("_roles")
        if cached_roles is not None:
            return cached_roles
        return []
    
    @roles.setter
    def roles(self, value: List[str]) -> None:
        """设置用户角色代码集合"""
        self.__dict__["_roles"] = value if value else []
    
    @property
    def permissions(self) -> List[str]:
        """
        获取用户权限代码集合
        
        优先使用缓存的权限列表，如果没有则返回空列表
        实际权限需要在登录或权限检查时从数据库加载并设置
        """
        cached_permissions = self.__dict__.get("_permissions")
        if cached_permissions is not None:
            return cached_permissions
        return []
    
    @permissions.setter
    def permissions(self, value: List[str]) -> None:
        """设置用户权限代码集合"""
        self.__dict__["_permissions"] = value if value else []
    
    def is_super_admin(self) -> bool:
        """
        判断当前用户是否是超级管理员
        
        Returns:
            bool: 如果用户角色包含 'super_admin' 则返回 True
        """
        return SUPER_ADMIN_ROLE in self.roles
    
    # fastapi-users 兼容字段（通过 hybrid_property 映射）
    @property
    def hashed_password(self) -> str:
        """fastapi-users 兼容：映射到 password_hash"""
        return self.password_hash
    
    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        """fastapi-users 兼容：设置 password_hash"""
        self.password_hash = value
    
    @property
    def is_active(self) -> bool:
        """fastapi-users 兼容：根据 status 判断是否激活"""
        return self.status == UserStatus.ACTIVE.value
    
    @is_active.setter
    def is_active(self, value: bool) -> None:
        """fastapi-users 兼容：设置 status"""
        self.status = UserStatus.ACTIVE.value if value else UserStatus.DISABLED.value
    
    @property
    def is_superuser(self) -> bool:
        """
        fastapi-users 兼容：超级管理员标志
        
        判断逻辑：
        1. 优先使用 is_super_admin() 方法（基于角色判断）
        2. 否则使用缓存的 _is_superuser 值（从 session 中读取）
        3. 兜底方案：检查用户名是否为 "admin"
        """
        # 🔥 优先使用角色判断
        if self.__dict__.get("_roles"):
            return self.is_super_admin()
        
        # 🔥 其次使用缓存值（从 session 中读取）
        if "_is_superuser" in self.__dict__:
            return bool(self.__dict__["_is_superuser"])
        
        # 兜底方案：用户名为 admin 的用户是超级管理员
        return self.username == "admin"
    
    @property
    def is_verified(self) -> bool:
        """fastapi-users 兼容：邮箱验证标志"""
        return self.email_verified_at is not None

    @property
    def email_verified(self) -> bool:
        """邮箱是否已验证"""
        return self.email_verified_at is not None

    @property
    def phone_verified(self) -> bool:
        """手机号是否已验证"""
        return self.phone_verified_at is not None
    
    _is_superuser: ClassVar[bool | None] = None
    _token_scope: ClassVar[List[str] | None] = None

    # 表约束
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled', 'locked')",
            name="check_user_status",
        ),
    )
    
    # 关系
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
    
    @property
    def display_name(self) -> str:
        """获取显示名称"""
        return self.nickname or self.username
