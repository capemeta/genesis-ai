"""
租户模型厂商凭证表。
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import CREDENTIAL_TYPES
from models.base import AuditMixin, Base, TenantMixin


class TenantModelProviderCredential(Base, TenantMixin, AuditMixin):
    """
    provider 凭证表。

    当前默认服务于租户级连接，未来可通过 owner_user_id 承载用户级私有凭证。
    """

    __tablename__ = "tenant_model_provider_credentials"

    __searchable_fields__ = ["credential_name", "credential_type"]

    tenant_provider_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="关联租户 provider 实例")
    owner_user_id: Mapped[UUID | None] = mapped_column(nullable=True, comment="凭证所有者")
    credential_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="凭证名称")
    credential_type: Mapped[str] = mapped_column(String(64), nullable=False, default="api_key", comment="凭证类型")
    encrypted_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="加密配置载荷")
    masked_summary: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="脱敏摘要")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否主凭证")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="过期时间")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后使用时间")

    __table_args__ = (
        UniqueConstraint(
            "tenant_provider_id",
            "credential_name",
            name="uq_tenant_model_provider_credentials_provider_name",
        ),
        CheckConstraint(
            f"credential_type IN {CREDENTIAL_TYPES}",
            name="check_tenant_model_provider_credential_type",
        ),
    )
