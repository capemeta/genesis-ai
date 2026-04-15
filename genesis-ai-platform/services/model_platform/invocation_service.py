"""
模型平台统一调用服务。
"""

import base64
import logging
import mimetypes
import time
from typing import Any, AsyncIterator
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.model_platform.audio_adapters import OpenAICompatibleAudioAdapter
from core.model_platform.chat_adapters import OllamaChatAdapter, OpenAICompatibleChatAdapter, OpenAICompatibleEmbeddingAdapter
from core.model_platform.litellm_adapters import LiteLLMChatAdapter, LiteLLMEmbeddingAdapter
from core.model_platform.rerank_adapters import NativeRerankAdapter
from rag.utils.limiters import (
    ConcurrencyContext,
    ConcurrencyPolicy,
    ConcurrencyScopeLimit,
    acquire_concurrency_lease,
    release_concurrency_lease,
    resolve_concurrency_policy,
)
from models.model_invocation_log import ModelInvocationLog
from models.model_provider_definition import ModelProviderDefinition
from models.platform_model import PlatformModel
from models.tenant_default_model import TenantDefaultModel
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider
from models.user import User
from services.model_platform.provider_integration_service import ModelProviderIntegrationService
from services.model_platform.response_normalizers import ResponseNormalizerMixin
from services.model_platform.runtime_profile_service import CapabilityRuntimeProfile, RuntimeProfileServiceMixin
from services.model_platform.settings_service import TENANT_RESOURCE_SCOPE

logger = logging.getLogger(__name__)


