"""
知识库文档运行态模型

对应表：kb_doc_runtime
"""
from uuid import UUID as PyUUID
from datetime import datetime

from sqlalchemy import DateTime, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.session import Base as SQLAlchemyBase


class KBDocRuntime(SQLAlchemyBase):
    """仅保存最新一次运行的文档级运行上下文。"""

    __tablename__ = "kb_doc_runtime"

    kb_doc_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        comment="知识库文档ID",
    )
    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="租户ID",
    )
    kb_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="知识库ID",
    )
    document_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="物理文档ID",
    )

    pipeline_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="当前流水线任务ID",
    )

    effective_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="本次实际生效配置",
    )
    parse_context: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="解析阶段全局上下文",
    )
    chunk_context: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="分块阶段全局上下文",
    )
    enhance_context: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="增强阶段全局上下文",
    )
    tag_context: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="标签阶段全局上下文",
    )
    summary_context: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="摘要阶段全局上下文",
    )
    stats: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="运行统计",
    )
    error_detail: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="结构化错误信息",
    )

    context_version: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        comment="运行态协议版本",
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
