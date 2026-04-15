"""聊天服务拆分模块：messages。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional
from uuid import UUID, uuid4

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestException, NotFoundException
from models.chat_message import ChatMessage, ChatMessageCitation
from models.chat_session import ChatSession, ChatSessionCapabilityBinding, ChatSessionStats
from models.chat_space import ChatSpace
from models.chat_turn import ChatTurn, ChatTurnRetrieval
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.model_provider_definition import ModelProviderDefinition
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



class ChatMessageMixin:
    """按职责拆分的聊天服务能力。"""

    async def list_messages(
        self: Any,
        *,
        session_id: UUID,
        current_user: User,
        include_backend_only: bool = False,
    ) -> list[ChatMessageRead]:
        """获取会话消息列表。"""
        await self._get_owned_session(session_id, current_user)
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.tenant_id == current_user.tenant_id,
                ChatMessage.session_id == session_id,
            )
            .order_by(
                ChatMessage.created_at.asc(),
                func.coalesce(ChatMessage.turn_id, ChatMessage.id).asc(),
                case(
                    (ChatMessage.role == "system", 0),
                    (ChatMessage.role == "user", 1),
                    (ChatMessage.role == "assistant", 2),
                    (ChatMessage.role == "tool", 3),
                    else_=9,
                ).asc(),
                ChatMessage.updated_at.asc(),
                ChatMessage.id.asc(),
            )
        )
        if not include_backend_only:
            stmt = stmt.where(ChatMessage.is_visible.is_(True))
        messages = (await self.db.execute(stmt)).scalars().all()
        message_ids = [item.id for item in messages]
        citation_map = await self._load_citation_map(message_ids)

        items: list[ChatMessageRead] = []
        for message in messages:
            item = ChatMessageRead.model_validate(message)
            item.citations = [
                ChatMessageCitationRead.model_validate(citation)
                for citation in citation_map.get(message.id, [])
            ]
            items.append(item)
        return items

    async def clear_session_messages(
        self: Any,
        *,
        session_id: UUID,
        current_user: User,
    ) -> None:
        """清空当前会话下全部消息与执行轮次（会话与配置保留）。"""
        session = await self._get_owned_session(session_id, current_user)
        tenant_id = current_user.tenant_id
        now = datetime.now(timezone.utc)

        # 先删轮次：子表（检索明细、工具调用、工作流运行）随 ON DELETE CASCADE 一并清理；消息上 turn_id 会 SET NULL
        await self.db.execute(
            delete(ChatTurn).where(
                ChatTurn.tenant_id == tenant_id,
                ChatTurn.session_id == session_id,
            )
        )
        # 解除消息自引用，避免批量删除时外键顺序问题
        await self.db.execute(
            update(ChatMessage)
            .where(
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.session_id == session_id,
            )
            .values(parent_message_id=None, replaces_message_id=None)
        )
        await self.db.execute(
            delete(ChatMessage).where(
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.session_id == session_id,
            )
        )

        stats = await self.db.get(ChatSessionStats, session_id)
        if stats:
            stats.message_count = 0
            stats.turn_count = 0
            stats.user_message_count = 0
            stats.assistant_message_count = 0
            stats.tool_call_count = 0
            stats.workflow_run_count = 0
            stats.total_input_tokens = 0
            stats.total_output_tokens = 0
            stats.total_tokens = 0
            stats.last_model_id = None
            stats.last_turn_status = None
            stats.updated_at = now

        session.last_message_at = None
        session.summary = None
        session.updated_by_id = current_user.id

        await self.db.commit()

    async def send_message(
        self: Any,
        *,
        session_id: UUID,
        data: ChatMessageSendRequest,
        current_user: User,
    ) -> ChatSendResponse:
        """
        发送消息并创建标准执行轮次占位。

        当前阶段实现：
        - 用户消息落库
        - 轮次快照创建
        - 基于租户模型直接调用大模型
        - 若空间绑定知识库，则注入“模拟知识库上下文”提示
        """
        prepared = await self._prepare_turn(
            session_id=session_id,
            data=data,
            current_user=current_user,
        )
        try:
            await self._execute_turn(
                prepared=prepared,
                current_user=current_user,
                stream_mode=False,
            )
        except Exception:
            raise

        return ChatSendResponse(
            session=await self.get_session(session_id=prepared["session"].id, current_user=current_user),
            turn=ChatTurnRead.model_validate(prepared["turn"]),
            user_message=ChatMessageRead.model_validate(prepared["user_message"]),
            assistant_message=ChatMessageRead.model_validate(prepared["assistant_message"]),
        )

    async def stream_message(
        self: Any,
        *,
        session_id: UUID,
        data: ChatMessageSendRequest,
        current_user: User,
    ) -> AsyncIterator[str]:
        """
        以 SSE 形式发送消息。

        当前阶段说明：
        - 消息状态流转是真实的
        - SSE 协议是真实的
        - 上游模型调用也是真实流式，模型返回增量后立即透传给前端
        """
        prepared = await self._prepare_turn(
            session_id=session_id,
            data=data,
            current_user=current_user,
        )
        session_id_text = str(prepared["session"].id)
        turn_id_text = str(prepared["turn"].id)
        assistant_message_id_text = str(prepared["assistant_message"].id)

        yield self._format_sse(
            event="turn.created",
            data={
                "session": self._safe_model_dump(await self.get_session(session_id=prepared["session"].id, current_user=current_user)),
                "turn": self._safe_model_dump(ChatTurnRead.model_validate(prepared["turn"])),
                "user_message": self._safe_model_dump(ChatMessageRead.model_validate(prepared["user_message"])),
                "assistant_message": self._safe_model_dump(ChatMessageRead.model_validate(prepared["assistant_message"])),
            },
        )

        try:
            assistant_message = prepared["assistant_message"]
            assistant_message.status = "streaming"
            await self.db.commit()
            await self.db.refresh(assistant_message)

            yield self._format_sse(
                event="assistant.status",
                data={
                    "message_id": str(assistant_message.id),
                    "turn_id": turn_id_text,
                    "status": "streaming",
                },
            )

            index = 0
            async for stream_event in self._execute_turn_streaming(
                prepared=prepared,
                current_user=current_user,
            ):
                if stream_event["type"] == "completed":
                    result = stream_event["result"]
                    break
                chunk = str(stream_event.get("delta") or "")
                if not chunk:
                    continue
                yield self._format_sse(
                    event="assistant.delta",
                    data={
                        "message_id": str(assistant_message.id),
                        "turn_id": turn_id_text,
                        "index": index,
                        "delta": chunk,
                    },
                )
                index += 1
                await asyncio.sleep(0)
            else:
                result = {"usage": {}}

            await self.db.refresh(assistant_message)
            yield self._format_sse(
                event="assistant.completed",
                data={
                    "session": self._safe_model_dump(await self.get_session(session_id=UUID(session_id_text), current_user=current_user)),
                    "turn": self._safe_model_dump(ChatTurnRead.model_validate(prepared["turn"])),
                    "assistant_message": self._safe_model_dump(ChatMessageRead.model_validate(assistant_message)),
                    "usage": result.get("usage", {}),
                },
            )
        except asyncio.CancelledError:
            # 客户端主动断开连接时应立即结束，不写入额外 SSE 失败事件。
            raise
        except Exception as exc:
            # 如果异常来自 flush/commit，Session 会进入 pending rollback 状态；
            # 先回滚，避免格式化失败事件时再次触发 SQLAlchemy 懒加载异常。
            try:
                await self.db.rollback()
            except Exception:
                pass
            yield self._format_sse(
                event="assistant.failed",
                data={
                    "turn_id": turn_id_text,
                    "message_id": assistant_message_id_text,
                    "error": str(exc),
                },
            )
            # SSE 响应一旦开始发送，不能再向上抛出异常，否则会触发
            # "Caught handled exception, but response already started."。
            return

    async def get_bootstrap_options(self: Any, *, current_user: User) -> ChatBootstrapResponse:
        """获取聊天页面初始化所需的下拉选项。"""
        retrieval_stmt = (
            select(RetrievalProfile)
            .where(
                RetrievalProfile.tenant_id == current_user.tenant_id,
                RetrievalProfile.status == "active",
            )
            .order_by(RetrievalProfile.updated_at.desc())
        )
        workflow_stmt = (
            select(Workflow)
            .where(
                Workflow.tenant_id == current_user.tenant_id,
                Workflow.status.in_(["draft", "active"]),
            )
            .order_by(Workflow.updated_at.desc())
        )
        kb_stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.tenant_id == current_user.tenant_id)
            .order_by(KnowledgeBase.updated_at.desc())
        )
        # 聊天侧候选模型需要同时尊重模型级和厂商级的启用/展示开关，
        # 避免厂商被隐藏后，前端仍然看到其下属模型。
        model_stmt = (
            select(
                TenantModel,
                PlatformModel,
                func.coalesce(
                    func.nullif(ModelProviderDefinition.display_name, ""),
                    func.nullif(TenantModelProvider.name, ""),
                    "未知厂商",
                ).label("provider_name"),
                ModelProviderDefinition.provider_code.label("provider_code"),
            )
            .join(PlatformModel, PlatformModel.id == TenantModel.platform_model_id)
            .join(TenantModelProvider, TenantModelProvider.id == TenantModel.tenant_provider_id)
            .outerjoin(
                ModelProviderDefinition,
                ModelProviderDefinition.id == TenantModelProvider.provider_definition_id,
            )
            .where(
                TenantModel.tenant_id == current_user.tenant_id,
                TenantModel.resource_scope == "tenant",
                TenantModel.is_enabled.is_(True),
                TenantModel.is_visible_in_ui.is_(True),
                TenantModelProvider.tenant_id == current_user.tenant_id,
                TenantModelProvider.resource_scope == "tenant",
                TenantModelProvider.is_enabled.is_(True),
                TenantModelProvider.is_visible_in_ui.is_(True),
                TenantModel.model_type == "chat",
                PlatformModel.is_enabled.is_(True),
            )
            .order_by(TenantModel.priority.asc(), PlatformModel.display_name.asc())
        )
        rerank_model_stmt = (
            select(
                TenantModel,
                PlatformModel,
                func.coalesce(
                    func.nullif(ModelProviderDefinition.display_name, ""),
                    func.nullif(TenantModelProvider.name, ""),
                    "未知厂商",
                ).label("provider_name"),
                ModelProviderDefinition.provider_code.label("provider_code"),
            )
            .join(PlatformModel, PlatformModel.id == TenantModel.platform_model_id)
            .join(TenantModelProvider, TenantModelProvider.id == TenantModel.tenant_provider_id)
            .outerjoin(
                ModelProviderDefinition,
                ModelProviderDefinition.id == TenantModelProvider.provider_definition_id,
            )
            .where(
                TenantModel.tenant_id == current_user.tenant_id,
                TenantModel.resource_scope == "tenant",
                TenantModel.is_enabled.is_(True),
                TenantModel.is_visible_in_ui.is_(True),
                TenantModelProvider.tenant_id == current_user.tenant_id,
                TenantModelProvider.resource_scope == "tenant",
                TenantModelProvider.is_enabled.is_(True),
                TenantModelProvider.is_visible_in_ui.is_(True),
                TenantModel.model_type == "rerank",
                PlatformModel.is_enabled.is_(True),
            )
            .order_by(TenantModel.priority.asc(), PlatformModel.display_name.asc())
        )

        retrieval_profiles = (await self.db.execute(retrieval_stmt)).scalars().all()
        workflows = (await self.db.execute(workflow_stmt)).scalars().all()
        knowledge_bases = (await self.db.execute(kb_stmt)).scalars().all()
        model_rows = (await self.db.execute(model_stmt)).all()
        rerank_model_rows = (await self.db.execute(rerank_model_stmt)).all()

        return ChatBootstrapResponse(
            retrieval_profiles=[RetrievalProfileOption.model_validate(item) for item in retrieval_profiles],
            workflows=[WorkflowOption.model_validate(item) for item in workflows],
            knowledge_bases=[
                ChatSelectorOption(
                    id=item.id,
                    name=item.name,
                    description=item.description,
                    extra={"visibility": item.visibility, "type": item.type},
                )
                for item in knowledge_bases
            ],
            models=[
                ChatSelectorOption(
                    id=tenant_model.id,
                    name=tenant_model.model_alias or platform_model.display_name,
                    description=platform_model.description,
                    extra={
                        "platform_model_id": str(platform_model.id),
                        "model_key": platform_model.model_key,
                        "model_type": tenant_model.model_type,
                        "supports_tools": platform_model.supports_tools,
                        "provider_name": provider_name,
                        "provider_display_name": provider_name,
                        "provider_code": provider_code,
                        "provider_id": str(tenant_model.tenant_provider_id),
                    },
                )
                for tenant_model, platform_model, provider_name, provider_code in model_rows
            ],
            rerank_models=[
                ChatSelectorOption(
                    id=tenant_model.id,
                    name=tenant_model.model_alias or platform_model.display_name,
                    description=platform_model.description,
                    extra={
                        "platform_model_id": str(platform_model.id),
                        "model_key": platform_model.model_key,
                        "model_type": tenant_model.model_type,
                        "provider_name": provider_name,
                        "provider_display_name": provider_name,
                        "provider_code": provider_code,
                        "provider_id": str(tenant_model.tenant_provider_id),
                    },
                )
                for tenant_model, platform_model, provider_name, provider_code in rerank_model_rows
            ],
        )

    async def list_knowledge_base_picker_options(
        self: Any,
        *,
        current_user: User,
        page: int,
        page_size: int,
        search: str | None,
        exclude_ids: list[UUID],
    ) -> tuple[list[ChatSelectorOption], int]:
        """聊天侧栏专用：可选知识库分页列表，服务端排除已挂载项（不经过知识库列表页 CRUD）。"""
        conditions = [KnowledgeBase.tenant_id == current_user.tenant_id]
        if exclude_ids:
            conditions.append(KnowledgeBase.id.notin_(exclude_ids))
        normalized = (search or "").strip()
        if normalized:
            like = f"%{normalized}%"
            conditions.append(
                or_(
                    KnowledgeBase.name.ilike(like),
                    KnowledgeBase.description.ilike(like),
                )
            )

        count_stmt = select(func.count(KnowledgeBase.id)).where(*conditions)
        total = int((await self.db.execute(count_stmt)).scalar_one() or 0)

        offset = (page - 1) * page_size
        list_stmt = (
            select(KnowledgeBase)
            .where(*conditions)
            .order_by(KnowledgeBase.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self.db.execute(list_stmt)).scalars().all()
        options = [
            ChatSelectorOption(
                id=item.id,
                name=item.name,
                description=item.description,
                extra={"visibility": item.visibility, "type": item.type},
            )
            for item in rows
        ]
        return options, total
