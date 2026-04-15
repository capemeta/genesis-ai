"""
模型平台运行时画像服务。

职责：
1. 解析能力级覆盖配置；
2. 生成统一运行时画像；
3. 维护 adapter / request_schema / endpoint_path 的默认策略矩阵；
4. 序列化调试面板所需的路由解析结果与来源信息。
"""

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

from core.model_platform.rerank_adapters import RerankEndpointProfile
from models.model_provider_definition import ModelProviderDefinition
from models.platform_model import PlatformModel
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider


@dataclass(slots=True)
class CapabilityDefaultRule:
    """能力默认规则项。"""

    capability_type: str
    provider_codes: tuple[str, ...] | None = None
    request_schemas: tuple[str, ...] | None = None
    adapter_type: str | None = None
    request_schema: str | None = None
    endpoint_path: str | None = None


# 厂商 + 能力默认策略矩阵。
# 说明：
# 1. 统一承载 adapter / request_schema / endpoint_path 的默认推导；
# 2. 规则按顺序匹配，越靠前优先级越高；
# 3. 未命中规则时，自动回落到各字段的通用默认逻辑。
CAPABILITY_DEFAULT_RULE_MATRIX: tuple[CapabilityDefaultRule, ...] = (
    # Tongyi embedding 默认走 native，避免部分兼容实现参数差异导致的首跳失败。
    CapabilityDefaultRule(capability_type="embedding", provider_codes=("tongyi_qianwen",), adapter_type="native"),
    # Ollama chat 走 /api/chat。
    CapabilityDefaultRule(
        capability_type="chat",
        provider_codes=("ollama",),
        request_schemas=("openai_chat_completions", "openai_vision"),
        endpoint_path="/api/chat",
    ),
    # Tongyi rerank 的 openai_rerank 走 compatible-api。
    CapabilityDefaultRule(
        capability_type="rerank",
        provider_codes=("tongyi_qianwen",),
        request_schemas=("openai_rerank",),
        endpoint_path="/compatible-api/v1/reranks",
    ),
    # DashScope 原生 rerank 服务路径。
    CapabilityDefaultRule(
        capability_type="rerank",
        request_schemas=("dashscope_text_rerank_v1", "dashscope_multimodal_rerank_v1"),
        endpoint_path="/api/v1/services/rerank/text-rerank/text-rerank",
    ),
    # OpenAI 兼容族通用路径。
    CapabilityDefaultRule(capability_type="chat", request_schemas=("openai_chat_completions", "openai_vision"), endpoint_path="/chat/completions"),
    CapabilityDefaultRule(capability_type="embedding", request_schema="openai_embedding", endpoint_path="/embeddings"),
    CapabilityDefaultRule(capability_type="rerank", request_schemas=("openai_rerank",), endpoint_path="/reranks"),
    CapabilityDefaultRule(capability_type="asr", request_schema="openai_audio_transcription", endpoint_path="/audio/transcriptions"),
    CapabilityDefaultRule(capability_type="tts", request_schema="openai_audio_speech", endpoint_path="/audio/speech"),
    # 通用 request schema 默认。
    CapabilityDefaultRule(capability_type="chat", request_schema="openai_chat_completions"),
    CapabilityDefaultRule(capability_type="vision", request_schema="openai_vision"),
    CapabilityDefaultRule(capability_type="embedding", request_schema="openai_embedding"),
    CapabilityDefaultRule(capability_type="asr", request_schema="openai_audio_transcription"),
    CapabilityDefaultRule(capability_type="tts", request_schema="openai_audio_speech"),
)


@dataclass(slots=True)
class CapabilityRuntimeProfile:
    """统一能力运行时画像，承载解析后的最终路由配置。"""

    capability_type: str
    adapter_type: str
    base_url: str
    implementation_key: str
    request_schema: str
    response_schema: str
    endpoint_path: str | None = None
    supports_multimodal_input: bool = False
    timeout_seconds: float = 30.0
    extra_headers: dict[str, str] | None = None


