"""
异步任务模型

对应表：tasks
SQL 定义：docker/postgresql/init-schema.sql
"""
from typing import Optional, Any
from uuid import UUID as PyUUID
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from models.base import Base, AuditMixin


class Task(Base, AuditMixin):
    """
    异步任务模型 - 管理后台耗时任务（如文档解析、向量化）
    
    对应表：tasks
    SQL 定义：docker/postgresql/init-schema.sql
    
    继承 AuditMixin 自动获得审计字段：
    - created_by_id, updated_by_id
    - created_by_name, updated_by_name
    - created_at, updated_at
    """
    __tablename__ = "tasks"
    
    # 覆盖 Base 的自动 UUID 生成，因为任务 ID 通常由 Celery 或任务引擎外部生成
    id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        comment="任务ID (通常由 Celery 生成)"
    )
    
    # 租户隔离
    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 所有权
    owner_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="任务所有者ID"
    )
    
    # 业务字段
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="任务类型: document_parse, embedding_generate, kb_sync 等"
    )
    
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True,
        comment="任务状态: pending, running, success, failed, cancelled, retrying"
    )
    
    # 业务目标关联
    target_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="关联的目标资源ID（快捷索引）"
    )
    
    target_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="目标类型，如 'kb_document'"
    )
    
    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="任务进度 (0-100)"
    )
    
    # 时间统计
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始执行时间"
    )
    
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="结束/终结时间"
    )
    
    # 数据载荷
    payload: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="任务输入参数"
    )
    
    result: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="任务执行结果"
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="简短的异常/失败描述"
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, type={self.task_type}, status={self.status})>"
