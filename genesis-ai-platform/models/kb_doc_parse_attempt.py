"""
知识库文档解析尝试模型

对应表：kb_doc_parse_attempts
"""
from typing import Optional
from uuid import UUID as PyUUID
from datetime import datetime

from sqlalchemy import String, Integer, Text, BIGINT, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from models.base import Base


class KBDocParseAttempt(Base):
    """
    知识库文档解析尝试模型。

    一次解析 attempt 对应一条记录，步骤日志聚合存放在 logs_json 中。
    """

    __tablename__ = "kb_doc_parse_attempts"

    kb_doc_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="关联的知识库文档ID",
    )

    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        comment="租户ID",
    )

    kb_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        comment="知识库ID",
    )

    document_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        comment="物理文档ID",
    )

    attempt_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="当前文档的第几次解析尝试",
    )

    task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="对应的任务ID",
    )

    trigger_source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="system",
        comment="触发来源",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="processing",
        comment="本次尝试最终状态",
    )

    runtime_stage: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment="本次尝试的当前运行阶段快照",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="本次尝试的错误摘要",
    )

    parse_strategy: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="解析策略",
    )

    parser: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="配置或选择的解析器",
    )

    effective_parser: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="实际生效的解析器",
    )

    chunk_strategy: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="分块策略",
    )

    config_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="本次尝试的生效配置快照",
    )

    stats: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="本次尝试的统计信息",
    )

    logs_json: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="本次尝试的步骤日志时间线",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        comment="本次尝试开始时间",
    )

    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="本次尝试结束时间",
    )

    duration_ms: Mapped[Optional[int]] = mapped_column(
        BIGINT,
        nullable=True,
        comment="本次尝试耗时，单位毫秒",
    )

    def __repr__(self) -> str:
        return (
            f"<KBDocParseAttempt(id={self.id}, kb_doc_id={self.kb_doc_id}, "
            f"attempt_no={self.attempt_no}, status={self.status})>"
        )
