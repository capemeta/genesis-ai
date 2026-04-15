"""
速率限制器
基于 Redis 实现的 API 速率限制
"""
from datetime import datetime, timedelta
from typing import Optional
from redis.asyncio import Redis
from fastapi import Request, HTTPException, status, Depends
from core.exceptions import TooManyRequestsException
from core.database import get_redis


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, Optional[int]]:
        """
        检查速率限制
        
        Args:
            key: 限制键（如 IP 地址、用户 ID）
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
        
        Returns:
            (是否允许, 剩余秒数)
        """
        rate_key = f"rate_limit:{key}"
        
        # 获取当前计数
        current = await self.redis.get(rate_key)
        
        if current is None:
            # 首次请求，设置计数为 1
            await self.redis.setex(rate_key, window_seconds, 1)
            return True, None
        
        current_count = int(current)
        
        if current_count >= max_requests:
            # 超过限制，获取剩余时间
            ttl = await self.redis.ttl(rate_key)
            return False, ttl
        
        # 增加计数
        await self.redis.incr(rate_key)
        return True, None
    
    async def check_login_attempts(
        self,
        identifier: str,
        max_attempts: int = 5,
        lockout_minutes: int = 15,
    ) -> tuple[bool, Optional[int]]:
        """
        检查登录尝试次数
        
        Args:
            identifier: 标识符（用户名、邮箱或 IP）
            max_attempts: 最大尝试次数
            lockout_minutes: 锁定时间（分钟）
        
        Returns:
            (是否允许, 剩余秒数)
        """
        key = f"login_attempts:{identifier}"
        
        # 获取当前尝试次数
        attempts = await self.redis.get(key)
        
        if attempts is None:
            return True, None
        
        attempts_count = int(attempts)
        
        if attempts_count >= max_attempts:
            # 超过限制，获取剩余锁定时间
            ttl = await self.redis.ttl(key)
            return False, ttl
        
        return True, None
    
    async def record_login_failure(
        self,
        identifier: str,
        lockout_minutes: int = 15,
    ):
        """
        记录登录失败
        
        Args:
            identifier: 标识符（用户名、邮箱或 IP）
            lockout_minutes: 锁定时间（分钟）
        """
        key = f"login_attempts:{identifier}"
        
        # 增加失败次数
        await self.redis.incr(key)
        
        # 设置过期时间
        await self.redis.expire(key, lockout_minutes * 60)
    
    async def clear_login_attempts(self, identifier: str):
        """
        清除登录失败记录
        
        Args:
            identifier: 标识符（用户名、邮箱或 IP）
        """
        key = f"login_attempts:{identifier}"
        await self.redis.delete(key)
    
    async def check_api_rate_limit(
        self,
        request: Request,
        max_requests: int = 100,
        window_seconds: int = 60,
    ):
        """
        检查 API 速率限制（中间件使用）
        
        Args:
            request: FastAPI 请求对象
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
        
        Raises:
            TooManyRequestsException: 超过速率限制
        """
        # 获取客户端 IP
        client_ip = request.client.host if request.client else "unknown"
        
        # 如果用户已登录，使用用户 ID
        user = getattr(request.state, "user", None)
        if user:
            key = f"user:{user.id}"
        else:
            key = f"ip:{client_ip}"
        
        # 检查速率限制
        allowed, ttl = await self.check_rate_limit(key, max_requests, window_seconds)
        
        if not allowed:
            raise TooManyRequestsException(
                f"Too many requests. Try again in {ttl} seconds."
            )


# 依赖注入函数
async def get_rate_limiter(redis: Redis = Depends(get_redis)) -> RateLimiter:
    """获取速率限制器实例"""
    return RateLimiter(redis)
