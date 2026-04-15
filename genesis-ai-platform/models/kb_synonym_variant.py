"""
同义词口语子表模型

对应表：kb_synonym_variants
SQL 定义：docker/postgresql/init-schema.sql
"""
from typing import TYPE_CHECKING, Optional
from uuid import UUID as PyUUID

from sqlalchemy import String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, AuditMixin

if TYPE_CHECKING:
    from models.kb_synonym import KBSynonym


class KBSynonymVariant(Base, AuditMixin):
    """
    同义词口语子表模型

    一个口语一条记录，归属于一个标准词。
    """

    __tablename__ = "kb_synonym_variants"
    __searchable_fields__ = ["user_term", "description"]

    synonym_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("kb_synonyms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联标准词ID",
    )

    user_term: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="用户口语词",
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

    synonym: Mapped["KBSynonym"] = relationship(
        "KBSynonym",
        back_populates="variants",
    )

    def __repr__(self) -> str:
        return f"<KBSynonymVariant(id={self.id}, user_term={self.user_term})>"