class RuntimeProfileServiceMixin:
    """运行时画像解析与序列化能力。"""

    def _resolve_capability_override(
        self,
        *,
        provider: TenantModelProvider,
        capability_type: str,
    ) -> dict[str, Any]:
        """解析能力级覆盖配置，同时兼容旧 capability_base_urls。"""
        capability_override = dict((provider.capability_overrides or {}).get(capability_type) or {})
        legacy_base_url = (provider.capability_base_urls or {}).get(capability_type)
        if legacy_base_url and "base_url" not in capability_override:
            capability_override["base_url"] = legacy_base_url
        return capability_override

    def _resolve_rerank_endpoint_profile(
        self,
        *,
        provider_definition: ModelProviderDefinition,
        provider: TenantModelProvider,
        tenant_model: TenantModel,
        platform_model: PlatformModel,
    ) -> RerankEndpointProfile:
        """解析 rerank 端点画像。"""
        runtime_profile = self._resolve_capability_runtime_profile(
            capability_type="rerank",
            provider_definition=provider_definition,
            provider=provider,
            tenant_model=tenant_model,
            platform_model=platform_model,
        )
        if not runtime_profile.endpoint_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rerank 能力缺少 endpoint_path 配置")

        return RerankEndpointProfile(
            base_url=runtime_profile.base_url,
            endpoint_path=runtime_profile.endpoint_path,
            request_schema=runtime_profile.request_schema,
            response_schema=runtime_profile.response_schema,
            supports_multimodal_input=runtime_profile.supports_multimodal_input,
            timeout_seconds=runtime_profile.timeout_seconds,
            extra_headers=runtime_profile.extra_headers,
        )

    def _resolve_capability_runtime_profile(
        self,
        *,
        capability_type: str,
        provider_definition: ModelProviderDefinition,
        provider: TenantModelProvider,
        tenant_model: TenantModel,
        platform_model: PlatformModel,
    ) -> CapabilityRuntimeProfile:
        """解析统一能力运行时画像，后续能力可复用同一套路由规则。"""
        capability_override = self._resolve_capability_override(provider=provider, capability_type=capability_type)
        runtime_config = tenant_model.model_runtime_config or {}

        adapter_type = (
            tenant_model.adapter_override_type
            or str(runtime_config.get("adapter_type") or "").strip()
            or str(capability_override.get("adapter_type") or "").strip()
            or provider.adapter_override_type
            or self._infer_default_capability_adapter_type(
                capability_type=capability_type,
                provider_definition=provider_definition,
                platform_model=platform_model,
            )
        )
        implementation_key = (
            tenant_model.implementation_key_override
            or str(runtime_config.get("implementation_key") or "").strip()
            or str(capability_override.get("implementation_key") or "").strip()
            or self._infer_default_capability_implementation_key(
                capability_type=capability_type,
                provider_definition=provider_definition,
                platform_model=platform_model,
            )
        )
        request_schema = (
            tenant_model.request_schema_override
            or str(runtime_config.get("request_schema") or "").strip()
            or str(capability_override.get("request_schema") or "").strip()
            or self._infer_default_capability_request_schema(
                capability_type=capability_type,
                provider_definition=provider_definition,
                platform_model=platform_model,
                implementation_key=implementation_key,
            )
        )
        response_schema = (
            str(runtime_config.get("response_schema") or "").strip()
            or str(capability_override.get("response_schema") or "").strip()
            or request_schema
        )
        base_url = (
            str(runtime_config.get("base_url_override") or "").strip()
            or str(capability_override.get("base_url") or "").strip()
            or self._infer_default_capability_base_url(
                capability_type=capability_type,
                provider=provider,
            )
        )
        endpoint_path = (
            tenant_model.endpoint_path_override
            or str(runtime_config.get("endpoint_path_override") or "").strip()
            or str(capability_override.get("endpoint_path") or "").strip()
            or self._infer_default_capability_endpoint_path(
                capability_type=capability_type,
                request_schema=request_schema,
                provider_definition=provider_definition,
                provider=provider,
            )
        )
        supports_multimodal_input = bool(
            runtime_config.get("supports_multimodal_input")
            if "supports_multimodal_input" in runtime_config
            else capability_override.get("supports_multimodal_input")
            if "supports_multimodal_input" in capability_override
            else capability_type in {"vision"}
            or request_schema in {"dashscope_multimodal_rerank_v1", "openai_vision", "openai_responses_vision"}
        )
        timeout_seconds = float(capability_override.get("timeout") or runtime_config.get("timeout") or 30.0)
        extra_headers = capability_override.get("extra_headers")
        if extra_headers is not None and not isinstance(extra_headers, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{capability_type} extra_headers 配置必须是对象",
            )
        if not base_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{capability_type} 能力缺少 base_url 配置",
            )

        return CapabilityRuntimeProfile(
            capability_type=capability_type,
            adapter_type=adapter_type,
            base_url=base_url.rstrip("/"),
            implementation_key=implementation_key,
            request_schema=request_schema,
            response_schema=response_schema,
            endpoint_path=endpoint_path,
            supports_multimodal_input=supports_multimodal_input,
            timeout_seconds=timeout_seconds,
            extra_headers=extra_headers,
        )

    def _infer_default_capability_adapter_type(
        self,
        *,
        capability_type: str,
        provider_definition: ModelProviderDefinition,
        platform_model: PlatformModel,
    ) -> str:
        """按厂商与能力推导默认适配器，优先查统一策略矩阵。"""
        _ = platform_model
        matched_rule = self._match_capability_default_rule(
            capability_type=capability_type,
            provider_code=str(provider_definition.provider_code or "").strip().lower(),
        )
        if matched_rule and matched_rule.adapter_type:
            return matched_rule.adapter_type
        return provider_definition.adapter_type

    def _match_capability_default_rule(
        self,
        *,
        capability_type: str,
        provider_code: str,
        request_schema: str | None = None,
    ) -> CapabilityDefaultRule | None:
        """按顺序匹配能力默认规则，命中首条即返回。"""
        normalized_capability = str(capability_type or "").strip().lower()
        normalized_provider = str(provider_code or "").strip().lower()
        normalized_request_schema = str(request_schema or "").strip().lower() or None

        for rule in CAPABILITY_DEFAULT_RULE_MATRIX:
            if rule.capability_type != normalized_capability:
                continue
            if rule.provider_codes and normalized_provider not in rule.provider_codes:
                continue
            if rule.request_schemas and (normalized_request_schema is None or normalized_request_schema not in rule.request_schemas):
                continue
            if rule.request_schema and rule.request_schema != normalized_request_schema:
                continue
            return rule
        return None

    def _infer_default_rerank_implementation_key(
        self,
        *,
        provider_definition: ModelProviderDefinition,
        platform_model: PlatformModel,
    ) -> str:
        """根据厂商与模型名推导默认 rerank 协议实现键。"""
        raw_name = str(platform_model.raw_model_name or "").strip().lower()
        provider_code = str(provider_definition.provider_code or "").strip().lower()
        if provider_code == "tongyi_qianwen":
            if "vl-rerank" in raw_name:
                return "dashscope_multimodal_rerank_v1"
            if "qwen3-rerank" in raw_name:
                return "openai_rerank"
            if "rerank" in raw_name:
                return "dashscope_text_rerank_v1"
        return "openai_rerank"

    def _infer_default_capability_implementation_key(
        self,
        *,
        capability_type: str,
        provider_definition: ModelProviderDefinition,
        platform_model: PlatformModel,
    ) -> str:
        """推导能力默认实现键，为后续更多能力接入保留统一出口。"""
        if capability_type == "rerank":
            return self._infer_default_rerank_implementation_key(
                provider_definition=provider_definition,
                platform_model=platform_model,
            )
        if capability_type == "embedding":
            return "openai_embedding"
        if capability_type == "asr":
            return "openai_audio_transcription"
        if capability_type == "tts":
            return "openai_audio_speech"
        if capability_type == "vision":
            return "openai_vision"
        if capability_type == "chat":
            return "openai_chat_completions"
        return capability_type

    def _infer_default_capability_request_schema(
        self,
        *,
        capability_type: str,
        provider_definition: ModelProviderDefinition,
        platform_model: PlatformModel,
        implementation_key: str,
    ) -> str:
        """推导能力默认 request schema，优先查统一策略矩阵。"""
        _ = platform_model
        matched_rule = self._match_capability_default_rule(
            capability_type=capability_type,
            provider_code=str(provider_definition.provider_code or "").strip().lower(),
        )
        if matched_rule and matched_rule.request_schema:
            return matched_rule.request_schema
        return implementation_key

    def _infer_default_capability_base_url(
        self,
        *,
        capability_type: str,
        provider: TenantModelProvider,
    ) -> str:
        """推导能力默认 base_url。"""
        base_url = str(provider.base_url or "").strip().rstrip("/")
        if capability_type == "rerank" and "dashscope.aliyuncs.com" in base_url and "/compatible-mode/" in base_url:
            return "https://dashscope.aliyuncs.com"
        return base_url

    def _infer_default_capability_endpoint_path(
        self,
        *,
        capability_type: str,
        request_schema: str,
        provider_definition: ModelProviderDefinition,
        provider: TenantModelProvider,
    ) -> str | None:
        """根据能力与请求协议推导默认 endpoint path。"""
        matched_rule = self._match_capability_default_rule(
            capability_type=capability_type,
            provider_code=str(provider_definition.provider_code or "").strip().lower(),
            request_schema=request_schema,
        )
        if matched_rule and matched_rule.endpoint_path:
            return matched_rule.endpoint_path

        # 兜底：保留历史兼容判断，避免未覆盖规则时出现行为漂移。
        if capability_type == "rerank" and request_schema == "openai_rerank":
            if str(provider.base_url or "").strip().rstrip("/").endswith("/v1"):
                return "/reranks"
            return "/reranks"
        if capability_type == "chat" and str(provider_definition.protocol_type or "").strip().lower() == "ollama":
            return "/api/chat"
        return None

    def _serialize_runtime_profile(
        self,
        *,
        tenant_model: TenantModel,
        provider: TenantModelProvider,
        provider_definition: ModelProviderDefinition,
        platform_model: PlatformModel,
        runtime_profile: CapabilityRuntimeProfile,
    ) -> dict[str, Any]:
        """序列化运行时画像，供前端调试面板直接展示。"""
        effective_url = runtime_profile.base_url
        if runtime_profile.endpoint_path:
            effective_url = f"{runtime_profile.base_url.rstrip('/')}/{runtime_profile.endpoint_path.lstrip('/')}"
        rate_limit_config = self._resolve_effective_rate_limit_config(
            tenant_model=tenant_model,
            capability_type=runtime_profile.capability_type,
        )
        sources = self._resolve_runtime_profile_sources(
            capability_type=runtime_profile.capability_type,
            provider_definition=provider_definition,
            provider=provider,
            tenant_model=tenant_model,
            platform_model=platform_model,
            runtime_profile=runtime_profile,
        )
        return {
            "tenant_model_id": tenant_model.id,
            "provider_name": provider.name,
            "provider_code": provider_definition.provider_code,
            "model_name": platform_model.raw_model_name,
            "display_name": tenant_model.model_alias or platform_model.display_name,
            "capability_type": runtime_profile.capability_type,
            "adapter_type": runtime_profile.adapter_type,
            "implementation_key": runtime_profile.implementation_key,
            "request_schema": runtime_profile.request_schema,
            "response_schema": runtime_profile.response_schema,
            "base_url": runtime_profile.base_url,
            "endpoint_path": runtime_profile.endpoint_path,
            "effective_url": effective_url,
            "supports_multimodal_input": runtime_profile.supports_multimodal_input,
            "timeout_seconds": runtime_profile.timeout_seconds,
            "concurrency_limit": (
                max(1, int(rate_limit_config["concurrency_limit"]))
                if rate_limit_config.get("concurrency_limit") not in (None, "")
                else None
            ),
            "concurrency_mode": str(rate_limit_config.get("wait_mode") or rate_limit_config.get("mode") or "").strip() or None,
            "concurrency_wait_timeout_seconds": (
                max(0, int(rate_limit_config["wait_timeout_seconds"]))
                if rate_limit_config.get("wait_timeout_seconds") not in (None, "")
                else None
            ),
            "extra_headers": runtime_profile.extra_headers or {},
            "sources": sources,
        }

    def _resolve_runtime_profile_sources(
        self,
        *,
        capability_type: str,
        provider_definition: ModelProviderDefinition,
        provider: TenantModelProvider,
        tenant_model: TenantModel,
        platform_model: PlatformModel,
        runtime_profile: CapabilityRuntimeProfile,
    ) -> dict[str, str]:
        """标记关键字段最终来自哪一层配置，方便调试覆盖链。"""
        capability_override = self._resolve_capability_override(provider=provider, capability_type=capability_type)
        runtime_config = tenant_model.model_runtime_config or {}
        sources: dict[str, str] = {}

        def pick_source(
            field_name: str,
            *,
            model_override_value: Any = None,
            runtime_key: str | None = None,
            capability_key: str | None = None,
            provider_value: Any = None,
            fallback_label: str = "默认推导",
        ) -> None:
            runtime_value = runtime_config.get(runtime_key) if runtime_key else None
            capability_value = capability_override.get(capability_key) if capability_key else None
            if model_override_value not in (None, ""):
                sources[field_name] = "模型级覆盖"
            elif runtime_value not in (None, ""):
                sources[field_name] = "模型运行时配置"
            elif capability_value not in (None, ""):
                sources[field_name] = "能力级覆盖"
            elif provider_value not in (None, ""):
                sources[field_name] = "厂商默认配置"
            else:
                sources[field_name] = fallback_label

        pick_source(
            "adapter_type",
            model_override_value=tenant_model.adapter_override_type,
            runtime_key="adapter_type",
            capability_key="adapter_type",
            provider_value=provider.adapter_override_type
            or self._infer_default_capability_adapter_type(
                capability_type=capability_type,
                provider_definition=provider_definition,
                platform_model=platform_model,
            ),
            fallback_label="厂商定义默认值",
        )
        pick_source(
            "implementation_key",
            model_override_value=tenant_model.implementation_key_override,
            runtime_key="implementation_key",
            capability_key="implementation_key",
        )
        pick_source(
            "request_schema",
            model_override_value=tenant_model.request_schema_override,
            runtime_key="request_schema",
            capability_key="request_schema",
        )
        pick_source(
            "response_schema",
            runtime_key="response_schema",
            capability_key="response_schema",
            fallback_label="默认继承 Request Schema",
        )
        pick_source(
            "base_url",
            runtime_key="base_url_override",
            capability_key="base_url",
            provider_value=provider.base_url,
        )
        pick_source(
            "endpoint_path",
            model_override_value=tenant_model.endpoint_path_override,
            runtime_key="endpoint_path_override",
            capability_key="endpoint_path",
        )
        if self._resolve_effective_rate_limit_config(
            tenant_model=tenant_model,
            capability_type=capability_type,
        ):
            sources["concurrency_limit"] = "模型级限流配置"
        else:
            sources["concurrency_limit"] = "未配置（仅全局并发）"
        if "supports_multimodal_input" in runtime_config:
            sources["supports_multimodal_input"] = "模型运行时配置"
        elif "supports_multimodal_input" in capability_override:
            sources["supports_multimodal_input"] = "能力级覆盖"
        elif capability_type in {"vision"} or runtime_profile.request_schema in {
            "dashscope_multimodal_rerank_v1",
            "openai_vision",
            "openai_responses_vision",
        }:
            sources["supports_multimodal_input"] = "默认推导"
        else:
            sources["supports_multimodal_input"] = "默认关闭"

        return sources
