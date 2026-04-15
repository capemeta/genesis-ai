"""
模型同步记录表。
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.model_platform.constants import SYNC_STATUSES
from models.base import Base


class ModelSyncRecord(Base):
    """记录每次模型发现与同步的结果。"""

    __tablename__ = "model_sync_records"

    tenant_provider_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="关联租户 provider 实例")
    sync_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", comment="同步类型")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", comment="同步状态")
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="发现模型数")
    added_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增模型数")
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="更新模型数")
    disabled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="禁用模型数")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="原始同步结果")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="完成时间")

    __table_args__ = (
        CheckConstraint(f"status IN {SYNC_STATUSES}", name="check_model_sync_record_status"),
    )
