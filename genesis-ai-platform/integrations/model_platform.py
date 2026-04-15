"""
模型平台的 LangChain / LlamaIndex 包装器。

设计目标：
- 上层框架只关心“租户模型 ID / 默认能力模型”
- 底层统一复用模型平台配置、日志、鉴权和适配器路由
- 后续替换 LiteLLM 或增加 Native Adapter 时，不影响框架接入层
"""
from __future__ import annotations

from collections.abc import Generator, Sequence
from typing import Any
from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage as LangChainChatMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.llms.types import (
    ChatMessage,
    ChatResponse,
    CompletionResponse,
    LLMMetadata,
    MessageRole,
)
from llama_index.core.llms import CustomLLM
from pydantic import ConfigDict, Field

from core.database import async_session_maker
from core.model_platform.runtime_client import ModelPlatformRuntimeClient


class PlatformLangChainChatModel(BaseChatModel):  # type: ignore[misc]
    """LangChain 聊天模型包装器。"""

    current_user: Any = Field(exclude=True)
    tenant_model_id: UUID | None = None
    capability_type: str = "chat"
    temperature: float | None = None
    max_tokens: int | None = None
    extra_body: dict[str, Any] = Field(default_factory=dict)
    session_factory: Any = Field(default=async_session_maker, exclude=True, repr=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _llm_type(self) -> str:
        return "genesis_model_platform"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """同步生成聊天结果。"""
        response = self._build_runtime_client().chat(
            tenant_model_id=kwargs.get("tenant_model_id", self.tenant_model_id),
            capability_type=self.capability_type,
            messages=self._convert_langchain_messages(messages),
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            extra_body=self._merge_extra_body(stop=stop, runtime_extra_body=kwargs.get("extra_body")),
            request_source="langchain",
        )
        return self._build_langchain_result(response)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """异步生成聊天结果。"""
        response = await self._build_runtime_client().achat(
            tenant_model_id=kwargs.get("tenant_model_id", self.tenant_model_id),
            capability_type=self.capability_type,
            messages=self._convert_langchain_messages(messages),
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            extra_body=self._merge_extra_body(stop=stop, runtime_extra_body=kwargs.get("extra_body")),
            request_source="langchain",
        )
        return self._build_langchain_result(response)

    def _build_runtime_client(self) -> ModelPlatformRuntimeClient:
        """构造运行时客户端。"""
        return ModelPlatformRuntimeClient(
            current_user=self.current_user,
            session_factory=self.session_factory,
        )

    def _convert_langchain_messages(self, messages: list[BaseMessage]) -> list[dict[str, Any]]:
        """将 LangChain 消息转换为平台统一消息。"""
        converted: list[dict[str, Any]] = []
        for message in messages:
            converted.append(
                {
                    "role": self._resolve_langchain_role(message),
                    "content": self._normalize_content(message.content),
                }
            )
        return converted

    def _resolve_langchain_role(self, message: BaseMessage) -> str:
        """解析 LangChain 消息角色。"""
        if isinstance(message, SystemMessage):
            return "system"
        if isinstance(message, HumanMessage):
            return "user"
        if isinstance(message, AIMessage):
            return "assistant"
        if isinstance(message, ToolMessage):
            return "tool"
        if isinstance(message, LangChainChatMessage):
            if message.role in {"system", "user", "assistant", "tool"}:
                return str(message.role)
        if getattr(message, "type", "") == "system":
            return "system"
        if getattr(message, "type", "") in {"human", "user"}:
            return "user"
        if getattr(message, "type", "") in {"ai", "assistant"}:
            return "assistant"
        return "user"

    def _normalize_content(self, content: Any) -> str:
        """归一化消息内容。"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            normalized_parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    normalized_parts.append(item)
                elif isinstance(item, dict):
                    text_value = item.get("text") or item.get("content") or item.get("value")
                    if text_value is not None:
                        normalized_parts.append(str(text_value))
            return "\n".join(part for part in normalized_parts if part)
        return str(content)

    def _merge_extra_body(
        self,
        *,
        stop: list[str] | None,
        runtime_extra_body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """合并 LangChain 调用时的扩展参数。"""
        merged = dict(self.extra_body)
        if isinstance(runtime_extra_body, dict):
            merged.update(runtime_extra_body)
        if stop:
            merged["stop"] = stop
        return merged

    def _build_langchain_result(self, response: dict[str, Any]) -> ChatResult:
        """将平台响应转换为 LangChain 结果。"""
        generations: list[ChatGeneration] = []
        usage = response.get("usage", {}) or {}
        usage_metadata = {key: value for key, value in usage.items() if value is not None}

        for item in response.get("choices", []):
            message_payload = item.get("message", {}) or {}
            ai_message = AIMessage(
                content=str(message_payload.get("content", "")),
                response_metadata={
                    "finish_reason": item.get("finish_reason"),
                    "adapter_type": response.get("adapter_type"),
                    "model": response.get("model"),
                },
                usage_metadata=usage_metadata or None,
            )
            generations.append(ChatGeneration(message=ai_message))

        return ChatResult(
            generations=generations,
            llm_output={
                "model": response.get("model"),
                "adapter_type": response.get("adapter_type"),
                "usage": usage,
                "raw_response": response.get("raw_response", {}),
            },
        )


class PlatformLangChainEmbeddings(Embeddings):  # type: ignore[misc]
    """LangChain Embeddings 包装器。"""

    def __init__(
        self,
        *,
        current_user: Any,
        tenant_model_id: UUID | None = None,
        capability_type: str = "embedding",
        extra_body: dict[str, Any] | None = None,
        session_factory: Any = async_session_maker,
    ) -> None:
        self.current_user = current_user
        self.tenant_model_id = tenant_model_id
        self.capability_type = capability_type
        self.extra_body = extra_body or {}
        self.session_factory = session_factory

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """同步批量向量化。"""
        response = self._build_runtime_client().embed(
            tenant_model_id=self.tenant_model_id,
            capability_type=self.capability_type,
            input_texts=texts,
            extra_body=self.extra_body,
            request_source="langchain",
        )
        return [list(map(float, item.get("embedding", []))) for item in response.get("data", [])]

    def embed_query(self, text: str) -> list[float]:
        """同步查询向量化。"""
        vectors = self.embed_documents([text])
        return vectors[0] if vectors else []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """异步批量向量化。"""
        response = await self._build_runtime_client().aembed(
            tenant_model_id=self.tenant_model_id,
            capability_type=self.capability_type,
            input_texts=texts,
            extra_body=self.extra_body,
            request_source="langchain",
        )
        return [list(map(float, item.get("embedding", []))) for item in response.get("data", [])]

    async def aembed_query(self, text: str) -> list[float]:
        """异步查询向量化。"""
        vectors = await self.aembed_documents([text])
        return vectors[0] if vectors else []

    def _build_runtime_client(self) -> ModelPlatformRuntimeClient:
        """构造运行时客户端。"""
        return ModelPlatformRuntimeClient(
            current_user=self.current_user,
            session_factory=self.session_factory,
        )


class PlatformLlamaIndexLLM(CustomLLM):  # type: ignore[misc]
    """LlamaIndex LLM 包装器。"""

    current_user: Any = Field(exclude=True)
    tenant_model_id: UUID | None = None
    capability_type: str = "chat"
    temperature: float | None = None
    max_tokens: int | None = None
    extra_body: dict[str, Any] = Field(default_factory=dict)
    context_window: int = 131072
    num_output: int = 4096
    session_factory: Any = Field(default=async_session_maker, exclude=True, repr=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def metadata(self) -> LLMMetadata:
        """暴露 LlamaIndex 所需模型元信息。"""
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.num_output,
            is_chat_model=True,
            is_function_calling_model=False,
            model_name="genesis_model_platform",
            system_role=MessageRole.SYSTEM,
        )

    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        """同步文本完成。"""
        response = self._build_runtime_client().chat(
            tenant_model_id=kwargs.get("tenant_model_id", self.tenant_model_id),
            capability_type=self.capability_type,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            extra_body=self._merge_extra_body(kwargs.get("extra_body")),
            request_source="llamaindex",
        )
        text = self._extract_response_text(response)
        return CompletionResponse(
            text=text,
            raw=response,
            additional_kwargs={
                "usage": response.get("usage", {}),
                "adapter_type": response.get("adapter_type"),
            },
        )

    def stream_complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> Generator[CompletionResponse, None, None]:
        """当前阶段先提供单次返回的伪流式结果。"""
        response = self.complete(prompt, formatted=formatted, **kwargs)
        yield CompletionResponse(
            text=response.text,
            delta=response.text,
            raw=response.raw,
            additional_kwargs=response.additional_kwargs,
        )

    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """同步对话调用。"""
        response = self._build_runtime_client().chat(
            tenant_model_id=kwargs.get("tenant_model_id", self.tenant_model_id),
            capability_type=self.capability_type,
            messages=self._convert_llamaindex_messages(messages),
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            extra_body=self._merge_extra_body(kwargs.get("extra_body")),
            request_source="llamaindex",
        )
        return self._build_llamaindex_chat_response(response)

    def stream_chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> Generator[ChatResponse, None, None]:
        """当前阶段先提供单次返回的伪流式结果。"""
        yield self.chat(messages, **kwargs)

    async def achat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """异步对话调用。"""
        response = await self._build_runtime_client().achat(
            tenant_model_id=kwargs.get("tenant_model_id", self.tenant_model_id),
            capability_type=self.capability_type,
            messages=self._convert_llamaindex_messages(messages),
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            extra_body=self._merge_extra_body(kwargs.get("extra_body")),
            request_source="llamaindex",
        )
        return self._build_llamaindex_chat_response(response)

    async def acomplete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        """异步文本完成。"""
        response = await self._build_runtime_client().achat(
            tenant_model_id=kwargs.get("tenant_model_id", self.tenant_model_id),
            capability_type=self.capability_type,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            extra_body=self._merge_extra_body(kwargs.get("extra_body")),
            request_source="llamaindex",
        )
        text = self._extract_response_text(response)
        return CompletionResponse(
            text=text,
            raw=response,
            additional_kwargs={
                "usage": response.get("usage", {}),
                "adapter_type": response.get("adapter_type"),
            },
        )

    def _build_runtime_client(self) -> ModelPlatformRuntimeClient:
        """构造运行时客户端。"""
        return ModelPlatformRuntimeClient(
            current_user=self.current_user,
            session_factory=self.session_factory,
        )

    def _convert_llamaindex_messages(self, messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
        """将 LlamaIndex 消息转换为平台统一消息。"""
        converted: list[dict[str, Any]] = []
        for message in messages:
            role_value = message.role.value if hasattr(message.role, "value") else str(message.role)
            normalized_role = role_value if role_value in {"system", "user", "assistant", "tool"} else "user"
            converted.append(
                {
                    "role": normalized_role,
                    "content": message.content or "",
                }
            )
        return converted

    def _build_llamaindex_chat_response(self, response: dict[str, Any]) -> ChatResponse:
        """构造 LlamaIndex 聊天响应。"""
        text = self._extract_response_text(response)
        return ChatResponse(
            message=ChatMessage(role=MessageRole.ASSISTANT, content=text),
            raw=response,
            additional_kwargs={
                "usage": response.get("usage", {}),
                "adapter_type": response.get("adapter_type"),
            },
        )

    def _extract_response_text(self, response: dict[str, Any]) -> str:
        """提取统一响应中的首条文本。"""
        choices = response.get("choices", []) or []
        if not choices:
            return ""
        message_payload = choices[0].get("message", {}) or {}
        return str(message_payload.get("content", ""))

    def _merge_extra_body(self, runtime_extra_body: dict[str, Any] | None) -> dict[str, Any]:
        """合并调用时扩展参数。"""
        merged = dict(self.extra_body)
        if isinstance(runtime_extra_body, dict):
            merged.update(runtime_extra_body)
        return merged


class PlatformLlamaIndexEmbedding(BaseEmbedding):  # type: ignore[misc]
    """LlamaIndex Embedding 包装器。"""

    current_user: Any = Field(exclude=True)
    tenant_model_id: UUID | None = None
    capability_type: str = "embedding"
    extra_body: dict[str, Any] = Field(default_factory=dict)
    session_factory: Any = Field(default=async_session_maker, exclude=True, repr=False)
    model_name: str = "genesis_model_platform_embedding"

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_query_embedding(self, query: str) -> list[float]:
        """同步查询向量。"""
        return self._embed_sync([query])[0] if query else []

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """异步查询向量。"""
        vectors = await self._embed_async([query]) if query else []
        return vectors[0] if vectors else []

    def _get_text_embedding(self, text: str) -> list[float]:
        """同步文本向量。"""
        vectors = self._embed_sync([text]) if text else []
        return vectors[0] if vectors else []

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """同步批量文本向量。"""
        return self._embed_sync(texts)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        """异步文本向量。"""
        vectors = await self._embed_async([text]) if text else []
        return vectors[0] if vectors else []

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """异步批量文本向量。"""
        return await self._embed_async(texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        """同步向量化。"""
        if not texts:
            return []
        response = self._build_runtime_client().embed(
            tenant_model_id=self.tenant_model_id,
            capability_type=self.capability_type,
            input_texts=texts,
            extra_body=self.extra_body,
            request_source="llamaindex",
        )
        return [list(map(float, item.get("embedding", []))) for item in response.get("data", [])]

    async def _embed_async(self, texts: list[str]) -> list[list[float]]:
        """异步向量化。"""
        if not texts:
            return []
        response = await self._build_runtime_client().aembed(
            tenant_model_id=self.tenant_model_id,
            capability_type=self.capability_type,
            input_texts=texts,
            extra_body=self.extra_body,
            request_source="llamaindex",
        )
        return [list(map(float, item.get("embedding", []))) for item in response.get("data", [])]

    def _build_runtime_client(self) -> ModelPlatformRuntimeClient:
        """构造运行时客户端。"""
        return ModelPlatformRuntimeClient(
            current_user=self.current_user,
            session_factory=self.session_factory,
        )
