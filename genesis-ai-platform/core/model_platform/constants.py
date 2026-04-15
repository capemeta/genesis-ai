"""
模型平台常量定义。
"""

CAPABILITY_TYPES: tuple[str, ...] = (
    "chat",
    "vision",
    "embedding",
    "rerank",
    "asr",
    "tts",
    "image",
    "video",
    "ocr",
    "document_parse",
)

PROVIDER_PROTOCOL_TYPES: tuple[str, ...] = (
    "openai",
    "openai_compatible",
    "anthropic_native",
    "gemini_native",
    "azure_openai",
    "ollama",
    "vllm",
    "bedrock",
    "custom",
)

ENDPOINT_TYPES: tuple[str, ...] = (
    "official",
    "openai_compatible",
    "local",
    "proxy",
)

CREDENTIAL_TYPES: tuple[str, ...] = (
    "api_key",
    "access_key_secret",
    "oauth",
    "none",
)

ADAPTER_TYPES: tuple[str, ...] = (
    "litellm",
    "native",
    "openai_sdk",
    "custom",
)

MODEL_SOURCE_TYPES: tuple[str, ...] = (
    "builtin",
    "discovered",
    "manual",
)

RESOURCE_SCOPE_TYPES: tuple[str, ...] = (
    "tenant",
    "user",
)

MODEL_GRANTEE_TYPES: tuple[str, ...] = (
    "tenant",
    "role",
    "user",
)

SYNC_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "success",
    "failed",
)
