"""
Session 存储 - 纯 Redis Session 方案
不使用 JWT，所有 session 数据存储在 Redis 中
更简单、更安全、更易于管理
"""
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Awaitable, Optional, Dict, Any, List, cast
from uuid import UUID
from redis.asyncio import Redis
import json
import secrets

from core.config import settings
from core.exceptions import InvalidTokenException, TokenExpiredException

if TYPE_CHECKING:
    from models.user import User


class SessionType:
    """Session 类型枚举"""
    ACCESS = "access"
    REFRESH = "refresh"


class SessionStore:
    """
    Session 存储
    
    设计理念：
    1. Session ID 作为 token（随机字符串，不可预测）
    2. 所有 session 数据存储在 Redis 中
    3. 支持快速撤销、会话管理
    4. 无需 JWT，避免 token 无法撤销的问题
    
    类似于传统的 Session 管理，但使用 Redis 作为存储
    """
    
    def __init__(self, redis: Redis):
        self.redis = redis
        
        # 🔥 Redis Key 前缀（区分 access 和 refresh）
        self.ACCESS_SESSION_PREFIX = "auth:access:"
        self.REFRESH_SESSION_PREFIX = "auth:refresh:"
        self.USER_SESSIONS_PREFIX = "auth:user:sessions:"
        self.REFRESH_REVOKED_PREFIX = "auth:refresh:revoked:"
        self.REFRESH_LOCK_PREFIX = "auth:refresh:lock:"
        
        # Session 过期时间
        self.ACCESS_SESSION_EXPIRE = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.REFRESH_SESSION_EXPIRE = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    def _generate_session_id(self) -> str:
        """
        生成安全的 Session ID
        
        Returns:
            32 字节的随机字符串（URL 安全）
        """
        return secrets.token_urlsafe(32)
    
    async def create_session(
        self,
        session_type: str,
        user_id: UUID,
        tenant_id: UUID,
        client_ip: str,
        user_agent: Optional[str] = None,
        scope: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_info: Optional[Dict[str, Any]] = None,
        custom_access_expire: Optional[timedelta] = None,  # 🔥 新增：自定义 access 过期时间
        custom_refresh_expire: Optional[timedelta] = None,  # 🔥 新增：自定义 refresh 过期时间
    ) -> str:
        """
        创建 Session
        
        Args:
            session_type: Session 类型（access/refresh）
            user_id: 用户 ID
            tenant_id: 租户 ID
            client_ip: 客户端 IP
            user_agent: User-Agent
            scope: 权限范围
            metadata: 额外元数据
            user_info: 用户信息（仅 access session 需要，用于缓存）
            custom_access_expire: 自定义 access 过期时间（可选）
            custom_refresh_expire: 自定义 refresh 过期时间（可选）
            
        Returns:
            Session ID（作为 token 使用）
        """
        # 🔥 使用自定义过期时间或默认值
        if session_type == SessionType.ACCESS:
            expire_delta = custom_access_expire or self.ACCESS_SESSION_EXPIRE
        elif session_type == SessionType.REFRESH:
            expire_delta = custom_refresh_expire or self.REFRESH_SESSION_EXPIRE
        else:
            expire_delta = self.ACCESS_SESSION_EXPIRE
        
        # 🔥 只在创建 access session 时检查数量限制
        # 因为 auth:user:sessions 只存储 access token（代表活跃会话）
        if session_type == SessionType.ACCESS:
            user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
            session_count = await cast(Awaitable[int], self.redis.scard(user_sessions_key))
            
            MAX_SESSIONS_PER_USER = 10  # 每个用户最多 10 个活跃会话
            if session_count >= MAX_SESSIONS_PER_USER:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"User {user_id} has reached max sessions limit ({MAX_SESSIONS_PER_USER}), "
                    f"removing oldest session"
                )
                # 删除最旧的 access session（FIFO）
                oldest_access_id = await cast(Awaitable[Any], self.redis.spop(user_sessions_key))
                if oldest_access_id:
                    # 读取 access session 获取关联的 refresh token
                    access_json = await self.redis.get(f"{self.ACCESS_SESSION_PREFIX}{oldest_access_id}")
                    if access_json:
                        try:
                            access_data = json.loads(access_json)
                            refresh_id = access_data.get("refresh_session_id")
                            # 删除 access 和关联的 refresh
                            await self.redis.delete(f"{self.ACCESS_SESSION_PREFIX}{oldest_access_id}")
                            if refresh_id:
                                await self.redis.delete(f"{self.REFRESH_SESSION_PREFIX}{refresh_id}")
                        except Exception:
                            pass
        
        # 生成 Session ID
        session_id = self._generate_session_id()
        
        # 🔥 根据 session 类型选择 key 前缀
        if session_type == SessionType.ACCESS:
            key_prefix = self.ACCESS_SESSION_PREFIX
        elif session_type == SessionType.REFRESH:
            key_prefix = self.REFRESH_SESSION_PREFIX
        else:
            key_prefix = self.ACCESS_SESSION_PREFIX  # 默认
        
        # 构建 session 数据
        # 🔥 修复：使用 UTC 时间并确保时区信息正确
        now = datetime.now(timezone.utc)
        
        # 🔥 优化：根据 session 类型构建不同的数据结构
        if session_type == SessionType.ACCESS:
            # Access session：包含完整信息 + 用户信息缓存
            ttl = int(expire_delta.total_seconds())
            expires_at = now + expire_delta
            session_data = {
                "session_id": session_id,
                "session_type": session_type,
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "client_ip": client_ip,
                "user_agent": user_agent or "",
                "scope": scope or [],
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                **(metadata or {}),
            }
            # 添加用户信息缓存
            if user_info:
                session_data["user"] = user_info
                
        elif session_type == SessionType.REFRESH:
            # 🔥 Refresh session：只存储最小必要信息（减少冗余）
            # 不存储：client_ip, user_agent, user（这些从 access session 继承）
            ttl = int(expire_delta.total_seconds())
            expires_at = now + expire_delta
            session_data = {
                "session_id": session_id,
                "session_type": session_type,
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "scope": scope or [],
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                **(metadata or {}),
            }
        else:
            # 默认（兼容）
            ttl = int(expire_delta.total_seconds())
            expires_at = now + expire_delta
            session_data = {
                "session_id": session_id,
                "session_type": session_type,
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "client_ip": client_ip,
                "user_agent": user_agent or "",
                "scope": scope or [],
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                **(metadata or {}),
            }
        
        # 存储到 Redis
        async with self.redis.pipeline() as pipe:
            # 1. 存储 session 数据（使用对应的 key 前缀）
            pipe.setex(
                f"{key_prefix}{session_id}",
                ttl,
                json.dumps(session_data),
            )
            
            # 2. 只有 access session 才添加到用户会话列表
            # 🔥 优化：auth:user:sessions 只存储 access token（代表活跃会话）
            # 通过 access session 的 refresh_session_id 可以找到对应的 refresh token
            if session_type == SessionType.ACCESS:
                pipe.sadd(f"{self.USER_SESSIONS_PREFIX}{user_id}", session_id)
                # 使用 access token 的过期时间（会话活跃度的标志）
                pipe.expire(f"{self.USER_SESSIONS_PREFIX}{user_id}", ttl)
            
            await pipe.execute()
        
        return session_id
    
    async def read_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        读取 Session 信息
        
        Args:
            session_id: Session ID
        
        Returns:
            Session 数据，如果不存在返回 None
        
        Raises:
            TokenExpiredException: Session 已过期（Redis 自动删除）
        """
        # 🔥 尝试从两个前缀读取（兼容 access 和 refresh）
        session_json = await self.redis.get(f"{self.ACCESS_SESSION_PREFIX}{session_id}")
        if not session_json:
            session_json = await self.redis.get(f"{self.REFRESH_SESSION_PREFIX}{session_id}")
        
        if not session_json:
            return None
        
        session_data = json.loads(session_json)
        
        # 检查是否过期（双重保险，Redis TTL 已经处理）
        expires_at = datetime.fromisoformat(session_data.get("expires_at"))
        if datetime.now(timezone.utc) > expires_at:
            # 已过期，删除
            await self.remove_session(session_id)
            return None
        
        return session_data
    
    async def remove_session(self, session_id: str) -> bool:
        """
        删除 Session（撤销）
        
        Args:
            session_id: Session ID（可以是 access 或 refresh）
        
        Returns:
            是否成功删除
        """
        try:
            # 先尝试作为 access session 读取
            access_json = await self.redis.get(f"{self.ACCESS_SESSION_PREFIX}{session_id}")
            refresh_json = await self.redis.get(f"{self.REFRESH_SESSION_PREFIX}{session_id}")
            
            user_id = None
            refresh_id = None
            access_id = None
            
            # 如果是 access session
            if access_json:
                try:
                    access_data = json.loads(access_json)
                    user_id = access_data.get("user_id")
                    refresh_id = access_data.get("refresh_session_id")
                    access_id = session_id
                except Exception:
                    pass
            
            # 如果是 refresh session
            if refresh_json:
                try:
                    refresh_data = json.loads(refresh_json)
                    user_id = user_id or refresh_data.get("user_id")
                    access_id = access_id or refresh_data.get("access_session_id")
                    refresh_id = refresh_id or session_id
                except Exception:
                    pass
            
            # 删除 session（删除整个 session pair）
            async with self.redis.pipeline() as pipe:
                if access_id:
                    pipe.delete(f"{self.ACCESS_SESSION_PREFIX}{access_id}")
                    # 从用户会话列表中移除（只有 access token 在列表中）
                    if user_id:
                        pipe.srem(f"{self.USER_SESSIONS_PREFIX}{user_id}", access_id)
                
                if refresh_id:
                    pipe.delete(f"{self.REFRESH_SESSION_PREFIX}{refresh_id}")
                
                await pipe.execute()
            
            return True
            
        except Exception:
            return False
    
    async def remove_user_sessions(self, user_id: UUID) -> int:
        """
        删除用户的所有 Session
        
        Args:
            user_id: 用户 ID
        
        Returns:
            删除的 session pair 数量
        """
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
        
        # 获取所有 access session IDs（auth:user:sessions 只存储 access token）
        access_session_ids = await cast(Awaitable[Any], self.redis.smembers(user_sessions_key))
        
        if not access_session_ids:
            return 0
        
        # 删除所有 session pairs
        keys_to_delete = []
        session_pair_count = 0
        
        for access_id in access_session_ids:
            # 读取 access session 获取关联的 refresh token
            access_json = await self.redis.get(f"{self.ACCESS_SESSION_PREFIX}{access_id}")
            if access_json:
                try:
                    access_data = json.loads(access_json)
                    refresh_id = access_data.get("refresh_session_id")
                    
                    # 删除 access 和 refresh
                    keys_to_delete.append(f"{self.ACCESS_SESSION_PREFIX}{access_id}")
                    if refresh_id:
                        keys_to_delete.append(f"{self.REFRESH_SESSION_PREFIX}{refresh_id}")
                    
                    session_pair_count += 1
                except Exception:
                    # 如果解析失败，至少删除 access token
                    keys_to_delete.append(f"{self.ACCESS_SESSION_PREFIX}{access_id}")
            else:
                # access session 已经不存在，但还在列表中（清理）
                keys_to_delete.append(f"{self.ACCESS_SESSION_PREFIX}{access_id}")
        
        # 删除用户会话列表
        keys_to_delete.append(user_sessions_key)
        
        if keys_to_delete:
            await cast(Awaitable[Any], self.redis.delete(*keys_to_delete))
        
        return session_pair_count
    
    async def get_user_sessions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        获取用户的所有活跃 Session
        
        Args:
            user_id: 用户 ID
        
        Returns:
            Session 列表（每个元素包含 access 和 refresh 信息）
        """
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
        # auth:user:sessions 只存储 access token IDs
        access_session_ids = await cast(Awaitable[Any], self.redis.smembers(user_sessions_key))
        
        if not access_session_ids:
            return []
        
        sessions = []
        invalid_session_ids = []
        
        for access_id in access_session_ids:
            # 读取 access session
            access_json = await self.redis.get(f"{self.ACCESS_SESSION_PREFIX}{access_id}")
            
            if access_json:
                try:
                    access_data = json.loads(access_json)
                    refresh_id = access_data.get("refresh_session_id")
                    
                    # 构建完整的会话信息
                    session_info = {
                        "access_session": access_data,
                        "access_token": access_id,
                        "refresh_token": refresh_id,
                        # 便于前端展示的字段
                        "client_ip": access_data.get("client_ip"),
                        "user_agent": access_data.get("user_agent"),
                        "created_at": access_data.get("created_at"),
                        "expires_at": access_data.get("expires_at"),
                    }
                    sessions.append(session_info)
                except Exception:
                    # 解析失败，标记为无效
                    invalid_session_ids.append(access_id)
            else:
                # access session 已过期或被删除
                invalid_session_ids.append(access_id)
        
        # 清理无效的 session ID
        if invalid_session_ids:
            await cast(Awaitable[Any], self.redis.srem(user_sessions_key, *invalid_session_ids))
        
        return sessions
    
    async def update_user_info_in_sessions(
        self,
        user_id: UUID,
        user_info: Dict[str, Any]
    ) -> int:
        """
        更新用户所有 access session 中的用户信息缓存
        
        当用户修改个人信息（昵称、邮箱、头像等）后，需要更新所有活跃 session 中的缓存
        
        Args:
            user_id: 用户 ID
            user_info: 新的用户信息
        
        Returns:
            更新的 session 数量
        """
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
        # 获取所有 access session IDs
        access_session_ids = await cast(Awaitable[Any], self.redis.smembers(user_sessions_key))
        
        if not access_session_ids:
            return 0
        
        updated_count = 0
        
        for access_id in access_session_ids:
            # 读取 access session
            access_json = await self.redis.get(f"{self.ACCESS_SESSION_PREFIX}{access_id}")
            
            if access_json:
                try:
                    access_data = json.loads(access_json)
                    
                    # 更新用户信息
                    access_data["user"] = user_info
                    
                    # 获取剩余 TTL
                    ttl = await self.redis.ttl(f"{self.ACCESS_SESSION_PREFIX}{access_id}")
                    
                    if ttl > 0:
                        # 重新写入 Redis（保持原有的 TTL）
                        await self.redis.setex(
                            f"{self.ACCESS_SESSION_PREFIX}{access_id}",
                            ttl,
                            json.dumps(access_data)
                        )
                        updated_count += 1
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to update user info in session {access_id}: {e}")
        
        return updated_count


