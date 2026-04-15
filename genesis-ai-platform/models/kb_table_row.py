"""
表格知识库行模型

对应表：kb_table_rows
用于承载表格知识库中的结构化行记录，是 Excel/CSV 表格分块的上游事实来源。
"""
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import String, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, AuditMixin


class KBTableRow(Base, AuditMixin):
    """
    表格知识库行主事实模型。

    一条记录表示一个表格知识库文档中的一条结构化业务记录。
    """

    __tablename__ = "kb_table_rows"

    __searchable_fields__ = ["row_uid", "sheet_name"]

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

    kb_doc_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属知识库文档挂载ID",
    )

    document_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属物理文档ID",
    )

    row_uid: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="行级稳定业务键",
    )

    sheet_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="所属工作表名称",
    )

    row_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="数据区内行序号（1-based，不含表头）",
    )

    source_row_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Excel 原始物理行号（1-based，含表头偏移）",
    )

    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="excel_import",
        comment="来源类型：excel_import/manual",
    )

    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="行版本号，编辑后递增",
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否软删除",
    )

    row_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="行内容哈希，用于增量重建与变更检测",
    )

    row_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="行主事实数据，原始结构化记录",
    )

    source_meta: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="来源追溯信息",
    )

    def __repr__(self) -> str:
        return (
            f"<KBTableRow(id={self.id}, kb_doc_id={self.kb_doc_id}, "
            f"sheet_name={self.sheet_name!r}, row_index={self.row_index})>"
        )
