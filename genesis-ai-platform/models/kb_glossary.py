"""
专业术语模型

对应表：kb_glossaries
SQL 定义：docker/postgresql/init-schema.sql
"""
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, AuditMixin


class KBGlossary(Base, AuditMixin):
    """
    专业术语模型

    仅用于术语定义管理与生成阶段上下文增强，不参与查询改写。
    """

    __tablename__ = "kb_glossaries"
    __searchable_fields__ = ["term", "definition", "examples"]

    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID",
    )

    kb_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="所属知识库ID，NULL表示租户级公共术语",
    )

    term: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="标准术语名称",
    )

    definition: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="术语定义",
    )

    examples: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="术语示例",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="启用状态",
    )

    def __repr__(self) -> str:
        return f"<KBGlossary(id={self.id}, term={self.term})>"
