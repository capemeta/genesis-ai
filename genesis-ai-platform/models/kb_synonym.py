"""
同义词主表模型

对应表：kb_synonyms
SQL 定义：docker/postgresql/init-schema.sql
"""
from typing import TYPE_CHECKING, Optional, List
from uuid import UUID as PyUUID

from sqlalchemy import String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, AuditMixin

if TYPE_CHECKING:
    from models.kb_synonym_variant import KBSynonymVariant


class KBSynonym(Base, AuditMixin):
    """
    同义词主表模型

    一个标准词一条记录，口语词通过子表维护。
    """

    __tablename__ = "kb_synonyms"
    __searchable_fields__ = ["professional_term", "description"]

    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID",
    )

    kb_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="所属知识库ID，NULL表示租户级公共标准词",
    )

    professional_term: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="标准词（专业说法）",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="优先级，值越小优先级越高",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="启用状态",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注说明",
    )

    variants: Mapped[List["KBSynonymVariant"]] = relationship(
        "KBSynonymVariant",
        back_populates="synonym",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<KBSynonym(id={self.id}, professional_term={self.professional_term})>"
