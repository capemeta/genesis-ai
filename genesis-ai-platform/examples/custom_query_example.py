"""
自定义查询完整示例
展示如何在 CRUD 工厂中实现复杂的连表查询
"""
from typing import List, Tuple, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import joinedload, selectinload

from core.base_service import BaseService
from core.crud_factory import crud_factory
from models.knowledge_base import KnowledgeBase
from models.document import Document
from models.user import User
from models.folder import Folder
from schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead


# ==================== 示例 1：基础连表查询 ====================

class KnowledgeBaseService(BaseService[KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate]):
    """
    知识库服务 - 基础连表查询
    
    需求：查询知识库列表时，同时加载：
    1. 创建者信息
    2. 文档数量
    3. 最后更新时间
    """
    
    async def list_resources(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at desc",
        user_id: Optional[UUID] = None,
        include_public: bool = True
    ) -> Tuple[List[KnowledgeBase], int]:
        """重写列表方法 - 添加连表查询"""
        
        # 基础条件
        conditions = [
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.deleted_at.is_(None)
        ]
        
        # 权限过滤
        if user_id and include_public:
            conditions.append(
                or_(
                    KnowledgeBase.owner_id == user_id,
                    KnowledgeBase.visibility == "tenant_public"
                )
            )
        
        # 自定义过滤
        if filters:
            if "name" in filters:
                conditions.append(KnowledgeBase.name.ilike(f"%{filters['name']}%"))
            if "status" in filters:
                conditions.append(KnowledgeBase.status == filters["status"])
        
        # 计算总数
        count_stmt = select(func.count()).select_from(KnowledgeBase).where(*conditions)
        total = await self.db.scalar(count_stmt) or 0
        
        # 主查询 - 使用 joinedload 关联加载
        stmt = (
            select(KnowledgeBase)
            .options(
                joinedload(KnowledgeBase.owner)  # 关联加载创建者
            )
            .where(*conditions)
        )
        
        # 排序
        parts = order_by.split()
        if len(parts) == 2 and hasattr(KnowledgeBase, parts[0]):
            field = getattr(KnowledgeBase, parts[0])
            stmt = stmt.order_by(field.desc() if parts[1] == "desc" else field.asc())
        
        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # 执行查询
        result = await self.db.execute(stmt)
        kbs = result.unique().scalars().all()
        
        # 为每个知识库添加文档统计（使用子查询）
        for kb in kbs:
            doc_count_stmt = select(func.count()).select_from(Document).where(
                Document.kb_id == kb.id,
                Document.deleted_at.is_(None)
            )
            kb.document_count = await self.db.scalar(doc_count_stmt) or 0
        
        return list(kbs), total


# ==================== 示例 2：复杂聚合查询 ====================

