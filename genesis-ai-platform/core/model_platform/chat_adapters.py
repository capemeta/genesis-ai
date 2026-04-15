"""
模型平台聊天适配器。

当前先实现最小可用直连版本：
- OpenAI 兼容协议
- Ollama

后续可以在同一接口下继续补 LiteLLM Adapter。
"""
import json
from typing import Any, AsyncIterator

import httpx


class OpenAICompatibleChatAdapter:
    """OpenAI 兼容协议聊天适配器。"""

    async def chat(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model_name: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        endpoint_path: str = "/chat/completions",
        extra_headers: dict[str, str] | None = None,
        timeout_seconds: float = 120.0,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """调用 OpenAI 兼容 `/chat/completions` 接口。"""
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": False,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra_body:
            payload.update(extra_body)

        timeout = httpx.Timeout(timeout_seconds, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def stream_chat(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model_name: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        endpoint_path: str = "/chat/completions",
        extra_headers: dict[str, str] | None = None,
        timeout_seconds: float = 120.0,
        extra_body: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式调用 OpenAI 兼容 `/chat/completions` 接口。"""
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra_body:
            payload.update(extra_body)
        payload["stream"] = True

        timeout = httpx.Timeout(timeout_seconds, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    yield json.loads(data)


class OpenAICompatibleEmbeddingAdapter:
    """OpenAI 兼容协议 embedding 适配器。"""

    async def embed(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model_name: str,
        input_texts: list[str],
        endpoint_path: str = "/embeddings",
        extra_headers: dict[str, str] | None = None,
        timeout_seconds: float = 120.0,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """调用 OpenAI 兼容 `/embeddings` 接口。"""
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)

        payload: dict[str, Any] = {
            "model": model_name,
            "input": input_texts,
        }
        if extra_body:
            payload.update(extra_body)

        self._sanitize_embedding_payload(payload)

        timeout = httpx.Timeout(timeout_seconds, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def _sanitize_embedding_payload(self, payload: dict[str, Any]) -> None:
        """清洗 embedding 请求，避免兼容网关因非标准参数拒绝请求。"""
        encoding_format = payload.get("encoding_format")
        if isinstance(encoding_format, str):
            normalized_encoding_format = encoding_format.strip().lower()
            if normalized_encoding_format in {"float", "base64"}:
                payload["encoding_format"] = normalized_encoding_format
                return
        payload.pop("encoding_format", None)


class OllamaChatAdapter:
    """Ollama 聊天适配器。"""

    async def chat(
        self,
        *,
        base_url: str,
        model_name: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        endpoint_path: str = "/api/chat",
        timeout_seconds: float = 120.0,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """调用 Ollama `/api/chat` 接口。"""
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": False,
        }
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if options:
            payload["options"] = options
        if extra_body:
            payload.update(extra_body)

        timeout = httpx.Timeout(timeout_seconds, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def stream_chat(
        self,
        *,
        base_url: str,
        model_name: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        endpoint_path: str = "/api/chat",
        timeout_seconds: float = 120.0,
        extra_body: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式调用 Ollama `/api/chat` 接口。"""
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": True,
        }
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if options:
            payload["options"] = options
        if extra_body:
            payload.update(extra_body)
        payload["stream"] = True

        timeout = httpx.Timeout(timeout_seconds, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if line:
                        yield json.loads(line)
