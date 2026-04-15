"""
聊天空间相关模型
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ChatSpace(Base):
    """
    聊天空间

    对应聊天首页卡片层，是一个长期存在的聊天入口容器。
    """

    __tablename__ = "chat_spaces"
    __searchable_fields__ = ["name", "description"]

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="空间所有者ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="空间名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="空间描述")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", comment="状态：active、archived、deleted"
    )
    entrypoint_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="入口类型：assistant、workflow、agent"
    )
    entrypoint_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="入口对象ID")
    default_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="空间级默认配置"
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否置顶"
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, comment="展示排序"
    )
    last_session_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近一次会话创建或活跃时间"
    )
    created_by_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="创建人ID")
    updated_by_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="修改人ID")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived', 'deleted')", name="ck_chat_spaces_status"),
        CheckConstraint(
            "entrypoint_type IN ('assistant', 'workflow', 'agent')",
            name="ck_chat_spaces_entrypoint_type",
        ),
    )
