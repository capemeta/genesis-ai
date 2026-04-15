"""
知识库运行时模型解析器。

职责：
- 统一解析知识库在运行时真正使用的模型
- 优先使用知识库显式配置
- 未显式配置时回退到模型中心的租户默认模型
- 仅返回当前租户内已启用、可调用的模型
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge_base import KnowledgeBase
from models.model_provider_definition import ModelProviderDefinition
from models.platform_model import PlatformModel
from models.tenant_default_model import TenantDefaultModel
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider

TENANT_RESOURCE_SCOPE = "tenant"


@dataclass(slots=True)
class ResolvedTenantModelRef:
    """运行时模型解析结果。"""

    tenant_model_id: UUID
    provider_code: str
    raw_model_name: str
    display_name: str
    capability_type: str


def kb_requires_chat_model(kb: KnowledgeBase) -> bool:
    """判断当前知识库是否需要聊天类模型。"""
    intelligence_config = dict(kb.intelligence_config or {})
    enhancement_cfg = dict(intelligence_config.get("enhancement") or {})
    kg_cfg = dict(intelligence_config.get("knowledge_graph") or {})
    raptor_cfg = dict(intelligence_config.get("raptor") or {})
    return (
        enhancement_cfg.get("enabled") is not False
        or bool(kg_cfg.get("enabled"))
        or bool(raptor_cfg.get("enabled"))
    )


async def resolve_kb_runtime_model(
    session: AsyncSession,
    *,
    kb: KnowledgeBase,
    capability_type: str,
) -> ResolvedTenantModelRef:
    """解析知识库当前能力的实际模型。"""
    preferred_model_id = _get_kb_preferred_model_id(kb, capability_type)
    if preferred_model_id:
        return await resolve_tenant_runtime_model_by_id(
            session,
            tenant_id=kb.tenant_id,
            capability_type=capability_type,
            tenant_model_id=preferred_model_id,
        )

    preferred_model_name = _get_kb_preferred_model_name(kb, capability_type)
    if preferred_model_name:
        return await resolve_tenant_runtime_model(
            session,
            tenant_id=kb.tenant_id,
            capability_type=capability_type,
            preferred_model_name=preferred_model_name,
        )

    return await resolve_tenant_runtime_model(
        session,
        tenant_id=kb.tenant_id,
        capability_type=capability_type,
        preferred_model_name=None,
    )


async def resolve_tenant_runtime_model_by_id(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    capability_type: str,
    tenant_model_id: UUID,
) -> ResolvedTenantModelRef:
    """按 tenant_model_id 精确解析运行时模型。"""
    enabled_models = await _load_enabled_models(session, tenant_id=tenant_id, capability_type=capability_type)
    for item in enabled_models:
        if item.tenant_model_id == tenant_model_id:
            return item

    capability_label = _capability_label(capability_type)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"知识库配置的{capability_label}模型不存在或未启用，请先在模型服务中检查配置",
    )


async def resolve_tenant_runtime_model(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    capability_type: str,
    preferred_model_name: str | None,
) -> ResolvedTenantModelRef:
    """按租户模型池解析运行时模型。"""
    enabled_models = await _load_enabled_models(session, tenant_id=tenant_id, capability_type=capability_type)

    if preferred_model_name:
        matched = _match_enabled_model(enabled_models, preferred_model_name)
        if matched is None:
            capability_label = _capability_label(capability_type)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"知识库配置的{capability_label}模型“{preferred_model_name}”不存在或未启用，"
                    "请先在模型服务中同步并启用对应模型"
                ),
            )
        return matched

    default_stmt = select(TenantDefaultModel).where(
        TenantDefaultModel.tenant_id == tenant_id,
        TenantDefaultModel.resource_scope == TENANT_RESOURCE_SCOPE,
        TenantDefaultModel.capability_type == capability_type,
        TenantDefaultModel.is_enabled == True,  # noqa: E712
    )
    default_result = await session.execute(default_stmt)
    default_binding = default_result.scalar_one_or_none()
    if default_binding is None:
        capability_label = _capability_label(capability_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前租户尚未配置默认{capability_label}模型，请先到模型服务中设置默认模型",
        )

    for item in enabled_models:
        if item.tenant_model_id == default_binding.tenant_model_id:
            return item

    capability_label = _capability_label(capability_type)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"当前租户的默认{capability_label}模型不存在或未启用，请先检查模型服务配置",
    )


async def validate_kb_runtime_models(
    session: AsyncSession,
    *,
    kb: KnowledgeBase,
) -> dict[str, dict[str, str]]:
    """校验知识库运行时所需模型是否齐备，并返回快照。"""
    resolved_embedding = await resolve_kb_runtime_model(
        session,
        kb=kb,
        capability_type="embedding",
    )
    result = {
        "embedding": _serialize_model_ref(resolved_embedding),
    }

    if kb_requires_chat_model(kb):
        resolved_chat = await resolve_kb_runtime_model(
            session,
            kb=kb,
            capability_type="chat",
        )
        result["chat"] = _serialize_model_ref(resolved_chat)

    return result


async def _load_enabled_models(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    capability_type: str,
) -> list[ResolvedTenantModelRef]:
    """加载当前租户下可用于指定能力的启用模型。"""
    stmt = (
        select(TenantModel, PlatformModel, TenantModelProvider, ModelProviderDefinition)
        .join(PlatformModel, PlatformModel.id == TenantModel.platform_model_id)
        .join(TenantModelProvider, TenantModelProvider.id == TenantModel.tenant_provider_id)
        .join(ModelProviderDefinition, ModelProviderDefinition.id == TenantModelProvider.provider_definition_id)
        .where(
            TenantModel.tenant_id == tenant_id,
            TenantModel.resource_scope == TENANT_RESOURCE_SCOPE,
            TenantModel.is_enabled == True,  # noqa: E712
            TenantModelProvider.tenant_id == tenant_id,
            TenantModelProvider.is_enabled == True,  # noqa: E712
            PlatformModel.is_enabled == True,  # noqa: E712
            ModelProviderDefinition.is_enabled == True,  # noqa: E712
        )
    )
    rows = (await session.execute(stmt)).all()
    resolved: list[ResolvedTenantModelRef] = []
    for tenant_model, platform_model, _provider, provider_definition in rows:
        capabilities = set(_normalize_capabilities(tenant_model.capabilities or platform_model.capabilities or []))
        if capability_type not in capabilities:
            model_type = str(tenant_model.model_type or platform_model.model_type or "").strip().lower()
            if model_type != capability_type:
                continue
        resolved.append(
            ResolvedTenantModelRef(
                tenant_model_id=tenant_model.id,
                provider_code=str(provider_definition.provider_code or "").strip(),
                raw_model_name=str(platform_model.raw_model_name or "").strip(),
                display_name=str(tenant_model.model_alias or platform_model.display_name or platform_model.raw_model_name or "").strip(),
                capability_type=capability_type,
            )
        )
    return resolved


def _match_enabled_model(
    enabled_models: Iterable[ResolvedTenantModelRef],
    preferred_model_name: str,
) -> ResolvedTenantModelRef | None:
    """按知识库中保存的模型名称匹配启用模型。"""
    target = _normalize_model_name(preferred_model_name)
    for item in enabled_models:
        candidates = {
            _normalize_model_name(item.raw_model_name),
            _normalize_model_name(item.display_name),
        }
        if target in candidates:
            return item
    return None


def _normalize_capabilities(values: Iterable[object]) -> list[str]:
    """规范化能力列表。"""
    return [str(value or "").strip().lower() for value in values if str(value or "").strip()]


def _normalize_model_name(value: str | None) -> str:
    """规范化模型名称比较口径。"""
    return str(value or "").strip().lower()


def _get_kb_preferred_model_name(kb: KnowledgeBase, capability_type: str) -> str | None:
    """读取知识库当前能力的显式模型配置。"""
    if capability_type == "embedding":
        return str(kb.embedding_model or "").strip() or None
    if capability_type == "chat":
        return str(kb.index_model or "").strip() or None
    if capability_type == "vision":
        return str(kb.vision_model or "").strip() or None
    return None


def _get_kb_preferred_model_id(kb: KnowledgeBase, capability_type: str) -> UUID | None:
    """读取知识库当前能力的显式模型 ID 配置。"""
    if capability_type == "embedding":
        return kb.embedding_model_id
    if capability_type == "chat":
        return getattr(kb, "index_model_id", None)
    if capability_type == "vision":
        return getattr(kb, "vision_model_id", None)
    return None


def _capability_label(capability_type: str) -> str:
    """能力类型转中文标签。"""
    label_map = {
        "chat": "大模型",
        "embedding": "嵌入",
        "vision": "视觉",
    }
    return label_map.get(capability_type, capability_type)


def _serialize_model_ref(ref: ResolvedTenantModelRef) -> dict[str, str]:
    """序列化模型快照，便于写入运行态。"""
    return {
        "tenant_model_id": str(ref.tenant_model_id),
        "provider_code": ref.provider_code,
        "raw_model_name": ref.raw_model_name,
        "display_name": ref.display_name,
        "capability_type": ref.capability_type,
    }
