"""
模型平台设置中心服务。
"""

import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_service import BaseService
from core.model_platform.constants import CAPABILITY_TYPES
from models.model_adapter_binding import ModelAdapterBinding
from models.model_provider_definition import ModelProviderDefinition
from models.platform_model import PlatformModel
from models.tenant_default_model import TenantDefaultModel
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider
from models.tenant_model_provider_credential import TenantModelProviderCredential
from models.user import User

TENANT_RESOURCE_SCOPE = "tenant"


class ModelProviderDefinitionService(BaseService):  # type: ignore[misc]
    """模型厂商定义服务。"""

    def __init__(self, db: AsyncSession, model: type[ModelProviderDefinition] | None = None) -> None:
        super().__init__(model=model or ModelProviderDefinition, db=db, resource_name="model_provider_definition")


class TenantModelProviderService(BaseService):  # type: ignore[misc]
    """租户模型厂商配置服务。"""

    def __init__(self, db: AsyncSession, model: type[TenantModelProvider] | None = None) -> None:
        super().__init__(model=model or TenantModelProvider, db=db, resource_name="tenant_model_provider")


class TenantModelProviderCredentialService(BaseService):  # type: ignore[misc]
    """租户模型厂商凭证服务。"""

    def __init__(self, db: AsyncSession, model: type[TenantModelProviderCredential] | None = None) -> None:
        super().__init__(model=model or TenantModelProviderCredential, db=db, resource_name="tenant_model_provider_credential")


class PlatformModelService(BaseService):  # type: ignore[misc]
    """平台模型目录服务。"""

    def __init__(self, db: AsyncSession, model: type[PlatformModel] | None = None) -> None:
        super().__init__(model=model or PlatformModel, db=db, resource_name="platform_model")


class TenantModelService(BaseService):  # type: ignore[misc]
    """租户模型映射服务。"""

    def __init__(self, db: AsyncSession, model: type[TenantModel] | None = None) -> None:
        super().__init__(model=model or TenantModel, db=db, resource_name="tenant_model")


class TenantDefaultModelService(BaseService):  # type: ignore[misc]
    """租户默认模型服务。"""

    def __init__(self, db: AsyncSession, model: type[TenantDefaultModel] | None = None) -> None:
        super().__init__(model=model or TenantDefaultModel, db=db, resource_name="tenant_default_model")


class ModelAdapterBindingService(BaseService):  # type: ignore[misc]
    """适配器绑定服务。"""

    def __init__(self, db: AsyncSession, model: type[ModelAdapterBinding] | None = None) -> None:
        super().__init__(model=model or ModelAdapterBinding, db=db, resource_name="model_adapter_binding")


