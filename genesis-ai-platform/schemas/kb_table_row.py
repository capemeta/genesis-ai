"""
表格知识库行 Schema 定义
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TableRowDatasetDetailRequest(BaseModel):
    """获取表格数据集详情请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")


class TableRowListRequest(BaseModel):
    """列出表格行请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")
    include_deleted: bool = Field(default=False, description="是否包含已删除行")
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    search: Optional[str] = Field(default=None, description="全局搜索关键词")
    column_filters: Dict[str, str] = Field(default_factory=dict, description="字段筛选条件")


class TableRowUpdatePayload(BaseModel):
    """更新表格行数据载荷。"""

    row_data: Dict[str, Any] = Field(..., description="完整行数据")


class TableRowUpdateRequest(BaseModel):
    """更新单条表格行请求。"""

    row_id: UUID = Field(..., description="表格行ID")
    item: TableRowUpdatePayload = Field(..., description="行数据")


class TableRowCreatePayload(BaseModel):
    """新增表格行数据载荷。"""

    sheet_name: Optional[str] = Field(default=None, description="目标工作表名称")
    row_data: Dict[str, Any] = Field(..., description="完整行数据")


class TableRowCreateRequest(BaseModel):
    """新增单条表格行请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")
    item: TableRowCreatePayload = Field(..., description="新增行数据")


class TableRowRebuildRequest(BaseModel):
    """基于 kb_table_rows 重新生成 chunk 请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")


class TableRowDeleteRequest(BaseModel):
    """删除单条表格行请求。"""

    row_id: UUID = Field(..., description="表格行ID")


class TableRowRead(BaseModel):
    """表格行响应结构。"""

    id: UUID
    kb_doc_id: UUID
    row_uid: str
    sheet_name: str
    row_index: int
    source_row_number: Optional[int] = None
    source_type: str
    row_version: int
    is_deleted: bool
    row_data: Dict[str, Any]
    source_meta: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TableRowListResponse(BaseModel):
    """表格行列表响应。"""

    dataset: Dict[str, Any]
    rows: List[TableRowRead]
    total: int
    page: int
    page_size: int
