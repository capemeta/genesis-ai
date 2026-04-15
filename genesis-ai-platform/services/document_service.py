"""
文档相关服务
包含物理资产管理 (DocumentService) 与 RAG 挂载管理 (KBDocumentService)
"""
import json
from typing import Optional, List, Any, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import joinedload

from core.base_service import BaseService
from models.document import Document
from models.knowledge_base_document import KnowledgeBaseDocument
from models.user import User
from schemas.document import (
    DocumentRead, KBDocumentCreate, KBDocumentUpdate, KBDocumentListRequest
)


# 这些元数据由系统任务维护，用户侧不允许通过文件列表直接覆盖。
RESERVED_CUSTOM_METADATA_KEYS = {
    "content_kind",
    "table_rows_ready",
    "table_row_count",
    "table_rows_updated_at",
    "qa_rows_ready",
    "qa_row_count",
    "qa_rows_updated_at",
    "source_mode",
    "source_file_type",
    "qa_template_version",
    "virtual_file",
    "has_manual_edits",
    "edited_waiting_reparse",
    "pending_reparse_row_count",
    "last_rebuild_from_rows_at",
}


def _normalize_editable_metadata_value(value: Any) -> Optional[str]:
    """将用户可编辑元数据统一收敛为字符串，避免复杂对象污染结构。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _sanitize_user_metadata(metadata: Dict[str, Any]) -> Dict[str, str]:
    """过滤系统保留键，只保留允许用户编辑的元数据。"""
    sanitized: Dict[str, str] = {}
    if not isinstance(metadata, dict):
        return sanitized

    for raw_key, raw_value in metadata.items():
        key = str(raw_key or "").strip()
        if not key or key in RESERVED_CUSTOM_METADATA_KEYS:
            continue

        normalized_value = _normalize_editable_metadata_value(raw_value)
        if normalized_value in (None, ""):
            continue
        sanitized[key] = normalized_value

    return sanitized


class DocumentService(BaseService[Document, Any, Any]):
    """物理文档服务"""
    pass


class KBDocumentService(BaseService[KnowledgeBaseDocument, KBDocumentCreate, KBDocumentUpdate]):
    """知识库文档挂载服务 (File Browser 核心逻辑)"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(KnowledgeBaseDocument, db)
    
    async def list(
        self,
        request_data: KBDocumentListRequest,
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        列表查询 - 支持按知识库、文件夹过滤，并关联物理文档详情
        """
        use_session = session or self.db
        
        # 1. 基础查询：关联物理文档表
        stmt = select(KnowledgeBaseDocument).options(
            joinedload(KnowledgeBaseDocument.document) # 假设配置了 relationship
        ).where(
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
            KnowledgeBaseDocument.kb_id == request_data.kb_id
        )
        
        # 2. 文件夹过滤
        if request_data.folder_id:
            if request_data.include_subfolders:
                # 递归逻辑：通常需要 join folders 获取路径，或者通过 folder_id 关联查询
                # 这里简单处理：仅支持文件夹内
                stmt = stmt.where(KnowledgeBaseDocument.folder_id == request_data.folder_id)
            else:
                stmt = stmt.where(KnowledgeBaseDocument.folder_id == request_data.folder_id)
        elif not request_data.search:
            # 如果没搜索也没选文件夹，默认显示根目录
            stmt = stmt.where(KnowledgeBaseDocument.folder_id == None)

        # 3. 状态过滤
        if request_data.parse_status:
            stmt = stmt.where(KnowledgeBaseDocument.parse_status == request_data.parse_status)

        # 4. 搜索搜索（由于需要搜索物理文件名，必须 Join）
        from sqlalchemy.orm import aliased
        doc_alias = aliased(Document)
        
        # 重新构建带 Join 的查询以便搜索
        stmt = select(KnowledgeBaseDocument).join(
            Document, KnowledgeBaseDocument.document_id == Document.id
        ).where(
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
            KnowledgeBaseDocument.kb_id == request_data.kb_id
        )
        
        if request_data.search:
            search_query = f"%{request_data.search}%"
            stmt = stmt.where(Document.name.ilike(search_query))

        # 5. 分页与计数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await use_session.scalar(count_stmt)
        
        # 分页
        stmt = stmt.offset((request_data.page - 1) * request_data.page_size).limit(request_data.page_size)
        
        # 执行查询
        result = await use_session.execute(stmt)
        items = result.scalars().all()
        
        # 6. 后处理：手动加载文档信息（如果 joinedload 不奏效）
        # CRUD Factory 期望返回的是模型列表或符合 Read Schema 的对象
        return {
            "items": items,
            "total": total,
            "page": request_data.page,
            "page_size": request_data.page_size
        }

    async def update_tags(
        self,
        kb_doc_id: UUID,
        tag_ids: List[UUID],
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        更新文档标签（只更新标签）
        
        Args:
            kb_doc_id: 知识库文档ID
            tag_ids: 标签ID列表
            current_user: 当前用户
            session: 数据库会话
        
        Returns:
            更新结果
        """
        from services.kb_doc_tag_service import KbDocTagService
        
        use_session = session or self.db

        # 1. 查询知识库文档记录
        stmt = select(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.id == kb_doc_id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id
        )
        result = await use_session.execute(stmt)
        kb_doc = result.scalar_one_or_none()
        
        if not kb_doc:
            return None

        # 2. 权限检查
        if kb_doc.owner_id != current_user.id:
            raise PermissionError("无权修改此文档")
        
        # 3. 处理标签更新
        tags = await KbDocTagService.set_kb_doc_tags(
            session=use_session,
            kb_doc_id=kb_doc_id,
            tag_ids=tag_ids,
            tenant_id=current_user.tenant_id,
            kb_id=kb_doc.kb_id,
        )

        return {
            "kb_document_id": str(kb_doc_id),
            "tags": tags
        }

    async def update_metadata(
        self,
        kb_doc_id: UUID,
        metadata: Dict[str, Any],
        current_user: User,
        session: Optional[AsyncSession] = None,
        merge_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        更新文档元数据（只更新元数据）
        
        Args:
            kb_doc_id: 知识库文档ID
            metadata: 元数据字典
            current_user: 当前用户
            session: 数据库会话
            merge_metadata: 是否合并元数据（False=全量覆盖，True=合并模式）
        
        Returns:
            更新结果
        """
        from datetime import datetime
        from sqlalchemy import update
        
        use_session = session or self.db

        # 1. 查询知识库文档记录
        stmt = select(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.id == kb_doc_id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id
        )
        result = await use_session.execute(stmt)
        kb_doc = result.scalar_one_or_none()
        
        if not kb_doc:
            return None

        # 2. 权限检查
        if kb_doc.owner_id != current_user.id:
            raise PermissionError("无权修改此文档")
        
        editable_metadata = _sanitize_user_metadata(metadata)

        # 3. 处理元数据更新
        if merge_metadata:
            # 批量操作：合并模式（保留现有元数据，添加新的）
            existing = kb_doc.custom_metadata or {}
            if not isinstance(existing, dict):
                existing = {}
            
            new_metadata = existing.copy()
            for k, v in editable_metadata.items():
                new_metadata[k] = v
        else:
            # 单个文档编辑：全量覆盖模式
            existing = kb_doc.custom_metadata or {}
            if not isinstance(existing, dict):
                existing = {}

            # 保留系统保留键，只覆盖用户自定义项。
            new_metadata = {
                key: value
                for key, value in existing.items()
                if key in RESERVED_CUSTOM_METADATA_KEYS
            }
            new_metadata.update(editable_metadata)

        stmt = (
            update(KnowledgeBaseDocument)
            .where(KnowledgeBaseDocument.id == kb_doc_id)
            .values(
                custom_metadata=new_metadata,
                updated_by_id=current_user.id,
                updated_by_name=current_user.nickname,
                updated_at=datetime.utcnow()
            )
        )
        await use_session.execute(stmt)

        return {
            "kb_document_id": str(kb_doc_id),
            "metadata": new_metadata
        }

    async def update_tags_and_metadata(
        self,
        kb_doc_id: UUID,
        metadata: Dict[str, Any],
        tag_ids: List[UUID],
        intelligence_config: Optional[Dict[str, Any]],
        current_user: User,
        session: Optional[AsyncSession] = None,
        merge_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        更新文档标签和元数据（同时更新两者）
        
        Args:
            kb_doc_id: 知识库文档ID
            metadata: 元数据字典
            tag_ids: 标签ID列表
            current_user: 当前用户
            session: 数据库会话
            merge_metadata: 是否合并元数据（False=全量覆盖，True=合并模式）
        
        Returns:
            更新结果
        """
        from datetime import datetime
        from services.kb_doc_tag_service import KbDocTagService
        from sqlalchemy import update
        
        use_session = session or self.db

        # 1. 查询知识库文档记录
        stmt = select(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.id == kb_doc_id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id
        )
        result = await use_session.execute(stmt)
        kb_doc = result.scalar_one_or_none()
        
        if not kb_doc:
            return None

        # 2. 权限检查
        if kb_doc.owner_id != current_user.id:
            raise PermissionError("无权修改此文档")
        
        response_data = {
            "kb_document_id": str(kb_doc_id)
        }

        editable_metadata = _sanitize_user_metadata(metadata)

        # 3. 处理元数据更新
        if merge_metadata:
            # 批量操作：合并模式（保留现有元数据，添加新的）
            existing = kb_doc.custom_metadata or {}
            if not isinstance(existing, dict):
                existing = {}
            
            new_metadata = existing.copy()
            for k, v in editable_metadata.items():
                new_metadata[k] = v
        else:
            # 单个文档编辑：全量覆盖模式
            existing = kb_doc.custom_metadata or {}
            if not isinstance(existing, dict):
                existing = {}

            # 保留系统保留键，只覆盖用户自定义项。
            new_metadata = {
                key: value
                for key, value in existing.items()
                if key in RESERVED_CUSTOM_METADATA_KEYS
            }
            new_metadata.update(editable_metadata)

        # 统一构建文档级智能配置，当前用于承载“文档补充说明”等回答增强项。
        next_intelligence_config = kb_doc.intelligence_config or {}
        if not isinstance(next_intelligence_config, dict):
            next_intelligence_config = {}
        if intelligence_config is not None:
            next_intelligence_config = intelligence_config

        stmt = (
            update(KnowledgeBaseDocument)
            .where(KnowledgeBaseDocument.id == kb_doc_id)
            .values(
                custom_metadata=new_metadata,
                intelligence_config=next_intelligence_config,
                updated_by_id=current_user.id,
                updated_by_name=current_user.nickname,
                updated_at=datetime.utcnow()
            )
        )
        await use_session.execute(stmt)
        response_data["metadata"] = new_metadata
        response_data["intelligence_config"] = next_intelligence_config

        # 4. 处理标签更新
        tags = await KbDocTagService.set_kb_doc_tags(
            session=use_session,
            kb_doc_id=kb_doc_id,
            tag_ids=tag_ids,
            tenant_id=current_user.tenant_id,
            kb_id=kb_doc.kb_id,
        )
        response_data["tags"] = tags

        return response_data
