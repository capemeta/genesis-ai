"""
模型平台响应归一化工具。
"""

from typing import Any
from uuid import UUID


class ResponseNormalizerMixin:
    """统一封装各能力响应归一化逻辑。"""

    def _normalize_openai_chat_response(
        self,
        *,
        tenant_model_id: UUID,
        model_name: str,
        adapter_type: str,
        raw_response: dict[str, Any],
    ) -> dict[str, Any]:
        """归一化 OpenAI 兼容聊天响应。"""
        choices: list[dict[str, Any]] = []
        for index, item in enumerate(raw_response.get("choices", [])):
            message = item.get("message", {})
            choices.append(
                {
                    "index": int(item.get("index", index)),
                    "message": {
                        "role": str(message.get("role", "assistant")),
                        "content": str(message.get("content", "")),
                    },
                    "finish_reason": item.get("finish_reason"),
                }
            )

        usage_payload = raw_response.get("usage", {}) or {}
        usage = {
            "input_tokens": usage_payload.get("prompt_tokens"),
            "output_tokens": usage_payload.get("completion_tokens"),
            "total_tokens": usage_payload.get("total_tokens"),
        }

        return {
            "model": str(raw_response.get("model", model_name)),
            "tenant_model_id": tenant_model_id,
            "capability_type": "chat",
            "adapter_type": adapter_type,
            "choices": choices,
            "usage": usage,
            "raw_response": raw_response,
        }

    def _normalize_ollama_chat_response(
        self,
        *,
        tenant_model_id: UUID,
        model_name: str,
        adapter_type: str,
        raw_response: dict[str, Any],
    ) -> dict[str, Any]:
        """归一化 Ollama 聊天响应。"""
        message = raw_response.get("message", {}) or {}
        usage = {
            "input_tokens": raw_response.get("prompt_eval_count"),
            "output_tokens": raw_response.get("eval_count"),
            "total_tokens": (raw_response.get("prompt_eval_count") or 0) + (raw_response.get("eval_count") or 0),
        }
        return {
            "model": str(raw_response.get("model", model_name)),
            "tenant_model_id": tenant_model_id,
            "capability_type": "chat",
            "adapter_type": adapter_type,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": str(message.get("role", "assistant")),
                        "content": str(message.get("content", "")),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": usage,
            "raw_response": raw_response,
        }

    def _normalize_embedding_response(
        self,
        *,
        tenant_model_id: UUID,
        model_name: str,
        adapter_type: str,
        raw_response: dict[str, Any],
    ) -> dict[str, Any]:
        """归一化 embedding 响应。"""
        data_items: list[dict[str, Any]] = []
        for index, item in enumerate(raw_response.get("data", [])):
            data_items.append(
                {
                    "index": int(item.get("index", index)),
                    "embedding": item.get("embedding", []),
                }
            )

        usage_payload = raw_response.get("usage", {}) or {}
        usage = {
            "input_tokens": usage_payload.get("prompt_tokens"),
            "output_tokens": None,
            "total_tokens": usage_payload.get("total_tokens"),
        }
        return {
            "model": str(raw_response.get("model", model_name)),
            "tenant_model_id": tenant_model_id,
            "capability_type": "embedding",
            "adapter_type": adapter_type,
            "data": data_items,
            "usage": usage,
            "raw_response": raw_response,
        }

    def _normalize_rerank_response(
        self,
        *,
        tenant_model_id: UUID,
        adapter_type: str,
        raw_result: dict[str, Any],
    ) -> dict[str, Any]:
        """归一化 rerank 响应。"""
        usage_payload = raw_result.get("usage", {}) or {}
        usage = {
            "input_tokens": usage_payload.get("prompt_tokens") or usage_payload.get("input_tokens") or usage_payload.get("total_tokens"),
            "output_tokens": usage_payload.get("output_tokens"),
            "total_tokens": usage_payload.get("total_tokens") or usage_payload.get("input_tokens"),
        }
        return {
            "model": str(raw_result.get("model", "")),
            "tenant_model_id": tenant_model_id,
            "capability_type": "rerank",
            "adapter_type": adapter_type,
            "results": raw_result.get("results", []),
            "usage": usage,
            "raw_response": raw_result.get("raw_response", {}),
        }

    def _normalize_transcription_response(
        self,
        *,
        tenant_model_id: UUID,
        model_name: str,
        adapter_type: str,
        raw_result: dict[str, Any],
    ) -> dict[str, Any]:
        """归一化 ASR 响应。"""
        usage_payload = raw_result.get("usage", {}) or {}
        usage = {
            "input_tokens": usage_payload.get("prompt_tokens") or usage_payload.get("input_tokens"),
            "output_tokens": usage_payload.get("completion_tokens") or usage_payload.get("output_tokens"),
            "total_tokens": usage_payload.get("total_tokens"),
        }
        return {
            "model": model_name,
            "tenant_model_id": tenant_model_id,
            "capability_type": "asr",
            "adapter_type": adapter_type,
            "text": str(raw_result.get("text", "")),
            "language": raw_result.get("language"),
            "duration_seconds": raw_result.get("duration"),
            "segments": raw_result.get("segments", []),
            "usage": usage,
            "raw_response": raw_result.get("raw_response", {}),
        }

    def _normalize_speech_response(
        self,
        *,
        tenant_model_id: UUID,
        model_name: str,
        adapter_type: str,
        raw_result: dict[str, Any],
    ) -> dict[str, Any]:
        """归一化 TTS 响应。"""
        return {
            "model": model_name,
            "tenant_model_id": tenant_model_id,
            "capability_type": "tts",
            "adapter_type": adapter_type,
            "audio_base64": str(raw_result.get("audio_base64", "")),
            "content_type": str(raw_result.get("content_type", "application/octet-stream")),
            "content_length": raw_result.get("content_length"),
            "usage": {},
            "raw_response": raw_result.get("raw_response", {}),
        }
