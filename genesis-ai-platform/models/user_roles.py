"""
用户-角色关联表
"""
from sqlalchemy import Table, Column, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from core.database.session import Base

# 用户-角色关联表（多对多）
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), nullable=False, comment="用户ID"),
    Column('role_id', UUID(as_uuid=True), nullable=False, comment="角色ID"),
    Column('tenant_id', UUID(as_uuid=True), nullable=False, comment="所属租户ID"),
    Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间"),
    comment="用户-角色关联表 - 定义用户拥有哪些角色，支持一个用户多个角色"
)
