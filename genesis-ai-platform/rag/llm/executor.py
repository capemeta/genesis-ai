"""
统一 LLM 执行器。

当前职责：
- 为 RAG 内部增强链路收口聊天调用入口
- 按知识库模型配置优先、租户默认模型兜底解析实际模型
- 统一复用模型中心的调用、审计与限流机制
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from core.database import async_session_maker
from core.model_platform.kb_model_resolver import resolve_kb_runtime_model, resolve_tenant_runtime_model
from models.knowledge_base import KnowledgeBase
from services.model_platform_service import ModelInvocationService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMRequest:
    """统一 LLM 请求。"""

    messages: list[dict[str, Any]]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    extra_body: dict[str, Any] = field(default_factory=dict)
    request_source: str = "runtime_internal"
    workload_type: str = "batch_llm_enhance"
    tenant_id: str | None = None
    kb_id: str | None = None
    kb_doc_id: str | None = None


@dataclass(slots=True)
class LLMResponse:
    """统一 LLM 响应。"""

    model: str
    content: str
    raw_response: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    tenant_model_id: str | None = None


class LLMExecutor:
    """统一 LLM 执行器。"""

    def __init__(self, *, session_maker: Any | None = None) -> None:
        """
        初始化执行器。

        Celery 任务会在每次 asyncio.run() 中创建独立 event loop，任务内必须注入
        当前 loop 专属的 session maker，避免复用全局连接池导致跨 loop 错误。
        """
        self.session_maker = session_maker or async_session_maker

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """
        执行非流式聊天请求。

        注意：
        - 并发控制已经统一下沉到模型中心调用服务
        - 这里主要负责知识库模型解析与请求组织
        """
        if request.stream:
            raise NotImplementedError("当前阶段统一执行器暂未开放流式输出，请使用后续 stream_chat 入口")
        if not request.tenant_id:
            raise RuntimeError("统一 LLM 执行器必须提供 tenant_id")

        tenant_uuid = UUID(str(request.tenant_id))
        async with self.session_maker() as session:
            tenant_model_id = await self._resolve_tenant_model_id(
                session=session,
                tenant_id=tenant_uuid,
                kb_id=request.kb_id,
                preferred_model_name=request.model,
            )
            current_user = SimpleNamespace(
                tenant_id=tenant_uuid,
                id=None,
                nickname="System",
                username="system",
            )
            service = ModelInvocationService(session)
            try:
                raw_response = await service.chat(
                    current_user=current_user,
                    tenant_model_id=tenant_model_id,
                    capability_type="chat",
                    messages=request.messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=False,
                    extra_body=request.extra_body,
                    request_source=request.request_source,
                )
            except HTTPException as exc:
                raise RuntimeError(str(exc.detail)) from exc

        content = self._extract_message_content(raw_response)
        usage = self._normalize_usage(raw_response)
        return LLMResponse(
            model=str(raw_response.get("model") or ""),
            content=content,
            raw_response=raw_response,
            usage=usage,
            tenant_model_id=str(raw_response.get("tenant_model_id") or tenant_model_id),
        )

    async def stream_chat(self, request: LLMRequest) -> Any:
        """
        预留流式聊天入口。

        后续实现要求：
        - 统一走模型中心流式接口
        - 由模型中心负责租约续租
        - 流结束 / 中断 / 异常时统一释放资源
        """
        _ = request
        raise NotImplementedError("当前阶段仅实现非流式 chat，后续流式接口将基于模型中心统一入口实现")

    async def _resolve_tenant_model_id(
        self,
        *,
        session,
        tenant_id: UUID,
        kb_id: str | None,
        preferred_model_name: str | None,
    ) -> UUID:
        """解析当前请求实际应使用的租户模型 ID。"""
        if kb_id:
            kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == UUID(str(kb_id)))
            kb_result = await session.execute(kb_stmt)
            kb = kb_result.scalar_one_or_none()
            if kb is None:
                raise RuntimeError("知识库不存在，无法解析增强模型配置")
            resolved = await resolve_kb_runtime_model(session, kb=kb, capability_type="chat")
            return resolved.tenant_model_id

        resolved = await resolve_tenant_runtime_model(
            session,
            tenant_id=tenant_id,
            capability_type="chat",
            preferred_model_name=str(preferred_model_name or "").strip() or None,
        )
        return resolved.tenant_model_id

    def _extract_message_content(self, raw_response: dict[str, Any]) -> str:
        """从模型中心归一化响应中提取首条文本内容。"""
        choices = list(raw_response.get("choices") or [])
        if not choices:
            raise RuntimeError("LLM 返回结果为空，未包含 choices")
        message = dict((choices[0] or {}).get("message") or {})
        content = str(message.get("content") or "").strip()
        if not content:
            raise RuntimeError("LLM 返回结果为空，未包含 message.content")
        return content

    def _normalize_usage(self, raw_response: dict[str, Any]) -> dict[str, Any]:
        """归一化 token 用量字段。"""
        usage = dict(raw_response.get("usage") or {})
        return {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
