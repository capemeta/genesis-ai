"""
全局认证中间件
默认所有 API 都需要认证，白名单中的路径除外
基于纯 Redis Session 存储

🔥 双模式认证支持：
1. Cookie 模式（优先）：从 Cookie 中读取 access_token
2. Bearer Token 模式（兼容）：从 Authorization Header 读取

认证流程：
1. 跳过 OPTIONS 请求（CORS 预检）
2. 检查是否在白名单中
3. 优先从 Cookie 读取 token，其次从 Header 读取
4. 验证 Session 是否有效
5. 将用户信息存储到 request.state
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from core.exceptions import TokenExpiredException, InvalidTokenException
from core.config.settings import settings


# ==================== 白名单配置 ====================

def _build_public_paths() -> tuple:
    """
    构建公开路径集合和前缀列表
    自动根据 ROOT_PATH 配置生成带前缀和不带前缀的路径
    
    Returns:
        tuple: (公开路径集合, 公开路径前缀列表)
    """
    root_path = settings.ROOT_PATH.rstrip("/")
    
    # 基础公开路径（不带前缀）
    base_paths = [
        "/",                            # 根路径
        "/docs",                        # Swagger 文档
        "/redoc",                       # ReDoc 文档
        "/openapi.json",                # OpenAPI Schema
        "/api/v1/auth/login",           # 登录
        "/api/v1/auth/register",        # 注册
        "/api/v1/auth/refresh",         # 刷新 Token
        "/api/v1/password/forgot",      # 忘记密码
        "/api/v1/password/reset",       # 重置密码
        "/api/v1/captcha/create",       # 创建验证码
        "/api/v1/captcha/verify",       # 验证验证码
        "/api/v1/captcha/required",     # 检查是否需要验证码
        "/api/v1/health",               # 健康检查
    ]
    
    # 基础公开前缀（不带前缀）
    base_prefixes = [
        "/uploads/",                    # 静态文件（头像等）
        "/static/",                     # 静态文件
        "/public/",                     # 公开资源
        "/assets/",                     # 资源文件
        "/api/v1/captcha/image/",       # 验证码图片
        "/api/v1/documents/public/",    # 文档公开访问（图片外链）
    ]
    
    paths = set()
    prefixes = []
    
    # 添加不带前缀的路径
    paths.update(base_paths)
    prefixes.extend(base_prefixes)
    
    # 如果配置了 ROOT_PATH，添加带前缀的路径
    if root_path and root_path != "/":
        paths.add(root_path)  # 添加根路径本身
        for path in base_paths:
            if path == "/":
                continue  # 跳过根路径
            paths.add(f"{root_path}{path}")
        for prefix in base_prefixes:
            prefixes.append(f"{root_path}{prefix}")
    
    return paths, prefixes


def _build_public_prefixes() -> list:
    """
    已废弃：使用 _build_public_paths() 返回的第二个值
    """
    _, prefixes = _build_public_paths()
    return prefixes


# 🔥 延迟初始化：在首次访问时才生成白名单
# 避免在模块导入时就执行，此时 .env 可能还没加载
_PUBLIC_PATHS = None
_PUBLIC_PATH_PREFIXES = None


def get_public_paths() -> set:
    """获取公开路径集合（延迟初始化）"""
    global _PUBLIC_PATHS, _PUBLIC_PATH_PREFIXES
    if _PUBLIC_PATHS is None:
        _PUBLIC_PATHS, _PUBLIC_PATH_PREFIXES = _build_public_paths()
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Initialized public paths with ROOT_PATH={settings.ROOT_PATH}: {sorted(_PUBLIC_PATHS)}")
        logger.info(f"Initialized public prefixes: {_PUBLIC_PATH_PREFIXES}")
    return _PUBLIC_PATHS


def get_public_prefixes() -> list:
    """获取公开路径前缀列表（延迟初始化）"""
    global _PUBLIC_PATH_PREFIXES
    if _PUBLIC_PATH_PREFIXES is None:
        # 触发初始化
        get_public_paths()
    return _PUBLIC_PATH_PREFIXES


class AuthMiddleware(BaseHTTPMiddleware):
    """
    全局认证中间件
    
    功能：
    1. 检查请求路径是否在白名单中
    2. 验证 JWT Token
    3. 将用户信息存储到 request.state
    4. 统一处理认证异常
    """
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        path = request.url.path
        
        # 0. 跳过 OPTIONS 请求（CORS preflight）
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # 1. 检查是否在白名单中
        if self._is_public_path(path):
            return await call_next(request)
        
        # 2. 🔥 双模式支持：优先从 Cookie 读取，其次从 Header 读取
        session_id = None
        auth_mode = None
        
        # 方式 1: 从 Cookie 读取（优先，更安全）
        session_id = request.cookies.get("access_token")
        if session_id:
            auth_mode = "cookie"
        
        # 方式 2: 从 Authorization Header 读取（兼容 localStorage 模式）
        if not session_id:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                if not auth_header.startswith("Bearer "):
                    return self._unauthorized_response("Invalid authorization header format", request)
                session_id = auth_header.split(" ")[1]
                auth_mode = "bearer"
        
        # 如果两种方式都没有 token
        if not session_id:
            return self._unauthorized_response("Missing authorization credentials", request)
        
        # 3. 验证 Session
        try:
            # 获取 Redis 客户端（使用全局连接池）
            from core.database import get_redis_client
            redis = get_redis_client()
            
            # 使用 SessionStore 验证
            from core.security.token_store import SessionStore
            session_store = SessionStore(redis)
            session_data = await session_store.read_session(session_id)
            
            if not session_data:
                return self._unauthorized_response("Session not found or has been revoked", request)
            
            user_id = session_data.get("user_id")
            tenant_id = session_data.get("tenant_id")
            
            if not user_id or not tenant_id:
                return self._unauthorized_response("Invalid session data", request)
            
            # 4. 将用户信息存储到 request.state（供后续使用）
            request.state.user_id = user_id
            request.state.tenant_id = tenant_id
            request.state.auth_mode = auth_mode  # 🔥 记录认证模式
            
        except TokenExpiredException:
            return self._unauthorized_response("Session has expired", request)
        except InvalidTokenException as e:
            return self._unauthorized_response(f"Invalid session: {str(e)}", request)
        except Exception as e:
            return self._unauthorized_response(f"Session validation failed: {str(e)}", request)
        
        # 5. 继续处理请求
        return await call_next(request)
    
    
    def _is_public_path(self, path: str) -> bool:
        """
        检查路径是否在白名单中
        
        Args:
            path: 请求路径
            
        Returns:
            bool: 是否为公开路径
        """
        # 🔥 使用延迟初始化的白名单
        public_paths = get_public_paths()
        public_prefixes = get_public_prefixes()
        
        # 精确匹配
        if path in public_paths:
            return True
        
        # 前缀匹配
        for prefix in public_prefixes:
            if path.startswith(prefix):
                return True
        
        return False
    
    def _unauthorized_response(self, detail: str, request: Request = None) -> JSONResponse:
        """
        返回 401 未授权响应
        
        Args:
            detail: 错误详情
            request: 请求对象（用于获取 Origin）
            
        Returns:
            JSONResponse: 401 响应
        """
        headers = {"WWW-Authenticate": "Bearer"}
        
        # 添加 CORS 头以支持跨域错误响应
        if request:
            origin = request.headers.get("origin")
            if origin:
                headers["Access-Control-Allow-Origin"] = origin
                headers["Access-Control-Allow-Credentials"] = "true"
        
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers=headers,
        )


def add_public_path(path: str, with_prefix: bool = True) -> None:
    """
    动态添加公开路径到白名单
    
    Args:
        path: 路径
        with_prefix: 是否同时添加带 ROOT_PATH 前缀的路径
    """
    public_paths = get_public_paths()
    public_paths.add(path)
    
    # 如果配置了 ROOT_PATH，同时添加带前缀的路径
    if with_prefix:
        root_path = settings.ROOT_PATH.rstrip("/")
        if root_path and root_path != "/" and path != "/":
            public_paths.add(f"{root_path}{path}")


def add_public_prefix(prefix: str, with_prefix: bool = True) -> None:
    """
    动态添加公开路径前缀到白名单
    
    Args:
        prefix: 路径前缀
        with_prefix: 是否同时添加带 ROOT_PATH 前缀的路径
    """
    public_prefixes = get_public_prefixes()
    public_prefixes.append(prefix)
    
    # 如果配置了 ROOT_PATH，同时添加带前缀的路径
    if with_prefix:
        root_path = settings.ROOT_PATH.rstrip("/")
        if root_path and root_path != "/":
            public_prefixes.append(f"{root_path}{prefix}")


def remove_public_path(path: str, with_prefix: bool = True) -> None:
    """
    从白名单移除公开路径
    
    Args:
        path: 路径
        with_prefix: 是否同时移除带 ROOT_PATH 前缀的路径
    """
    public_paths = get_public_paths()
    public_paths.discard(path)
    
    # 如果配置了 ROOT_PATH，同时移除带前缀的路径
    if with_prefix:
        root_path = settings.ROOT_PATH.rstrip("/")
        if root_path and root_path != "/" and path != "/":
            public_paths.discard(f"{root_path}{path}")
