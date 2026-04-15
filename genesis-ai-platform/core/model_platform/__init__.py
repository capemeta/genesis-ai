"""
模型平台核心包。

注意：
- 这里保持轻量，避免包初始化阶段引入 services / models 造成循环引用
- 需要具体实现时，请直接从对应子模块导入
"""

from core.model_platform.constants import (
    ADAPTER_TYPES,
    CAPABILITY_TYPES,
    CREDENTIAL_TYPES,
    ENDPOINT_TYPES,
    MODEL_SOURCE_TYPES,
    PROVIDER_PROTOCOL_TYPES,
    SYNC_STATUSES,
)
from core.model_platform.ports import (
    AsrModelPort,
    ChatModelPort,
    DocumentParseModelPort,
    EmbeddingModelPort,
    OcrModelPort,
    RerankModelPort,
    TtsModelPort,
    VisionModelPort,
)

__all__ = [
    "ADAPTER_TYPES",
    "CAPABILITY_TYPES",
    "CREDENTIAL_TYPES",
    "ENDPOINT_TYPES",
    "MODEL_SOURCE_TYPES",
    "PROVIDER_PROTOCOL_TYPES",
    "SYNC_STATUSES",
    "AsrModelPort",
    "ChatModelPort",
    "DocumentParseModelPort",
    "EmbeddingModelPort",
    "OcrModelPort",
    "RerankModelPort",
    "TtsModelPort",
    "VisionModelPort",
]
