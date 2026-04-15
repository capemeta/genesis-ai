"""
文档解析任务

整合旧的 parsing_service 逻辑：
- 分布式锁（防止并发解析）
- 状态管理和进度跟踪
- 解析日志记录
- 取消机制
- 文件加载（本地/S3）
- 基于 kb_doc_id 的完整业务流程
"""

import logging
import time
import asyncio
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID
from io import BytesIO
from pathlib import Path

import redis.exceptions as redis_exc
from sqlalchemy import select, delete

from tasks.celery_tasks import celery_app
from core.database.session import create_task_redis_client, close_task_redis_client, create_task_session_maker, close_task_db_engine
from models.knowledge_base_document import KnowledgeBaseDocument
from models.knowledge_base import KnowledgeBase
from models.document import Document
from models.kb_qa_row import KBQARow
from models.kb_table_row import KBTableRow
from models.kb_web_page import KBWebPage
from models.kb_web_page_version import KBWebPageVersion
from core.config import settings
from core.storage import get_storage_driver
from core.storage.base import StorageDriver
from core.storage.path_utils import generate_storage_path
from rag.enums import ParseStrategy
from rag.ingestion.parsers import ParserFactory
from .common import (
    add_log,
    build_effective_config,
    check_cancel,
    mark_cancelled,
    mark_failed,
    document_lock,
    reset_kb_doc_runtime,
    set_runtime_stage,
    sync_latest_attempt_snapshot,
    upsert_kb_doc_runtime,
)
from rag.utils.model_utils import model_config_manager
from core.model_platform.kb_model_resolver import resolve_kb_runtime_model
from utils.qa_markdown import build_qa_markdown_text
import os

logger = logging.getLogger(__name__)


RUNTIME_PARSE_CONTEXT_KEYS = {
    "parser",
    "parse_method",
    "parse_strategy",
    "ocr",
    "vision",
    "mineru",
    "docling",
    "mineru_markdown",
    "docling_markdown",
    "markdown_document_id",
    "markdown_preview_key",
    "preview_md_mode",
    "preview_md_source_used",
    "element_count",
    "file_name",
    "file_extension",
}

RUNTIME_CHUNK_CONTEXT_KEYS = {
    "pdf_image_assets",
    "pdf_image_document_ids",
    "pdf_image_processing",
    "docx_image_assets",
    "docx_image_document_ids",
    "docx_image_processing",
    "image_assets",
    "image_document_ids",
    "image_processing",
}


