"""
网页同步执行记录模型

对应表：kb_web_sync_runs
"""
from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import BIGINT, Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class KBWebSyncRun(Base):
    """网页同步执行记录模型。"""

    __tablename__ = "kb_web_sync_runs"
    # 运行记录表只追加不更新，与数据库表结构保持一致（无 updated_at）。
    updated_at = None  # type: ignore[assignment]

    tenant_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    kb_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    kb_web_page_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    kb_doc_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    version_id: Mapped[Optional[PyUUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    schedule_id: Mapped[Optional[PyUUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(BIGINT, nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_changed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    old_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chunks_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunks_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logs_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    triggered_by_id: Mapped[Optional[PyUUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    triggered_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
