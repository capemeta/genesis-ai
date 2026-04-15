"""
术语与同义词相关 Schema
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class KBGlossaryBase(BaseModel):
    """术语基础 Schema"""

    kb_id: Optional[UUID] = Field(default=None, description="所属知识库ID，NULL表示租户级公共术语")
    term: str = Field(..., min_length=1, max_length=255, description="标准术语名称")
    definition: str = Field(..., min_length=1, description="术语定义")
    examples: Optional[str] = Field(default=None, description="术语示例")
    is_active: bool = Field(default=True, description="启用状态")


class KBGlossaryCreate(KBGlossaryBase):
    """术语创建 Schema"""


class KBGlossaryUpdate(BaseModel):
    """术语更新 Schema"""

    kb_id: Optional[UUID] = Field(default=None, description="所属知识库ID")
    term: Optional[str] = Field(default=None, min_length=1, max_length=255, description="标准术语名称")
    definition: Optional[str] = Field(default=None, min_length=1, description="术语定义")
    examples: Optional[str] = Field(default=None, description="术语示例")
    is_active: Optional[bool] = Field(default=None, description="启用状态")


class KBGlossaryRead(KBGlossaryBase):
    """术语读取 Schema"""

    id: UUID
    tenant_id: UUID
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBSynonymBase(BaseModel):
    """同义词主表基础 Schema"""

    kb_id: Optional[UUID] = Field(default=None, description="所属知识库ID，NULL表示租户级公共标准词")
    professional_term: str = Field(..., min_length=1, max_length=255, description="标准词（专业说法）")
    priority: int = Field(default=100, ge=0, le=100000, description="优先级，值越小优先")
    is_active: bool = Field(default=True, description="启用状态")
    description: Optional[str] = Field(default=None, description="备注说明")


class KBSynonymCreate(KBSynonymBase):
    """同义词主表创建 Schema"""


class KBSynonymUpdate(BaseModel):
    """同义词主表更新 Schema"""

    kb_id: Optional[UUID] = Field(default=None, description="所属知识库ID")
    professional_term: Optional[str] = Field(default=None, min_length=1, max_length=255, description="标准词")
    priority: Optional[int] = Field(default=None, ge=0, le=100000, description="优先级")
    is_active: Optional[bool] = Field(default=None, description="启用状态")
    description: Optional[str] = Field(default=None, description="备注说明")


class KBSynonymRead(KBSynonymBase):
    """同义词主表读取 Schema"""

    id: UUID
    tenant_id: UUID
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBSynonymVariantBase(BaseModel):
    """同义词口语子表基础 Schema"""

    synonym_id: UUID = Field(..., description="关联标准词ID")
    user_term: str = Field(..., min_length=1, max_length=255, description="用户口语词")
    is_active: bool = Field(default=True, description="启用状态")
    description: Optional[str] = Field(default=None, description="备注说明")


class KBSynonymVariantCreate(KBSynonymVariantBase):
    """同义词口语子表创建 Schema"""


class KBSynonymVariantUpdate(BaseModel):
    """同义词口语子表更新 Schema"""

    synonym_id: Optional[UUID] = Field(default=None, description="关联标准词ID")
    user_term: Optional[str] = Field(default=None, min_length=1, max_length=255, description="用户口语词")
    is_active: Optional[bool] = Field(default=None, description="启用状态")
    description: Optional[str] = Field(default=None, description="备注说明")


class KBSynonymVariantRead(KBSynonymVariantBase):
    """同义词口语子表读取 Schema"""

    id: UUID
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SynonymRewritePreviewRequest(BaseModel):
    """同义词改写预览请求"""

    kb_id: Optional[UUID] = Field(default=None, description="知识库ID，传入后优先使用知识库级规则")
    query: str = Field(..., min_length=1, description="用户原始查询")


class SynonymRewriteMatch(BaseModel):
    """同义词命中详情"""

    user_term: str = Field(..., description="命中的用户口语词")
    professional_term: str = Field(..., description="映射到的标准词")
    synonym_id: UUID = Field(..., description="标准词记录ID")
    variant_id: UUID = Field(..., description="口语词记录ID")
    scope: str = Field(..., description="规则作用域：kb 或 tenant")


class SynonymRewritePreviewResponse(BaseModel):
    """同义词改写预览响应"""

    raw_query: str = Field(..., description="原始查询")
    rewritten_query: str = Field(..., description="改写后的查询")
    matches: List[SynonymRewriteMatch] = Field(default_factory=list, description="命中规则列表")


class SynonymVariantBatchItem(BaseModel):
    """同义词口语批量项"""

    user_term: str = Field(..., min_length=1, max_length=255, description="用户口语词")
    is_active: bool = Field(default=True, description="启用状态")
    description: Optional[str] = Field(default=None, description="备注说明")


class SynonymVariantBatchUpsertRequest(BaseModel):
    """同义词口语批量维护请求"""

    synonym_id: UUID = Field(..., description="标准词ID")
    variants: List[SynonymVariantBatchItem] = Field(default_factory=list, description="口语词列表")
    replace: bool = Field(
        default=False,
        description="是否替换模式：true-以本次列表为准删除其余口语；false-仅新增/更新",
    )


class SynonymVariantBatchUpsertResponse(BaseModel):
    """同义词口语批量维护响应"""

    synonym_id: UUID = Field(..., description="标准词ID")
    inserted_count: int = Field(..., description="新增数量")
    updated_count: int = Field(..., description="更新数量")
    deleted_count: int = Field(..., description="删除数量")
    total_count: int = Field(..., description="处理后总数量")
