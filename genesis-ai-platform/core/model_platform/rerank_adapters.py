"""
Rerank 适配器。

职责：
- 将统一 rerank 请求转换为上游协议
- 处理不同 endpoint / 请求结构 / 返回结构
- 归一为平台统一响应
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class RerankEndpointProfile:
    """统一 rerank 端点画像。"""

    base_url: str
    endpoint_path: str
    request_schema: str
    response_schema: str
    supports_multimodal_input: bool = False
    timeout_seconds: float = 30.0
    extra_headers: dict[str, str] | None = None


class NativeRerankAdapter:
    """原生 rerank 适配器。"""

    async def rerank(
        self,
        *,
        profile: RerankEndpointProfile,
        api_key: str | None,
        model_name: str,
        query: str | dict[str, Any],
        documents: list[str | dict[str, Any]],
        top_n: int | None = None,
        return_documents: bool | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行原生 rerank 调用。"""
        extra_options = extra_options or {}
        request_json = self._build_request(
            request_schema=profile.request_schema,
            model_name=model_name,
            query=query,
            documents=documents,
            top_n=top_n,
            return_documents=return_documents,
            extra_options=extra_options,
        )
        headers = self._build_headers(
            api_key=api_key,
            extra_headers=profile.extra_headers,
        )
        url = f"{profile.base_url.rstrip('/')}/{profile.endpoint_path.lstrip('/')}"
        timeout = httpx.Timeout(profile.timeout_seconds, connect=min(10.0, profile.timeout_seconds))

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=request_json)
            response.raise_for_status()
            payload = response.json()

        return self._normalize_response(
            response_schema=profile.response_schema,
            model_name=model_name,
            raw_response=payload,
        )

    def _build_headers(
        self,
        *,
        api_key: str | None,
        extra_headers: dict[str, str] | None,
    ) -> dict[str, str]:
        """构造请求头。"""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _build_request(
        self,
        *,
        request_schema: str,
        model_name: str,
        query: str | dict[str, Any],
        documents: list[str | dict[str, Any]],
        top_n: int | None,
        return_documents: bool | None,
        extra_options: dict[str, Any],
    ) -> dict[str, Any]:
        """根据协议模板构造请求体。"""
        if request_schema == "openai_rerank":
            payload: dict[str, Any] = {
                "model": model_name,
                "query": query if isinstance(query, str) else query.get("text", ""),
                "documents": documents,
            }
            if top_n is not None:
                payload["top_n"] = top_n
            payload.update(extra_options)
            return payload

        if request_schema == "dashscope_text_rerank_v1":
            parameters = dict(extra_options.get("parameters") or {})
            if top_n is not None:
                parameters.setdefault("top_n", top_n)
            if return_documents is not None:
                parameters.setdefault("return_documents", return_documents)
            payload = {
                "model": model_name,
                "input": {
                    "query": query if isinstance(query, str) else query.get("text", ""),
                    "documents": [self._normalize_text_document(item) for item in documents],
                },
            }
            if parameters:
                payload["parameters"] = parameters
            for key, value in extra_options.items():
                if key != "parameters":
                    payload[key] = value
            return payload

        if request_schema == "dashscope_multimodal_rerank_v1":
            parameters = dict(extra_options.get("parameters") or {})
            if top_n is not None:
                parameters.setdefault("top_n", top_n)
            if return_documents is not None:
                parameters.setdefault("return_documents", return_documents)
            payload = {
                "model": model_name,
                "input": {
                    "query": query,
                    "documents": [self._normalize_multimodal_document(item) for item in documents],
                },
            }
            if parameters:
                payload["parameters"] = parameters
            for key, value in extra_options.items():
                if key != "parameters":
                    payload[key] = value
            return payload

        raise ValueError(f"暂不支持的 rerank 请求协议: {request_schema}")

    def _normalize_response(
        self,
        *,
        response_schema: str,
        model_name: str,
        raw_response: dict[str, Any],
    ) -> dict[str, Any]:
        """将上游响应归一为平台统一格式。"""
        if response_schema == "openai_rerank":
            results = []
            for index, item in enumerate(raw_response.get("results", [])):
                results.append(
                    {
                        "index": int(item.get("index", index)),
                        "score": float(item.get("relevance_score", item.get("score", 0.0))),
                        "document": item.get("document"),
                    }
                )
            return {
                "model": str(raw_response.get("model", model_name)),
                "results": results,
                "usage": raw_response.get("usage", {}) or {},
                "raw_response": raw_response,
            }

        if response_schema in {"dashscope_text_rerank_v1", "dashscope_multimodal_rerank_v1"}:
            output = raw_response.get("output", {}) or {}
            results = []
            for index, item in enumerate(output.get("results", [])):
                results.append(
                    {
                        "index": int(item.get("index", index)),
                        "score": float(item.get("relevance_score", item.get("score", 0.0))),
                        "document": item.get("document"),
                    }
                )
            usage = raw_response.get("usage", {}) or {}
            return {
                "model": str(raw_response.get("model", model_name)),
                "results": results,
                "usage": usage,
                "raw_response": raw_response,
            }

        raise ValueError(f"暂不支持的 rerank 响应协议: {response_schema}")

    def _normalize_text_document(self, item: str | dict[str, Any]) -> str:
        """将文档归一为纯文本。"""
        if isinstance(item, str):
            return item
        if "text" in item:
            return str(item["text"])
        raise ValueError("当前文本 rerank 仅支持字符串或带 text 字段的文档")

    def _normalize_multimodal_document(self, item: str | dict[str, Any]) -> dict[str, Any]:
        """将文档归一为多模态结构。"""
        if isinstance(item, str):
            return {"text": item}
        if any(key in item for key in ("text", "image", "video")):
            return item
        raise ValueError("多模态 rerank 文档必须包含 text/image/video 字段")
