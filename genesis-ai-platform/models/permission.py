"""
权限模型
统一管理菜单权限和功能权限
"""
from sqlalchemy import String, Text, Integer, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID as PyUUID
from typing import Optional

from models.base import Base, AuditMixin, TenantMixin


class Permission(Base, AuditMixin, TenantMixin):
    """
    权限模型 - 统一管理菜单权限和功能权限
    
    type='menu': 菜单权限，控制前端路由和菜单显示
    type='function': 功能权限，控制后端 API 接口访问
    type='directory': 目录，仅用于菜单分组，不可跳转（path 为 NULL）
    
    对应表：permissions
    SQL 定义：docker/postgresql/init-schema.sql
    
    注意：当前数据库表结构需要扩展以支持菜单权限字段
    """
    __tablename__ = "permissions"
    __searchable_fields__ = ["code", "name", "module"]
    
    # 基础字段
    code: Mapped[str] = mapped_column(
        String(100), 
        nullable=False, 
        unique=True,
        comment="权限代码，全局唯一"
    )
    
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="权限名称"
    )
    
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="function",
        comment="权限类型：menu-菜单权限，function-功能权限，directory-目录（仅用于菜单分组）"
    )
    
    module: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="所属模块"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="权限描述"
    )
    
    # 状态字段
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="状态：0-正常，1-停用"
    )
    
    # 菜单权限专用字段
    parent_id: Mapped[Optional[PyUUID]] = mapped_column(
        nullable=True,
        comment="父菜单ID"
    )
    
    path: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="前端路由路径"
    )
    
    icon: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="菜单图标"
    )
    
    component: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="前端组件路径"
    )
    
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序顺序"
    )
    
    is_hidden: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否隐藏"
    )
    
    # 功能权限专用字段
    api_path: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="API 路径"
    )
    
    http_method: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="HTTP 方法"
    )
    
    # 表级约束
    __table_args__ = (
        CheckConstraint(
            "type IN ('menu', 'function', 'directory')",
            name="ck_permissions_type"
        ),
        CheckConstraint(
            "status IN (0, 1)",
            name="ck_permissions_status"
        ),
    )
    
    def __repr__(self) -> str:
        return f"<Permission(code={self.code}, name={self.name}, type={self.type})>"
