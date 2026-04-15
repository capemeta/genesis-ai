"""
多模型平台自定义接口。

这里承载 CRUD 之外的动作型接口：
- 测试连接
- 同步模型
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from core.database import get_async_session
from models.user import User
from schemas.model_platform import (
    ModelAudioTranscriptionRequest,
    ModelAudioTranscriptionResponse,
    ModelChatCompletionRequest,
    ModelChatCompletionResponse,
    ModelDebugInvokeRequest,
    ModelDebugInvokeResponse,
    ModelDebugRuntimeProfileRequest,
    ModelDebugRuntimeProfileResponse,
    ModelEmbeddingRequest,
    ModelEmbeddingResponse,
    ModelRerankRequest,
    ModelRerankResponse,
    ModelSpeechRequest,
    ModelSpeechResponse,
    ModelSettingsDefaultModelUpsertRequest,
    ModelSettingsDefaultModelUpsertResponse,
    ModelSettingsCustomProviderCreateRequest,
    ModelSettingsCustomProviderCreateResponse,
    ModelSettingsCustomProviderArchiveRequest,
    ModelSettingsCustomProviderArchiveResponse,
    ModelSettingsManualModelCreateRequest,
    ModelSettingsManualModelCreateResponse,
    ModelSettingsModelsBatchUpdateRequest,
    ModelSettingsModelsBatchUpdateResponse,
    ModelSettingsOverviewResponse,
    ModelSettingsProviderUpsertRequest,
    ModelSettingsProviderUpsertResponse,
    ModelProviderSyncRequest,
    ModelProviderSyncResponse,
    ModelProviderTestConnectionRequest,
    ModelProviderTestConnectionResponse,
)
from services.model_platform_service import (
    ModelInvocationService,
    ModelProviderIntegrationService,
    ModelSettingsService,
)

router = APIRouter(prefix="/model-platform", tags=["model-platform"])


@router.get(
    "/settings/overview",
    response_model=ModelSettingsOverviewResponse,
    summary="获取模型设置概览",
    description="聚合内置厂商、租户厂商实例、模型分组和默认模型，供模型设置页使用。"
)
async def get_model_settings_overview(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelSettingsOverviewResponse:
    """获取模型设置页概览数据。"""
    service = ModelSettingsService(session)
    result = await service.get_overview(current_user)
    return ModelSettingsOverviewResponse(**result)


@router.post(
    "/settings/providers/upsert",
    response_model=ModelSettingsProviderUpsertResponse,
    summary="保存模型厂商配置",
    description="按厂商定义创建或更新租户级厂商实例与主凭证。"
)
async def upsert_model_settings_provider(
    request: ModelSettingsProviderUpsertRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelSettingsProviderUpsertResponse:
    """保存模型设置页中的厂商配置。"""
    service = ModelSettingsService(session)
    result = await service.upsert_provider_settings(request.model_dump(), current_user)
    return ModelSettingsProviderUpsertResponse(**result)


@router.post(
    "/settings/providers/create-custom",
    response_model=ModelSettingsCustomProviderCreateResponse,
    summary="创建自定义厂商",
    description="在模型设置页中一次性创建自定义厂商定义、租户厂商实例和主凭证。"
)
async def create_model_settings_custom_provider(
    request: ModelSettingsCustomProviderCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelSettingsCustomProviderCreateResponse:
    """创建自定义厂商。"""
    service = ModelSettingsService(session)
    result = await service.create_custom_provider(current_user=current_user, payload=request.model_dump())
    return ModelSettingsCustomProviderCreateResponse(**result)


@router.post(
    "/settings/providers/archive-custom",
    response_model=ModelSettingsCustomProviderArchiveResponse,
    summary="归档自定义厂商",
    description="归档自定义厂商定义，并禁用当前租户下关联的厂商实例、模型和默认模型绑定。"
)
async def archive_model_settings_custom_provider(
    request: ModelSettingsCustomProviderArchiveRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelSettingsCustomProviderArchiveResponse:
    """归档自定义厂商。"""
    service = ModelSettingsService(session)
    result = await service.archive_custom_provider(
        current_user=current_user,
        provider_definition_id=request.provider_definition_id,
    )
    return ModelSettingsCustomProviderArchiveResponse(**result)


@router.post(
    "/settings/models/manual",
    response_model=ModelSettingsManualModelCreateResponse,
    summary="手动添加模型",
    description="手动添加一个模型到指定厂商，支持指定模型类型和能力。"
)
async def create_manual_model(
    request: ModelSettingsManualModelCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelSettingsManualModelCreateResponse:
    """手动添加模型。"""
    service = ModelSettingsService(session)
    result = await service.create_manual_model(
        current_user=current_user,
        payload=request.model_dump(),
    )
    return ModelSettingsManualModelCreateResponse(**result)


@router.post(
    "/settings/models/batch-update",
    response_model=ModelSettingsModelsBatchUpdateResponse,
    summary="批量更新模型状态",
    description="按模型 ID 列表批量更新启用状态或前端可见性。"
)
async def batch_update_model_settings_models(
    request: ModelSettingsModelsBatchUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelSettingsModelsBatchUpdateResponse:
    """批量更新模型设置页中的模型状态。"""
    service = ModelSettingsService(session)
    result = await service.batch_update_models(
        current_user=current_user,
        model_ids=request.model_ids,
        is_enabled=request.is_enabled,
        is_visible_in_ui=request.is_visible_in_ui,
    )
    return ModelSettingsModelsBatchUpdateResponse(**result)


@router.post(
    "/settings/default-models/upsert",
    response_model=ModelSettingsDefaultModelUpsertResponse,
    summary="保存默认模型",
    description="按能力类型创建、更新或清空默认模型。"
)
async def upsert_model_settings_default_model(
    request: ModelSettingsDefaultModelUpsertRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelSettingsDefaultModelUpsertResponse:
    """保存模型设置页中的默认模型配置。"""
    service = ModelSettingsService(session)
    result = await service.upsert_default_model(
        current_user=current_user,
        capability_type=request.capability_type,
        tenant_model_id=request.tenant_model_id,
    )
    return ModelSettingsDefaultModelUpsertResponse(**result)


@router.post(
    "/providers/test-connection",
    response_model=ModelProviderTestConnectionResponse,
    summary="测试模型厂商连接",
    description="测试指定租户模型厂商配置的连通性，并尝试发现模型列表。"
)
async def test_provider_connection(
    request: ModelProviderTestConnectionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelProviderTestConnectionResponse:
    """测试 provider 连通性。"""
    service = ModelProviderIntegrationService(session)
    result = await service.test_connection(request.tenant_provider_id, current_user)
    return ModelProviderTestConnectionResponse(**result)


@router.post(
    "/providers/sync-models",
    response_model=ModelProviderSyncResponse,
    summary="同步模型列表",
    description="从指定 provider 拉取模型清单，更新平台模型目录与租户模型绑定。"
)
async def sync_provider_models(
    request: ModelProviderSyncRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelProviderSyncResponse:
    """同步 provider 模型列表。"""
    service = ModelProviderIntegrationService(session)
    result = await service.sync_models(
        request.tenant_provider_id,
        current_user,
        auto_enable_models=request.auto_enable_models,
        overwrite_existing_display_name=request.overwrite_existing_display_name,
    )
    return ModelProviderSyncResponse(**result)


@router.post(
    "/chat/completions",
    response_model=ModelChatCompletionResponse,
    summary="统一聊天调用",
    description="通过模型平台统一调用租户已配置的聊天模型。当前阶段支持 OpenAI-compatible / vLLM / Ollama 非流式调用。"
)
async def model_chat_completions(
    request: ModelChatCompletionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelChatCompletionResponse:
    """统一聊天调用入口。"""
    service = ModelInvocationService(session)
    result = await service.chat(
        current_user=current_user,
        tenant_model_id=request.tenant_model_id,
        capability_type=request.capability_type,
        messages=[message.model_dump() for message in request.messages],
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=request.stream,
        extra_body=request.extra_body,
    )
    return ModelChatCompletionResponse(**result)


@router.post(
    "/embeddings",
    response_model=ModelEmbeddingResponse,
    summary="统一向量化调用",
    description="通过模型平台统一调用租户已配置的 embedding 模型。当前阶段优先走 LiteLLM。"
)
async def model_embeddings(
    request: ModelEmbeddingRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelEmbeddingResponse:
    """统一 embedding 调用入口。"""
    service = ModelInvocationService(session)
    input_texts = request.input if isinstance(request.input, list) else [request.input]
    result = await service.embed(
        current_user=current_user,
        tenant_model_id=request.tenant_model_id,
        capability_type=request.capability_type,
        input_texts=input_texts,
        extra_body=request.extra_body,
    )
    return ModelEmbeddingResponse(**result)


@router.post(
    "/rerank",
    response_model=ModelRerankResponse,
    summary="统一重排序调用",
    description="通过模型平台统一调用租户已配置的 rerank 模型，支持协议级适配与响应归一。"
)
async def model_rerank(
    request: ModelRerankRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelRerankResponse:
    """统一 rerank 调用入口。"""
    service = ModelInvocationService(session)
    documents = [
        item.model_dump(exclude_none=True) if hasattr(item, "model_dump") else item
        for item in request.documents
    ]
    result = await service.rerank(
        current_user=current_user,
        tenant_model_id=request.tenant_model_id,
        capability_type=request.capability_type,
        query=request.query,
        documents=documents,
        top_n=request.top_n,
        return_documents=request.return_documents,
        extra_body=request.extra_body,
    )
    return ModelRerankResponse(**result)


@router.post(
    "/audio/transcriptions",
    response_model=ModelAudioTranscriptionResponse,
    summary="统一语音识别调用",
    description="通过模型平台统一调用租户已配置的 ASR 模型，当前阶段优先支持 OpenAI-compatible 音频识别协议。"
)
async def model_audio_transcriptions(
    request: ModelAudioTranscriptionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelAudioTranscriptionResponse:
    """统一 ASR 调用入口。"""
    service = ModelInvocationService(session)
    result = await service.transcribe(
        current_user=current_user,
        tenant_model_id=request.tenant_model_id,
        capability_type=request.capability_type,
        audio_url=request.audio_url,
        audio_base64=request.audio_base64,
        filename=request.filename,
        mime_type=request.mime_type,
        language=request.language,
        prompt=request.prompt,
        response_format=request.response_format,
        temperature=request.temperature,
        extra_body=request.extra_body,
    )
    return ModelAudioTranscriptionResponse(**result)


@router.post(
    "/audio/speech",
    response_model=ModelSpeechResponse,
    summary="统一语音合成调用",
    description="通过模型平台统一调用租户已配置的 TTS 模型，当前阶段优先支持 OpenAI-compatible 语音合成协议。"
)
async def model_audio_speech(
    request: ModelSpeechRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelSpeechResponse:
    """统一 TTS 调用入口。"""
    service = ModelInvocationService(session)
    result = await service.synthesize_speech(
        current_user=current_user,
        tenant_model_id=request.tenant_model_id,
        capability_type=request.capability_type,
        text=request.input,
        voice=request.voice,
        response_format=request.response_format,
        speed=request.speed,
        extra_body=request.extra_body,
    )
    return ModelSpeechResponse(**result)


@router.post(
    "/debug/runtime-profile",
    response_model=ModelDebugRuntimeProfileResponse,
    summary="预览模型运行时画像",
    description="解析指定模型在当前配置下的最终调用路由，供模型中心调试面板使用。"
)
async def preview_model_debug_runtime_profile(
    request: ModelDebugRuntimeProfileRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelDebugRuntimeProfileResponse:
    """预览指定模型的最终运行时路由。"""
    service = ModelInvocationService(session)
    result = await service.preview_runtime_profile(
        current_user=current_user,
        tenant_model_id=request.tenant_model_id,
        capability_type=request.capability_type,
    )
    return ModelDebugRuntimeProfileResponse(**result)


@router.post(
    "/debug/invoke",
    response_model=ModelDebugInvokeResponse,
    summary="执行模型最小调试调用",
    description="按能力类型执行一条最小测试请求，并返回运行时画像与统一结果。"
)
async def invoke_model_debug_request(
    request: ModelDebugInvokeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ModelDebugInvokeResponse:
    """执行调试面板最小测试调用。"""
    service = ModelInvocationService(session)
    result = await service.debug_invoke(
        current_user=current_user,
        payload=request.model_dump(),
    )
    return ModelDebugInvokeResponse(**result)
