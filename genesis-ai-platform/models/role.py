"""
角色模型
RBAC 权限系统核心
"""
from sqlalchemy import String, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from models.base import Base, AuditMixin, TenantMixin


class Role(Base, AuditMixin, TenantMixin):
    """
    角色模型
    
    对应表：roles
    SQL 定义：docker/postgresql/init-schema.sql
    迁移：docker/postgresql/migrations/004_enhance_roles_table.sql
    
    继承 AuditMixin 自动获得审计字段：
    - created_by_id, updated_by_id
    - created_by_name, updated_by_name
    - created_at, updated_at
    
    继承 TenantMixin 自动获得租户隔离字段：
    - tenant_id
    """
    __tablename__ = "roles"
    __searchable_fields__ = ["name", "code", "description"]
    
    # 角色编码（租户内唯一，用于系统内部标识）
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="角色编码，如 admin、user、readonly"
    )
    
    # 角色名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="角色名称"
    )
    
    # 角色描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="角色描述"
    )
    
    # 状态：0-正常，1-停用
    status: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        default="0",
        comment="状态：0-正常，1-停用"
    )
    
    # 删除标志：0-正常，1-删除
    del_flag: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        default="0",
        comment="删除标志：0-正常，1-删除"
    )
    
    # 排序顺序
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序顺序，数字越小越靠前"
    )
    
    # 是否系统角色
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否系统角色"
    )
    
    def __repr__(self) -> str:
        return f"<Role(id={self.id}, code={self.code}, name={self.name})>"
