"""
标签模型

对应表：tags
SQL 定义：docker/postgresql/init-schema.sql
"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from uuid import UUID as PyUUID
from typing import Optional

from models.base import Base, AuditMixin


class Tag(Base, AuditMixin):
    """
    标签模型 - 支持文档分类和检索
    
    对应表：tags
    SQL 定义：docker/postgresql/init-schema.sql
    
    继承 AuditMixin 自动获得审计字段：
    - created_by_id, updated_by_id
    - created_by_name, updated_by_name
    - created_at, updated_at
    """
    __tablename__ = "tags"
    
    # 配置可搜索字段（用于 search 参数的模糊搜索）
    __searchable_fields__ = ["name", "description"]
    
    # 租户隔离
    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 业务字段
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="标签名称"
    )
    
    aliases: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment='标签别名，如["AI", "人工智能"]'
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="标签语义描述，用于 AI 理解"
    )
    
    color: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="blue",
        comment="标签颜色，用于前端显示"
    )

    allowed_target_types: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: ["kb_doc"],
        comment="标签适用对象，如['kb']、['kb_doc']、['folder'] 或多选组合"
    )
    
    kb_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="所属知识库ID，NULL表示全局标签"
    )
    
    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name={self.name})>"
