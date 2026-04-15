"""
模型使用授权表。

当前阶段先完成数据结构与 Schema 对齐，后续真正启用权限控制时再接入业务逻辑。
"""
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import MODEL_GRANTEE_TYPES
from models.base import AuditMixin, Base, TenantMixin


class TenantModelGrant(Base, TenantMixin, AuditMixin):
    """
    模型使用授权记录。
    """

    __tablename__ = "tenant_model_grants"

    tenant_model_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="关联租户模型 ID")
    grantee_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="授权对象类型")
    grantee_id: Mapped[UUID | None] = mapped_column(nullable=True, comment="授权对象 ID")
    can_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否允许使用")
    can_manage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否允许管理")

    __table_args__ = (
        CheckConstraint(f"grantee_type IN {MODEL_GRANTEE_TYPES}", name="check_tenant_model_grants_grantee_type"),
        CheckConstraint(
            "(grantee_type = 'tenant' AND grantee_id IS NULL) OR "
            "(grantee_type IN ('role', 'user') AND grantee_id IS NOT NULL)",
            name="check_tenant_model_grants_grantee",
        ),
    )
