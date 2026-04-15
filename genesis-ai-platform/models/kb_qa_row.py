"""
QA 行模型

对应表：kb_qa_rows
用于承载 QA 数据集中的每一条问答记录，是 QA chunks 的上游事实来源。
"""
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from models.base import Base, AuditMixin


class KBQARow(Base, AuditMixin):
    """
    QA 主事实模型。

    一条记录表示一个 QA 数据集中的一条问答。
    """

    __tablename__ = "kb_qa_rows"

    __searchable_fields__ = ["question", "answer", "category"]

    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID",
    )

    kb_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属知识库ID",
    )

    document_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属载体文档ID",
    )

    kb_doc_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属知识库文档挂载ID",
    )

    source_row_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="稳定来源记录ID",
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="在当前问答集中的稳定顺序",
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="标准问题",
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="标准答案",
    )

    similar_questions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="相似问题数组",
    )

    category: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="问答分类",
    )

    tags: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="标签数组",
    )

    source_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="imported",
        comment="来源模式：imported/manual",
    )

    source_row: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="来源行号",
    )

    source_sheet_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="来源工作表名称",
    )

    has_manual_edits: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否发生过人工修改",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用参与检索",
    )

    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="内容哈希，用于增量重建",
    )

    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="内容版本号，更新时递增",
    )

    def __repr__(self) -> str:
        return (
            f"<KBQARow(id={self.id}, kb_doc_id={self.kb_doc_id}, "
            f"position={self.position}, question={self.question[:20]!r})>"
        )
