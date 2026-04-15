"""
存储服务模块

支持多种存储驱动：
- local: 本地文件系统
- s3: AWS S3 / SeaweedFS S3
"""
from typing import Optional

from core.storage.base import StorageDriver
from core.storage.local_driver import get_local_driver


def get_s3_driver():
    """延迟加载 S3 驱动，避免在进程启动阶段提前触发重依赖导入。"""
    from core.storage.s3_driver import get_s3_driver as _get_s3_driver

    return _get_s3_driver()


def get_storage_driver(driver_type: Optional[str] = None) -> StorageDriver:
    """
    获取存储驱动实例（工厂方法）
    
    Args:
        driver_type: 驱动类型（local/s3），如果为 None 则从配置读取
        
    Returns:
        StorageDriver 实例
        
    Raises:
        ValueError: 不支持的存储驱动类型
    """
    from core.config import settings
    
    driver = driver_type or settings.STORAGE_DRIVER
    
    if driver == "local":
        return get_local_driver(settings.LOCAL_STORAGE_PATH)
    elif driver == "s3":
        return get_s3_driver()
    else:
        raise ValueError(f"不支持的存储驱动: {driver}，支持的类型: local, s3")


__all__ = [
    "StorageDriver",
    "get_storage_driver",
    "get_local_driver",
    "get_s3_driver",
]
