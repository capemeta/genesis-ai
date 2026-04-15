"""
文件夹 Schema 定义
"""
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class FolderBase(BaseModel):
    """文件夹基础 Schema"""
    name: str = Field(..., min_length=1, max_length=255, description="文件夹名称")
    summary: Optional[str] = Field(None, description="文件夹摘要")
    kb_id: Optional[UUID] = Field(None, description="所属知识库ID")
    parent_id: Optional[UUID] = Field(None, description="父文件夹ID")


class FolderCreate(FolderBase):
    """创建文件夹 Schema"""
    tags: Optional[list[str]] = Field(None, description="文件夹标签名称列表")


class FolderUpdate(BaseModel):
    """更新文件夹 Schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="文件夹名称")
    summary: Optional[str] = Field(None, description="文件夹摘要")
    parent_id: Optional[UUID] = Field(None, description="父文件夹ID")
    tags: Optional[list[str]] = Field(None, description="文件夹标签名称列表")


class FolderRead(FolderBase):
    """文件夹读取 Schema"""
    id: UUID
    tenant_id: UUID
    owner_id: UUID
    path: str
    full_name_path: Optional[str] = None
    level: int
    created_by_id: Optional[UUID]
    created_by_name: Optional[str]
    updated_by_id: Optional[UUID]
    updated_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FolderTreeNode(FolderRead):
    """文件夹树节点 Schema（包含子节点）"""
    children: list["FolderTreeNode"] = Field(default_factory=list, description="子文件夹列表")
    
    class Config:
        from_attributes = True