class SessionService:
    """
    Session 服务
    
    职责：
    1. 创建 Session
    2. 验证 Session
    3. 刷新 Session
    4. 撤销 Session
    
    纯 Redis Session 方案，不使用 JWT
    """
    
    def __init__(self, session_store: SessionStore):
        self.session_store = session_store
    
    async def create_access_session(
        self,
        user_id: UUID,
        tenant_id: UUID,
        client_ip: str,
        user_agent: Optional[str] = None,
        scope: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建 Access Session
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            client_ip: 客户端 IP
            user_agent: User-Agent
            scope: 权限范围
            metadata: 额外元数据
            user_info: 用户信息（用于缓存，避免每次请求查数据库）
        
        Returns:
            Session ID（作为 access token 使用）
        """
        return await self.session_store.create_session(
            session_type=SessionType.ACCESS,
            user_id=user_id,
            tenant_id=tenant_id,
            client_ip=client_ip,
            user_agent=user_agent,
            scope=scope,
            metadata=metadata,
            user_info=user_info,
        )
    
    async def create_refresh_session(
        self,
        user_id: UUID,
        tenant_id: UUID,
        client_ip: str,
        user_agent: Optional[str] = None,
        scope: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建 Refresh Session
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            client_ip: 客户端 IP
            user_agent: User-Agent
            scope: 权限范围
            metadata: 额外元数据
        
        Returns:
            Session ID（作为 refresh token 使用）
        """
        return await self.session_store.create_session(
            session_type=SessionType.REFRESH,
            user_id=user_id,
            tenant_id=tenant_id,
            client_ip=client_ip,
            user_agent=user_agent,
            scope=scope,
            metadata=metadata,
        )
    
    async def create_session_pair(
        self,
        user_id: UUID,
        tenant_id: UUID,
        client_ip: str,
        user_agent: Optional[str] = None,
        scope: Optional[List[str]] = None,
        token_family_id: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None,
        custom_access_expire: Optional[timedelta] = None,  # 🔥 新增
        custom_refresh_expire: Optional[timedelta] = None,  # 🔥 新增
    ) -> Dict[str, Any]:
        """
        创建 Session 对（Access + Refresh）
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            client_ip: 客户端 IP
            user_agent: User-Agent
            scope: 权限范围
            token_family_id: Token 家族 ID（用于重放检测）
            user_info: 用户信息（缓存在 access session 中）
            custom_access_expire: 自定义 access 过期时间（可选）
            custom_refresh_expire: 自定义 refresh 过期时间（可选）
        
        Returns:
            包含 access_token 和 refresh_token 的字典
        """
        from uuid import uuid4
        
        # 如果没有提供 token_family_id，生成一个新的
        if not token_family_id:
            token_family_id = str(uuid4())
        
        # 创建 refresh session（先创建，因为 access 需要引用它）
        refresh_token = await self.session_store.create_session(
            session_type=SessionType.REFRESH,
            user_id=user_id,
            tenant_id=tenant_id,
            client_ip=client_ip,
            user_agent=user_agent,
            scope=scope,
            metadata={"token_family_id": token_family_id},
            custom_refresh_expire=custom_refresh_expire,  # 🔥 传递自定义过期时间
        )
        
        # 创建 access session，并关联 refresh session
        access_token = await self.session_store.create_session(
            session_type=SessionType.ACCESS,
            user_id=user_id,
            tenant_id=tenant_id,
            client_ip=client_ip,
            user_agent=user_agent,
            scope=scope,
            metadata={
                "refresh_session_id": refresh_token,
                "token_family_id": token_family_id,
            },
            user_info=user_info,  # 🔥 传递用户信息
            custom_access_expire=custom_access_expire,  # 🔥 传递自定义过期时间
        )
        
        # 在 refresh session 中也存储 access session（双向关联）
        refresh_session = await self.session_store.read_session(refresh_token)
        if refresh_session:
            refresh_session["access_session_id"] = access_token
            # 🔥 使用自定义过期时间或默认值
            refresh_expire = custom_refresh_expire or self.session_store.REFRESH_SESSION_EXPIRE
            ttl = int(refresh_expire.total_seconds())
            await self.session_store.redis.setex(
                f"{self.session_store.REFRESH_SESSION_PREFIX}{refresh_token}",
                ttl,
                json.dumps(refresh_session),
            )
        
        # 🔥 返回时使用实际的过期时间
        access_expire = custom_access_expire or self.session_store.ACCESS_SESSION_EXPIRE
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(access_expire.total_seconds()),  # 🔥 使用实际过期时间
            "scope": " ".join(scope) if scope else None,
        }
    
    async def verify_session(self, session_id: str) -> Dict[str, Any]:
        """
        验证 Session
        
        Args:
            session_id: Session ID
        
        Returns:
            Session 数据
        
        Raises:
            InvalidTokenException: Session 无效
            TokenExpiredException: Session 已过期
        """
        session_data = await self.session_store.read_session(session_id)
        
        if not session_data:
            raise InvalidTokenException("Session not found or has been revoked")
        
        return session_data
    
    async def refresh_session(
        self,
        refresh_session_id: str,
        client_ip: str,
        user_agent: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        刷新 Session（实现 Refresh Token 轮换 + 重放检测）
        
        Args:
            refresh_session_id: Refresh Session ID
            client_ip: 客户端 IP
            user_agent: User-Agent
            user_info: 用户信息（用于缓存在新的 access session 中）
        
        Returns:
            新的 session 对
        
        安全措施：
        - Refresh Token 轮换：每次刷新后，旧的 refresh session 被撤销
        - 重放检测：如果旧的 refresh token 被再次使用，撤销整个 token 家族
        - 并发控制：使用分布式锁防止同一 refresh token 被并发使用
        - IP/UA 变化监控：记录 IP 和 User-Agent 变化（警告但不阻止）
        """
        # 使用分布式锁防止并发刷新
        lock_key = f"{self.session_store.REFRESH_LOCK_PREFIX}{refresh_session_id}"
        lock_value = secrets.token_urlsafe(16)
        lock_ttl = 10  # 🔥 延长锁的过期时间到 10 秒（防止慢请求导致的误判）
        
        # 尝试获取锁（SETNX）
        lock_acquired = await self.session_store.redis.set(
            lock_key,
            lock_value,
            nx=True,  # 只在 key 不存在时设置
            ex=lock_ttl
        )
        
        if not lock_acquired:
            # 锁已被其他请求持有，说明正在并发刷新
            # 🔥 返回更友好的错误信息
            raise InvalidTokenException(
                "Refresh token is being used by another request. "
                "Please wait a moment and try again."
            )
        
        try:
            # 检查 refresh token 是否已被使用过（重放检测）
            revoked_key = f"{self.session_store.REFRESH_REVOKED_PREFIX}{refresh_session_id}"
            is_revoked = await self.session_store.redis.get(revoked_key)
            
            if is_revoked:
                # 这个 refresh token 已经被使用过并轮换了，但现在又被使用
                # 这是重放攻击的迹象！
                import logging
                logger = logging.getLogger(__name__)
                
                # 解析被撤销的 token 信息
                try:
                    revoked_info = json.loads(is_revoked)
                    user_id = revoked_info.get("user_id")
                    token_family_id = revoked_info.get("token_family_id")
                    
                    logger.warning(
                        f"Refresh token replay attack detected! "
                        f"refresh_session_id={refresh_session_id}, "
                        f"user_id={user_id}, "
                        f"token_family_id={token_family_id}, "
                        f"client_ip={client_ip}"
                    )
                    
                    # 撤销整个 token 家族（所有相关 session）
                    if token_family_id:
                        await self._revoke_token_family(token_family_id)
                        logger.warning(f"Revoked entire token family: {token_family_id}")
                    
                    # 如果有 user_id，撤销该用户的所有 session（更激进的安全措施）
                    if user_id:
                        await self.revoke_all_user_sessions(UUID(user_id))
                        logger.warning(f"Revoked all sessions for user: {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error handling token replay: {e}")
                
                raise InvalidTokenException(
                    "Refresh token has already been used. "
                    "All sessions have been revoked for security reasons. "
                    "Please login again."
                )
            
            # 验证 refresh session
            session_data = await self.verify_session(refresh_session_id)
            
            if session_data.get("session_type") != SessionType.REFRESH:
                raise InvalidTokenException("Invalid session type")
            
            user_id = UUID(session_data["user_id"])
            tenant_id = UUID(session_data["tenant_id"])
            scope = session_data.get("scope", [])
            token_family_id = session_data.get("token_family_id")
            
            # 如果没有 token_family_id，生成一个（向后兼容）
            if not token_family_id:
                from uuid import uuid4
                token_family_id = str(uuid4())
            
            # 🔥 新增：验证 IP 和 User-Agent（监控但不阻止）
            original_ip = session_data.get("client_ip")
            original_ua = session_data.get("user_agent")
            
            import logging
            logger = logging.getLogger(__name__)
            
            if original_ip and original_ip != client_ip:
                logger.warning(
                    f"IP changed during token refresh: "
                    f"original={original_ip}, current={client_ip}, "
                    f"user_id={user_id}, token_family_id={token_family_id}"
                )
            
            if original_ua and original_ua != user_agent:
                logger.warning(
                    f"User-Agent changed during token refresh: "
                    f"original={original_ua[:50]}..., current={user_agent[:50] if user_agent else 'None'}..., "
                    f"user_id={user_id}, token_family_id={token_family_id}"
                )
            
            # 标记这个 refresh token 为已使用（存储 7 天，与 refresh token 有效期一致）
            # 🔥 修复：使用 UTC 时间并确保时区信息正确
            revoked_at = datetime.now(timezone.utc)
            revoked_info = {
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "token_family_id": token_family_id,
                "revoked_at": revoked_at.isoformat(),
                "client_ip": client_ip,
            }
            await self.session_store.redis.setex(
                revoked_key,
                int(self.session_store.REFRESH_SESSION_EXPIRE.total_seconds()),
                json.dumps(revoked_info)
            )
            
            # 撤销旧的 access session
            old_access_session_id = session_data.get("access_session_id")
            if old_access_session_id:
                await self.revoke_session(old_access_session_id)
            
            # 撤销旧的 refresh session
            await self.revoke_session(refresh_session_id)
            
            # 🔥 创建新的 session 对（继承 token_family_id，传入 user_info）
            new_session_data = await self.create_session_pair(
                user_id=user_id,
                tenant_id=tenant_id,
                client_ip=client_ip,
                user_agent=user_agent,
                scope=scope,
                token_family_id=token_family_id,
                user_info=user_info,  # 传入用户信息
            )
            
            return new_session_data
            
        finally:
            # 释放锁（使用 Lua 脚本确保只删除自己的锁）
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            await cast(Awaitable[Any], self.session_store.redis.eval(lua_script, 1, lock_key, lock_value))
    
    async def _revoke_token_family(self, token_family_id: str) -> int:
        """
        撤销整个 token 家族
        
        Args:
            token_family_id: Token 家族 ID
        
        Returns:
            撤销的 session 数量
        """
        # 查找所有属于这个家族的 session
        # 使用 Redis SCAN 遍历所有 session key
        cursor = 0
        revoked_count = 0
        
        # 🔥 扫描两个前缀
        for prefix in [self.session_store.ACCESS_SESSION_PREFIX, self.session_store.REFRESH_SESSION_PREFIX]:
            pattern = f"{prefix}*"
            cursor = 0
            
            while True:
                cursor, keys = await self.session_store.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                for key in keys:
                    try:
                        session_json = await self.session_store.redis.get(key)
                        if session_json:
                            session_data = json.loads(session_json)
                            if session_data.get("token_family_id") == token_family_id:
                                # 删除这个 session
                                await self.session_store.redis.delete(key)
                                revoked_count += 1
                    except Exception:
                        pass
                
                if cursor == 0:
                    break
        
        return revoked_count
    
    async def revoke_session(self, session_id: str) -> bool:
        """
        撤销 Session
        
        Args:
            session_id: Session ID
        
        Returns:
            是否成功撤销
        """
        return await self.session_store.remove_session(session_id)
    
    async def revoke_all_user_sessions(self, user_id: UUID) -> int:
        """
        撤销用户的所有 Session
        
        Args:
            user_id: 用户 ID
        
        Returns:
            撤销的 session 数量
        """
        return await self.session_store.remove_user_sessions(user_id)
    
    async def get_user_active_sessions(
        self,
        user_id: UUID,
        current_session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取用户的活跃会话（用于会话管理页面）
        
        Args:
            user_id: 用户 ID
            current_session_id: 当前会话 ID（用于标记当前设备）
        
        Returns:
            会话列表，每个会话包含：
            - session_id: 会话 ID
            - user_agent: User-Agent 字符串
            - client_ip: 客户端 IP
            - created_at: 创建时间
            - last_active_at: 最后活跃时间（使用 expires_at 推算）
            - is_current: 是否为当前会话
        """
        sessions = await self.session_store.get_user_sessions(user_id)
        
        result = []
        for session in sessions:
            access_data = session.get("access_session", {})
            access_token = session.get("access_token")
            
            # 计算最后活跃时间（使用 expires_at 推算）
            created_at_str = access_data.get("created_at")
            expires_at_str = access_data.get("expires_at")
            
            # 最后活跃时间 = 当前时间（如果未过期）或创建时间
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                now = datetime.now(timezone.utc)
                if now < expires_at:
                    # 未过期，最后活跃时间 = 当前时间
                    last_active_at = now.isoformat()
                else:
                    # 已过期（理论上不应该出现），使用创建时间
                    last_active_at = created_at_str
            else:
                last_active_at = created_at_str
            
            result.append({
                "session_id": access_token,
                "user_agent": access_data.get("user_agent", ""),
                "client_ip": access_data.get("client_ip", ""),
                "created_at": created_at_str,
                "last_active_at": last_active_at,
                "is_current": access_token == current_session_id if current_session_id else False
            })
        
        # 按最后活跃时间倒序排序
        result.sort(key=lambda x: x["last_active_at"], reverse=True)
        
        return result
    
    async def revoke_other_sessions(
        self,
        user_id: UUID,
        current_session_id: str
    ) -> int:
        """
        注销用户所有其他会话（保留当前会话）
        
        Args:
            user_id: 用户 ID
            current_session_id: 当前会话 ID（不会被注销）
        
        Returns:
            注销的会话数量
        """
        sessions = await self.session_store.get_user_sessions(user_id)
        revoked_count = 0
        
        for session in sessions:
            access_token = session.get("access_token")
            if access_token and access_token != current_session_id:
                # 注销这个会话（会同时删除 access 和 refresh）
                await self.revoke_session(access_token)
                revoked_count += 1
        
        return revoked_count
    
    async def update_user_info_in_all_sessions(
        self,
        user_id: UUID,
        user_info: Dict[str, Any]
    ) -> int:
        """
        更新用户所有 session 中的用户信息缓存
        
        当用户修改个人信息后调用此方法，更新所有活跃 session 中的缓存
        
        Args:
            user_id: 用户 ID
            user_info: 新的用户信息字典，应包含：
                - id: 用户 ID
                - username: 用户名
                - email: 邮箱
                - nickname: 昵称
                - avatar_url: 头像 URL
                - is_active: 是否激活
                - is_superuser: 是否超级管理员
        
        Returns:
            更新的 session 数量
        """
        return await self.session_store.update_user_info_in_sessions(user_id, user_info)
    
    async def refresh_user_info_in_sessions(
        self,
        user: "User"
    ) -> int:
        """
        刷新用户在所有 session 中的完整信息（包括角色和权限）
        
        该方法会：
        1. 从 user 对象读取 roles 和 permissions 属性
        2. 构建完整的 user_info 字典
        3. 更新所有活跃 session 中的缓存
        
        使用场景：
        - /me 接口：用户刷新页面时同步最新的角色和权限
        - 角色变更后：管理员修改用户角色，需要立即生效
        - 权限调整后：角色权限被修改，需要同步到所有在线用户
        
        Args:
            user: User 对象，必须包含：
                - id: 用户 ID
                - username: 用户名
                - email: 邮箱
                - nickname: 昵称
                - avatar_url: 头像 URL
                - is_active: 是否激活
                - is_superuser: 是否超级管理员
                - tenant_id: 租户 ID
                - roles: 角色代码列表（必须在调用前设置）
                - permissions: 权限代码列表（必须在调用前设置）
        
        Returns:
            更新的 session 数量
        
        Example:
            ```python
            # 先查询角色和权限
            user.roles = await role_service.get_user_role_codes(...)
            user.permissions = await permission_service.get_user_permissions_with_user(...)
            
            # 然后更新 session
            updated_count = await session_service.refresh_user_info_in_sessions(user)
            logger.info(f"Updated {updated_count} sessions")
            ```
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # 🔥 直接从 user 对象读取角色和权限（调用方已经查询并设置）
            role_codes = getattr(user, 'roles', [])
            permission_codes = getattr(user, 'permissions', [])
            
            # 🔥 准备完整的用户信息（包含角色和权限）
            user_info = {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "nickname": user.nickname,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "avatar_url": user.avatar_url,
                "roles": role_codes,  # 🔥 角色信息
                "permissions": permission_codes,  # 🔥 权限信息
            }
            
            # 🔥 更新所有活跃 session 中的缓存
            updated_count = await self.update_user_info_in_all_sessions(
                user.id,
                user_info
            )
            
            logger.info(
                f"Refreshed user info in {updated_count} sessions for user {user.username} "
                f"(roles: {len(role_codes)}, permissions: {len(permission_codes)})"
            )
            
            return updated_count
            
        except Exception as e:
            logger.error(
                f"Failed to refresh user info in sessions for user {user.id}: {e}",
                exc_info=True
            )
            raise
