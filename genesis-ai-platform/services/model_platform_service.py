"""
多模型平台服务定义。

当前先提供基础 CRUD 服务骨架，后续可以继续补：
- 连接测试
- 模型同步
- 默认模型校验
- LiteLLM / Native Adapter 路由
"""
import logging
from typing import Any
from uuid import UUID, uuid5, NAMESPACE_DNS

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.model_provider_definition import ModelProviderDefinition
from services.model_platform import (
    ModelAdapterBindingService,
    ModelProviderDefinitionService,
    ModelInvocationService,
    ModelProviderIntegrationService,
    ModelSettingsService,
    PlatformModelService,
    TenantDefaultModelService,
    TenantModelProviderCredentialService,
    TenantModelProviderService,
    TenantModelService,
)

logger = logging.getLogger(__name__)

# 当前阶段平台运行时只启用租户级模型资源。
TENANT_RESOURCE_SCOPE = "tenant"

BUILTIN_PROVIDER_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "provider_code": "openai",
        "display_name": "OpenAI",
        "protocol_type": "openai",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision", "asr", "tts", "image"],
        "description": "OpenAI 官方服务接入。",
        "sort_order": 10,
        "metadata_info": {"default_base_url": "https://api.openai.com/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "gemini",
        "display_name": "Gemini",
        "protocol_type": "gemini_native",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision"],
        "description": "Gemini 官方服务接入。",
        "sort_order": 20,
        "metadata_info": {"default_base_url": "https://generativelanguage.googleapis.com", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "deepseek",
        "display_name": "DeepSeek",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding"],
        "description": "DeepSeek 官方兼容接口接入。",
        "sort_order": 30,
        "metadata_info": {"default_base_url": "https://api.deepseek.com/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "moonshot",
        "display_name": "Moonshot",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision"],
        "description": "Moonshot 官方兼容接口接入。",
        "sort_order": 40,
        "metadata_info": {"default_base_url": "https://api.moonshot.cn/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "zhipu_ai",
        "display_name": "ZHIPU-AI",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision"],
        "description": "智谱 AI 官方兼容接口接入。",
        "sort_order": 50,
        "metadata_info": {"default_base_url": "https://open.bigmodel.cn/api/paas/v4", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "xai",
        "display_name": "xAI",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat"],
        "description": "xAI 官方兼容接口接入。",
        "sort_order": 60,
        "metadata_info": {"default_base_url": "https://api.x.ai/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "anthropic",
        "display_name": "Anthropic",
        "protocol_type": "anthropic_native",
        "adapter_type": "litellm",
        "supports_model_discovery": False,
        "supported_capabilities": ["chat", "vision"],
        "description": "Anthropic 官方 Messages API 接入。",
        "sort_order": 65,
        "metadata_info": {"default_base_url": "https://api.anthropic.com", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "baidu_yiyan",
        "display_name": "BaiduYiyan",
        "protocol_type": "custom",
        "adapter_type": "custom",
        "supports_model_discovery": False,
        "supported_capabilities": ["chat", "embedding", "rerank", "image"],
        "description": "百度千帆 / 文心一言官方接入。",
        "sort_order": 70,
        "metadata_info": {"default_base_url": "https://qianfan.baidubce.com/v2", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "openai_compatible",
        "display_name": "OpenAI-API-Compatible",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "rerank", "vision", "asr", "tts"],
        "description": "兼容 OpenAI /models、/chat/completions 等协议的统一接入方式。",
        "sort_order": 80,
        "metadata_info": {"default_base_url": "", "default_endpoint_type": "openai_compatible", "base_url_editable": True},
    },
    {
        "provider_code": "openrouter",
        "display_name": "OpenRouter",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "vision", "embedding", "image"],
        "description": "OpenRouter 聚合路由服务，按 OpenAI 兼容协议接入。",
        "sort_order": 82,
        "metadata_info": {"default_base_url": "https://openrouter.ai/api/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "groq",
        "display_name": "Groq",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "vision", "asr"],
        "description": "Groq 官方兼容接口接入。",
        "sort_order": 84,
        "metadata_info": {"default_base_url": "https://api.groq.com/openai/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "tongyi_qianwen",
        "display_name": "Tongyi-Qianwen",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "rerank", "vision", "asr", "tts"],
        "description": "阿里云百炼 / 通义千问兼容接口接入。",
        "sort_order": 86,
        "metadata_info": {"default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "doubao",
        "display_name": "Doubao",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision"],
        "description": "火山方舟 / 豆包兼容接口接入。",
        "sort_order": 88,
        "metadata_info": {"default_base_url": "https://ark.cn-beijing.volces.com/api/v3", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "ppio",
        "display_name": "PPIO",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "rerank", "vision"],
        "description": "PPIO 派欧云兼容接口接入。",
        "sort_order": 89,
        "metadata_info": {"default_base_url": "https://api.ppinfra.com/v3/openai", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "ollama",
        "display_name": "Ollama",
        "protocol_type": "ollama",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision"],
        "description": "本地 Ollama 服务接入，支持通过 /api/tags 自动发现模型。",
        "sort_order": 90,
        "metadata_info": {"default_base_url": "http://127.0.0.1:11434", "default_endpoint_type": "local", "base_url_editable": True},
    },
    {
        "provider_code": "azure_openai",
        "display_name": "Azure-OpenAI",
        "protocol_type": "azure_openai",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision"],
        "description": "Azure OpenAI 官方接入。",
        "sort_order": 100,
        "metadata_info": {"default_base_url": "https://your-resource.openai.azure.com", "default_endpoint_type": "official", "base_url_editable": True},
    },
    {
        "provider_code": "minimax",
        "display_name": "MiniMax",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "tts"],
        "description": "MiniMax 官方兼容接口接入。",
        "sort_order": 110,
        "metadata_info": {"default_base_url": "https://api.minimax.chat/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "together_ai",
        "display_name": "TogetherAI",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "image", "vision"],
        "description": "Together AI 官方兼容接口接入。",
        "sort_order": 115,
        "metadata_info": {"default_base_url": "https://api.together.xyz/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "fireworks",
        "display_name": "Fireworks",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "image", "vision"],
        "description": "Fireworks AI 官方兼容接口接入。",
        "sort_order": 118,
        "metadata_info": {"default_base_url": "https://api.fireworks.ai/inference/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "nvidia",
        "display_name": "NVIDIA",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "rerank"],
        "description": "NVIDIA NIM / API Catalog 兼容接口接入。",
        "sort_order": 120,
        "metadata_info": {"default_base_url": "https://integrate.api.nvidia.com/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "siliconflow",
        "display_name": "SILICONFLOW",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "rerank", "vision"],
        "description": "硅基流动官方兼容接口接入。",
        "sort_order": 130,
        "metadata_info": {"default_base_url": "https://api.siliconflow.cn/v1", "default_endpoint_type": "official", "base_url_editable": False},
    },
    {
        "provider_code": "vllm",
        "display_name": "vLLM",
        "protocol_type": "vllm",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding"],
        "description": "本地或私有化 vLLM 推理服务，按 OpenAI 兼容方式接入。",
        "sort_order": 140,
        "metadata_info": {"default_base_url": "", "default_endpoint_type": "proxy", "base_url_editable": True},
    },
    {
        "provider_code": "lmstudio",
        "display_name": "LM Studio",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision"],
        "description": "LM Studio 本地兼容接口接入。",
        "sort_order": 145,
        "metadata_info": {"default_base_url": "http://127.0.0.1:1234/v1", "default_endpoint_type": "local", "base_url_editable": True},
    },
    {
        "provider_code": "localai",
        "display_name": "LocalAI",
        "protocol_type": "openai_compatible",
        "adapter_type": "litellm",
        "supports_model_discovery": True,
        "supported_capabilities": ["chat", "embedding", "vision", "tts", "image"],
        "description": "LocalAI 本地兼容接口接入。",
        "sort_order": 146,
        "metadata_info": {"default_base_url": "http://127.0.0.1:8080/v1", "default_endpoint_type": "local", "base_url_editable": True},
    },
    {
        "provider_code": "mineru",
        "display_name": "MinerU",
        "protocol_type": "custom",
        "adapter_type": "custom",
        "supports_model_discovery": False,
        "supported_capabilities": ["ocr", "document_parse"],
        "description": "MinerU 文档解析服务，适合 OCR、版面分析与结构抽取。",
        "sort_order": 150,
        "metadata_info": {"default_base_url": "http://127.0.0.1:8001", "default_endpoint_type": "proxy", "base_url_editable": True},
    },
)


async def seed_builtin_model_provider_definitions(db: AsyncSession) -> int:
    """
    初始化内置 provider 定义。

    返回值为本次新增的记录数。
    """
    added_count = 0
    for item in BUILTIN_PROVIDER_DEFINITIONS:
        stmt = select(ModelProviderDefinition).where(
            ModelProviderDefinition.provider_code == item["provider_code"]
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            provider_definition = ModelProviderDefinition(
                id=uuid5(NAMESPACE_DNS, f"genesis-ai:model-provider-definition:{item['provider_code']}"),
                provider_code=item["provider_code"],
                display_name=item["display_name"],
                protocol_type=item["protocol_type"],
                adapter_type=item["adapter_type"],
                supports_model_discovery=item["supports_model_discovery"],
                supported_capabilities=item["supported_capabilities"],
                is_builtin=True,
                is_enabled=True,
                description=item["description"],
                sort_order=int(item.get("sort_order", 100)),
                metadata_info=dict(item.get("metadata_info", {})),
            )
            db.add(provider_definition)
            added_count += 1
            continue

        # 开发阶段内置定义允许按最新代码直接覆盖，避免前端读取到过期的内置厂商清单。
        existing.display_name = item["display_name"]
        existing.protocol_type = item["protocol_type"]
        existing.adapter_type = item["adapter_type"]
        existing.supports_model_discovery = item["supports_model_discovery"]
        existing.supported_capabilities = item["supported_capabilities"]
        existing.is_builtin = True
        existing.is_enabled = True
        existing.description = item["description"]
        existing.sort_order = int(item.get("sort_order", existing.sort_order or 100))
        existing.metadata_info = dict(item.get("metadata_info", {}))

    if added_count > 0 or BUILTIN_PROVIDER_DEFINITIONS:
        await db.commit()
    return added_count
