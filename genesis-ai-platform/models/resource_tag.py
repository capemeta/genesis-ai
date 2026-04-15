"""
资源标签关联模型

对应表：resource_tags
SQL 定义：docker/postgresql/init-schema.sql

target_type 约定（前后端统一，避免混淆）：
- folder: 文件夹，target_id = folder.id
- kb: 知识库，target_id = knowledge_bases.id
- kb_doc: 知识库文档（文件列表中的文档），target_id = knowledge_base_documents.id
"""
from sqlalchemy import String

# 与前端、SQL 注释一致，供 service 层复用
TARGET_TYPE_FOLDER = "folder"
TARGET_TYPE_KB = "kb"
TARGET_TYPE_KB_DOC = "kb_doc"
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from uuid import UUID as PyUUID
from typing import Optional

from models.base import Base, AuditMixin


class ResourceTag(Base, AuditMixin):
    """
    资源标签关联模型 - 支持文档、文件夹等多种资源打标签
    
    对应表：resource_tags
    SQL 定义：docker/postgresql/init-schema.sql
    
    继承 Base 类，自动包含：
    - id: UUID (主键)
    - created_at: TIMESTAMPTZ (创建时间)
    - updated_at: TIMESTAMPTZ (更新时间)
    
    继承 AuditMixin，自动包含：
    - created_by_id: UUID (创建人ID)
    - created_by_name: VARCHAR(255) (创建人名称)
    - updated_by_id: UUID (更新人ID)
    - updated_by_name: VARCHAR(255) (更新人名称)
    """
    __tablename__ = "resource_tags"
    
    # 租户隔离
    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 标签ID
    tag_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="标签ID"
    )
    
    # 目标资源
    target_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="目标资源ID"
    )
    
    target_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="目标类型：folder-文件夹、kb-知识库、kb_doc-知识库文档(knowledge_base_documents.id)"
    )
    
    # 知识库关联
    kb_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="所属知识库ID"
    )
    
    # 操作类型
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="add",
        comment="操作类型：add-添加、remove-移除"
    )
    
    def __repr__(self) -> str:
        return f"<ResourceTag(tag_id={self.tag_id}, target_id={self.target_id}, target_type={self.target_type})>"

