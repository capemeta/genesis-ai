"""
知识库-文档关联模型

对应表：knowledge_base_documents
SQL 定义：docker/postgresql/init-schema.sql
"""
from typing import Optional, TYPE_CHECKING
from uuid import UUID as PyUUID
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, BIGINT, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from models.base import Base, AuditMixin
from models.kb_doc_runtime import KBDocRuntime

if TYPE_CHECKING:
    from models.document import Document
    from models.folder import Folder


class KnowledgeBaseDocument(Base, AuditMixin):
    """
    知识库-文档关联模型
    
    对应表：knowledge_base_documents
    管理文档在特定知识库中的解析状态、摘要及配置
    
    继承 AuditMixin 自动获得审计字段：
    - created_by_id, updated_by_id
    - created_by_name, updated_by_name
    - created_at, updated_at
    """
    __tablename__ = "knowledge_base_documents"
    
    # 租户隔离
    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 关联字段
    kb_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="知识库ID"
    )
    
    document_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="关联的物理文档ID"
    )
    
    folder_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="在知识库中的逻辑文件夹位置"
    )
    
    display_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="显示名称（可选），为空时使用 documents.name"
    )

    owner_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="资源所有者"
    )
    
    # 解析状态与内容
    parse_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
        comment="解析状态：pending-等待启动、queued-排队中、processing-解析中、completed-已完成、failed-失败"
    )

    parse_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="解析失败时的错误信息"
    )
    
    parse_progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="解析进度，0-100，用于前端进度条显示"
    )
    
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="解析生成的切片总数"
    )
    
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="针对该知识库语境生成的文档摘要"
    )

    custom_metadata: Mapped[dict] = mapped_column(
        "metadata",  # 数据库字段名
        JSONB,
        default=dict,
        nullable=True,
        comment="业务元数据，如{'year': 2024}，覆盖或补充 global metadata"
    )
    
    # 解析配置
    parse_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="解析配置重载"
    )
    
    chunking_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="分块配置"
    )

    intelligence_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="文档级智能能力覆盖配置，统一承载 enhancement、knowledge_graph、raptor"
    )

    runtime_stage: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment="运行阶段"
    )

    runtime_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="运行态更新时间"
    )

    # 解析时间统计
    parse_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始解析时间"
    )
    
    parse_ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="解析完成时间"
    )
    
    parse_duration_milliseconds: Mapped[Optional[int]] = mapped_column(
        BIGINT,
        nullable=True,
        comment="总解析耗时（毫秒）"
    )
    
    task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Celery 任务 ID"
    )

    markdown_document_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="中间转换后的 Markdown 文档 ID (用于预览)"
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="显示顺序"
    )
    
    # 启用状态
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否参与检索"
    )

    # 关系定义
    document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[document_id],
        primaryjoin="KnowledgeBaseDocument.document_id == Document.id",
        viewonly=True, # 仅用于查询
    )
    
    folder: Mapped[Optional["Folder"]] = relationship(
        "Folder",
        foreign_keys=[folder_id],
        primaryjoin="KnowledgeBaseDocument.folder_id == Folder.id",
        viewonly=True,  # 仅用于查询
    )
    
    runtime: Mapped[Optional["KBDocRuntime"]] = relationship(
        "KBDocRuntime",
        primaryjoin=lambda: KnowledgeBaseDocument.id == foreign(KBDocRuntime.kb_doc_id),
        uselist=False,
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseDocument(id={self.id}, kb_id={self.kb_id}, document_id={self.document_id}, parse_status={self.parse_status})>"
