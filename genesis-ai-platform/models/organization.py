"""
组织架构模型
"""
from sqlalchemy import String, Text, Integer, UUID, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import UserDefinedType
from datetime import datetime
from uuid import UUID as PyUUID, uuid4
from typing import Optional

from models.base import Base


class LTREE(UserDefinedType):
    """
    PostgreSQL ltree 类型
    """
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


class Organization(Base):
    """
    组织架构模型
    
    对应表：organizations
    SQL 定义：docker/postgresql/init-schema.sql
    
    使用 ltree 实现树形结构，支持高效的祖先/后代查询
    """
    __tablename__ = "organizations"
    
    # 主键
    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="组织ID"
    )
    
    # 租户隔离
    tenant_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 所有权
    owner_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="部门主管/负责人ID"
    )
    
    # 树形结构
    parent_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="父部门ID，NULL表示租户根部门"
    )
    
    # 业务字段
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="部门名称"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="部门描述"
    )
    
    # ltree 路径
    path: Mapped[str] = mapped_column(
        LTREE,
        nullable=False,
        comment="层级路径，如 't1.rd.frontend'"
    )
    
    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="层级深度，根部门为1"
    )
    
    # 配额限制
    limits: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="部门级限额覆盖"
    )
    
    # 排序和状态字段
    order_num: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="排序号，数字越小越靠前"
    )
    
    status: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        default='0',
        comment="状态：0-正常，1-停用"
    )
    
    del_flag: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        default='0',
        comment="删除标志：0-正常，1-删除"
    )
    
    # 联系信息字段（非必填）
    leader_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="负责人姓名"
    )
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="联系电话"
    )
    
    email: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="邮箱"
    )
    
    # 审计字段
    created_by_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="创建人ID"
    )
    
    created_by_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="创建人名称（冗余字段）"
    )
    
    updated_by_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="最后修改人ID"
    )
    
    updated_by_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="最后修改人名称（冗余字段）"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="创建时间"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="最后更新时间"
    )
    
    # 表级约束和索引
    __table_args__ = (
        # GIST 索引用于 ltree 查询（已在 SQL 中定义）
        Index('idx_org_tenant_path', 'tenant_id', 'path', postgresql_using='gist'),
    )
    
    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, path={self.path})>"
