"""
模型适配器绑定表。
"""
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import ADAPTER_TYPES, CAPABILITY_TYPES
from models.base import Base


class ModelAdapterBinding(Base):
    """
    适配器覆盖规则。
    """

    __tablename__ = "model_adapter_bindings"

    tenant_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True, comment="租户 ID，为空表示全局")
    provider_definition_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True, comment="厂商定义 ID")
    tenant_provider_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True, comment="租户 provider 实例 ID")
    capability_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="能力类型")
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="适配器类型")
    implementation_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="具体实现键")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="优先级")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    metadata_info: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, comment="扩展元数据")

    __table_args__ = (
        CheckConstraint(
            f"capability_type IN {CAPABILITY_TYPES}",
            name="check_model_adapter_binding_capability_type",
        ),
        CheckConstraint(
            f"adapter_type IN {ADAPTER_TYPES}",
            name="check_model_adapter_binding_adapter_type",
        ),
    )
