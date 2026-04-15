"""
网页版本模型

对应表：kb_web_page_versions
"""
from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, AuditMixin


class KBWebPageVersion(Base, AuditMixin):
    """网页版本模型。"""

    __tablename__ = "kb_web_page_versions"

    tenant_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    kb_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    kb_web_page_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    kb_doc_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    document_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_material_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    fetch_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fetch_ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fetch_status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    final_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    site_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extractor: Mapped[str] = mapped_column(String(32), nullable=False, default="trafilatura")

    raw_html_document_id: Mapped[Optional[PyUUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    markdown_document_id: Mapped[Optional[PyUUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    text_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diff_from_version_id: Mapped[Optional[PyUUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    chunk_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
