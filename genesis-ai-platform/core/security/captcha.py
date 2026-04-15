"""
验证码生成和验证
支持图形验证码和滑动验证码
"""
import random
import string
import secrets
from io import BytesIO
from typing import Any, Optional, cast
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from redis.asyncio import Redis
from fastapi import Depends
from core.database import get_redis


class CaptchaGenerator:
    """验证码生成器"""
    
    # 验证码字符集（排除易混淆字符）
    CHAR_SET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    
    @staticmethod
    def generate_text(length: int = 4) -> str:
        """
        生成验证码文本
        
        Args:
            length: 验证码长度
        
        Returns:
            验证码文本
        """
        return ''.join(random.choices(CaptchaGenerator.CHAR_SET, k=length))
    
    @staticmethod
    def generate_image(
        text: str,
        width: int = 120,
        height: int = 40,
        font_size: int = 28,
    ) -> BytesIO:
        """
        生成验证码图片
        
        Args:
            text: 验证码文本
            width: 图片宽度
            height: 图片高度
            font_size: 字体大小
        
        Returns:
            图片字节流
        """
        # 创建图片
        font: Any
        image = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        
        # 尝试加载字体（如果失败使用默认字体）
        try:
            # Windows 字体路径
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                # Linux 字体路径
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                # 使用默认字体
                font = cast(ImageFont.ImageFont, ImageFont.load_default())
        
        # 绘制干扰线
        for _ in range(random.randint(3, 5)):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=1)
        
        # 绘制干扰点
        for _ in range(random.randint(50, 100)):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill=(150, 150, 150))
        
        # 绘制验证码文本
        char_width = width // len(text)
        for i, char in enumerate(text):
            # 随机位置和颜色
            x = char_width * i + random.randint(5, 10)
            y = random.randint(5, 10)
            color = (
                random.randint(0, 100),
                random.randint(0, 100),
                random.randint(0, 100),
            )
            
            # 绘制字符
            draw.text((x, y), char, font=font, fill=color)
        
        # 应用滤镜（可选）
        # image = image.filter(ImageFilter.SMOOTH)
        
        # 转换为字节流
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def generate_token() -> str:
        """
        生成验证码令牌（用于标识验证码）
        
        Returns:
            验证码令牌
        """
        return secrets.token_urlsafe(32)


class CaptchaService:
    """验证码服务"""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.generator = CaptchaGenerator()
    
    async def create_captcha(
        self,
        captcha_type: str = "image",
        length: int = 4,
        expire_seconds: int = 300,
    ) -> tuple[str, str | BytesIO]:
        """
        创建验证码
        
        Args:
            captcha_type: 验证码类型（image 或 text）
            length: 验证码长度
            expire_seconds: 过期时间（秒）
        
        Returns:
            (验证码令牌, 验证码内容/图片)
        """
        # 生成验证码文本
        text = self.generator.generate_text(length)
        
        # 生成令牌
        token = self.generator.generate_token()
        
        # 存储到 Redis（转为小写便于验证）
        key = f"captcha:{token}"
        await self.redis.setex(key, expire_seconds, text.lower())
        
        # 根据类型返回
        if captcha_type == "image":
            image = self.generator.generate_image(text)
            return token, image
        else:
            return token, text
    
    async def verify_captcha(
        self,
        token: str,
        user_input: str,
        case_sensitive: bool = False,
    ) -> bool:
        """
        验证验证码
        
        Args:
            token: 验证码令牌
            user_input: 用户输入
            case_sensitive: 是否区分大小写
        
        Returns:
            是否验证通过
        """
        key = f"captcha:{token}"
        
        # 从 Redis 获取验证码
        stored_text = await self.redis.get(key)
        
        if not stored_text:
            # 验证码不存在或已过期
            return False
        
        # 验证后删除（一次性使用）
        await self.redis.delete(key)
        
        # 比较
        if case_sensitive:
            return user_input == stored_text
        else:
            return user_input.lower() == stored_text.lower()
    
    async def get_captcha_attempts(self, identifier: str) -> int:
        """
        获取验证码尝试次数
        
        Args:
            identifier: 标识符（IP 或用户 ID）
        
        Returns:
            尝试次数
        """
        key = f"captcha_attempts:{identifier}"
        attempts = await self.redis.get(key)
        return int(attempts) if attempts else 0
    
    async def record_captcha_failure(
        self,
        identifier: str,
        expire_seconds: int = 3600,
    ):
        """
        记录验证码验证失败
        
        Args:
            identifier: 标识符（IP 或用户 ID）
            expire_seconds: 过期时间（秒）
        """
        key = f"captcha_attempts:{identifier}"
        await self.redis.incr(key)
        await self.redis.expire(key, expire_seconds)
    
    async def clear_captcha_attempts(self, identifier: str):
        """
        清除验证码尝试记录
        
        Args:
            identifier: 标识符（IP 或用户 ID）
        """
        key = f"captcha_attempts:{identifier}"
        await self.redis.delete(key)
    
    async def should_require_captcha(
        self,
        identifier: str,
        threshold: int = 3,
    ) -> bool:
        """
        判断是否需要验证码
        
        Args:
            identifier: 标识符（IP 或用户 ID）
            threshold: 失败次数阈值
        
        Returns:
            是否需要验证码
        """
        attempts = await self.get_captcha_attempts(identifier)
        return attempts >= threshold


# 依赖注入函数
async def get_captcha_service(redis: Redis = Depends(get_redis)) -> CaptchaService:
    """获取验证码服务实例"""
    return CaptchaService(redis)
