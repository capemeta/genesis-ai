"""
自定义异常类
统一的异常处理
"""
from fastapi import HTTPException, status
from starlette.exceptions import HTTPException as StarletteHTTPException


class BaseAPIException(HTTPException):
    """基础 API 异常"""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


# ==================== 4xx 客户端错误 ====================

class BadRequestException(BaseAPIException):
    """400 - 错误的请求"""
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UnauthorizedException(BaseAPIException):
    """401 - 未授权"""
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenException(BaseAPIException):
    """403 - 禁止访问"""
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundException(BaseAPIException):
    """404 - 资源不存在"""
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictException(BaseAPIException):
    """409 - 资源冲突"""
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ValidationException(BaseAPIException):
    """422 - 验证失败"""
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class TooManyRequestsException(BaseAPIException):
    """429 - 请求过多"""
    def __init__(self, detail: str = "Too many requests"):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


# ==================== 5xx 服务器错误 ====================

class InternalServerException(BaseAPIException):
    """500 - 服务器内部错误"""
    def __init__(self, detail: str = "Internal server error"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


# ==================== 业务异常 ====================

class UserNotFoundException(NotFoundException):
    """用户不存在"""
    def __init__(self, detail: str = "User not found"):
        super().__init__(detail=detail)


class UserAlreadyExistsException(ConflictException):
    """用户已存在"""
    def __init__(self, detail: str = "User already exists"):
        super().__init__(detail=detail)


class InvalidCredentialsException(UnauthorizedException):
    """无效的凭证"""
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(detail=detail)


class TokenExpiredException(UnauthorizedException):
    """Token 已过期"""
    def __init__(self, detail: str = "Token has expired"):
        super().__init__(detail=detail)


class InvalidTokenException(UnauthorizedException):
    """无效的 Token"""
    def __init__(self, detail: str = "Invalid token"):
        super().__init__(detail=detail)


class TenantNotFoundException(NotFoundException):
    """租户不存在"""
    def __init__(self, detail: str = "Tenant not found"):
        super().__init__(detail=detail)


class PermissionDeniedException(ForbiddenException):
    """权限不足"""
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(detail=detail)


# ============================================================================
# 全局异常处理器（新增）
# ============================================================================

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from core.response import ResponseBuilder

logger = logging.getLogger(__name__)


async def starlette_http_exception_handler(
    request: Request, 
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    处理 Starlette HTTP 异常（包括 405 Method Not Allowed）
    
    这个处理器专门处理 Starlette 框架级别的 HTTP 异常，
    例如：405 Method Not Allowed、404 Not Found 等
    
    Args:
        request: FastAPI 请求对象
        exc: Starlette HTTP 异常对象
        
    Returns:
        JSONResponse: 统一格式的错误响应
    """
    # 记录 WARNING 级别日志
    logger.warning(
        f"Starlette HTTP exception: {exc.detail} | Status: {exc.status_code} | "
        f"Path: {request.url.path} | Method: {request.method}"
    )
    
    # 针对 405 错误提供更友好的消息
    if exc.status_code == 405:
        message = f"不支持的请求方法: {request.method}。请检查 API 文档了解支持的方法。"
    else:
        message = str(exc.detail)
    
    # 构建统一错误响应
    return ResponseBuilder.build_error(
        message=message,
        http_status=exc.status_code
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    处理 HTTP 异常（包括自定义的 BaseAPIException）
    
    Args:
        request: FastAPI 请求对象
        exc: HTTP 异常对象
        
    Returns:
        JSONResponse: 统一格式的错误响应
    """
    # 记录 WARNING 级别日志
    logger.warning(
        f"HTTP exception: {exc.detail} | Status: {exc.status_code} | Path: {request.url.path}"
    )
    
    # 构建统一错误响应
    return ResponseBuilder.build_error(
        message=str(exc.detail),
        http_status=exc.status_code
    )


async def enhanced_validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """
    增强的验证异常处理器
    保持现有的登录失败记录逻辑，同时统一响应格式
    
    Args:
        request: FastAPI 请求对象
        exc: 验证异常对象
        
    Returns:
        JSONResponse: 统一格式的错误响应
    """
    # 保持现有的登录失败记录逻辑
    if request.url.path.endswith("/auth/login"):
        try:
            from core.database.session import get_redis
            from core.security.captcha import CaptchaService
            from utils.request_utils import get_client_ip
            
            redis = await get_redis()
            captcha_service = CaptchaService(redis)
            client_ip = get_client_ip(request)
            await captcha_service.record_captcha_failure(client_ip)
            
            logger.warning(f"Login validation failed from IP {client_ip}: {exc.errors()}")
        except Exception as e:
            # 记录错误但不影响响应
            logger.error(f"Failed to record validation failure: {e}")
    
    # 提取第一个错误消息
    first_error = exc.errors()[0] if exc.errors() else {}
    error_message = first_error.get("msg", "参数校验失败")
    
    # 记录 WARNING 级别日志
    logger.warning(f"Validation error: {error_message} | Path: {request.url.path}")
    
    # 序列化错误详情（确保所有对象都可以 JSON 序列化）
    serializable_errors = []
    for error in exc.errors():
        serializable_error = {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "input": error.get("input"),
        }
        # 处理 ctx 字段中的 ValueError 等不可序列化对象
        if "ctx" in error:
            ctx = error["ctx"]
            serializable_ctx = {}
            for key, value in ctx.items():
                # 将所有值转换为字符串以确保可序列化
                if isinstance(value, Exception):
                    serializable_ctx[key] = str(value)
                else:
                    serializable_ctx[key] = value
            serializable_error["ctx"] = serializable_ctx
        
        serializable_errors.append(serializable_error)
    
    # 构建统一错误响应
    return ResponseBuilder.build_error(
        message=error_message,
        http_status=422,
        details=serializable_errors
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    处理数据库异常
    
    Args:
        request: FastAPI 请求对象
        exc: SQLAlchemy 异常对象
        
    Returns:
        JSONResponse: 统一格式的错误响应
    """
    # 记录 ERROR 级别日志（包含完整堆栈）
    logger.error(f"Database error: {str(exc)} | Path: {request.url.path}", exc_info=True)
    
    # 根据 DEBUG 模式返回不同的错误消息
    from core.config.settings import settings
    if settings.DEBUG:
        message = f"数据库错误: {str(exc)}"
    else:
        message = "数据库连接异常，请稍后重试"
    
    # 构建统一错误响应
    return ResponseBuilder.build_error(
        message=message,
        http_status=500
    )


async def redis_exception_handler(request: Request, exc: RedisError) -> JSONResponse:
    """
    处理 Redis 异常
    
    Args:
        request: FastAPI 请求对象
        exc: Redis 异常对象
        
    Returns:
        JSONResponse: 统一格式的错误响应
    """
    # 记录 ERROR 级别日志（包含完整堆栈）
    logger.error(f"Redis error: {str(exc)} | Path: {request.url.path}", exc_info=True)
    
    # 返回用户友好消息
    return ResponseBuilder.build_error(
        message="缓存服务异常，请稍后重试",
        http_status=500
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    处理未知异常（兜底处理器）
    
    Args:
        request: FastAPI 请求对象
        exc: 通用异常对象
        
    Returns:
        JSONResponse: 统一格式的错误响应
    """
    # 记录 ERROR 级别日志（包含完整堆栈）
    logger.error(f"Unhandled exception: {str(exc)} | Path: {request.url.path}", exc_info=True)
    
    # 根据 DEBUG 模式返回不同的错误消息
    from core.config.settings import settings
    if settings.DEBUG:
        message = f"服务器内部错误: {str(exc)}"
        details = [str(exc)]
    else:
        message = "服务器内部错误，请稍后重试"
        details = None
    
    # 构建统一错误响应
    return ResponseBuilder.build_error(
        message=message,
        http_status=500,
        details=details
    )
