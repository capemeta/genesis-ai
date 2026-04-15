"""聊天服务拆分模块：formatting。"""
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



class ChatFormattingMixin:
    """按职责拆分的聊天服务能力。"""

    @staticmethod
    def _resolve_tenant_model_id(session: ChatSession) -> Optional[UUID]:
        """解析会话级默认模型。"""
        session_model_id = (session.config_override or {}).get("default_model_id")
        if session_model_id:
            return UUID(str(session_model_id))
        return None

    @staticmethod
    def _resolve_retrieval_profile_id(session: ChatSession) -> Optional[UUID]:
        """解析会话级检索配置模板。当前前端已不暴露该项，但后端仍保留兼容扩展位。"""
        retrieval_profile_id = (session.config_override or {}).get("default_retrieval_profile_id")
        if retrieval_profile_id:
            return UUID(str(retrieval_profile_id))
        return None

    @staticmethod
    def _extract_generation_options(
        effective_config: dict[str, Any],
    ) -> tuple[Optional[float], Optional[int], dict[str, Any]]:
        """从会话配置中提取模型生成参数。"""
        temperature = effective_config.get("temperature")
        max_tokens = effective_config.get("max_tokens")
        extra_body: dict[str, Any] = {}
        for key in ("top_p", "presence_penalty", "frequency_penalty", "reasoning_effort"):
            if key in effective_config:
                extra_body[key] = effective_config[key]
        return temperature, max_tokens, extra_body

    @staticmethod
    def _extract_assistant_content(result: dict[str, Any]) -> str:
        """从统一模型响应中提取助手文本。"""
        choices = list(result.get("choices") or [])
        if not choices:
            return ""
        message = dict((choices[0] or {}).get("message") or {})
        return str(message.get("content") or "")

    @staticmethod
    def _extract_stream_delta(chunk: dict[str, Any]) -> str:
        """从不同上游协议的流式 chunk 中提取文本增量。"""
        choices = list(chunk.get("choices") or [])
        if choices:
            delta = dict((choices[0] or {}).get("delta") or {})
            if "content" in delta:
                return str(delta.get("content") or "")
            message = dict((choices[0] or {}).get("message") or {})
            if "content" in message:
                return str(message.get("content") or "")

        message = dict(chunk.get("message") or {})
        if "content" in message:
            return str(message.get("content") or "")

        return str(chunk.get("content") or "")

    @staticmethod
    def _merge_stream_usage(current: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
        """合并流式响应中的 token 用量；多数上游只在最后一帧返回。"""
        raw_usage = dict(chunk.get("usage") or {})
        if not raw_usage and ("prompt_eval_count" in chunk or "eval_count" in chunk):
            raw_usage = {
                "prompt_eval_count": chunk.get("prompt_eval_count"),
                "eval_count": chunk.get("eval_count"),
            }
        if not raw_usage:
            return current

        next_usage = dict(current)
        if "prompt_tokens" in raw_usage:
            next_usage["input_tokens"] = raw_usage.get("prompt_tokens")
        if "completion_tokens" in raw_usage:
            next_usage["output_tokens"] = raw_usage.get("completion_tokens")
        if "total_tokens" in raw_usage:
            next_usage["total_tokens"] = raw_usage.get("total_tokens")
        if "prompt_eval_count" in raw_usage:
            next_usage["input_tokens"] = raw_usage.get("prompt_eval_count")
        if "eval_count" in raw_usage:
            next_usage["output_tokens"] = raw_usage.get("eval_count")
        if next_usage.get("input_tokens") is not None and next_usage.get("output_tokens") is not None:
            next_usage["total_tokens"] = int(next_usage["input_tokens"] or 0) + int(next_usage["output_tokens"] or 0)
        return next_usage

    @staticmethod
    def _format_sse(*, event: str, data: dict[str, Any]) -> str:
        """格式化 SSE 消息。"""
        payload = json.dumps(data, ensure_ascii=False, default=str)
        return f"event: {event}\ndata: {payload}\n\n"

    @staticmethod
    def _safe_model_dump(value: Any) -> Any:
        """统一处理 Pydantic 模型序列化。"""
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", by_alias=True)
        return value

    @staticmethod
    def _resolve_execution_mode(entrypoint_type: str) -> str:
        """根据入口类型映射执行模式。"""
        if entrypoint_type == "workflow":
            return "workflow"
        if entrypoint_type == "agent":
            return "agent"
        return "retrieval_chat"

    @staticmethod
    def _merge_dicts(*parts: dict[str, Any]) -> dict[str, Any]:
        """浅层合并多个配置字典。"""
        merged: dict[str, Any] = {}
        for part in parts:
            merged.update(part or {})
        return merged

    @staticmethod
    def _coerce_optional_uuid(value: Any) -> Optional[UUID]:
        """将配置中的字符串 UUID 安全转换为 UUID 对象。"""
        if value in (None, "", "null"):
            return None
        return UUID(str(value))

    @staticmethod
    def _build_session_read(
        session: ChatSession,
        stats: Optional[ChatSessionStats],
        capabilities: Optional[list[dict[str, Any]]] = None,
    ) -> ChatSessionRead:
        """组装会话读取模型。"""
        item = ChatSessionRead.model_validate(session)
        if stats:
            item.stats = ChatSessionStatsRead.model_validate(stats)
        item.capabilities = capabilities or []
        return item

    @staticmethod
    def _serialize_capability_binding(binding: ChatSessionCapabilityBinding) -> dict[str, Any]:
        """序列化能力挂载，便于前端直接消费。"""
        return {
            "id": str(binding.id),
            "session_id": str(binding.session_id),
            "capability_type": binding.capability_type,
            "capability_id": str(binding.capability_id),
            "binding_role": binding.binding_role,
            "is_enabled": binding.is_enabled,
            "priority": binding.priority,
            "config": binding.config,
            "created_at": binding.created_at.isoformat(),
            "updated_at": binding.updated_at.isoformat(),
        }
