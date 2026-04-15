"""
表格知识库数据集服务

负责：
- 表格行数据查询
- 表格行编辑
- 编辑后置为待重解析
- 基于 kb_table_rows 重新生成 chunks
"""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID as PyUUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import String, bindparam, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.chunk import Chunk
from models.document import Document
from models.kb_table_row import KBTableRow
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.user import User
from rag.ingestion.chunkers.excel_table_chunker import ExcelTableChunker
from rag.search_units import build_search_units_for_chunks, delete_search_projections_for_chunk_ids
from rag.utils.model_utils import model_config_manager
from rag.utils.token_utils import count_tokens


class TableDatasetService:
    """表格知识库数据集服务。"""

    # 允许人工维护表格行的解析状态。
    _EDITABLE_PARSE_STATUSES = {"completed", "failed", "cancelled"}
    # 解析任务仍在推进中的状态，必须禁止人工维护，避免和解析流程互相覆盖。
    _LOCKED_PARSE_STATUSES = {"queued", "processing", "cancelling"}

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dataset_detail(
        self,
        kb_doc_id: PyUUID,
        current_user: User,
    ) -> Dict[str, Any]:
        """获取表格数据集详情。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        self._ensure_table_dataset(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)

        total_rows = await self.session.scalar(
            select(func.count()).select_from(KBTableRow).where(
                KBTableRow.kb_doc_id == kb_doc.id,
                KBTableRow.is_deleted.is_(False),
            )
        ) or 0

        metadata = dict(kb_doc.custom_metadata or {})
        pending_rows = int(metadata.get("pending_reparse_row_count") or 0)
        metadata["has_pending_reparse"] = bool(
            metadata.get("edited_waiting_reparse")
            or pending_rows > 0
            or kb_doc.runtime_stage == "edited_waiting_reparse"
        )

        return {
            "kb_doc_id": str(kb_doc.id),
            "kb_id": str(kb_doc.kb_id),
            "document_id": str(kb_doc.document_id),
            "name": document.name,
            "display_name": kb_doc.display_name or document.name,
            "file_type": document.file_type,
            "carrier_type": document.carrier_type,
            "asset_kind": document.asset_kind,
            "source_type": document.source_type,
            "parse_status": kb_doc.parse_status,
            "runtime_stage": kb_doc.runtime_stage,
            "parse_error": kb_doc.parse_error,
            "chunk_count": int(kb_doc.chunk_count or 0),
            "row_count": int(total_rows),
            "pending_reparse_row_count": int(pending_rows),
            "folder_id": str(kb_doc.folder_id) if kb_doc.folder_id else None,
            "metadata": metadata,
            "created_at": kb_doc.created_at.isoformat() if kb_doc.created_at else None,
            "updated_at": kb_doc.updated_at.isoformat() if kb_doc.updated_at else None,
        }

    async def list_rows(
        self,
        kb_doc_id: PyUUID,
        current_user: User,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        column_filters: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[KBTableRow], int]:
        """列出表格行，并返回分页总数。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        self._ensure_table_dataset(kb_doc)
        kb = await self._get_kb(kb_doc.kb_id, current_user.tenant_id)

        base_stmt = select(KBTableRow).where(KBTableRow.kb_doc_id == kb_doc.id)
        if not include_deleted:
            base_stmt = base_stmt.where(KBTableRow.is_deleted.is_(False))

        normalized_search = str(search or "").strip()
        if normalized_search:
            like_value = f"%{normalized_search}%"
            searchable_columns = self._get_searchable_columns(kb)
            if searchable_columns:
                base_stmt = base_stmt.where(
                    or_(
                        *[
                            KBTableRow.row_data[str(column_name)].astext.ilike(like_value)
                            for column_name in searchable_columns
                        ]
                    )
                )
            else:
                # 未配置可检索字段时，回退到整行 JSON 模糊搜索，避免界面出现“搜不到任何记录”。
                base_stmt = base_stmt.where(
                    func.cast(KBTableRow.row_data, String).ilike(like_value)
                )

        for column_name, raw_value in (column_filters or {}).items():
            normalized_value = str(raw_value or "").strip()
            if not normalized_value:
                continue
            like_value = f"%{normalized_value}%"
            base_stmt = base_stmt.where(
                KBTableRow.row_data[str(column_name)].astext.ilike(like_value)
            )

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int(await self.session.scalar(total_stmt) or 0)

        stmt = (
            base_stmt
            .order_by(KBTableRow.sheet_name.asc(), KBTableRow.row_index.asc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def update_row(
        self,
        row_id: PyUUID,
        row_data: Dict[str, Any],
        current_user: User,
    ) -> Dict[str, Any]:
        """更新单条表格行，并将当前数据集置为待重解析。"""
        table_row = await self._get_row_for_user(row_id, current_user)
        kb_doc = await self._get_kb_doc_for_user(table_row.kb_doc_id, current_user)
        self._ensure_table_dataset(kb_doc)
        self._ensure_dataset_mutable(kb_doc, action_label="修改记录")

        normalized_row_data = self._normalize_row_data(row_data, table_row, kb_doc)
        table_row.row_data = normalized_row_data
        table_row.row_hash = self._compute_row_hash(normalized_row_data)
        table_row.row_version = int(table_row.row_version or 1) + 1
        table_row.source_type = "manual"
        table_row.updated_by_id = current_user.id
        table_row.updated_by_name = current_user.nickname
        table_row.updated_at = datetime.now(timezone.utc)

        source_meta = dict(table_row.source_meta or {})
        source_meta["has_manual_edits"] = True
        source_meta["last_manual_edit_at"] = datetime.now(timezone.utc).isoformat()
        table_row.source_meta = source_meta

        await self.session.flush()
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=1)
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)
        return {
            "row_id": str(table_row.id),
            "row_version": table_row.row_version,
            "dataset": await self.get_dataset_detail(kb_doc.id, current_user),
            "document_name": document.name,
        }

    async def create_row(
        self,
        kb_doc_id: PyUUID,
        row_data: Dict[str, Any],
        current_user: User,
        sheet_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """新增单条表格行，并将当前数据集置为待重解析。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        self._ensure_table_dataset(kb_doc)
        self._ensure_dataset_mutable(kb_doc, action_label="新增记录")

        active_rows, _ = await self.list_rows(
            kb_doc.id,
            current_user,
            include_deleted=False,
            page=1,
            page_size=100000,
        )
        target_sheet_name = self._resolve_target_sheet_name(active_rows, sheet_name)
        header = self._resolve_header_for_new_row(active_rows, row_data, target_sheet_name, kb_doc)
        normalized_row_data = self._normalize_new_row_data(row_data, header)
        next_row_index = self._next_row_index(active_rows, target_sheet_name)

        source_meta = self._build_new_row_source_meta(
            active_rows=active_rows,
            header=header,
            sheet_name=target_sheet_name,
            kb_doc=kb_doc,
        )
        source_meta["has_manual_edits"] = True
        source_meta["created_from"] = "manual"
        source_meta["last_manual_edit_at"] = datetime.now(timezone.utc).isoformat()

        new_row = KBTableRow(
            tenant_id=current_user.tenant_id,
            kb_id=kb_doc.kb_id,
            kb_doc_id=kb_doc.id,
            document_id=kb_doc.document_id,
            row_uid=f"{kb_doc.id}:{target_sheet_name}:{next_row_index}:{uuid4()}",
            sheet_name=target_sheet_name,
            row_index=next_row_index,
            source_row_number=None,
            source_type="manual",
            row_version=1,
            is_deleted=False,
            row_hash=self._compute_row_hash(normalized_row_data),
            row_data=normalized_row_data,
            source_meta=source_meta,
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(new_row)
        await self.session.flush()

        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=1)
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)
        return {
            "row_id": str(new_row.id),
            "row_version": new_row.row_version,
            "dataset": await self.get_dataset_detail(kb_doc.id, current_user),
            "document_name": document.name,
        }

    async def delete_row(
        self,
        row_id: PyUUID,
        current_user: User,
    ) -> Dict[str, Any]:
        """软删除单条表格行，并将当前数据集置为待重解析。"""
        table_row = await self._get_row_for_user(row_id, current_user)
        kb_doc = await self._get_kb_doc_for_user(table_row.kb_doc_id, current_user)
        self._ensure_table_dataset(kb_doc)
        self._ensure_dataset_mutable(kb_doc, action_label="删除记录")

        if table_row.is_deleted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前表格行已删除")

        table_row.is_deleted = True
        table_row.source_type = "manual"
        table_row.row_version = int(table_row.row_version or 1) + 1
        table_row.updated_by_id = current_user.id
        table_row.updated_by_name = current_user.nickname
        table_row.updated_at = datetime.now(timezone.utc)

        source_meta = dict(table_row.source_meta or {})
        source_meta["has_manual_edits"] = True
        source_meta["deleted_from_dataset"] = True
        source_meta["last_manual_edit_at"] = datetime.now(timezone.utc).isoformat()
        table_row.source_meta = source_meta

        await self.session.flush()
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=1)
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)
        return {
            "row_id": str(table_row.id),
            "row_version": table_row.row_version,
            "dataset": await self.get_dataset_detail(kb_doc.id, current_user),
            "document_name": document.name,
        }

    async def rebuild_dataset(
        self,
        kb_doc_id: PyUUID,
        current_user: User,
    ) -> Dict[str, Any]:
        """基于 kb_table_rows 重建当前表格数据集的 chunks。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        self._ensure_table_dataset(kb_doc)
        self._ensure_dataset_mutable(kb_doc, action_label="重新解析数据集")

        rows, _ = await self.list_rows(
            kb_doc.id,
            current_user,
            include_deleted=False,
            page=1,
            page_size=100000,
        )
        if not rows:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前数据集没有可重建的表格行")

        kb = await self._get_kb(kb_doc.kb_id, current_user.tenant_id)
        await self._delete_kb_doc_chunks(kb_doc.id)

        metadata = self._build_chunker_metadata(rows, kb_doc)
        chunker = self._build_chunker(kb, kb_doc)
        final_chunks = chunker.chunk("", metadata)
        new_chunk_ids = await self._persist_chunks(kb_doc, final_chunks)

        kb_doc.parse_status = "completed"
        kb_doc.parse_error = None
        kb_doc.parse_progress = 100
        kb_doc.chunk_count = len(new_chunk_ids)
        kb_doc.runtime_stage = "completed"
        kb_doc.runtime_updated_at = datetime.now(timezone.utc)
        kb_doc.parse_ended_at = datetime.now(timezone.utc)
        kb_doc.updated_at = datetime.now(timezone.utc)

        custom_metadata = dict(kb_doc.custom_metadata or {})
        custom_metadata["has_manual_edits"] = True
        custom_metadata["edited_waiting_reparse"] = False
        custom_metadata["pending_reparse_row_count"] = 0
        custom_metadata["last_rebuild_from_rows_at"] = datetime.now(timezone.utc).isoformat()
        kb_doc.custom_metadata = custom_metadata

        await self.session.commit()
        self._trigger_train(kb_doc.id, new_chunk_ids)
        return await self.get_dataset_detail(kb_doc.id, current_user)

    def _build_chunker_metadata(
        self,
        rows: List[KBTableRow],
        kb_doc: KnowledgeBaseDocument,
    ) -> Dict[str, Any]:
        """将 kb_table_rows 适配为 ExcelTableChunker 需要的标准输入。"""
        table_rows: List[Dict[str, Any]] = []
        sheet_headers = self._get_sheet_headers(kb_doc)
        sheet_row_count: Dict[str, int] = defaultdict(int)
        sheet_header_row_numbers = self._get_sheet_header_row_numbers(kb_doc)

        for row in rows:
            source_meta = dict(row.source_meta or {})
            header = list(sheet_headers.get(row.sheet_name) or list((row.row_data or {}).keys()))
            row_data = dict(row.row_data or {})
            values = [self._stringify_cell_value(row_data.get(col)) for col in header]

            table_rows.append(
                {
                    "table_row_id": str(row.id),
                    "row_uid": row.row_uid,
                    "sheet_name": row.sheet_name,
                    "row_index": int(row.row_index),
                    "header": header,
                    "values": values,
                }
            )

            if row.sheet_name not in sheet_headers:
                sheet_headers[row.sheet_name] = header
            sheet_row_count[row.sheet_name] += 1

        sheets = [
            {
                "sheet_name": sheet_name,
                "header": sheet_headers.get(sheet_name, []),
                "header_row_number": sheet_header_row_numbers.get(sheet_name),
                "row_count": int(sheet_row_count.get(sheet_name, 0)),
            }
            for sheet_name in sorted(sheet_headers.keys())
        ]
        return {
            "parse_method": "excel_table_from_rows",
            "parser": "kb_table_rows",
            "table_rows": table_rows,
            "sheets": sheets,
        }

    def _ensure_dataset_mutable(
        self,
        kb_doc: KnowledgeBaseDocument,
        action_label: str,
    ) -> None:
        """校验当前数据集是否允许人工维护。"""
        parse_status = str(kb_doc.parse_status or "").strip().lower()
        runtime_stage = str(kb_doc.runtime_stage or "").strip().lower()

        # 手工编辑后进入待重解析时，允许继续维护并最终手动重建。
        if runtime_stage == "edited_waiting_reparse":
            return

        if parse_status in self._EDITABLE_PARSE_STATUSES:
            return

        if parse_status in self._LOCKED_PARSE_STATUSES:
            status_label = {
                "queued": "排队中",
                "processing": "解析中",
                "cancelling": "取消中",
            }.get(parse_status, parse_status or "未知状态")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"当前文档{status_label}，暂不允许{action_label}，请等待解析任务结束后再操作",
            )

        if parse_status == "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"当前文档尚未完成首轮解析，暂不允许{action_label}，请先完成解析后再操作",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"当前文档状态不支持{action_label}，请刷新后重试",
        )

    def _build_chunker(
        self,
        kb: KnowledgeBase,
        kb_doc: KnowledgeBaseDocument,
    ) -> ExcelTableChunker:
        """根据知识库配置构造表格分块器。"""
        chunking_config = dict(kb.chunking_config or {})
        chunking_config.update(dict(kb_doc.chunking_config or {}))
        retrieval_config = dict(kb.retrieval_config or {})
        table_retrieval = dict(retrieval_config.get("table") or {})
        table_schema = dict(table_retrieval.get("schema") or {})
        columns = list(table_schema.get("columns") or [])

        filter_columns = [
            str(col.get("name"))
            for col in columns
            if col.get("name") and bool(col.get("filterable"))
        ]
        key_columns = list(table_retrieval.get("key_columns") or [])
        model_name = str(kb.embedding_model or "BAAI/bge-large-zh-v1.5")
        safe_limit = int(model_config_manager.get_safe_token_limit(model_name, default=512))
        requested_max_embed_tokens = int(chunking_config.get("max_embed_tokens") or safe_limit)
        # 表格重建链路也要与首次解析保持一致，统一按模型安全上限收口。
        max_embed_tokens = max(1, min(requested_max_embed_tokens, safe_limit))

        return ExcelTableChunker(
            chunk_size=int(chunking_config.get("chunk_size") or 512),
            chunk_overlap=int(chunking_config.get("overlap") or 0),
            filter_columns=filter_columns,
            key_columns=key_columns,
            max_embed_tokens=max_embed_tokens,
            token_count_method="tokenizer",
            enable_summary_chunk=True,
        )

    @staticmethod
    def _get_searchable_columns(kb: KnowledgeBase) -> List[str]:
        """返回结构定义中声明为 searchable 的字段名列表。"""
        retrieval_config = dict(kb.retrieval_config or {})
        table_retrieval = dict(retrieval_config.get("table") or {})
        table_schema = dict(table_retrieval.get("schema") or {})
        columns = list(table_schema.get("columns") or [])
        return [
            str(column.get("name"))
            for column in columns
            if column.get("name") and bool(column.get("searchable"))
        ]

    async def _persist_chunks(
        self,
        kb_doc: KnowledgeBaseDocument,
        final_chunks: List[Dict[str, Any]],
    ) -> List[int]:
        """将表格分块结果写入 chunks。"""
        new_chunks: List[Chunk] = []
        for idx, fc in enumerate(final_chunks):
            content = str(fc.get("text") or "").strip()
            metadata_info = dict(fc.get("metadata") or {})
            table_row_id = metadata_info.get("table_row_id")
            content_group_id: Optional[PyUUID] = None
            if table_row_id:
                try:
                    content_group_id = PyUUID(str(table_row_id))
                except (TypeError, ValueError):
                    # 表格分块缺少合法行 ID 时允许降级为空，避免影响写入链路。
                    content_group_id = None
            new_chunks.append(
                Chunk(
                    tenant_id=kb_doc.tenant_id,
                    kb_id=kb_doc.kb_id,
                    document_id=kb_doc.document_id,
                    kb_doc_id=kb_doc.id,
                    content=content,
                    original_content=None,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    content_blocks=list(
                        fc.get("content_blocks")
                        or [{"type": "table", "text": content, "source_refs": []}]
                    ),
                    structure_version=1,
                    token_count=count_tokens(content),
                    text_length=len(content),
                    summary=None,
                    chunk_type=str(fc.get("type") or "table"),
                    status="success",
                    is_active=True,
                    is_content_edited=False,
                    position=idx,
                    path=None,
                    parent_id=None,
                    source_type="table",
                    content_group_id=content_group_id,
                    display_enabled=True,
                    metadata_info=metadata_info,
                )
            )

        if new_chunks:
            self.session.add_all(new_chunks)
            await self.session.flush()
            kb = await self.session.get(KnowledgeBase, kb_doc.kb_id)
            new_search_units = build_search_units_for_chunks(
                chunks=new_chunks,
                kb_type="table",
                retrieval_config=dict((kb.retrieval_config or {}) if kb else {}),
                kb_doc_summary=str(kb_doc.summary or "").strip() or None,
            )
            if new_search_units:
                self.session.add_all(new_search_units)
        return [chunk.id for chunk in new_chunks]

    async def _delete_kb_doc_chunks(self, kb_doc_id: PyUUID) -> None:
        """删除当前数据集已有 chunks 与检索投影。"""
        result = await self.session.execute(select(Chunk.id).where(Chunk.kb_doc_id == kb_doc_id))
        chunk_ids = [int(chunk_id) for chunk_id in result.scalars().all()]
        await delete_search_projections_for_chunk_ids(self.session, chunk_ids)
        await self.session.execute(delete(Chunk).where(Chunk.kb_doc_id == kb_doc_id))

    async def _mark_kb_doc_pending_reparse(
        self,
        kb_doc: KnowledgeBaseDocument,
        current_user: User,
        row_delta: int = 0,
    ) -> None:
        """编辑后将文档标记为待重解析。"""
        kb_doc.parse_status = "pending"
        kb_doc.parse_error = "表格数据已修改，请重新触发解析"
        kb_doc.parse_progress = 0
        kb_doc.chunk_count = 0
        kb_doc.runtime_stage = "edited_waiting_reparse"
        kb_doc.runtime_updated_at = datetime.now(timezone.utc)
        kb_doc.updated_at = datetime.now(timezone.utc)
        kb_doc.updated_by_id = current_user.id
        kb_doc.updated_by_name = current_user.nickname

        custom_metadata = dict(kb_doc.custom_metadata or {})
        custom_metadata["has_manual_edits"] = True
        custom_metadata["edited_waiting_reparse"] = True
        custom_metadata["pending_reparse_row_count"] = int(custom_metadata.get("pending_reparse_row_count") or 0) + max(row_delta, 0)
        kb_doc.custom_metadata = custom_metadata

    async def _get_row_for_user(self, row_id: PyUUID, current_user: User) -> KBTableRow:
        """获取当前用户有权访问的表格行。"""
        stmt = select(KBTableRow).where(
            KBTableRow.id == row_id,
            KBTableRow.tenant_id == current_user.tenant_id,
        )
        result = await self.session.execute(stmt)
        table_row = result.scalar_one_or_none()
        if not table_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="表格行不存在")
        return table_row

    async def _get_kb_doc_for_user(self, kb_doc_id: PyUUID, current_user: User) -> KnowledgeBaseDocument:
        """获取当前用户可访问的知识库文档挂载。"""
        stmt = select(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.id == kb_doc_id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
        )
        result = await self.session.execute(stmt)
        kb_doc = result.scalar_one_or_none()
        if not kb_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")
        return kb_doc

    async def _get_document(self, document_id: PyUUID, tenant_id: PyUUID) -> Document:
        """获取物理文档。"""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联文档不存在")
        return document

    async def _get_kb(self, kb_id: PyUUID, tenant_id: PyUUID) -> KnowledgeBase:
        """获取知识库配置。"""
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        kb = result.scalar_one_or_none()
        if not kb:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        return kb

    @staticmethod
    def _ensure_table_dataset(kb_doc: KnowledgeBaseDocument) -> None:
        """校验当前挂载是否属于表格知识库。"""
        content_kind = str((kb_doc.custom_metadata or {}).get("content_kind") or "").strip()
        chunk_strategy = str(
            (kb_doc.chunking_config or {}).get("chunk_strategy")
            or (kb_doc.chunking_config or {}).get("strategy")
            or ""
        ).strip()
        if content_kind and content_kind != "table_dataset":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前数据集不是表格知识库数据集")
        if not content_kind and chunk_strategy and chunk_strategy != "excel_table":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前数据集不是表格知识库数据集")

    def _normalize_row_data(
        self,
        row_data: Dict[str, Any],
        table_row: KBTableRow,
        kb_doc: KnowledgeBaseDocument,
    ) -> Dict[str, Any]:
        """按现有表头顺序规范化行数据。"""
        current_data = dict(table_row.row_data or {})
        header = self._get_sheet_header(kb_doc, table_row.sheet_name)
        if not header:
            header = list(current_data.keys())
        normalized: Dict[str, Any] = {}
        for col in header:
            normalized[col] = TableDatasetService._stringify_cell_value(row_data.get(col))
        for col, value in row_data.items():
            if col not in normalized:
                normalized[str(col)] = TableDatasetService._stringify_cell_value(value)
        return normalized

    @staticmethod
    def _resolve_target_sheet_name(rows: List[KBTableRow], sheet_name: Optional[str]) -> str:
        """确定新增行所属的工作表。"""
        candidate = str(sheet_name or "").strip()
        if candidate:
            return candidate
        if rows:
            return str(rows[0].sheet_name)
        return "Sheet1"

    def _resolve_header_for_new_row(
        self,
        rows: List[KBTableRow],
        row_data: Dict[str, Any],
        sheet_name: str,
        kb_doc: KnowledgeBaseDocument,
    ) -> List[str]:
        """优先复用同 Sheet 既有表头，否则退化为当前提交字段。"""
        header = self._get_sheet_header(kb_doc, sheet_name)
        if header:
            return header
        for row in rows:
            if row.sheet_name != sheet_name:
                continue
            current_keys = [str(key) for key in (row.row_data or {}).keys()]
            if current_keys:
                return current_keys
        return [str(key) for key in row_data.keys()]

    @staticmethod
    def _normalize_new_row_data(row_data: Dict[str, Any], header: List[str]) -> Dict[str, Any]:
        """按目标表头规范化新增行。"""
        normalized: Dict[str, Any] = {}
        for col in header:
            normalized[col] = TableDatasetService._stringify_cell_value(row_data.get(col))
        for col, value in row_data.items():
            if str(col) not in normalized:
                normalized[str(col)] = TableDatasetService._stringify_cell_value(value)
        return normalized

    @staticmethod
    def _next_row_index(rows: List[KBTableRow], sheet_name: str) -> int:
        """计算同一 Sheet 的下一个行序号。"""
        current_indexes = [int(row.row_index) for row in rows if row.sheet_name == sheet_name and not row.is_deleted]
        if not current_indexes:
            return 1
        return max(current_indexes) + 1

    def _build_new_row_source_meta(
        self,
        active_rows: List[KBTableRow],
        header: List[str],
        sheet_name: str,
        kb_doc: KnowledgeBaseDocument,
    ) -> Dict[str, Any]:
        """构建新增行的追溯信息。"""
        header_row_number = self._get_sheet_header_row_numbers(kb_doc).get(sheet_name)
        for row in active_rows:
            if row.sheet_name != sheet_name:
                continue
            source_meta = dict(row.source_meta or {})
            base_meta = {
                "header_row_number": header_row_number or source_meta.get("header_row_number"),
                "source_anchor": source_meta.get("source_anchor"),
            }
            return {k: v for k, v in base_meta.items() if v is not None}
        if header_row_number is not None:
            return {"header_row_number": header_row_number}
        return {}

    @staticmethod
    def _get_sheet_headers(kb_doc: KnowledgeBaseDocument) -> Dict[str, List[str]]:
        """读取表格型文档在文档级元数据中保存的 Sheet 表头。"""
        metadata = dict(kb_doc.custom_metadata or {})
        raw_map = dict(metadata.get("table_sheet_headers") or {})
        headers: Dict[str, List[str]] = {}
        for sheet_name, header in raw_map.items():
            normalized_sheet_name = str(sheet_name or "").strip()
            if not normalized_sheet_name or not isinstance(header, list):
                continue
            normalized_header = [str(item) for item in header if str(item).strip()]
            if normalized_header:
                headers[normalized_sheet_name] = normalized_header
        return headers

    @classmethod
    def _get_sheet_header(cls, kb_doc: KnowledgeBaseDocument, sheet_name: str) -> List[str]:
        """读取指定 Sheet 的表头定义。"""
        return list(cls._get_sheet_headers(kb_doc).get(sheet_name) or [])

    @staticmethod
    def _get_sheet_header_row_numbers(kb_doc: KnowledgeBaseDocument) -> Dict[str, int]:
        """读取指定文档各 Sheet 的表头物理行号。"""
        metadata = dict(kb_doc.custom_metadata or {})
        raw_map = dict(metadata.get("table_sheet_header_row_numbers") or {})
        row_numbers: Dict[str, int] = {}
        for sheet_name, row_number in raw_map.items():
            normalized_sheet_name = str(sheet_name or "").strip()
            if not normalized_sheet_name:
                continue
            try:
                normalized_row_number = int(row_number)
            except (TypeError, ValueError):
                continue
            if normalized_row_number > 0:
                row_numbers[normalized_sheet_name] = normalized_row_number
        return row_numbers

    @staticmethod
    def _compute_row_hash(row_data: Dict[str, Any]) -> str:
        """计算行数据哈希。"""
        payload = json.dumps(row_data, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _stringify_cell_value(value: Any) -> str:
        """统一单元格值为字符串表示。"""
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _trigger_train(kb_doc_id: PyUUID, chunk_ids: List[int]) -> None:
        """重建成功后触发向量训练。"""
        if not chunk_ids:
            return
        from rag.ingestion.tasks.train_task import train_document_task

        train_document_task.delay(str(kb_doc_id), [str(chunk_id) for chunk_id in chunk_ids])
