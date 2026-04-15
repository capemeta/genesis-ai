"""
平台统一模型目录表。
"""
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import CAPABILITY_TYPES, MODEL_SOURCE_TYPES
from models.base import Base


class PlatformModel(Base):
    """
    平台统一模型目录。
    """

    __tablename__ = "platform_models"

    __searchable_fields__ = ["model_key", "raw_model_name", "display_name", "model_family"]

    provider_definition_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True, comment="默认归属 provider")
    model_key: Mapped[str] = mapped_column(String(255), nullable=False, comment="平台唯一模型键")
    raw_model_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="厂商原始模型名")
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="展示名")
    model_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="主能力类型")
    capabilities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, comment="能力列表")
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="上下文窗口")
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="最大输出 token")
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="向量维度")
    supports_stream: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否支持流式")
    supports_tools: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否支持工具调用")
    supports_structured_output: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否支持结构化输出"
    )
    supports_vision_input: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否支持视觉输入")
    supports_audio_input: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否支持音频输入")
    supports_audio_output: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否支持音频输出")
    pricing_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="成本元数据")
    model_family: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="模型家族")
    release_channel: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="发布通道")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual", comment="来源类型")
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否内置")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="平台目录层是否启用")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="模型说明")
    metadata_info: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, comment="扩展元数据")

    __table_args__ = (
        UniqueConstraint("model_key", name="uq_platform_models_model_key"),
        CheckConstraint(f"model_type IN {CAPABILITY_TYPES}", name="check_platform_model_model_type"),
        CheckConstraint(f"source_type IN {MODEL_SOURCE_TYPES}", name="check_platform_model_source_type"),
    )
