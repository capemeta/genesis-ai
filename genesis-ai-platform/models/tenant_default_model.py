"""
租户默认模型表。
"""
from uuid import UUID

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import CAPABILITY_TYPES, RESOURCE_SCOPE_TYPES
from models.base import AuditMixin, Base, TenantMixin


class TenantDefaultModel(Base, TenantMixin, AuditMixin):
    """
    按能力类型维护作用域化默认模型。

    当前业务只读写租户级默认模型，用户级默认模型后续按需求开启。
    """

    __tablename__ = "tenant_default_models"

    resource_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="tenant", comment="资源作用域")
    owner_user_id: Mapped[UUID | None] = mapped_column(nullable=True, comment="资源所有者")
    capability_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="能力类型")
    tenant_model_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="关联租户模型 ID")
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=True, comment="是否启用")

    __table_args__ = (
        CheckConstraint(f"resource_scope IN {RESOURCE_SCOPE_TYPES}", name="check_tenant_default_model_resource_scope"),
        CheckConstraint(
            "(resource_scope = 'tenant' AND owner_user_id IS NULL) OR "
            "(resource_scope = 'user' AND owner_user_id IS NOT NULL)",
            name="check_tenant_default_model_scope_owner",
        ),
        CheckConstraint(
            f"capability_type IN {CAPABILITY_TYPES}",
            name="check_tenant_default_model_capability_type",
        ),
    )
