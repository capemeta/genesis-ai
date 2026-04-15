"""聊天服务拆分模块：turn_executor。"""
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
from services.model_platform_service import ModelInvocationService
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



class ChatTurnExecutorMixin:
    """按职责拆分的聊天服务能力。"""

    async def _prepare_turn(
        self: Any,
        *,
        session_id: UUID,
        data: ChatMessageSendRequest,
        current_user: User,
    ) -> dict[str, Any]:
        """准备本轮消息与执行快照。"""
        session = await self._get_owned_session(session_id, current_user)
        space = await self._get_owned_space(session.chat_space_id, current_user)
        now = datetime.now(timezone.utc)
        effective_config = self._merge_dicts(space.default_config, session.config_override, data.config_override)
        tenant_model_id = self._coerce_optional_uuid(effective_config.get("default_model_id")) or self._resolve_tenant_model_id(session)
        effective_retrieval_profile_id = self._coerce_optional_uuid(effective_config.get("default_retrieval_profile_id")) or self._resolve_retrieval_profile_id(session)

        user_message = ChatMessage(
            tenant_id=current_user.tenant_id,
            session_id=session.id,
            role="user",
            message_type="text",
            status="completed",
            source_channel=data.source_channel,
            content=data.content,
            content_blocks=data.content_blocks,
            display_content=data.content,
            metadata_info=data.metadata_info,
            user_id=current_user.id,
        )
        self.db.add(user_message)
        await self.db.flush()

        turn = ChatTurn(
            tenant_id=current_user.tenant_id,
            session_id=session.id,
            request_id=uuid4(),
            execution_mode=self._resolve_execution_mode(space.entrypoint_type),
            status="running",
            user_message_id=user_message.id,
            effective_model_id=tenant_model_id,
            effective_retrieval_profile_id=effective_retrieval_profile_id,
            effective_config=effective_config,
            final_query=data.content,
            started_at=now,
            debug_summary={
                "source_channel": data.source_channel,
                "space_entrypoint_type": space.entrypoint_type,
            },
        )
        self.db.add(turn)
        await self.db.flush()

        assistant_message = ChatMessage(
            tenant_id=current_user.tenant_id,
            session_id=session.id,
            turn_id=turn.id,
            role="assistant",
            message_type="text",
            status="pending",
            source_channel=data.source_channel,
            content=None,
            content_blocks=[],
            display_content=None,
            metadata_info={"pending_reason": "waiting_for_execution"},
        )
        self.db.add(assistant_message)
        await self.db.flush()

        user_message.turn_id = turn.id
        turn.assistant_message_id = assistant_message.id

        session.last_message_at = now
        session.updated_by_id = current_user.id
        space.last_session_at = now
        space.updated_by_id = current_user.id

        await self._upsert_session_stats_for_send(
            session_id=session.id,
            tenant_id=current_user.tenant_id,
            effective_model_id=tenant_model_id,
            turn_status=turn.status,
            updated_at=now,
        )

        await self.db.commit()
        await self.db.refresh(session)
        await self.db.refresh(space)
        await self.db.refresh(turn)
        await self.db.refresh(user_message)
        await self.db.refresh(assistant_message)

        return {
            "session": session,
            "space": space,
            "turn": turn,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "effective_config": effective_config,
            "tenant_model_id": tenant_model_id,
        }

    async def _execute_turn(
        self: Any,
        *,
        prepared: dict[str, Any],
        current_user: User,
        stream_mode: bool,
    ) -> dict[str, Any]:
        """执行模型调用并更新轮次、消息、统计。"""
        session: ChatSession = prepared["session"]
        space: ChatSpace = prepared["space"]
        turn: ChatTurn = prepared["turn"]
        user_message: ChatMessage = prepared["user_message"]
        assistant_message: ChatMessage = prepared["assistant_message"]
        effective_config: dict[str, Any] = prepared["effective_config"]
        tenant_model_id: Optional[UUID] = prepared["tenant_model_id"]
        retrieval_package = await self._retrieve_session_context(
            session_id=session.id,
            turn_id=turn.id,
            current_user=current_user,
            query=user_message.content or "",
            effective_config=effective_config,
            tenant_model_id=tenant_model_id,
        )

        model_messages = await self._build_model_messages(
            session_id=session.id,
            current_user=current_user,
            current_user_message=user_message,
            effective_config=effective_config,
            retrieval_package=retrieval_package,
        )
        temperature, max_tokens, extra_body = self._extract_generation_options(effective_config)

        invocation_service = ModelInvocationService(self.db)
        started_perf = time.perf_counter()
        try:
            result = await invocation_service.chat(
                current_user=current_user,
                tenant_model_id=tenant_model_id,
                capability_type="chat",
                messages=model_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                extra_body=extra_body,
                request_source="chat_session_stream" if stream_mode else "chat_session",
            )
            latency_ms = int((time.perf_counter() - started_perf) * 1000)
            assistant_content = self._extract_assistant_content(result)
            usage = dict(result.get("usage") or {})
            completed_at = datetime.now(timezone.utc)
            actual_tenant_model_id = result.get("tenant_model_id") or tenant_model_id

            assistant_message.status = "completed"
            assistant_message.content = assistant_content
            assistant_message.display_content = assistant_content
            assistant_message.content_blocks = [
                {"type": "text", "text": assistant_content, "source_refs": []}
            ]
            assistant_message.metadata_info = self._merge_dicts(
                assistant_message.metadata_info,
                {
                    "model_response": {
                        "model": result.get("model"),
                        "tenant_model_id": str(result.get("tenant_model_id")) if result.get("tenant_model_id") else None,
                        "adapter_type": result.get("adapter_type"),
                    },
                    "retrieval_context": retrieval_package["summary"],
                    "persistent_context": dict((retrieval_package.get("persistent_context") or {}).get("debug") or {}),
                    "filter_inheritance": dict((retrieval_package.get("filter_inheritance") or {}).get("debug") or {}),
                },
            )

            await self._replace_assistant_citations(
                assistant_message=assistant_message,
                turn=turn,
                retrieval_package=retrieval_package,
            )

            turn.status = "completed"
            turn.effective_model_id = actual_tenant_model_id
            turn.prompt_tokens = usage.get("input_tokens")
            turn.completion_tokens = usage.get("output_tokens")
            turn.total_tokens = usage.get("total_tokens")
            turn.latency_ms = latency_ms
            turn.completed_at = completed_at
            turn.debug_summary = self._merge_dicts(
                turn.debug_summary,
                {
                    "retrieval_context": retrieval_package["summary"],
                    "persistent_context": dict((retrieval_package.get("persistent_context") or {}).get("debug") or {}),
                    "filter_inheritance": dict((retrieval_package.get("filter_inheritance") or {}).get("debug") or {}),
                    "response_model": result.get("model"),
                    "stream_mode": stream_mode,
                },
            )

            session.last_message_at = completed_at
            await self._update_session_stats_after_completion(
                session_id=session.id,
                completion_tokens=usage.get("output_tokens"),
                prompt_tokens=usage.get("input_tokens"),
                total_tokens=usage.get("total_tokens"),
                effective_model_id=actual_tenant_model_id,
                turn_status=turn.status,
                updated_at=completed_at,
            )
            await self.db.commit()
            await self.db.refresh(turn)
            await self.db.refresh(assistant_message)
            return result
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            assistant_message.status = "failed"
            assistant_message.error_message = str(exc)
            assistant_message.display_content = "模型调用失败，请稍后重试。"
            assistant_message.metadata_info = self._merge_dicts(
                assistant_message.metadata_info,
                {"failure_reason": str(exc)},
            )

            turn.status = "failed"
            turn.error_message = str(exc)
            turn.error_code = "model_invocation_failed"
            turn.completed_at = completed_at
            turn.latency_ms = int((time.perf_counter() - started_perf) * 1000)

            await self._update_session_stats_after_completion(
                session_id=session.id,
                completion_tokens=0,
                prompt_tokens=0,
                total_tokens=0,
                effective_model_id=tenant_model_id,
                turn_status=turn.status,
                updated_at=completed_at,
            )
            await self.db.commit()
            await self.db.refresh(turn)
            await self.db.refresh(assistant_message)
            raise

    async def _execute_turn_streaming(
        self: Any,
        *,
        prepared: dict[str, Any],
        current_user: User,
    ) -> AsyncIterator[dict[str, Any]]:
        """执行真实流式模型调用，并在上游返回增量时即时透传。"""
        session: ChatSession = prepared["session"]
        turn: ChatTurn = prepared["turn"]
        user_message: ChatMessage = prepared["user_message"]
        assistant_message: ChatMessage = prepared["assistant_message"]
        effective_config: dict[str, Any] = prepared["effective_config"]
        tenant_model_id: Optional[UUID] = prepared["tenant_model_id"]
        retrieval_package = await self._retrieve_session_context(
            session_id=session.id,
            turn_id=turn.id,
            current_user=current_user,
            query=user_message.content or "",
            effective_config=effective_config,
            tenant_model_id=tenant_model_id,
        )

        model_messages = await self._build_model_messages(
            session_id=session.id,
            current_user=current_user,
            current_user_message=user_message,
            effective_config=effective_config,
            retrieval_package=retrieval_package,
        )
        temperature, max_tokens, extra_body = self._extract_generation_options(effective_config)

        invocation_service = ModelInvocationService(self.db)
        started_perf = time.perf_counter()
        assistant_content_parts: list[str] = []
        usage: dict[str, Any] = {}
        try:
            async for raw_chunk in invocation_service.stream_chat(
                current_user=current_user,
                tenant_model_id=tenant_model_id,
                capability_type="chat",
                messages=model_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
                request_source="chat_session_stream",
            ):
                usage = self._merge_stream_usage(usage, raw_chunk)
                delta = self._extract_stream_delta(raw_chunk)
                if not delta:
                    continue
                assistant_content_parts.append(delta)
                yield {"type": "delta", "delta": delta}

            latency_ms = int((time.perf_counter() - started_perf) * 1000)
            completed_at = datetime.now(timezone.utc)
            assistant_content = "".join(assistant_content_parts)

            assistant_message.status = "completed"
            assistant_message.content = assistant_content
            assistant_message.display_content = assistant_content
            assistant_message.content_blocks = [
                {"type": "text", "text": assistant_content, "source_refs": []}
            ]
            assistant_message.metadata_info = self._merge_dicts(
                assistant_message.metadata_info,
                {
                    "retrieval_context": retrieval_package["summary"],
                    "persistent_context": dict((retrieval_package.get("persistent_context") or {}).get("debug") or {}),
                    "filter_inheritance": dict((retrieval_package.get("filter_inheritance") or {}).get("debug") or {}),
                    "stream_mode": True,
                },
            )

            await self._replace_assistant_citations(
                assistant_message=assistant_message,
                turn=turn,
                retrieval_package=retrieval_package,
            )

            turn.status = "completed"
            turn.prompt_tokens = usage.get("input_tokens")
            turn.completion_tokens = usage.get("output_tokens")
            turn.total_tokens = usage.get("total_tokens")
            turn.latency_ms = latency_ms
            turn.completed_at = completed_at
            turn.debug_summary = self._merge_dicts(
                turn.debug_summary,
                {
                    "retrieval_context": retrieval_package["summary"],
                    "persistent_context": dict((retrieval_package.get("persistent_context") or {}).get("debug") or {}),
                    "filter_inheritance": dict((retrieval_package.get("filter_inheritance") or {}).get("debug") or {}),
                    "stream_mode": True,
                },
            )

            session.last_message_at = completed_at
            await self._update_session_stats_after_completion(
                session_id=session.id,
                completion_tokens=usage.get("output_tokens"),
                prompt_tokens=usage.get("input_tokens"),
                total_tokens=usage.get("total_tokens"),
                effective_model_id=tenant_model_id,
                turn_status=turn.status,
                updated_at=completed_at,
            )
            await self.db.commit()
            await self.db.refresh(turn)
            await self.db.refresh(assistant_message)
            yield {
                "type": "completed",
                "result": {
                    "usage": usage,
                    "choices": [{"message": {"role": "assistant", "content": assistant_content}}],
                },
            }
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            assistant_message.status = "failed"
            assistant_message.error_message = str(exc)
            assistant_message.display_content = "模型调用失败，请稍后重试。"
            assistant_message.metadata_info = self._merge_dicts(
                assistant_message.metadata_info,
                {"failure_reason": str(exc)},
            )

            turn.status = "failed"
            turn.error_message = str(exc)
            turn.error_code = "model_invocation_failed"
            turn.completed_at = completed_at
            turn.latency_ms = int((time.perf_counter() - started_perf) * 1000)

            await self._update_session_stats_after_completion(
                session_id=session.id,
                completion_tokens=0,
                prompt_tokens=0,
                total_tokens=0,
                effective_model_id=tenant_model_id,
                turn_status=turn.status,
                updated_at=completed_at,
            )
            await self.db.commit()
            await self.db.refresh(turn)
            await self.db.refresh(assistant_message)
            raise

    async def _update_session_stats_after_completion(
        self: Any,
        *,
        session_id: UUID,
        completion_tokens: Optional[int],
        prompt_tokens: Optional[int],
        total_tokens: Optional[int],
        effective_model_id: Optional[UUID],
        turn_status: str,
        updated_at: datetime,
    ) -> None:
        """模型返回后补齐 token 和轮次状态统计。"""
        stats = await self.db.get(ChatSessionStats, session_id)
        if not stats:
            return
        stats.total_input_tokens += int(prompt_tokens or 0)
        stats.total_output_tokens += int(completion_tokens or 0)
        stats.total_tokens += int(total_tokens or 0)
        stats.last_model_id = effective_model_id
        stats.last_turn_status = turn_status
        stats.updated_at = updated_at

    async def _build_model_messages(
        self: Any,
        *,
        session_id: UUID,
        current_user: User,
        current_user_message: ChatMessage,
        effective_config: dict[str, Any],
        retrieval_package: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """组装发往大模型的消息列表。"""
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.tenant_id == current_user.tenant_id,
                ChatMessage.session_id == session_id,
                ChatMessage.id != current_user_message.id,
                ChatMessage.role.in_(["system", "user", "assistant"]),
                ChatMessage.status == "completed",
            )
            .order_by(ChatMessage.created_at.asc())
        )
        history_messages = (await self.db.execute(stmt)).scalars().all()

        model_messages: list[dict[str, Any]] = []
        system_prompt = str(effective_config.get("system_prompt") or "").strip()
        if system_prompt:
            model_messages.append({"role": "system", "content": system_prompt})

        retrieval_prompt = self._build_retrieval_context_prompt(retrieval_package)
        if retrieval_prompt:
            model_messages.append({"role": "system", "content": retrieval_prompt})

        for item in history_messages:
            if not item.content:
                continue
            model_messages.append({"role": item.role, "content": item.content})

        model_messages.append({"role": "user", "content": current_user_message.content or ""})
        return model_messages
