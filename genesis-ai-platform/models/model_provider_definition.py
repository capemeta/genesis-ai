"""
模型厂商定义表。
"""
from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import ADAPTER_TYPES, PROVIDER_PROTOCOL_TYPES
from models.base import Base


class ModelProviderDefinition(Base):
    """
    平台内置的厂商协议定义。
    """

    __tablename__ = "model_provider_definitions"

    __searchable_fields__ = ["provider_code", "display_name", "protocol_type"]

    provider_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="平台内部厂商编码")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="厂商展示名称")
    protocol_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="协议类型")
    adapter_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="litellm",
        comment="默认适配器类型"
    )
    supports_model_discovery: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否支持动态发现模型"
    )
    supported_capabilities: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="支持的能力列表"
    )
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="厂商图标地址")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="排序值")
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否系统内置")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否全局启用")
    metadata_info: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, comment="扩展元数据")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="厂商定义说明")

    __table_args__ = (
        UniqueConstraint("provider_code", name="uq_model_provider_definitions_provider_code"),
        CheckConstraint(
            f"protocol_type IN {PROVIDER_PROTOCOL_TYPES}",
            name="check_model_provider_definition_protocol_type",
        ),
        CheckConstraint(
            f"adapter_type IN {ADAPTER_TYPES}",
            name="check_model_provider_definition_adapter_type",
        ),
    )
