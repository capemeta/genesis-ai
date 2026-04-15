"""
QA 行 Schema 定义
"""
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class QAItemStructured(BaseModel):
    """QA 内容结构。"""

    question: str = Field(..., min_length=1, description="标准问题")
    answer: str = Field(..., min_length=1, description="标准答案")
    similar_questions: List[str] = Field(default_factory=list, description="相似问题")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    category: Optional[str] = Field(None, description="分类")


class QAVirtualDatasetCreateRequest(BaseModel):
    """创建 QA 虚拟文件数据集请求。"""

    kb_id: UUID = Field(..., description="知识库ID")
    dataset_name: str = Field(..., min_length=1, max_length=255, description="问答集名称")
    folder_id: Optional[UUID] = Field(None, description="所属文件夹ID")
    items: List[QAItemStructured] = Field(default_factory=list, description="初始化问答")


class QAItemListRequest(BaseModel):
    """按数据集列出 QA 内容项请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")
    include_disabled: bool = Field(default=True, description="是否包含已禁用问答")


class QADatasetDetailRequest(BaseModel):
    """获取 QA 数据集详情请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")


class QAKBFacetRequest(BaseModel):
    """获取 QA 知识库可选分类/标签请求。"""

    kb_id: UUID = Field(..., description="知识库ID")


class QADatasetRebuildRequest(BaseModel):
    """基于 kb_qa_rows 重新生成 chunks 请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")


class QAItemCreateRequest(BaseModel):
    """创建 QA 内容项请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")
    item: QAItemStructured = Field(..., description="问答内容")


class QAItemBatchCreateRequest(BaseModel):
    """批量创建 QA 内容项请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")
    items: List[QAItemStructured] = Field(..., min_length=1, description="问答内容列表")


class QAItemUpdateRequest(BaseModel):
    """更新 QA 内容项请求。"""

    item_id: UUID = Field(..., description="QA 行ID")
    item: QAItemStructured = Field(..., description="问答内容")


class QAItemBatchUpdateEntry(BaseModel):
    """批量更新中的单条 QA 内容。"""

    item_id: UUID = Field(..., description="QA 行ID")
    item: QAItemStructured = Field(..., description="问答内容")


class QAItemBatchUpdateRequest(BaseModel):
    """批量更新 QA 内容项请求。"""

    items: List[QAItemBatchUpdateEntry] = Field(..., min_length=1, description="待更新问答列表")


class QAItemDeleteRequest(BaseModel):
    """删除 QA 内容项请求。"""

    item_id: UUID = Field(..., description="QA 行ID")


class QAItemBatchDeleteRequest(BaseModel):
    """批量删除 QA 内容项请求。"""

    item_ids: List[UUID] = Field(..., min_length=1, description="QA 行ID列表")


class QAItemToggleEnabledRequest(BaseModel):
    """启用或禁用 QA 内容项请求。"""

    item_id: UUID = Field(..., description="QA 行ID")
    enabled: bool = Field(..., description="目标启用状态")


class QAItemBatchToggleEnabledRequest(BaseModel):
    """批量启用或禁用 QA 内容项请求。"""

    item_ids: List[UUID] = Field(..., min_length=1, description="QA 行ID列表")
    enabled: bool = Field(..., description="目标启用状态")


class QAItemReorderEntry(BaseModel):
    """顺序调整中的单条问答位置。"""

    item_id: UUID = Field(..., description="QA 行ID")
    position: int = Field(..., ge=0, description="目标顺序位置")


class QAItemReorderRequest(BaseModel):
    """调整 QA 内容项顺序请求。"""

    kb_doc_id: UUID = Field(..., description="知识库文档挂载ID")
    items: List[QAItemReorderEntry] = Field(..., min_length=1, description="顺序列表")
