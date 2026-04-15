"""
文档 Schema 定义
包含物理文档与知识库挂载文档的定义
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, computed_field


class DocumentBase(BaseModel):
    """物理文档基础字段"""
    name: str = Field(..., description="文件名")
    file_type: Optional[str] = Field(None, description="文件扩展名")
    file_size: int = Field(0, description="文件大小(Bytes)")
    mime_type: Optional[str] = Field(None, description="MIME类型")
    carrier_type: str = Field("file", description="载体对象类型")
    asset_kind: str = Field("physical", description="载体存在形态")
    source_type: str = Field("upload", description="进入系统方式")
    source_url: Optional[str] = Field(None, description="来源URL")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="原始元数据")


class DocumentRead(DocumentBase):
    """物理文档读取接口返回"""
    id: UUID
    tenant_id: UUID
    owner_id: UUID
    content_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    id: UUID = Field(..., description="知识库文档关联ID")
    document_id: UUID = Field(..., description="物理文档ID")
    name: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小")
    file_type: Optional[str] = Field(None, description="文件类型")
    parse_status: str = Field(..., description="解析状态")
    is_duplicate: bool = Field(False, description="是否为重复文件")
    is_instant_upload: bool = Field(False, description="是否为秒传")


class KBDocumentBase(BaseModel):
    """知识库文档挂载基础字段"""
    kb_id: UUID
    document_id: UUID
    folder_id: Optional[UUID] = None
    parse_config: Optional[Dict[str, Any]] = None
    chunking_config: Dict[str, Any] = Field(default_factory=dict, description="分块配置")
    intelligence_config: Dict[str, Any] = Field(default_factory=dict, description="文档级智能能力覆盖配置")
    custom_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata", description="业务元数据")
    is_enabled: bool = True


class KBDocumentCreate(KBDocumentBase):
    """挂载文档创建"""
    pass


class KBDocumentUpdate(BaseModel):
    """挂载文档更新（状态、摘要等由后端任务系统更新）"""
    folder_id: Optional[UUID] = None
    parse_config: Optional[Dict[str, Any]] = None
    chunking_config: Optional[Dict[str, Any]] = None
    intelligence_config: Optional[Dict[str, Any]] = None
    custom_metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata", description="业务元数据")
    is_enabled: Optional[bool] = None


class KBDocumentRead(KBDocumentBase):
    """知识库文档读取（包含状态、耗时、日志等）"""
    id: UUID
    tenant_id: UUID
    owner_id: UUID
    parse_status: str
    parse_error: Optional[str] = None
    runtime_stage: Optional[str] = None
    runtime_updated_at: Optional[datetime] = None
    chunk_count: int = Field(..., description="切片总数")
    
    @computed_field
    @property
    def chunks(self) -> int:
        """映射 chunks 到 chunk_count，兼容前端"""
        return self.chunk_count

    summary: Optional[str] = None
    parsing_logs: List[Any] = []
    parse_started_at: Optional[datetime] = None
    parse_ended_at: Optional[datetime] = None
    parse_duration_milliseconds: Optional[int] = None
    display_order: int = 0
    created_at: datetime
    updated_at: datetime
    
    # 扩展字段：关联物理文件信息（方便前端一次性获取展示）
    document: Optional[DocumentRead] = None
    
    model_config = ConfigDict(from_attributes=True)


class KBDocumentListRequest(BaseModel):
    """列表查询参数"""
    kb_id: UUID
    folder_id: Optional[UUID] = None
    include_subfolders: bool = False
    parse_status: Optional[str] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 20

