"""
Token 管理器 - 基于 Redis 的 Token 存储
提供 Token 的创建、验证、刷新、撤销等功能
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from redis.asyncio import Redis
from jose import jwt, JWTError
import json

from core.config import settings
from core.exceptions import InvalidTokenException, TokenExpiredException


class TokenManager:
    """
    Token 管理器
    
    功能：
    - Token 存储在 Redis 中，支持快速撤销
    - 支持 Access Token 和 Refresh Token
    - 支持单点登录（可选）
    - 记录 Token 元数据（IP、设备等）
    """
    
    def __init__(self, redis: Redis):
        self.redis = redis
        
        # Redis Key 前缀
        self.ACCESS_TOKEN_PREFIX = "token:access:"
        self.REFRESH_TOKEN_PREFIX = "token:refresh:"
        self.USER_TOKENS_PREFIX = "user:tokens:"
        
        # Token 过期时间
        self.ACCESS_TOKEN_EXPIRE = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.REFRESH_TOKEN_EXPIRE = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    async def create_token_pair(
        self,
        user_id: UUID,
        tenant_id: UUID,
        client_ip: str,
        user_agent: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        创建 Access Token 和 Refresh Token 对
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            client_ip: 客户端 IP
            user_agent: User-Agent
            device_id: 设备 ID（可选，用于单点登录）
        
        Returns:
            包含 access_token 和 refresh_token 的字典
        """
        # 生成唯一的 token ID
        access_token_id = str(uuid4())
        refresh_token_id = str(uuid4())
        
        now = datetime.now(timezone.utc)
        access_expire = now + self.ACCESS_TOKEN_EXPIRE
        refresh_expire = now + self.REFRESH_TOKEN_EXPIRE
        
        # 创建 JWT payload
        access_payload = {
            "jti": access_token_id,  # JWT ID
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(access_expire.timestamp()),
        }
        
        refresh_payload = {
            "jti": refresh_token_id,
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int(refresh_expire.timestamp()),
        }
        
        # 生成 JWT
        access_token = jwt.encode(
            access_payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        
        refresh_token = jwt.encode(
            refresh_payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        
        # 存储 Token 元数据到 Redis
        access_metadata = {
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "token_id": access_token_id,
            "type": "access",
            "client_ip": client_ip,
            "user_agent": user_agent or "",
            "device_id": device_id or "",
            "created_at": now.isoformat(),
            "expires_at": access_expire.isoformat(),
            "refresh_token_id": refresh_token_id,  # 关联的 refresh token
        }
        
        refresh_metadata = {
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "token_id": refresh_token_id,
            "type": "refresh",
            "client_ip": client_ip,
            "user_agent": user_agent or "",
            "device_id": device_id or "",
            "created_at": now.isoformat(),
            "expires_at": refresh_expire.isoformat(),
            "access_token_id": access_token_id,  # 关联的 access token
        }
        
        # 存储到 Redis（使用 pipeline 提高性能）
        async with self.redis.pipeline() as pipe:
            # 存储 access token
            pipe.setex(
                f"{self.ACCESS_TOKEN_PREFIX}{access_token_id}",
                int(self.ACCESS_TOKEN_EXPIRE.total_seconds()),
                json.dumps(access_metadata),
            )
            
            # 存储 refresh token
            pipe.setex(
                f"{self.REFRESH_TOKEN_PREFIX}{refresh_token_id}",
                int(self.REFRESH_TOKEN_EXPIRE.total_seconds()),
                json.dumps(refresh_metadata),
            )
            
            # 将 token 添加到用户的 token 列表（用于管理用户的所有 token）
            user_tokens_key = f"{self.USER_TOKENS_PREFIX}{user_id}"
            pipe.sadd(user_tokens_key, access_token_id, refresh_token_id)
            pipe.expire(user_tokens_key, int(self.REFRESH_TOKEN_EXPIRE.total_seconds()))
            
            await pipe.execute()
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(self.ACCESS_TOKEN_EXPIRE.total_seconds()),
        }
    
    async def verify_access_token(self, token: str) -> Dict[str, Any]:
        """
        验证 Access Token
        
        Args:
            token: JWT token 字符串
        
        Returns:
            Token payload 和元数据
        
        Raises:
            InvalidTokenException: Token 无效
            TokenExpiredException: Token 已过期
        """
        try:
            # 解码 JWT
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            
            # 检查 token 类型
            if payload.get("type") != "access":
                raise InvalidTokenException("Invalid token type")
            
            token_id = payload.get("jti")
            if not token_id:
                raise InvalidTokenException("Missing token ID")
            
            # 从 Redis 获取 token 元数据
            metadata_json = await self.redis.get(f"{self.ACCESS_TOKEN_PREFIX}{token_id}")
            
            if not metadata_json:
                # Token 不存在或已被撤销
                raise InvalidTokenException("Token has been revoked or expired")
            
            metadata = json.loads(metadata_json)
            
            # 合并 payload 和 metadata
            return {
                **payload,
                **metadata,
            }
            
        except jwt.ExpiredSignatureError:
            raise TokenExpiredException("Token has expired")
        except JWTError as e:
            raise InvalidTokenException(f"Invalid token: {str(e)}")
    
    async def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        """
        验证 Refresh Token
        
        Args:
            token: JWT token 字符串
        
        Returns:
            Token payload 和元数据
        
        Raises:
            InvalidTokenException: Token 无效
            TokenExpiredException: Token 已过期
        """
        try:
            # 解码 JWT
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            
            # 检查 token 类型
            if payload.get("type") != "refresh":
                raise InvalidTokenException("Invalid token type")
            
            token_id = payload.get("jti")
            if not token_id:
                raise InvalidTokenException("Missing token ID")
            
            # 从 Redis 获取 token 元数据
            metadata_json = await self.redis.get(f"{self.REFRESH_TOKEN_PREFIX}{token_id}")
            
            if not metadata_json:
                raise InvalidTokenException("Token has been revoked or expired")
            
            metadata = json.loads(metadata_json)
            
            return {
                **payload,
                **metadata,
            }
            
        except jwt.ExpiredSignatureError:
            raise TokenExpiredException("Token has expired")
        except JWTError as e:
            raise InvalidTokenException(f"Invalid token: {str(e)}")
    
    async def refresh_token(
        self,
        refresh_token: str,
        client_ip: str,
        user_agent: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        使用 Refresh Token 刷新 Access Token
        
        Args:
            refresh_token: Refresh Token
            client_ip: 客户端 IP
            user_agent: User-Agent
        
        Returns:
            新的 token 对
        
        Raises:
            InvalidTokenException: Token 无效
            TokenExpiredException: Token 已过期
        """
        # 验证 refresh token
        token_data = await self.verify_refresh_token(refresh_token)
        
        user_id = UUID(token_data["user_id"])
        tenant_id = UUID(token_data["tenant_id"])
        device_id = token_data.get("device_id")
        
        # 撤销旧的 access token（如果存在）
        old_access_token_id = token_data.get("access_token_id")
        if old_access_token_id:
            await self.redis.delete(f"{self.ACCESS_TOKEN_PREFIX}{old_access_token_id}")
        
        # 创建新的 token 对
        return await self.create_token_pair(
            user_id=user_id,
            tenant_id=tenant_id,
            client_ip=client_ip,
            user_agent=user_agent,
            device_id=device_id,
        )
    
    async def revoke_token(self, token: str) -> bool:
        """
        撤销 Token（登出）
        
        Args:
            token: JWT token 字符串
        
        Returns:
            是否成功撤销
        """
        try:
            # 解码 token（不验证过期时间）
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},
            )
            
            token_id = payload.get("jti")
            token_type = payload.get("type")
            
            if not token_id or not token_type:
                return False
            
            # 删除 token
            if token_type == "access":
                deleted = await self.redis.delete(f"{self.ACCESS_TOKEN_PREFIX}{token_id}")
            elif token_type == "refresh":
                deleted = await self.redis.delete(f"{self.REFRESH_TOKEN_PREFIX}{token_id}")
            else:
                return False
            
            # 从用户 token 列表中移除
            user_id = payload.get("sub")
            if user_id:
                await self.redis.srem(f"{self.USER_TOKENS_PREFIX}{user_id}", token_id)
            
            return deleted > 0
            
        except Exception:
            return False
    
    async def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """
        撤销用户的所有 Token（强制登出所有设备）
        
        Args:
            user_id: 用户 ID
        
        Returns:
            撤销的 token 数量
        """
        user_tokens_key = f"{self.USER_TOKENS_PREFIX}{user_id}"
        
        # 获取用户的所有 token ID
        token_ids = await self.redis.smembers(user_tokens_key)
        
        if not token_ids:
            return 0
        
        # 删除所有 token
        keys_to_delete = []
        for token_id in token_ids:
            keys_to_delete.append(f"{self.ACCESS_TOKEN_PREFIX}{token_id}")
            keys_to_delete.append(f"{self.REFRESH_TOKEN_PREFIX}{token_id}")
        
        deleted = await self.redis.delete(*keys_to_delete)
        
        # 清空用户 token 列表
        await self.redis.delete(user_tokens_key)
        
        return deleted
    
    async def get_user_active_tokens(self, user_id: UUID) -> list[Dict[str, Any]]:
        """
        获取用户的所有活跃 Token
        
        Args:
            user_id: 用户 ID
        
        Returns:
            Token 元数据列表
        """
        user_tokens_key = f"{self.USER_TOKENS_PREFIX}{user_id}"
        token_ids = await self.redis.smembers(user_tokens_key)
        
        if not token_ids:
            return []
        
        tokens = []
        for token_id in token_ids:
            # 尝试获取 access token
            metadata_json = await self.redis.get(f"{self.ACCESS_TOKEN_PREFIX}{token_id}")
            if metadata_json:
                tokens.append(json.loads(metadata_json))
                continue
            
            # 尝试获取 refresh token
            metadata_json = await self.redis.get(f"{self.REFRESH_TOKEN_PREFIX}{token_id}")
            if metadata_json:
                tokens.append(json.loads(metadata_json))
        
        return tokens
    
    async def cleanup_expired_tokens(self) -> int:
        """
        清理过期的 Token（Redis 会自动过期，这个方法主要用于清理用户 token 列表）
        
        Returns:
            清理的 token 数量
        """
        # Redis 的 SETEX 会自动过期，这里主要清理用户 token 列表中的无效引用
        # 这个方法可以作为定时任务运行
        
        # 获取所有用户 token 列表的 key
        pattern = f"{self.USER_TOKENS_PREFIX}*"
        cursor = 0
        cleaned = 0
        
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                # 获取 token ID 列表
                token_ids = await self.redis.smembers(key)
                
                for token_id in token_ids:
                    # 检查 token 是否还存在
                    access_exists = await self.redis.exists(f"{self.ACCESS_TOKEN_PREFIX}{token_id}")
                    refresh_exists = await self.redis.exists(f"{self.REFRESH_TOKEN_PREFIX}{token_id}")
                    
                    if not access_exists and not refresh_exists:
                        # Token 已过期，从列表中移除
                        await self.redis.srem(key, token_id)
                        cleaned += 1
            
            if cursor == 0:
                break
        
        return cleaned
