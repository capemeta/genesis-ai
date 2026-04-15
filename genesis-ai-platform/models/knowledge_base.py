"""
知识库模型
"""
from typing import Optional
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base, AuditMixin


class KnowledgeBase(Base, AuditMixin):
    """
    知识库主表
    
    继承 AuditMixin 自动获得审计字段：
    - created_by_id, created_by_name
    - updated_by_id, updated_by_name
    
    Base 已提供：
    - id (UUID)
    - created_at, updated_at
    """
    __tablename__ = "knowledge_bases"
    
    # 🔍 搜索字段配置（用于 crud_factory 的模糊搜索）
    __searchable_fields__ = ["name", "description"]
    
    # 租户隔离
    tenant_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 所有权
    owner_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="知识库所有者ID"
    )
    
    # 业务字段
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="知识库名称，租户内唯一"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="知识库描述信息"
    )
    
    icon_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="知识库图标URL"
    )
    
    visibility: Mapped[str] = mapped_column(
        String(20),
        default="private",
        nullable=False,
        comment="可见性：private-私有，tenant_public-租户内公开"
    )
    
    type: Mapped[str] = mapped_column(
        String(50),
        default="general",
        nullable=False,
        comment="知识库类型：general-通用, qa-问答, table-表格, web-网页, media-多媒体, connector-同步应用"
    )
    
    # RAG 配置字段
    chunking_mode: Mapped[str] = mapped_column(
        String(20),
        default="smart",
        nullable=False,
        comment="分块模式：smart-智能分块（系统最佳实践）, custom-自定义分块（使用 chunking_config）"
    )
    chunking_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="分块配置，仅承载分块策略、块大小、重叠等结构参数"
    )
    
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="嵌入模型名称，如 'text-embedding-3-small'"
    )
    
    embedding_model_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
        comment="使用的向量租户模型ID（tenant_models.id）"
    )
    
    index_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="索引模型名称，用于文档理解与检索增强"
    )

    index_model_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
        comment="使用的索引租户模型ID（tenant_models.id）"
    )
    
    vision_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="视觉模型名称，用于图片/PDF中的图像理解"
    )

    vision_model_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
        comment="使用的视觉租户模型ID（tenant_models.id）"
    )
    
    pdf_parser_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "parser": "native",
            "enable_ocr": True,
            "ocr_engine": "auto",
            "ocr_languages": ["ch", "en"],
            "extract_images": False,
            "extract_tables": True
        },
        comment="PDF解析器配置，包含解析引擎和OCR设置"
    )
    
    retrieval_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="检索配置，如{ 'top_k': 5, 'score_threshold': 0.7, 'rerank': true }"
    )

    intelligence_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="智能能力配置，统一承载 enhancement、knowledge_graph、raptor"
    )

    # 约束
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_kb_tenant_name"),
        CheckConstraint(
            "visibility IN ('private', 'tenant_public')",
            name="check_kb_visibility"
        ),
        CheckConstraint(
            "type IN ('general', 'qa', 'table', 'web', 'media', 'connector')",
            name="check_kb_type"
        ),
        CheckConstraint(
            "chunking_mode IN ('smart', 'custom')",
            name="check_kb_chunking_mode"
        ),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name={self.name}, type={self.type})>"
