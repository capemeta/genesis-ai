"""
检索投影模型

对应表：chunk_search_units
"""
from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.session import Base as SQLAlchemyBase


class ChunkSearchUnit(SQLAlchemyBase):
    """canonical chunk 的检索投影表。"""

    __tablename__ = "chunk_search_units"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="检索投影ID",
    )
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
    chunk_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="关联 canonical chunk ID",
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
    content_group_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="业务聚合单元ID",
    )
    search_scope: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="检索语义域，如 default/question/answer/summary",
    )
    search_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="真正送入检索引擎的文本",
    )
    search_text_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="检索文本哈希",
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="检索文本 Token 数",
    )
    text_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="检索文本字符数",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否激活",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否主检索投影",
    )
    priority: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=100,
        comment="默认优先级",
    )
    metadata_info: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="检索元数据",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="更新时间",
    )
