"""
QA 数据集服务

负责：
- QA 虚拟文件数据集创建
- QA 文件导入
- QA 行的增删改查
- QA chunks 的同步重建
"""
import hashlib
import json
import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID as PyUUID

from fastapi import HTTPException, status
from sqlalchemy import bindparam, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.storage import get_storage_driver
from core.storage.path_utils import generate_storage_path
from models.chunk import Chunk
from models.document import Document
from models.kb_qa_row import KBQARow
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.user import User
from rag.enums import ChunkType
from rag.ingestion.chunkers.qa import QAChunker
from rag.ingestion.parsers.qa import QAParser
from rag.search_units import build_search_units_for_chunks, delete_search_projections_for_chunk_ids
from rag.utils.token_utils import count_tokens
from services.kb_document_parse_service import (
    dispatch_parse_pipeline,
    prepare_parse_pipeline_submission,
)
from utils.qa_markdown import build_qa_markdown_text


class QADatasetService:
    """QA 数据集服务。"""

    # 允许人工维护的状态，与表格型知识库保持一致。
    _EDITABLE_PARSE_STATUSES = {"completed", "failed", "cancelled", "pending"}
    _LOCKED_PARSE_STATUSES = {"queued", "processing", "cancelling"}

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_virtual_dataset(
        self,
        kb_id: PyUUID,
        dataset_name: str,
        current_user: User,
        folder_id: Optional[PyUUID] = None,
        items: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """创建 QA 虚拟文件数据集。"""
        kb = await self._get_editable_qa_kb(kb_id, current_user)
        normalized_name = self._normalize_dataset_filename(dataset_name)
        now = datetime.now(timezone.utc)

        document = Document(
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
            name=normalized_name,
            file_type="JSON",
            storage_driver=settings.STORAGE_DRIVER,
            bucket_name=(
                settings.SEAWEEDFS_BUCKET
                if settings.STORAGE_DRIVER == "s3"
                else settings.LOCAL_STORAGE_PATH
            ),
            file_key="",
            file_size=0,
            mime_type="application/json",
            carrier_type="generated_snapshot",
            asset_kind="virtual",
            source_type="manual",
            source_url=None,
            content_hash=None,
            metadata_info={
                "virtual_file": True,
                "content_kind": "qa_dataset",
            },
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
        )
        self.session.add(document)
        await self.session.flush()

        document.file_key = generate_storage_path(
            tenant_id=current_user.tenant_id,
            filename=normalized_name,
            resource_type="documents",
            document_id=document.id,
        )

        kb_doc = KnowledgeBaseDocument(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
            document_id=document.id,
            folder_id=folder_id,
            # 统一保留扩展名，避免 QA 文件列表展示与上传文件名不一致（如丢失 .csv）
            display_name=normalized_name,
            owner_id=current_user.id,
            parse_status="completed",
            parse_error=None,
            parse_progress=100,
            chunk_count=0,
            summary=None,
            custom_metadata={
                "content_kind": "qa_dataset",
                "virtual_file": True,
                "source_mode": "manual",
            },
            parse_config=None,
            chunking_config={"strategy": "qa"},
            intelligence_config={},
            runtime_stage="completed",
            runtime_updated_at=now,
            parse_started_at=now,
            parse_ended_at=now,
            parse_duration_milliseconds=0,
            task_id=None,
            markdown_document_id=None,
            display_order=0,
            is_enabled=True,
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
        )
        self.session.add(kb_doc)
        await self.session.flush()

        normalized_items = [self._normalize_qa_structured_item(item) for item in (items or [])]
        if normalized_items:
            await self._bulk_create_items(
                kb_doc=kb_doc,
                document=document,
                current_user=current_user,
                items=normalized_items,
            )
            self._update_qa_dataset_metadata(
                kb_doc,
                row_count=len(normalized_items),
                source_mode="manual",
                virtual_file=True,
            )

        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        parse_signature = None
        if normalized_items:
            parse_signature = await self._queue_parse_pipeline(kb_doc)
        await self.session.commit()
        if parse_signature is not None:
            dispatch_parse_pipeline(parse_signature)

        return await self._build_dataset_detail_payload(kb_doc, document=document)

    async def import_dataset_file(
        self,
        kb_id: PyUUID,
        filename: str,
        file_buffer: bytes,
        current_user: User,
        folder_id: Optional[PyUUID] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """导入 QA 文件并创建可继续维护的问答集。"""
        if not filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")
        if not file_buffer:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不能为空")
        if len(file_buffer) > 20 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="导入文件大小不能超过 20MB")

        kb = await self._get_editable_qa_kb(kb_id, current_user)
        now = datetime.now(timezone.utc)
        file_ext = Path(filename).suffix.lower()
        parser = QAParser()
        if not parser.supports(file_ext):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QA 导入仅支持 .csv / .xlsx 文件",
            )

        try:
            _, metadata = parser.parse(file_buffer=file_buffer, file_extension=file_ext)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "QA_IMPORT_VALIDATION_ERROR",
                    "message": str(exc),
                    "hint": "请先下载标准模板，并检查必填列、别名分隔符 ||、enabled 值以及重复问题。",
                },
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "QA_IMPORT_PARSE_ERROR",
                    "message": f"文件解析失败: {exc}",
                    "hint": "请确认文件为 csv/xlsx，且未损坏。",
                },
            ) from exc

        qa_items = list(metadata.get("qa_items") or [])
        bucket_name = (
            settings.SEAWEEDFS_BUCKET
            if settings.STORAGE_DRIVER == "s3"
            else settings.LOCAL_STORAGE_PATH
        )
        normalized_filename = self._normalize_import_filename(filename)
        document = Document(
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
            name=normalized_filename,
            file_type=file_ext.upper().lstrip("."),
            storage_driver=settings.STORAGE_DRIVER,
            bucket_name=bucket_name,
            file_key="",
            file_size=len(file_buffer),
            mime_type=content_type or self._guess_import_mime_type(file_ext),
            carrier_type="file",
            asset_kind="physical",
            source_type="upload",
            source_url=None,
            content_hash=hashlib.sha256(file_buffer).hexdigest(),
            metadata_info={
                "virtual_file": False,
                "content_kind": "qa_dataset",
                "qa_template_version": metadata.get("template_version"),
            },
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
        )
        self.session.add(document)
        await self.session.flush()

        document.file_key = generate_storage_path(
            tenant_id=current_user.tenant_id,
            filename=normalized_filename,
            resource_type="documents",
            document_id=document.id,
        )
        await self._upload_document_bytes(
            document=document,
            file_buffer=file_buffer,
            content_type=document.mime_type or "application/octet-stream",
            extra_metadata={
                "uploaded_by": str(current_user.id),
                "content_kind": "qa_dataset",
                "template_version": str(metadata.get("template_version") or "qa_import_v1"),
            },
        )

        kb_doc = KnowledgeBaseDocument(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
            document_id=document.id,
            folder_id=folder_id,
            # 统一保留扩展名，避免 QA 文件列表展示与上传文件名不一致（如丢失 .csv）
            display_name=normalized_filename,
            owner_id=current_user.id,
            parse_status="pending",
            parse_error=None,
            parse_progress=0,
            chunk_count=0,
            summary=None,
            custom_metadata={
                "content_kind": "qa_dataset",
                "virtual_file": False,
                "source_mode": "imported",
                "source_file_type": file_ext.lstrip("."),
            },
            parse_config={"strategy": "qa"},
            chunking_config={"strategy": "qa"},
            intelligence_config={},
            runtime_stage="pending",
            runtime_updated_at=now,
            parse_started_at=None,
            parse_ended_at=None,
            parse_duration_milliseconds=0,
            task_id=None,
            markdown_document_id=None,
            display_order=0,
            is_enabled=True,
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
        )
        self.session.add(kb_doc)
        await self.session.flush()

        await self._bulk_create_imported_items(
            kb_doc=kb_doc,
            document=document,
            current_user=current_user,
            items=qa_items,
        )
        self._update_qa_dataset_metadata(
            kb_doc,
            row_count=len(qa_items),
            source_mode="imported",
            virtual_file=False,
            source_file_type=file_ext.lstrip("."),
            template_version=str(metadata.get("template_version") or "qa_import_v1"),
        )
        parse_signature = await self._queue_parse_pipeline(kb_doc)
        await self.session.commit()
        dispatch_parse_pipeline(parse_signature)

        return await self._build_dataset_detail_payload(kb_doc, document=document)

    async def list_items(
        self,
        kb_doc_id: PyUUID,
        current_user: User,
        include_disabled: bool = True,
    ) -> List[KBQARow]:
        """列出 QA 行。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        self._ensure_qa_dataset(kb_doc)
        return await self._list_items_by_kb_doc_id(kb_doc.id, include_disabled)

    async def get_dataset_detail(
        self,
        kb_doc_id: PyUUID,
        current_user: User,
    ) -> Dict[str, Any]:
        """获取 QA 数据集详情。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        self._ensure_qa_dataset(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)
        return await self._build_dataset_detail_payload(kb_doc, document=document)

    async def get_kb_facets(
        self,
        *,
        kb_id: PyUUID,
        current_user: User,
    ) -> Dict[str, Any]:
        """返回 QA 知识库下可选的分类与标签。"""

        kb = await self._get_readable_qa_kb(kb_id, current_user)

        category_stmt = (
            select(KBQARow.category)
            .where(
                KBQARow.tenant_id == current_user.tenant_id,
                KBQARow.kb_id == kb.id,
                KBQARow.is_enabled.is_(True),
                KBQARow.category.is_not(None),
                KBQARow.category != "",
            )
            .distinct()
            .order_by(KBQARow.category.asc())
        )
        categories = [
            str(row[0]).strip()
            for row in (await self.session.execute(category_stmt)).all()
            if str(row[0] or "").strip()
        ]

        tag_stmt = select(KBQARow.tags).where(
            KBQARow.tenant_id == current_user.tenant_id,
            KBQARow.kb_id == kb.id,
            KBQARow.is_enabled.is_(True),
        )
        tag_rows = (await self.session.execute(tag_stmt)).all()
        tags = self._collect_distinct_tags(
            row[0] for row in tag_rows
        )

        return {
            "kb_id": str(kb.id),
            "categories": categories,
            "tags": tags,
        }

    async def export_dataset_csv(
        self,
        kb_doc_id: PyUUID,
        current_user: User,
    ) -> tuple[bytes, str]:
        """导出当前问答集为 CSV（基于最新 QA 行，不回退到原始上传文件）。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        self._ensure_qa_dataset(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)
        items = await self._list_items_by_kb_doc_id(kb_doc.id, include_disabled=True)

        output = StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["question", "answer", "similar_questions", "category", "tags", "enabled"])
        for item in items:
            writer.writerow(
                [
                    str(item.question or "").strip(),
                    str(item.answer or "").strip(),
                    "||".join(str(v).strip() for v in (item.similar_questions or []) if str(v).strip()),
                    str(item.category or "").strip(),
                    ",".join(str(v).strip() for v in (item.tags or []) if str(v).strip()),
                    "true" if bool(item.is_enabled) else "false",
                ]
            )

        csv_text = output.getvalue()
        csv_bytes = csv_text.encode("utf-8-sig")
        filename = self._build_export_csv_filename(kb_doc.display_name or document.name)
        return csv_bytes, filename

    async def preview_import_file(
        self,
        filename: str,
        file_buffer: bytes,
    ) -> Dict[str, Any]:
        """预检 QA 导入文件模板并返回解析预览。"""
        if not filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")
        if not file_buffer:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不能为空")
        if len(file_buffer) > 20 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="预检文件大小不能超过 20MB")

        file_ext = Path(filename).suffix.lower()
        parser = QAParser()
        if not parser.supports(file_ext):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QA 导入仅支持 .csv / .xlsx 文件",
            )

        try:
            _, metadata = parser.parse(file_buffer=file_buffer, file_extension=file_ext)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "QA_IMPORT_VALIDATION_ERROR",
                    "message": str(exc),
                    "hint": "请先下载标准模板，并检查必填列、别名分隔符 ||、enabled 值以及重复问题。",
                },
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "QA_IMPORT_PARSE_ERROR",
                    "message": f"文件解析失败: {exc}",
                    "hint": "请确认文件为 csv/xlsx，且未损坏。",
                },
            ) from exc

        qa_items = list(metadata.get("qa_items") or [])
        enabled_count = sum(1 for item in qa_items if bool(item.get("is_enabled", True)))
        preview_items = [
            {
                "record_id": item.get("record_id"),
                "question": item.get("question"),
                "answer": item.get("answer"),
                "similar_questions": list(item.get("similar_questions") or []),
                "category": item.get("category"),
                "tags": list(item.get("tags") or []),
                "is_enabled": bool(item.get("is_enabled", True)),
                "source_row": item.get("source_row"),
                "source_sheet_name": item.get("source_sheet_name"),
            }
            for item in qa_items[:20]
        ]

        return {
            "file_name": filename,
            "file_type": file_ext.lstrip("."),
            "template_version": metadata.get("template_version"),
            "supported_file_types": list(metadata.get("supported_file_types") or []),
            "required_headers": ["question", "answer"],
            "optional_headers": ["similar_questions", "category", "tags", "enabled"],
            "similar_questions_separator": "||",
            "tag_separators": [",", "，", ";", "；"],
            "item_count": len(qa_items),
            "enabled_item_count": enabled_count,
            "disabled_item_count": len(qa_items) - enabled_count,
            "preview_count": len(preview_items),
            "preview_items": preview_items,
        }

    async def create_item(
        self,
        kb_doc_id: PyUUID,
        item: Dict[str, Any],
        current_user: User,
    ) -> Dict[str, Any]:
        """创建单条 QA 行。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        await self._ensure_kb_doc_editable(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)
        structured = self._normalize_qa_structured_item(item)

        position = await self.session.scalar(
            select(func.coalesce(func.max(KBQARow.position), -1) + 1).where(
                KBQARow.kb_doc_id == kb_doc.id,
            )
        )
        qa_row = self._build_qa_row(
            kb_doc=kb_doc,
            document=document,
            current_user=current_user,
            structured=structured,
            position=int(position or 0),
        )
        self.session.add(qa_row)
        await self.session.flush()

        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=1)
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "item_id": str(qa_row.id),
            "chunk_count_delta": 0,
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def batch_create_items(
        self,
        kb_doc_id: PyUUID,
        items: List[Dict[str, Any]],
        current_user: User,
    ) -> Dict[str, Any]:
        """批量创建 QA 行。"""
        if not items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问答列表不能为空")

        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        await self._ensure_kb_doc_editable(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)

        position = await self.session.scalar(
            select(func.coalesce(func.max(KBQARow.position), -1) + 1).where(
                KBQARow.kb_doc_id == kb_doc.id,
            )
        )
        next_position = int(position or 0)

        created_item_ids: List[str] = []
        for raw_item in items:
            structured = self._normalize_qa_structured_item(raw_item)
            qa_row = self._build_qa_row(
                kb_doc=kb_doc,
                document=document,
                current_user=current_user,
                structured=structured,
                position=next_position,
            )
            next_position += 1
            self.session.add(qa_row)
            await self.session.flush()
            created_item_ids.append(str(qa_row.id))

        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=len(created_item_ids))
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "created_item_ids": created_item_ids,
            "created_count": len(created_item_ids),
            "chunk_count_delta": 0,
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def update_item(
        self,
        item_id: PyUUID,
        item: Dict[str, Any],
        current_user: User,
    ) -> Dict[str, Any]:
        """更新单条 QA 行。"""
        qa_row = await self._get_item_for_user(item_id, current_user)
        await self._ensure_item_editable(qa_row, current_user)

        kb_doc = await self._get_kb_doc_for_user(qa_row.kb_doc_id, current_user)
        document = await self._get_document(qa_row.document_id, current_user.tenant_id)
        structured = self._normalize_qa_structured_item(item)

        self._apply_qa_row_update(
            qa_row=qa_row,
            structured=structured,
            current_user=current_user,
        )
        await self.session.flush()
        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=1)
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "item_id": str(qa_row.id),
            "chunk_count_delta": 0,
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def batch_update_items(
        self,
        item_updates: List[Dict[str, Any]],
        current_user: User,
    ) -> Dict[str, Any]:
        """批量更新 QA 内容项。"""
        if not item_updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问答列表不能为空")

        item_ids = [PyUUID(str(item_update.get("item_id"))) for item_update in item_updates]
        if len(set(item_ids)) != len(item_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="批量更新的问答ID不能重复")

        qa_rows = await self._get_items_for_user(item_ids, current_user)
        kb_doc = await self._get_kb_doc_for_user(qa_rows[0].kb_doc_id, current_user)
        await self._ensure_kb_doc_editable(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)

        row_map = {row.id: row for row in qa_rows}
        updated_item_ids: List[str] = []

        for item_update in item_updates:
            item_id = PyUUID(str(item_update.get("item_id")))
            qa_row = row_map.get(item_id)
            if not qa_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部分问答不存在")
            if qa_row.kb_doc_id != kb_doc.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能跨问答集批量更新")

            structured = self._normalize_qa_structured_item(dict(item_update.get("item") or {}))
            self._apply_qa_row_update(
                qa_row=qa_row,
                structured=structured,
                current_user=current_user,
            )
            updated_item_ids.append(str(qa_row.id))

        await self.session.flush()
        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=len(updated_item_ids))
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "item_ids": updated_item_ids,
            "updated_count": len(updated_item_ids),
            "chunk_count_delta": 0,
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def delete_item(self, item_id: PyUUID, current_user: User) -> Dict[str, Any]:
        """删除单条 QA 内容项。"""
        qa_row = await self._get_item_for_user(item_id, current_user)
        await self._ensure_item_editable(qa_row, current_user)

        kb_doc = await self._get_kb_doc_for_user(qa_row.kb_doc_id, current_user)
        document = await self._get_document(qa_row.document_id, current_user.tenant_id)

        await self.session.delete(qa_row)
        await self.session.flush()
        await self._normalize_positions(kb_doc.id)
        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=1)
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "item_id": str(item_id),
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def batch_delete_items(
        self,
        item_ids: List[PyUUID],
        current_user: User,
    ) -> Dict[str, Any]:
        """批量删除 QA 内容项。"""
        if not item_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问答列表不能为空")

        qa_rows = await self._get_items_for_user(item_ids, current_user)
        kb_doc = await self._get_kb_doc_for_user(qa_rows[0].kb_doc_id, current_user)
        await self._ensure_kb_doc_editable(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)

        deleted_item_ids: List[str] = []
        for qa_row in qa_rows:
            if qa_row.kb_doc_id != kb_doc.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能跨问答集批量删除")
            deleted_item_ids.append(str(qa_row.id))
            await self.session.delete(qa_row)

        await self.session.flush()
        await self._normalize_positions(kb_doc.id)
        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=len(deleted_item_ids))
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "deleted_item_ids": deleted_item_ids,
            "deleted_count": len(deleted_item_ids),
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def toggle_item_enabled(
        self,
        item_id: PyUUID,
        enabled: bool,
        current_user: User,
    ) -> Dict[str, Any]:
        """启用或禁用 QA 内容项。"""
        qa_row = await self._get_item_for_user(item_id, current_user)
        await self._ensure_item_editable(qa_row, current_user)

        kb_doc = await self._get_kb_doc_for_user(qa_row.kb_doc_id, current_user)
        document = await self._get_document(qa_row.document_id, current_user.tenant_id)

        qa_row.is_enabled = enabled
        qa_row.updated_by_id = current_user.id
        qa_row.updated_by_name = current_user.nickname
        qa_row.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=1)
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "item_id": str(qa_row.id),
            "enabled": enabled,
            "chunk_count_delta": 0,
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def batch_toggle_items_enabled(
        self,
        item_ids: List[PyUUID],
        enabled: bool,
        current_user: User,
    ) -> Dict[str, Any]:
        """批量启用或禁用 QA 内容项。"""
        if not item_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问答列表不能为空")

        qa_rows = await self._get_items_for_user(item_ids, current_user)
        kb_doc = await self._get_kb_doc_for_user(qa_rows[0].kb_doc_id, current_user)
        await self._ensure_kb_doc_editable(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)

        toggled_item_ids: List[str] = []
        for qa_row in qa_rows:
            if qa_row.kb_doc_id != kb_doc.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能跨问答集批量启停")
            qa_row.is_enabled = enabled
            qa_row.updated_by_id = current_user.id
            qa_row.updated_by_name = current_user.nickname
            qa_row.updated_at = datetime.now(timezone.utc)
            toggled_item_ids.append(str(qa_row.id))

        await self.session.flush()
        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=len(toggled_item_ids))
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "item_ids": toggled_item_ids,
            "enabled": enabled,
            "chunk_count_delta": 0,
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def reorder_items(
        self,
        kb_doc_id: PyUUID,
        item_orders: List[Dict[str, Any]],
        current_user: User,
    ) -> Dict[str, Any]:
        """调整 QA 行顺序。"""
        if not item_orders:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="顺序列表不能为空")

        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        await self._ensure_kb_doc_editable(kb_doc)
        document = await self._get_document(kb_doc.document_id, current_user.tenant_id)

        item_ids = [PyUUID(str(item_order.get("item_id"))) for item_order in item_orders]
        if len(set(item_ids)) != len(item_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="顺序列表中的问答ID不能重复")

        qa_rows = await self._get_items_for_user(item_ids, current_user)
        row_map = {row.id: row for row in qa_rows}
        existing_rows = await self._list_items_by_kb_doc_id(kb_doc.id, include_disabled=True)

        provided_positions = [int(item_order.get("position") or 0) for item_order in item_orders]
        if len(set(provided_positions)) != len(provided_positions):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目标顺序位置不能重复")
        if min(provided_positions) < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目标顺序位置不能小于0")

        for qa_row in qa_rows:
            if qa_row.kb_doc_id != kb_doc.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能跨问答集调整顺序")

        provided_map = {
            PyUUID(str(item_order.get("item_id"))): int(item_order.get("position") or 0)
            for item_order in item_orders
        }
        untouched_rows = [row for row in existing_rows if row.id not in provided_map]
        ordered_slots = list(range(len(existing_rows)))
        used_slots = set(provided_map.values())
        if max(used_slots) >= len(existing_rows):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目标顺序位置超出范围")
        remaining_slots = [slot for slot in ordered_slots if slot not in used_slots]

        for qa_row, slot in zip(untouched_rows, remaining_slots):
            qa_row.position = slot
        for item_id, target_position in provided_map.items():
            row_map[item_id].position = target_position

        await self.session.flush()
        await self._normalize_positions(kb_doc.id)
        self._mark_kb_doc_updated(kb_doc, current_user)
        await self._sync_manual_dataset_file(document=document, kb_doc=kb_doc)
        await self._mark_kb_doc_pending_reparse(kb_doc, current_user, row_delta=len(item_ids))
        await self._delete_kb_doc_chunks(kb_doc.id)
        await self.session.commit()

        return {
            "item_ids": [str(item_id) for item_id in item_ids],
            "dataset": await self._build_dataset_detail_payload(kb_doc, document=document),
        }

    async def rebuild_dataset(
        self,
        kb_doc_id: PyUUID,
        current_user: User,
    ) -> Dict[str, Any]:
        """基于 kb_qa_rows 重建当前 QA 数据集的 chunks。"""
        kb_doc = await self._get_kb_doc_for_user(kb_doc_id, current_user)
        self._ensure_qa_dataset(kb_doc)
        self._ensure_dataset_mutable(kb_doc, action_label="重新解析数据集")

        all_items = await self._list_items_by_kb_doc_id(kb_doc.id, include_disabled=True)
        if not all_items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前数据集没有可重建的问答")

        await self._delete_kb_doc_chunks(kb_doc.id)
        new_chunk_ids = await self._rebuild_chunks_for_kb_doc(kb_doc)

        custom_metadata = dict(kb_doc.custom_metadata or {})
        custom_metadata["has_manual_edits"] = True
        custom_metadata["edited_waiting_reparse"] = False
        custom_metadata["pending_reparse_row_count"] = 0
        custom_metadata["last_rebuild_from_rows_at"] = datetime.now(timezone.utc).isoformat()
        kb_doc.custom_metadata = custom_metadata

        await self.session.commit()
        self._trigger_train(kb_doc.id, new_chunk_ids)
        return await self.get_dataset_detail(kb_doc.id, current_user)

    async def _rebuild_chunks_for_kb_doc(self, kb_doc: KnowledgeBaseDocument) -> List[int]:
        """按当前 QA 行全量重建 QA chunks。"""
        items = await self._list_items_by_kb_doc_id(kb_doc.id, include_disabled=False)
        payload = [
            self._qa_row_to_chunk_payload(item)
            for item in items
            if item.is_enabled
        ]
        chunker = QAChunker(
            chunk_size=int((kb_doc.chunking_config or {}).get("chunk_size") or 512),
            chunk_overlap=int((kb_doc.chunking_config or {}).get("chunk_overlap") or 50),
        )
        final_chunks = chunker.chunk("", {"qa_items": payload})

        existing_chunk_ids = await self._find_chunk_ids_for_kb_doc(kb_doc.id)
        await self._delete_search_projections_for_chunk_ids(existing_chunk_ids)
        await self.session.execute(delete(Chunk).where(Chunk.kb_doc_id == kb_doc.id))

        new_chunks: List[Chunk] = []
        for idx, fc in enumerate(final_chunks):
            content = str(fc.get("text") or "").strip()
            metadata_info = dict(fc.get("metadata") or {})
            qa_row_id = metadata_info.get("qa_row_id")
            content_group_id: Optional[PyUUID] = None
            if qa_row_id:
                try:
                    content_group_id = PyUUID(str(qa_row_id))
                except (TypeError, ValueError):
                    # QA 行 ID 非法时降级为空，避免单条脏数据阻断整批重建。
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
                        or [{"type": "text", "text": content, "source_refs": []}]
                    ),
                    structure_version=1,
                    token_count=count_tokens(content),
                    text_length=len(content),
                    summary=None,
                    chunk_type=str(fc.get("type") or ChunkType.QA.value),
                    status="success",
                    is_active=True,
                    is_content_edited=False,
                    position=idx,
                    path=None,
                    parent_id=None,
                    source_type="qa",
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
                kb_type="qa",
                retrieval_config=dict((kb.retrieval_config or {}) if kb else {}),
                kb_doc_summary=str(kb_doc.summary or "").strip() or None,
            )
            if new_search_units:
                self.session.add_all(new_search_units)

        kb_doc.chunk_count = len(new_chunks)
        kb_doc.parse_status = "completed"
        kb_doc.parse_error = None
        kb_doc.parse_progress = 100
        kb_doc.runtime_stage = "completed"
        kb_doc.runtime_updated_at = datetime.now(timezone.utc)
        kb_doc.parse_ended_at = datetime.now(timezone.utc)
        kb_doc.updated_at = datetime.now(timezone.utc)

        return [chunk.id for chunk in new_chunks]

    async def _rebuild_single_item_chunks(
        self,
        kb_doc: KnowledgeBaseDocument,
        qa_row: KBQARow,
    ) -> List[int]:
        """增量重建单条 QA 行对应的 chunks。"""
        await self._delete_item_chunks(qa_row.id)

        if not qa_row.is_enabled:
            return []

        payload = [self._qa_row_to_chunk_payload(qa_row)]
        chunker = QAChunker(
            chunk_size=int((kb_doc.chunking_config or {}).get("chunk_size") or 512),
            chunk_overlap=int((kb_doc.chunking_config or {}).get("chunk_overlap") or 50),
        )
        final_chunks = chunker.chunk("", {"qa_items": payload})

        new_chunks: List[Chunk] = []
        for fc in final_chunks:
            content = str(fc.get("text") or "").strip()
            metadata_info = dict(fc.get("metadata") or {})
            qa_row_id = metadata_info.get("qa_row_id")
            content_group_id: Optional[PyUUID] = None
            if qa_row_id:
                try:
                    content_group_id = PyUUID(str(qa_row_id))
                except (TypeError, ValueError):
                    # QA 行 ID 非法时降级为空，避免单条脏数据阻断单行重建。
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
                        or [{"type": "text", "text": content, "source_refs": []}]
                    ),
                    structure_version=1,
                    token_count=count_tokens(content),
                    text_length=len(content),
                    summary=None,
                    chunk_type=str(fc.get("type") or ChunkType.QA.value),
                    status="success",
                    is_active=True,
                    is_content_edited=False,
                    position=0,
                    path=None,
                    parent_id=None,
                    source_type="qa",
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
                kb_type="qa",
                retrieval_config=dict((kb.retrieval_config or {}) if kb else {}),
                kb_doc_summary=str(kb_doc.summary or "").strip() or None,
            )
            if new_search_units:
                self.session.add_all(new_search_units)

        return [chunk.id for chunk in new_chunks]

    async def _delete_item_chunks(self, qa_row_id: PyUUID) -> None:
        """删除单条 QA 行关联的所有 chunks。"""
        chunk_ids = await self._find_chunk_ids_for_item(qa_row_id)
        await self._delete_search_projections_for_chunk_ids(chunk_ids)
        await self.session.execute(
            delete(Chunk).where(
                Chunk.metadata_info["qa_row_id"].astext == str(qa_row_id)
            )
        )

    async def _find_chunk_ids_for_kb_doc(self, kb_doc_id: PyUUID) -> List[int]:
        """查询某个 QA 数据集当前关联的全部 chunk ID。"""
        result = await self.session.execute(
            select(Chunk.id).where(Chunk.kb_doc_id == kb_doc_id)
        )
        return [int(chunk_id) for chunk_id in result.scalars().all()]

    async def _find_chunk_ids_for_item(self, qa_row_id: PyUUID) -> List[int]:
        """查询某条 QA 行当前关联的 chunk ID。"""
        result = await self.session.execute(
            select(Chunk.id).where(
                Chunk.metadata_info["qa_row_id"].astext == str(qa_row_id)
            )
        )
        return [int(chunk_id) for chunk_id in result.scalars().all()]

    async def _delete_search_projections_for_chunk_ids(self, chunk_ids: List[int]) -> None:
        """删除指定 chunk 对应的检索投影，避免遗留孤儿索引数据。"""
        await delete_search_projections_for_chunk_ids(self.session, chunk_ids)

    async def _delete_kb_doc_chunks(self, kb_doc_id: PyUUID) -> None:
        """删除当前 QA 数据集已有 chunks 与检索投影。"""
        chunk_ids = await self._find_chunk_ids_for_kb_doc(kb_doc_id)
        await self._delete_search_projections_for_chunk_ids(chunk_ids)
        await self.session.execute(delete(Chunk).where(Chunk.kb_doc_id == kb_doc_id))

    async def _normalize_chunk_positions(self, kb_doc_id: PyUUID) -> None:
        """按 QA 行顺序重排 chunk.position。"""
        items = await self._list_items_by_kb_doc_id(kb_doc_id, include_disabled=True)
        item_position_map = {str(item.id): item.position for item in items}

        result = await self.session.execute(
            select(Chunk).where(Chunk.kb_doc_id == kb_doc_id)
        )
        chunks = list(result.scalars().all())

        def sort_key(chunk: Chunk) -> tuple[int, int, int]:
            metadata_info = dict(chunk.metadata_info or {})
            qa_row_id = str(metadata_info.get("qa_row_id") or "")
            chunk_role = str(metadata_info.get("chunk_role") or "")
            role_order = 0 if chunk_role == "qa_row" else 1
            part_index = int(metadata_info.get("answer_part_index") or 0)
            item_position = item_position_map.get(qa_row_id, 10**9)
            return (item_position, role_order, part_index)

        for index, chunk in enumerate(sorted(chunks, key=sort_key)):
            chunk.position = index

    async def _refresh_kb_doc_chunk_stats(self, kb_doc: KnowledgeBaseDocument) -> None:
        """刷新知识库文档的 chunk 统计与运行状态。"""
        current_chunk_count = int(
            await self.session.scalar(
                select(func.count()).select_from(Chunk).where(Chunk.kb_doc_id == kb_doc.id)
            )
            or 0
        )
        kb_doc.chunk_count = current_chunk_count
        kb_doc.parse_status = "completed"
        kb_doc.parse_error = None
        kb_doc.parse_progress = 100
        kb_doc.runtime_stage = "completed"
        kb_doc.runtime_updated_at = datetime.now(timezone.utc)
        kb_doc.parse_ended_at = datetime.now(timezone.utc)

    async def _mark_kb_doc_pending_reparse(
        self,
        kb_doc: KnowledgeBaseDocument,
        current_user: User,
        row_delta: int = 0,
    ) -> None:
        """编辑后将 QA 数据集标记为待重建。"""
        kb_doc.parse_status = "pending"
        kb_doc.parse_error = "QA 数据已修改，请重新触发解析"
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
        kb_doc.updated_at = datetime.now(timezone.utc)

    async def _sync_manual_dataset_file(self, document: Document, kb_doc: KnowledgeBaseDocument) -> None:
        """同步 QA 数据集快照或维护导入型问答集的变更标记。"""
        items = await self._list_items_by_kb_doc_id(kb_doc.id, include_disabled=True)
        is_virtual_file = bool((document.metadata_info or {}).get("virtual_file"))
        if not is_virtual_file or document.source_type != "manual" or document.asset_kind != "virtual":
            metadata_info = dict(document.metadata_info or {})
            metadata_info["content_kind"] = "qa_dataset"
            metadata_info["has_manual_edits"] = True
            document.metadata_info = metadata_info

            custom_metadata = dict(kb_doc.custom_metadata or {})
            custom_metadata["has_manual_edits"] = True
            kb_doc.custom_metadata = custom_metadata

            document.updated_by_id = kb_doc.updated_by_id
            document.updated_by_name = kb_doc.updated_by_name
            document.updated_at = datetime.now(timezone.utc)
            return

        dataset_payload = [
            {
                "id": str(item.id),
                "position": item.position,
                "is_enabled": item.is_enabled,
                "question": item.question,
                "answer": item.answer,
                "similar_questions": list(item.similar_questions or []),
                "tags": list(item.tags or []),
                "category": item.category,
            }
            for item in items
        ]
        raw_bytes = json.dumps(dataset_payload, ensure_ascii=False, indent=2).encode("utf-8")

        storage = get_storage_driver(document.storage_driver)
        await storage.upload(
            file=BytesIO(raw_bytes),
            key=document.file_key,
            content_type="application/json",
            metadata={
                "tenant_id": str(document.tenant_id),
                "document_id": str(document.id),
                "kb_doc_id": str(kb_doc.id),
                "content_kind": "qa_dataset",
                "virtual_file": "true",
            },
        )

        document.file_size = len(raw_bytes)
        document.content_hash = hashlib.sha256(raw_bytes).hexdigest()
        document.updated_by_id = kb_doc.updated_by_id
        document.updated_by_name = kb_doc.updated_by_name
        document.updated_at = datetime.now(timezone.utc)

    async def _bulk_create_items(
        self,
        kb_doc: KnowledgeBaseDocument,
        document: Document,
        current_user: User,
        items: List[Dict[str, Any]],
    ) -> None:
        """批量创建初始 QA 行。"""
        for position, structured in enumerate(items):
            self.session.add(
                self._build_qa_row(
                    kb_doc=kb_doc,
                    document=document,
                    current_user=current_user,
                    structured=structured,
                    position=position,
                )
            )
        await self.session.flush()

    async def _bulk_create_imported_items(
        self,
        kb_doc: KnowledgeBaseDocument,
        document: Document,
        current_user: User,
        items: List[Dict[str, Any]],
    ) -> None:
        """批量创建导入型 QA 行。"""
        for position, raw_item in enumerate(items):
            structured = self._normalize_qa_structured_item(raw_item)
            qa_group_id = str(raw_item.get("record_id") or f"imported-{position + 1}")
            is_enabled = bool(raw_item.get("is_enabled", True))
            source_row = raw_item.get("source_row")
            source_sheet_name = raw_item.get("source_sheet_name")

            self.session.add(
                KBQARow(
                    tenant_id=kb_doc.tenant_id,
                    kb_id=kb_doc.kb_id,
                    document_id=document.id,
                    kb_doc_id=kb_doc.id,
                    source_row_id=qa_group_id,
                    position=position,
                    question=structured["question"],
                    answer=structured["answer"],
                    similar_questions=list(structured["similar_questions"]),
                    category=structured["category"],
                    tags=list(structured["tags"]),
                    source_mode="imported",
                    source_row=source_row,
                    source_sheet_name=source_sheet_name,
                    has_manual_edits=False,
                    is_enabled=is_enabled,
                    content_hash=self._build_content_hash(structured),
                    version_no=1,
                    created_by_id=current_user.id,
                    created_by_name=current_user.nickname,
                    updated_by_id=current_user.id,
                    updated_by_name=current_user.nickname,
                )
            )
        await self.session.flush()

    async def _build_dataset_detail_payload(
        self,
        kb_doc: KnowledgeBaseDocument,
        document: Optional[Document] = None,
    ) -> Dict[str, Any]:
        """构造统一的 QA 数据集详情响应。"""
        target_document = document or await self._get_document(kb_doc.document_id, kb_doc.tenant_id)
        items = await self._list_items_by_kb_doc_id(kb_doc.id, include_disabled=True)
        enabled_count = sum(1 for item in items if item.is_enabled)
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
            "document_id": str(target_document.id),
            "name": target_document.name,
            "display_name": kb_doc.display_name or target_document.name,
            "file_type": target_document.file_type,
            "carrier_type": target_document.carrier_type,
            "asset_kind": target_document.asset_kind,
            "source_type": target_document.source_type,
            "is_virtual_file": bool((target_document.metadata_info or {}).get("virtual_file")),
            "is_editable": True,
            "parse_status": kb_doc.parse_status,
            "runtime_stage": kb_doc.runtime_stage,
            "parse_error": kb_doc.parse_error,
            "chunk_count": kb_doc.chunk_count,
            "item_count": len(items),
            "enabled_item_count": enabled_count,
            "disabled_item_count": len(items) - enabled_count,
            "pending_reparse_row_count": pending_rows,
            "folder_id": str(kb_doc.folder_id) if kb_doc.folder_id else None,
            "metadata": metadata,
            "created_at": kb_doc.created_at.isoformat() if kb_doc.created_at else None,
            "updated_at": kb_doc.updated_at.isoformat() if kb_doc.updated_at else None,
        }

    def _build_qa_row(
        self,
        kb_doc: KnowledgeBaseDocument,
        document: Document,
        current_user: User,
        structured: Dict[str, Any],
        position: int,
    ) -> KBQARow:
        """构造 QA 行实体。"""
        qa_group_id = f"qa-{position + 1:06d}"
        return KBQARow(
            tenant_id=kb_doc.tenant_id,
            kb_id=kb_doc.kb_id,
            document_id=document.id,
            kb_doc_id=kb_doc.id,
            source_row_id=qa_group_id,
            position=position,
            question=structured["question"],
            answer=structured["answer"],
            similar_questions=list(structured["similar_questions"]),
            category=structured["category"],
            tags=list(structured["tags"]),
            source_mode="manual",
            source_row=None,
            source_sheet_name=None,
            has_manual_edits=False,
            is_enabled=True,
            content_hash=self._build_content_hash(structured),
            version_no=1,
            created_by_id=current_user.id,
            created_by_name=current_user.nickname,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
        )

    def _apply_qa_row_update(
        self,
        qa_row: KBQARow,
        structured: Dict[str, Any],
        current_user: User,
    ) -> None:
        """将规范化后的 QA 结构回写到 QA 行。"""
        qa_row.question = structured["question"]
        qa_row.answer = structured["answer"]
        qa_row.similar_questions = list(structured["similar_questions"])
        qa_row.category = structured["category"]
        qa_row.tags = list(structured["tags"])
        qa_row.content_hash = self._build_content_hash(structured)
        qa_row.version_no = int(qa_row.version_no or 1) + 1
        qa_row.has_manual_edits = True
        qa_row.updated_by_id = current_user.id
        qa_row.updated_by_name = current_user.nickname
        qa_row.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _mark_kb_doc_updated(kb_doc: KnowledgeBaseDocument, current_user: User) -> None:
        """刷新问答集载体的更新审计字段。"""
        kb_doc.updated_by_id = current_user.id
        kb_doc.updated_by_name = current_user.nickname
        kb_doc.updated_at = datetime.now(timezone.utc)

    async def _normalize_positions(self, kb_doc_id: PyUUID) -> None:
        """删除后重排 position。"""
        items = await self._list_items_by_kb_doc_id(kb_doc_id, include_disabled=True)
        for index, item in enumerate(items):
            item.position = index

    async def _list_items_by_kb_doc_id(
        self,
        kb_doc_id: PyUUID,
        include_disabled: bool,
    ) -> List[KBQARow]:
        """内部按 kb_doc_id 查询 QA 行。"""
        stmt = (
            select(KBQARow)
            .where(KBQARow.kb_doc_id == kb_doc_id)
            .order_by(KBQARow.position.asc(), KBQARow.created_at.asc())
        )
        if not include_disabled:
            stmt = stmt.where(KBQARow.is_enabled.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_editable_qa_kb(self, kb_id: PyUUID, current_user: User) -> KnowledgeBase:
        """获取可编辑的 QA 知识库。"""
        kb = await self.session.get(KnowledgeBase, kb_id)
        if not kb or kb.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        if kb.type != "qa":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前知识库不是 QA 类型")
        if kb.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改当前知识库")
        return kb

    async def _get_readable_qa_kb(self, kb_id: PyUUID, current_user: User) -> KnowledgeBase:
        """获取可读取的 QA 知识库。"""

        kb = await self.session.get(KnowledgeBase, kb_id)
        if not kb or kb.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        if kb.type != "qa":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前知识库不是 QA 类型")
        return kb

    def _collect_distinct_tags(
        self,
        tag_values: Iterable[Any],
        *,
        limit: Optional[int] = None,
    ) -> List[str]:
        """把多行 JSON 标签数组整理成稳定去重后的标签列表。"""

        seen: set[str] = set()
        ordered: List[str] = []
        for raw_value in tag_values:
            if not isinstance(raw_value, list):
                continue
            for item in raw_value:
                normalized = str(item or "").strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                ordered.append(normalized)
                if limit is not None and len(ordered) >= limit:
                    return sorted(ordered)
        return sorted(ordered)

    async def _get_kb_doc_for_user(self, kb_doc_id: PyUUID, current_user: User) -> KnowledgeBaseDocument:
        """获取知识库文档挂载记录并校验权限。"""
        stmt = select(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.id == kb_doc_id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
        )
        result = await self.session.execute(stmt)
        kb_doc = result.scalar_one_or_none()
        if not kb_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="问答集不存在")
        if kb_doc.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问当前问答集")
        kb = await self.session.get(KnowledgeBase, kb_doc.kb_id)
        if not kb or kb.type != "qa":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前知识库不是 QA 类型")
        return kb_doc

    async def _get_document(self, document_id: PyUUID, tenant_id: PyUUID) -> Document:
        """获取载体文档。"""
        stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="载体文档不存在")
        return document

    async def _get_item_for_user(self, item_id: PyUUID, current_user: User) -> KBQARow:
        """获取 QA 行并校验租户。"""
        stmt = select(KBQARow).where(
            KBQARow.id == item_id,
            KBQARow.tenant_id == current_user.tenant_id,
        )
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="问答不存在")
        return item

    async def _get_items_for_user(self, item_ids: List[PyUUID], current_user: User) -> List[KBQARow]:
        """批量获取 QA 行并校验租户。"""
        result = await self.session.execute(
            select(KBQARow).where(
                KBQARow.id.in_(item_ids),
                KBQARow.tenant_id == current_user.tenant_id,
            )
        )
        items = list(result.scalars().all())
        if len(items) != len(item_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部分问答不存在")
        item_map = {item.id: item for item in items}
        return [item_map[item_id] for item_id in item_ids]

    async def _ensure_item_editable(self, item: KBQARow, current_user: User) -> None:
        """校验 QA 行是否允许编辑。"""
        kb_doc = await self._get_kb_doc_for_user(item.kb_doc_id, current_user)
        await self._ensure_kb_doc_editable(kb_doc)

    async def _ensure_kb_doc_editable(self, kb_doc: KnowledgeBaseDocument) -> None:
        """校验问答集是否允许编辑。"""
        self._ensure_qa_dataset(kb_doc)
        self._ensure_dataset_mutable(kb_doc, action_label="维护问答集")

    def _ensure_qa_dataset(self, kb_doc: KnowledgeBaseDocument) -> None:
        """校验当前挂载是否为 QA 数据集。"""
        custom_metadata = dict(kb_doc.custom_metadata or {})
        content_kind = custom_metadata.get("content_kind")
        if content_kind and content_kind != "qa_dataset":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前文档不是 QA 数据集")

    def _ensure_dataset_mutable(
        self,
        kb_doc: KnowledgeBaseDocument,
        action_label: str,
    ) -> None:
        """校验当前 QA 数据集是否允许人工维护。"""
        parse_status = str(kb_doc.parse_status or "").strip().lower()
        runtime_stage = str(kb_doc.runtime_stage or "").strip().lower()

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

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"当前文档状态不支持{action_label}，请刷新后重试",
        )

    def _qa_row_to_chunk_payload(self, item: KBQARow) -> Dict[str, Any]:
        """将 QA 行转换为 QAChunker 输入结构。"""
        return {
            "qa_row_id": str(item.id),
            "record_id": str(item.source_row_id or item.id),
            "question": str(item.question or "").strip(),
            "answer": str(item.answer or "").strip(),
            "similar_questions": list(item.similar_questions or []),
            "tags": list(item.tags or []),
            "category": item.category,
            "source_row": item.source_row,
            "source_sheet_name": item.source_sheet_name,
            "source_mode": item.source_mode,
            "position": int(item.position or 0),
        }

    @staticmethod
    def _build_qa_content_text(structured: Dict[str, Any]) -> str:
        """构造内容项文本视图。"""
        return build_qa_markdown_text(
            question=str(structured.get("question") or "").strip(),
            answer=str(structured.get("answer") or "").strip(),
            similar_questions=structured.get("similar_questions") or [],
            category=str(structured.get("category") or "").strip(),
            tags=structured.get("tags") or [],
        )

    @staticmethod
    def _build_qa_summary(answer: str) -> str:
        """生成简短摘要。"""
        normalized = str(answer or "").strip()
        if len(normalized) <= 120:
            return normalized
        return f"{normalized[:117]}..."

    @staticmethod
    def _build_content_hash(structured: Dict[str, Any]) -> str:
        """基于结构化内容生成稳定哈希。"""
        raw = json.dumps(structured, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _update_qa_dataset_metadata(
        self,
        kb_doc: KnowledgeBaseDocument,
        *,
        row_count: int,
        source_mode: str,
        virtual_file: bool,
        source_file_type: Optional[str] = None,
        template_version: Optional[str] = None,
    ) -> None:
        """刷新 QA 数据集在文档级的统计与来源信息。"""
        custom_metadata = dict(kb_doc.custom_metadata or {})
        custom_metadata["content_kind"] = "qa_dataset"
        custom_metadata["qa_rows_ready"] = True
        custom_metadata["qa_row_count"] = int(row_count)
        custom_metadata["qa_rows_updated_at"] = datetime.now(timezone.utc).isoformat()
        custom_metadata["source_mode"] = source_mode
        custom_metadata["virtual_file"] = bool(virtual_file)
        if source_file_type:
            custom_metadata["source_file_type"] = source_file_type
        if template_version:
            custom_metadata["qa_template_version"] = template_version
        kb_doc.custom_metadata = custom_metadata

    async def _queue_parse_pipeline(self, kb_doc: KnowledgeBaseDocument):
        """将 QA 数据集送入统一的 parse -> chunk -> train 任务链。"""
        return await prepare_parse_pipeline_submission(
            self.session,
            kb_doc,
            reset_chunk_count=True,
        )

    @staticmethod
    def _normalize_dataset_filename(dataset_name: str) -> str:
        """规范化问答集文件名。"""
        name = str(dataset_name or "").strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问答集名称不能为空")
        if not name.lower().endswith(".json"):
            name = f"{name}.json"
        if len(name) > 255:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问答集名称过长")
        return name

    @staticmethod
    def _normalize_import_filename(filename: str) -> str:
        """规范化导入文件名。"""
        name = str(filename or "").strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")
        if len(name) > 255:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名过长")
        return name

    @staticmethod
    def _guess_import_mime_type(file_ext: str) -> str:
        """根据扩展名推断导入文件的 MIME 类型。"""
        if file_ext == ".csv":
            return "text/csv"
        if file_ext == ".xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return "application/octet-stream"

    @staticmethod
    def _build_export_csv_filename(raw_name: str) -> str:
        """构造导出的 CSV 文件名。"""
        name = str(raw_name or "").strip() or "qa_dataset"
        name = name.replace("\\", "_").replace("/", "_")
        stem = Path(name).stem or "qa_dataset"
        return f"{stem}.csv"

    @staticmethod
    def _normalize_qa_structured_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """规范化 QA 内容结构。"""
        question = str((item or {}).get("question") or "").strip()
        answer = str((item or {}).get("answer") or "").strip()
        if not question:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题不能为空")
        if not answer:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="答案不能为空")

        aliases: List[str] = []
        for value in (item or {}).get("similar_questions") or []:
            text = str(value or "").strip()
            if text and text != question and text not in aliases:
                aliases.append(text)

        tags: List[str] = []
        for value in (item or {}).get("tags") or []:
            text = str(value or "").strip()
            if text and text not in tags:
                tags.append(text)

        category = str((item or {}).get("category") or "").strip() or None
        return {
            "question": question,
            "answer": answer,
            "similar_questions": aliases,
            "tags": tags,
            "category": category,
        }

    async def _upload_document_bytes(
        self,
        document: Document,
        file_buffer: bytes,
        content_type: str,
        extra_metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """上传导入文件到存储系统。"""
        storage = get_storage_driver(document.storage_driver)
        metadata = {
            "tenant_id": str(document.tenant_id),
            "document_id": str(document.id),
            "original_filename": document.name,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        await storage.upload(
            file=BytesIO(file_buffer),
            key=document.file_key,
            content_type=content_type,
            metadata=metadata,
        )

    @staticmethod
    def _trigger_train(kb_doc_id: PyUUID, chunk_ids: List[int]) -> None:
        """懒加载触发训练任务，避免 API 启动时提前拉起任务依赖链。"""
        if not chunk_ids:
            return

        from rag.ingestion.tasks.train_task import train_document_task

        train_document_task.delay(str(kb_doc_id), [str(chunk_id) for chunk_id in chunk_ids])
