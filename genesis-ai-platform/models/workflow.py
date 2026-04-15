"""
工作流定义模型
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Workflow(Base):
    """
    工作流定义

    当前阶段主要用于聊天空间入口选择与工作流运行记录关联。
    """

    __tablename__ = "workflows"
    __searchable_fields__ = ["name", "description"]

    tenant_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="所属租户ID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="工作流名称",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="工作流描述",
    )
    workflow_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="chat_flow",
        comment="工作流类型：chat_flow、task_flow、tool_flow",
    )
    definition: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="工作流定义JSON",
    )
    input_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="输入结构定义JSON",
    )
    output_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="输出结构定义JSON",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        comment="状态：draft、active、archived",
    )
    created_by_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
        comment="创建人ID",
    )
    updated_by_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
        comment="修改人ID",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_workflows_tenant_name"),
        CheckConstraint(
            "workflow_type IN ('chat_flow', 'task_flow', 'tool_flow')",
            name="ck_workflows_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_workflows_status",
        ),
    )
