"""
权限缓存服务
使用 Redis 缓存用户权限，提升性能
"""
from typing import List, Optional
from uuid import UUID
import json
import redis.asyncio as redis

from core.config.settings import settings


class PermissionCache:
    """权限缓存服务 - 使用 Redis 缓存用户权限"""
    
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL)
        self.ttl = 3600  # 缓存1小时
    
    def _get_key(self, user_id: UUID, tenant_id: UUID) -> str:
        """生成缓存键"""
        return f"permissions:user:{user_id}:tenant:{tenant_id}"
    
    async def get_permissions(
        self, 
        user_id: UUID, 
        tenant_id: UUID
    ) -> Optional[List[str]]:
        """
        从缓存获取用户权限
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            
        Returns:
            权限代码列表，如果缓存不存在则返回 None
        """
        key = self._get_key(user_id, tenant_id)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_permissions(
        self, 
        user_id: UUID, 
        tenant_id: UUID, 
        permissions: List[str]
    ):
        """
        设置用户权限缓存
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            permissions: 权限代码列表
        """
        key = self._get_key(user_id, tenant_id)
        await self.redis.setex(
            key, 
            self.ttl, 
            json.dumps(permissions)
        )
    
    async def delete_permissions(
        self, 
        user_id: UUID, 
        tenant_id: UUID
    ):
        """
        删除用户权限缓存
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
        """
        key = self._get_key(user_id, tenant_id)
        await self.redis.delete(key)
    
    async def delete_user_all_permissions(self, user_id: UUID):
        """
        删除用户所有租户的权限缓存
        
        Args:
            user_id: 用户 ID
        """
        pattern = f"permissions:user:{user_id}:tenant:*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self.redis.delete(*keys)
    
    async def delete_tenant_all_permissions(self, tenant_id: UUID):
        """
        删除租户所有用户的权限缓存
        
        Args:
            tenant_id: 租户 ID
        """
        pattern = f"permissions:user:*:tenant:{tenant_id}"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self.redis.delete(*keys)


# 全局实例
permission_cache = PermissionCache()
