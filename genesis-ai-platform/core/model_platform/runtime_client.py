"""
模型平台运行时客户端。

这一层用于在应用内复用模型平台，而不是只能通过 HTTP API 调用。
典型场景包括：
- LangChain / LlamaIndex 包装器
- RAG 内部组件
- 任务调度与工作流
"""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session_maker
from models.user import User
from services.model_platform_service import ModelInvocationService

T = TypeVar("T")


def run_async_blocking(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """
    在同步上下文中运行异步协程。

    这里额外处理“当前线程已经存在 event loop”的场景，
    避免 LangChain / LlamaIndex 的同步接口在异步环境中直接报错。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    result_box: dict[str, T] = {}
    error_box: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result_box["value"] = asyncio.run(coro_factory())
        except BaseException as exc:  # noqa: BLE001
            error_box["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_box:
        raise error_box["error"]
    return result_box["value"]


class ModelPlatformRuntimeClient:
    """应用内模型平台运行时客户端。"""

    def __init__(
        self,
        *,
        current_user: User,
        session_factory: Any = async_session_maker,
    ) -> None:
        self.current_user = current_user
        self.session_factory = session_factory

    async def achat(
        self,
        *,
        tenant_model_id: UUID | None,
        capability_type: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_body: dict[str, Any] | None = None,
        request_source: str = "runtime",
    ) -> dict[str, Any]:
        """异步聊天调用。"""
        async with self.session_factory() as session:
            session = session if isinstance(session, AsyncSession) else session
            service = ModelInvocationService(session)
            return cast(dict[str, Any], await service.chat(
                current_user=self.current_user,
                tenant_model_id=tenant_model_id,
                capability_type=capability_type,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                extra_body=extra_body,
                request_source=request_source,
            ))

    def chat(
        self,
        *,
        tenant_model_id: UUID | None,
        capability_type: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_body: dict[str, Any] | None = None,
        request_source: str = "runtime",
    ) -> dict[str, Any]:
        """同步聊天调用。"""
        return run_async_blocking(
            lambda: self.achat(
                tenant_model_id=tenant_model_id,
                capability_type=capability_type,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
                request_source=request_source,
            )
        )

    async def aembed(
        self,
        *,
        tenant_model_id: UUID | None,
        capability_type: str,
        input_texts: list[str],
        extra_body: dict[str, Any] | None = None,
        request_source: str = "runtime",
    ) -> dict[str, Any]:
        """异步向量化调用。"""
        async with self.session_factory() as session:
            session = session if isinstance(session, AsyncSession) else session
            service = ModelInvocationService(session)
            return cast(dict[str, Any], await service.embed(
                current_user=self.current_user,
                tenant_model_id=tenant_model_id,
                capability_type=capability_type,
                input_texts=input_texts,
                extra_body=extra_body,
                request_source=request_source,
            ))

    def embed(
        self,
        *,
        tenant_model_id: UUID | None,
        capability_type: str,
        input_texts: list[str],
        extra_body: dict[str, Any] | None = None,
        request_source: str = "runtime",
    ) -> dict[str, Any]:
        """同步向量化调用。"""
        return run_async_blocking(
            lambda: self.aembed(
                tenant_model_id=tenant_model_id,
                capability_type=capability_type,
                input_texts=input_texts,
                extra_body=extra_body,
                request_source=request_source,
            )
        )
