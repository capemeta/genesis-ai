"""
分块器基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseChunker(ABC):
    """
    分块器基类
    
    所有分块器必须继承此类并实现 chunk 方法
    
    设计原则：
    - Celery Worker 本身是独立进程，不受主应用 GIL 限制
    - 分块器只提供同步方法 chunk()，简单直接
    - 不需要异步，Celery 任务本身就是同步的
    """
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50, **kwargs):
        """
        初始化分块器
        
        Args:
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
            **kwargs: 其他配置参数
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.config = kwargs
    
    @abstractmethod
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        分块（同步方法）
        
        Args:
            text: 待分块的文本
            metadata: 文档元数据
        
        Returns:
            List[Dict[str, Any]]: 分块列表，标准结构如下：
                [
                    {
                        "text": "分块内容",
                        "metadata": {"page": 1, ...},
                        "type": "text"  # 可选，默认为 text。支持 values: text, html, table, image, media, code, json
                    },
                    ...
                ]
        
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError("子类必须实现 chunk 方法")
