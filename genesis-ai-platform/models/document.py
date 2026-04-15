"""
文档载体模型

对应表：documents
SQL 定义：docker/postgresql/init-schema.sql
"""
from typing import Optional
from datetime import datetime
from uuid import UUID as PyUUID
from sqlalchemy import String, BIGINT, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from models.base import Base, AuditMixin


class Document(Base, AuditMixin):
    """
    文档载体模型。

    对应表：documents
    仅表达“载体对象”本身，不承载知识库内容语义。
    可以表示：
    - 上传文件
    - 系统生成快照
    - 远程页面/第三方对象

    继承 AuditMixin 自动获得审计字段：
    - created_by_id, updated_by_id
    - created_by_name, updated_by_name
    - created_at, updated_at
    """
    __tablename__ = "documents"
    
    # 配置可搜索字段（用于 search 参数的模糊搜索）
    __searchable_fields__ = ["name", "file_type"]
    
    # 租户隔离
    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 所有权
    owner_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="文档所有者ID"
    )
    
    # 业务字段
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="文档名称，含扩展名"
    )
    
    file_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="文件类型（PDF/DOCX等），通常为大写后缀"
    )
    
    storage_driver: Mapped[str] = mapped_column(
        String(20),
        default="local",
        nullable=False,
        comment="存储驱动：local-本地、s3-AWS S3、oss-阿里云OSS"
    )
    
    bucket_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="存储位置：S3存储-bucket名称（如genesis-ai-files），本地存储-基础路径（如./storage-data）"
    )
    
    file_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="文件存储路径/键名（相对于bucket_name的路径）"
    )
    
    file_size: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
        default=0,
        comment="文件大小，单位字节"
    )
    
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME类型"
    )

    carrier_type: Mapped[str] = mapped_column(
        String(50),
        default="file",
        nullable=False,
        index=True,
        comment="载体对象类型：file/url/web_page/feishu_doc/github_repo/github_blob/lark_doc/generated_snapshot/api_object"
    )

    asset_kind: Mapped[str] = mapped_column(
        String(20),
        default="physical",
        nullable=False,
        index=True,
        comment="载体存在形态：physical-物理文件、virtual-虚拟快照、remote-远程对象"
    )
    
    source_type: Mapped[str] = mapped_column(
        String(50),
        default="upload",
        nullable=False,
        index=True,
        comment="进入系统方式：upload-上传、manual-人工创建、crawl-抓取、sync-同步、system-系统生成"
    )
    
    source_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="来源URL"
    )
    
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="文件内容哈希（SHA256），用于去重"
    )
    
    metadata_info: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="原始元数据"
    )
    
    # 软删除字段
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="软删除标志：false-正常，true-已删除"
    )
    
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="删除时间，用于审计和定期清理"
    )
    
    deleted_by_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="删除人ID"
    )
    
    deleted_by_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="删除人名称（冗余字段）"
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, name={self.name}, carrier_type={self.carrier_type}, "
            f"asset_kind={self.asset_kind}, source_type={self.source_type}, is_deleted={self.is_deleted})>"
        )
