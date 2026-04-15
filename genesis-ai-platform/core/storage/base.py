"""
存储服务基类
"""
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
from pathlib import Path


class StorageDriver(ABC):
    """存储驱动抽象基类"""
    
    @abstractmethod
    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        上传文件
        
        Args:
            file: 文件对象
            key: 存储键名/路径
            content_type: MIME 类型
            metadata: 元数据
            
        Returns:
            str: 文件访问 URL 或路径
        """
        pass
    
    @abstractmethod
    async def download(self, key: str, destination: Path) -> None:
        """
        下载文件
        
        Args:
            key: 存储键名/路径
            destination: 本地保存路径
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        删除文件
        
        Args:
            key: 存储键名/路径
        """
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            key: 存储键名/路径
            
        Returns:
            bool: 是否存在
        """
        pass
    
    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """
        获取文件访问 URL（预签名）
        
        Args:
            key: 存储键名/路径
            expires_in: 过期时间（秒）
            
        Returns:
            str: 访问 URL
        """
        pass

    @abstractmethod
    async def get_content(self, key: str) -> bytes:
        """
        获取文件内容（一次性读取，适用于小文件）
        
        Args:
            key: 存储键名/路径
            
        Returns:
            bytes: 文件内容
        """
        pass
    
    @abstractmethod
    async def get_stream(self, key: str, chunk_size: int = 8192):
        """
        获取文件流（分块读取，适用于大文件）
        
        Args:
            key: 存储键名/路径
            chunk_size: 每次读取的块大小（字节）
            
        Yields:
            bytes: 文件内容块
        """
        pass
