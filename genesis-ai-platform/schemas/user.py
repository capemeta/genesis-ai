"""
用户 Schema 定义
"""
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


class UserCreate(BaseModel):
    """用户创建 Schema"""
    username: str = Field(..., min_length=1, max_length=100, description="用户名")
    nickname: str = Field(..., min_length=1, max_length=255, description="昵称（必填）")
    password: str = Field(..., min_length=8, max_length=20, description="密码（8-20位，必须包含大小写字母、数字和特殊字符）")
    email: Optional[str] = Field(None, max_length=255, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    job_title: Optional[str] = Field(None, max_length=100, description="职位")
    employee_no: Optional[str] = Field(None, max_length=100, description="工号")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    organization_id: Optional[UUID] = Field(None, description="所属部门ID")
    status: Optional[str] = Field("active", description="状态")
    role_ids: list[UUID] = Field(default_factory=list, description="角色ID列表")
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名格式"""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """验证邮箱格式"""
        if v and not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("邮箱格式不正确")
        return v
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """验证手机号格式"""
        if v and not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码强度"""
        if len(v) < 8 or len(v) > 20:
            raise ValueError("密码长度必须为8-20位")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含小写字母")
        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含数字")
        if not re.search(r"[&*^%$#@!]", v):
            raise ValueError("密码必须包含特殊字符(&*^%$#@!中的一个)")
        return v
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """验证状态值"""
        if v not in ["active", "disabled", "locked"]:
            raise ValueError("状态必须是 active、disabled 或 locked")
        return v


class UserUpdate(BaseModel):
    """
    用户更新 Schema
    
    注意：
    - password 字段可选，如果提供则会更新密码（需要管理员权限）
    - 用户自己修改密码建议使用：POST /api/v1/password/change（需要验证旧密码）
    """
    id: UUID = Field(..., description="用户ID")
    nickname: str = Field(..., min_length=1, max_length=255, description="昵称（必填）")
    email: Optional[str] = Field(None, max_length=255, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    job_title: Optional[str] = Field(None, max_length=100, description="职位")
    employee_no: Optional[str] = Field(None, max_length=100, description="工号")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    organization_id: Optional[UUID] = Field(None, description="所属部门ID")
    status: Optional[str] = Field(None, description="状态")
    password: Optional[str] = Field(None, min_length=8, max_length=20, description="新密码（可选，8-20位）")
    role_ids: list[UUID] = Field(default_factory=list, description="角色ID列表")
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """验证邮箱格式"""
        if v and not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("邮箱格式不正确")
        return v
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """验证手机号格式"""
        if v and not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """验证状态值"""
        if v and v not in ["active", "disabled", "locked"]:
            raise ValueError("状态必须是 active、disabled 或 locked")
        return v


class UserRead(BaseModel):
    """用户读取 Schema"""
    id: UUID
    tenant_id: UUID
    organization_id: Optional[UUID] = None
    organization_name: Optional[str] = None
    username: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    job_title: Optional[str] = None
    employee_no: Optional[str] = None
    bio: Optional[str] = None
    status: str
    role_names: list[str] = Field(default_factory=list)
    email_verified_at: Optional[datetime] = None
    phone_verified_at: Optional[datetime] = None
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    last_active_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


# ==================== 列表查询 Schema ====================

class UserListRequest(BaseModel):
    """用户列表查询请求"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    search: Optional[str] = Field(None, description="搜索关键词（用户名、昵称、邮箱）")
    status: Optional[str] = Field(None, description="状态过滤")
    organization_id: Optional[UUID] = Field(None, description="组织ID过滤")


class UserListItem(BaseModel):
    """用户列表项"""
    id: UUID
    username: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    employee_no: Optional[str] = None
    bio: Optional[str] = None
    status: str
    organization_id: Optional[UUID] = None
    organization_name: Optional[str] = None  # 冗余字段，前端显示用
    role_names: list[str] = []  # 角色名称列表
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """用户列表响应"""
    data: list[UserListItem]
    total: int


# ==================== 删除 Schema ====================

class UserDeleteRequest(BaseModel):
    """用户删除请求"""
    id: UUID = Field(..., description="用户 ID")


# ==================== 角色分配 Schema ====================

class UserResetPasswordRequest(BaseModel):
    """重置用户密码请求（管理员操作）"""
    user_id: UUID = Field(..., description="用户 ID")
    new_password: str = Field(..., min_length=8, max_length=20, description="新密码（8-20位，必须包含大小写字母、数字和特殊字符）")
    
    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码强度"""
        if len(v) < 8 or len(v) > 20:
            raise ValueError("密码长度必须为8-20位")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含小写字母")
        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含数字")
        if not re.search(r"[&*^%$#@!]", v):
            raise ValueError("密码必须包含特殊字符(&*^%$#@!中的一个)")
        return v


class UserAssignRolesRequest(BaseModel):
    """为用户分配角色请求"""
    user_id: UUID = Field(..., description="用户 ID")
    role_ids: list[UUID] = Field(..., description="角色 ID 列表")


class UserGetRolesRequest(BaseModel):
    """获取用户角色请求"""
    user_id: UUID = Field(..., description="用户 ID")
