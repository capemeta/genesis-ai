"""
租户模型厂商接入实例表。
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import ADAPTER_TYPES, ENDPOINT_TYPES, RESOURCE_SCOPE_TYPES, SYNC_STATUSES
from models.base import AuditMixin, Base, TenantMixin


class TenantModelProvider(Base, TenantMixin, AuditMixin):
    """
    作用域化 provider 接入实例。

    当前业务默认只使用租户级资源，但这里提前预留用户级私有资源结构。
    """

    __tablename__ = "tenant_model_providers"

    __searchable_fields__ = ["name", "description", "endpoint_type", "base_url"]

    provider_definition_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="关联厂商定义 ID")
    resource_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="tenant", comment="资源作用域")
    owner_user_id: Mapped[UUID | None] = mapped_column(nullable=True, comment="资源所有者")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="租户自定义 provider 名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="实例描述")
    endpoint_type: Mapped[str] = mapped_column(String(64), nullable=False, default="official", comment="接入类型")
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False, comment="调用入口地址")
    api_version: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="API 版本号")
    region: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="区域标识")
    adapter_override_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="覆盖默认适配器"
    )
    capability_base_urls: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="各能力专用URL，键为 capability_type，值为 base_url"
    )
    capability_overrides: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="各能力高级覆盖配置，如 endpoint_path/request_schema/adapter_type"
    )
    discovery_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="模型发现参数")
    request_defaults: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="默认请求参数")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="厂商实例是否启用")
    is_visible_in_ui: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="前端是否展示")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近同步时间")
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", comment="同步状态")
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近同步错误")

    __table_args__ = (
        CheckConstraint(f"resource_scope IN {RESOURCE_SCOPE_TYPES}", name="check_tenant_model_provider_resource_scope"),
        CheckConstraint(
            "(resource_scope = 'tenant' AND owner_user_id IS NULL) OR "
            "(resource_scope = 'user' AND owner_user_id IS NOT NULL)",
            name="check_tenant_model_provider_scope_owner",
        ),
        CheckConstraint(f"endpoint_type IN {ENDPOINT_TYPES}", name="check_tenant_model_provider_endpoint_type"),
        CheckConstraint(f"sync_status IN {SYNC_STATUSES}", name="check_tenant_model_provider_sync_status"),
        CheckConstraint(
            f"adapter_override_type IS NULL OR adapter_override_type IN {ADAPTER_TYPES}",
            name="check_tenant_model_provider_adapter_override_type",
        ),
    )
