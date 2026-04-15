"""聊天服务拆分模块：sessions。"""
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



class ChatSessionMixin:
    """按职责拆分的聊天服务能力。"""

    async def list_session_capabilities(
        self: Any,
        *,
        session_id: UUID,
        current_user: User,
    ) -> list[dict[str, Any]]:
        """获取聊天会话能力挂载列表。"""
        await self._get_owned_session(session_id, current_user)
        stmt = (
            select(ChatSessionCapabilityBinding)
            .where(
                ChatSessionCapabilityBinding.tenant_id == current_user.tenant_id,
                ChatSessionCapabilityBinding.session_id == session_id,
            )
            .order_by(ChatSessionCapabilityBinding.priority.asc(), ChatSessionCapabilityBinding.created_at.asc())
        )
        bindings = (await self.db.execute(stmt)).scalars().all()
        return [self._serialize_capability_binding(item) for item in bindings]

    async def create_session_capability(
        self: Any,
        *,
        session_id: UUID,
        data: ChatCapabilityBindingCreate,
        current_user: User,
    ) -> dict[str, Any]:
        """新增聊天会话能力挂载。"""
        await self._get_owned_session(session_id, current_user)
        await self._validate_capability_reference(
            tenant_id=current_user.tenant_id,
            capability_type=data.capability_type,
            capability_id=data.capability_id,
        )

        stmt = select(ChatSessionCapabilityBinding).where(
            ChatSessionCapabilityBinding.tenant_id == current_user.tenant_id,
            ChatSessionCapabilityBinding.session_id == session_id,
            ChatSessionCapabilityBinding.capability_type == data.capability_type,
            ChatSessionCapabilityBinding.capability_id == data.capability_id,
            ChatSessionCapabilityBinding.binding_role == data.binding_role,
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise BadRequestException("该能力已挂载到当前聊天会话，请勿重复添加")

        binding = ChatSessionCapabilityBinding(
            tenant_id=current_user.tenant_id,
            session_id=session_id,
            **data.model_dump(),
        )
        self.db.add(binding)
        await self.db.commit()
        await self.db.refresh(binding)
        return self._serialize_capability_binding(binding)

    async def update_session_capability(
        self: Any,
        *,
        session_id: UUID,
        binding_id: UUID,
        data: ChatCapabilityBindingUpdate,
        current_user: User,
    ) -> dict[str, Any]:
        """更新聊天会话能力挂载。"""
        await self._get_owned_session(session_id, current_user)
        binding = await self._get_session_capability_binding(
            session_id=session_id,
            binding_id=binding_id,
            current_user=current_user,
        )
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(binding, field, value)

        await self.db.commit()
        await self.db.refresh(binding)
        return self._serialize_capability_binding(binding)

    async def delete_session_capability(
        self: Any,
        *,
        session_id: UUID,
        binding_id: UUID,
        current_user: User,
    ) -> None:
        """删除聊天会话能力挂载。"""
        await self._get_owned_session(session_id, current_user)
        binding = await self._get_session_capability_binding(
            session_id=session_id,
            binding_id=binding_id,
            current_user=current_user,
        )
        await self.db.delete(binding)
        await self.db.commit()

    async def list_sessions(
        self: Any,
        *,
        space_id: UUID,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        status: str = "active",
    ) -> tuple[list[ChatSessionRead], int]:
        """分页获取聊天空间下的会话列表。"""
        await self._get_owned_space(space_id, current_user)
        conditions = [
            ChatSession.tenant_id == current_user.tenant_id,
            ChatSession.chat_space_id == space_id,
            ChatSession.owner_id == current_user.id,
        ]
        if status:
            conditions.append(ChatSession.status == status)

        total_stmt = select(func.count()).select_from(ChatSession).where(*conditions)
        total = int((await self.db.scalar(total_stmt)) or 0)

        stmt = (
            select(ChatSession, ChatSessionStats)
            .outerjoin(ChatSessionStats, ChatSessionStats.session_id == ChatSession.id)
            .where(*conditions)
            .order_by(ChatSession.is_pinned.desc(), ChatSession.display_order.asc(), ChatSession.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).all()
        return [self._build_session_read(session, stats) for session, stats in rows], total

    async def create_session(
        self: Any,
        *,
        space_id: UUID,
        data: ChatSessionCreate,
        current_user: User,
    ) -> ChatSessionRead:
        """在聊天空间下创建新会话。"""
        space = await self._get_owned_space(space_id, current_user)
        now = datetime.now(timezone.utc)
        await self._validate_session_config_override(
            tenant_id=current_user.tenant_id,
            config_override=data.config_override,
        )

        session = ChatSession(
            tenant_id=current_user.tenant_id,
            chat_space_id=space_id,
            owner_id=current_user.id,
            created_by_id=current_user.id,
            updated_by_id=current_user.id,
            **data.model_dump(),
        )
        self.db.add(session)
        await self.db.flush()

        stats = ChatSessionStats(
            session_id=session.id,
            tenant_id=current_user.tenant_id,
            updated_at=now,
        )
        self.db.add(stats)

        space.last_session_at = now
        space.updated_by_id = current_user.id

        await self.db.commit()
        await self.db.refresh(session)
        await self.db.refresh(stats)
        return self._build_session_read(session, stats)

    async def get_session(self: Any, *, session_id: UUID, current_user: User) -> ChatSessionRead:
        """获取会话详情及统计。"""
        base_session = await self._get_owned_session(session_id, current_user)
        stmt = (
            select(ChatSession, ChatSessionStats)
            .outerjoin(ChatSessionStats, ChatSessionStats.session_id == ChatSession.id)
            .where(
                ChatSession.id == base_session.id,
                ChatSession.tenant_id == current_user.tenant_id,
                ChatSession.owner_id == current_user.id,
            )
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if not row:
            raise NotFoundException("聊天会话不存在")
        session, stats = row
        capabilities = await self.list_session_capabilities(session_id=base_session.id, current_user=current_user)
        return self._build_session_read(session, stats, capabilities)

    async def update_session(
        self: Any,
        *,
        session_id: UUID,
        data: ChatSessionUpdate,
        current_user: User,
    ) -> ChatSessionRead:
        """更新会话信息。"""
        session = await self._get_owned_session(session_id, current_user)
        update_data = data.model_dump(exclude_unset=True)
        now = datetime.now(timezone.utc)

        if "config_override" in update_data:
            await self._validate_session_config_override(
                tenant_id=current_user.tenant_id,
                config_override=update_data.get("config_override") or {},
            )

        for field, value in update_data.items():
            setattr(session, field, value)

        if update_data.get("status") == "archived":
            session.archived_at = now
            session.deleted_at = None
        elif update_data.get("status") == "active":
            session.archived_at = None
            session.deleted_at = None
        elif update_data.get("status") == "deleted":
            session.deleted_at = now

        session.updated_by_id = current_user.id
        await self.db.commit()
        if update_data.get("status") == "deleted":
            # 删除后仍需返回本次更新结果，因此要先显式刷新对象，避免提交后属性过期再触发异步懒加载。
            await self.db.refresh(session)
            stats = await self.db.get(ChatSessionStats, session_id)
            if stats:
                await self.db.refresh(stats)
            capabilities = await self.list_session_capabilities(session_id=session_id, current_user=current_user)
            return self._build_session_read(session, stats, capabilities)
        return await self.get_session(session_id=session_id, current_user=current_user)

    async def _get_owned_session(
        self: Any,
        session_id: UUID,
        current_user: User,
        *,
        allow_deleted: bool = False,
    ) -> ChatSession:
        """获取当前用户拥有的聊天会话。"""
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == current_user.tenant_id,
            ChatSession.owner_id == current_user.id,
        )
        if not allow_deleted:
            stmt = stmt.where(ChatSession.status != "deleted")
        session = (await self.db.execute(stmt)).scalar_one_or_none()
        if not session:
            raise NotFoundException("聊天会话不存在")
        return session

    async def _get_session_capability_binding(
        self: Any,
        *,
        session_id: UUID,
        binding_id: UUID,
        current_user: User,
    ) -> ChatSessionCapabilityBinding:
        """获取聊天会话能力挂载。"""
        stmt = select(ChatSessionCapabilityBinding).where(
            ChatSessionCapabilityBinding.id == binding_id,
            ChatSessionCapabilityBinding.tenant_id == current_user.tenant_id,
            ChatSessionCapabilityBinding.session_id == session_id,
        )
        binding = (await self.db.execute(stmt)).scalar_one_or_none()
        if not binding:
            raise NotFoundException("能力挂载不存在")
        return binding

    async def _validate_entrypoint(
        self: Any,
        *,
        tenant_id: UUID,
        entrypoint_type: str,
        entrypoint_id: Optional[UUID],
    ) -> None:
        """校验入口对象是否合法。"""
        if not entrypoint_id:
            return
        if entrypoint_type == "workflow":
            stmt = select(Workflow.id).where(
                Workflow.id == entrypoint_id,
                Workflow.tenant_id == tenant_id,
            )
            workflow_id = await self.db.scalar(stmt)
            if not workflow_id:
                raise BadRequestException("指定的工作流不存在或不属于当前租户")

    async def _validate_model_id(self: Any, tenant_id: UUID, model_id: Optional[UUID]) -> None:
        """校验默认模型是否存在。此处绑定 tenant_model_id。"""
        if not model_id:
            return
        stmt = select(TenantModel.id).where(
            TenantModel.id == model_id,
            TenantModel.tenant_id == tenant_id,
            TenantModel.resource_scope == "tenant",
            TenantModel.is_enabled.is_(True),
        )
        if not await self.db.scalar(stmt):
            raise BadRequestException("指定的默认模型不存在或未启用")

    async def _validate_retrieval_profile_id(
        self: Any,
        tenant_id: UUID,
        retrieval_profile_id: Optional[UUID],
    ) -> None:
        """校验检索模板是否存在。"""
        if not retrieval_profile_id:
            return
        stmt = select(RetrievalProfile.id).where(
            RetrievalProfile.id == retrieval_profile_id,
            RetrievalProfile.tenant_id == tenant_id,
        )
        if not await self.db.scalar(stmt):
            raise BadRequestException("指定的检索模板不存在")

    async def _validate_session_config_override(
        self: Any,
        *,
        tenant_id: UUID,
        config_override: dict[str, Any],
    ) -> None:
        """校验会话级配置中的强引用对象。"""
        await self._validate_model_id(
            tenant_id,
            self._coerce_optional_uuid((config_override or {}).get("default_model_id")),
        )
        await self._validate_retrieval_profile_id(
            tenant_id,
            self._coerce_optional_uuid((config_override or {}).get("default_retrieval_profile_id")),
        )

    async def _validate_capability_reference(
        self: Any,
        *,
        tenant_id: UUID,
        capability_type: str,
        capability_id: UUID,
    ) -> None:
        """校验能力挂载引用。当前阶段只校验已实现的核心对象。"""
        stmt = None
        if capability_type == "knowledge_base":
            stmt = select(KnowledgeBase.id).where(
                KnowledgeBase.id == capability_id,
                KnowledgeBase.tenant_id == tenant_id,
            )
        elif capability_type == "workflow":
            stmt = select(Workflow.id).where(
                Workflow.id == capability_id,
                Workflow.tenant_id == tenant_id,
            )
        if stmt is not None and not await self.db.scalar(stmt):
            raise BadRequestException("能力对象不存在或不属于当前租户")
