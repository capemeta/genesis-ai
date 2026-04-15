"""
租户 Schema 定义
"""
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

from schemas.common import ListRequest


class TenantLimits(BaseModel):
    """租户配额限制"""
    max_users: Optional[int] = Field(None, ge=1, description="最大用户数")
    max_storage_gb: Optional[int] = Field(None, ge=1, description="最大存储空间（GB）")


class TenantListRequest(ListRequest):
    """
    租户列表请求
    
    继承通用 ListRequest，自动包含：
    - page, page_size: 分页参数
    - search: 简单搜索（模糊匹配）
    - filters: 精确过滤
    - advanced_filters: 高级过滤（支持操作符）
    - sort_by, sort_order: 排序参数
    """
    pass


class TenantGetRequest(BaseModel):
    """获取单个租户请求"""
    id: UUID = Field(..., description="租户ID")


class TenantCreate(BaseModel):
    """创建租户请求"""
    owner_id: UUID = Field(..., description="所有者ID")
    name: str = Field(..., min_length=1, max_length=255, description="租户名称")
    description: Optional[str] = Field(None, description="租户描述")
    limits: TenantLimits = Field(default_factory=TenantLimits, description="配额限制")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证租户名称"""
        if not v.strip():
            raise ValueError("租户名称不能为空")
        return v.strip()


class TenantUpdate(BaseModel):
    """更新租户请求（不包含 id，id 由路由层处理）"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="租户名称")
    description: Optional[str] = Field(None, description="租户描述")
    limits: Optional[TenantLimits] = Field(None, description="配额限制")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """验证租户名称"""
        if v is not None and not v.strip():
            raise ValueError("租户名称不能为空")
        return v.strip() if v else None


class TenantDelete(BaseModel):
    """删除租户请求"""
    id: UUID = Field(..., description="租户ID")


class TenantResponse(BaseModel):
    """租户响应"""
    id: UUID
    owner_id: UUID
    name: str
    description: Optional[str]
    limits: dict
    created_by_id: Optional[UUID]
    created_by_name: Optional[str]
    updated_by_id: Optional[UUID]
    updated_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
