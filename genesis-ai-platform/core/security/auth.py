"""
认证配置
基于 Redis Token 存储的统一认证系统
借鉴 Spring Security 设计理念，支持未来 OAuth 2.0 扩展
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from models.user import User
from core.database import get_async_session, get_redis
from core.security.crypto import verify_password, get_password_hash
from core.security.token_store import SessionStore, SessionService
from core.exceptions import UnauthorizedException, InvalidCredentialsException, TokenExpiredException, InvalidTokenException
from repositories.user_repo import UserRepository
from services.auth_service import AuthService


# HTTP Bearer 认证（可选，支持双模式）
# 🔥 auto_error=False 使其成为可选，允许从 Cookie 读取
security = HTTPBearer(auto_error=False)

# OAuth2 密码模式（兼容 OAuth 2.0）
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",  # OAuth 2.0 标准端点
    scopes={
        "read": "读取权限",
        "write": "写入权限",
        "admin": "管理员权限",
        "kb:read": "知识库读取",
        "kb:write": "知识库写入",
    },
    auto_error=False  # 🔥 可选，支持双模式
)


def get_session_service(redis: Redis = Depends(get_redis)) -> SessionService:
    """获取 Session 服务"""
    session_store = SessionStore(redis)
    return SessionService(session_store)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    session_service: SessionService = Depends(get_session_service),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """
    获取当前用户
    从 Redis 存储的 Session 中解析用户信息
    
    🔥 双模式支持：
    1. Cookie 模式：从 Cookie 读取 session_id（优先）
    2. Bearer Token 模式：从 Authorization Header 读取 session_id
    
    🔥 优化：优先从 session 缓存读取用户信息，减少数据库查询
    
    支持：
    1. Bearer Token 认证（Session ID）
    2. Session 验证和撤销
    3. 权限范围（Scope）检查
    4. 用户信息缓存（避免每次请求查数据库）
    """
    # 🔥 双模式支持：优先从 Cookie 读取，其次从 Header 读取
    session_id = None
    
    # 方式 1: 从 Cookie 读取（优先）
    session_id = request.cookies.get("access_token")
    
    # 方式 2: 从 Authorization Header 读取（兼容）
    if not session_id and credentials:
        session_id = credentials.credentials
    
    if not session_id:
        raise UnauthorizedException("Missing authentication credentials")
    
    try:
        # 验证 session
        session_data = await session_service.verify_session(session_id)
        
        user_id_raw = session_data.get("user_id")
        if user_id_raw is None:
            raise UnauthorizedException("Invalid session data")
        user_id = str(user_id_raw)
        
        # 🔥 优先从 session 中读取用户信息（缓存）
        cached_user_info = session_data.get("user")
        
        if cached_user_info:
            # 从缓存构建 User 对象（避免数据库查询）
            # 注意：这里创建的是一个"轻量级"的 User 对象，不是完整的 ORM 对象
            # 它包含了认证和授权所需的基本信息
            from datetime import datetime, timezone
            
            user = User()
            user.id = UUID(cached_user_info["id"])
            user.tenant_id = UUID(session_data["tenant_id"])
            user.username = cached_user_info["username"]
            user.email = cached_user_info.get("email")
            user.nickname = cached_user_info.get("nickname")
            # 🔥 修复：is_active 有 setter，可以赋值
            user.is_active = cached_user_info.get("is_active", True)
            # 🔥 修复：is_superuser 是只读属性，通过 _is_superuser 缓存
            user.__dict__["_is_superuser"] = cached_user_info.get("is_superuser", False)
            user.avatar_url = cached_user_info.get("avatar_url")
            
            # 🔥 新增：设置用户角色信息
            user.roles = cached_user_info.get("roles", [])
            
            # 🔥 新增：设置用户权限信息
            user.permissions = cached_user_info.get("permissions", [])
            
            # 🔥 修复：设置必需的时间戳字段（避免 Pydantic 验证失败）
            # 这些字段在响应序列化时需要
            user.created_at = datetime.now(timezone.utc)
            user.updated_at = datetime.now(timezone.utc)
            
            # 将 session scope 附加到用户对象
            user.__dict__["_token_scope"] = session_data.get("scope", [])
            
            return user
        
        # 🔥 降级方案：如果 session 中没有用户信息，从数据库查询
        # （兼容旧的 session 或 refresh session）
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"User info not found in session {session_id}, falling back to database query")
        
    except TokenExpiredException:
        raise UnauthorizedException("Session has expired")
    except InvalidTokenException as e:
        raise UnauthorizedException(f"Invalid session: {str(e)}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error validating session: {e}", exc_info=True)
        raise UnauthorizedException(f"Could not validate credentials: {str(e)}")
    
    # 从数据库获取用户（降级方案）
    user_repo = UserRepository(db)
    user_from_db = await user_repo.get(UUID(user_id))
    
    if user_from_db is None:
        raise UnauthorizedException("User not found")
    
    if not user_from_db.is_active:
        raise UnauthorizedException("Inactive user")
    
    # 将 session scope 附加到用户对象（用于权限检查）
    user_from_db.__dict__["_token_scope"] = session_data.get("scope", [])
    
    return user_from_db


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前激活用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前超级管理员"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def authenticate_user(
    username_or_email: str,
    password: str,
    db: AsyncSession,
) -> User | None:
    """
    验证用户凭证（防时序攻击版本）
    
    安全措施：
    - 即使用户不存在，也执行一次哈希验证，防止通过响应时间判断用户是否存在
    - 使用固定的 dummy hash 确保时间消耗一致
    
    Args:
        username_or_email: 用户名或邮箱
        password: 密码
        db: 数据库会话
    
    Returns:
        User 对象或 None
    """
    service = AuthService(db)
    return await service.authenticate_user(
        username_or_email=username_or_email,
        password=password,
    )


async def update_last_login(user: User, ip: str, db: AsyncSession) -> None:
    """
    更新用户最后登录信息
    
    Args:
        user: 用户对象
        ip: 登录 IP
        db: 数据库会话
    """
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip
    user.last_active_at = user.last_login_at
    user.failed_login_count = 0
    user.locked_until = None
    if user.activated_at is None:
        user.activated_at = user.last_login_at
    await db.commit()
    await db.refresh(user)



async def get_current_user_with_scope(
    required_scope: List[str],
    user: User = Depends(get_current_user),
) -> User:
    """
    获取当前用户并检查权限范围
    
    Args:
        required_scope: 需要的权限范围
        user: 当前用户
    
    Returns:
        用户对象
    
    Raises:
        HTTPException: 权限不足
    
    示例:
        @router.get("/admin")
        async def admin_only(
            user: User = Depends(lambda: get_current_user_with_scope(["admin"]))
        ):
            pass
    """
    token_scope = user.__dict__.get("_token_scope", [])
    
    # 检查是否有所需的任意一个权限
    if not any(scope in token_scope for scope in required_scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required: {required_scope}",
        )
    
    return user
