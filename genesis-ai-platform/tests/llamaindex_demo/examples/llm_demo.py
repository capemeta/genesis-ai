"""
配置模块 - 初始化 LlamaIndex Settings
"""
import os
import sys

# 添加父目录到 Python 路径，以便导入 core 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Settings 
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.base.llms.types import (
    ChatMessage,
)

"""内部初始化函数"""
api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    raise ValueError("❌ 环境变量 DASHSCOPE_API_KEY 未设置")

llm = OpenAILike(
        model="deepseek-v3",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=api_key,
        context_window=128000,
        is_chat_model=True,
        is_function_calling_model=True,
)
llm = Settings.llm
messages = [
    ChatMessage(
        role="system", content="你是一个智能助手"
    ),
    ChatMessage(role="user", content="今天赣州天气怎样"),
]

response = llm.stream_chat(messages)
for chunk in response:
    print(chunk.delta, end="", flush=True)
print()


