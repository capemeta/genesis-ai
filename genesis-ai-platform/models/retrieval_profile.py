"""
检索配置模板模型
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class RetrievalProfile(Base):
    """
    检索配置模板

    用于沉淀可复用的检索策略模板，供聊天空间与执行轮次引用。
    """

    __tablename__ = "retrieval_profiles"
    __searchable_fields__ = ["name", "description"]

    tenant_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="所属租户ID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="模板名称",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="模板描述",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        comment="状态：active-启用，archived-归档",
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="检索模板配置",
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
        UniqueConstraint("tenant_id", "name", name="uq_retrieval_profiles_tenant_name"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_retrieval_profiles_status"),
    )
