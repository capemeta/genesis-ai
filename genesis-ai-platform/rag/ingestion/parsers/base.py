"""
解析器基类
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any


class BaseParser(ABC):
    """
    解析器基类
    
    所有解析器必须继承此类并实现 parse 方法
    """
    
    def __init__(self, **kwargs):
        """
        初始化解析器
        
        Args:
            **kwargs: 解析器配置参数
        """
        self.config = kwargs
    
    @abstractmethod
    def parse(self, file_buffer: bytes, file_extension: str) -> Tuple[str, Dict[str, Any]]:
        """
        解析文件（同步方法）
        
        ⚠️ 重要设计原则：
        1. 解析任务是 CPU 密集型（文本提取、OCR、布局分析）
        2. 使用同步方法，简单直接
        3. Celery Worker 本身是独立进程，不受主应用 GIL 限制
        4. 部署时使用 prefork Worker：
           celery -A tasks worker -Q parse --pool=prefork --concurrency=4
        
        Args:
            file_buffer: 文件二进制内容
            file_extension: 文件扩展名（如 .pdf, .docx）
        
        Returns:
            Tuple[str, Dict[str, Any]]: (解析后的文本, 元数据)
        
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError("子类必须实现 parse 方法")
    
    @abstractmethod
    def supports(self, file_extension: str) -> bool:
        """
        检查是否支持该文件类型
        
        Args:
            file_extension: 文件扩展名
        
        Returns:
            bool: 是否支持
        """
        raise NotImplementedError("子类必须实现 supports 方法")
