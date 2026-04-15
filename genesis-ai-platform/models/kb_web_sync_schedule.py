"""
网页同步调度规则模型

对应表：kb_web_sync_schedules
"""
from datetime import date, datetime, time
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, AuditMixin


class KBWebSyncSchedule(Base, AuditMixin):
    """网页同步调度规则模型。"""

    __tablename__ = "kb_web_sync_schedules"

    tenant_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    kb_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    kb_web_page_id: Mapped[Optional[PyUUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    scope_level: Mapped[str] = mapped_column(String(32), nullable=False, default="kb_default")
    schedule_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    cron_expr: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    interval_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    interval_unit: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    run_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    run_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weekdays: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    monthdays: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_trigger_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    jitter_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
