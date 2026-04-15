"""
配置模块 - 初始化 LlamaIndex Settings
"""
import os
from llama_index.core import Settings
from llama_index.embeddings.dashscope import (
    DashScopeEmbedding,
    DashScopeTextEmbeddingModels,
    DashScopeTextEmbeddingType,
)
from llama_index.llms.openai_like import OpenAILike


def _bootstrap():
    """内部初始化函数"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("❌ 环境变量 DASHSCOPE_API_KEY 未设置")

    # 配置 Embedding
    Settings.embed_model = DashScopeEmbedding(
        model_name=DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V3,
        text_type=DashScopeTextEmbeddingType.TEXT_TYPE_DOCUMENT,
        api_key=api_key,
    )

    # 配置 LLM
    Settings.llm = OpenAILike(
        model="deepseek-v3",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=api_key,
        context_window=128000,
        is_chat_model=True,
        is_function_calling_model=True,
        additional_kwargs={
            "extra_body": {"enable_thinking": True}
        }
    )
    print("[OK] LlamaIndex initialized successfully")


# 执行初始化
_bootstrap()

# 显式导出
__all__ = ["Settings"]