class ModelInvocationService(RuntimeProfileServiceMixin, ResponseNormalizerMixin):
    """
    统一模型调用服务。

    当前阶段先实现：
    - 聊天能力
    - OpenAI 兼容 / vLLM 直连
    - Ollama 直连
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.openai_adapter = OpenAICompatibleChatAdapter()
        self.openai_embedding_adapter = OpenAICompatibleEmbeddingAdapter()
        self.openai_audio_adapter = OpenAICompatibleAudioAdapter()
        self.ollama_adapter = OllamaChatAdapter()
        self.litellm_chat_adapter = LiteLLMChatAdapter()
        self.litellm_embedding_adapter = LiteLLMEmbeddingAdapter()
        self.native_rerank_adapter = NativeRerankAdapter()

    def _resolve_effective_rate_limit_config(
        self,
        *,
        tenant_model: TenantModel,
        capability_type: str,
    ) -> dict[str, Any]:
        """解析模型级限流配置，兼容平铺和按能力分组两种写法。"""
        raw_config = tenant_model.rate_limit_config or {}
        if not isinstance(raw_config, dict):
            return {}

        default_config = raw_config.get("default")
        capability_config = raw_config.get(capability_type)
        if isinstance(default_config, dict) or isinstance(capability_config, dict):
            merged: dict[str, Any] = {}
            if isinstance(default_config, dict):
                merged.update(default_config)
            if isinstance(capability_config, dict):
                merged.update(capability_config)
            return merged

        # 兼容旧的平铺写法，例如直接写 {"concurrency_limit": 4}
        if any(key in raw_config for key in ("concurrency_limit", "mode", "wait_mode", "wait_timeout_seconds")):
            return dict(raw_config)
        return {}

    def _build_invocation_concurrency_policy(
        self,
        *,
        limiter_type: str,
        capability_type: str,
        tenant_model: TenantModel,
        context: ConcurrencyContext,
    ) -> ConcurrencyPolicy:
        """构造模型调用并发策略，先保留全局闸门，再叠加模型级更严格限制。"""
        base_policy = resolve_concurrency_policy(limiter_type, context=context)
        effective_config = self._resolve_effective_rate_limit_config(
            tenant_model=tenant_model,
            capability_type=capability_type,
        )
        if not effective_config:
            return base_policy

        scope_limits = list(base_policy.scope_limits)
        concurrency_limit = effective_config.get("concurrency_limit")
        if concurrency_limit not in (None, ""):
            try:
                normalized_limit = max(1, int(str(concurrency_limit)))
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{capability_type} 限流配置 concurrency_limit 必须是正整数",
                ) from None
            scope_limits.append(
                ConcurrencyScopeLimit(
                    key=f"concurrency:{limiter_type}:tenant-model:{tenant_model.id}",
                    limit=normalized_limit,
                )
            )

        mode = str(effective_config.get("wait_mode") or effective_config.get("mode") or base_policy.mode).strip().lower()
        if mode not in {"fail_fast", "wait", "wait_timeout"}:
            mode = base_policy.mode

        wait_timeout_seconds = base_policy.wait_timeout_seconds
        timeout_value = effective_config.get("wait_timeout_seconds")
        if timeout_value not in (None, ""):
            try:
                wait_timeout_seconds = max(0, int(str(timeout_value)))
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{capability_type} 限流配置 wait_timeout_seconds 必须是非负整数",
                ) from None
        elif mode == "wait":
            wait_timeout_seconds = None

        return ConcurrencyPolicy(
            limiter_type=base_policy.limiter_type,
            mode=mode,
            wait_timeout_seconds=wait_timeout_seconds,
            lease_ttl_seconds=base_policy.lease_ttl_seconds,
            poll_interval_ms=base_policy.poll_interval_ms,
            scope_limits=scope_limits,
        )

    def _acquire_model_invocation_lease(
        self,
        *,
        limiter_type: str,
        capability_type: str,
        tenant_model: TenantModel,
        context: ConcurrencyContext,
    ):
        """统一获取模型调用租约，让所有能力在同一入口层应用并发规则。"""
        policy = self._build_invocation_concurrency_policy(
            limiter_type=limiter_type,
            capability_type=capability_type,
            tenant_model=tenant_model,
            context=context,
        )
        return acquire_concurrency_lease(
            limiter_type,
            context=context,
            policy=policy,
        )

    async def chat(
        self,
        *,
        current_user: User,
        tenant_model_id: UUID | None,
        capability_type: str,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        extra_body: dict[str, Any] | None = None,
        request_source: str = "api",
    ) -> dict[str, Any]:
        """统一聊天调用入口。"""
        if stream:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前阶段暂不支持流式聊天，请先使用 stream=false",
            )
        if capability_type != "chat":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前阶段仅支持 chat 能力调用",
            )

        tenant_model = await self._resolve_tenant_model(current_user, tenant_model_id, capability_type)
        provider_stmt = select(TenantModelProvider).where(
            TenantModelProvider.id == tenant_model.tenant_provider_id,
            TenantModelProvider.tenant_id == current_user.tenant_id,
            TenantModelProvider.is_enabled == True,  # noqa: E712
        )
        provider_result = await self.db.execute(provider_stmt)
        provider = provider_result.scalar_one_or_none()
        if provider is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型所属厂商未启用或不存在")

        platform_model_stmt = select(PlatformModel).where(
            PlatformModel.id == tenant_model.platform_model_id,
            PlatformModel.is_enabled == True,  # noqa: E712
        )
        platform_model_result = await self.db.execute(platform_model_stmt)
        platform_model = platform_model_result.scalar_one_or_none()
        if platform_model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="平台模型不存在或已禁用")

        definition_stmt = select(ModelProviderDefinition).where(
            ModelProviderDefinition.id == provider.provider_definition_id,
            ModelProviderDefinition.is_enabled == True,  # noqa: E712
        )
        definition_result = await self.db.execute(definition_stmt)
        provider_definition = definition_result.scalar_one_or_none()
        if provider_definition is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型厂商定义不存在或已禁用")

        credential = await ModelProviderIntegrationService(self.db)._load_primary_credential(provider.id)
        api_key = None
        credential_config: dict[str, Any] = {}
        if credential is not None:
            credential_config = credential.encrypted_config or {}
            api_key = str(credential_config.get("api_key", "")).strip() or None

        lease = self._acquire_model_invocation_lease(
            limiter_type="llm",
            capability_type="chat",
            tenant_model=tenant_model,
            context=ConcurrencyContext(
                tenant_id=str(current_user.tenant_id),
                provider=str(provider_definition.provider_code or "").strip() or None,
                model=str(platform_model.raw_model_name or "").strip() or None,
                workload_type="model_platform_chat",
                request_source=request_source,
            ),
        )
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="模型并发资源不足，请稍后重试",
            )

        start_ts = time.perf_counter()
        raw_response: dict[str, Any]
        adapter_type = provider.adapter_override_type or provider_definition.adapter_type
        merged_extra_body = self._merge_request_defaults(
            provider.request_defaults,
            tenant_model.request_defaults,
            extra_body,
        )
        try:
            runtime_profile = self._resolve_capability_runtime_profile(
                capability_type="chat",
                provider_definition=provider_definition,
                provider=provider,
                tenant_model=tenant_model,
                platform_model=platform_model,
            )
            adapter_type = runtime_profile.adapter_type
            protocol_type = provider_definition.protocol_type
            normalized = await self._dispatch_chat(
                protocol_type=protocol_type,
                runtime_profile=runtime_profile,
                provider=provider,
                platform_model=platform_model,
                api_key=api_key,
                credential_config=credential_config,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=merged_extra_body,
                tenant_model_id=tenant_model.id,
            )
            if normalized is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"当前阶段暂不支持协议 {protocol_type} 的聊天调用",
                )

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="chat",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="success",
                latency_ms=latency_ms,
                usage=normalized["usage"],
                error_code=None,
                error_message=None,
            )
            return normalized
        except HTTPException as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="chat",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code=str(exc.status_code),
                error_message=str(exc.detail),
            )
            raise
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            detail = exc.response.text
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="chat",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code=str(exc.response.status_code),
                error_message=detail,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"上游模型服务返回错误: {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="chat",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code="internal_error",
                error_message=str(exc),
            )
            logger.exception("模型聊天调用失败")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="模型调用失败") from exc
        finally:
            release_concurrency_lease(lease)

    async def stream_chat(
        self,
        *,
        current_user: User,
        tenant_model_id: UUID | None,
        capability_type: str,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        extra_body: dict[str, Any] | None = None,
        request_source: str = "api",
    ) -> AsyncIterator[dict[str, Any]]:
        """统一流式聊天调用入口。"""
        if capability_type != "chat":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前阶段仅支持 chat 能力调用",
            )

        (
            tenant_model,
            provider,
            platform_model,
            provider_definition,
            api_key,
            credential_config,
        ) = await self._prepare_invocation_context(
            current_user=current_user,
            tenant_model_id=tenant_model_id,
            capability_type=capability_type,
        )

        lease = self._acquire_model_invocation_lease(
            limiter_type="llm",
            capability_type="chat",
            tenant_model=tenant_model,
            context=ConcurrencyContext(
                tenant_id=str(current_user.tenant_id),
                provider=str(provider_definition.provider_code or "").strip() or None,
                model=str(platform_model.raw_model_name or "").strip() or None,
                workload_type="model_platform_chat_stream",
                request_source=request_source,
            ),
        )
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="模型并发资源不足，请稍后重试",
            )

        start_ts = time.perf_counter()
        adapter_type = provider.adapter_override_type or provider_definition.adapter_type
        merged_extra_body = self._merge_request_defaults(
            provider.request_defaults,
            tenant_model.request_defaults,
            extra_body,
        )
        usage: dict[str, Any] = {}
        try:
            runtime_profile = self._resolve_capability_runtime_profile(
                capability_type="chat",
                provider_definition=provider_definition,
                provider=provider,
                tenant_model=tenant_model,
                platform_model=platform_model,
            )
            adapter_type = runtime_profile.adapter_type
            async for chunk in self._dispatch_chat_stream(
                protocol_type=provider_definition.protocol_type,
                runtime_profile=runtime_profile,
                provider=provider,
                platform_model=platform_model,
                api_key=api_key,
                credential_config=credential_config,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=merged_extra_body,
            ):
                usage = self._merge_stream_usage(usage, chunk)
                yield chunk

            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="chat",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="success",
                latency_ms=int((time.perf_counter() - start_ts) * 1000),
                usage=usage,
                error_code=None,
                error_message=None,
            )
        except HTTPException as exc:
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="chat",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=int((time.perf_counter() - start_ts) * 1000),
                usage={},
                error_code=str(exc.status_code),
                error_message=str(exc.detail),
            )
            raise
        except httpx.HTTPStatusError as exc:
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="chat",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=int((time.perf_counter() - start_ts) * 1000),
                usage={},
                error_code=str(exc.response.status_code),
                error_message=exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"上游模型服务返回错误: {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="chat",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=int((time.perf_counter() - start_ts) * 1000),
                usage={},
                error_code="internal_error",
                error_message=str(exc),
            )
            logger.exception("模型流式聊天调用失败")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="模型调用失败") from exc
        finally:
            release_concurrency_lease(lease)

    async def embed(
        self,
        *,
        current_user: User,
        tenant_model_id: UUID | None,
        capability_type: str,
        input_texts: list[str],
        extra_body: dict[str, Any] | None = None,
        request_source: str = "api",
    ) -> dict[str, Any]:
        """统一 embedding 调用入口。"""
        if capability_type != "embedding":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前阶段仅支持 embedding 能力调用",
            )

        tenant_model = await self._resolve_tenant_model(current_user, tenant_model_id, capability_type)
        provider_stmt = select(TenantModelProvider).where(
            TenantModelProvider.id == tenant_model.tenant_provider_id,
            TenantModelProvider.tenant_id == current_user.tenant_id,
            TenantModelProvider.is_enabled == True,  # noqa: E712
        )
        provider_result = await self.db.execute(provider_stmt)
        provider = provider_result.scalar_one_or_none()
        if provider is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型所属厂商未启用或不存在")

        platform_model_stmt = select(PlatformModel).where(
            PlatformModel.id == tenant_model.platform_model_id,
            PlatformModel.is_enabled == True,  # noqa: E712
        )
        platform_model_result = await self.db.execute(platform_model_stmt)
        platform_model = platform_model_result.scalar_one_or_none()
        if platform_model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="平台模型不存在或已禁用")

        definition_stmt = select(ModelProviderDefinition).where(
            ModelProviderDefinition.id == provider.provider_definition_id,
            ModelProviderDefinition.is_enabled == True,  # noqa: E712
        )
        definition_result = await self.db.execute(definition_stmt)
        provider_definition = definition_result.scalar_one_or_none()
        if provider_definition is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型厂商定义不存在或已禁用")

        credential = await ModelProviderIntegrationService(self.db)._load_primary_credential(provider.id)
        api_key = None
        credential_config: dict[str, Any] = {}
        if credential is not None:
            credential_config = credential.encrypted_config or {}
            api_key = str(credential_config.get("api_key", "")).strip() or None

        lease = self._acquire_model_invocation_lease(
            limiter_type="embed",
            capability_type="embedding",
            tenant_model=tenant_model,
            context=ConcurrencyContext(
                tenant_id=str(current_user.tenant_id),
                provider=str(provider_definition.provider_code or "").strip() or None,
                model=str(platform_model.raw_model_name or "").strip() or None,
                workload_type="model_platform_embedding",
                request_source=request_source,
            ),
        )
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="向量模型并发资源不足，请稍后重试",
            )

        start_ts = time.perf_counter()
        adapter_type = provider.adapter_override_type or provider_definition.adapter_type
        executed_adapter_type = adapter_type
        merged_extra_body = self._merge_request_defaults(
            provider.request_defaults,
            tenant_model.request_defaults,
            extra_body,
        )
        try:
            runtime_profile = self._resolve_capability_runtime_profile(
                capability_type="embedding",
                provider_definition=provider_definition,
                provider=provider,
                tenant_model=tenant_model,
                platform_model=platform_model,
            )
            adapter_type = runtime_profile.adapter_type
            executed_adapter_type = adapter_type
            protocol_type = provider_definition.protocol_type
            if adapter_type == "litellm":
                try:
                    raw_response = await self.litellm_embedding_adapter.embed(
                        protocol_type=protocol_type,
                        base_url=runtime_profile.base_url,
                        api_key=api_key,
                        model_name=platform_model.raw_model_name,
                        input_texts=input_texts,
                        api_version=provider.api_version,
                        region=provider.region,
                        provider_config=provider.request_defaults,
                        credential_config=credential_config,
                        extra_body=merged_extra_body,
                    )
                    normalized = self._normalize_embedding_response(
                        tenant_model_id=tenant_model.id,
                        model_name=platform_model.raw_model_name,
                        adapter_type=adapter_type,
                        raw_response=raw_response,
                    )
                except Exception:
                    if protocol_type not in {"openai", "openai_compatible", "vllm", "azure_openai"}:
                        raise
                    logger.warning("LiteLLM embedding 调用失败，尝试回退直连适配器", exc_info=True)
                    raw_response = await self.openai_embedding_adapter.embed(
                        base_url=runtime_profile.base_url,
                        api_key=api_key,
                        model_name=platform_model.raw_model_name,
                        input_texts=input_texts,
                        endpoint_path=runtime_profile.endpoint_path or "/embeddings",
                        extra_headers=runtime_profile.extra_headers,
                        timeout_seconds=runtime_profile.timeout_seconds,
                        extra_body=merged_extra_body,
                    )
                    normalized = self._normalize_embedding_response(
                        tenant_model_id=tenant_model.id,
                        model_name=platform_model.raw_model_name,
                        adapter_type="native",
                        raw_response=raw_response,
                    )
                    executed_adapter_type = "native"
            elif adapter_type in {"native", "custom"}:
                raw_response = await self.openai_embedding_adapter.embed(
                    base_url=runtime_profile.base_url,
                    api_key=api_key,
                    model_name=platform_model.raw_model_name,
                    input_texts=input_texts,
                    endpoint_path=runtime_profile.endpoint_path or "/embeddings",
                    extra_headers=runtime_profile.extra_headers,
                    timeout_seconds=runtime_profile.timeout_seconds,
                    extra_body=merged_extra_body,
                )
                normalized = self._normalize_embedding_response(
                    tenant_model_id=tenant_model.id,
                    model_name=platform_model.raw_model_name,
                    adapter_type=adapter_type,
                    raw_response=raw_response,
                )
                executed_adapter_type = adapter_type
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"当前阶段暂未实现适配器 {adapter_type} 的 embedding 调用",
                )

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="embedding",
                adapter_type=executed_adapter_type,
                request_source=request_source,
                status_value="success",
                latency_ms=latency_ms,
                usage=normalized["usage"],
                error_code=None,
                error_message=None,
            )
            return normalized
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="embedding",
                adapter_type=executed_adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code=str(exc.response.status_code),
                error_message=exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"上游模型服务返回错误: {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="embedding",
                adapter_type=executed_adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code="internal_error",
                error_message=str(exc),
            )
            logger.exception("模型 embedding 调用失败")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="模型调用失败") from exc
        finally:
            release_concurrency_lease(lease)

    async def rerank(
        self,
        *,
        current_user: User,
        tenant_model_id: UUID | None,
        capability_type: str,
        query: str | dict[str, Any],
        documents: list[str | dict[str, Any]],
        top_n: int | None = None,
        return_documents: bool | None = None,
        extra_body: dict[str, Any] | None = None,
        request_source: str = "api",
    ) -> dict[str, Any]:
        """统一 rerank 调用入口。"""
        if capability_type != "rerank":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前阶段仅支持 rerank 能力调用",
            )

        tenant_model = await self._resolve_tenant_model(current_user, tenant_model_id, capability_type)
        provider_stmt = select(TenantModelProvider).where(
            TenantModelProvider.id == tenant_model.tenant_provider_id,
            TenantModelProvider.tenant_id == current_user.tenant_id,
            TenantModelProvider.is_enabled == True,  # noqa: E712
        )
        provider_result = await self.db.execute(provider_stmt)
        provider = provider_result.scalar_one_or_none()
        if provider is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型所属厂商未启用或不存在")

        platform_model_stmt = select(PlatformModel).where(
            PlatformModel.id == tenant_model.platform_model_id,
            PlatformModel.is_enabled == True,  # noqa: E712
        )
        platform_model_result = await self.db.execute(platform_model_stmt)
        platform_model = platform_model_result.scalar_one_or_none()
        if platform_model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="平台模型不存在或已禁用")

        definition_stmt = select(ModelProviderDefinition).where(
            ModelProviderDefinition.id == provider.provider_definition_id,
            ModelProviderDefinition.is_enabled == True,  # noqa: E712
        )
        definition_result = await self.db.execute(definition_stmt)
        provider_definition = definition_result.scalar_one_or_none()
        if provider_definition is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型厂商定义不存在或已禁用")

        credential = await ModelProviderIntegrationService(self.db)._load_primary_credential(provider.id)
        api_key = None
        if credential is not None:
            api_key = str((credential.encrypted_config or {}).get("api_key", "")).strip() or None

        lease = self._acquire_model_invocation_lease(
            limiter_type="llm",
            capability_type="rerank",
            tenant_model=tenant_model,
            context=ConcurrencyContext(
                tenant_id=str(current_user.tenant_id),
                provider=str(provider_definition.provider_code or "").strip() or None,
                model=str(platform_model.raw_model_name or "").strip() or None,
                workload_type="model_platform_rerank",
                request_source=request_source,
            ),
        )
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="重排序模型并发资源不足，请稍后重试",
            )

        start_ts = time.perf_counter()
        adapter_type = provider.adapter_override_type or provider_definition.adapter_type
        merged_extra_body = self._merge_request_defaults(
            provider.request_defaults,
            tenant_model.request_defaults,
            extra_body,
        )
        try:
            runtime_profile = self._resolve_capability_runtime_profile(
                capability_type="rerank",
                provider_definition=provider_definition,
                provider=provider,
                tenant_model=tenant_model,
                platform_model=platform_model,
            )
            adapter_type = runtime_profile.adapter_type
            profile = self._resolve_rerank_endpoint_profile(
                provider_definition=provider_definition,
                provider=provider,
                tenant_model=tenant_model,
                platform_model=platform_model,
            )
            if adapter_type == "litellm":
                adapter_type = "native"
            if adapter_type not in {"native", "custom"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"当前阶段暂未实现适配器 {adapter_type} 的 rerank 调用",
                )

            raw_result = await self.native_rerank_adapter.rerank(
                profile=profile,
                api_key=api_key,
                model_name=platform_model.raw_model_name,
                query=query,
                documents=documents,
                top_n=top_n,
                return_documents=return_documents,
                extra_options=merged_extra_body,
            )
            normalized = self._normalize_rerank_response(
                tenant_model_id=tenant_model.id,
                adapter_type=adapter_type,
                raw_result=raw_result,
            )

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="rerank",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="success",
                latency_ms=latency_ms,
                usage=normalized["usage"],
                error_code=None,
                error_message=None,
            )
            return normalized
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="rerank",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code=str(exc.response.status_code),
                error_message=exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"上游模型服务返回错误: {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="rerank",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code="internal_error",
                error_message=str(exc),
            )
            logger.exception("模型 rerank 调用失败")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="模型调用失败") from exc
        finally:
            release_concurrency_lease(lease)

    async def transcribe(
        self,
        *,
        current_user: User,
        tenant_model_id: UUID | None,
        capability_type: str,
        audio_url: str | None,
        audio_base64: str | None,
        filename: str | None,
        mime_type: str | None,
        language: str | None = None,
        prompt: str | None = None,
        response_format: str | None = None,
        temperature: float | None = None,
        extra_body: dict[str, Any] | None = None,
        request_source: str = "api",
    ) -> dict[str, Any]:
        """统一 ASR 调用入口。"""
        if capability_type != "asr":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前阶段仅支持 asr 能力调用",
            )

        tenant_model, provider, platform_model, provider_definition, api_key, credential_config = await self._prepare_invocation_context(
            current_user=current_user,
            tenant_model_id=tenant_model_id,
            capability_type=capability_type,
        )
        lease = self._acquire_model_invocation_lease(
            limiter_type="llm",
            capability_type="asr",
            tenant_model=tenant_model,
            context=ConcurrencyContext(
                tenant_id=str(current_user.tenant_id),
                provider=str(provider_definition.provider_code or "").strip() or None,
                model=str(platform_model.raw_model_name or "").strip() or None,
                workload_type="model_platform_asr",
                request_source=request_source,
            ),
        )
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="语音识别模型并发资源不足，请稍后重试",
            )

        start_ts = time.perf_counter()
        adapter_type = provider.adapter_override_type or provider_definition.adapter_type
        merged_extra_body = self._merge_request_defaults(
            provider.request_defaults,
            tenant_model.request_defaults,
            extra_body,
        )
        try:
            runtime_profile = self._resolve_capability_runtime_profile(
                capability_type="asr",
                provider_definition=provider_definition,
                provider=provider,
                tenant_model=tenant_model,
                platform_model=platform_model,
            )
            adapter_type = runtime_profile.adapter_type
            audio_payload = await self._resolve_audio_input_payload(
                audio_url=audio_url,
                audio_base64_value=audio_base64,
                filename=filename,
                mime_type=mime_type,
            )
            if adapter_type == "litellm":
                adapter_type = "native"
            if adapter_type not in {"native", "custom"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"当前阶段暂未实现适配器 {adapter_type} 的 asr 调用",
                )

            raw_result = await self.openai_audio_adapter.transcribe(
                base_url=runtime_profile.base_url,
                api_key=api_key,
                model_name=platform_model.raw_model_name,
                audio_bytes=audio_payload["audio_bytes"],
                filename=audio_payload["filename"],
                mime_type=audio_payload["mime_type"],
                endpoint_path=runtime_profile.endpoint_path or "/audio/transcriptions",
                language=language,
                prompt=prompt,
                response_format=response_format,
                temperature=temperature,
                extra_headers=runtime_profile.extra_headers,
                extra_body=merged_extra_body,
                timeout_seconds=runtime_profile.timeout_seconds,
            )
            normalized = self._normalize_transcription_response(
                tenant_model_id=tenant_model.id,
                model_name=platform_model.raw_model_name,
                adapter_type=adapter_type,
                raw_result=raw_result,
            )

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="asr",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="success",
                latency_ms=latency_ms,
                usage=normalized["usage"],
                error_code=None,
                error_message=None,
            )
            return normalized
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="asr",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code=str(exc.response.status_code),
                error_message=exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"上游模型服务返回错误: {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="asr",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code="internal_error",
                error_message=str(exc),
            )
            logger.exception("模型 asr 调用失败")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="模型调用失败") from exc
        finally:
            release_concurrency_lease(lease)

    async def synthesize_speech(
        self,
        *,
        current_user: User,
        tenant_model_id: UUID | None,
        capability_type: str,
        text: str,
        voice: str,
        response_format: str | None = None,
        speed: float | None = None,
        extra_body: dict[str, Any] | None = None,
        request_source: str = "api",
    ) -> dict[str, Any]:
        """统一 TTS 调用入口。"""
        if capability_type != "tts":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前阶段仅支持 tts 能力调用",
            )

        tenant_model, provider, platform_model, provider_definition, api_key, credential_config = await self._prepare_invocation_context(
            current_user=current_user,
            tenant_model_id=tenant_model_id,
            capability_type=capability_type,
        )
        lease = self._acquire_model_invocation_lease(
            limiter_type="llm",
            capability_type="tts",
            tenant_model=tenant_model,
            context=ConcurrencyContext(
                tenant_id=str(current_user.tenant_id),
                provider=str(provider_definition.provider_code or "").strip() or None,
                model=str(platform_model.raw_model_name or "").strip() or None,
                workload_type="model_platform_tts",
                request_source=request_source,
            ),
        )
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="语音合成模型并发资源不足，请稍后重试",
            )

        start_ts = time.perf_counter()
        adapter_type = provider.adapter_override_type or provider_definition.adapter_type
        merged_extra_body = self._merge_request_defaults(
            provider.request_defaults,
            tenant_model.request_defaults,
            extra_body,
        )
        try:
            runtime_profile = self._resolve_capability_runtime_profile(
                capability_type="tts",
                provider_definition=provider_definition,
                provider=provider,
                tenant_model=tenant_model,
                platform_model=platform_model,
            )
            adapter_type = runtime_profile.adapter_type
            if adapter_type == "litellm":
                adapter_type = "native"
            if adapter_type not in {"native", "custom"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"当前阶段暂未实现适配器 {adapter_type} 的 tts 调用",
                )

            raw_result = await self.openai_audio_adapter.synthesize(
                base_url=runtime_profile.base_url,
                api_key=api_key,
                model_name=platform_model.raw_model_name,
                text=text,
                voice=voice,
                endpoint_path=runtime_profile.endpoint_path or "/audio/speech",
                response_format=response_format,
                speed=speed,
                extra_headers=runtime_profile.extra_headers,
                extra_body=merged_extra_body,
                timeout_seconds=runtime_profile.timeout_seconds,
            )
            normalized = self._normalize_speech_response(
                tenant_model_id=tenant_model.id,
                model_name=platform_model.raw_model_name,
                adapter_type=adapter_type,
                raw_result=raw_result,
            )

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="tts",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="success",
                latency_ms=latency_ms,
                usage=normalized["usage"],
                error_code=None,
                error_message=None,
            )
            return normalized
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="tts",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code=str(exc.response.status_code),
                error_message=exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"上游模型服务返回错误: {exc.response.status_code}",
            ) from exc
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            await self._record_invocation(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=provider.id,
                tenant_model_id=tenant_model.id,
                capability_type="tts",
                adapter_type=adapter_type,
                request_source=request_source,
                status_value="failed",
                latency_ms=latency_ms,
                usage={},
                error_code="internal_error",
                error_message=str(exc),
            )
            logger.exception("模型 tts 调用失败")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="模型调用失败") from exc
        finally:
            release_concurrency_lease(lease)

    async def preview_runtime_profile(
        self,
        *,
        current_user: User,
        tenant_model_id: UUID,
        capability_type: str,
    ) -> dict[str, Any]:
        """预览指定模型的最终运行时画像，供前端调试面板展示。"""
        tenant_model, provider, platform_model, provider_definition, _, _ = await self._prepare_invocation_context(
            current_user=current_user,
            tenant_model_id=tenant_model_id,
            capability_type=capability_type,
        )
        runtime_profile = self._resolve_capability_runtime_profile(
            capability_type=capability_type,
            provider_definition=provider_definition,
            provider=provider,
            tenant_model=tenant_model,
            platform_model=platform_model,
        )
        return self._serialize_runtime_profile(
            tenant_model=tenant_model,
            provider=provider,
            provider_definition=provider_definition,
            platform_model=platform_model,
            runtime_profile=runtime_profile,
        )

    async def debug_invoke(
        self,
        *,
        current_user: User,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """执行调试面板的最小测试调用。"""
        tenant_model_id = payload["tenant_model_id"]
        capability_type = str(payload.get("capability_type") or "").strip()
        profile = await self.preview_runtime_profile(
            current_user=current_user,
            tenant_model_id=tenant_model_id,
            capability_type=capability_type,
        )

        if capability_type == "chat":
            prompt = str(payload.get("prompt") or "").strip() or "你好，请用一句话介绍你自己。"
            result = await self.chat(
                current_user=current_user,
                tenant_model_id=tenant_model_id,
                capability_type="chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=payload.get("temperature"),
                max_tokens=payload.get("max_tokens"),
                stream=False,
                extra_body=None,
                request_source="debug_panel",
            )
        elif capability_type == "embedding":
            prompt = str(payload.get("prompt") or "").strip() or "这是一个用于调试 embedding 的示例文本。"
            result = await self.embed(
                current_user=current_user,
                tenant_model_id=tenant_model_id,
                capability_type="embedding",
                input_texts=[prompt],
                extra_body=None,
                request_source="debug_panel",
            )
        elif capability_type == "rerank":
            query = str(payload.get("query") or "").strip() or "什么是文本排序模型"
            raw_documents = payload.get("documents") or []
            documents: list[str | dict[str, Any]] = [
                str(item).strip()
                for item in raw_documents
                if str(item).strip()
            ] or [
                "文本排序模型广泛用于搜索引擎和推荐系统中。",
                "量子计算是计算科学的一个前沿领域。",
                "预训练语言模型推动了文本排序模型的发展。",
            ]
            result = await self.rerank(
                current_user=current_user,
                tenant_model_id=tenant_model_id,
                capability_type="rerank",
                query=query,
                documents=documents,
                top_n=payload.get("top_n"),
                return_documents=payload.get("return_documents"),
                extra_body=None,
                request_source="debug_panel",
            )
        elif capability_type == "asr":
            result = await self.transcribe(
                current_user=current_user,
                tenant_model_id=tenant_model_id,
                capability_type="asr",
                audio_url=payload.get("audio_url"),
                audio_base64=payload.get("audio_base64"),
                filename=payload.get("filename"),
                mime_type=payload.get("mime_type"),
                language=None,
                prompt=str(payload.get("prompt") or "").strip() or None,
                response_format=payload.get("response_format"),
                temperature=payload.get("temperature"),
                extra_body=None,
                request_source="debug_panel",
            )
        elif capability_type == "tts":
            prompt = str(payload.get("prompt") or "").strip() or "这是一个用于调试语音合成的示例文本。"
            voice = str(payload.get("voice") or "").strip() or "alloy"
            result = await self.synthesize_speech(
                current_user=current_user,
                tenant_model_id=tenant_model_id,
                capability_type="tts",
                text=prompt,
                voice=voice,
                response_format=payload.get("response_format"),
                speed=None,
                extra_body=None,
                request_source="debug_panel",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"当前调试面板暂不支持能力 {capability_type}",
            )

        return {
            "profile": profile,
            "result": result,
        }

    async def _dispatch_chat(
        self,
        *,
        protocol_type: str,
        runtime_profile: CapabilityRuntimeProfile,
        provider: TenantModelProvider,
        platform_model: PlatformModel,
        api_key: str | None,
        credential_config: dict[str, Any],
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        extra_body: dict[str, Any] | None,
        tenant_model_id: UUID,
    ) -> dict[str, Any] | None:
        """分发聊天调用，优先走 LiteLLM，失败时对部分协议回退直连。"""
        raw_response: dict[str, Any]
        planned_adapter_type = runtime_profile.adapter_type
        if planned_adapter_type == "litellm":
            try:
                raw_response = await self.litellm_chat_adapter.chat(
                    protocol_type=protocol_type,
                    base_url=runtime_profile.base_url,
                    api_key=api_key,
                    model_name=platform_model.raw_model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_version=provider.api_version,
                    region=provider.region,
                    provider_config=provider.request_defaults,
                    credential_config=credential_config,
                    extra_body=extra_body,
                )
                if protocol_type == "ollama":
                    normalized = self._normalize_ollama_chat_response(
                        tenant_model_id=tenant_model_id,
                        model_name=platform_model.raw_model_name,
                        adapter_type="litellm",
                        raw_response=raw_response,
                    )
                    normalized["planned_adapter_type"] = planned_adapter_type
                    normalized["execution_path"] = "litellm"
                    return normalized
                normalized = self._normalize_openai_chat_response(
                    tenant_model_id=tenant_model_id,
                    model_name=platform_model.raw_model_name,
                    adapter_type="litellm",
                    raw_response=raw_response,
                )
                normalized["planned_adapter_type"] = planned_adapter_type
                normalized["execution_path"] = "litellm"
                return normalized
            except Exception:
                logger.warning("LiteLLM 聊天调用失败，尝试回退直连适配器", exc_info=True)

        if protocol_type in {"openai", "openai_compatible", "vllm", "azure_openai"}:
            raw_response = await self.openai_adapter.chat(
                base_url=runtime_profile.base_url,
                api_key=api_key,
                model_name=platform_model.raw_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                endpoint_path=runtime_profile.endpoint_path or "/chat/completions",
                extra_headers=runtime_profile.extra_headers,
                timeout_seconds=runtime_profile.timeout_seconds,
                extra_body=extra_body,
            )
            normalized = self._normalize_openai_chat_response(
                tenant_model_id=tenant_model_id,
                model_name=platform_model.raw_model_name,
                adapter_type="native" if planned_adapter_type == "litellm" else planned_adapter_type,
                raw_response=raw_response,
            )
            normalized["planned_adapter_type"] = planned_adapter_type
            normalized["execution_path"] = (
                "fallback_openai_compatible"
                if planned_adapter_type == "litellm"
                else "direct_openai_compatible"
            )
            return normalized
        if protocol_type == "ollama":
            raw_response = await self.ollama_adapter.chat(
                base_url=runtime_profile.base_url,
                model_name=platform_model.raw_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                endpoint_path=runtime_profile.endpoint_path or "/api/chat",
                timeout_seconds=runtime_profile.timeout_seconds,
                extra_body=extra_body,
            )
            normalized = self._normalize_ollama_chat_response(
                tenant_model_id=tenant_model_id,
                model_name=platform_model.raw_model_name,
                adapter_type="native" if planned_adapter_type == "litellm" else planned_adapter_type,
                raw_response=raw_response,
            )
            normalized["planned_adapter_type"] = planned_adapter_type
            normalized["execution_path"] = (
                "fallback_ollama"
                if planned_adapter_type == "litellm"
                else "direct_ollama"
            )
            return normalized
        return None

    async def _dispatch_chat_stream(
        self,
        *,
        protocol_type: str,
        runtime_profile: CapabilityRuntimeProfile,
        provider: TenantModelProvider,
        platform_model: PlatformModel,
        api_key: str | None,
        credential_config: dict[str, Any],
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        extra_body: dict[str, Any] | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """分发流式聊天调用，保持与非流式调用相同的适配器优先级。"""
        planned_adapter_type = runtime_profile.adapter_type
        if planned_adapter_type == "litellm":
            has_yielded = False
            try:
                async for chunk in self.litellm_chat_adapter.stream_chat(
                    protocol_type=protocol_type,
                    base_url=runtime_profile.base_url,
                    api_key=api_key,
                    model_name=platform_model.raw_model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_version=provider.api_version,
                    region=provider.region,
                    provider_config=provider.request_defaults,
                    credential_config=credential_config,
                    extra_body=extra_body,
                ):
                    has_yielded = True
                    yield chunk
                return
            except Exception:
                if has_yielded:
                    raise
                logger.warning("LiteLLM 流式聊天调用失败，尝试回退直连适配器", exc_info=True)

        if protocol_type in {"openai", "openai_compatible", "vllm", "azure_openai"}:
            async for chunk in self.openai_adapter.stream_chat(
                base_url=runtime_profile.base_url,
                api_key=api_key,
                model_name=platform_model.raw_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                endpoint_path=runtime_profile.endpoint_path or "/chat/completions",
                extra_headers=runtime_profile.extra_headers,
                timeout_seconds=runtime_profile.timeout_seconds,
                extra_body=extra_body,
            ):
                yield chunk
            return

        if protocol_type == "ollama":
            async for chunk in self.ollama_adapter.stream_chat(
                base_url=runtime_profile.base_url,
                model_name=platform_model.raw_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                endpoint_path=runtime_profile.endpoint_path or "/api/chat",
                timeout_seconds=runtime_profile.timeout_seconds,
                extra_body=extra_body,
            ):
                yield chunk
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前阶段暂不支持协议 {protocol_type} 的流式聊天调用",
        )

    @staticmethod
    def _merge_stream_usage(current: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
        """从流式 chunk 中提取用量信息；不同上游可能只在最后一帧返回。"""
        raw_usage = chunk.get("usage") or {}
        if not isinstance(raw_usage, dict):
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
        return next_usage

    async def _prepare_invocation_context(
        self,
        *,
        current_user: User,
        tenant_model_id: UUID | None,
        capability_type: str,
    ) -> tuple[TenantModel, TenantModelProvider, PlatformModel, ModelProviderDefinition, str | None, dict[str, Any]]:
        """统一解析调用上下文，避免不同能力重复查询。"""
        tenant_model = await self._resolve_tenant_model(current_user, tenant_model_id, capability_type)
        provider_stmt = select(TenantModelProvider).where(
            TenantModelProvider.id == tenant_model.tenant_provider_id,
            TenantModelProvider.tenant_id == current_user.tenant_id,
            TenantModelProvider.is_enabled == True,  # noqa: E712
        )
        provider_result = await self.db.execute(provider_stmt)
        provider = provider_result.scalar_one_or_none()
        if provider is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型所属厂商未启用或不存在")

        platform_model_stmt = select(PlatformModel).where(
            PlatformModel.id == tenant_model.platform_model_id,
            PlatformModel.is_enabled == True,  # noqa: E712
        )
        platform_model_result = await self.db.execute(platform_model_stmt)
        platform_model = platform_model_result.scalar_one_or_none()
        if platform_model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="平台模型不存在或已禁用")

        definition_stmt = select(ModelProviderDefinition).where(
            ModelProviderDefinition.id == provider.provider_definition_id,
            ModelProviderDefinition.is_enabled == True,  # noqa: E712
        )
        definition_result = await self.db.execute(definition_stmt)
        provider_definition = definition_result.scalar_one_or_none()
        if provider_definition is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型厂商定义不存在或已禁用")

        credential = await ModelProviderIntegrationService(self.db)._load_primary_credential(provider.id)
        api_key = None
        credential_config: dict[str, Any] = {}
        if credential is not None:
            credential_config = credential.encrypted_config or {}
            api_key = str(credential_config.get("api_key", "")).strip() or None
        return tenant_model, provider, platform_model, provider_definition, api_key, credential_config

    def _merge_request_defaults(self, *configs: dict[str, Any] | None) -> dict[str, Any]:
        """合并 provider、模型和调用时的默认参数。"""
        merged: dict[str, Any] = {}
        for config in configs:
            if not isinstance(config, dict):
                continue
            merged.update(config)
        return merged

    async def _resolve_audio_input_payload(
        self,
        *,
        audio_url: str | None,
        audio_base64_value: str | None,
        filename: str | None,
        mime_type: str | None,
    ) -> dict[str, Any]:
        """解析 ASR 输入音频，统一转成字节内容。"""
        resolved_filename = str(filename or "").strip() or None
        resolved_mime_type = str(mime_type or "").strip() or None
        if audio_base64_value:
            try:
                audio_bytes = base64.b64decode(audio_base64_value)
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="audio_base64 不是有效的 base64 字符串") from exc
            return {
                "audio_bytes": audio_bytes,
                "filename": resolved_filename or "audio-input.wav",
                "mime_type": resolved_mime_type or "audio/wav",
            }

        if not audio_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少音频输入")

        timeout = httpx.Timeout(60.0, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(audio_url)
            response.raise_for_status()
            parsed = urlparse(audio_url)
            url_filename = parsed.path.rsplit("/", 1)[-1] if parsed.path else ""
            inferred_filename = resolved_filename or url_filename or "audio-input.wav"
            inferred_mime_type = resolved_mime_type or response.headers.get("content-type") or mimetypes.guess_type(inferred_filename)[0] or "application/octet-stream"
            return {
                "audio_bytes": response.content,
                "filename": inferred_filename,
                "mime_type": inferred_mime_type,
            }

    async def _resolve_tenant_model(
        self,
        current_user: User,
        tenant_model_id: UUID | None,
        capability_type: str,
    ) -> TenantModel:
        """解析本次调用使用的租户模型。"""
        if tenant_model_id is not None:
            stmt = select(TenantModel).where(
                TenantModel.id == tenant_model_id,
                TenantModel.tenant_id == current_user.tenant_id,
                TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
                TenantModel.is_enabled == True,  # noqa: E712
            )
            result = await self.db.execute(stmt)
            tenant_model = result.scalar_one_or_none()
            if tenant_model is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租户模型不存在或未启用")
            return tenant_model

        default_stmt = select(TenantDefaultModel).where(
            TenantDefaultModel.tenant_id == current_user.tenant_id,
            TenantDefaultModel.resource_scope == TENANT_RESOURCE_SCOPE,
            TenantDefaultModel.capability_type == capability_type,
            TenantDefaultModel.is_enabled == True,  # noqa: E712
        )
        default_result = await self.db.execute(default_stmt)
        default_binding = default_result.scalar_one_or_none()
        if default_binding is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"当前租户尚未配置默认 {capability_type} 模型")

        model_stmt = select(TenantModel).where(
            TenantModel.id == default_binding.tenant_model_id,
            TenantModel.tenant_id == current_user.tenant_id,
            TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
            TenantModel.is_enabled == True,  # noqa: E712
        )
        model_result = await self.db.execute(model_stmt)
        tenant_model = model_result.scalar_one_or_none()
        if tenant_model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"默认 {capability_type} 模型不存在或未启用")
        return tenant_model
    async def _record_invocation(
        self,
        *,
        tenant_id: UUID,
        tenant_provider_id: UUID,
        tenant_model_id: UUID,
        capability_type: str,
        adapter_type: str,
        request_source: str,
        status_value: str,
        latency_ms: int,
        usage: dict[str, Any],
        error_code: str | None,
        error_message: str | None,
    ) -> None:
        """记录模型调用日志。"""
        log = ModelInvocationLog(
            tenant_id=tenant_id,
            tenant_provider_id=tenant_provider_id,
            tenant_model_id=tenant_model_id,
            capability_type=capability_type,
            adapter_type=adapter_type if adapter_type in {"litellm", "native", "openai_sdk", "custom"} else "custom",
            request_source=request_source,
            status=status_value,
            latency_ms=latency_ms,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            total_tokens=usage.get("total_tokens"),
            error_code=error_code,
            error_message=error_message,
        )
        self.db.add(log)
        await self.db.commit()


