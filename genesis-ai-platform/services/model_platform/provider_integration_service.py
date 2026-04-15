"""
模型平台厂商接入与模型发现服务。

职责：
1. 厂商连通性测试；
2. 厂商模型发现与同步；
3. 提供调用层复用的 provider/credential 加载方法。
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.model_provider_definition import ModelProviderDefinition
from models.model_sync_record import ModelSyncRecord
from models.platform_model import PlatformModel
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider
from models.tenant_model_provider_credential import TenantModelProviderCredential
from models.user import User

logger = logging.getLogger(__name__)

# 当前阶段平台运行时只启用租户级模型资源。
TENANT_RESOURCE_SCOPE = "tenant"


class ModelProviderIntegrationService:
    """
    provider 连通性测试与模型同步服务。

    当前第一阶段先覆盖三类协议：
    - OpenAI 兼容接口
    - vLLM（按 OpenAI 兼容处理）
    - Ollama
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def test_connection(self, tenant_provider_id: UUID, current_user: User) -> dict[str, Any]:
        """测试指定 provider 的连通性并返回模型样例。"""
        provider, provider_definition = await self._load_provider_bundle(tenant_provider_id, current_user.tenant_id)
        credential = await self._load_primary_credential(tenant_provider_id)
        discovered_models = await self._discover_models(provider, provider_definition, credential)

        return {
            "success": True,
            "provider_id": provider.id,
            "provider_name": provider.name,
            "protocol_type": provider_definition.protocol_type,
            "base_url": provider.base_url,
            "detail": "连接成功",
            "discovered_model_count": len(discovered_models),
            "sample_models": [model["raw_model_name"] for model in discovered_models[:10]],
        }

    async def sync_models(
        self,
        tenant_provider_id: UUID,
        current_user: User,
        *,
        auto_enable_models: bool = True,
        overwrite_existing_display_name: bool = False,
    ) -> dict[str, Any]:
        """同步 provider 模型目录，并可选自动创建租户模型绑定。"""
        provider, provider_definition = await self._load_provider_bundle(tenant_provider_id, current_user.tenant_id)
        credential = await self._load_primary_credential(tenant_provider_id)
        sync_record = ModelSyncRecord(
            tenant_provider_id=tenant_provider_id,
            sync_type="manual",
            status="running",
        )
        self.db.add(sync_record)
        await self.db.flush()

        try:
            discovered_models = await self._discover_models(provider, provider_definition, credential)
            added_count = 0
            updated_count = 0
            enabled_binding_count = 0

            for item in discovered_models:
                platform_model = await self._get_platform_model_by_key(item["model_key"])
                if platform_model is None:
                    platform_model = PlatformModel(
                        provider_definition_id=provider_definition.id,
                        model_key=item["model_key"],
                        raw_model_name=item["raw_model_name"],
                        display_name=item["display_name"],
                        model_type=item["model_type"],
                        capabilities=item["capabilities"],
                        context_window=item.get("context_window"),
                        max_output_tokens=item.get("max_output_tokens"),
                        embedding_dimension=item.get("embedding_dimension"),
                        supports_stream=item["supports_stream"],
                        supports_tools=item.get("supports_tools", False),
                        supports_structured_output=item.get("supports_structured_output", False),
                        supports_vision_input=item.get("supports_vision_input", False),
                        supports_audio_input=item.get("supports_audio_input", False),
                        supports_audio_output=item.get("supports_audio_output", False),
                        model_family=item.get("model_family"),
                        release_channel=item.get("release_channel"),
                        metadata_info=item["metadata_info"],
                        source_type="discovered",
                        is_enabled=True,
                    )
                    self.db.add(platform_model)
                    await self.db.flush()
                    added_count += 1
                else:
                    platform_model.raw_model_name = item["raw_model_name"]
                    platform_model.model_type = item["model_type"]
                    platform_model.capabilities = item["capabilities"]
                    platform_model.context_window = item.get("context_window") or platform_model.context_window
                    platform_model.max_output_tokens = item.get("max_output_tokens") or platform_model.max_output_tokens
                    platform_model.embedding_dimension = item.get("embedding_dimension") or platform_model.embedding_dimension
                    platform_model.supports_stream = item["supports_stream"]
                    platform_model.supports_tools = item.get("supports_tools", False)
                    platform_model.supports_structured_output = item.get("supports_structured_output", False)
                    platform_model.supports_vision_input = item.get("supports_vision_input", False)
                    platform_model.supports_audio_input = item.get("supports_audio_input", False)
                    platform_model.supports_audio_output = item.get("supports_audio_output", False)
                    platform_model.model_family = item.get("model_family") or platform_model.model_family
                    platform_model.release_channel = item.get("release_channel") or platform_model.release_channel
                    platform_model.provider_definition_id = provider_definition.id
                    platform_model.metadata_info = item["metadata_info"]
                    if overwrite_existing_display_name:
                        platform_model.display_name = item["display_name"]
                    updated_count += 1

                tenant_model = await self._get_tenant_model(
                    tenant_id=current_user.tenant_id,
                    tenant_provider_id=tenant_provider_id,
                    platform_model_id=platform_model.id,
                )
                if tenant_model is None and auto_enable_models:
                    tenant_model = TenantModel(
                        tenant_id=current_user.tenant_id,
                        resource_scope=TENANT_RESOURCE_SCOPE,
                        owner_user_id=None,
                        tenant_provider_id=tenant_provider_id,
                        platform_model_id=platform_model.id,
                        model_alias=platform_model.display_name,
                        model_type=platform_model.model_type,
                        capabilities=platform_model.capabilities,
                        source_type="discovered",
                        group_key=platform_model.model_family,
                        is_enabled=True,
                        is_visible_in_ui=True,
                        created_by_id=current_user.id,
                        created_by_name=current_user.nickname or current_user.username or "System",
                        updated_by_id=current_user.id,
                        updated_by_name=current_user.nickname or current_user.username or "System",
                    )
                    self.db.add(tenant_model)
                    enabled_binding_count += 1
                elif tenant_model is not None:
                    tenant_model.model_type = platform_model.model_type
                    tenant_model.capabilities = platform_model.capabilities
                    tenant_model.source_type = "discovered"
                    tenant_model.group_key = platform_model.model_family
                    tenant_model.updated_by_id = current_user.id
                    tenant_model.updated_by_name = current_user.nickname or current_user.username or "System"

            sync_record.status = "success"
            sync_record.discovered_count = len(discovered_models)
            sync_record.added_count = added_count
            sync_record.updated_count = updated_count
            sync_record.raw_payload = {"models": discovered_models}
            sync_record.finished_at = datetime.now(timezone.utc)

            provider.last_sync_at = datetime.now(timezone.utc)
            provider.sync_status = "success"
            provider.sync_error = None

            await self.db.commit()
            await self.db.refresh(sync_record)

            return {
                "success": True,
                "sync_record_id": sync_record.id,
                "tenant_provider_id": tenant_provider_id,
                "discovered_count": len(discovered_models),
                "added_count": added_count,
                "updated_count": updated_count,
                "enabled_binding_count": enabled_binding_count,
                "detail": "模型同步成功",
            }
        except Exception as exc:
            sync_record.status = "failed"
            sync_record.error_message = str(exc)
            sync_record.finished_at = datetime.now(timezone.utc)
            provider.sync_status = "failed"
            provider.sync_error = str(exc)
            provider.last_sync_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.exception("模型同步失败: tenant_provider_id=%s", tenant_provider_id)
            raise

    async def _load_provider_bundle(
        self,
        tenant_provider_id: UUID,
        tenant_id: UUID,
    ) -> tuple[TenantModelProvider, ModelProviderDefinition]:
        """加载 provider 实例及其定义。"""
        provider_stmt = select(TenantModelProvider).where(
            TenantModelProvider.id == tenant_provider_id,
            TenantModelProvider.tenant_id == tenant_id,
            TenantModelProvider.resource_scope == TENANT_RESOURCE_SCOPE,
        )
        provider_result = await self.db.execute(provider_stmt)
        provider = provider_result.scalar_one_or_none()
        if provider is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型厂商配置不存在")

        definition_stmt = select(ModelProviderDefinition).where(
            ModelProviderDefinition.id == provider.provider_definition_id
        )
        definition_result = await self.db.execute(definition_stmt)
        provider_definition = definition_result.scalar_one_or_none()
        if provider_definition is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型厂商定义不存在")

        return provider, provider_definition

    async def _load_primary_credential(
        self,
        tenant_provider_id: UUID,
    ) -> TenantModelProviderCredential | None:
        """加载启用中的主凭证。"""
        stmt = (
            select(TenantModelProviderCredential)
            .where(
                TenantModelProviderCredential.tenant_provider_id == tenant_provider_id,
                TenantModelProviderCredential.is_enabled == True,  # noqa: E712
            )
            .order_by(TenantModelProviderCredential.is_primary.desc(), TenantModelProviderCredential.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _discover_models(
        self,
        provider: TenantModelProvider,
        provider_definition: ModelProviderDefinition,
        credential: TenantModelProviderCredential | None,
    ) -> list[dict[str, Any]]:
        """根据协议类型发现模型列表。"""
        protocol_type = provider_definition.protocol_type
        if protocol_type in {"openai", "openai_compatible", "vllm", "azure_openai"}:
            return await self._discover_openai_compatible_models(provider, provider_definition, credential)
        if protocol_type == "ollama":
            return await self._discover_ollama_models(provider)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前阶段暂不支持协议 {protocol_type} 的自动发现",
        )

    async def _discover_openai_compatible_models(
        self,
        provider: TenantModelProvider,
        provider_definition: ModelProviderDefinition,
        credential: TenantModelProviderCredential | None,
    ) -> list[dict[str, Any]]:
        """发现 OpenAI 兼容模型。"""
        headers: dict[str, str] = {}
        timeout = httpx.Timeout(20.0, connect=10.0)
        if credential is not None:
            api_key = str(credential.encrypted_config.get("api_key", "")).strip()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

        base_url = provider.base_url.rstrip("/")

        # Tongyi-Qianwen 使用百炼平台的官方模型列表 API
        if provider_definition.provider_code == "tongyi_qianwen":
            models = await self._discover_dashscope_models(base_url, headers, timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{base_url}/models", headers=headers)
                response.raise_for_status()
                payload = response.json()

            models = []
            for item in payload.get("data", []):
                raw_name = str(item.get("id", "")).strip()
                if not raw_name:
                    continue
                models.append(self._build_discovered_model(raw_name=raw_name, source_payload=item))

        return models

    async def _discover_dashscope_models(
        self,
        base_url: str,
        headers: dict[str, str],
        timeout: httpx.Timeout,
    ) -> list[dict[str, Any]]:
        """
        发现百炼平台（Tongyi-Qianwen）的模型列表。

        百炼平台使用专有的模型列表接口：GET /api/v1/models
        返回格式与 OpenAI 不兼容，需要单独处理。
        page_size 最大支持 100，总共约 439 个模型，需要约 5 次分页请求。
        """
        import asyncio

        _ = base_url
        # 百炼平台的官方模型列表 API
        dashscope_api_base = "https://dashscope.aliyuncs.com/api/v1"
        models: list[dict[str, Any]] = []
        page_no = 1
        page_size = 100  # 百炼 API 最大支持 100
        max_retries = 3

        async with httpx.AsyncClient(timeout=timeout) as client:
            while True:
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        response = await client.get(
                            f"{dashscope_api_base}/models",
                            headers=headers,
                            params={"page_no": page_no, "page_size": page_size},
                        )
                        if response.status_code == 429:
                            retry_count += 1
                            if retry_count < max_retries:
                                await asyncio.sleep(3 * retry_count)  # 递增等待时间
                                continue
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="百炼平台请求过于频繁，请稍后重试",
                            )
                        response.raise_for_status()
                        break
                    except httpx.HTTPStatusError:
                        retry_count += 1
                        if retry_count < max_retries:
                            await asyncio.sleep(1 * retry_count)
                            continue
                        raise

                payload = response.json()

                if not payload.get("success"):
                    logger.warning("百炼 API 返回 success=false，page_no=%s", page_no)
                    break

                output = payload.get("output", {})
                model_list = output.get("models", [])
                if not model_list:
                    logger.info("百炼 API 模型列表为空，page_no=%s", page_no)
                    break

                for item in model_list:
                    raw_name = str(item.get("model", "")).strip()
                    if not raw_name:
                        continue
                    models.append(self._build_discovered_model(
                        raw_name=raw_name,
                        source_payload=item,
                    ))

                total = output.get("total", 0)
                logger.info("百炼 API 第 %s 页：获取 %s 个模型，total=%s", page_no, len(model_list), total)

                if page_no * page_size >= total:
                    break
                page_no += 1
                # 请求间隔，避免触发限流
                await asyncio.sleep(1)

        return models

    async def _discover_ollama_models(self, provider: TenantModelProvider) -> list[dict[str, Any]]:
        """发现 Ollama 模型。"""
        base_url = provider.base_url.rstrip("/")
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()

        models: list[dict[str, Any]] = []
        for item in payload.get("models", []):
            raw_name = str(item.get("name", "")).strip()
            if not raw_name:
                continue
            models.append(self._build_discovered_model(raw_name=raw_name, source_payload=item))
        return models

    def _build_discovered_model(
        self,
        *,
        raw_name: str,
        source_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """将发现结果归一为平台模型结构。"""
        normalized_name = raw_name.strip()
        lower_name = normalized_name.lower()
        capabilities = ["chat"]
        model_type = "chat"
        details_raw = source_payload.get("details")
        details: dict[str, Any] = details_raw if isinstance(details_raw, dict) else {}
        model_metadata = self._extract_model_metadata(source_payload=source_payload, details=details)

        if "embedding" in lower_name or lower_name.startswith("bge") or lower_name.startswith("gte"):
            capabilities = ["embedding"]
            model_type = "embedding"
        elif "rerank" in lower_name:
            capabilities = ["rerank"]
            model_type = "rerank"
        elif "whisper" in lower_name or "asr" in lower_name:
            capabilities = ["asr"]
            model_type = "asr"
        elif "tts" in lower_name:
            capabilities = ["tts"]
            model_type = "tts"
        elif "vl" in lower_name or "vision" in lower_name or "gpt-4o" in lower_name:
            capabilities = ["chat", "vision"]
            model_type = "chat"

        return {
            "model_key": normalized_name,
            "raw_model_name": normalized_name,
            "display_name": normalized_name,
            "model_type": model_type,
            "capabilities": capabilities,
            "context_window": model_metadata["context_window"],
            "max_output_tokens": model_metadata["max_output_tokens"],
            "embedding_dimension": model_metadata["embedding_dimension"],
            "supports_stream": model_type == "chat",
            "supports_tools": model_metadata["supports_tools"],
            "supports_structured_output": model_metadata["supports_structured_output"],
            "supports_vision_input": "vision" in capabilities,
            "supports_audio_input": model_type == "asr",
            "supports_audio_output": model_type == "tts",
            "model_family": model_metadata["model_family"],
            "release_channel": model_metadata["release_channel"],
            "metadata_info": {"source_payload": source_payload, "discovered_metadata": model_metadata},
        }

    def _extract_model_metadata(self, *, source_payload: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
        """从常见模型发现响应中提取可展示元信息，提取不到时保持为空。"""

        def pick_positive_int(*keys: str) -> int | None:
            for key in keys:
                raw_value = source_payload.get(key)
                if raw_value is None:
                    raw_value = details.get(key)
                if raw_value is None:
                    continue
                try:
                    value = int(raw_value)
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    return value
            return None

        raw_family = source_payload.get("family") or details.get("family") or source_payload.get("owned_by")
        parameter_size = details.get("parameter_size")
        quantization_level = details.get("quantization_level")
        release_channel = source_payload.get("release_channel") or source_payload.get("permission_type")

        return {
            "context_window": pick_positive_int("context_window", "context_length", "max_context_length", "max_model_len", "max_sequence_length", "n_ctx"),
            "max_output_tokens": pick_positive_int("max_output_tokens", "max_tokens", "output_token_limit"),
            "embedding_dimension": pick_positive_int("embedding_dimension", "dimensions", "dimension", "embedding_dimensions"),
            "supports_tools": bool(source_payload.get("supports_tools") or source_payload.get("tool_calls")),
            "supports_structured_output": bool(source_payload.get("supports_structured_output") or source_payload.get("response_format")),
            "model_family": str(raw_family).strip() if raw_family else None,
            "release_channel": str(release_channel).strip() if release_channel else None,
            "parameter_size": str(parameter_size).strip() if parameter_size else None,
            "quantization_level": str(quantization_level).strip() if quantization_level else None,
        }

    async def _get_platform_model_by_key(self, model_key: str) -> PlatformModel | None:
        """按唯一键查询平台模型。"""
        stmt = select(PlatformModel).where(PlatformModel.model_key == model_key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_tenant_model(
        self,
        *,
        tenant_id: UUID,
        tenant_provider_id: UUID,
        platform_model_id: UUID,
    ) -> TenantModel | None:
        """查询租户模型绑定。"""
        stmt = select(TenantModel).where(
            TenantModel.tenant_id == tenant_id,
            TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
            TenantModel.tenant_provider_id == tenant_provider_id,
            TenantModel.platform_model_id == platform_model_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _build_masked_summary(self, api_key: str | None) -> str | None:
        """构造前端展示用的脱敏凭证摘要。"""
        normalized = str(api_key or "").strip()
        if not normalized:
            return None
        if len(normalized) <= 8:
            return f"{normalized[:2]}***{normalized[-2:]}"
        return f"{normalized[:4]}***{normalized[-4:]}"
