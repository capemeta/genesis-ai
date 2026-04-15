"""
租户启用模型绑定表。
"""
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import CAPABILITY_TYPES, MODEL_SOURCE_TYPES, RESOURCE_SCOPE_TYPES
from models.base import AuditMixin, Base, TenantMixin


class TenantModel(Base, TenantMixin, AuditMixin):
    """
    作用域化模型启用绑定。

    当前运行逻辑只启用租户级模型池，但结构已经预留用户级私有模型池。
    """

    __tablename__ = "tenant_models"

    __searchable_fields__ = ["model_alias", "model_type"]

    resource_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="tenant", comment="资源作用域")
    owner_user_id: Mapped[UUID | None] = mapped_column(nullable=True, comment="资源所有者")
    tenant_provider_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="关联租户 provider")
    platform_model_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="关联平台模型目录")
    model_alias: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="租户模型别名")
    model_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="冗余保存主能力类型")
    capabilities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, comment="租户侧能力快照")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="discovered", comment="来源类型")
    group_key: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="前端分组键")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="模型是否启用")
    is_visible_in_ui: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="前端是否展示")
    is_default_for_type: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否为类型默认")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="路由优先级")
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="负载均衡权重")
    adapter_override_type: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="模型级适配器覆盖")
    implementation_key_override: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="模型级实现键覆盖"
    )
    request_schema_override: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="模型级请求协议覆盖"
    )
    endpoint_path_override: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="模型级 endpoint path 覆盖"
    )
    request_defaults: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="默认请求参数")
    model_runtime_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="模型级运行时高级配置"
    )
    rate_limit_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="限流配置")
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, comment="标签")
    metadata_info: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, comment="扩展元数据")

    __table_args__ = (
        CheckConstraint(f"resource_scope IN {RESOURCE_SCOPE_TYPES}", name="check_tenant_model_resource_scope"),
        CheckConstraint(
            "(resource_scope = 'tenant' AND owner_user_id IS NULL) OR "
            "(resource_scope = 'user' AND owner_user_id IS NOT NULL)",
            name="check_tenant_model_scope_owner",
        ),
        CheckConstraint(f"model_type IN {CAPABILITY_TYPES}", name="check_tenant_model_model_type"),
        CheckConstraint(f"source_type IN {MODEL_SOURCE_TYPES}", name="check_tenant_model_source_type"),
    )
