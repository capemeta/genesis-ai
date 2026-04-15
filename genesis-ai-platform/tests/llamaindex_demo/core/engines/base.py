"""
Base Engine - 引擎基类
"""
import os
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseEngine(ABC):
    """引擎基类 - 定义所有引擎的通用接口"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化引擎
        
        Args:
            data_dir: 数据目录路径，默认为 llamaindex_demo/data
        """
        if data_dir is None:
            # 获取 llamaindex_demo 目录
            engines_dir = os.path.dirname(os.path.abspath(__file__))
            core_dir = os.path.dirname(engines_dir)
            demo_dir = os.path.dirname(core_dir)
            self.data_dir = os.path.join(demo_dir, "data")
        else:
            self.data_dir = data_dir
    
    @abstractmethod
    def chat(self, message: str) -> str:
        """
        同步对话接口
        
        Args:
            message: 用户消息
            
        Returns:
            str: AI 回复
        """
        pass
    
    @abstractmethod
    async def achat(self, message: str) -> str:
        """
        异步对话接口
        
        Args:
            message: 用户消息
            
        Returns:
            str: AI 回复
        """
        pass
    
    def stream_chat(self, message: str):
        """
        流式对话接口（同步）
        
        Args:
            message: 用户消息
            
        Yields:
            str: AI 回复的文本片段
        """
        raise NotImplementedError("This engine does not support streaming")
    
    async def astream_chat(self, message: str):
        """
        流式对话接口（异步）
        
        Args:
            message: 用户消息
            
        Yields:
            str: AI 回复的文本片段
        """
        raise NotImplementedError("This engine does not support async streaming")
