"""
LiteLLM 适配器。

当前职责：
- 统一包装 LiteLLM 的聊天与向量化调用
- 对不同协议生成较稳定的调用参数
- 为后续 Native Adapter 覆盖保留清晰边界
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, cast


@dataclass(slots=True)
class LiteLLMResolvedRequest:
    """LiteLLM 最终请求参数。"""

    payload: dict[str, Any]
    normalized_model_name: str


class LiteLLMRequestResolver:
    """LiteLLM 请求参数解析器。"""

    def resolve(
        self,
        *,
        capability_type: str,
        protocol_type: str,
        base_url: str,
        model_name: str,
        api_key: str | None,
        api_version: str | None = None,
        region: str | None = None,
        provider_config: dict[str, Any] | None = None,
        credential_config: dict[str, Any] | None = None,
        request_kwargs: dict[str, Any] | None = None,
    ) -> LiteLLMResolvedRequest:
        """根据协议类型构造 LiteLLM 请求参数。"""
        provider_config = provider_config or {}
        credential_config = credential_config or {}
        request_kwargs = request_kwargs or {}

        payload: dict[str, Any] = dict(request_kwargs)
        normalized_model_name = self._resolve_model_name(
            protocol_type=protocol_type,
            model_name=model_name,
            provider_config=provider_config,
            credential_config=credential_config,
        )

        payload["model"] = normalized_model_name
        self._apply_base_connection(
            payload=payload,
            protocol_type=protocol_type,
            capability_type=capability_type,
            base_url=base_url,
            api_key=api_key,
            api_version=api_version,
            region=region,
            provider_config=provider_config,
            credential_config=credential_config,
        )
        self._apply_provider_specific_options(
            payload=payload,
            protocol_type=protocol_type,
            provider_config=provider_config,
            credential_config=credential_config,
        )
        return LiteLLMResolvedRequest(payload=payload, normalized_model_name=normalized_model_name)

    def _resolve_model_name(
        self,
        *,
        protocol_type: str,
        model_name: str,
        provider_config: dict[str, Any],
        credential_config: dict[str, Any],
    ) -> str:
        """解析 LiteLLM 需要的模型名。"""
        if protocol_type == "ollama":
            return f"ollama/{model_name}"
        if protocol_type == "azure_openai":
            deployment_name = self._pick_first_non_empty(
                provider_config.get("azure_deployment"),
                credential_config.get("azure_deployment"),
                model_name,
            )
            return f"azure/{deployment_name}"
        if protocol_type == "anthropic_native":
            return f"anthropic/{model_name}"
        if protocol_type == "gemini_native":
            return f"gemini/{model_name}"
        if protocol_type == "bedrock":
            return f"bedrock/{model_name}"
        custom_provider = self._pick_first_non_empty(
            provider_config.get("litellm_provider"),
            credential_config.get("litellm_provider"),
        )
        if custom_provider:
            return f"{custom_provider}/{model_name}"
        return model_name

    def _apply_base_connection(
        self,
        *,
        payload: dict[str, Any],
        protocol_type: str,
        capability_type: str,
        base_url: str,
        api_key: str | None,
        api_version: str | None,
        region: str | None,
        provider_config: dict[str, Any],
        credential_config: dict[str, Any],
    ) -> None:
        """写入通用连接参数。"""
        normalized_base_url = base_url.rstrip("/")
        if protocol_type not in {"anthropic_native", "gemini_native", "bedrock"}:
            payload.setdefault("api_base", normalized_base_url)

        # 大多数 provider 都兼容 api_key 的概念，统一优先透传。
        if api_key:
            payload.setdefault("api_key", api_key)

        resolved_api_version = self._pick_first_non_empty(
            provider_config.get("api_version"),
            credential_config.get("api_version"),
            api_version,
        )
        if protocol_type == "azure_openai" and resolved_api_version:
            payload.setdefault("api_version", resolved_api_version)

        resolved_region = self._pick_first_non_empty(
            provider_config.get("aws_region_name"),
            credential_config.get("aws_region_name"),
            provider_config.get("region"),
            credential_config.get("region"),
            region,
        )
        if protocol_type == "bedrock" and resolved_region:
            payload.setdefault("aws_region_name", resolved_region)

        if capability_type == "embedding":
            payload.pop("messages", None)
        elif capability_type == "chat":
            payload.pop("input", None)

    def _apply_provider_specific_options(
        self,
        *,
        payload: dict[str, Any],
        protocol_type: str,
        provider_config: dict[str, Any],
        credential_config: dict[str, Any],
    ) -> None:
        """写入 provider 特有参数。"""
        # OpenAI 兼容协议如果模型名本身没有 provider 前缀，LiteLLM 往往无法自动识别 provider。
        # 这里统一兜底指定 custom_llm_provider，避免 qwen/deepseek 等非 OpenAI 官方模型名触发
        # “LLM Provider NOT provided” 错误。
        if protocol_type in {"openai", "openai_compatible", "vllm"} and "custom_llm_provider" not in payload:
            payload["custom_llm_provider"] = "openai"

        if protocol_type == "bedrock":
            access_key_id = self._pick_first_non_empty(
                credential_config.get("aws_access_key_id"),
                credential_config.get("access_key_id"),
            )
            secret_access_key = self._pick_first_non_empty(
                credential_config.get("aws_secret_access_key"),
                credential_config.get("secret_access_key"),
            )
            session_token = self._pick_first_non_empty(
                credential_config.get("aws_session_token"),
                credential_config.get("session_token"),
            )
            if access_key_id:
                payload.setdefault("aws_access_key_id", access_key_id)
            if secret_access_key:
                payload.setdefault("aws_secret_access_key", secret_access_key)
            if session_token:
                payload.setdefault("aws_session_token", session_token)

        # 某些代理网关会要求自定义 Header，统一走 extra_headers 透传。
        extra_headers = provider_config.get("extra_headers") or credential_config.get("extra_headers")
        if isinstance(extra_headers, dict) and extra_headers:
            merged_headers = dict(payload.get("extra_headers") or {})
            merged_headers.update(extra_headers)
            payload["extra_headers"] = merged_headers

        # 允许用统一配置透传 LiteLLM 的供应商参数，便于后续细粒度覆盖。
        for key in (
            "custom_llm_provider",
            "organization",
            "project",
            "timeout",
            "num_retries",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "reasoning_effort",
        ):
            value = self._pick_first_non_empty(provider_config.get(key), credential_config.get(key))
            if value is not None and key not in payload:
                payload[key] = value

    def _pick_first_non_empty(self, *values: Any) -> Any:
        """选择第一个非空配置值。"""
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return None


class LiteLLMChatAdapter:
    """LiteLLM 聊天适配器。"""

    def __init__(self) -> None:
        self.request_resolver = LiteLLMRequestResolver()

    async def chat(
        self,
        *,
        protocol_type: str,
        base_url: str,
        api_key: str | None,
        model_name: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        api_version: str | None = None,
        region: str | None = None,
        provider_config: dict[str, Any] | None = None,
        credential_config: dict[str, Any] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行聊天调用。"""
        import litellm

        request_kwargs: dict[str, Any] = {"messages": messages}
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens
        if extra_body:
            request_kwargs.update(extra_body)

        resolved_request = self.request_resolver.resolve(
            capability_type="chat",
            protocol_type=protocol_type,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            api_version=api_version,
            region=region,
            provider_config=provider_config,
            credential_config=credential_config,
            request_kwargs=request_kwargs,
        )

        response = await litellm.acompletion(**resolved_request.payload)
        if hasattr(response, "model_dump"):
            return cast(dict[str, Any], response.model_dump())
        return cast(dict[str, Any], dict(response))

    async def stream_chat(
        self,
        *,
        protocol_type: str,
        base_url: str,
        api_key: str | None,
        model_name: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        api_version: str | None = None,
        region: str | None = None,
        provider_config: dict[str, Any] | None = None,
        credential_config: dict[str, Any] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """执行流式聊天调用。"""
        import litellm

        request_kwargs: dict[str, Any] = {"messages": messages, "stream": True}
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens
        if extra_body:
            request_kwargs.update(extra_body)
        request_kwargs["stream"] = True

        resolved_request = self.request_resolver.resolve(
            capability_type="chat",
            protocol_type=protocol_type,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            api_version=api_version,
            region=region,
            provider_config=provider_config,
            credential_config=credential_config,
            request_kwargs=request_kwargs,
        )

        response = await litellm.acompletion(**resolved_request.payload)
        async for chunk in response:
            if hasattr(chunk, "model_dump"):
                yield cast(dict[str, Any], chunk.model_dump())
            else:
                yield cast(dict[str, Any], dict(chunk))


class LiteLLMEmbeddingAdapter:
    """LiteLLM 向量化适配器。"""

    def __init__(self) -> None:
        self.request_resolver = LiteLLMRequestResolver()

    async def embed(
        self,
        *,
        protocol_type: str,
        base_url: str,
        api_key: str | None,
        model_name: str,
        input_texts: list[str],
        api_version: str | None = None,
        region: str | None = None,
        provider_config: dict[str, Any] | None = None,
        credential_config: dict[str, Any] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行 embedding 调用。"""
        import litellm

        request_kwargs: dict[str, Any] = {"input": input_texts}
        if extra_body:
            request_kwargs.update(extra_body)

        resolved_request = self.request_resolver.resolve(
            capability_type="embedding",
            protocol_type=protocol_type,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            api_version=api_version,
            region=region,
            provider_config=provider_config,
            credential_config=credential_config,
            request_kwargs=request_kwargs,
        )

        self._sanitize_embedding_payload(resolved_request.payload)

        response = await litellm.aembedding(**resolved_request.payload)
        if hasattr(response, "model_dump"):
            return cast(dict[str, Any], response.model_dump())
        return cast(dict[str, Any], dict(response))

    def _sanitize_embedding_payload(self, payload: dict[str, Any]) -> None:
        """清洗 embedding 请求，避免兼容网关因非标准参数拒绝请求。"""
        encoding_format = payload.get("encoding_format")
        if isinstance(encoding_format, str):
            normalized_encoding_format = encoding_format.strip().lower()
            if normalized_encoding_format in {"float", "base64"}:
                payload["encoding_format"] = normalized_encoding_format
                return
        if "encoding_format" in payload:
            payload.pop("encoding_format", None)
