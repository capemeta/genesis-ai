"""
认证 API
登录、Token 刷新、会话管理等
基于 Redis Session 存储，支持 OAuth 2.0 标准端点

🔥 双模式认证支持：
1. Cookie 模式（HttpOnly + SameSite）- 更安全，防止 XSS
2. Bearer Token 模式（localStorage）- 更灵活，适合移动端/API

登录接口会同时设置 Cookie 和返回 token，前端可以选择使用哪种方式
认证中间件会优先从 Cookie 读取，其次从 Authorization Header 读取
"""
import logging

from fastapi import APIRouter, Depends, Request, Response, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.database import get_async_session, get_redis
from core.config import settings
from core.security import (
    authenticate_user,
    update_last_login,
    get_current_user,
    get_session_service,
    RateLimiter,
    CaptchaService,
)
from core.security.token_store import SessionService
from core.security.oauth2 import TokenResponse, Scope
from core.exceptions import InvalidCredentialsException, TooManyRequestsException, BadRequestException
from core.response import ResponseBuilder
from schemas.auth import Token, LoginRequest
from models.user import User
from services.auth_service import AuthService
from services.permission_service import PermissionService
from utils.request_utils import get_client_ip

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login")
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_session),
    redis: Redis = Depends(get_redis),
    session_service: SessionService = Depends(get_session_service),
):
    """
    用户登录（密码模式）
    
    🔥 双模式支持：
    - 同时设置 HttpOnly Cookie（防止 XSS）
    - 同时返回 token 到响应体（兼容 localStorage）
    - 前端可以选择使用 Cookie 或 Bearer Token
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    - **remember**: 是否记住我（影响过期时间）
    - **captcha_token**: 验证码令牌（必填）
    - **captcha_code**: 验证码（必填）
    
    安全措施：
    - 🔥 始终要求验证码（增强安全性）
    - 登录失败 5 次后锁定 15 分钟
    - 记录登录 IP 和时间
    - Session 存储在 Redis 中，支持快速撤销
    - Cookie 使用 HttpOnly + SameSite 防止 XSS 和 CSRF
    """
    rate_limiter = RateLimiter(redis)
    captcha_service = CaptchaService(redis)
    
    # 获取真实 IP
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    
    # 🔥 始终要求验证码
    if not login_data.captcha_token or not login_data.captcha_code:
        raise BadRequestException("请输入验证码")
    
    # 验证验证码
    captcha_valid = await captcha_service.verify_captcha(
        token=login_data.captcha_token,
        user_input=login_data.captcha_code,
        case_sensitive=False,
    )
    
    if not captcha_valid:
        await captcha_service.record_captcha_failure(client_ip)
        raise BadRequestException("验证码错误或已过期")
    
    # 检查登录尝试次数（用户名 + IP 双重限制）
    identifier = f"{login_data.username}:{client_ip}"
    allowed, ttl = await rate_limiter.check_login_attempts(identifier, max_attempts=5, lockout_minutes=15)
    
    if not allowed:
        raise TooManyRequestsException(
            f"登录尝试次数过多，账户已被锁定，请在 {ttl} 秒后重试"
        )
    
    # 验证用户凭证
    user = await authenticate_user(
        login_data.username,
        login_data.password,
        db,
    )
    
    if not user:
        # 记录登录失败
        await rate_limiter.record_login_failure(identifier, lockout_minutes=15)
        await captcha_service.record_captcha_failure(client_ip)
        raise InvalidCredentialsException("用户名或密码错误")
    
    # 登录成功，清除失败记录
    await rate_limiter.clear_login_attempts(identifier)
    await captcha_service.clear_captcha_attempts(client_ip)
    
    # 更新最后登录信息
    await update_last_login(user, client_ip, db)
    
    auth_service = AuthService(db)
    session_data = await auth_service.create_session_payload(
        user=user,
        session_service=session_service,
        client_ip=client_ip,
        user_agent=user_agent,
        remember=login_data.remember,
    )
    
    # 🔥 设置 HttpOnly Cookie（同时支持 Cookie 和 Bearer Token 模式）
    # 检测是否在 HTTPS 环境
    is_secure = request.url.scheme == "https"
    
    # 🔥 计算正确的 path（考虑 ROOT_PATH）
    root_path = settings.ROOT_PATH.rstrip("/")
    refresh_path = f"{root_path}/api/v1/auth/refresh" if root_path else "/api/v1/auth/refresh"
    refresh_max_age = (
        settings.REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER * 24 * 3600
        if login_data.remember
        else settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )
    
    # 设置 Access Token Cookie
    response.set_cookie(
        key="access_token",
        value=session_data["access_token"],
        max_age=session_data["expires_in"],
        httponly=True,           # 🔥 防止 JavaScript 读取，防止 XSS 攻击
        secure=is_secure,        # HTTPS 环境下启用（HTTP 下必须为 False）
        samesite="lax",          # 🔥 防止 CSRF 攻击（lax 允许顶级导航）
        path="/",                # 所有路径都可以访问
        domain=None,             # 自动使用当前域名
    )
    
    # 设置 Refresh Token Cookie（更严格的限制）
    response.set_cookie(
        key="refresh_token",
        value=session_data["refresh_token"],
        max_age=refresh_max_age,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path=refresh_path,  # 🔥 只在刷新接口可用，考虑 ROOT_PATH
        domain=None,
    )
    
    logger.info(
        f"User {user.username} logged in successfully from {client_ip} "
        f"(HTTPS: {is_secure}, Remember: {login_data.remember})"
    )
    
    # 🔥 同时返回 token 到响应体（兼容 localStorage 模式）
    return ResponseBuilder.build_success(
        data=Token(**session_data).model_dump(),
        message="登录成功"
    )


