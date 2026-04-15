"""
文本切片模型

对应表：chunks
SQL 定义：docker/postgresql/init-schema.sql
"""
from typing import Optional
from uuid import UUID as PyUUID
from datetime import datetime
from sqlalchemy import String, Text, Integer, BIGINT, Boolean, DateTime, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.types import UserDefinedType

from models.base import Base


class LTREE(UserDefinedType):
    """PostgreSQL ltree 类型"""
    cache_ok = True

    def get_col_spec(self, **kw):
        return "LTREE"

    def bind_processor(self, dialect):
        def process(value):
            return value
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            return value
        return process


class Chunk(Base):
    """
    文本切片模型 - 存储解析后的段落内容

    对应表：chunks
    由于数据量大，主键使用 BIGINT 自增，而非 UUID。
    只有 created_at，没有 updated_at（海量数据优化）。
    """
    __tablename__ = "chunks"

    # 配置可搜索字段（用于 search 参数的模糊搜索）
    __searchable_fields__ = ["content", "summary"]

    # 覆盖 Base 的 UUID id，使用 BIGINT 自增
    id: Mapped[int] = mapped_column(  # type: ignore[assignment]
        BIGINT,
        primary_key=True,
        autoincrement=True,
        comment="分段ID"
    )

    # 覆盖 Base 的 created_at（使用数据库默认值）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )

    # 明确排除 updated_at（chunks 表没有此字段）
    updated_at = None  # type: ignore[assignment]

    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )

    kb_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属知识库ID"
    )

    document_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属物理文档ID"
    )

    kb_doc_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属知识库文档挂载ID"
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="切片文本内容"
    )

    original_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="原始检索文本快照，仅在用户编辑后保存"
    )

    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="canonical content 哈希，用于增量重建检索投影"
    )

    content_blocks: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="分段内容块，text/code/image/table"
    )

    structure_version: Mapped[int] = mapped_column(
        SmallInteger,
        default=1,
        nullable=False,
        comment="内容结构版本"
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="文本对应的Token数"
    )

    text_length: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="文本字符长度"
    )

    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="分块摘要主字段；增强摘要统一落此顶层字段"
    )

    chunk_type: Mapped[str] = mapped_column(
        String(20),
        default="text",
        comment="切片类型：text, html, image, table, media, qa, code, json, summary, mixed"
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="success",
        comment="状态"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否激活"
    )

    display_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否允许作为最终上下文展示给前端或 LLM"
    )

    is_content_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否已编辑检索文本，不影响 content_blocks 原始结构"
    )

    position: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="在文档中的位置序号"
    )

    path: Mapped[Optional[str]] = mapped_column(
        LTREE,
        nullable=True,
        comment="文档内部结构路径（ltree），如 'root.chap1.sec1'"
    )

    parent_id: Mapped[Optional[int]] = mapped_column(
        BIGINT,
        nullable=True,
        comment="父切片ID"
    )

    source_type: Mapped[str] = mapped_column(
        String(30),
        default="document",
        nullable=False,
        comment="内容来源类型：document, qa, table, web, graph_context"
    )

    content_group_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="业务聚合单元ID，用于将多个 chunk 聚合回同一条记录或同一组内容"
    )

    metadata_info: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="分块元数据；增强协议统一使用 enhancement，其中关键词为 enhancement.keywords，检索问题为 enhancement.questions"
    )

    # 表级约束和索引
    __table_args__ = ()

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, kb_id={self.kb_id}, content_len={len(self.content)})>"
