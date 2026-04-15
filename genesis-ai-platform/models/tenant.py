"""
租户模型
"""
from typing import TYPE_CHECKING
from uuid import UUID
from sqlalchemy import String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, AuditMixin

if TYPE_CHECKING:
    from models.user import User


class Tenant(Base, AuditMixin):
    """
    租户表
    多租户隔离的顶层实体
    完全按照 docker/postgresql/init-schema.sql 中的定义
    """
    __tablename__ = "tenants"
    
    # 配置可搜索字段（用于 search 参数的模糊搜索）
    __searchable_fields__ = ["name", "description"]
    
    # 基本信息
    owner_id: Mapped[UUID] = mapped_column(
        nullable=False,
        comment="首席管理员/所有者ID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="租户名称，全局唯一",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="租户描述信息",
    )
    
    # 配额限制
    limits: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment='配额限制，如 {"max_users": 100, "max_storage_gb": 1000}',
    )
    
    # 关系
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name={self.name})>"