class KnowledgeBaseServiceWithStats(BaseService[KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate]):
    """
    知识库服务 - 聚合统计
    
    需求：查询知识库列表时，包含：
    1. 总文档数
    2. 已处理文档数
    3. 处理进度
    4. 总文件大小
    5. 最后更新时间
    """
    
    async def list_resources(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at desc",
        user_id: Optional[UUID] = None,
        include_public: bool = True
    ) -> Tuple[List[KnowledgeBase], int]:
        """重写列表方法 - 添加聚合统计"""
        
        # 基础条件
        conditions = [
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.deleted_at.is_(None)
        ]
        
        # 子查询：总文档数
        total_docs_subq = (
            select(func.count(Document.id))
            .where(
                Document.kb_id == KnowledgeBase.id,
                Document.deleted_at.is_(None)
            )
            .correlate(KnowledgeBase)
            .scalar_subquery()
        )
        
        # 子查询：已处理文档数
        processed_docs_subq = (
            select(func.count(Document.id))
            .where(
                Document.kb_id == KnowledgeBase.id,
                Document.status == "processed",
                Document.deleted_at.is_(None)
            )
            .correlate(KnowledgeBase)
            .scalar_subquery()
        )
        
        # 子查询：总文件大小
        total_size_subq = (
            select(func.coalesce(func.sum(Document.file_size), 0))
            .where(
                Document.kb_id == KnowledgeBase.id,
                Document.deleted_at.is_(None)
            )
            .correlate(KnowledgeBase)
            .scalar_subquery()
        )
        
        # 子查询：最后更新时间
        last_update_subq = (
            select(func.max(Document.updated_at))
            .where(
                Document.kb_id == KnowledgeBase.id,
                Document.deleted_at.is_(None)
            )
            .correlate(KnowledgeBase)
            .scalar_subquery()
        )
        
        # 主查询
        stmt = (
            select(
                KnowledgeBase,
                total_docs_subq.label("total_docs"),
                processed_docs_subq.label("processed_docs"),
                total_size_subq.label("total_size"),
                last_update_subq.label("last_update")
            )
            .where(*conditions)
        )
        
        # 支持按统计字段排序
        if order_by == "doc_count desc":
            stmt = stmt.order_by(total_docs_subq.desc())
        elif order_by == "total_size desc":
            stmt = stmt.order_by(total_size_subq.desc())
        else:
            parts = order_by.split()
            if len(parts) == 2 and hasattr(KnowledgeBase, parts[0]):
                field = getattr(KnowledgeBase, parts[0])
                stmt = stmt.order_by(field.desc() if parts[1] == "desc" else field.asc())
        
        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # 执行查询
        result = await self.db.execute(stmt)
        rows = result.all()
        
        # 构造结果
        kbs = []
        for kb, total_docs, processed_docs, total_size, last_update in rows:
            # 添加统计信息
            kb.total_documents = total_docs or 0
            kb.processed_documents = processed_docs or 0
            kb.processing_progress = (
                (processed_docs / total_docs * 100) if total_docs > 0 else 0
            )
            kb.total_file_size = total_size or 0
            kb.last_document_update = last_update
            kbs.append(kb)
        
        # 计算总数
        count_stmt = select(func.count()).select_from(KnowledgeBase).where(*conditions)
        total = await self.db.scalar(count_stmt) or 0
        
        return kbs, total


# ==================== 示例 3：多表连接查询 ====================

class DocumentService(BaseService[Document, DocumentCreate, DocumentUpdate]):
    """
    文档服务 - 多表连接
    
    需求：查询文档列表时，关联：
    1. 知识库信息
    2. 所有者信息
    3. 文件夹信息
    4. 标签列表
    """
    
    async def list_resources(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at desc",
        user_id: Optional[UUID] = None,
        include_public: bool = True
    ) -> Tuple[List[Document], int]:
        """重写列表方法 - 多表连接查询"""
        
        # 基础查询 - 连接多个表
        stmt = (
            select(Document)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .join(User, Document.owner_id == User.id)
            .outerjoin(Folder, Document.folder_id == Folder.id)
            .options(
                joinedload(Document.knowledge_base),
                joinedload(Document.owner),
                joinedload(Document.folder),
                selectinload(Document.tags)  # 一对多关系
            )
            .where(
                Document.tenant_id == tenant_id,
                Document.deleted_at.is_(None)
            )
        )
        
        # 复杂过滤条件
        if filters:
            # 按知识库名称过滤
            if "kb_name" in filters:
                stmt = stmt.where(KnowledgeBase.name.ilike(f"%{filters['kb_name']}%"))
            
            # 按所有者名称过滤
            if "owner_name" in filters:
                stmt = stmt.where(User.nickname.ilike(f"%{filters['owner_name']}%"))
            
            # 按文件夹路径过滤
            if "folder_path" in filters:
                stmt = stmt.where(Folder.path.like(f"{filters['folder_path']}%"))
            
            # 按文件类型过滤（多选）
            if "file_types" in filters and filters["file_types"]:
                stmt = stmt.where(Document.file_type.in_(filters["file_types"]))
            
            # 按状态过滤（多选）
            if "statuses" in filters and filters["statuses"]:
                stmt = stmt.where(Document.status.in_(filters["statuses"]))
            
            # 全文搜索
            if "search" in filters:
                search_term = f"%{filters['search']}%"
                stmt = stmt.where(
                    or_(
                        Document.title.ilike(search_term),
                        Document.content.ilike(search_term)
                    )
                )
            
            # 日期范围
            if "date_from" in filters:
                stmt = stmt.where(Document.created_at >= filters["date_from"])
            if "date_to" in filters:
                stmt = stmt.where(Document.created_at <= filters["date_to"])
        
        # 排序
        parts = order_by.split()
        if len(parts) == 2:
            if parts[0] == "kb_name":
                stmt = stmt.order_by(
                    KnowledgeBase.name.desc() if parts[1] == "desc" else KnowledgeBase.name.asc()
                )
            elif parts[0] == "owner_name":
                stmt = stmt.order_by(
                    User.nickname.desc() if parts[1] == "desc" else User.nickname.asc()
                )
            elif hasattr(Document, parts[0]):
                field = getattr(Document, parts[0])
                stmt = stmt.order_by(field.desc() if parts[1] == "desc" else field.asc())
        
        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # 执行查询
        result = await self.db.execute(stmt)
        documents = result.unique().scalars().all()
        
        # 计算总数（使用相同的过滤条件）
        count_stmt = (
            select(func.count())
            .select_from(Document)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .join(User, Document.owner_id == User.id)
            .outerjoin(Folder, Document.folder_id == Folder.id)
            .where(
                Document.tenant_id == tenant_id,
                Document.deleted_at.is_(None)
            )
        )
        
        # 应用相同的过滤条件
        if filters:
            if "kb_name" in filters:
                count_stmt = count_stmt.where(KnowledgeBase.name.ilike(f"%{filters['kb_name']}%"))
            if "owner_name" in filters:
                count_stmt = count_stmt.where(User.nickname.ilike(f"%{filters['owner_name']}%"))
            # ... 其他过滤条件
        
        total = await self.db.scalar(count_stmt) or 0
        
        return list(documents), total


