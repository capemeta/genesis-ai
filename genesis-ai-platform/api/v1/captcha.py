"""
验证码 API
生成和验证验证码
"""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from core.database import get_redis
from core.security import CaptchaService, get_captcha_service
from core.response import ResponseBuilder
from utils.request_utils import get_client_ip

router = APIRouter()


class CaptchaCreateResponse(BaseModel):
    """验证码创建响应"""
    token: str = Field(..., description="验证码令牌")
    image_url: str = Field(..., description="验证码图片 URL")
    expires_in: int = Field(default=300, description="过期时间（秒）")


class CaptchaVerifyRequest(BaseModel):
    """验证码验证请求"""
    token: str = Field(..., description="验证码令牌")
    code: str = Field(..., min_length=4, max_length=6, description="验证码")


class CaptchaVerifyResponse(BaseModel):
    """验证码验证响应"""
    valid: bool = Field(..., description="是否有效")
    message: str = Field(..., description="响应消息")


@router.post("/create")
async def create_captcha(
    request: Request,
    captcha_service: CaptchaService = Depends(get_captcha_service),
):
    """
    创建验证码
    
    返回验证码令牌和图片 URL
    """
    # 生成验证码
    token, _ = await captcha_service.create_captcha(
        captcha_type="image",
        length=4,
        expire_seconds=300,  # 5 分钟
    )
    
    # 构建图片 URL
    base_url = str(request.base_url).rstrip('/')
    image_url = f"{base_url}/api/v1/captcha/image/{token}"
    
    return ResponseBuilder.build_success(
        data={
            "token": token,
            "image_url": image_url,
            "expires_in": 300
        },
        message="验证码创建成功"
    )


@router.get("/image/{token}")
async def get_captcha_image(
    token: str,
    redis: Redis = Depends(get_redis),
):
    """
    获取验证码图片
    
    根据令牌返回验证码图片
    """
    # 从 Redis 获取验证码文本
    key = f"captcha:{token}"
    text = await redis.get(key)
    
    if not text:
        # 验证码不存在或已过期
        return Response(
            content="Captcha expired or not found",
            status_code=404,
            media_type="text/plain",
        )
    
    # 生成图片
    from core.security import CaptchaGenerator
    generator = CaptchaGenerator()
    image_buffer = generator.generate_image(text.upper())
    
    # 返回图片
    return StreamingResponse(
        image_buffer,
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.post("/verify")
async def verify_captcha(
    verify_request: CaptchaVerifyRequest,
    request: Request,
    captcha_service: CaptchaService = Depends(get_captcha_service),
):
    """
    验证验证码
    
    验证用户输入的验证码是否正确
    """
    # 获取真实 IP
    client_ip = get_client_ip(request)
    
    # 验证验证码
    is_valid = await captcha_service.verify_captcha(
        token=verify_request.token,
        user_input=verify_request.code,
        case_sensitive=False,
    )
    
    if is_valid:
        # 验证成功，清除失败记录
        await captcha_service.clear_captcha_attempts(client_ip)
        return ResponseBuilder.build_success(
            data={"valid": True},
            message="验证码验证成功"
        )
    else:
        # 验证失败，记录失败次数
        await captcha_service.record_captcha_failure(client_ip)
        return ResponseBuilder.build_success(
            data={"valid": False},
            message="验证码错误或已过期"
        )


@router.get("/required")
async def check_captcha_required(
    request: Request,
    captcha_service: CaptchaService = Depends(get_captcha_service),
):
    """
    检查是否需要验证码
    
    根据失败次数判断是否需要显示验证码
    """
    # 获取真实 IP
    client_ip = get_client_ip(request)
    
    # 检查是否需要验证码（3 次失败后需要）
    required = await captcha_service.should_require_captcha(
        identifier=client_ip,
        threshold=3,
    )
    
    attempts = await captcha_service.get_captcha_attempts(client_ip)
    
    # 添加调试信息
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Captcha check - IP: {client_ip}, Attempts: {attempts}, Required: {required}")
    
    return ResponseBuilder.build_success(
        data={
            "required": required,
            "attempts": attempts,
            "threshold": 3,
            "client_ip": client_ip
        },
        message="需要验证码" if required else "暂不需要验证码"
    )
