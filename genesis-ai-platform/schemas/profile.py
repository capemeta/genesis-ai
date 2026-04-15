"""
个人资料相关 Schema
"""
from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfileResponse(BaseModel):
    """当前用户个人资料响应"""

    id: str
    username: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    job_title: Optional[str] = None
    bio: Optional[str] = None
    status: str
    tenant_id: str
    tenant_name: Optional[str] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False
    last_login_at: Optional[str] = None
    last_login_ip: Optional[str] = None
    last_active_at: Optional[str] = None
    password_changed_at: Optional[str] = None
    language: str = "zh"
    timezone: str = "Asia/Shanghai"
    theme: str = "system"
    date_format: str = "YYYY-MM-DD"
    time_format: str = "24h"
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    """个人资料更新请求"""

    nickname: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    job_title: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    language: Optional[Literal["zh", "en"]] = None
    timezone: Optional[str] = Field(None, max_length=64, description="时区，如 Asia/Shanghai")
    theme: Optional[Literal["light", "dark", "system"]] = None
    date_format: Optional[str] = Field(None, max_length=32)
    time_format: Optional[Literal["12h", "24h"]] = None


class SessionInfo(BaseModel):
    """会话信息"""

    session_id: str
    user_agent: str
    client_ip: str
    created_at: str
    last_active_at: str
    is_current: bool


class SessionListResponse(BaseModel):
    """会话列表响应"""

    data: List[SessionInfo]
    total: int
