"""
角色-权限关联表
"""
from sqlalchemy import Table, Column, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from core.database.session import Base

# 角色-权限关联表（多对多）
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', UUID(as_uuid=True), nullable=False, comment="角色ID"),
    Column('permission_id', UUID(as_uuid=True), nullable=False, comment="权限ID"),
    Column('tenant_id', UUID(as_uuid=True), nullable=False, comment="所属租户ID"),
    Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间"),
    comment="角色-权限关联表 - 定义角色拥有哪些权限，RBAC核心关联"
)
