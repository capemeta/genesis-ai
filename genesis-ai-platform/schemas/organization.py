"""
组织架构 Schema 定义
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, field_serializer
import re


class OrganizationCreate(BaseModel):
    """组织创建 Schema"""
    parent_id: Optional[UUID] = Field(None, description="父部门ID，NULL表示根部门")
    name: str = Field(..., min_length=1, max_length=255, description="部门名称")
    description: Optional[str] = Field(None, description="部门描述")
    order_num: int = Field(default=10, ge=0, description="排序号，数字越小越靠前")
    status: str = Field(default='0', description="状态：0-正常，1-停用")
    leader_name: Optional[str] = Field(None, max_length=100, description="负责人姓名")
    phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """验证状态值"""
        if v not in ['0', '1']:
            raise ValueError("状态必须是 0（正常）或 1（停用）")
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
        """验证电话格式（支持手机和座机）"""
        if v:
            # 支持手机号（11位）或座机（区号-号码）
            if not re.match(r"^1[3-9]\d{9}$|^0\d{2,3}-?\d{7,8}$", v):
                raise ValueError("电话格式不正确")
        return v


class OrganizationUpdate(BaseModel):
    """组织更新 Schema"""
    id: UUID = Field(..., description="组织ID")
    parent_id: Optional[UUID] = Field(None, description="父部门ID")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="部门名称")
    description: Optional[str] = Field(None, description="部门描述")
    order_num: Optional[int] = Field(None, ge=0, description="排序号")
    status: Optional[str] = Field(None, description="状态：0-正常，1-停用")
    leader_name: Optional[str] = Field(None, max_length=100, description="负责人姓名")
    phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    cascade_disable: Optional[bool] = Field(False, description="是否级联停用子部门（仅当 status='1' 时有效）")
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """验证状态值"""
        if v and v not in ['0', '1']:
            raise ValueError("状态必须是 0（正常）或 1（停用）")
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
        """验证电话格式"""
        if v and not re.match(r"^1[3-9]\d{9}$|^0\d{2,3}-?\d{7,8}$", v):
            raise ValueError("电话格式不正确")
        return v


class OrganizationRead(BaseModel):
    """组织读取 Schema"""
    id: UUID
    tenant_id: UUID
    parent_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    path: str
    level: int
    order_num: int
    status: str
    del_flag: str
    leader_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime, _info) -> str:
        """将 datetime 序列化为 yyyy-MM-dd HH:mm:ss 格式"""
        if dt:
            # 转换为本地时区（UTC+8）
            from datetime import timezone, timedelta
            local_tz = timezone(timedelta(hours=8))
            local_dt = dt.astimezone(local_tz)
            return local_dt.strftime('%Y-%m-%d %H:%M:%S')
        return ''
    
    model_config = {"from_attributes": True}


class OrganizationTreeNode(BaseModel):
    """组织树节点 Schema（用于下拉选择器）"""
    id: UUID
    parent_id: Optional[UUID] = None
    name: str
    order_num: int
    status: str
    level: int
    children: List["OrganizationTreeNode"] = []
    
    model_config = {"from_attributes": True}


class OrganizationListResponse(BaseModel):
    """组织列表响应（扁平结构，前端构建树）"""
    id: UUID
    tenant_id: UUID
    parent_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    path: str
    level: int
    order_num: int
    status: str
    leader_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime
    
    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime, _info) -> str:
        """将 datetime 序列化为 yyyy-MM-dd HH:mm:ss 格式"""
        if dt:
            # 转换为本地时区（UTC+8）
            from datetime import timezone, timedelta
            local_tz = timezone(timedelta(hours=8))
            local_dt = dt.astimezone(local_tz)
            return local_dt.strftime('%Y-%m-%d %H:%M:%S')
        return ''
    
    model_config = {"from_attributes": True}


class OrganizationDeleteRequest(BaseModel):
    """组织删除请求"""
    id: UUID = Field(..., description="组织ID")
