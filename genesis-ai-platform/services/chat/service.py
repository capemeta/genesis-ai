"""聊天模块服务门面。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from services.chat.filter_inheritance import ChatFilterInheritanceMixin
from services.chat.formatting import ChatFormattingMixin
from services.chat.messages import ChatMessageMixin
from services.chat.persistence import ChatPersistenceMixin
from services.chat.retrieval_context import ChatRetrievalContextMixin
from services.chat.sessions import ChatSessionMixin
from services.chat.spaces import ChatSpaceMixin
from services.chat.turn_executor import ChatTurnExecutorMixin


class ChatService(
    ChatSpaceMixin,
    ChatSessionMixin,
    ChatMessageMixin,
    ChatTurnExecutorMixin,
    ChatRetrievalContextMixin,
    ChatFilterInheritanceMixin,
    ChatPersistenceMixin,
    ChatFormattingMixin,
):
    """
    聊天模块服务门面。

    设计原则：
    - API 层只依赖 ChatService 门面。
    - 具体业务能力按空间、会话、消息、执行、检索等职责拆分到独立模块。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
