"""
模型平台音频适配器。

当前先实现最小可用直连版本：
- OpenAI 兼容 ASR `/audio/transcriptions`
- OpenAI 兼容 TTS `/audio/speech`
"""
from __future__ import annotations

import base64
from typing import Any

import httpx


class OpenAICompatibleAudioAdapter:
    """OpenAI 兼容协议音频适配器。"""

    async def transcribe(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model_name: str,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
        endpoint_path: str = "/audio/transcriptions",
        language: str | None = None,
        prompt: str | None = None,
        response_format: str | None = None,
        temperature: float | None = None,
        extra_headers: dict[str, str] | None = None,
        extra_body: dict[str, Any] | None = None,
        timeout_seconds: float = 120.0,
    ) -> dict[str, Any]:
        """调用 OpenAI 兼容 ASR 接口。"""
        headers = self._build_auth_headers(api_key=api_key, extra_headers=extra_headers)
        payload: dict[str, Any] = {"model": model_name}
        if language:
            payload["language"] = language
        if prompt:
            payload["prompt"] = prompt
        if response_format:
            payload["response_format"] = response_format
        if temperature is not None:
            payload["temperature"] = temperature
        if extra_body:
            payload.update(extra_body)

        files = {
            "file": (filename, audio_bytes, mime_type),
        }
        timeout = httpx.Timeout(timeout_seconds, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self._join_url(base_url=base_url, endpoint_path=endpoint_path),
                data={key: self._stringify_form_value(value) for key, value in payload.items()},
                files=files,
                headers=headers,
            )
            response.raise_for_status()
            return self._normalize_transcription_response(response)

    async def synthesize(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model_name: str,
        text: str,
        voice: str,
        endpoint_path: str = "/audio/speech",
        response_format: str | None = None,
        speed: float | None = None,
        extra_headers: dict[str, str] | None = None,
        extra_body: dict[str, Any] | None = None,
        timeout_seconds: float = 120.0,
    ) -> dict[str, Any]:
        """调用 OpenAI 兼容 TTS 接口。"""
        headers = self._build_auth_headers(api_key=api_key, extra_headers=extra_headers)
        payload: dict[str, Any] = {
            "model": model_name,
            "input": text,
            "voice": voice,
        }
        if response_format:
            payload["response_format"] = response_format
        if speed is not None:
            payload["speed"] = speed
        if extra_body:
            payload.update(extra_body)

        timeout = httpx.Timeout(timeout_seconds, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self._join_url(base_url=base_url, endpoint_path=endpoint_path),
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            audio_base64 = base64.b64encode(response.content).decode("utf-8")
            return {
                "audio_base64": audio_base64,
                "content_type": response.headers.get("content-type", "application/octet-stream"),
                "content_length": len(response.content),
                "raw_response": {
                    "headers": dict(response.headers),
                    "status_code": response.status_code,
                },
            }

    def _build_auth_headers(
        self,
        *,
        api_key: str | None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """构造请求头。"""
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _join_url(self, *, base_url: str, endpoint_path: str) -> str:
        """拼接请求地址。"""
        normalized_base_url = base_url.rstrip("/")
        normalized_path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        return f"{normalized_base_url}{normalized_path}"

    def _stringify_form_value(self, value: Any) -> str:
        """将 multipart 表单值统一转成字符串。"""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _normalize_transcription_response(self, response: httpx.Response) -> dict[str, Any]:
        """归一化 ASR 原始响应。"""
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return {
                "text": response.text,
                "language": None,
                "duration": None,
                "segments": [],
                "raw_response": {
                    "text": response.text,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                },
            }

        payload = response.json()
        return {
            "text": payload.get("text", ""),
            "language": payload.get("language"),
            "duration": payload.get("duration"),
            "segments": payload.get("segments", []) or [],
            "usage": payload.get("usage", {}) or {},
            "raw_response": payload,
        }
