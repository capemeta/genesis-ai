"""
模型调用日志表。
"""
from uuid import UUID

from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import ADAPTER_TYPES, CAPABILITY_TYPES
from models.base import Base


class ModelInvocationLog(Base):
    """统一记录模型调用的观测与审计信息。"""

    __tablename__ = "model_invocation_logs"

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="租户 ID")
    tenant_provider_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True, comment="租户 provider ID")
    tenant_model_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True, comment="租户模型 ID")
    capability_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="能力类型")
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="实际适配器类型")
    request_source: Mapped[str] = mapped_column(String(64), nullable=False, comment="请求来源")
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="链路请求 ID")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", comment="调用状态")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="耗时毫秒")
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="输入 token")
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="输出 token")
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="总 token")
    cost_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="成本元数据")
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="错误码")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误详情")
    metadata_info: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, comment="扩展观测字段")

    __table_args__ = (
        CheckConstraint(
            f"capability_type IN {CAPABILITY_TYPES}",
            name="check_model_invocation_log_capability_type",
        ),
        CheckConstraint(
            f"adapter_type IN {ADAPTER_TYPES}",
            name="check_model_invocation_log_adapter_type",
        ),
    )
