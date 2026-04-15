"""
本地文件系统存储驱动

支持相对路径和绝对路径：
- 相对路径：相对于项目根目录（main.py 所在目录）
- 绝对路径：直接使用指定的路径

最佳实践：
- 开发环境：使用相对路径（如 ./storage）
- 生产环境：使用绝对路径（如 /var/lib/genesis-ai/storage）
"""
import logging
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, cast

from core.storage.base import StorageDriver

logger = logging.getLogger(__name__)


class LocalStorageDriver(StorageDriver):
    """本地文件系统存储驱动"""
    
    def __init__(self, base_path: str):
        """
        初始化本地存储驱动
        
        Args:
            base_path: 存储根目录
                - 相对路径：相对于项目根目录（main.py 所在目录）
                - 绝对路径：直接使用指定的路径
        
        Examples:
            >>> # 相对路径（开发环境推荐）
            >>> driver = LocalStorageDriver("./storage")
            >>> driver = LocalStorageDriver("storage")
            
            >>> # 绝对路径（生产环境推荐）
            >>> driver = LocalStorageDriver("/var/lib/genesis-ai/storage")
            >>> driver = LocalStorageDriver("C:/data/genesis-ai/storage")  # Windows
        """
        # 处理路径
        path = Path(base_path)
        
        if path.is_absolute():
            # 绝对路径：直接使用
            self.base_path = path
        else:
            # 相对路径：相对于项目根目录（main.py 所在目录）
            # 获取项目根目录（向上查找直到找到 main.py）
            project_root = self._find_project_root()
            self.base_path = project_root / path
        
        # 确保目录存在
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"本地存储初始化: {self.base_path.absolute()}")
    
    def _find_project_root(self) -> Path:
        """
        查找项目根目录（main.py 所在目录）
        
        Returns:
            项目根目录路径
        """
        # 从当前文件向上查找
        current = Path(__file__).resolve()
        
        # 向上查找直到找到 main.py
        for parent in [current] + list(current.parents):
            if (parent / "main.py").exists():
                return parent
        
        # 如果没找到 main.py，使用当前工作目录
        logger.warning("未找到 main.py，使用当前工作目录作为项目根目录")
        return Path.cwd()
    
    def _get_full_path(self, key: str) -> Path:
        """
        获取文件的完整路径
        
        Args:
            key: 存储键名/路径
            
        Returns:
            完整的文件路径
        """
        return self.base_path / key
    
    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        上传文件到本地文件系统
        
        Args:
            file: 文件对象
            key: 存储键名/路径
            content_type: MIME 类型（本地存储不使用）
            metadata: 元数据（本地存储不使用）
            
        Returns:
            str: 文件存储路径（相对于 base_path）
        """
        try:
            full_path = self._get_full_path(key)
            
            # 确保父目录存在
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(full_path, 'wb') as f:
                # 如果 file 有 read 方法，使用 read
                if hasattr(file, 'read'):
                    shutil.copyfileobj(file, f)
                else:
                    # 否则假设是字节数据
                    f.write(cast(bytes, file))
            
            logger.info(f"文件上传成功: {key} -> {full_path}")
            return key
            
        except Exception as e:
            logger.error(f"文件上传失败: {key}, 错误: {e}")
            raise
    
    async def download(self, key: str, destination: Path) -> None:
        """
        从本地文件系统下载文件（复制到目标位置）
        
        Args:
            key: 存储键名/路径
            destination: 本地保存路径
        """
        try:
            source = self._get_full_path(key)
            
            if not source.exists():
                raise FileNotFoundError(f"文件不存在: {key}")
            
            # 确保目标目录存在
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(source, destination)
            
            logger.info(f"文件下载成功: {key} -> {destination}")
            
        except Exception as e:
            logger.error(f"文件下载失败: {key}, 错误: {e}")
            raise
    
    async def delete(self, key: str) -> None:
        """
        从本地文件系统删除文件
        
        Args:
            key: 存储键名/路径
        """
        try:
            full_path = self._get_full_path(key)
            
            if full_path.exists():
                full_path.unlink()
                logger.info(f"文件删除成功: {key}")
                
                # 尝试删除空的父目录（最多向上删除 3 层）
                self._cleanup_empty_dirs(full_path.parent, max_levels=3)
            else:
                logger.warning(f"文件不存在，无需删除: {key}")
                
        except Exception as e:
            logger.error(f"文件删除失败: {key}, 错误: {e}")
            raise
    
    def _cleanup_empty_dirs(self, directory: Path, max_levels: int = 3) -> None:
        """
        清理空目录（向上递归）
        
        Args:
            directory: 要检查的目录
            max_levels: 最多向上清理的层数
        """
        try:
            for _ in range(max_levels):
                # 如果目录不存在或不是目录，停止
                if not directory.exists() or not directory.is_dir():
                    break
                
                # 如果目录不为空，停止
                if any(directory.iterdir()):
                    break
                
                # 如果是 base_path，停止（不删除根目录）
                if directory == self.base_path:
                    break
                
                # 删除空目录
                directory.rmdir()
                logger.debug(f"删除空目录: {directory}")
                
                # 向上一层
                directory = directory.parent
                
        except Exception as e:
            logger.debug(f"清理空目录失败: {e}")
    
    async def exists(self, key: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            key: 存储键名/路径
            
        Returns:
            bool: 是否存在
        """
        full_path = self._get_full_path(key)
        return full_path.exists() and full_path.is_file()
    
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """
        获取文件访问 URL
        
        注意：本地存储不支持预签名 URL，返回文件的绝对路径
        实际使用时应该通过后端 API 代理下载
        
        Args:
            key: 存储键名/路径
            expires_in: 过期时间（本地存储不使用）
            
        Returns:
            str: 文件绝对路径
        """
        full_path = self._get_full_path(key)
        
        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {key}")
        
        # 返回绝对路径
        return str(full_path.absolute())
    
    async def get_content(self, key: str) -> bytes:
        """
        获取文件内容（一次性读取，适用于小文件）
        
        Args:
            key: 存储键名/路径
            
        Returns:
            bytes: 文件内容
        """
        try:
            full_path = self._get_full_path(key)
            
            if not full_path.exists():
                raise FileNotFoundError(f"文件不存在: {key}")
            
            with open(full_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"获取文件内容失败: {key}, 错误: {e}")
            raise
    
    async def get_stream(self, key: str, chunk_size: int = 8192):
        """
        获取文件流（分块读取，适用于大文件）
        
        Args:
            key: 存储键名/路径
            chunk_size: 每次读取的块大小（字节）
            
        Yields:
            bytes: 文件内容块
        """
        full_path = self._get_full_path(key)
        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {key}")
        
        try:
            # 使用同步文件读取（在异步生成器中）
            with open(full_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    
        except Exception as e:
            logger.error(f"获取文件流失败: {key}, 错误: {e}")
            raise


# 全局本地存储驱动实例字典（支持多个 base_path）
_local_drivers: dict[str, LocalStorageDriver] = {}


def get_local_driver(base_path: Optional[str] = None) -> LocalStorageDriver:
    """
    获取本地存储驱动实例（支持多个 base_path）
    
    Args:
        base_path: 存储根目录（可选，首次调用时必须提供）
        
    Returns:
        LocalStorageDriver 实例
        
    Note:
        使用字典缓存，支持不同的 base_path 对应不同的驱动实例
        这样可以支持混合存储（不同文档使用不同的存储路径）
    """
    global _local_drivers
    
    if base_path is None:
        raise ValueError("必须提供 base_path 参数")
    
    # 规范化路径（转换为绝对路径）
    path = Path(base_path)
    if not path.is_absolute():
        # 相对路径：相对于项目根目录
        current = Path(__file__).resolve()
        for parent in [current] + list(current.parents):
            if (parent / "main.py").exists():
                path = parent / path
                break
        else:
            path = Path.cwd() / path
    
    # 使用绝对路径作为缓存键
    cache_key = str(path.absolute())
    
    if cache_key not in _local_drivers:
        _local_drivers[cache_key] = LocalStorageDriver(base_path)
    
    return _local_drivers[cache_key]
