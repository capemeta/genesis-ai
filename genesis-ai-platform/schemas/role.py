"""
角色 Schema 定义
"""
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    """角色创建 Schema"""
    code: str = Field(..., min_length=1, max_length=50, description="角色代码")
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    status: str = Field("0", pattern="^[01]$", description="状态：0-正常，1-停用")
    sort_order: int = Field(0, description="排序顺序")


class RoleUpdate(BaseModel):
    """角色更新 Schema"""
    id: UUID = Field(..., description="角色 ID")
    code: Optional[str] = Field(None, min_length=1, max_length=50, description="角色代码")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    status: Optional[str] = Field(None, pattern="^[01]$", description="状态：0-正常，1-停用")
    sort_order: Optional[int] = Field(None, description="排序顺序")


class RoleRead(BaseModel):
    """角色读取 Schema"""
    id: UUID
    tenant_id: Optional[UUID] = None
    code: str
    name: str
    description: Optional[str] = None
    status: str
    del_flag: str
    sort_order: int
    is_system: bool
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class RoleListItem(BaseModel):
    """角色列表项"""
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    status: str
    sort_order: int
    created_at: datetime
    
    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    """角色列表响应"""
    data: list[RoleListItem]
    total: int


class RoleDeleteRequest(BaseModel):
    """角色删除请求"""
    id: UUID = Field(..., description="角色 ID")


# ==================== 权限分配 Schema ====================

class RoleAssignPermissionsRequest(BaseModel):
    """为角色分配权限请求"""
    role_id: UUID = Field(..., description="角色 ID")
    permission_ids: list[UUID] = Field(..., description="权限 ID 列表")


class RoleGetPermissionsRequest(BaseModel):
    """获取角色权限请求"""
    role_id: UUID = Field(..., description="角色 ID")


class RolePermissionResponse(BaseModel):
    """角色权限响应"""
    role_id: UUID
    permission_ids: list[UUID]