# ==================== 注册到 CRUD 工厂 ====================

def register_custom_services():
    """注册使用自定义 Service 的 CRUD 路由"""
    
    # 示例 1：基础连表查询
    crud_factory.register(
        model=KnowledgeBase,
        prefix="/knowledge-bases",
        tags=["knowledge-bases"],
        service_class=KnowledgeBaseService,  # 使用自定义 Service
        list_permissions=["kb:read", "admin"],
        create_permissions=["kb:write", "admin"],
        update_permissions=["kb:write", "admin"],
        delete_permissions=["kb:delete", "admin"]
    )
    
    # 示例 2：带统计的知识库（使用不同的路由前缀）
    crud_factory.register(
        model=KnowledgeBase,
        prefix="/knowledge-bases-stats",
        tags=["knowledge-bases"],
        service_class=KnowledgeBaseServiceWithStats,  # 使用带统计的 Service
        list_permissions=["kb:read", "admin"]
    )
    
    # 示例 3：多表连接的文档查询
    crud_factory.register(
        model=Document,
        prefix="/documents",
        tags=["documents"],
        service_class=DocumentService,  # 使用自定义 Service
        list_permissions=["doc:read", "admin"],
        create_permissions=["doc:write", "admin"],
        update_permissions=["doc:write", "admin"],
        delete_permissions=["doc:delete", "admin"]
    )


# ==================== 使用示例 ====================

"""
前端调用示例：

// 基础查询
GET /api/v1/knowledge-bases?page=1&pageSize=20

// 带过滤条件
GET /api/v1/knowledge-bases?page=1&pageSize=20&name=测试&status=active

// 带统计信息
GET /api/v1/knowledge-bases-stats?page=1&pageSize=20

// 多表连接查询
GET /api/v1/documents?page=1&pageSize=20&kb_name=知识库&owner_name=张三&file_types=pdf,docx

响应格式（自动符合 Refine 规范）：
{
  "data": [
    {
      "id": "uuid",
      "name": "知识库名称",
      "owner": {
        "id": "uuid",
        "nickname": "张三"
      },
      "document_count": 10,
      "total_documents": 10,
      "processed_documents": 8,
      "processing_progress": 80.0,
      "total_file_size": 1024000,
      "last_document_update": "2026-01-11T10:00:00Z"
    }
  ],
  "total": 100
}
"""
