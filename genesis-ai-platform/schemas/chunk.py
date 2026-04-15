"""
切片 Schema 定义
"""
from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from schemas.common import ListRequest


class ChunkBase(BaseModel):
    """切片基础 Schema"""
    content: str = Field(..., description="切片检索文本内容")
    original_content: Optional[str] = Field(None, description="原始检索文本快照，仅在内容被编辑后存在")
    content_hash: Optional[str] = Field(None, description="canonical content 哈希，用于增量重建检索投影")
    content_blocks: list[dict[str, Any]] = Field(default_factory=list, description="结构化正文流")
    structure_version: int = Field(default=1, description="内容结构协议版本")
    token_count: int = Field(default=0, description="Token 数量")
    text_length: int = Field(default=0, description="文本字符长度")
    summary: Optional[str] = Field(None, description="分块摘要主字段；增强摘要统一落此顶层字段")
    chunk_type: str = Field(default="text", description="切片类型：text, html, image, table, media, qa, code, json, summary, mixed")
    status: str = Field(default="success", description="状态")
    is_active: bool = Field(default=True, description="是否激活")
    display_enabled: bool = Field(default=True, description="是否允许作为最终上下文展示")
    is_content_edited: bool = Field(default=False, description="是否已编辑检索文本")
    position: int = Field(default=0, description="在文档中的位置序号")
    path: Optional[str] = Field(None, description="文档内部结构路径（ltree）")
    parent_id: Optional[int] = Field(None, description="父切片ID")
    source_type: str = Field(default="document", description="内容来源类型")
    content_group_id: Optional[UUID] = Field(None, description="业务聚合单元ID")
    metadata_info: dict = Field(
        default_factory=dict,
        description=(
            "分块元数据；增强协议统一使用 metadata_info.enhancement，"
            "其中关键词为 enhancement.keywords，检索问题为 enhancement.questions"
        ),
    )


class ChunkCreate(ChunkBase):
    """创建切片 Schema"""
    kb_id: UUID = Field(..., description="所属知识库ID")
    document_id: UUID = Field(..., description="所属物理文档ID")
    kb_doc_id: UUID = Field(..., description="所属知识库文档挂载ID")


class ChunkUpdate(BaseModel):
    """更新切片 Schema"""
    content: Optional[str] = Field(None, description="切片检索文本内容")
    original_content: Optional[str] = Field(None, description="原始检索文本快照")
    content_blocks: Optional[list[dict[str, Any]]] = Field(None, description="结构化正文流")
    structure_version: Optional[int] = Field(None, description="内容结构协议版本")
    token_count: Optional[int] = Field(None, description="Token 数量")
    text_length: Optional[int] = Field(None, description="文本字符长度")
    summary: Optional[str] = Field(None, description="分段摘要")
    chunk_type: Optional[str] = Field(None, description="切片类型")
    status: Optional[str] = Field(None, description="状态")
    is_active: Optional[bool] = Field(None, description="是否激活")
    display_enabled: Optional[bool] = Field(None, description="是否允许作为最终上下文展示")
    is_content_edited: Optional[bool] = Field(None, description="是否已编辑检索文本")
    position: Optional[int] = Field(None, description="位置序号")
    path: Optional[str] = Field(None, description="文档内部结构路径")
    parent_id: Optional[int] = Field(None, description="父切片ID")
    source_type: Optional[str] = Field(None, description="内容来源类型")
    content_group_id: Optional[UUID] = Field(None, description="业务聚合单元ID")
    metadata_info: Optional[dict] = Field(
        None,
        description=(
            "分块元数据；增强协议统一使用 metadata_info.enhancement，"
            "其中关键词为 enhancement.keywords，检索问题为 enhancement.questions"
        ),
    )


class ChunkRead(ChunkBase):
    """读取切片 Schema"""
    id: int = Field(..., description="切片ID")
    tenant_id: UUID = Field(..., description="所属租户ID")
    kb_id: UUID = Field(..., description="所属知识库ID")
    document_id: UUID = Field(..., description="所属物理文档ID")
    kb_doc_id: UUID = Field(..., description="所属知识库文档挂载ID")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(
        from_attributes=True,
    )


class ChunkListRequest(ListRequest):
    """
    切片列表请求 Schema

    继承 ListRequest 自动获得：
    - 分页参数（page, page_size）
    - 排序参数（sort_by, sort_order）
    - 过滤参数（search, filters, advanced_filters）
    - Refine 兼容参数（_start, _end, _sort, _order, q）
    - 辅助方法（get_page(), get_page_size(), get_order_by(), get_search()）
    """
    pass


class ChunkNodeIdRequest(BaseModel):
    """按 node_id 获取切片的请求体。"""

    node_id: str = Field(..., min_length=1, description="分块层级节点 ID")