@router.post("/register", status_code=status.HTTP_403_FORBIDDEN)
async def register(
):
    """
    自助注册入口已关闭

    当前平台账号由后台管理员统一创建，
    前端和开放接口均不提供用户自助注册。
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="当前环境未开放自助注册，请联系管理员创建账号",
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_session),
    session_service: SessionService = Depends(get_session_service),
):
    """
    用户登出
    
    双模式支持：
    - 清除 HttpOnly Cookie
    - 从 Redis 中删除 session
    - 返回成功响应（前端可以清除 localStorage）
    
    功能：
    - 从 Redis 中删除 access session 和关联的 refresh session（立即失效）
    - 清除 Cookie（如果使用 Cookie 模式）
    - 记录登出事件（审计日志）
    
    安全措施：
    - 同时撤销 access 和 refresh session，防止 refresh token 继续使用
    - 即使 access session 已过期或无效，也能正确清除 Cookie 并返回成功
    - 允许无效 session 调用（避免前端因 session 失效导致 logout 死循环）
    - 即使撤销失败，也返回成功（前端会清除 token）
    """
    auth_service = AuthService(db)
    await auth_service.logout(
        request=request,
        session_service=session_service,
    )
    
    # 始终清除 Cookie（无论 session 是否有效）
    root_path = settings.ROOT_PATH.rstrip("/")
    refresh_path = f"{root_path}/api/v1/auth/refresh" if root_path else "/api/v1/auth/refresh"
    
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path=refresh_path)
    
    # 始终返回成功
    return ResponseBuilder.build_success(
        message="登出成功"
    )



@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    session_service: SessionService = Depends(get_session_service),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_async_session),
):
    """
    刷新 Access Token
    
    🔥 Cookie 模式（推荐）：
    - 从 Cookie 中读取 refresh_token（HttpOnly，更安全）
    - 浏览器自动携带 Cookie，前端无需处理
    
    🔥 Bearer Token 模式（兼容）：
    - 从请求体读取 refresh_token
    - 适用于移动端或无法使用 Cookie 的场景
    
    功能：
    - 使用 Refresh Session 获取新的 Access Session
    - 旧的 Access Session 会被撤销
    - 返回新的 session 对
    - 🔥 刷新时重新查询用户信息，确保数据最新
    
    安全措施：
    - Rate limiting 防止暴力破解
    - 验证 session 类型
    - Token 轮换和重放检测
    """
    # 🔥 新增：Rate limiting 防止刷新接口被滥用
    from core.security import RateLimiter
    rate_limiter = RateLimiter(redis)
    
    client_ip = get_client_ip(request)
    identifier = f"refresh:{client_ip}"
    
    # 每分钟最多 20 次刷新请求（放宽限制，区分正常过期和恶意刷新）
    allowed, ttl = await rate_limiter.check_login_attempts(
        identifier, 
        max_attempts=20, 
        lockout_minutes=1  # 锁定 1 分钟（原逻辑不变，主要优化是次数上限和错误区分）
    )
    
    if not allowed:
        raise TooManyRequestsException(
            f"Too many refresh requests. Please try again in {ttl} seconds"
        )
    
    user_agent = request.headers.get("User-Agent")
    
    # 🔥 Cookie 模式（优先）：从 Cookie 读取 refresh_token
    refresh_token_value = request.cookies.get("refresh_token")
    
    # 🔥 Bearer Token 模式（兼容）：从请求体读取
    if not refresh_token_value:
        # 尝试从请求体读取（兼容旧的 Bearer Token 模式）
        try:
            body = await request.json()
            refresh_token_value = body.get("refresh_token")
        except Exception:
            pass
    
    if not refresh_token_value:
        raise InvalidCredentialsException("Missing refresh token (not found in Cookie or request body)")
    
    try:
        auth_service = AuthService(db)
        session_data, user, is_remember = await auth_service.refresh_session_payload(
            refresh_session_id=refresh_token_value,
            session_service=session_service,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        
        # 刷新成功，清除失败记录
        await rate_limiter.clear_login_attempts(identifier)
        
        # 🔥 设置新的 Cookie（如果原来使用 Cookie 模式）
        if request.cookies.get("refresh_token") or request.cookies.get("access_token"):
            is_secure = request.url.scheme == "https"
            
            if is_remember:
                refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER * 24 * 3600
            else:
                refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
            
            # 🔥 计算正确的 path（考虑 ROOT_PATH）
            root_path = settings.ROOT_PATH.rstrip("/")
            refresh_path = f"{root_path}/api/v1/auth/refresh" if root_path else "/api/v1/auth/refresh"
            
            # 设置新的 Access Token Cookie
            response.set_cookie(
                key="access_token",
                value=session_data["access_token"],
                max_age=session_data["expires_in"],
                httponly=True,
                secure=is_secure,
                samesite="lax",
                path="/",
            )
            
            # 设置新的 Refresh Token Cookie
            response.set_cookie(
                key="refresh_token",
                value=session_data["refresh_token"],
                max_age=refresh_max_age,
                httponly=True,
                secure=is_secure,
                samesite="lax",
                path=refresh_path,  # 🔥 考虑 ROOT_PATH
            )
            
            logger.info(
                f"Token refreshed successfully for user {user.id} from {client_ip} "
                f"(HTTPS: {is_secure}, Cookie mode, Remember: {is_remember})"
            )
        
        return ResponseBuilder.build_success(
            data=Token(**session_data).model_dump(),
            message="Token 刷新成功"
        )
        
    except Exception as e:
        error_msg = str(e)
        # 区分 session 正常过期和恶意刷新：
        # session 过期属于正常情况，不记录失败次数，避免误触限流
        if "Session not found" not in error_msg and "has been revoked" not in error_msg:
            await rate_limiter.record_login_failure(identifier, lockout_minutes=1)
        raise InvalidCredentialsException(f"Failed to refresh session: {error_msg}")


@router.post("/logout-all", status_code=status.HTTP_200_OK)
async def logout_all_devices(
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    """
    登出所有设备
    
    功能：
    - 撤销用户的所有 Session
    - 强制所有设备重新登录
    
    使用场景：
    - 密码被盗用
    - 设备丢失
    - 安全审计
    """
    # 撤销所有 session
    revoked_count = await session_service.revoke_all_user_sessions(current_user.id)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"User {current_user.id} logged out from all devices, "
        f"revoked {revoked_count} sessions"
    )
    
    return ResponseBuilder.build_success(
        data={"revoked_count": revoked_count},
        message=f"已登出所有设备，撤销了 {revoked_count} 个 session"
    )


@router.get("/sessions")
async def list_active_sessions(
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    """
    查看活跃会话
    
    功能：
    - 查看用户的所有活跃 session
    - 显示登录设备、IP、时间等信息
    
    使用场景：
    - 安全审计
    - 查看登录设备
    - 发现异常登录
    """
    # 获取所有活跃 session
    sessions = await session_service.get_user_active_sessions(current_user.id)
    
    # 格式化返回数据
    formatted_sessions = []
    for session in sessions:
        formatted_sessions.append({
            "session_id": session.get("session_id"),
            "type": session.get("session_type"),
            "client_ip": session.get("client_ip"),
            "user_agent": session.get("user_agent"),
            "created_at": session.get("created_at"),
            "expires_at": session.get("expires_at"),
        })
    
    return ResponseBuilder.build_success(
        data={
            "sessions": formatted_sessions,
            "total": len(formatted_sessions)
        },
        message="获取会话列表成功"
    )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    """
    撤销指定会话
    
    功能：
    - 撤销指定的 session
    - 强制该设备重新登录
    
    使用场景：
    - 发现异常登录
    - 远程登出某个设备
    """
    # 验证 session 是否属于当前用户
    sessions = await session_service.get_user_active_sessions(current_user.id)
    session_found = False
    
    for session in sessions:
        if session.get("session_id") == session_id:
            session_found = True
            break
    
    if not session_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or does not belong to you",
        )
    
    # 撤销 session
    await session_service.revoke_session(session_id)
    
    return ResponseBuilder.build_success(
        message="会话已撤销"
    )



@router.post("/token")
async def oauth2_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_async_session),
    redis: Redis = Depends(get_redis),
    session_service: SessionService = Depends(get_session_service),
):
    """
    OAuth 2.0 标准 Token 端点
    
    支持的 grant_type:
    - password: 密码模式（当前实现）
    - refresh_token: 刷新令牌（未来实现）
    - authorization_code: 授权码模式（未来实现）
    - client_credentials: 客户端凭证模式（未来实现）
    
    符合 RFC 6749 (OAuth 2.0) 规范
    """
    rate_limiter = RateLimiter(redis)
    
    # 获取客户端信息
    client_ip = get_client_ip(request) if request else "unknown"
    user_agent = request.headers.get("User-Agent") if request else None
    
    # 检查登录尝试次数
    identifier = f"{form_data.username}:{client_ip}"
    allowed, ttl = await rate_limiter.check_login_attempts(identifier, max_attempts=5, lockout_minutes=15)
    
    if not allowed:
        raise TooManyRequestsException(
            f"Too many login attempts. Please try again in {ttl} seconds"
        )
    
    # 验证用户凭证
    user = await authenticate_user(
        form_data.username,
        form_data.password,
        db,
    )
    
    if not user:
        await rate_limiter.record_login_failure(identifier, lockout_minutes=15)
        raise InvalidCredentialsException("Invalid username or password")
    
    # 登录成功
    await rate_limiter.clear_login_attempts(identifier)
    await update_last_login(user, client_ip, db)
    
    # 解析请求的 scope
    requested_scope = Scope.parse_scope_string(form_data.scopes) if form_data.scopes else []

    auth_service = AuthService(db)
    session_data = await auth_service.create_session_payload(
        user=user,
        session_service=session_service,
        client_ip=client_ip,
        user_agent=user_agent,
        requested_scope=requested_scope,
    )
    
    return ResponseBuilder.build_success(
        data=TokenResponse(**session_data).model_dump(),
        message="Token 获取成功"
    )



# ==================== 权限相关接口 ====================

@router.post("/user-permissions")
async def get_user_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取当前用户的所有权限代码（直接查询数据库，不使用缓存）
    
    返回用户拥有的所有权限代码列表，用于前端权限控制
    前端应该在登录时调用一次，然后缓存到 store 中
    
    Returns:
        权限代码列表，如 ["user:create", "user:update", "menu:system"]
    """
    service = PermissionService(db)
    permissions = await service.get_user_permissions_with_user(
        current_user,
        use_cache=False  # 🔥 不使用 Redis 缓存，直接查询数据库
    )
    
    return ResponseBuilder.build_success(
        data=permissions,
        message="获取权限列表成功"
    )


