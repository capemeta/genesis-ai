"""
Simple Chat Engine - 简单对话引擎
不使用 RAG，直接与 LLM 对话
"""
from typing import Optional
from llama_index.core.chat_engine import SimpleChatEngine as LlamaSimpleChatEngine
from llama_index.core.llms import ChatMessage
from ..config import Settings
from .base import BaseEngine


class SimpleChatEngine(BaseEngine):
    """简单对话引擎 - 纯 LLM 对话（无 RAG）"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化简单对话引擎
        
        Args:
            data_dir: 数据目录（此引擎不使用，但保持接口一致）
        """
        super().__init__(data_dir)
        self.chat_engine = LlamaSimpleChatEngine.from_defaults()
        self.chat_history = []
        print(f"🚀 Simple Chat 引擎初始化完成")
    
    def chat(self, message: str) -> str:
        """同步对话"""
        response = self.chat_engine.chat(message)
        return str(response)
    
    async def achat(self, message: str) -> str:
        """异步对话"""
        response = await self.chat_engine.achat(message)
        return str(response)
    
    def stream_chat(self, message: str):
        """流式对话（同步）"""
        response = self.chat_engine.stream_chat(message)
        for token in response.response_gen:
            yield token
    
    async def astream_chat(self, message: str):
        """流式对话（异步）"""
        response = await self.chat_engine.astream_chat(message)
        async for token in response.async_response_gen():
            yield token
    
    def reset(self):
        """重置对话历史"""
        self.chat_engine.reset()
        self.chat_history = []
