"""
标签 Schema 定义
"""
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List

TAG_TARGET_TYPES = ["folder", "kb", "kb_doc"]


class TagBase(BaseModel):
    """标签基础 Schema"""
    name: str = Field(..., min_length=1, max_length=255, description="标签名称")
    aliases: Optional[List[str]] = Field(None, description="标签别名")
    description: Optional[str] = Field(None, description="标签语义描述")
    color: str = Field(default="blue", description="标签颜色，支持预设颜色名或十六进制颜色值")
    allowed_target_types: List[str] = Field(
        default_factory=lambda: ["kb_doc"],
        description="标签适用对象，支持 kb / kb_doc / folder 多选"
    )
    kb_id: Optional[UUID] = Field(None, description="所属知识库ID，NULL表示全局标签")


class TagCreate(TagBase):
    """创建标签 Schema"""
    pass


class TagUpdate(BaseModel):
    """更新标签 Schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="标签名称")
    aliases: Optional[List[str]] = Field(None, description="标签别名")
    description: Optional[str] = Field(None, description="标签语义描述")
    color: Optional[str] = Field(None, description="标签颜色，支持预设颜色名或十六进制颜色值")
    allowed_target_types: Optional[List[str]] = Field(
        None,
        description="标签适用对象，支持 kb / kb_doc / folder 多选"
    )


class TagRead(BaseModel):
    """标签读取 Schema"""
    id: UUID
    tenant_id: UUID
    name: str
    aliases: Optional[List[str]] = None
    description: Optional[str] = None
    color: Optional[str] = Field(default="blue", description="标签颜色，支持预设颜色名或十六进制颜色值")
    allowed_target_types: List[str] = Field(default_factory=lambda: ["kb_doc"])
    kb_id: Optional[UUID] = None
    created_by_id: Optional[UUID]
    created_by_name: Optional[str]
    updated_by_id: Optional[UUID]
    updated_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ResourceTagBase(BaseModel):
    """资源标签关联基础 Schema"""
    tag_id: UUID = Field(..., description="标签ID")
    target_id: UUID = Field(..., description="目标资源ID（folder 时为 folder.id，kb 时为 knowledge_bases.id，kb_doc 时为 knowledge_base_documents.id）")
    target_type: str = Field(..., description="目标类型：folder-文件夹、kb-知识库、kb_doc-知识库文档")
    kb_id: Optional[UUID] = Field(None, description="所属知识库ID")


class ResourceTagCreate(ResourceTagBase):
    """创建资源标签关联 Schema"""
    pass


class ResourceTagRead(ResourceTagBase):
    """资源标签关联读取 Schema"""
    id: UUID
    tenant_id: UUID
    action: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class FolderTagsRequest(BaseModel):
    """文件夹标签请求 Schema"""
    folder_id: UUID = Field(..., description="文件夹ID")
    tag_ids: List[UUID] = Field(..., description="标签ID列表")


class FolderTagsResponse(BaseModel):
    """文件夹标签响应 Schema"""
    folder_id: UUID
    tags: List[TagRead]


class KbDocTagsRequest(BaseModel):
    """知识库文档标签请求 Schema（resource_tags.target_type=kb_doc）"""
    kb_doc_id: UUID = Field(..., description="知识库文档ID（knowledge_base_documents.id）")
    tag_ids: List[UUID] = Field(..., description="标签ID列表")


class KbDocTagsResponse(BaseModel):
    """知识库文档标签响应 Schema"""
    kb_doc_id: UUID
    tags: List[TagRead]


class KbTagsRequest(BaseModel):
    """知识库标签请求 Schema（resource_tags.target_type=kb）"""
    kb_id: UUID = Field(..., description="知识库ID（knowledge_bases.id）")
    tag_ids: List[UUID] = Field(..., description="标签ID列表")


class KbTagsResponse(BaseModel):
    """知识库标签响应 Schema"""
    kb_id: UUID
    tags: List[TagRead]
