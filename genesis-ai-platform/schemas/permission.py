"""
权限管理 Schema
定义权限的请求和响应数据结构
"""
from pydantic import BaseModel, Field, field_validator, field_serializer
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import Optional


class PermissionCreate(BaseModel):
    """创建权限的请求 Schema"""
    
    # 必填字段
    code: str = Field(..., min_length=1, max_length=100, description="权限代码，全局唯一")
    name: str = Field(..., min_length=1, max_length=100, description="权限名称")
    type: str = Field(..., description="权限类型：menu-菜单权限，function-功能权限，directory-目录")
    module: str = Field(..., min_length=1, max_length=50, description="所属模块")
    
    # 可选字段
    description: Optional[str] = Field(None, description="权限描述")
    status: int = Field(default=0, description="状态：0-正常，1-停用")
    
    # 菜单权限专用字段
    parent_id: Optional[UUID] = Field(None, description="父菜单ID")
    path: Optional[str] = Field(None, max_length=255, description="前端路由路径")
    icon: Optional[str] = Field(None, max_length=100, description="菜单图标")
    component: Optional[str] = Field(None, max_length=255, description="前端组件路径")
    sort_order: int = Field(default=0, description="排序顺序")
    is_hidden: bool = Field(default=False, description="是否隐藏")
    
    # 功能权限专用字段
    api_path: Optional[str] = Field(None, max_length=255, description="API 路径")
    http_method: Optional[str] = Field(None, max_length=10, description="HTTP 方法")
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证权限类型"""
        allowed_types = ['menu', 'function', 'directory']
        if v not in allowed_types:
            raise ValueError(f"type 必须是 {', '.join(allowed_types)} 之一")
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: int) -> int:
        """验证状态"""
        if v not in [0, 1]:
            raise ValueError("status 必须是 0（正常）或 1（停用）")
        return v


class PermissionUpdate(BaseModel):
    """更新权限的请求 Schema"""
    
    # 必填字段
    id: UUID = Field(..., description="权限ID")
    
    # 可选字段（所有字段都可以更新）
    code: Optional[str] = Field(None, min_length=1, max_length=100, description="权限代码")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="权限名称")
    type: Optional[str] = Field(None, description="权限类型")
    module: Optional[str] = Field(None, min_length=1, max_length=50, description="所属模块")
    description: Optional[str] = Field(None, description="权限描述")
    status: Optional[int] = Field(None, description="状态")
    
    # 菜单权限专用字段
    parent_id: Optional[UUID] = Field(None, description="父菜单ID")
    path: Optional[str] = Field(None, max_length=255, description="前端路由路径")
    icon: Optional[str] = Field(None, max_length=100, description="菜单图标")
    component: Optional[str] = Field(None, max_length=255, description="前端组件路径")
    sort_order: Optional[int] = Field(None, description="排序顺序")
    is_hidden: Optional[bool] = Field(None, description="是否隐藏")
    
    # 功能权限专用字段
    api_path: Optional[str] = Field(None, max_length=255, description="API 路径")
    http_method: Optional[str] = Field(None, max_length=10, description="HTTP 方法")
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        """验证权限类型"""
        if v is not None:
            allowed_types = ['menu', 'function', 'directory']
            if v not in allowed_types:
                raise ValueError(f"type 必须是 {', '.join(allowed_types)} 之一")
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[int]) -> Optional[int]:
        """验证状态"""
        if v is not None and v not in [0, 1]:
            raise ValueError("status 必须是 0（正常）或 1（停用）")
        return v


class PermissionRead(BaseModel):
    """权限详情的响应 Schema"""
    
    # 基础字段
    id: UUID
    tenant_id: Optional[UUID]
    code: str
    name: str
    type: str
    module: str
    description: Optional[str]
    status: int
    
    # 菜单权限专用字段
    parent_id: Optional[UUID]
    path: Optional[str]
    icon: Optional[str]
    component: Optional[str]
    sort_order: int
    is_hidden: bool
    
    # 功能权限专用字段
    api_path: Optional[str]
    http_method: Optional[str]
    
    # 审计字段
    created_by_id: Optional[UUID]
    created_by_name: Optional[str]
    updated_by_id: Optional[UUID]
    updated_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PermissionListItem(BaseModel):
    """权限列表项的响应 Schema（简化版）"""
    
    id: UUID
    code: str
    name: str
    type: str
    module: str
    description: Optional[str]
    status: int
    parent_id: Optional[UUID]
    icon: Optional[str]
    path: Optional[str]
    sort_order: int
    created_at: datetime
    
    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime, _info) -> str:
        """将 datetime 序列化为 yyyy-MM-dd HH:mm:ss 格式"""
        if dt:
            # 转换为本地时区（UTC+8）
            local_tz = timezone(timedelta(hours=8))
            local_dt = dt.astimezone(local_tz)
            return local_dt.strftime('%Y-%m-%d %H:%M:%S')
        return ''
    
    class Config:
        from_attributes = True


class PermissionListResponse(BaseModel):
    """权限列表的响应 Schema"""
    
    data: list[PermissionListItem]
    total: int


class PermissionDeleteRequest(BaseModel):
    """删除权限的请求 Schema"""
    
    id: UUID = Field(..., description="权限ID")
