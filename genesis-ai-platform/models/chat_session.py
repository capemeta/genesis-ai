"""
聊天会话相关模型
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from core.database.session import Base as SQLAlchemyBase


class ChatSession(Base):
    """
    聊天会话

    对应聊天空间下的一次具体聊天实例。
    """

    __tablename__ = "chat_sessions"
    __searchable_fields__ = ["title", "summary"]

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    chat_space_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_spaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属聊天空间ID",
    )
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="会话所有者ID")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="会话标题")
    title_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual", comment="标题来源"
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="会话摘要")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", comment="状态"
    )
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ui", comment="来源渠道"
    )
    visibility: Mapped[str] = mapped_column(
        String(32), nullable=False, default="user_visible", comment="可见性"
    )
    persistence_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="persistent", comment="持久化模式"
    )
    config_override: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="会话级配置覆盖"
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否置顶"
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, comment="展示排序"
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后一条消息时间"
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="会话关闭时间"
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="会话归档时间"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="会话删除时间"
    )
    created_by_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="创建人ID")
    updated_by_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="修改人ID")

    __table_args__ = (
        CheckConstraint(
            "title_source IN ('manual', 'auto', 'fallback')",
            name="ck_chat_sessions_title_source",
        ),
        CheckConstraint("status IN ('active', 'archived', 'deleted')", name="ck_chat_sessions_status"),
        CheckConstraint("channel IN ('ui', 'api', 'system')", name="ck_chat_sessions_channel"),
        CheckConstraint(
            "visibility IN ('user_visible', 'backend_only')",
            name="ck_chat_sessions_visibility",
        ),
        CheckConstraint(
            "persistence_mode IN ('persistent', 'ephemeral')",
            name="ck_chat_sessions_persistence_mode",
        ),
    )


class ChatSessionStats(SQLAlchemyBase):
    """
    会话统计缓存

    为聊天列表与侧边栏提供轻量统计，避免频繁扫描消息表。
    """

    __tablename__ = "chat_session_stats"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        primary_key=True,
        comment="会话ID",
    )
    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    message_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="消息总数")
    turn_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="轮次总数")
    user_message_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="用户消息数")
    assistant_message_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="助手消息数")
    tool_call_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="工具调用数")
    workflow_run_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="工作流运行数")
    total_input_tokens: Mapped[int] = mapped_column(nullable=False, default=0, comment="输入Token累计")
    total_output_tokens: Mapped[int] = mapped_column(nullable=False, default=0, comment="输出Token累计")
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0, comment="Token总量")
    last_model_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="最近一次执行模型ID")
    last_turn_status: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="最近一次轮次状态"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="更新时间"
    )


class ChatSessionCapabilityBinding(Base):
    """
    聊天会话能力挂载

    当前产品语义下，知识库、工具、MCP 等都应绑定到具体会话，而不是绑定到聊天空间。
    """

    __tablename__ = "chat_session_capability_bindings"

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属聊天会话ID",
    )
    capability_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="能力类型")
    capability_id: Mapped[UUID] = mapped_column(nullable=False, comment="能力对象ID")
    binding_role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="default", comment="绑定角色"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用"
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, comment="优先级"
    )
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="局部覆盖配置"
    )

    __table_args__ = (
        CheckConstraint(
            "capability_type IN ('knowledge_base', 'tool', 'search_provider', 'mcp_server', 'workflow', 'skill')",
            name="ck_chat_session_capability_type",
        ),
        CheckConstraint(
            "binding_role IN ('default', 'primary', 'secondary', 'optional')",
            name="ck_chat_session_binding_role",
        ),
        UniqueConstraint(
            "session_id",
            "capability_type",
            "capability_id",
            "binding_role",
            name="uq_chat_session_capability_binding",
        ),
    )
