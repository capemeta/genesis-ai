"""
网页主事实模型

对应表：kb_web_pages
"""
from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, AuditMixin


class KBWebPage(Base, AuditMixin):
    """网页主事实模型。"""

    __tablename__ = "kb_web_pages"

    tenant_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True, comment="所属租户ID")
    kb_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True, comment="所属知识库ID")
    document_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True, comment="关联载体文档ID"
    )
    kb_doc_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, unique=True, index=True, comment="关联知识库文档挂载ID"
    )
    folder_id: Mapped[Optional[PyUUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, comment="知识库内文件夹ID")

    url: Mapped[str] = mapped_column(Text, nullable=False, comment="原始URL")
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False, comment="规范化URL")
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="canonical URL")
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="域名")
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="页面标题")
    site_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="站点名称")

    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual", comment="来源：manual/sitemap/discovered"
    )
    fetch_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="auto", comment="抓取模式：auto/static/browser"
    )
    sync_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="idle", comment="同步状态：idle/queued/syncing/success/partial_success/failed"
    )
    content_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="new", comment="内容状态：new/unchanged/changed/gone"
    )

    last_success_version_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, comment="最近成功版本ID（逻辑关联）"
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近同步成功时间"
    )
    last_content_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近内容变化时间"
    )
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="下次同步时间"
    )
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近执行最新性校验时间"
    )
    last_check_status: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="最近校验结果：latest/outdated/failed"
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="最近错误")
    last_http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="最近HTTP状态码")
    etag: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="ETag")
    last_modified: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="Last-Modified")
    latest_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True, comment="最近内容哈希")

    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="页面级抓取与抽取配置")
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="额外元数据")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
