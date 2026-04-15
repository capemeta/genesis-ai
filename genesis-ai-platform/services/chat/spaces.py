"""聊天服务拆分模块：spaces。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestException, NotFoundException
from models.chat_message import ChatMessage, ChatMessageCitation
from models.chat_session import ChatSession, ChatSessionCapabilityBinding, ChatSessionStats
from models.chat_space import ChatSpace
from models.chat_turn import ChatTurn, ChatTurnRetrieval
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.retrieval_profile import RetrievalProfile
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider
from models.platform_model import PlatformModel
from models.user import User
from models.workflow import Workflow
from rag.retrieval.hybrid import HybridRetrievalService
from schemas.chat import (
    ChatBootstrapResponse,
    ChatCapabilityBindingCreate,
    ChatCapabilityBindingUpdate,
    ChatMessageCitationRead,
    ChatMessageRead,
    ChatMessageSendRequest,
    ChatSelectorOption,
    ChatSendResponse,
    ChatSessionCreate,
    ChatSessionRead,
    ChatSessionStatsRead,
    ChatSessionUpdate,
    ChatSpaceCreate,
    ChatSpaceRead,
    ChatSpaceUpdate,
    ChatTurnRead,
    RetrievalProfileOption,
    WorkflowOption,
)



class ChatSpaceMixin:
    """按职责拆分的聊天服务能力。"""

    async def list_spaces(
        self: Any,
        *,
        current_user: User,
        search: Optional[str] = None,
        status: str = "active",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ChatSpaceRead], int]:
        """分页查询聊天空间列表。"""
        conditions = [
            ChatSpace.tenant_id == current_user.tenant_id,
            ChatSpace.owner_id == current_user.id,
        ]
        if status:
            conditions.append(ChatSpace.status == status)
        if search:
            conditions.append(ChatSpace.name.ilike(f"%{search}%"))

        total_stmt = select(func.count()).select_from(ChatSpace).where(*conditions)
        total = int((await self.db.scalar(total_stmt)) or 0)

        stmt = (
            select(ChatSpace)
            .where(*conditions)
            .order_by(ChatSpace.is_pinned.desc(), ChatSpace.display_order.asc(), ChatSpace.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [ChatSpaceRead.model_validate(row) for row in rows], total

    async def create_space(self: Any, *, data: ChatSpaceCreate, current_user: User) -> ChatSpaceRead:
        """创建聊天空间。"""
        await self._validate_entrypoint(
            tenant_id=current_user.tenant_id,
            entrypoint_type=data.entrypoint_type,
            entrypoint_id=data.entrypoint_id,
        )

        space = ChatSpace(
            **data.model_dump(),
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
            created_by_id=current_user.id,
            updated_by_id=current_user.id,
        )
        self.db.add(space)
        await self.db.commit()
        await self.db.refresh(space)
        return ChatSpaceRead.model_validate(space)

    async def get_space(self: Any, *, space_id: UUID, current_user: User) -> ChatSpaceRead:
        """获取聊天空间详情。"""
        space = await self._get_owned_space(space_id, current_user)
        return ChatSpaceRead.model_validate(space)

    async def update_space(
        self: Any,
        *,
        space_id: UUID,
        data: ChatSpaceUpdate,
        current_user: User,
    ) -> ChatSpaceRead:
        """更新聊天空间。"""
        space = await self._get_owned_space(space_id, current_user)
        update_data = data.model_dump(exclude_unset=True)

        if "entrypoint_type" in update_data or "entrypoint_id" in update_data:
            await self._validate_entrypoint(
                tenant_id=current_user.tenant_id,
                entrypoint_type=update_data.get("entrypoint_type", space.entrypoint_type),
                entrypoint_id=update_data.get("entrypoint_id", space.entrypoint_id),
            )

        for field, value in update_data.items():
            setattr(space, field, value)
        space.updated_by_id = current_user.id

        await self.db.commit()
        await self.db.refresh(space)
        return ChatSpaceRead.model_validate(space)

    async def delete_space(self: Any, *, space_id: UUID, current_user: User) -> None:
        """删除聊天空间。当前阶段采用物理删除。"""
        space = await self._get_owned_space(space_id, current_user)
        await self.db.delete(space)
        await self.db.commit()

    async def _get_owned_space(self: Any, space_id: UUID, current_user: User) -> ChatSpace:
        """获取当前用户拥有的聊天空间。"""
        stmt = select(ChatSpace).where(
            ChatSpace.id == space_id,
            ChatSpace.tenant_id == current_user.tenant_id,
            ChatSpace.owner_id == current_user.id,
        )
        space = (await self.db.execute(stmt)).scalar_one_or_none()
        if not space:
            raise NotFoundException("聊天空间不存在")
        return space
