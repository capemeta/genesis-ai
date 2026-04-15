"""
增强器基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseEnhancer(ABC):
    """
    增强器基类
    
    所有增强器必须继承此类并实现 enhance 方法
    
    设计原则：
    - 增强任务是 I/O 密集型（调用 LLM API）
    - 使用异步方法实现高并发
    - 配合 gevent Worker 实现协程并发
    """
    
    def __init__(self, **kwargs):
        """
        初始化增强器
        
        Args:
            **kwargs: 增强器配置参数
        """
        self.config = kwargs
    
    @abstractmethod
    async def enhance(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        增强分块（异步方法）
        
        Args:
            chunk: 分块数据，包含 text 和 metadata
        
        Returns:
            Dict[str, Any]: 增强后的分块数据
        
        Raises:
            NotImplementedError: 子类必须实现此方法
        
        注意：
        - 这是 I/O 密集任务（调用 LLM API）
        - 使用异步实现高并发
        - 部署时使用 gevent Worker：
          celery -A tasks worker -Q enhance --pool=gevent --concurrency=50
        """
        raise NotImplementedError("子类必须实现 enhance 方法")
