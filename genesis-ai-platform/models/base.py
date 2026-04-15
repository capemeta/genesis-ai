"""
基础模型类
包含通用字段和方法
"""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from core.database.session import Base as SQLAlchemyBase


class Base(SQLAlchemyBase):
    """
    基础模型类
    所有业务模型都应继承此类
    """
    __abstract__ = True
    
    # 主键
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # 审计字段
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"


class AuditMixin:
    """
    审计字段 Mixin
    用于需要记录创建人和修改人的表
    """
    created_by_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by_id: Mapped[UUID | None] = mapped_column(nullable=True)
    updated_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class TenantMixin:
    """
    租户隔离 Mixin
    用于需要租户隔离的表
    """
    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