@router.post("/user-menus")
async def get_user_menus(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取当前用户的菜单权限（直接查询数据库，不使用缓存）
    
    前端应该在登录时调用一次，然后缓存到 store 中
    只在以下情况重新调用：
    - 首次登录
    - 页面刷新
    - 重新登录
    
    返回格式：
    ```json
    {
        "code": 200,
        "message": "查询成功",
        "data": [
            {
                "id": "uuid",
                "code": "menu:knowledge-base",
                "name": "知识库",
                "type": "menu",
                "path": "/knowledge-base",
                "icon": "Database",
                "sort_order": 10,
                "children": []
            }
        ]
    }
    ```
    
    逻辑：
    - 超级管理员（code=super_admin）：返回所有菜单
    - 普通用户：根据角色权限返回对应菜单
    - 自动补全父级菜单（如果有子菜单权限，父菜单也可见）
    """
    service = PermissionService(db)
    
    menus = await service.get_user_menu_permissions(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        use_cache=False  # 🔥 不使用 Redis 缓存，直接查询数据库
    )
    
    return ResponseBuilder.build_success(
        data=menus,
        message="获取菜单树成功"
    )


@router.post("/check-permission")
async def check_permission(
    permission_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    检查用户是否有指定权限（直接查询数据库，不使用缓存）
    
    Args:
        permission_code: 权限代码，如 "user:create"
    
    Returns:
        是否有权限
    """
    service = PermissionService(db)
    
    has_permission = await service.check_user_has_permission(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        permission_code=permission_code
    )
    
    return ResponseBuilder.build_success(
        data=has_permission,
        message="有权限" if has_permission else "无权限"
    )


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
    session_service: SessionService = Depends(get_session_service),
):
    """
    获取当前用户信息（包含角色和权限）
    
    返回格式：
    ```json
    {
        "code": 200,
        "message": "获取用户信息成功",
        "data": {
            "id": "uuid",
            "username": "admin",
            "email": "admin@example.com",
            "nickname": "管理员",
            "avatar_url": "https://...",
            "is_active": true,
            "is_superuser": false,
            "tenant_id": "uuid",
            "roles": ["super_admin", "admin"],
            "permissions": ["user:create", "user:update", "menu:system"]
        }
    }
    ```
    
    使用场景：
    - 登录成功后调用，获取用户完整信息
    - 页面刷新时调用，恢复用户状态
    - 前端应该缓存到 auth-store 中
    
    功能：
    - 🔥 重新查询最新的角色和权限信息
    - 🔥 更新所有活跃 session 中的用户信息缓存
    """
    auth_service = AuthService(db)
    try:
        user_data = await auth_service.build_me_payload(
            user=current_user,
            session_service=session_service,
        )
    except Exception as e:
        logger.error(f"Failed to refresh session cache: {e}", exc_info=True)
        raise
    
    return ResponseBuilder.build_success(
        data=user_data,
        message="获取用户信息成功"
    )
