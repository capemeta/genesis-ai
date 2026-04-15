"""
验证中间件
处理 Pydantic 验证失败的情况
"""
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from core.database.session import get_redis
from core.security import CaptchaService
from utils.request_utils import get_client_ip
import logging

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    处理验证异常
    
    对于登录接口的验证失败，也记录失败次数
    """
    # 检查是否是登录接口
    if request.url.path.endswith("/auth/login"):
        try:
            # 获取 Redis 客户端
            redis = await get_redis()
            captcha_service = CaptchaService(redis)
            
            # 获取客户端 IP
            client_ip = get_client_ip(request)
            
            # 记录失败次数
            await captcha_service.record_captcha_failure(client_ip)
            
            logger.warning(
                f"Login validation failed from IP {client_ip}: {exc.errors()}"
            )
        except Exception as e:
            logger.error(f"Failed to record validation failure: {e}")
    
    # 返回标准的验证错误响应
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )
