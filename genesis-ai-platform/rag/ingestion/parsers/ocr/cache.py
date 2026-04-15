"""
OCR 结果缓存模块

特性：
1. 线程安全的 LRU 缓存
2. 基于图像哈希的缓存键
3. 自动过期机制
4. 内存限制保护
"""

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class OCRCache:
    """
    线程安全的 OCR 结果缓存
    
    使用 LRU (Least Recently Used) 策略，自动淘汰最久未使用的缓存项
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数（默认 100）
            ttl_seconds: 缓存过期时间（秒，默认 1 小时）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()  # 可重入锁，支持嵌套调用
        self._hits = 0
        self._misses = 0
    
    def _compute_cache_key(
        self,
        image_hash: str,
        engine: str,
        languages: List[str],
        variant: str,
        psm: Optional[int] = None,
        min_confidence: float = 45.0,
    ) -> str:
        """
        计算缓存键
        
        Args:
            image_hash: 图像哈希值
            engine: OCR 引擎名称
            languages: 语言列表
            variant: 变体名称
            psm: Tesseract PSM 模式
            min_confidence: 最小置信度
        
        Returns:
            缓存键字符串
        """
        # 组合所有影响识别结果的参数
        key_parts = [
            image_hash,
            engine,
            ",".join(sorted(languages)),
            variant,
            str(psm) if psm is not None else "none",
            f"{min_confidence:.2f}",
        ]
        return "|".join(key_parts)
    
    def get(
        self,
        image_hash: str,
        engine: str,
        languages: List[str],
        variant: str = "original",
        psm: Optional[int] = None,
        min_confidence: float = 45.0,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        从缓存获取 OCR 结果
        
        Returns:
            OCR 结果列表，如果未命中或已过期则返回 None
        """
        cache_key = self._compute_cache_key(
            image_hash, engine, languages, variant, psm, min_confidence
        )
        
        with self._lock:
            if cache_key not in self._cache:
                self._misses += 1
                return None
            
            result, timestamp = self._cache[cache_key]
            
            # 检查是否过期
            if time.time() - timestamp > self.ttl_seconds:
                del self._cache[cache_key]
                self._misses += 1
                logger.debug(f"[OCRCache] 缓存过期: {cache_key[:50]}...")
                return None
            
            # 移到末尾（LRU 更新）
            self._cache.move_to_end(cache_key)
            self._hits += 1
            logger.debug(f"[OCRCache] 缓存命中: {cache_key[:50]}...")
            return result
    
    def put(
        self,
        image_hash: str,
        engine: str,
        languages: List[str],
        result: List[Dict[str, Any]],
        variant: str = "original",
        psm: Optional[int] = None,
        min_confidence: float = 45.0,
    ) -> None:
        """
        将 OCR 结果存入缓存
        """
        cache_key = self._compute_cache_key(
            image_hash, engine, languages, variant, psm, min_confidence
        )
        
        with self._lock:
            # 如果缓存已满，删除最旧的条目
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"[OCRCache] 缓存已满，淘汰最旧条目: {oldest_key[:50]}...")
            
            # 存入缓存
            self._cache[cache_key] = (result, time.time())
            logger.debug(f"[OCRCache] 缓存存入: {cache_key[:50]}...")
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info("[OCRCache] 缓存已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            包含命中率、大小等信息的字典
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.2f}%",
                "ttl_seconds": self.ttl_seconds,
            }
    
    def cleanup_expired(self) -> int:
        """
        清理过期的缓存条目
        
        Returns:
            清理的条目数
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items()
                if current_time - timestamp > self.ttl_seconds
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"[OCRCache] 清理了 {len(expired_keys)} 个过期缓存条目")
            
            return len(expired_keys)


def compute_image_hash(image) -> str:
    """
    计算图像的哈希值
    
    Args:
        image: PIL Image 对象
    
    Returns:
        SHA256 哈希值（十六进制字符串）
    """
    try:
        import io
        
        # 将图像转换为字节流
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
        
        # 计算 SHA256 哈希
        return hashlib.sha256(image_bytes).hexdigest()
    except Exception as e:
        logger.warning(f"[OCRCache] 计算图像哈希失败: {e}")
        # 降级方案：使用图像尺寸和模式作为简单标识
        return f"{image.size[0]}x{image.size[1]}_{image.mode}_{id(image)}"


# 全局缓存实例（单例模式）
_global_cache: Optional[OCRCache] = None
_cache_lock = threading.Lock()


def get_global_cache(max_size: int = 100, ttl_seconds: int = 3600) -> OCRCache:
    """
    获取全局缓存实例（单例模式）
    
    Args:
        max_size: 最大缓存条目数
        ttl_seconds: 缓存过期时间（秒）
    
    Returns:
        全局 OCRCache 实例
    """
    global _global_cache
    
    with _cache_lock:
        if _global_cache is None:
            _global_cache = OCRCache(max_size=max_size, ttl_seconds=ttl_seconds)
            logger.info(f"[OCRCache] 初始化全局缓存: max_size={max_size}, ttl={ttl_seconds}s")
        
        return _global_cache


def clear_global_cache() -> None:
    """清空全局缓存"""
    global _global_cache
    
    with _cache_lock:
        if _global_cache is not None:
            _global_cache.clear()