def _extract_runtime_contexts(metadata: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """从解析元数据中拆分文档级运行态，避免重复写入每个 chunk。"""
    parse_context: Dict[str, Any] = {}
    chunk_context: Dict[str, Any] = {}

    for key in RUNTIME_PARSE_CONTEXT_KEYS:
        if key in metadata:
            parse_context[key] = metadata[key]

    for key in RUNTIME_CHUNK_CONTEXT_KEYS:
        if key in metadata:
            chunk_context[key] = metadata[key]

    return parse_context, chunk_context


def _build_public_document_url(document_id: str) -> str:
    """
    构建公开资源绝对 URL。

    优先级：
    1. settings.PUBLIC_API_BASE_URL（推荐在 .env 显式配置）
    2. 兜底使用 http://localhost:{PORT}{ROOT_PATH}
    """
    base_url = (settings.PUBLIC_API_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        root_path = (settings.ROOT_PATH or "/").strip()
        normalized_root = "" if root_path in {"", "/"} else f"/{root_path.strip('/')}"
        base_url = f"http://localhost:{settings.PORT}{normalized_root}"

    api_prefix = settings.API_V1_PREFIX if settings.API_V1_PREFIX.startswith("/") else f"/{settings.API_V1_PREFIX}"
    return f"{base_url}{api_prefix}/documents/public/{document_id}"


def _build_qa_content_text(item: Dict[str, Any]) -> str:
    """为 QA 内容项构造主文本视图。"""
    return build_qa_markdown_text(
        question=str(item.get("question") or "").strip(),
        answer=str(item.get("answer") or "").strip(),
        similar_questions=item.get("similar_questions") or [],
        category=str(item.get("category") or "").strip(),
        tags=item.get("tags") or [],
    )


def _build_table_row_hash(row_data: Dict[str, Any]) -> str:
    """计算表格行内容哈希。"""
    payload = json.dumps(row_data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_table_sheet_headers(kb_doc: KnowledgeBaseDocument) -> Dict[str, List[str]]:
    """从文档级元数据读取每个 Sheet 的表头定义。"""
    metadata = dict(kb_doc.custom_metadata or {})
    raw_map = dict(metadata.get("table_sheet_headers") or {})
    sheet_headers: Dict[str, List[str]] = {}
    for sheet_name, header in raw_map.items():
        normalized_sheet_name = str(sheet_name or "").strip()
        if not normalized_sheet_name or not isinstance(header, list):
            continue
        normalized_header = [str(item) for item in header if str(item).strip()]
        if normalized_header:
            sheet_headers[normalized_sheet_name] = normalized_header
    return sheet_headers


def _extract_table_sheet_header_row_numbers(kb_doc: KnowledgeBaseDocument) -> Dict[str, int]:
    """从文档级元数据读取每个 Sheet 的表头物理行号。"""
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


def _safe_parse_positive_int(value: Any) -> int | None:
    """安全解析正整数，非法值返回 None。"""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


async def _build_table_metadata_from_rows(
    session,
    kb_doc: KnowledgeBaseDocument,
) -> Dict[str, Any]:
    """
    从 kb_table_rows 重建表格 metadata。

    说明：
    - 仅用于表格知识库的后续解析/分块链路
    - 保留原有 Excel 解析链作为兜底，避免旧数据或异常场景直接失效
    """
    stmt = (
        select(KBTableRow)
        .where(
            KBTableRow.kb_doc_id == kb_doc.id,
            KBTableRow.is_deleted.is_(False),
        )
        .order_by(KBTableRow.sheet_name.asc(), KBTableRow.row_index.asc())
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    if not rows:
        return {}

    table_rows: List[Dict[str, Any]] = []
    sheet_headers: Dict[str, List[str]] = _extract_table_sheet_headers(kb_doc)
    sheet_header_row_numbers = _extract_table_sheet_header_row_numbers(kb_doc)
    sheet_info_map: Dict[str, Dict[str, Any]] = {}
    sheet_row_count: Dict[str, int] = {}

    for row in rows:
        source_meta = dict(row.source_meta or {})
        header = list(sheet_headers.get(row.sheet_name) or [])
        if not header:
            header = [str(item) for item in list(source_meta.get("header") or []) if str(item).strip()]
        if not header:
            header = [str(key) for key in (row.row_data or {}).keys()]
        row_data = dict(row.row_data or {})
        values = [str(row_data.get(col) or "").strip() for col in header]

        table_rows.append(
            {
                "table_row_id": str(row.id),
                "row_uid": row.row_uid,
                "sheet_name": row.sheet_name,
                "row_index": int(row.row_index),
                "header": header,
                "values": values,
                "source_row_number": row.source_row_number,
            }
        )

        if row.sheet_name not in sheet_headers:
            sheet_headers[row.sheet_name] = header
        sheet_row_count[row.sheet_name] = int(sheet_row_count.get(row.sheet_name, 0)) + 1
        if row.sheet_name not in sheet_info_map:
            header_row_number = sheet_header_row_numbers.get(row.sheet_name)
            if header_row_number is None:
                source_header_row_number = source_meta.get("header_row_number")
                header_row_number = _safe_parse_positive_int(source_header_row_number)
            sheet_info_map[row.sheet_name] = {
                "sheet_name": row.sheet_name,
                "header": header,
                "header_row_number": header_row_number,
                "row_count": 0,
            }

    sheets: List[Dict[str, Any]] = []
    for sheet_name in sorted(sheet_info_map.keys()):
        info = dict(sheet_info_map[sheet_name])
        info["row_count"] = int(sheet_row_count.get(sheet_name, 0))
        sheets.append(info)

    return {
        "parse_method": "excel_table_from_rows",
        "parser": "kb_table_rows",
        "table_rows": table_rows,
        "sheets": sheets,
        "table_row_count": len(table_rows),
    }


async def _build_qa_metadata_from_rows(
    session,
    kb_doc: KnowledgeBaseDocument,
) -> Dict[str, Any]:
    """
    从 kb_qa_rows 重建 QA metadata。

    说明：
    - QA 的解析阶段优先复用主事实表，避免重新从原始文件解析覆盖人工修改
    - 若当前 kb_doc 尚未落库任何 QA 行，则返回空字典，后续再回退到文件解析
    """
    stmt = (
        select(KBQARow)
        .where(KBQARow.kb_doc_id == kb_doc.id)
        .order_by(KBQARow.position.asc(), KBQARow.created_at.asc())
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    if not rows:
        return {}

    qa_items: List[Dict[str, Any]] = []
    for row in rows:
        qa_items.append(
            {
                "qa_row_id": str(row.id),
                "record_id": str(row.source_row_id or row.id),
                "question": str(row.question or "").strip(),
                "answer": str(row.answer or "").strip(),
                "similar_questions": list(row.similar_questions or []),
                "tags": list(row.tags or []),
                "category": row.category,
                "source_row": row.source_row,
                "source_sheet_name": row.source_sheet_name,
                "source_mode": row.source_mode,
                "is_enabled": bool(row.is_enabled),
                "position": int(row.position or 0),
            }
        )

    return {
        "parse_method": "qa_from_rows",
        "parser": "kb_qa_rows",
        "qa_items": qa_items,
        "qa_item_count": len(qa_items),
        "element_count": len(qa_items),
    }


async def _build_web_parse_payload(
    session,
    kb_doc: KnowledgeBaseDocument,
) -> tuple[str, Dict[str, Any]]:
    """
    从网页版本表重建 parse 输入。

    说明：
    - web_sync 已经负责抓取与正文抽取；
    - parse 阶段只做统一编排、日志与元数据组装；
    - 后续 chunk / enhance / train 仍复用通用链路。
    """
    page_stmt = select(KBWebPage).where(KBWebPage.kb_doc_id == kb_doc.id)
    page = (await session.execute(page_stmt)).scalar_one_or_none()
    if not page:
        raise ValueError("网页文档缺少 KBWebPage 主事实记录")

    version: KBWebPageVersion | None = None
    if page.last_success_version_id:
        version = await session.get(KBWebPageVersion, page.last_success_version_id)

    if version is None:
        version_stmt = (
            select(KBWebPageVersion)
            .where(
                KBWebPageVersion.kb_doc_id == kb_doc.id,
                KBWebPageVersion.is_current.is_(True),
            )
            .order_by(KBWebPageVersion.version_no.desc())
            .limit(1)
        )
        version = (await session.execute(version_stmt)).scalar_one_or_none()

    if version is None:
        raise ValueError("网页文档缺少可用的当前版本记录")

    text = str(version.content_text or "").strip()
    if not text:
        raise ValueError("网页当前版本没有可供分块的正文内容")

    parse_metadata: Dict[str, Any] = {
        "parser": "web",
        "parse_method": "web_extract",
        "version_id": str(version.id),
        "source_url": page.url,
        "url": page.url,
        "final_url": str(version.final_url or page.url or "").strip(),
        "canonical_url": str(version.canonical_url or page.canonical_url or version.final_url or page.url or "").strip(),
        "title": str(version.title or page.title or "").strip(),
        "site_name": str(version.site_name or page.site_name or page.domain or "").strip(),
        "extractor": str(version.extractor or "").strip(),
        "source_anchors": [],
        "page_numbers": [],
        "source_element_indices": [],
        "element_count": 0,
        "web_page_config": dict(page.config_json or {}),
        "web_chunking_config": dict((page.config_json or {}).get("chunking_config") or {}),
        "structured_sections": list((version.extra_metadata or {}).get("structured_sections") or []),
    }
    return text, parse_metadata


async def _persist_qa_content_items(
    session,
    kb_doc: KnowledgeBaseDocument,
    qa_items: list[Dict[str, Any]],
):
    """
    将 QA 解析结果持久化到 kb_qa_rows。

    当前策略：
    - 每次重新解析时全量替换当前 kb_doc 下的 QA 行
    - 生成稳定 position
    - 将数据库生成的 qa_row_id 回写到 qa_items，供后续分块使用
    """
    await session.execute(delete(KBQARow).where(KBQARow.kb_doc_id == kb_doc.id))
    await session.flush()

    new_items: list[KBQARow] = []
    for idx, item in enumerate(qa_items):
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        similar_questions = [str(v).strip() for v in (item.get("similar_questions") or []) if str(v).strip()]
        tags = [str(v).strip() for v in (item.get("tags") or []) if str(v).strip()]
        category = str(item.get("category") or "").strip() or None
        content_text = _build_qa_content_text(
            {
                "question": question,
                "answer": answer,
                "similar_questions": similar_questions,
                "tags": tags,
                "category": category,
            }
        )
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "question": question,
                    "answer": answer,
                    "similar_questions": similar_questions,
                    "tags": tags,
                    "category": category,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

        record = KBQARow(
            tenant_id=kb_doc.tenant_id,
            kb_id=kb_doc.kb_id,
            document_id=kb_doc.document_id,
            kb_doc_id=kb_doc.id,
            source_mode="manual" if str(item.get("source_mode") or "").strip() == "manual" else "imported",
            source_row_id=str(item.get("record_id") or f"qa-{idx + 1}"),
            position=idx,
            question=question,
            answer=answer,
            similar_questions=similar_questions,
            tags=tags,
            category=category,
            source_row=item.get("source_row"),
            source_sheet_name=item.get("source_sheet_name"),
            has_manual_edits=False,
            is_enabled=bool(item.get("is_enabled", True)),
            content_hash=content_hash,
            version_no=1,
            created_by_id=kb_doc.created_by_id,
            created_by_name=kb_doc.created_by_name,
            updated_by_id=kb_doc.updated_by_id,
            updated_by_name=kb_doc.updated_by_name,
        )
        new_items.append(record)

    session.add_all(new_items)
    await session.flush()

    for item, record in zip(qa_items, new_items):
        item["qa_row_id"] = str(record.id)
        item.setdefault("source_mode", record.source_mode)


async def _persist_table_rows(
    session,
    kb_doc: KnowledgeBaseDocument,
    metadata: Dict[str, Any],
):
    """
    将表格解析结果持久化到 kb_table_rows。

    当前策略：
    - 每次重新解析时全量替换当前 kb_doc 下的表格行
    - 生成稳定 row_uid
    - 将数据库生成的 table_row_id / row_uid 回写到 metadata.table_rows，供后续分块复用
    """
    await session.execute(delete(KBTableRow).where(KBTableRow.kb_doc_id == kb_doc.id))
    await session.flush()

    table_rows = list(metadata.get("table_rows") or [])
    sheets = list(metadata.get("sheets") or [])
    sheet_map = {
        str(sheet.get("sheet_name") or "Sheet"): sheet
        for sheet in sheets
        if isinstance(sheet, dict)
    }
    sheet_headers: Dict[str, List[str]] = {}
    sheet_header_row_numbers: Dict[str, int] = {}

    new_rows: list[KBTableRow] = []
    for row_dict in table_rows:
        if not isinstance(row_dict, dict):
            continue

        sheet_name = str(row_dict.get("sheet_name") or "Sheet")
        row_index = int(row_dict.get("row_index") or 0)
        header = [str(item) for item in (row_dict.get("header") or [])]
        values = [str(item or "").strip() for item in (row_dict.get("values") or [])]
        if row_index <= 0 or not header:
            continue

        row_uid = f"{kb_doc.id}:{sheet_name}:{row_index}"
        sheet_info = dict(sheet_map.get(sheet_name) or {})
        header_row_number = int(sheet_info.get("header_row_number") or 1)
        row_data = {col: (values[idx] if idx < len(values) else "") for idx, col in enumerate(header)}
        source_meta = {
            "sheet_name": sheet_name,
            "header_row_number": header_row_number,
            "source_anchor": f"{sheet_name}!R{row_index}",
        }
        sheet_headers[sheet_name] = list(header)
        sheet_header_row_numbers[sheet_name] = header_row_number

        record = KBTableRow(
            tenant_id=kb_doc.tenant_id,
            kb_id=kb_doc.kb_id,
            kb_doc_id=kb_doc.id,
            document_id=kb_doc.document_id,
            row_uid=row_uid,
            sheet_name=sheet_name,
            row_index=row_index,
            source_row_number=header_row_number + row_index,
            source_type="excel_import",
            row_version=1,
            is_deleted=False,
            row_hash=_build_table_row_hash(row_data),
            row_data=row_data,
            source_meta=source_meta,
            created_by_id=kb_doc.created_by_id,
            created_by_name=kb_doc.created_by_name,
            updated_by_id=kb_doc.updated_by_id,
            updated_by_name=kb_doc.updated_by_name,
        )
        new_rows.append(record)

    if new_rows:
        session.add_all(new_rows)
        await session.flush()

    # 表格型知识库的表头按文档/Sheet 维度单存，避免每行重复保存 header。
    custom_metadata = dict(kb_doc.custom_metadata or {})
    custom_metadata["table_sheet_headers"] = sheet_headers
    custom_metadata["table_sheet_header_row_numbers"] = sheet_header_row_numbers
    kb_doc.custom_metadata = custom_metadata

    for row_dict, record in zip(table_rows, new_rows):
        row_dict["table_row_id"] = str(record.id)
        row_dict["row_uid"] = record.row_uid
        row_dict["source_row_number"] = record.source_row_number


@celery_app.task(
    name="rag.ingestion.tasks.parse_document_task",
    bind=True,
    max_retries=3,
    soft_time_limit=settings.RAG_PARSE_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.RAG_PARSE_TASK_TIME_LIMIT,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def parse_document_task(self, kb_doc_id: str):
    """
    解析文档任务（整合旧逻辑）
    
    基于 kb_doc_id 的完整业务流程：
    1. 获取分布式锁
    2. 检查取消标志
    3. 加载文件（本地/S3）
    4. 解析文档
    5. 触发分块任务
    
    Args:
        kb_doc_id: 知识库文档 ID
    
    部署示例：
        celery -A tasks worker -Q parse --pool=prefork --concurrency=4 -n parse@%h
    """
    logger.info(f"[ParseTask] 收到解析任务: kb_doc_id={kb_doc_id}, retry={self.request.retries}")
    
    # 使用 asyncio.run 运行异步代码
    async def _run_process():
        # 为当前 event loop 创建独立的数据库引擎和 Redis 客户端
        task_engine, task_sm = create_task_session_maker()
        redis_client = create_task_redis_client()
        try:
            await _do_process_document(UUID(kb_doc_id), redis_client, task_sm)
        finally:
            await close_task_redis_client(redis_client)
            await close_task_db_engine(task_engine)
    
    try:
        asyncio.run(_run_process())
        logger.info(f"[ParseTask] 解析任务完成: kb_doc_id={kb_doc_id}")
        return {"status": "success", "kb_doc_id": kb_doc_id}
        
    except ValueError as e:
        # 文档正在被其他任务解析（分布式锁冲突）
        logger.warning(f"[ParseTask] 文档正在被其他任务解析: kb_doc_id={kb_doc_id}, error={e}")
        return {"status": "skipped", "kb_doc_id": kb_doc_id, "reason": str(e)}
        
    except Exception as e:
        logger.error(f"[ParseTask] 解析任务异常: kb_doc_id={kb_doc_id}, error={e}", exc_info=True)
        
        # 如果已经重试次数达上限，标记为失败，不再重试
        if self.request.retries >= self.max_retries:
            logger.error(f"[ParseTask] 解析任务重试次数已达上限: kb_doc_id={kb_doc_id}")
            
            async def _mark_failed():
                # mark_failed 只做 DB 操作，独立引擎避免跨 loop 问题
                me, ms = create_task_session_maker()
                try:
                    async with ms() as session:
                        stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id == UUID(kb_doc_id))
                        result = await session.execute(stmt)
                        kb_doc = result.scalar_one_or_none()
                        
                        if kb_doc:
                            await mark_failed(session, kb_doc, f"解析失败（已重试 {self.max_retries} 次）: {str(e)}")
                            await session.commit()
                finally:
                    await close_task_db_engine(me)
            
            try:
                asyncio.run(_mark_failed())
            except Exception as mark_err:
                logger.error(f"[ParseTask] 标记失败状态也失败了: {mark_err}")
            return {"status": "failed", "kb_doc_id": kb_doc_id, "error": str(e)}
        
        # Redis/网络超时类错误给予更长 countdown，便于服务恢复后再重试
        is_timeout = isinstance(e, (redis_exc.TimeoutError, redis_exc.ConnectionError, TimeoutError))
        countdown = min(60, 10 * (2 ** self.request.retries)) if is_timeout else (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)


async def _do_process_document(kb_doc_id: UUID, redis_client, session_maker):
    """实际的解析逻辑（已加锁）
    
    Args:
        kb_doc_id: 文档 ID
        redis_client: Redis 客户端（必须在当前 event loop 中创建）
        session_maker: 数据库 session 工厂（必须在当前 event loop 中创建）
    """
    start_time = time.time()
    
    # 使用分布式锁防止并发解析
    async with document_lock(kb_doc_id, redis_client):
        async with session_maker() as session:
            try:
                # 1. 获取文档信息
                stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id == kb_doc_id)
                result = await session.execute(stmt)
                kb_doc = result.scalar_one_or_none()
                
                if not kb_doc:
                    logger.error(f"[ParseTask] KnowledgeBaseDocument {kb_doc_id} 不存在")
                    return
                
                # 检查取消标志（第 1 次检查）
                if await check_cancel(redis_client, kb_doc_id):
                    logger.info(f"[ParseTask] 文档 {kb_doc_id} 收到取消请求，停止解析")
                    await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                    return
                
                # 幂等性检查：如果已经是 completed 状态，跳过
                if kb_doc.parse_status == "completed":
                    logger.info(f"[ParseTask] 文档 {kb_doc_id} 已完成解析，跳过")
                    return
                
                # 🔧 取消防护：如果 DB 状态已被 API 标记为 cancelled/cancelling，直接退出
                # 场景：queued 取消竞态 — Worker 取走任务时 API 已将状态设为 cancelled
                if kb_doc.parse_status in ("cancelled", "cancelling"):
                    logger.info(f"[ParseTask] 文档 {kb_doc_id} 已被取消 (status={kb_doc.parse_status})，停止解析")
                    # 如果是 cancelling，标记为 cancelled 并清理
                    if kb_doc.parse_status == "cancelling":
                        await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                    return
                
                # 获取物理文档路径
                doc_stmt = select(Document).where(Document.id == kb_doc.document_id)
                doc_result = await session.execute(doc_stmt)
                doc = doc_result.scalar_one_or_none()
                
                if not doc:
                    await mark_failed(session, kb_doc, "关联的物理文档丢失")
                    await session.commit()
                    return

                # 预先加载知识库配置，确保全链路使用统一的配置优先级计算。
                kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_doc.kb_id)
                kb_result = await session.execute(kb_stmt)
                kb = kb_result.scalar_one_or_none()
                effective_pipeline_config = build_effective_config(kb_doc, kb=kb)
                
                # 2. 更新状态和时间戳
                kb_doc.parse_status = "processing"
                kb_doc.parse_started_at = datetime.now()
                kb_doc.updated_at = datetime.now()
                set_runtime_stage(kb_doc, "loading")
                await add_log(session, kb_doc, "INIT", "任务初始化完成，开始解析...", "processing")
                await reset_kb_doc_runtime(
                    session,
                    kb_doc,
                    pipeline_task_id=kb_doc.task_id,
                    effective_config=effective_pipeline_config,
                )
                await upsert_kb_doc_runtime(
                    session,
                    kb_doc,
                    pipeline_task_id=kb_doc.task_id,
                    stats={"chunk_count": int(kb_doc.chunk_count or 0)},
                )
                await sync_latest_attempt_snapshot(
                    session,
                    kb_doc,
                    status="processing",
                    runtime_stage=kb_doc.runtime_stage,
                    task_id=kb_doc.task_id,
                    config_snapshot=effective_pipeline_config,
                    stats={"chunk_count": int(kb_doc.chunk_count or 0)},
                )
                await session.commit()
                
                logger.info(f"[ParseTask] 文档 {kb_doc_id} 开始解析")

                file_extension = os.path.splitext(doc.name)[1]
                file_ext_lower = (file_extension or "").strip().lower()
                is_excel_file = file_ext_lower in (".xlsx", ".xls")
                is_csv_file = file_ext_lower == ".csv"
                kb_type = str(kb.type or "general") if kb else "general"
                is_web_doc = (
                    kb_type == "web"
                    or str(doc.carrier_type or "").strip().lower() == "web_page"
                )

                table_rows_metadata = {}
                qa_rows_metadata = {}
                if kb_type == "table":
                    table_rows_metadata = await _build_table_metadata_from_rows(session, kb_doc)
                elif kb_type == "qa":
                    qa_rows_metadata = await _build_qa_metadata_from_rows(session, kb_doc)

                if await check_cancel(redis_client, kb_doc_id):
                    await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                    return

                data = b""
                storage_driver: StorageDriver | None = None
                if is_web_doc:
                    await add_log(session, kb_doc, "LOAD", "检测到网页同步文档，解析阶段将直接从网页版本表读取正文", "processing")
                    await session.commit()
                elif table_rows_metadata or qa_rows_metadata:
                    source_label = "kb_table_rows" if table_rows_metadata else "kb_qa_rows"
                    await add_log(session, kb_doc, "LOAD", f"检测到主事实表，解析阶段直接复用 {source_label}", "processing")
                    await session.commit()
                else:
                    await add_log(session, kb_doc, "LOAD", f"正在加载文件: {doc.name}", "processing")
                    await session.commit()

                    # 根据文档记录中的 storage_driver 获取对应的存储驱动
                    # 这样支持存储迁移和混合存储
                    if doc.storage_driver == "local":
                        from core.storage.local_driver import get_local_driver
                        # 使用文档记录中的 bucket_name（本地存储的基础路径）
                        logger.info(f"使用本地存储驱动，bucket_name={doc.bucket_name}, file_key={doc.file_key}")
                        storage_driver = get_local_driver(str(doc.bucket_name or settings.LOCAL_STORAGE_PATH))

                        # 🔍 调试：检查文件是否存在
                        file_exists = await storage_driver.exists(doc.file_key)
                        logger.info(f"文件存在性检查: file_key={doc.file_key}, exists={file_exists}")

                        if not file_exists:
                            # 打印完整路径用于调试
                            full_path = storage_driver._get_full_path(doc.file_key)
                            logger.error(f"文件不存在！完整路径: {full_path.absolute()}")
                            logger.error(f"文档信息: id={doc.id}, name={doc.name}, storage_driver={doc.storage_driver}")
                            logger.error(f"存储信息: bucket_name={doc.bucket_name}, file_key={doc.file_key}")

                            # 列出父目录的内容（如果存在）
                            if full_path.parent.exists():
                                logger.error(f"父目录内容: {list(full_path.parent.iterdir())[:10]}")  # 只显示前10个
                            else:
                                logger.error(f"父目录不存在: {full_path.parent.absolute()}")

                            raise FileNotFoundError(f"文件不存在: {doc.file_key}，完整路径: {full_path.absolute()}")

                    elif doc.storage_driver == "s3":
                        from core.storage.s3_driver import get_s3_driver
                        storage_driver = get_s3_driver()
                    else:
                        # 兜底：使用全局配置的存储驱动
                        logger.warning(f"文档 {doc.id} 的 storage_driver 未知: {doc.storage_driver}，使用全局配置")
                        storage_driver = get_storage_driver()
                    assert storage_driver is not None
                    data = await storage_driver.get_content(doc.file_key)

                # 4. 解析文档
                if await check_cancel(redis_client, kb_doc_id):
                    await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                    return
                
                await add_log(session, kb_doc, "PARSE", "提取文本内容...", "processing")
                set_runtime_stage(kb_doc, "parsing")
                await session.commit()
                
                # 确定解析策略
                if is_web_doc:
                    parse_strategy = "web_version"
                    file_extension = ".html"
                    file_ext_lower = ".html"
                elif kb_type == "table" and table_rows_metadata:
                    parse_strategy = "table_rows"
                elif kb_type == "qa" and qa_rows_metadata:
                    parse_strategy = "qa_rows"
                elif kb_type == "qa" and file_ext_lower in {".json", ".csv", ".xlsx", ".xls"}:
                    parse_strategy = ParseStrategy.QA
                # 1. 如果是 PDF，优先尊重知识库配置中的 pdf_parser_config.parser
                elif file_ext_lower == ".pdf" and kb:
                    # 从 pdf_parser_config 中获取 parser 配置
                    pdf_config = kb.pdf_parser_config or {}
                    config_pdf_parser = pdf_config.get("parser", "native")
                    
                    if config_pdf_parser == "mineru":
                        parse_strategy = ParseStrategy.MINERU
                    elif config_pdf_parser == "docling":
                        parse_strategy = ParseStrategy.DOCLING
                    elif config_pdf_parser == "tcadp":
                        parse_strategy = ParseStrategy.TCADP
                    else:
                        # native 模式下，对于 PDF 使用自动选择（可能选 OCR 或 BASIC）
                        parse_strategy = ParserFactory.auto_select_strategy(data, file_extension)
                else:
                    # 其他文件类型或 native PDF 走自动选择
                    parse_strategy = ParserFactory.auto_select_strategy(data, file_extension)
                
                logger.info(f"[ParseTask] 解析策略确定: {parse_strategy}")
                await add_log(
                    session,
                    kb_doc,
                    "PARSE",
                    f"解析策略已选择: {parse_strategy} (扩展名: {file_extension or 'unknown'})",
                    "processing"
                )
                await sync_latest_attempt_snapshot(
                    session,
                    kb_doc,
                    runtime_stage="parsing",
                    parse_strategy=str(parse_strategy),
                    config_snapshot=build_effective_config(
                        kb_doc,
                        {
                            "parse_strategy": str(parse_strategy),
                            "file_extension": file_extension,
                        },
                        kb=kb,
                    ),
                    stats={"file_size": len(data)},
                )
                
                # 创建解析器并解析
                await sync_latest_attempt_snapshot(
                    session,
                    kb_doc,
                    runtime_stage="parsing",
                    parse_strategy=str(parse_strategy),
                    config_snapshot=build_effective_config(
                        kb_doc,
                        {
                            "parse_strategy": str(parse_strategy),
                            "file_extension": file_extension,
                        },
                        kb=kb,
                    ),
                    stats={"file_size": len(data)},
                )
                if is_web_doc:
                    parser_name = "WebVersionParser"
                    text, parse_metadata = await _build_web_parse_payload(session, kb_doc)
                    await sync_latest_attempt_snapshot(
                        session,
                        kb_doc,
                        runtime_stage="parsing",
                        parser=parser_name,
                        config_snapshot=build_effective_config(
                            kb_doc,
                            {
                                "parse_strategy": str(parse_strategy),
                                "metadata_source": "kb_web_page_versions",
                                "file_extension": file_extension,
                            },
                            kb=kb,
                        ),
                        stats={"text_length": len(text)},
                    )
                    await add_log(
                        session,
                        kb_doc,
                        "PARSE",
                        (
                            "网页文档直接复用 kb_web_page_versions 当前版本正文，"
                            f"长度={len(text)}"
                        ),
                        "processing"
                    )
                elif kb_type == "table" and table_rows_metadata:
                    parser_name = "KBTableRowsParser"
                    text = ""
                    parse_metadata = table_rows_metadata
                    await sync_latest_attempt_snapshot(
                        session,
                        kb_doc,
                        runtime_stage="parsing",
                        parser=parser_name,
                        config_snapshot=build_effective_config(
                            kb_doc,
                            {
                                "parse_strategy": str(parse_strategy),
                                "metadata_source": "kb_table_rows",
                            },
                            kb=kb,
                        ),
                    )
                    await add_log(
                        session,
                        kb_doc,
                        "PARSE",
                        f"表格知识库直接复用 kb_table_rows，共 {len(parse_metadata.get('table_rows') or [])} 行",
                        "processing"
                    )
                elif kb_type == "qa" and qa_rows_metadata:
                    parser_name = "KBQARowsParser"
                    text = ""
                    parse_metadata = qa_rows_metadata
                    await sync_latest_attempt_snapshot(
                        session,
                        kb_doc,
                        runtime_stage="parsing",
                        parser=parser_name,
                        config_snapshot=build_effective_config(
                            kb_doc,
                            {
                                "parse_strategy": str(parse_strategy),
                                "metadata_source": "kb_qa_rows",
                            },
                            kb=kb,
                        ),
                    )
                    await add_log(
                        session,
                        kb_doc,
                        "PARSE",
                        f"QA 知识库直接复用 kb_qa_rows，共 {len(parse_metadata.get('qa_items') or [])} 条",
                        "processing"
                    )
                else:
                    parser_kwargs: Dict[str, Any] = {}
                    if file_ext_lower == ".pdf" and kb:
                        kb_pdf_parser_config = kb.pdf_parser_config or {}
                        # 统一读取“全局 + 类型 + 对象”后的解析配置，避免 PDF 配置来源分叉。
                        effective_parse_config = dict(
                            (build_effective_config(kb_doc, kb=kb).get("parse_config") or {})
                        )

                        doc_pdf_parser_config: Dict[str, Any] = {}
                        if isinstance(effective_parse_config, dict):
                            doc_pdf_parser_config = effective_parse_config.get("pdf_parser_config") or {}

                        merged_pdf_parser_config = {}
                        if isinstance(kb_pdf_parser_config, dict):
                            merged_pdf_parser_config.update(kb_pdf_parser_config)
                        if isinstance(doc_pdf_parser_config, dict):
                            merged_pdf_parser_config.update(doc_pdf_parser_config)

                        logger.info(
                            "[ParseTask] PDF 解析配置: kb.pdf_parser_config=%s, kb_doc.parse_config=%s, "
                            "doc_pdf_parser_config=%s, merged_pdf_parser_config=%s",
                            kb_pdf_parser_config,
                            effective_parse_config,
                            doc_pdf_parser_config,
                            merged_pdf_parser_config,
                        )

                        await add_log(
                            session,
                            kb_doc,
                            "CONFIG",
                            (
                                "PDF 解析配置已合并: "
                                f"kb_pdf_parser_config={kb_pdf_parser_config}, "
                                f"kb_doc_parse_config={effective_parse_config}, "
                                f"doc_pdf_parser_config={doc_pdf_parser_config}, "
                                f"merged_pdf_parser_config={merged_pdf_parser_config}"
                            ),
                            "processing",
                        )

                        parser_kwargs["pdf_parser_config"] = merged_pdf_parser_config
                    elif is_excel_file or is_csv_file:
                        # 通用知识库仍然从原始 Excel/CSV 直接解析。
                        parser_kwargs["excel_mode"] = "table" if kb_type == "table" else "general"

                    parser = ParserFactory.create_parser(ParseStrategy(parse_strategy), **parser_kwargs)
                    parser_name = parser.__class__.__name__
                    await sync_latest_attempt_snapshot(
                        session,
                        kb_doc,
                        runtime_stage="parsing",
                        parser=parser_name,
                        config_snapshot=build_effective_config(
                            kb_doc,
                            {
                                "parse_strategy": str(parse_strategy),
                                "pdf_parser_config": parser_kwargs.get("pdf_parser_config"),
                            },
                            kb=kb,
                        ),
                    )
                    await add_log(
                        session,
                        kb_doc,
                        "PARSE",
                        f"开始解析: parser={parser_name}, 文件大小={len(data)} bytes",
                        "processing"
                    )
                    text, parse_metadata = parser.parse(data, file_extension)

                # pdf 图片落库 + markdown 图片路径替换（与 docx 对齐）
                if storage_driver and (file_extension or "").strip().lower() == ".pdf":
                    ocr_info = parse_metadata.get("ocr") or {}
                    ocr_enabled = ocr_info.get("enabled", False)
                    ocr_engines = ocr_info.get("engines") or []
                    ocr_element_count = ocr_info.get("element_count") or 0
                    ocr_page_count = ocr_info.get("page_count") or 0
                    ocr_msg = (
                        f"OCR: enabled={ocr_enabled}, 引擎={ocr_engines}, 识别元素数={ocr_element_count}, 涉及页数={ocr_page_count}"
                    )
                    await add_log(
                        session,
                        kb_doc,
                        "PARSE",
                        (
                            "pdf 解析完成，开始处理图片:"
                            f" embedded={len(parse_metadata.get('pdf_embedded_images', []) or [])}; {ocr_msg}"
                        ),
                        "processing",
                    )
                    text, parse_metadata = await _persist_pdf_images_and_rewrite_markdown(
                        session=session,
                        storage_driver=storage_driver,
                        source_doc=doc,
                        kb_doc=kb_doc,
                        markdown_text=text,
                        parse_metadata=parse_metadata,
                    )
                    await add_log(
                        session,
                        kb_doc,
                        "PARSE",
                        (
                            "pdf 图片处理完成:"
                            f" stored_images={len(parse_metadata.get('pdf_image_assets', []) or [])},"
                            f" linked_urls={len(parse_metadata.get('pdf_image_document_ids', []) or [])}"
                        ),
                        "processing",
                    )

                # docx 图片落库 + markdown 图片路径替换（OCR/Vision 暂不处理，仅预留扩展）
                if storage_driver and (file_extension or "").strip().lower() == ".docx":
                    await add_log(
                        session,
                        kb_doc,
                        "PARSE",
                        (
                            "docx 解析完成，开始处理图片:"
                            f" placeholders={len(parse_metadata.get('docx_image_placeholders', []) or [])},"
                            f" embedded={len(parse_metadata.get('docx_embedded_images', []) or [])}"
                        ),
                        "processing"
                    )
                    text, parse_metadata = await _persist_docx_images_and_rewrite_markdown(
                        session=session,
                        storage_driver=storage_driver,
                        source_doc=doc,
                        kb_doc=kb_doc,
                        markdown_text=text,
                        parse_metadata=parse_metadata,
                    )
                    await add_log(
                        session,
                        kb_doc,
                        "PARSE",
                        (
                            "docx 图片处理完成:"
                            f" stored_images={len(parse_metadata.get('docx_image_assets', []) or [])},"
                            f" linked_urls={len(parse_metadata.get('docx_image_document_ids', []) or [])}"
                        ),
                        "processing"
                    )
                
                # 合并元数据
                metadata = {
                    "file_name": doc.name,
                    "file_extension": file_extension,
                    "parse_strategy": parse_strategy,
                    **parse_metadata  # 合并解析器返回的元数据
                }
                parse_context, chunk_context = _extract_runtime_contexts(metadata)
                if kb_type == "qa" and isinstance(metadata.get("qa_items"), list) and not qa_rows_metadata:
                    await _persist_qa_content_items(session, kb_doc, metadata["qa_items"])
                    metadata["qa_item_count"] = len(metadata["qa_items"])
                if kb_type == "table" and isinstance(metadata.get("table_rows"), list):
                    await _persist_table_rows(session, kb_doc, metadata)
                    metadata["table_row_count"] = len(metadata["table_rows"])
                parse_done_parts = [
                    f"text_length={len(text)}",
                    f"parse_method={parse_metadata.get('parse_method', 'unknown')}",
                ]
                ocr_info = parse_metadata.get("ocr") or {}
                if ocr_info:
                    parse_done_parts.append(
                        f"OCR: 引擎={ocr_info.get('engines') or []}, 识别元素数={ocr_info.get('element_count', 0)}, 页数={ocr_info.get('page_count', 0)}"
                    )
                await add_log(
                    session,
                    kb_doc,
                    "PARSE",
                    "文本提取完成: " + ", ".join(parse_done_parts),
                    "processing"
                )
                
                logger.info(f"[ParseTask] 解析完成，文本长度: {len(text)}")
                
                # 5. 存储解析成果 (将 Markdown 作为衍生 Document 维护)
                # 仅针对 PDF, Word, PPT 等需要“格式转换”的文件存储中间 MD 视图，原生的 MD/TXT 无需重复存储
                need_markdown_persistence = file_extension.lower() in (".pdf", ".docx", ".doc", ".pptx", ".ppt")
                try:
                    # 检查是否已存在关联的 Markdown 文档
                    markdown_doc = None
                    if need_markdown_persistence and kb_doc.markdown_document_id:
                        md_stmt = select(Document).where(Document.id == kb_doc.markdown_document_id)
                        md_res = await session.execute(md_stmt)
                        markdown_doc = md_res.scalar_one_or_none()

                    md_content_bytes = text.encode("utf-8")
                    md_hash = hashlib.sha256(md_content_bytes).hexdigest()
                    md_name = f"{Path(doc.name).stem}_parsed.md"

                    if need_markdown_persistence and not markdown_doc:
                        # 创建新的衍生文档记录
                        markdown_doc = Document(
                            tenant_id=kb_doc.tenant_id,
                            owner_id=kb_doc.owner_id,
                            name=md_name,
                            file_type="MD",
                            storage_driver=doc.storage_driver,
                            bucket_name=doc.bucket_name,
                            file_key="", # 待下文生成
                            file_size=len(md_content_bytes),
                            mime_type="text/markdown",
                            carrier_type="generated_snapshot",
                            asset_kind="virtual",
                            source_type="system",
                            content_hash=md_hash,
                            metadata_info={
                                "parent_document_id": str(doc.id),
                                "kb_doc_id": str(kb_doc.id),
                                "parser": metadata.get("parser")
                            },
                            created_by_id=doc.created_by_id,
                            created_by_name=doc.created_by_name
                        )
                        session.add(markdown_doc)
                        await session.flush() # 获取 ID

                        md_file_key = generate_storage_path(
                            tenant_id=kb_doc.tenant_id,
                            filename=md_name,
                            resource_type="parsed",
                            kb_doc_id=kb_doc.id
                        )
                        markdown_doc.file_key = md_file_key
                        kb_doc.markdown_document_id = markdown_doc.id
                    elif markdown_doc:
                        # 更新现有文档信息
                        markdown_doc.file_size = len(md_content_bytes)
                        markdown_doc.content_hash = md_hash
                        markdown_doc.updated_at = datetime.now()

                    if need_markdown_persistence and markdown_doc:
                        # 物理覆盖上传 (Overwrite Mode)
                        assert storage_driver is not None
                        await storage_driver.upload(
                            file=BytesIO(md_content_bytes),
                            key=markdown_doc.file_key,
                            content_type="text/markdown"
                        )
                        
                        # 确保 metadata 中也有记录以便分块任务使用
                        metadata["markdown_document_id"] = str(markdown_doc.id)
                        metadata["markdown_preview_key"] = markdown_doc.file_key
                        parse_context["markdown_document_id"] = str(markdown_doc.id)
                        parse_context["markdown_preview_key"] = markdown_doc.file_key
                        
                        logger.info(f"[ParseTask] 解析预览已持久化: {markdown_doc.id}")
                except Exception as upload_err:
                    logger.warning(f"[ParseTask] 持久化解析预览失败 (不阻断主流程): {upload_err}")

                # 6. 更新解析完成状态（parse 阶段完成）
                kb_doc.parse_ended_at = datetime.now()
                kb_doc.updated_at = datetime.now()
                kb_doc.parse_duration_milliseconds = int((time.time() - start_time) * 1000)
                done_msg = f"解析完成，文本长度: {len(text)}"
                ocr_info = parse_metadata.get("ocr") or {}
                if ocr_info and (ocr_info.get("element_count") or 0) > 0:
                    done_msg += f"; OCR: 引擎={ocr_info.get('engines') or []}, 识别元素数={ocr_info.get('element_count')}, 页数={ocr_info.get('page_count')}"
                await add_log(session, kb_doc, "PARSE", done_msg, "done")
                await sync_latest_attempt_snapshot(
                    session,
                    kb_doc,
                    runtime_stage="parsing",
                    parse_strategy=str(parse_strategy),
                    parser=parser_name,
                    effective_parser=str(metadata.get("parser") or parser_name),
                    config_snapshot=build_effective_config(
                        kb_doc,
                        {
                            "parse_strategy": str(parse_strategy),
                        },
                        kb=kb,
                    ),
                    stats={
                        "file_size": len(data),
                        "text_length": len(text),
                        "parse_duration_milliseconds": kb_doc.parse_duration_milliseconds,
                        "element_count": int(metadata.get("element_count") or 0),
                        "ocr_enabled": bool(ocr_info.get("enabled", False)),
                        "ocr_element_count": int(ocr_info.get("element_count") or 0),
                        "ocr_page_count": int(ocr_info.get("page_count") or 0),
                    },
                )
                await upsert_kb_doc_runtime(
                    session,
                    kb_doc,
                    pipeline_task_id=kb_doc.task_id,
                    effective_config=build_effective_config(
                        kb_doc,
                        {
                            "parse_strategy": parse_strategy,
                        },
                        kb=kb,
                    ),
                    parse_context=parse_context,
                    chunk_context=chunk_context,
                    stats={
                        "text_length": len(text),
                        "parse_duration_milliseconds": kb_doc.parse_duration_milliseconds,
                        "element_count": int(metadata.get("element_count") or 0),
                    },
                    error_detail={},
                )
                await session.commit()
                
                # 6. 根据知识库配置与文件类型选择分块策略（MD 用 markdown 更合理）
                effective_pipeline_config = build_effective_config(kb_doc, kb=kb)
                chunking_config = dict(effective_pipeline_config.get("chunking_config") or {})
                if is_web_doc:
                    # 网页同步允许页面级分块参数覆盖知识库默认值，但仍由后续安全上限统一收口。
                    web_chunking_config = dict(metadata.get("web_chunking_config") or {})
                    if web_chunking_config:
                        chunking_config = {
                            **chunking_config,
                            **web_chunking_config,
                        }
                chunking_mode = str(effective_pipeline_config.get("chunking_mode") or "smart")
                
                valid_strategies = (
                    "qa",
                    "fixed_size",
                    "markdown",
                    "recursive",
                    "semantic",
                    "general",
                    "smart",
                    "pdf_layout",
                    "excel_general",
                    "excel_table",
                    "web_page",
                    "rule_based",
                )
                file_ext_lower = (file_extension or "").strip().lower()
                is_md_file = file_ext_lower in (".md", ".markdown")
                is_txt_file = file_ext_lower in (".txt", ".log", ".json", ".py", ".js", ".java", ".c", ".cpp")
                config_strategy = chunking_config.get("chunk_strategy")
                pdf_config_strategy = str(chunking_config.get("pdf_chunk_strategy") or "").strip().lower()

                # PDF 分块策略统一收敛：
                # 1. 不传 / auto / markdown -> 一律走 markdown
                # 2. 只有显式 pdf_layout 才走版面分块
                resolved_pdf_strategy = None
                if file_ext_lower == ".pdf":
                    resolved_pdf_strategy = "pdf_layout" if pdf_config_strategy == "pdf_layout" else "markdown"

                # 1. 显式模式判断与智能路由
                if chunking_mode == "smart":
                    # --- 智能路由逻辑 ---
                    if is_web_doc:
                        chunk_strategy = "web_page"
                    elif kb_type == "qa":
                        chunk_strategy = "qa"
                    elif is_excel_file:
                        chunk_strategy = "excel_table" if kb_type == "table" else "excel_general"
                    elif is_csv_file:
                        chunk_strategy = "excel_table" if kb_type == "table" else "general"
                    elif is_md_file:
                        chunk_strategy = "markdown"
                    elif is_txt_file:
                        chunk_strategy = "general"
                    elif file_ext_lower == ".pdf":
                        chunk_strategy = resolved_pdf_strategy or "markdown"
                    elif file_ext_lower == ".docx":
                        # docx 已统一转换为 markdown 文本，优先走 markdown 分块
                        chunk_strategy = "markdown"
                    elif file_ext_lower == ".doc":
                        # .doc 旧格式暂不支持，保留兜底策略（解析阶段会给出明确错误）
                        chunk_strategy = "general"
                    elif file_ext_lower in (".pptx", ".ppt"):
                        # TODO: 待实现 PptChunker
                        chunk_strategy = "general"
                    else:
                        chunk_strategy = "general"
                    
                    logger.info(f"[ParseTask] 智能路由选择策略: {chunk_strategy} (文件类型: {file_ext_lower})")
                
                # 2. 手动/自定义模式 (Custom)
                elif file_ext_lower == ".pdf" and resolved_pdf_strategy:
                    chunk_strategy = resolved_pdf_strategy
                    logger.info(f"[ParseTask] PDF 使用前端指定分块策略: {chunk_strategy}")
                elif is_web_doc:
                    chunk_strategy = "web_page"
                    logger.info(f"[ParseTask] Web 知识库使用专用分块策略: {chunk_strategy}")
                elif kb_type == "qa":
                    chunk_strategy = "qa"
                    logger.info(f"[ParseTask] QA 知识库使用专用分块策略: {chunk_strategy}")
                elif config_strategy in valid_strategies:
                    chunk_strategy = config_strategy
                    logger.info(f"[ParseTask] 使用自定义分块策略: {chunk_strategy}")
                elif is_excel_file:
                    chunk_strategy = "excel_table" if kb_type == "table" else "excel_general"
                    logger.info(f"[ParseTask] Excel 使用知识库类型路由策略: {chunk_strategy}")
                elif is_csv_file:
                    chunk_strategy = "excel_table" if kb_type == "table" else "general"
                    logger.info(f"[ParseTask] CSV 使用知识库类型路由策略: {chunk_strategy}")
                else:
                    # 终极兜底：如果是文本类用 general，否则 fixed_size
                    chunk_strategy = "general" if is_txt_file else "fixed_size"
                    logger.info(f"[ParseTask] 策略兜底: {chunk_strategy}")
                if chunking_mode == "smart":
                    # 智能分块允许用户微调切片大小，但 overlap 由最终路由策略统一控制。
                    chunk_size = int(chunking_config.get("chunk_size", 512))
                    chunk_overlap = 0 if chunk_strategy == "markdown" else 50
                else:
                    chunk_size = int(chunking_config.get("chunk_size", 512))
                    chunk_overlap = int(chunking_config.get("overlap", 50))
                
                # 统一按知识库实际运行时 embedding 模型确定安全上限，未显式配置时回退租户默认模型。
                resolved_embedding_model = await resolve_kb_runtime_model(
                    session,
                    kb=kb,
                    capability_type="embedding",
                )
                model_name = resolved_embedding_model.raw_model_name
                safe_limit = model_config_manager.get_safe_token_limit(model_name, default=512)
                
                if chunk_size > safe_limit:
                    logger.warning(f"[ParseTask] chunk_size {chunk_size} 超过模型 {model_name} 的建议上限 {safe_limit}，已自动调整")
                    await add_log(session, kb_doc, "CHUNK", f"检测到分块大小超过模型建议上限 ({safe_limit})，已自动调整为安全值", "processing")
                    chunk_size = safe_limit

                chunk_size = max(100, min(2000, chunk_size))
                chunk_overlap = max(0, min(chunk_overlap, int(chunk_size * 0.5))) # 重叠不应超过分块的一半
                logger.info(f"[ParseTask] 分块策略: {chunk_strategy}, chunk_size={chunk_size}, overlap={chunk_overlap}, model={model_name}")
                await add_log(
                    session,
                    kb_doc,
                    "CHUNK",
                    (
                        "分块参数已确定:"
                        f" strategy={chunk_strategy}, chunk_size={chunk_size},"
                        f" overlap={chunk_overlap}, model={model_name}"
                    ),
                    "processing"
                )
                set_runtime_stage(kb_doc, "chunking")
                await sync_latest_attempt_snapshot(
                    session,
                    kb_doc,
                    runtime_stage="chunking",
                    parse_strategy=str(parse_strategy),
                    chunk_strategy=chunk_strategy,
                    config_snapshot=build_effective_config(
                        kb_doc,
                        {
                            "parse_strategy": str(parse_strategy),
                            "chunk_strategy": chunk_strategy,
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                            "embedding_model": model_name,
                            "embedding_model_limit": safe_limit,
                        },
                        kb=kb,
                    ),
                    stats={
                        "text_length": len(text),
                        "element_count": int(metadata.get("element_count") or 0),
                    },
                )
                await upsert_kb_doc_runtime(
                    session,
                    kb_doc,
                    pipeline_task_id=kb_doc.task_id,
                    effective_config=build_effective_config(
                        kb_doc,
                        {
                            "parse_strategy": parse_strategy,
                            "chunk_strategy": chunk_strategy,
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                            "embedding_model": model_name,
                            "embedding_model_limit": safe_limit,
                        },
                        kb=kb,
                    ),
                    stats={
                        "text_length": len(text),
                        "element_count": int(metadata.get("element_count") or 0),
                    },
                )
                await session.commit()
                
                # 7. 触发分块任务
                logger.info(f"[ParseTask] 触发分块任务: {kb_doc_id}")
                from rag.ingestion.tasks.chunk_task import (
                    build_excel_table_shard_tasks,
                    chunk_document_task,
                    chunk_excel_table_shard_task,
                    should_shard_excel_table,
                )
                # 过滤掉已明确传递的参数，防止 TypeError
                other_config = {k: v for k, v in chunking_config.items() if k not in ("chunk_strategy", "chunk_size", "overlap")}
                # 让分块器能区分 smart 与 custom，避免自定义参数影响智能分块默认行为。
                other_config["chunking_mode"] = chunking_mode
                if chunk_strategy == "web_page":
                    requested_max_embed_tokens = int(other_config.get("max_embed_tokens") or safe_limit)
                    other_config["max_embed_tokens"] = max(1, min(requested_max_embed_tokens, safe_limit))
                # 两种 Excel 策略都需要统一的向量预算与 token 口径，避免表格模式配置漂移。
                if chunk_strategy in ("excel_table", "excel_general"):
                    requested_max_embed_tokens = int(other_config.get("max_embed_tokens") or safe_limit)
                    # 表格模式的预算不能超过当前嵌入模型安全上限，避免某些链路绕过模型约束。
                    other_config["max_embed_tokens"] = max(1, min(requested_max_embed_tokens, safe_limit))
                    # Excel 分块固定使用 tokenizer 口径，避免 chars 近似低估中文 token。
                    other_config["token_count_method"] = "tokenizer"
                    # Sheet 根节点是前端层级展示和后续聚合的稳定锚点，统一保持开启。
                    other_config["enable_summary_chunk"] = True
                
                if chunk_strategy == "excel_table" and should_shard_excel_table(metadata):
                    shard_tasks = build_excel_table_shard_tasks(
                        str(kb_doc_id),
                        metadata,
                        chunk_strategy,
                        chunk_size,
                        chunk_overlap,
                        **other_config,
                    )
                    await add_log(
                        session,
                        kb_doc,
                        "CHUNK",
                        f"检测到大表，已拆分为 {len(shard_tasks)} 个分片任务并行处理",
                        "processing",
                    )
                    for shard in shard_tasks:
                        chunk_excel_table_shard_task.delay(
                            str(kb_doc_id),
                            text,
                            metadata,
                            chunk_strategy=chunk_strategy,
                            chunk_size=chunk_size,
                            chunk_overlap=chunk_overlap,
                            embedding_model_limit=safe_limit,
                            sheet_name=shard["sheet_name"],
                            sheet_root_node_id=shard["sheet_root_node_id"],
                            row_from=shard["row_from"],
                            row_to=shard["row_to"],
                            emit_summary=shard["emit_summary"],
                            clear_existing=shard["clear_existing"],
                            **other_config,
                        )
                else:
                    chunk_document_task.delay(
                        str(kb_doc_id),
                        text,
                        metadata,
                        chunk_strategy=chunk_strategy,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        embedding_model_limit=safe_limit,  # 🔧 传递嵌入模型的安全上限
                        **other_config
                    )
                
                # 🔧 不在此处清理取消标志！
                # 取消标志需要保留到整个任务链结束（chunk → enhance → train），
                # 由 mark_cancelled 或 mark_completed 统一清理。
                # 如果在此处删除，则 parse_task 最后一次 check_cancel 之后、
                # chunk_task 第一次 check_cancel 之前的取消请求会被"吞掉"。
                
                logger.info(f"[ParseTask] 文档 {kb_doc_id} 解析完成, 耗时 {kb_doc.parse_duration_milliseconds}ms")
                
            except Exception as e:
                logger.exception(f"[ParseTask] 解析文档 {kb_doc_id} 失败: {str(e)}")
                await session.rollback()
                # 不在此处 mark_failed，将异常向上抛出，由外层根据重试次数决定重试或 mark_failed
                raise


async def _persist_docx_images_and_rewrite_markdown(
    session,
    storage_driver,
    source_doc: Document,
    kb_doc: KnowledgeBaseDocument,
    markdown_text: str,
    parse_metadata: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    """
    将 docx 内嵌图片落库存储，并替换 markdown 占位符为可访问路径。

    约定：
    - `docx_embedded_images` 由 BasicParser 提供，包含图片二进制；
    - 当前仅做存储与路径替换，不做 OCR/Vision；
    - 结果会写回 `parse_metadata["docx_image_assets"]` 供后续流程扩展。
    """
    embedded_images = parse_metadata.pop("docx_embedded_images", []) or []
    placeholders = parse_metadata.get("docx_image_placeholders", []) or []
    if not embedded_images:
        return markdown_text, parse_metadata

    image_doc_ids: list[str] = []
    image_assets: list[Dict[str, Any]] = []
    image_url_map: dict[str, str] = {}
    rid_to_document_id: dict[str, str] = {}
    uploaded_keys: list[str] = []

    try:
        for image in embedded_images:
            image_id = str(image.get("id", "")).strip()
            image_rid = str(image.get("rid", "")).strip()
            image_blob = image.get("blob")
            if not image_id or not isinstance(image_blob, (bytes, bytearray)):
                continue

            content_type = str(image.get("content_type") or "application/octet-stream")
            ext = str(image.get("ext") or ".bin")
            if not ext.startswith("."):
                ext = f".{ext}"

            # 同一 rid 复用同一物理图片，避免重复落库
            if image_rid and image_rid in rid_to_document_id:
                reused_document_id = rid_to_document_id[image_rid]
                image_url_map[image_id] = _build_public_document_url(reused_document_id)
                continue

            image_hash = hashlib.sha256(image_blob).hexdigest()
            existing_stmt = select(Document).where(
                Document.tenant_id == source_doc.tenant_id,
                Document.content_hash == image_hash,
                Document.is_deleted == False,
            )
            existing_result = await session.execute(existing_stmt)
            existing_image_doc = existing_result.scalar_one_or_none()

            if existing_image_doc:
                image_document = existing_image_doc
            else:
                image_name = f"{Path(source_doc.name).stem}_{image_id}{ext}"
                image_document = Document(
                    tenant_id=source_doc.tenant_id,
                    owner_id=source_doc.owner_id,
                    name=image_name,
                    file_type=ext.upper().lstrip("."), 
                    storage_driver=source_doc.storage_driver,
                    bucket_name=source_doc.bucket_name,
                    file_key="",
                    file_size=len(image_blob),
                    mime_type=content_type,
                    carrier_type="file",
                    asset_kind="physical",
                    source_type="upload",
                    content_hash=image_hash,
                    metadata_info={
                        "origin": "docx_embedded_image",
                        "parent_document_id": str(source_doc.id),
                        "kb_doc_id": str(kb_doc.id),
                        "docx_image_id": image_id,
                        "docx_image_rid": image_rid,
                    },
                    created_by_id=source_doc.created_by_id,
                    created_by_name=source_doc.created_by_name,
                )
                session.add(image_document)
                await session.flush()

                image_file_key = generate_storage_path(
                    tenant_id=source_doc.tenant_id,
                    filename=image_name,
                    resource_type="documents",
                    document_id=image_document.id,
                )
                await storage_driver.upload(
                    file=BytesIO(image_blob),
                    key=image_file_key,
                    content_type=content_type,
                    metadata={
                        "tenant_id": str(source_doc.tenant_id),
                        "uploaded_by": str(source_doc.owner_id),
                        "document_id": str(image_document.id),
                        "original_filename": image_name,
                        "source_document_id": str(source_doc.id),
                    },
                )
                uploaded_keys.append(image_file_key)
                image_document.file_key = image_file_key

            image_document_id = str(image_document.id)
            image_doc_ids.append(image_document_id)
            image_assets.append(
                {
                    "id": image_id,
                    "rid": image_rid,
                    "image_document_id": image_document_id,
                    "url": _build_public_document_url(image_document_id),
                    "content_type": image_document.mime_type,
                    "file_key": image_document.file_key,
                }
            )
            image_url_map[image_id] = _build_public_document_url(image_document_id)
            if image_rid:
                rid_to_document_id[image_rid] = image_document_id
    except Exception:
        # 如果 DB 事务后续回滚，已上传文件会成为孤儿对象；这里先做 best-effort 清理。
        for key in uploaded_keys:
            try:
                await storage_driver.delete(key)
            except Exception as cleanup_err:
                logger.warning(f"[ParseTask] 清理 docx 临时图片失败: key={key}, error={cleanup_err}")
        raise

    # 替换 markdown 中的占位路径
    updated_markdown = markdown_text
    for image_id, image_url in image_url_map.items():
        updated_markdown = updated_markdown.replace(f"docx://embedded/{image_id}", image_url)

    # 更新占位符状态，标记已落库
    if placeholders:
        for item in placeholders:
            placeholder_id = str(item.get("id", "")).strip()
            if placeholder_id in image_url_map:
                item["status"] = "stored"
                item["url"] = image_url_map[placeholder_id]

    parse_metadata["docx_image_assets"] = image_assets
    parse_metadata["docx_image_document_ids"] = sorted(set(image_doc_ids))
    parse_metadata["docx_image_processing"] = {
        **(parse_metadata.get("docx_image_processing", {}) or {}),
        "status": "stored",
        "ocr_enabled": False,
        "vision_enabled": False,
        "next_step": "后续可基于 docx_image_assets 对接 OCRParser/VisionParser",
    }

    return updated_markdown, parse_metadata


async def _persist_pdf_images_and_rewrite_markdown(
    session,
    storage_driver,
    source_doc: Document,
    kb_doc: KnowledgeBaseDocument,
    markdown_text: str,
    parse_metadata: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    embedded_images = parse_metadata.pop("pdf_embedded_images", []) or []
    if not embedded_images:
        return markdown_text, parse_metadata

    image_doc_ids: list[str] = []
    image_assets: list[Dict[str, Any]] = []
    image_url_map: dict[str, str] = {}
    uploaded_keys: list[str] = []

    try:
        for image in embedded_images:
            image_id = str(image.get("id", "")).strip()
            image_blob = image.get("blob")
            if not image_id or not isinstance(image_blob, (bytes, bytearray)):
                continue

            content_type = str(image.get("content_type") or "application/octet-stream")
            ext = str(image.get("ext") or ".bin")
            if not ext.startswith("."):
                ext = f".{ext}"

            image_hash = hashlib.sha256(image_blob).hexdigest()
            existing_stmt = select(Document).where(
                Document.tenant_id == source_doc.tenant_id,
                Document.content_hash == image_hash,
                Document.is_deleted == False,
            )
            existing_result = await session.execute(existing_stmt)
            existing_image_doc = existing_result.scalar_one_or_none()

            if existing_image_doc:
                image_document = existing_image_doc
            else:
                image_name = f"{Path(source_doc.name).stem}_pdf_{image_id}{ext}"
                image_document = Document(
                    tenant_id=source_doc.tenant_id,
                    owner_id=source_doc.owner_id,
                    name=image_name,
                    file_type=ext.upper().lstrip("."),
                    storage_driver=source_doc.storage_driver,
                    bucket_name=source_doc.bucket_name,
                    file_key="",
                    file_size=len(image_blob),
                    mime_type=content_type,
                    carrier_type="file",
                    asset_kind="physical",
                    source_type="upload",
                    content_hash=image_hash,
                    metadata_info={
                        "origin": "pdf_embedded_image",
                        "parent_document_id": str(source_doc.id),
                        "kb_doc_id": str(kb_doc.id),
                        "pdf_image_id": image_id,
                        "page_no": image.get("page_no"),
                        "bbox": image.get("bbox"),
                    },
                    created_by_id=source_doc.created_by_id,
                    created_by_name=source_doc.created_by_name,
                )
                session.add(image_document)
                await session.flush()

                image_file_key = generate_storage_path(
                    tenant_id=source_doc.tenant_id,
                    filename=image_name,
                    resource_type="documents",
                    document_id=image_document.id,
                )
                await storage_driver.upload(
                    file=BytesIO(image_blob),
                    key=image_file_key,
                    content_type=content_type,
                    metadata={
                        "tenant_id": str(source_doc.tenant_id),
                        "uploaded_by": str(source_doc.owner_id),
                        "document_id": str(image_document.id),
                        "original_filename": image_name,
                        "source_document_id": str(source_doc.id),
                    },
                )
                uploaded_keys.append(image_file_key)
                image_document.file_key = image_file_key

            image_document_id = str(image_document.id)
            image_doc_ids.append(image_document_id)
            url = _build_public_document_url(image_document_id)
            image_assets.append(
                {
                    "id": image_id,
                    "image_document_id": image_document_id,
                    "url": url,
                    "content_type": image_document.mime_type,
                    "file_key": image_document.file_key,
                }
            )
            image_url_map[image_id] = url

    except Exception:
        for key in uploaded_keys:
            try:
                await storage_driver.delete(key)
            except Exception as cleanup_err:
                logger.warning(f"[ParseTask] 清理 pdf 临时图片失败: key={key}, error={cleanup_err}")
        raise

    updated_markdown = markdown_text
    for image_id, image_url in image_url_map.items():
        updated_markdown = updated_markdown.replace(f"pdf://embedded/{image_id}", image_url)

    elements = parse_metadata.get("elements")
    if isinstance(elements, list) and image_url_map:
        for el in elements:
            if not isinstance(el, dict):
                continue
            if el.get("type") != "image":
                continue
            content = str(el.get("content") or "")
            for image_id, image_url in image_url_map.items():
                if content == f"pdf://embedded/{image_id}":
                    el["content"] = image_url
                    break

    parse_metadata["pdf_image_assets"] = image_assets
    parse_metadata["pdf_image_document_ids"] = sorted(set(image_doc_ids))
    parse_metadata["pdf_image_processing"] = {
        **(parse_metadata.get("pdf_image_processing", {}) or {}),
        "status": "stored",
    }

    return updated_markdown, parse_metadata
