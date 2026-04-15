"""
文件夹模型

对应表：folders
SQL 定义：docker/postgresql/init-schema.sql
"""
from sqlalchemy import String, Text, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.types import UserDefinedType
from uuid import UUID as PyUUID
from typing import Optional

from models.base import Base, AuditMixin


class LTREE(UserDefinedType):
    """PostgreSQL ltree 类型"""
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


class Folder(Base, AuditMixin):
    """
    文件夹模型 - 支持无限层级的树形结构
    
    使用 ltree 实现高性能树形查询
    
    继承 AuditMixin 自动获得审计字段：
    - created_by_id, updated_by_id
    - created_by_name, updated_by_name
    - created_at, updated_at
    """
    __tablename__ = "folders"
    
    # 配置可搜索字段（用于 search 参数的模糊搜索）
    __searchable_fields__ = ["name", "summary"]
    
    # 租户隔离
    tenant_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属租户ID"
    )
    
    # 所有者
    owner_id: Mapped[PyUUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        comment="文件夹所有者ID"
    )
    
    # 知识库关联
    kb_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="所属知识库ID，NULL表示根文件夹"
    )
    
    # 父文件夹
    parent_id: Mapped[Optional[PyUUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="父文件夹ID，NULL表示根文件夹"
    )
    
    # 业务字段
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="文件夹名称"
    )
    
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="文件夹摘要，用于语义路由"
    )
    
    # ltree 路径
    path: Mapped[str] = mapped_column(
        LTREE,
        nullable=False,
        comment='ltree路径，格式如"kb_{kb_id_hex}.f_{f1_id_hex}.f_{f2_id_hex}"'
    )
    
    # 层级深度
    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="层级深度，根文件夹为1"
    )
    
    full_name_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="文件夹层级名称路径，冗余存储以实现高性能的面包屑和路径显示"
    )
    
    # 表级约束和索引
    __table_args__ = (
        Index(
            'idx_folders_kb_path',
            'kb_id',
            'path',
            postgresql_using='gist'
        ),
    )
    
    @property
    def path_ids(self) -> list[PyUUID]:
        """
        解析 ltree 路径，返回分段 ID 列表（已剥离前缀并转回 UUID）
        """
        if not self.path:
            return []
        
        segments = self.path.split('.')
        ids = []
        for seg in segments:
            # 剥离前缀 (kb_ 或 f_) 并转回 UUID
            if seg.startswith(('kb_', 'f_')):
                try:
                    ids.append(PyUUID(seg[3:]))
                except ValueError:
                    continue
            elif seg == 'root':
                continue
            else:
                # 兼容不带前缀的情况
                try:
                    ids.append(PyUUID(seg))
                except ValueError:
                    continue
        return ids

    def __repr__(self) -> str:
        return f"<Folder(id={self.id}, name={self.name}, path={self.path})>"
