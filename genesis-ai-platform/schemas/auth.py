"""
认证相关 Schema
"""
from uuid import UUID

from pydantic import AliasChoices, BaseModel, EmailStr, Field, field_validator


class Token(BaseModel):
    """Token 响应"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str | None = Field(None, description="刷新令牌（可选）")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int | None = Field(None, description="过期时间（秒）")


class TokenPayload(BaseModel):
    """Token 载荷"""
    sub: str  # user_id
    tenant_id: str
    exp: int


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")
    captcha_token: str | None = Field(None, description="验证码令牌")
    captcha_code: str | None = Field(None, min_length=4, max_length=6, description="验证码")
    remember: bool = Field(
        default=False,
        description="记住我（7天内自动登录）",
        validation_alias=AliasChoices("remember", "remember_me"),
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "password": "SecurePass@123",
                "captcha_token": "abc123...",
                "captcha_code": "ABCD",
                "remember": False,
            }
        }
    }


class RefreshTokenRequest(BaseModel):
    """
    刷新 Token 请求（仅用于文档和 Bearer Token 模式）
    
    🔥 注意：Cookie 模式下不使用此 Schema
    - Cookie 模式：refresh_token 从 Cookie 中读取（推荐）
    - Bearer Token 模式：refresh_token 从请求体读取（兼容）
    
    此 Schema 保留用于：
    1. API 文档生成
    2. Bearer Token 模式的客户端参考
    3. 向后兼容
    """
    refresh_token: str | None = Field(None, description="刷新令牌（Cookie 模式下可选）")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    }


class RegisterRequest(BaseModel):
    """注册请求"""
    tenant_id: UUID = Field(..., description="租户ID")
    email: EmailStr | None = Field(None, description="邮箱（可选）")
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
        description="用户名（3-50位，只能包含字母、数字、下划线、连字符）"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="密码（8-20位，必须包含大小写字母、数字和特殊字符&*^%$#@!中的一个）"
    )
    nickname: str | None = Field(None, max_length=255, description="昵称")
    
    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """验证密码强度"""
        from core.security import PasswordValidator
        
        is_valid, errors = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "username": "john_doe",
                "password": "SecurePass@123",
                "nickname": "John Doe",
            }
        }
    }


class PasswordChange(BaseModel):
    """修改密码"""
    old_password: str = Field(..., min_length=8, description="当前密码")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="新密码（8-20位，必须包含大小写字母、数字和特殊字符&*^%$#@!中的一个）"
    )
    logout_all_devices: bool = Field(
        default=False,
        description="是否登出所有设备（包括当前设备）。建议：如果怀疑账号被盗，请勾选此项"
    )
    
    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """验证新密码强度"""
        from core.security import PasswordValidator
        
        is_valid, errors = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v


class PasswordReset(BaseModel):
    """重置密码"""
    token: str = Field(..., description="重置令牌")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="新密码（8-100位，必须包含大小写字母、数字、特殊字符）"
    )
    
    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """验证新密码强度"""
        from core.security import PasswordValidator
        
        is_valid, errors = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v
