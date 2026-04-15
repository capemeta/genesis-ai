"""
聊天消息相关模型
"""
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.session import Base as SQLAlchemyBase
from models.base import Base


class ChatMessage(Base):
    """
    聊天消息

    只承载消息流，不承载执行明细。
    """

    __tablename__ = "chat_messages"

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )
    turn_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("chat_turns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属轮次ID",
    )
    parent_message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="父消息ID",
    )
    replaces_message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="被替代的旧消息ID",
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, comment="角色")
    message_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="text", comment="消息类型"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed", comment="消息状态"
    )
    source_channel: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源渠道"
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="主文本内容")
    content_blocks: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, comment="富内容块"
    )
    display_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展示内容"
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="错误码"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="错误信息"
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否对前端可见"
    )
    metadata_info: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, comment="扩展元数据"
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="关联用户ID")

    __table_args__ = (
        CheckConstraint("role IN ('system', 'user', 'assistant', 'tool')", name="ck_chat_messages_role"),
        CheckConstraint(
            "message_type IN ('text', 'event', 'tool_call', 'tool_result', 'workflow_event', 'file', 'citation_card')",
            name="ck_chat_messages_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'streaming', 'completed', 'failed', 'cancelled')",
            name="ck_chat_messages_status",
        ),
        CheckConstraint(
            "source_channel IN ('ui', 'api', 'system')",
            name="ck_chat_messages_source_channel",
        ),
    )


class ChatMessageCitation(SQLAlchemyBase):
    """
    消息引用

    由于数据库中该表缺少 updated_at 字段且当前环境无权修改表结构，
    此处不继承业务 Base 类，而是直接继承 SQLAlchemyBase 并手动定义必要字段，
    显式排除 updated_at 字段。
    """

    __tablename__ = "chat_message_citations"

    # 手动定义 Base 中的通用字段，排除 updated_at
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )
    turn_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, index=True, comment="所属轮次ID")
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属消息ID",
    )
    citation_index: Mapped[int] = mapped_column(nullable=False, comment="引用序号")
    kb_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="知识库ID")
    kb_doc_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="知识库文档挂载ID")
    chunk_id: Mapped[Optional[int]] = mapped_column(nullable=True, comment="分块ID")
    source_anchor: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="来源锚点")
    page_number: Mapped[Optional[int]] = mapped_column(nullable=True, comment="页码")
    snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="引用片段")
    score: Mapped[Optional[float]] = mapped_column(nullable=True, comment="引用分值")
    metadata_info: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, comment="扩展元数据"
    )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"
