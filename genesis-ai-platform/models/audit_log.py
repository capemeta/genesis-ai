"""
审计日志模型
统一的审计日志表，记录所有敏感操作
"""
from sqlalchemy import BigInteger, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from uuid import UUID as PyUUID
from typing import Optional, Dict, Any

from models.base import Base


class AuditLog(Base):
    """
    审计日志模型
    
    对应表：audit_logs
    SQL 定义：docker/postgresql/init-schema.sql
    
    用途：
    - 记录所有敏感操作（创建、删除、修改、共享等）
    - 权限变更审计（角色分配、权限授予等）
    - 安全审计和合规要求
    
    注意：
    - 使用 BIGSERIAL 主键（海量数据）
    - 不包含 owner_id、created_by_id 等审计字段（审计日志本身不需要审计）
    - detail 字段存储额外信息（operator_name, target_name, success, error_message 等）
    """
    __tablename__ = "audit_logs"
    
    # 主键（BIGSERIAL 自增长）
    id: Mapped[int] = mapped_column(  # type: ignore[assignment]
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="日志ID，BIGSERIAL自增长"
    )
    
    # 租户隔离
    tenant_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 操作人信息
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="操作用户ID，记录谁执行了操作"
    )
    
    # 操作信息
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="操作类型，如 create_kb, delete_doc, assign_role, revoke_permission"
    )
    
    # 目标资源信息
    target_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="目标类型，如 knowledge_base, document, user, role, permission"
    )
    
    target_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="目标资源ID，指向具体资源"
    )
    
    # 操作详情（JSONB 格式）
    detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="操作详情，JSON格式，存储额外信息"
    )
    
    # 网络信息
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="操作IP地址，用于安全分析"
    )
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
        comment="创建时间，记录操作时间"
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id})>"
    
    # ==================== 辅助方法 ====================
    
    @property
    def operator_name(self) -> Optional[str]:
        """从 detail 中获取操作人名称"""
        if self.detail:
            return self.detail.get("operator_name")
        return None
    
    @property
    def target_name(self) -> Optional[str]:
        """从 detail 中获取目标对象名称"""
        if self.detail:
            return self.detail.get("target_name")
        return None
    
    @property
    def success(self) -> bool:
        """从 detail 中获取操作是否成功"""
        if self.detail:
            return self.detail.get("success", True)
        return True
    
    @property
    def error_message(self) -> Optional[str]:
        """从 detail 中获取错误消息"""
        if self.detail:
            return self.detail.get("error_message")
        return None
    
    @property
    def user_agent(self) -> Optional[str]:
        """从 detail 中获取 User Agent"""
        if self.detail:
            return self.detail.get("user_agent")
        return None