class ModelSettingsService:
    """模型设置页专用聚合服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _as_positive_int(value: Any) -> int | None:
        """把 JSON 配置里的数字安全归一为正整数，避免前端展示脏值。"""
        if value is None or value == "":
            return None
        try:
            parsed_value = int(value)
        except (TypeError, ValueError):
            return None
        return parsed_value if parsed_value > 0 else None

    def _resolve_runtime_supported_capabilities(
        self,
        *,
        provider_definition: ModelProviderDefinition,
    ) -> list[str]:
        """按当前平台实际运行能力收敛厂商可调用能力，避免前端声明和后端执行脱节。"""
        declared_capabilities = [
            capability
            for capability in list(provider_definition.supported_capabilities or [])
            if capability in CAPABILITY_TYPES
        ]
        protocol_type = str(provider_definition.protocol_type or "").strip().lower()

        protocol_capability_map: dict[str, set[str]] = {
            "openai": {"chat", "vision", "embedding", "rerank", "asr", "tts"},
            "openai_compatible": {"chat", "vision", "embedding", "rerank", "asr", "tts"},
            "azure_openai": {"chat", "vision", "embedding", "rerank", "asr", "tts"},
            "ollama": {"chat", "vision", "embedding"},
            "vllm": {"chat", "vision", "embedding"},
            "anthropic_native": {"chat", "vision"},
            "gemini_native": {"chat", "vision"},
            "bedrock": {"chat", "vision"},
        }
        runtime_capabilities = protocol_capability_map.get(protocol_type, set())
        return [capability for capability in declared_capabilities if capability in runtime_capabilities]

    async def get_overview(self, current_user: User) -> dict[str, Any]:
        """聚合模型设置页所需的厂商、模型和默认模型数据。"""
        definitions_result = await self.db.execute(
            select(ModelProviderDefinition)
            .where(ModelProviderDefinition.is_enabled == True)  # noqa: E712
            .order_by(ModelProviderDefinition.sort_order.asc(), ModelProviderDefinition.display_name.asc())
        )
        definitions = list(definitions_result.scalars().all())

        providers_result = await self.db.execute(
            select(TenantModelProvider)
            .where(
                TenantModelProvider.tenant_id == current_user.tenant_id,
                TenantModelProvider.resource_scope == TENANT_RESOURCE_SCOPE,
            )
            .order_by(TenantModelProvider.updated_at.desc(), TenantModelProvider.created_at.desc())
        )
        tenant_providers = list(providers_result.scalars().all())

        provider_ids = [item.id for item in tenant_providers]
        credentials_by_provider: dict[UUID, TenantModelProviderCredential] = {}
        if provider_ids:
            credentials_result = await self.db.execute(
                select(TenantModelProviderCredential)
                .where(TenantModelProviderCredential.tenant_provider_id.in_(provider_ids))
                .order_by(
                    TenantModelProviderCredential.tenant_provider_id.asc(),
                    TenantModelProviderCredential.is_primary.desc(),
                    TenantModelProviderCredential.created_at.asc(),
                )
            )
            for credential in credentials_result.scalars().all():
                credentials_by_provider.setdefault(credential.tenant_provider_id, credential)

        provider_by_definition: dict[UUID, TenantModelProvider] = {}
        for provider in tenant_providers:
            provider_by_definition.setdefault(provider.provider_definition_id, provider)

        tenant_models_result = await self.db.execute(
            select(TenantModel).where(
                TenantModel.tenant_id == current_user.tenant_id,
                TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
            )
        )
        tenant_models = list(tenant_models_result.scalars().all())

        platform_model_ids = [item.platform_model_id for item in tenant_models]
        platform_models_by_id: dict[UUID, PlatformModel] = {}
        if platform_model_ids:
            platform_models_result = await self.db.execute(
                select(PlatformModel).where(PlatformModel.id.in_(platform_model_ids))
            )
            platform_models_by_id = {item.id: item for item in platform_models_result.scalars().all()}

        models_by_provider: dict[UUID, list[dict[str, Any]]] = {}
        for tenant_model in tenant_models:
            platform_model = platform_models_by_id.get(tenant_model.platform_model_id)
            if platform_model is None:
                continue
            runtime_config = tenant_model.model_runtime_config or {}
            model_group = (
                tenant_model.group_key
                or platform_model.model_family
                or str((platform_model.metadata_info or {}).get("group_name", "")).strip()
                or None
            )
            # 租户级运行时配置优先，用于私有化部署中同名模型上下文窗口不一致的场景。
            context_window = self._as_positive_int(runtime_config.get("context_window")) or platform_model.context_window
            max_output_tokens = self._as_positive_int(runtime_config.get("max_output_tokens")) or platform_model.max_output_tokens
            embedding_dimension = self._as_positive_int(runtime_config.get("embedding_dimension")) or platform_model.embedding_dimension
            models_by_provider.setdefault(tenant_model.tenant_provider_id, []).append(
                {
                    "tenant_model_id": tenant_model.id,
                    "platform_model_id": platform_model.id,
                    "display_name": tenant_model.model_alias or platform_model.display_name,
                    "raw_model_name": platform_model.raw_model_name,
                    "source_type": tenant_model.source_type or platform_model.source_type,
                    "model_type": tenant_model.model_type,
                    "capabilities": tenant_model.capabilities or platform_model.capabilities,
                    "group_name": model_group,
                    "context_window": context_window,
                    "max_output_tokens": max_output_tokens,
                    "embedding_dimension": embedding_dimension,
                    "supports_stream": platform_model.supports_stream,
                    "supports_tools": platform_model.supports_tools,
                    "supports_structured_output": platform_model.supports_structured_output,
                    "supports_vision_input": platform_model.supports_vision_input,
                    "supports_audio_input": platform_model.supports_audio_input,
                    "supports_audio_output": platform_model.supports_audio_output,
                    "model_family": platform_model.model_family,
                    "release_channel": platform_model.release_channel,
                    "model_runtime_config": runtime_config,
                    "metadata_info": platform_model.metadata_info or {},
                    "rate_limit_config": tenant_model.rate_limit_config or {},
                    "is_enabled": tenant_model.is_enabled,
                    "is_visible_in_ui": tenant_model.is_visible_in_ui,
                }
            )

        defaults_result = await self.db.execute(
            select(TenantDefaultModel).where(
                TenantDefaultModel.tenant_id == current_user.tenant_id,
                TenantDefaultModel.resource_scope == TENANT_RESOURCE_SCOPE,
                TenantDefaultModel.is_enabled == True,  # noqa: E712
            )
        )
        default_models = list(defaults_result.scalars().all())

        provider_items: list[dict[str, Any]] = []
        for definition in definitions:
            tenant_provider = provider_by_definition.get(definition.id)
            provider_credential: TenantModelProviderCredential | None = credentials_by_provider.get(tenant_provider.id) if tenant_provider is not None else None
            metadata_info = definition.metadata_info or {}
            default_base_url = str(metadata_info.get("default_base_url", "")).strip()
            default_endpoint_type = str(metadata_info.get("default_endpoint_type", "official")).strip() or "official"
            is_base_url_editable = bool(metadata_info.get("base_url_editable", not default_base_url))
            credential_payload = provider_credential.encrypted_config if provider_credential is not None else {}
            has_primary_credential = bool(credential_payload)
            is_local_endpoint = (tenant_provider.endpoint_type if tenant_provider else default_endpoint_type) == "local"
            has_provider_endpoint = bool(
                tenant_provider is not None
                and str(tenant_provider.base_url or default_base_url or "").strip()
            )

            provider_items.append(
                {
                    "provider_definition_id": definition.id,
                    "tenant_provider_id": tenant_provider.id if tenant_provider is not None else None,
                    "provider_code": definition.provider_code,
                    "display_name": definition.display_name,
                    "is_builtin": definition.is_builtin,
                    "protocol_type": definition.protocol_type,
                    "endpoint_type": tenant_provider.endpoint_type if tenant_provider is not None else default_endpoint_type,
                    "base_url": tenant_provider.base_url if tenant_provider is not None else default_base_url,
                    "is_base_url_editable": is_base_url_editable,
                    "is_enabled": tenant_provider.is_enabled if tenant_provider is not None else False,
                    "is_visible_in_ui": tenant_provider.is_visible_in_ui if tenant_provider is not None else False,
                    "is_configured": bool(tenant_provider is not None and (has_provider_endpoint or has_primary_credential or is_local_endpoint)),
                    "supports_model_discovery": definition.supports_model_discovery,
                    "supported_capabilities": definition.supported_capabilities,
                    "runtime_supported_capabilities": self._resolve_runtime_supported_capabilities(
                        provider_definition=definition,
                    ),
                    "capability_base_urls": tenant_provider.capability_base_urls if tenant_provider is not None else {},
                    "capability_overrides": tenant_provider.capability_overrides if tenant_provider is not None else {},
                    "icon_url": definition.icon_url,
                    "sort_order": definition.sort_order,
                    "last_sync_at": tenant_provider.last_sync_at if tenant_provider is not None else None,
                    "sync_status": tenant_provider.sync_status if tenant_provider is not None else None,
                    "sync_error": tenant_provider.sync_error if tenant_provider is not None else None,
                    "has_primary_credential": has_primary_credential,
                    "credential_masked_summary": provider_credential.masked_summary if provider_credential is not None else None,
                    "models": models_by_provider.get(tenant_provider.id, []) if tenant_provider is not None else [],
                }
            )

        return {
            "providers": provider_items,
            "default_models": [
                {
                    "capability_type": item.capability_type,
                    "tenant_model_id": item.tenant_model_id,
                }
                for item in default_models
            ],
        }

    async def upsert_provider_settings(self, payload: dict[str, Any], current_user: User) -> dict[str, Any]:
        """创建或更新租户厂商实例与主凭证。"""
        provider_definition_id = payload["provider_definition_id"]
        definition_result = await self.db.execute(
            select(ModelProviderDefinition).where(
                ModelProviderDefinition.id == provider_definition_id,
                ModelProviderDefinition.is_enabled == True,  # noqa: E712
            )
        )
        definition = definition_result.scalar_one_or_none()
        if definition is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厂商定义不存在")

        tenant_provider: TenantModelProvider | None = None
        if payload.get("tenant_provider_id"):
            provider_result = await self.db.execute(
                select(TenantModelProvider).where(
                    TenantModelProvider.id == payload["tenant_provider_id"],
                    TenantModelProvider.tenant_id == current_user.tenant_id,
                    TenantModelProvider.resource_scope == TENANT_RESOURCE_SCOPE,
                )
            )
            tenant_provider = provider_result.scalar_one_or_none()
        else:
            provider_result = await self.db.execute(
                select(TenantModelProvider)
                .where(
                    TenantModelProvider.tenant_id == current_user.tenant_id,
                    TenantModelProvider.provider_definition_id == provider_definition_id,
                    TenantModelProvider.resource_scope == TENANT_RESOURCE_SCOPE,
                )
                .order_by(TenantModelProvider.updated_at.desc(), TenantModelProvider.created_at.desc())
            )
            tenant_provider = provider_result.scalars().first()

        metadata_info = definition.metadata_info or {}
        is_base_url_editable = bool(metadata_info.get("base_url_editable", not metadata_info.get("default_base_url")))
        if is_base_url_editable:
            base_url = str(payload.get("base_url") or metadata_info.get("default_base_url") or "").strip()
        else:
            base_url = str(metadata_info.get("default_base_url") or "").strip()
        endpoint_type = str(payload.get("endpoint_type") or metadata_info.get("default_endpoint_type") or "official").strip()
        provider_name = str(payload.get("name") or definition.display_name).strip()
        if not base_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先填写厂商接入地址")

        capability_base_urls = payload.get("capability_base_urls", {})
        capability_overrides = payload.get("capability_overrides", {})
        if tenant_provider is None:
            tenant_provider = TenantModelProvider(
                tenant_id=current_user.tenant_id,
                resource_scope=TENANT_RESOURCE_SCOPE,
                owner_user_id=None,
                provider_definition_id=definition.id,
                name=provider_name,
                endpoint_type=endpoint_type,
                base_url=base_url,
                api_version=payload.get("api_version"),
                region=payload.get("region"),
                capability_base_urls=capability_base_urls,
                capability_overrides=capability_overrides,
                is_enabled=bool(payload.get("is_enabled", True)),
                is_visible_in_ui=bool(payload.get("is_visible_in_ui", True)),
                created_by_id=current_user.id,
                created_by_name=current_user.nickname or current_user.username or "System",
                updated_by_id=current_user.id,
                updated_by_name=current_user.nickname or current_user.username or "System",
            )
            self.db.add(tenant_provider)
            await self.db.flush()
        else:
            tenant_provider.name = provider_name
            tenant_provider.endpoint_type = endpoint_type
            tenant_provider.base_url = base_url
            tenant_provider.api_version = payload.get("api_version")
            tenant_provider.region = payload.get("region")
            tenant_provider.capability_base_urls = capability_base_urls
            tenant_provider.capability_overrides = capability_overrides
            tenant_provider.is_enabled = bool(payload.get("is_enabled", tenant_provider.is_enabled))
            tenant_provider.is_visible_in_ui = bool(payload.get("is_visible_in_ui", tenant_provider.is_visible_in_ui))
            tenant_provider.updated_by_id = current_user.id
            tenant_provider.updated_by_name = current_user.nickname or current_user.username or "System"

        api_key = payload.get("api_key")
        if api_key is not None:
            credential_result = await self.db.execute(
                select(TenantModelProviderCredential)
                .where(
                    TenantModelProviderCredential.tenant_provider_id == tenant_provider.id,
                    TenantModelProviderCredential.is_primary == True,  # noqa: E712
                )
                .order_by(TenantModelProviderCredential.created_at.asc())
            )
            credential: TenantModelProviderCredential | None = credential_result.scalars().first()
            if credential is None:
                credential = TenantModelProviderCredential(
                    tenant_id=current_user.tenant_id,
                    tenant_provider_id=tenant_provider.id,
                    owner_user_id=None,
                    credential_name="default",
                    credential_type="api_key",
                    encrypted_config={"api_key": api_key},
                    masked_summary=self._build_masked_summary(api_key),
                    is_primary=True,
                    is_enabled=True,
                    created_by_id=current_user.id,
                    created_by_name=current_user.nickname or current_user.username or "System",
                    updated_by_id=current_user.id,
                    updated_by_name=current_user.nickname or current_user.username or "System",
                )
                self.db.add(credential)
            else:
                credential.encrypted_config = {"api_key": api_key}
                credential.masked_summary = self._build_masked_summary(api_key)
                credential.is_enabled = True
                credential.updated_by_id = current_user.id
                credential.updated_by_name = current_user.nickname or current_user.username or "System"

        await self.db.commit()
        await self.db.refresh(tenant_provider)
        return {
            "success": True,
            "tenant_provider_id": tenant_provider.id,
            "detail": "厂商配置已保存",
        }

    async def upsert_default_model(
        self,
        *,
        current_user: User,
        capability_type: str,
        tenant_model_id: UUID | None,
    ) -> dict[str, Any]:
        """创建、更新或删除默认模型。"""
        default_result = await self.db.execute(
            select(TenantDefaultModel).where(
                TenantDefaultModel.tenant_id == current_user.tenant_id,
                TenantDefaultModel.resource_scope == TENANT_RESOURCE_SCOPE,
                TenantDefaultModel.capability_type == capability_type,
            )
        )
        default_binding = default_result.scalar_one_or_none()

        if tenant_model_id is None:
            if default_binding is not None:
                await self.db.delete(default_binding)
                await self.db.commit()
            return {
                "success": True,
                "capability_type": capability_type,
                "tenant_model_id": None,
                "detail": "默认模型已清空",
            }

        tenant_model_result = await self.db.execute(
            select(TenantModel).where(
                TenantModel.id == tenant_model_id,
                TenantModel.tenant_id == current_user.tenant_id,
                TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
                TenantModel.is_enabled == True,  # noqa: E712
            )
        )
        tenant_model = tenant_model_result.scalar_one_or_none()
        if tenant_model is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租户模型不存在或未启用")

        platform_model_result = await self.db.execute(
            select(PlatformModel).where(PlatformModel.id == tenant_model.platform_model_id)
        )
        platform_model = platform_model_result.scalar_one_or_none()
        if platform_model is None or capability_type not in platform_model.capabilities:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该模型不支持当前默认能力类型")

        if default_binding is None:
            default_binding = TenantDefaultModel(
                tenant_id=current_user.tenant_id,
                resource_scope=TENANT_RESOURCE_SCOPE,
                owner_user_id=None,
                capability_type=capability_type,
                tenant_model_id=tenant_model_id,
                is_enabled=True,
                created_by_id=current_user.id,
                created_by_name=current_user.nickname or current_user.username or "System",
                updated_by_id=current_user.id,
                updated_by_name=current_user.nickname or current_user.username or "System",
            )
            self.db.add(default_binding)
        else:
            default_binding.tenant_model_id = tenant_model_id
            default_binding.is_enabled = True
            default_binding.updated_by_id = current_user.id
            default_binding.updated_by_name = current_user.nickname or current_user.username or "System"

        await self.db.commit()
        return {
            "success": True,
            "capability_type": capability_type,
            "tenant_model_id": tenant_model_id,
            "detail": "默认模型已保存",
        }

    @staticmethod
    def _build_masked_summary(api_key: str | None) -> str | None:
        """构造前端展示用的脱敏凭证摘要。"""
        normalized = str(api_key or "").strip()
        if not normalized:
            return None
        if len(normalized) <= 8:
            return f"{normalized[:2]}***{normalized[-2:]}"
        return f"{normalized[:4]}***{normalized[-4:]}"

    async def create_custom_provider(
        self,
        *,
        current_user: User,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """创建自定义厂商定义与当前租户实例。"""
        provider_code = self._normalize_provider_code(
            payload.get("provider_code") or payload.get("display_name") or "custom-provider"
        )
        existing_result = await self.db.execute(
            select(ModelProviderDefinition).where(ModelProviderDefinition.provider_code == provider_code)
        )
        if existing_result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="厂商编码已存在，请更换后重试")

        protocol_type = str(payload["protocol_type"]).strip()
        adapter_type = self._resolve_adapter_type(protocol_type)
        display_name = str(payload["display_name"]).strip()
        endpoint_type = str(payload["endpoint_type"]).strip()
        supported_capabilities = list(dict.fromkeys(payload.get("supported_capabilities") or ["chat"]))
        base_url = str(payload["base_url"]).strip()
        api_key = str(payload.get("api_key") or "").strip()

        definition = ModelProviderDefinition(
            provider_code=provider_code,
            display_name=display_name,
            protocol_type=protocol_type,
            adapter_type=adapter_type,
            supports_model_discovery=protocol_type in {"openai", "openai_compatible", "azure_openai", "ollama", "vllm"},
            supported_capabilities=supported_capabilities,
            sort_order=1000,
            is_builtin=False,
            is_enabled=True,
            description=payload.get("description"),
            metadata_info={
                "default_base_url": base_url,
                "default_endpoint_type": endpoint_type,
                "base_url_editable": True,
                "created_from_settings": True,
            },
        )
        self.db.add(definition)
        await self.db.flush()

        tenant_provider = TenantModelProvider(
            tenant_id=current_user.tenant_id,
            resource_scope=TENANT_RESOURCE_SCOPE,
            owner_user_id=None,
            provider_definition_id=definition.id,
            name=display_name,
            description=payload.get("description"),
            endpoint_type=endpoint_type,
            base_url=base_url,
            is_enabled=bool(payload.get("is_enabled", True)),
            is_visible_in_ui=bool(payload.get("is_visible_in_ui", True)),
            created_by_id=current_user.id,
            created_by_name=current_user.nickname or current_user.username or "System",
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname or current_user.username or "System",
        )
        self.db.add(tenant_provider)
        await self.db.flush()

        if api_key:
            credential = TenantModelProviderCredential(
                tenant_id=current_user.tenant_id,
                tenant_provider_id=tenant_provider.id,
                owner_user_id=None,
                credential_name="default",
                credential_type="api_key",
                encrypted_config={"api_key": api_key},
                masked_summary=self._build_masked_summary(api_key),
                is_primary=True,
                is_enabled=True,
                created_by_id=current_user.id,
                created_by_name=current_user.nickname or current_user.username or "System",
                updated_by_id=current_user.id,
                updated_by_name=current_user.nickname or current_user.username or "System",
            )
            self.db.add(credential)

        await self.db.commit()
        return {
            "success": True,
            "provider_definition_id": definition.id,
            "tenant_provider_id": tenant_provider.id,
            "provider_code": provider_code,
            "detail": "自定义厂商已创建",
        }

    async def archive_custom_provider(self, *, current_user: User, provider_definition_id: UUID) -> dict[str, Any]:
        """归档自定义厂商及当前租户实例。"""
        definition_result = await self.db.execute(
            select(ModelProviderDefinition).where(ModelProviderDefinition.id == provider_definition_id)
        )
        definition = definition_result.scalar_one_or_none()
        if definition is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厂商定义不存在")
        if definition.is_builtin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="内置厂商不支持归档")

        definition.is_enabled = False
        metadata_info = dict(definition.metadata_info or {})
        metadata_info["archived"] = True
        definition.metadata_info = metadata_info

        providers_result = await self.db.execute(
            select(TenantModelProvider).where(
                TenantModelProvider.tenant_id == current_user.tenant_id,
                TenantModelProvider.provider_definition_id == provider_definition_id,
                TenantModelProvider.resource_scope == TENANT_RESOURCE_SCOPE,
            )
        )
        tenant_providers = list(providers_result.scalars().all())
        provider_ids = [item.id for item in tenant_providers]
        for tenant_provider in tenant_providers:
            tenant_provider.is_enabled = False
            tenant_provider.is_visible_in_ui = False
            tenant_provider.updated_by_id = current_user.id
            tenant_provider.updated_by_name = current_user.nickname or current_user.username or "System"

        if provider_ids:
            tenant_models_result = await self.db.execute(
                select(TenantModel).where(
                    TenantModel.tenant_id == current_user.tenant_id,
                    TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
                    TenantModel.tenant_provider_id.in_(provider_ids),
                )
            )
            tenant_models = list(tenant_models_result.scalars().all())
            model_ids = {item.id for item in tenant_models}
            for tenant_model in tenant_models:
                tenant_model.is_enabled = False
                tenant_model.is_visible_in_ui = False
                tenant_model.updated_by_id = current_user.id
                tenant_model.updated_by_name = current_user.nickname or current_user.username or "System"

            if model_ids:
                defaults_result = await self.db.execute(
                    select(TenantDefaultModel).where(
                        TenantDefaultModel.tenant_id == current_user.tenant_id,
                        TenantDefaultModel.resource_scope == TENANT_RESOURCE_SCOPE,
                        TenantDefaultModel.tenant_model_id.in_(model_ids),
                    )
                )
                for default_binding in defaults_result.scalars().all():
                    await self.db.delete(default_binding)

        await self.db.commit()
        return {
            "success": True,
            "provider_definition_id": provider_definition_id,
            "detail": "自定义厂商已归档",
        }

    async def create_manual_model(self, *, current_user: User, payload: dict[str, Any]) -> dict[str, Any]:
        """
        手动添加单个模型。

        支持用户手动指定模型名称、类型和能力，用于：
        - 厂商不支持 /models 接口的情况
        - 用户需要添加自定义模型的情况
        """
        tenant_provider_id = payload["tenant_provider_id"]
        model_key = payload["model_key"]
        raw_model_name = payload["raw_model_name"]
        display_name = payload["display_name"]
        model_type = payload["model_type"]
        context_window = payload.get("context_window")
        max_output_tokens = payload.get("max_output_tokens")
        embedding_dimension = payload.get("embedding_dimension")
        capabilities = payload.get("capabilities", [model_type])
        group_name = payload.get("group_name")
        adapter_override_type = payload.get("adapter_override_type")
        implementation_key_override = payload.get("implementation_key_override")
        request_schema_override = payload.get("request_schema_override")
        endpoint_path_override = payload.get("endpoint_path_override")
        model_runtime_config = dict(payload.get("model_runtime_config") or {})
        rate_limit_config = payload.get("rate_limit_config", {})
        is_enabled = payload.get("is_enabled", True)
        is_visible_in_ui = payload.get("is_visible_in_ui", True)

        # 验证 tenant_provider 存在且属于当前租户
        provider_result = await self.db.execute(
            select(TenantModelProvider).where(
                TenantModelProvider.id == tenant_provider_id,
                TenantModelProvider.tenant_id == current_user.tenant_id,
                TenantModelProvider.resource_scope == TENANT_RESOURCE_SCOPE,
            )
        )
        tenant_provider = provider_result.scalar_one_or_none()
        if tenant_provider is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厂商实例不存在")

        # 获取 provider_definition
        definition_result = await self.db.execute(
            select(ModelProviderDefinition).where(
                ModelProviderDefinition.id == tenant_provider.provider_definition_id,
                ModelProviderDefinition.is_enabled == True,  # noqa: E712
            )
        )
        provider_definition = definition_result.scalar_one_or_none()
        if provider_definition is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厂商定义不存在")

        # 检查模型是否已存在
        existing_platform_model_result = await self.db.execute(
            select(PlatformModel).where(PlatformModel.model_key == model_key)
        )
        platform_model = existing_platform_model_result.scalar_one_or_none()

        if platform_model is None:
            # 创建平台模型
            platform_model = PlatformModel(
                provider_definition_id=provider_definition.id,
                model_key=model_key,
                raw_model_name=raw_model_name,
                display_name=display_name,
                model_type=model_type,
                capabilities=capabilities,
                context_window=context_window,
                max_output_tokens=max_output_tokens,
                embedding_dimension=embedding_dimension if model_type == "embedding" else None,
                source_type="manual",
                is_builtin=False,
                is_enabled=True,
                supports_stream=(model_type == "chat"),
                supports_vision_input="vision" in capabilities,
                supports_audio_input=model_type == "asr",
                supports_audio_output=model_type == "tts",
            )
            self.db.add(platform_model)
            await self.db.flush()
        else:
            # 同名模型在不同私有化网关中规格可能不同，冲突时写入租户级运行时覆盖。
            if context_window is not None:
                if platform_model.context_window is None:
                    platform_model.context_window = int(context_window)
                elif int(platform_model.context_window) != int(context_window):
                    model_runtime_config["context_window"] = int(context_window)
            if max_output_tokens is not None:
                if platform_model.max_output_tokens is None:
                    platform_model.max_output_tokens = int(max_output_tokens)
                elif int(platform_model.max_output_tokens) != int(max_output_tokens):
                    model_runtime_config["max_output_tokens"] = int(max_output_tokens)
            if (
                model_type == "embedding"
                and embedding_dimension is not None
                and platform_model.embedding_dimension is not None
                and int(platform_model.embedding_dimension) != int(embedding_dimension)
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"模型 {display_name} 已配置 embedding_dimension={platform_model.embedding_dimension}，"
                        f"与请求值 {embedding_dimension} 不一致"
                    ),
                )
            if model_type == "embedding" and embedding_dimension is not None and platform_model.embedding_dimension is None:
                platform_model.embedding_dimension = int(embedding_dimension)

        # 检查租户模型绑定是否已存在
        existing_tenant_model_result = await self.db.execute(
            select(TenantModel).where(
                TenantModel.tenant_id == current_user.tenant_id,
                TenantModel.tenant_provider_id == tenant_provider_id,
                TenantModel.platform_model_id == platform_model.id,
                TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
            )
        )
        existing_tenant_model = existing_tenant_model_result.scalar_one_or_none()
        if existing_tenant_model is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"模型 {display_name} 已存在，无需重复添加"
            )

        # 创建租户模型绑定
        tenant_model = TenantModel(
            tenant_id=current_user.tenant_id,
            resource_scope=TENANT_RESOURCE_SCOPE,
            owner_user_id=None,
            tenant_provider_id=tenant_provider_id,
            platform_model_id=platform_model.id,
            model_alias=display_name,
            model_type=model_type,
            capabilities=capabilities,
            source_type="manual",
            group_key=group_name,
            is_enabled=is_enabled,
            is_visible_in_ui=is_visible_in_ui,
            adapter_override_type=adapter_override_type,
            implementation_key_override=implementation_key_override,
            request_schema_override=request_schema_override,
            endpoint_path_override=endpoint_path_override,
            model_runtime_config=model_runtime_config,
            rate_limit_config=rate_limit_config,
            created_by_id=current_user.id,
            created_by_name=current_user.nickname or current_user.username or "System",
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname or current_user.username or "System",
        )
        self.db.add(tenant_model)
        await self.db.commit()

        return {
            "success": True,
            "tenant_model_id": tenant_model.id,
            "platform_model_id": platform_model.id,
            "detail": f"模型 {display_name} 已添加",
        }

    async def batch_update_models(
        self,
        *,
        current_user: User,
        model_ids: list[UUID],
        is_enabled: bool | None = None,
        is_visible_in_ui: bool | None = None,
    ) -> dict[str, Any]:
        """批量更新租户模型状态。"""
        if is_enabled is None and is_visible_in_ui is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少需要提供一个可更新字段")

        unique_model_ids = list(dict.fromkeys(model_ids))
        if not unique_model_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模型 ID 列表不能为空")

        models_result = await self.db.execute(
            select(TenantModel).where(
                TenantModel.tenant_id == current_user.tenant_id,
                TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
                TenantModel.id.in_(unique_model_ids),
            )
        )
        tenant_models = list(models_result.scalars().all())
        if not tenant_models:
            return {
                "success": True,
                "updated_count": 0,
                "detail": "未匹配到可更新的模型",
            }

        updater_name = current_user.nickname or current_user.username or "System"
        for tenant_model in tenant_models:
            if is_enabled is not None:
                tenant_model.is_enabled = is_enabled
            if is_visible_in_ui is not None:
                tenant_model.is_visible_in_ui = is_visible_in_ui
            tenant_model.updated_by_id = current_user.id
            tenant_model.updated_by_name = updater_name

        await self.db.commit()
        return {
            "success": True,
            "updated_count": len(tenant_models),
            "detail": f"已批量更新 {len(tenant_models)} 个模型",
        }

    def _normalize_provider_code(self, value: str) -> str:
        """规范化自定义厂商编码。"""
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
        return normalized[:64] or "custom_provider"

    def _resolve_adapter_type(self, protocol_type: str) -> str:
        """按协议类型推导默认适配器。"""
        if protocol_type == "custom":
            return "custom"
        if protocol_type in {"openai", "openai_compatible", "azure_openai"}:
            return "litellm"
        return "litellm"
