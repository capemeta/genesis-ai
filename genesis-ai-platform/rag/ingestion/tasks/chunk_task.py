"""
文档分块任务

整合状态管理和日志记录
"""

from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime
import hashlib
from uuid import uuid5, NAMESPACE_DNS

import redis.exceptions as redis_exc
from sqlalchemy import select, delete, func

from tasks.celery_tasks import celery_app
from core.database.session import create_task_redis_client, close_task_redis_client, create_task_session_maker, close_task_db_engine
from models.knowledge_base_document import KnowledgeBaseDocument
from models.knowledge_base import KnowledgeBase
from models.chunk import Chunk
from models.kb_qa_row import KBQARow
from rag.enums import ChunkStrategy, ChunkType
from rag.ingestion.chunkers import ChunkerFactory
from rag.search_units import build_search_units_for_chunks, delete_search_projections_for_chunk_ids
from rag.schema import BaseChunk
from .common import (
    add_log,
    build_effective_config,
    check_cancel,
    mark_cancelled,
    mark_failed,
    set_runtime_stage,
    sync_latest_attempt_snapshot,
    upsert_kb_doc_runtime,
)
import asyncio
import logging

logger = logging.getLogger(__name__)

IMAGE_ANALYSIS_STATUSES = {"none", "caption", "ocr", "vision", "ocr_vision"}

# 表格模式大表分片阈值：单个 Sheet 数据行数超过此值时拆分为多个子任务
TABLE_BATCH_SIZE = 3000

CHUNK_METADATA_KEEP_KEYS = {
    "node_id",
    "origin_node_id",
    "parent_id",
    "child_ids",
    "depth",
    "is_leaf",
    "is_root",
    "is_hierarchical",
    "should_vectorize",
    "exclude_from_retrieval",
    "heading",
    "header_path",
    "section_level",
    "budget_header_text",
    "prompt_header_text",
    "prompt_header_paths",
    "source_anchors",
    "source_element_indices",
    "source_anchor_engine",
    "source_anchor_confidence",
    "source_anchor_coordinate_system",
    "source_ref_protocol",
    "page_numbers",
    "primary_page_number",
    "parser",
    "parse_method",
    "chunk_strategy",
    "qa_row_id",
    "chunk_role",
    "tags",
    "category",
    "question",
    "similar_questions",
    "answer_part_index",
    "answer_part_total",
    "table_row_id",
    "version_id",
    "content_group_id",
    "source_mode",
    "source_row",
    "source_sheet_name",
    "row_id",
    "row_count",
    "filter_column_names",
    # Excel 专属字段
    "sheet_name",           # 工作表名称
    "row_index",            # 原始行号（表格模式，1-based）
    "row_start",            # chunk 起始行（通用模式，1-based）
    "row_end",              # chunk 结束行（通用模式，1-based）
    "header",               # 表头列名列表
    "filter_fields",        # 过滤列键值对 {"地区": "南康区"}，用于检索前精确过滤
    "is_row_overflow",      # 第三级降级：单行超 token 拆成多个 sub-chunk 时为 True
    "overflow_part_index",  # overflow 子块序号（1-based）
    "overflow_part_total",  # overflow 子块总数
    "content_truncated",    # 通用模式：content 超限后被截断时为 True（content_blocks 保留完整数据）
    "formula_none_cells",   # 公式缓存为 None 的单元格数量（用于向用户告警）
    "chunk_role",           # Excel 父子块角色（summary/row_parent/row_child）
    "field_names",          # 当前 chunk 关联的列名列表
    "identity_field_names", # 当前 chunk 复用的身份列名
    "row_identity_text",    # 行身份文本（如 Sheet + 行号）
}


async def _load_qa_items_for_chunking(session, kb_doc_id: UUID) -> List[Dict[str, Any]]:
    """从 QA 主事实表中加载当前 kb_doc 的 QA 行，供 QAChunker 使用。"""
    stmt = (
        select(KBQARow)
        .where(
            KBQARow.kb_doc_id == kb_doc_id,
            KBQARow.is_enabled.is_(True),
        )
        .order_by(KBQARow.position.asc(), KBQARow.created_at.asc())
    )
    result = await session.execute(stmt)
    items = result.scalars().all()

    payload: List[Dict[str, Any]] = []
    for item in items:
        payload.append(
            {
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
        )
    return payload


def _safe_parse_uuid(value: Any) -> Optional[UUID]:
    """安全解析 UUID 字符串，非法值返回 None。"""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return UUID(raw)
    except (TypeError, ValueError, AttributeError):
        return None


def _resolve_chunk_source_type(kb_type: str, chunk_metadata: Dict[str, Any], parse_metadata: Dict[str, Any]) -> str:
    """推断 chunk 的来源类型，便于后续检索与聚合。"""
    if chunk_metadata.get("qa_row_id"):
        return "qa"
    if chunk_metadata.get("table_row_id"):
        return "table"
    if chunk_metadata.get("version_id") or str(parse_metadata.get("parse_method") or "").strip() == "web_extract":
        return "web"
    if kb_type == "qa":
        return "qa"
    if kb_type == "table":
        return "table"
    if kb_type == "web":
        return "web"
    return "document"


def _resolve_chunk_content_group_id(chunk_metadata: Dict[str, Any]) -> Optional[UUID]:
    """解析业务聚合单元ID，优先使用事实表主键。"""
    for key in ("content_group_id", "qa_row_id", "table_row_id", "version_id"):
        parsed = _safe_parse_uuid(chunk_metadata.get(key))
        if parsed is not None:
            return parsed
    return None


def _normalize_source_ref_legacy(ref: Any) -> Optional[Dict[str, Any]]:
    """统一来源引用结构，避免各分块策略输出不一致。

    支持两种形态：
    - PDF 坐标型：必须有 page_no + page_number + bbox（四元组）
    - 非 PDF 行定位型（Excel 等）：有 page_no + element_index，无 bbox 也可通过
    """
    if not isinstance(ref, dict):
        return None

    page_no = ref.get("page_no")
    page_number = ref.get("page_number")
    if page_number is None and isinstance(page_no, int):
        page_number = page_no + 1
    if page_no is None and isinstance(page_number, int):
        page_no = page_number - 1

    if not isinstance(page_no, int) or not isinstance(page_number, int):
        return None

    bbox = ref.get("bbox")
    element_index = ref.get("element_index")

    if isinstance(bbox, list) and len(bbox) == 4:
        # PDF 坐标型：校验 bbox 合法性
        try:
            norm_bbox = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
        except Exception:
            return None
        if norm_bbox[2] <= norm_bbox[0] or norm_bbox[3] <= norm_bbox[1]:
            return None
        normalized: Dict[str, Any] = {
            "page_no": page_no,
            "page_number": page_number,
            "bbox": norm_bbox,
        }
        if isinstance(element_index, int):
            normalized["element_index"] = element_index
        if ref.get("element_type") is not None:
            normalized["element_type"] = str(ref["element_type"])
        return normalized

    # 非 PDF 行定位型（Excel、表格等无坐标场景）：要求至少有 element_index 定位行
    if isinstance(element_index, int):
        normalized = {
            "page_no": page_no,
            "page_number": page_number,
            "element_index": element_index,
        }
        if ref.get("element_type") is not None:
            normalized["element_type"] = str(ref["element_type"])
        return normalized

    return None


def _build_source_refs_from_element_indices(
    elements: List[Dict[str, Any]],
    indices: List[int],
) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for i in indices:
        if i < 0 or i >= len(elements):
            continue
        item = elements[i]
        refs.append(
            {
                "page_no": int(item["page_no"]),
                "page_number": int(item["page_no"]) + 1,
                "bbox": [float(v) for v in item["bbox"]],
                "element_index": int(item["idx"]),
                "element_type": "text",
            }
        )
    return refs


def _dedupe_int_list(values: List[Any]) -> List[int]:
    seen: set[int] = set()
    out: List[int] = []
    for value in values:
        if not isinstance(value, int) or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _dedupe_anchors(anchors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[Tuple[int, float, float, float, float]] = set()
    out: List[Dict[str, Any]] = []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        page_no = anchor.get("page_no")
        bbox = anchor.get("bbox")
        if not isinstance(page_no, int) or not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        try:
            key = (page_no, float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "page_no": page_no,
                "page_number": int(anchor.get("page_number", page_no + 1)),
                "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
            }
        )
    return out


def _dedupe_source_refs_legacy(refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """去重 source_refs，支持 PDF 坐标型（有 bbox）和非 PDF 行定位型（无 bbox 但有 element_index）。"""
    seen_with_bbox: set[Tuple[int, int, float, float, float, float]] = set()
    seen_no_bbox: set[Tuple[int, int]] = set()
    out: List[Dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        page_no = ref.get("page_no")
        element_index = ref.get("element_index")
        bbox = ref.get("bbox")
        if not isinstance(page_no, int) or not isinstance(element_index, int):
            continue

        if isinstance(bbox, list) and len(bbox) == 4:
            # PDF 坐标型
            try:
                key = (
                    page_no,
                    element_index,
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                )
            except Exception:
                continue
            if key in seen_with_bbox:
                continue
            seen_with_bbox.add(key)
            out.append(
                {
                    "page_no": page_no,
                    "page_number": int(ref.get("page_number", page_no + 1)),
                    "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                    "element_index": element_index,
                    "element_type": str(ref.get("element_type") or "text"),
                }
            )
        else:
            # 非 PDF 行定位型（Excel 等）
            key_no_bbox = (page_no, element_index)
            if key_no_bbox in seen_no_bbox:
                continue
            seen_no_bbox.add(key_no_bbox)
            entry: Dict[str, Any] = {
                "page_no": page_no,
                "page_number": int(ref.get("page_number", page_no + 1)),
                "element_index": element_index,
            }
            if ref.get("element_type") is not None:
                entry["element_type"] = str(ref["element_type"])
            out.append(entry)
    return out


# 新协议实现：覆盖上方旧版 source_refs 归一化与去重逻辑。
def _normalize_source_ref(ref: Any) -> Optional[Dict[str, Any]]:
    """统一来源引用结构，支持 PDF 坐标定位和 Excel 行定位。"""
    if not isinstance(ref, dict):
        return None

    ref_type = str(ref.get("ref_type") or "").strip().lower()
    if ref_type == "web_anchor":
        url = str(ref.get("url") or "").strip()
        canonical_url = str(ref.get("canonical_url") or url).strip()
        dom_index = ref.get("dom_index")
        if not url or not isinstance(dom_index, int):
            return None
        heading_path = ref.get("heading_path")
        normalized_web_ref: Dict[str, Any] = {
            "ref_type": "web_anchor",
            "url": url,
            "canonical_url": canonical_url,
            "dom_index": dom_index,
            "anchor_text": str(ref.get("anchor_text") or "").strip(),
        }
        if isinstance(heading_path, list):
            normalized_web_ref["heading_path"] = [str(item).strip() for item in heading_path if str(item).strip()]
        return normalized_web_ref

    if ref_type == "excel_row":
        sheet_name = str(ref.get("sheet_name") or "").strip()
        row_index = ref.get("row_index")
        element_index = ref.get("element_index")
        if not sheet_name or not isinstance(row_index, int) or not isinstance(element_index, int):
            return None

        normalized_excel_ref: Dict[str, Any] = {
            "ref_type": "excel_row",
            "sheet_name": sheet_name,
            "row_index": row_index,
            "element_index": element_index,
        }
        if ref.get("element_type") is not None:
            normalized_excel_ref["element_type"] = str(ref["element_type"])
        field_names = ref.get("field_names")
        if isinstance(field_names, list):
            normalized_excel_ref["field_names"] = [str(item) for item in field_names if str(item).strip()]
        return normalized_excel_ref

    page_no = ref.get("page_no")
    page_number = ref.get("page_number")
    if page_number is None and isinstance(page_no, int):
        page_number = page_no + 1
    if page_no is None and isinstance(page_number, int):
        page_no = page_number - 1

    if not isinstance(page_no, int) or not isinstance(page_number, int):
        return None

    bbox = ref.get("bbox")
    element_index = ref.get("element_index")

    if isinstance(bbox, list) and len(bbox) == 4:
        try:
            norm_bbox = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
        except Exception:
            return None
        if norm_bbox[2] <= norm_bbox[0] or norm_bbox[3] <= norm_bbox[1]:
            return None
        normalized_pdf_ref: Dict[str, Any] = {
            "ref_type": "pdf_bbox",
            "page_no": page_no,
            "page_number": page_number,
            "bbox": norm_bbox,
        }
        if isinstance(element_index, int):
            normalized_pdf_ref["element_index"] = element_index
        if ref.get("element_type") is not None:
            normalized_pdf_ref["element_type"] = str(ref["element_type"])
        return normalized_pdf_ref

    if isinstance(element_index, int):
        normalized_legacy_ref: Dict[str, Any] = {
            "ref_type": "legacy_element",
            "page_no": page_no,
            "page_number": page_number,
            "element_index": element_index,
        }
        if ref.get("element_type") is not None:
            normalized_legacy_ref["element_type"] = str(ref["element_type"])
        return normalized_legacy_ref

    return None


def _dedupe_source_refs(refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """去重 source_refs，按引用类型分别保持稳定键。"""
    seen_pdf: set[Tuple[int, int, float, float, float, float]] = set()
    seen_excel: set[Tuple[str, int, int]] = set()
    seen_legacy: set[Tuple[int, int]] = set()
    seen_web: set[Tuple[str, str, int]] = set()
    out: List[Dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue

        ref_type = str(ref.get("ref_type") or "").strip().lower()
        if ref_type == "web_anchor":
            url = str(ref.get("url") or "").strip()
            canonical_url = str(ref.get("canonical_url") or url).strip()
            dom_index = ref.get("dom_index")
            if not url or not isinstance(dom_index, int):
                continue
            web_key = (url, canonical_url, dom_index)
            if web_key in seen_web:
                continue
            seen_web.add(web_key)
            entry: Dict[str, Any] = {
                "ref_type": "web_anchor",
                "url": url,
                "canonical_url": canonical_url,
                "dom_index": dom_index,
                "anchor_text": str(ref.get("anchor_text") or "").strip(),
            }
            heading_path = ref.get("heading_path")
            if isinstance(heading_path, list):
                entry["heading_path"] = [str(item).strip() for item in heading_path if str(item).strip()]
            out.append(entry)
            continue

        if ref_type == "excel_row":
            sheet_name = str(ref.get("sheet_name") or "").strip()
            row_index = ref.get("row_index")
            element_index = ref.get("element_index")
            if not sheet_name or not isinstance(row_index, int) or not isinstance(element_index, int):
                continue
            key_excel = (sheet_name, row_index, element_index)
            if key_excel in seen_excel:
                continue
            seen_excel.add(key_excel)
            excel_entry: Dict[str, Any] = {
                "ref_type": "excel_row",
                "sheet_name": sheet_name,
                "row_index": row_index,
                "element_index": element_index,
            }
            if ref.get("element_type") is not None:
                excel_entry["element_type"] = str(ref["element_type"])
            field_names = ref.get("field_names")
            if isinstance(field_names, list):
                excel_entry["field_names"] = [str(item) for item in field_names if str(item).strip()]
            out.append(excel_entry)
            continue

        page_no = ref.get("page_no")
        element_index = ref.get("element_index")
        bbox = ref.get("bbox")
        if not isinstance(page_no, int) or not isinstance(element_index, int):
            continue

        if isinstance(bbox, list) and len(bbox) == 4:
            try:
                key = (
                    page_no,
                    element_index,
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                )
            except Exception:
                continue
            if key in seen_pdf:
                continue
            seen_pdf.add(key)
            out.append(
                {
                    "ref_type": "pdf_bbox",
                    "page_no": page_no,
                    "page_number": int(ref.get("page_number", page_no + 1)),
                    "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                    "element_index": element_index,
                    "element_type": str(ref.get("element_type") or "text"),
                }
            )
            continue

        key_legacy = (page_no, element_index)
        if key_legacy in seen_legacy:
            continue
        seen_legacy.add(key_legacy)
        entry = {
            "ref_type": "legacy_element",
            "page_no": page_no,
            "page_number": int(ref.get("page_number", page_no + 1)),
            "element_index": element_index,
        }
        if ref.get("element_type") is not None:
            entry["element_type"] = str(ref["element_type"])
        out.append(entry)
    return out


def _apply_pdf_chunk_source_data(
    fc: Dict[str, Any],
    parse_metadata: Dict[str, Any],
    elements: List[Dict[str, Any]],
    indices: List[int],
    source_anchor_engine: str,
    source_anchor_confidence: str,
) -> None:
    indices = _dedupe_int_list(indices)
    if not indices:
        return

    anchors = _dedupe_anchors(_anchors_from_element_indices(elements, indices))
    refs = _dedupe_source_refs(_build_source_refs_from_element_indices(elements, indices))
    if not anchors:
        return

    fc_meta = fc.get("metadata") or {}
    if not isinstance(fc_meta, dict):
        fc_meta = {}

    fc_meta["source_element_indices"] = indices
    fc_meta["source_anchors"] = anchors
    fc_meta["source_anchor_engine"] = source_anchor_engine
    fc_meta["source_anchor_confidence"] = source_anchor_confidence
    fc_meta.setdefault("source_anchor_coordinate_system", "top_left_pdf_points")
    fc_meta["page_numbers"] = _page_numbers_from_anchors(anchors)
    if fc_meta["page_numbers"]:
        fc_meta["primary_page_number"] = fc_meta["page_numbers"][0]

    fc["metadata"] = fc_meta
    fc["content_blocks"] = _build_standard_chunk_content_blocks(
        fc,
        str(fc.get("text") or ""),
        str(fc.get("type") or ChunkType.TEXT.value),
        {"source_refs": refs},
        parse_metadata,
    )


def _collect_descendant_element_indices(
    chunk: Dict[str, Any],
    node_map: Dict[str, Dict[str, Any]],
    visited: Optional[set[str]] = None,
) -> List[int]:
    chunk_meta = chunk.get("metadata") or {}
    if not isinstance(chunk_meta, dict):
        return []

    node_id = chunk_meta.get("node_id")
    if not isinstance(node_id, str) or not node_id:
        node_id = None

    local_visited = visited or set()
    if node_id:
        if node_id in local_visited:
            return []
        local_visited.add(node_id)

    indices: List[int] = []
    raw_indices = chunk_meta.get("source_element_indices")
    if isinstance(raw_indices, list):
        indices.extend([v for v in raw_indices if isinstance(v, int)])

    child_ids = chunk_meta.get("child_ids")
    if isinstance(child_ids, list):
        for child_id in child_ids:
            if not isinstance(child_id, str):
                continue
            child_chunk = node_map.get(child_id)
            if not isinstance(child_chunk, dict):
                continue
            indices.extend(_collect_descendant_element_indices(child_chunk, node_map, local_visited))

    return _dedupe_int_list(indices)


def _find_nearest_ancestor_source_indices(
    chunk: Dict[str, Any],
    node_map: Dict[str, Dict[str, Any]],
) -> List[int]:
    chunk_meta = chunk.get("metadata") or {}
    if not isinstance(chunk_meta, dict):
        return []

    visited: set[str] = set()
    parent_id = chunk_meta.get("parent_id")
    while isinstance(parent_id, str) and parent_id:
        if parent_id in visited:
            break
        visited.add(parent_id)
        parent_chunk = node_map.get(parent_id)
        if not isinstance(parent_chunk, dict):
            break
        parent_meta = parent_chunk.get("metadata") or {}
        if not isinstance(parent_meta, dict):
            break
        indices = parent_meta.get("source_element_indices")
        if isinstance(indices, list) and indices:
            return _dedupe_int_list(indices)
        parent_id = parent_meta.get("parent_id")
    return []


def _find_origin_source_indices(
    chunk: Dict[str, Any],
    node_map: Dict[str, Dict[str, Any]],
) -> List[int]:
    chunk_meta = chunk.get("metadata") or {}
    if not isinstance(chunk_meta, dict):
        return []

    origin_node_id = chunk_meta.get("origin_node_id")
    if not isinstance(origin_node_id, str) or not origin_node_id:
        return []

    origin_chunk = node_map.get(origin_node_id)
    if not isinstance(origin_chunk, dict):
        return []

    origin_meta = origin_chunk.get("metadata") or {}
    if not isinstance(origin_meta, dict):
        return []

    indices = origin_meta.get("source_element_indices")
    if isinstance(indices, list) and indices:
        return _dedupe_int_list(indices)

    return []


def _get_element_by_index(parse_metadata: Dict[str, Any], element_index: Any) -> Optional[Dict[str, Any]]:
    elements = parse_metadata.get("elements")
    if not isinstance(elements, list) or not isinstance(element_index, int):
        return None
    if element_index < 0 or element_index >= len(elements):
        return None
    item = elements[element_index]
    return item if isinstance(item, dict) else None


def _build_image_analysis_from_element(element: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    element_metadata: Dict[str, Any] = (
        dict(element.get("metadata") or {})
        if isinstance(element, dict) and isinstance(element.get("metadata"), dict)
        else {}
    )
    raw_caption = element_metadata.get("image_caption")
    caption = [str(item).strip() for item in raw_caption if str(item).strip()] if isinstance(raw_caption, list) else []
    ocr_text = str(element_metadata.get("ocr_text") or "").strip()
    vision_text = str(element_metadata.get("vision_text") or "").strip()

    status = "none"
    if ocr_text and vision_text:
        status = "ocr_vision"
    elif vision_text:
        status = "vision"
    elif ocr_text:
        status = "ocr"
    elif caption:
        status = "caption"

    return {
        "status": status,
        "caption": caption,
        "ocr_text": ocr_text or None,
        "vision_text": vision_text or None,
    }


def _hydrate_image_block_protocol(
    block: Dict[str, Any],
    parse_metadata: Dict[str, Any],
    chunk_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    if str(block.get("type") or "").lower() != "image":
        return block

    raw_refs = block.get("source_refs")
    refs: List[Any] = list(raw_refs) if isinstance(raw_refs, list) else []
    element_index = None
    for ref in refs:
        if isinstance(ref, dict) and isinstance(ref.get("element_index"), int):
            element_index = int(ref["element_index"])
            break

    if element_index is None:
        source_indices: Any = chunk_metadata.get("source_element_indices")
        if isinstance(source_indices, list) and source_indices and isinstance(source_indices[0], int):
            element_index = int(source_indices[0])

    element = _get_element_by_index(parse_metadata, element_index)
    element_metadata: Dict[str, Any] = (
        dict(element.get("metadata") or {})
        if isinstance(element, dict) and isinstance(element.get("metadata"), dict)
        else {}
    )
    origin: Dict[str, Any] = dict(block.get("origin") or {}) if isinstance(block.get("origin"), dict) else {}
    analysis: Dict[str, Any] = dict(block.get("analysis") or {}) if isinstance(block.get("analysis"), dict) else {}
    hydrated_analysis = _build_image_analysis_from_element(element)
    status = str(analysis.get("status") or hydrated_analysis["status"]).strip().lower()
    if status not in IMAGE_ANALYSIS_STATUSES:
        status = hydrated_analysis["status"]

    block["origin"] = {
        "parser": origin.get("parser") if origin.get("parser") is not None else (str(element_metadata.get("source") or "").strip() or None),
        "modality": origin.get("modality") if origin.get("modality") is not None else (str(element_metadata.get("modality") or "").strip() or None),
    }
    block["analysis"] = {
        "status": status,
        "caption": analysis.get("caption") if isinstance(analysis.get("caption"), list) and analysis.get("caption") else hydrated_analysis["caption"],
        "ocr_text": analysis.get("ocr_text") if analysis.get("ocr_text") else hydrated_analysis["ocr_text"],
        "vision_text": analysis.get("vision_text") if analysis.get("vision_text") else hydrated_analysis["vision_text"],
    }
    return block


def _build_standard_chunk_content_blocks(
    fc: Dict[str, Any],
    content: str,
    chunk_type: str,
    chunk_metadata: Dict[str, Any],
    parse_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """统一构造结构化内容块，确保所有分块策略都输出相同协议。"""
    parse_metadata = parse_metadata or {}
    raw_fallback_refs = chunk_metadata.get("source_refs")
    fallback_refs: List[Any] = list(raw_fallback_refs) if isinstance(raw_fallback_refs, list) else []
    normalized_fallback_refs = [ref for ref in (_normalize_source_ref(item) for item in fallback_refs) if ref]
    content_blocks = fc.get("content_blocks")
    if isinstance(content_blocks, list) and content_blocks:
        normalized_blocks: List[Dict[str, Any]] = []
        for block_idx, block in enumerate(content_blocks, start=1):
            if not isinstance(block, dict):
                continue
            normalized_block = dict(block)
            normalized_block.setdefault("block_id", f"b{block_idx}")
            normalized_block["type"] = str(normalized_block.get("type") or chunk_type or "text").lower()
            refs = normalized_block.get("source_refs")
            if isinstance(refs, list):
                normalized_refs = [ref for ref in (_normalize_source_ref(item) for item in refs) if ref]
                normalized_block["source_refs"] = normalized_refs or list(normalized_fallback_refs)
            else:
                normalized_block["source_refs"] = list(normalized_fallback_refs)
            normalized_block = _hydrate_image_block_protocol(normalized_block, parse_metadata, chunk_metadata)
            normalized_blocks.append(normalized_block)
        if normalized_blocks:
            return normalized_blocks

    block_type = str(chunk_type or "text").lower()
    default_block: Dict[str, Any] = {
        "block_id": "b1",
        "type": block_type,
        "source_refs": [],
    }
    if block_type == "image":
        default_block["url"] = content
    else:
        default_block["text"] = content

    if normalized_fallback_refs:
        default_block["source_refs"] = list(normalized_fallback_refs)
    default_block = _hydrate_image_block_protocol(default_block, parse_metadata, chunk_metadata)

    return [default_block]


def _build_chunk_content_blocks(fc: Dict[str, Any], content: str, chunk_type: str) -> List[Dict[str, Any]]:
    """统一构造结构化内容块，避免 chunks.content_blocks 长期为空。"""
    content_blocks = fc.get("content_blocks")
    if isinstance(content_blocks, list) and content_blocks:
        return content_blocks
    return [
        {
            "text": content,
            "type": chunk_type,
        }
    ]


def _resolve_chunk_structure_version(fc: Dict[str, Any]) -> int:
    """解析结构版本，默认回退到 v1。"""
    value = fc.get("structure_version")
    if isinstance(value, int) and value > 0:
        return value
    return 1


def _resolve_chunk_parent_id(fc: Dict[str, Any]) -> Optional[int]:
    """仅在 parent_id 为整数主键时落库，避免把 node_id 误写入 BIGINT。"""
    value = fc.get("parent_id")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _resolve_chunk_path(fc: Dict[str, Any], chunk_metadata: Dict[str, Any]) -> Optional[str]:
    """优先读取显式 path，未提供则不强行推导。"""
    value = fc.get("path")
    if isinstance(value, str) and value.strip():
        return value.strip()
    meta_value = chunk_metadata.get("path")
    if isinstance(meta_value, str) and meta_value.strip():
        return meta_value.strip()
    return None


def _normalize_text_for_match(text: str) -> str:
    """Normalize text for loose matching between chunk text and parser elements."""
    if not text:
        return ""
    import re
    text = text.lower()
    # Keep CJK, latin letters and digits, collapse everything else into spaces.
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _looks_like_short_cjk_anchor(text: str) -> bool:
    """识别类似“化学”“数学”这类很短但有定位价值的中文标题。"""
    if not text:
        return False
    cjk_chars = [ch for ch in text if "\u4e00" <= ch <= "\u9fff"]
    return len(cjk_chars) >= 2


def _token_overlap_score(text_a: str, text_b: str) -> float:
    if not text_a or not text_b:
        return 0.0
    a_tokens = set(text_a.split())
    b_tokens = set(text_b.split())
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    denom = min(len(a_tokens), len(b_tokens))
    if denom <= 0:
        return 0.0
    return inter / denom


def _extract_match_lines(chunk_text: str, max_lines: int = 48) -> List[str]:
    lines: List[str] = []
    for raw in (chunk_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        # Skip most markdown syntax-only lines.
        if all(ch in "#`*-|:> " for ch in line):
            continue
        normalized = _normalize_text_for_match(line)
        # 中文短标题通常只有 2-4 个字，不能像普通正文一样直接过滤掉。
        if len(normalized) < 6 and not _looks_like_short_cjk_anchor(normalized):
            continue
        lines.append(normalized)
        if len(lines) >= max_lines:
            break
    return lines


def _build_pdf_text_elements(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    elements = metadata.get("elements")
    if not isinstance(elements, list):
        return []

    out: List[Dict[str, Any]] = []
    for idx, el in enumerate(elements):
        if not isinstance(el, dict):
            continue
        page_no = el.get("page_no")
        bbox = el.get("bbox")
        content = el.get("content")
        if not isinstance(page_no, int):
            continue
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        if not isinstance(content, str) or not content.strip():
            continue

        normalized = _normalize_text_for_match(content)
        if not normalized:
            continue

        try:
            x0, y0, x1, y1 = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
        except Exception:
            continue
        if x1 <= x0 or y1 <= y0:
            continue

        out.append(
            {
                "idx": idx,
                "norm": normalized,
                "page_no": page_no,
                "bbox": [x0, y0, x1, y1],
            }
        )
    return out


def _find_chunk_element_indices(
    chunk_text: str,
    elements: List[Dict[str, Any]],
    start_idx: int,
) -> Tuple[List[int], int]:
    if not elements:
        return [], start_idx

    matched: List[int] = []
    cursor = max(0, start_idx)
    lines = _extract_match_lines(chunk_text)

    # Pass 1: ordered line-based matching, robust against chunk merge/split.
    for line in lines:
        max_j = min(len(elements), cursor + 260)
        found: Optional[int] = None
        for j in range(cursor, max_j):
            elem_norm = elements[j]["norm"]
            if line in elem_norm or elem_norm in line:
                found = j
                break
            if _token_overlap_score(line, elem_norm) >= 0.72:
                found = j
                break
        if found is not None:
            matched.append(found)
            cursor = found + 1

    if matched:
        unique = sorted(set(matched))
        return unique, min(len(elements), unique[-1] + 1)

    # Pass 2 fallback: best single element near cursor.
    norm_chunk = _normalize_text_for_match(chunk_text)
    if not norm_chunk:
        return [], start_idx

    best_j: Optional[int] = None
    best_score = 0.0
    max_j = min(len(elements), cursor + 360)
    for j in range(cursor, max_j):
        elem_norm = elements[j]["norm"]
        score = _token_overlap_score(norm_chunk, elem_norm)
        if score > best_score:
            best_score = score
            best_j = j
    if best_j is None or best_score < 0.30:
        return [], start_idx
    return [best_j], min(len(elements), best_j + 1)


def _find_chunk_element_indices_within_candidates(
    chunk_text: str,
    elements: List[Dict[str, Any]],
    candidate_indices: List[int],
    start_idx: int,
) -> Tuple[List[int], int]:
    """在限定候选元素范围内做顺序匹配，避免拆分子块串到相邻题目。"""
    normalized_candidates = _dedupe_int_list(candidate_indices)
    if not normalized_candidates:
        return [], start_idx

    candidate_elements: List[Dict[str, Any]] = []
    for idx in normalized_candidates:
        if 0 <= idx < len(elements):
            candidate_elements.append(elements[idx])

    if not candidate_elements:
        return [], start_idx

    local_indices, next_start = _find_chunk_element_indices(chunk_text, candidate_elements, start_idx)
    if not local_indices:
        return [], start_idx

    mapped_indices = [int(candidate_elements[local_idx]["idx"]) for local_idx in local_indices]
    return _dedupe_int_list(mapped_indices), next_start


def _anchors_from_element_indices(
    elements: List[Dict[str, Any]],
    indices: List[int],
) -> List[Dict[str, Any]]:
    if not indices:
        return []
    per_page: Dict[int, List[List[float]]] = {}
    for i in indices:
        if i < 0 or i >= len(elements):
            continue
        item = elements[i]
        page_no = int(item["page_no"])
        per_page.setdefault(page_no, []).append(item["bbox"])

    anchors: List[Dict[str, Any]] = []
    for page_no in sorted(per_page.keys()):
        boxes = per_page[page_no]
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y1 = max(b[3] for b in boxes)
        anchors.append(
            {
                "page_no": page_no,
                "page_number": page_no + 1,
                "bbox": [x0, y0, x1, y1],
            }
        )
    return anchors


def _page_numbers_from_anchors(anchors: List[Dict[str, Any]]) -> List[int]:
    page_numbers: List[int] = []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        page_number = anchor.get("page_number")
        if isinstance(page_number, int) and page_number not in page_numbers:
            page_numbers.append(page_number)
    return page_numbers


def _attach_pdf_source_anchors(
    final_chunks: List[Dict[str, Any]],
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Attach source anchors to chunk metadata without altering chunking logic.
    Works as a post-process and is safe for markdown split/merge output.
    """
    elements = _build_pdf_text_elements(metadata)
    if not elements:
        return final_chunks

    node_map: Dict[str, Dict[str, Any]] = {}
    direct_match_chunks: List[Dict[str, Any]] = []
    split_descendant_chunks: List[Dict[str, Any]] = []
    aggregate_chunks: List[Dict[str, Any]] = []

    for fc in final_chunks:
        if not isinstance(fc, dict):
            continue
        fc_meta = fc.get("metadata") or {}
        if not isinstance(fc_meta, dict):
            fc_meta = {}
            fc["metadata"] = fc_meta

        node_id = fc_meta.get("node_id")
        if isinstance(node_id, str) and node_id:
            node_map[node_id] = fc

        has_children = bool(fc_meta.get("child_ids"))
        is_split_descendant = bool(fc_meta.get("is_split")) and isinstance(fc_meta.get("parent_id"), str)
        has_explicit_source = isinstance(fc_meta.get("source_element_indices"), list) and bool(fc_meta.get("source_element_indices"))

        if has_children:
            aggregate_chunks.append(fc)

        if has_explicit_source:
            _apply_pdf_chunk_source_data(
                fc,
                metadata,
                elements,
                list(fc_meta.get("source_element_indices") or []),
                str(fc_meta.get("source_anchor_engine") or "pdf_elements_v1"),
                str(fc_meta.get("source_anchor_confidence") or "high"),
            )
            continue

        if is_split_descendant:
            split_descendant_chunks.append(fc)
            continue

        if not has_children or fc_meta.get("is_independent_element"):
            direct_match_chunks.append(fc)

    cursor = 0
    split_origin_cursors: Dict[str, int] = {}
    for fc in direct_match_chunks:
        text = fc.get("text") or ""
        indices, cursor = _find_chunk_element_indices(text, elements, cursor)
        if indices:
            _apply_pdf_chunk_source_data(
                fc,
                metadata,
                elements,
                indices,
                "pdf_elements_v1",
                "high" if len(indices) > 1 else "medium",
            )

    # 拆分出的子块若无法单独匹配，直接继承原始大块的位置，保证继续拆分后不丢锚点。
    for fc in split_descendant_chunks:
        fc_meta = fc.get("metadata") or {}
        if not isinstance(fc_meta, dict):
            continue
        existing_indices = fc_meta.get("source_element_indices")
        if isinstance(existing_indices, list) and existing_indices:
            _apply_pdf_chunk_source_data(
                fc,
                metadata,
                elements,
                list(existing_indices),
                str(fc_meta.get("source_anchor_engine") or "pdf_elements_inherited_v1"),
                str(fc_meta.get("source_anchor_confidence") or "high"),
            )
            continue

        inherited_indices = _find_origin_source_indices(fc, node_map)
        if not inherited_indices:
            inherited_indices = _find_nearest_ancestor_source_indices(fc, node_map)
        matched_indices: List[int] = []
        if inherited_indices:
            match_scope_key = str(
                fc_meta.get("origin_node_id")
                or fc_meta.get("parent_id")
                or fc_meta.get("node_id")
                or ""
            )
            local_cursor = split_origin_cursors.get(match_scope_key, 0)
            matched_indices, next_cursor = _find_chunk_element_indices_within_candidates(
                str(fc.get("text") or ""),
                elements,
                inherited_indices,
                local_cursor,
            )
            if matched_indices:
                split_origin_cursors[match_scope_key] = next_cursor
                _apply_pdf_chunk_source_data(
                    fc,
                    metadata,
                    elements,
                    matched_indices,
                    "pdf_elements_split_match_v1",
                    "high" if len(matched_indices) > 1 else "medium",
                )
                continue
        if inherited_indices:
            _apply_pdf_chunk_source_data(
                fc,
                metadata,
                elements,
                inherited_indices,
                "pdf_elements_inherited_v1",
                "high",
            )

    # 根块/父块聚合后代位置，避免上层块和叶子块之间互相“抢”游标。
    for fc in reversed(aggregate_chunks):
        indices = _collect_descendant_element_indices(fc, node_map)
        if indices:
            refined_indices, _ = _find_chunk_element_indices_within_candidates(
                str(fc.get("text") or ""),
                elements,
                indices,
                0,
            )
            if refined_indices:
                indices = refined_indices
            _apply_pdf_chunk_source_data(
                fc,
                metadata,
                elements,
                indices,
                "pdf_elements_aggregate_v1",
                "high" if len(indices) > 1 else "medium",
            )

    # 兜底：仍缺失位置的块，继承最近祖先的位置，保证协议字段稳定存在。
    for fc in final_chunks:
        if not isinstance(fc, dict):
            continue
        fc_meta = fc.get("metadata") or {}
        if not isinstance(fc_meta, dict):
            continue
        existing_indices = fc_meta.get("source_element_indices")
        if isinstance(existing_indices, list) and existing_indices:
            continue
        inherited_indices = _find_nearest_ancestor_source_indices(fc, node_map)
        if inherited_indices:
            _apply_pdf_chunk_source_data(
                fc,
                metadata,
                elements,
                inherited_indices,
                "pdf_elements_inherited_v1",
                "medium",
            )

    return final_chunks


def _slim_chunk_metadata(
    metadata: Dict[str, Any],
    chunk_metadata: Optional[Dict[str, Any]],
    chunk_strategy: str,
) -> Dict[str, Any]:
    """只保留 chunk 局部元数据，文档级大字段统一下沉到 runtime。"""
    slim: Dict[str, Any] = {}
    source = chunk_metadata if isinstance(chunk_metadata, dict) else {}

    for key in CHUNK_METADATA_KEEP_KEYS:
        if key in source:
            slim[key] = source[key]

    parser_name = source.get("parser") or metadata.get("parser")
    parse_method = source.get("parse_method") or metadata.get("parse_method")
    if parser_name:
        slim["parser"] = parser_name
    if parse_method:
        slim["parse_method"] = parse_method

    if "chunk_strategy" not in slim:
        slim["chunk_strategy"] = chunk_strategy

    page_numbers = source.get("page_numbers")
    if not isinstance(page_numbers, list) or not page_numbers:
        anchors = source.get("source_anchors")
        if isinstance(anchors, list) and anchors:
            page_numbers = _page_numbers_from_anchors(anchors)
    if isinstance(page_numbers, list) and page_numbers:
        slim["page_numbers"] = [int(v) for v in page_numbers if isinstance(v, int)]
        if slim["page_numbers"]:
            primary_page_number = source.get("primary_page_number")
            if isinstance(primary_page_number, int):
                slim["primary_page_number"] = primary_page_number
            else:
                slim["primary_page_number"] = slim["page_numbers"][0]

    return slim


@celery_app.task(
    name="rag.ingestion.tasks.chunk_document_task",
    bind=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=360,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
)
def chunk_document_task(
    self,
    kb_doc_id: str,
    raw_text: str,
    metadata: Dict[str, Any],
    chunk_strategy: str = "fixed_size",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    **kwargs
):
    """
    分块任务（整合状态管理）
    
    Args:
        kb_doc_id: 知识库文档 ID
        raw_text: 原始文本
        metadata: 文档元数据
        chunk_strategy: 分块策略
        chunk_size: 分块大小
        chunk_overlap: 分块重叠大小
    
    流程：
        1. 根据策略选择分块器
        2. 执行分块（CPU 密集，同步执行）
        3. 保存分块结果到 Chunks 表
        4. 触发增强任务
        5. 更新状态
    """
    logger.info(f"[ChunkTask] 开始分块: {kb_doc_id}, 策略: {chunk_strategy}")
    
    # 使用 asyncio.run 运行异步代码
    async def _run_chunk():
        # 为当前 event loop 创建独立的数据库引擎和 Redis 客户端
        task_engine, task_sm = create_task_session_maker()
        redis_client = create_task_redis_client()
        try:
            from .common import document_lock
            async with document_lock(UUID(kb_doc_id), redis_client):
                await _do_chunk_document(
                    UUID(kb_doc_id),
                    raw_text,
                    metadata,
                    chunk_strategy,
                    chunk_size,
                    chunk_overlap,
                    redis_client,
                    task_sm,
                    **kwargs
                )
        finally:
            await close_task_redis_client(redis_client)
            await close_task_db_engine(task_engine)
    
    try:
        asyncio.run(_run_chunk())
        logger.info(f"[ChunkTask] 分块完成: {kb_doc_id}")
        return {"status": "success", "kb_doc_id": kb_doc_id}
        
    except Exception as e:
        logger.error(f"[ChunkTask] 分块失败: {kb_doc_id}, 错误: {str(e)}", exc_info=True)
        # 重试次数达上限则标记文档失败，避免一直处于 processing
        if self.request.retries >= self.max_retries:
            logger.error(f"[ChunkTask] 分块重试次数已达上限: kb_doc_id={kb_doc_id}")

            async def _mark_failed():
                # mark_failed 只做 DB 操作，独立引擎避免跨 loop 问题
                me, ms = create_task_session_maker()
                try:
                    async with ms() as session:
                        stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id == UUID(kb_doc_id))
                        result = await session.execute(stmt)
                        kb_doc = result.scalar_one_or_none()
                        if kb_doc:
                            await mark_failed(session, kb_doc, f"分块失败（已重试 {self.max_retries} 次）: {str(e)}")
                            await session.commit()
                finally:
                    await close_task_db_engine(me)

            try:
                asyncio.run(_mark_failed())
            except Exception as mark_err:
                logger.error(f"[ChunkTask] 标记失败状态也失败了: {mark_err}")
            return {"status": "failed", "kb_doc_id": kb_doc_id, "error": str(e)}
        # Redis/网络超时给予更长 countdown，便于服务恢复后重试
        is_timeout = isinstance(e, (redis_exc.TimeoutError, redis_exc.ConnectionError, TimeoutError))
        countdown = min(60, 10 * (2 ** self.request.retries)) if is_timeout else (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)


async def _do_chunk_document(
    kb_doc_id: UUID,
    raw_text: str,
    metadata: Dict[str, Any],
    chunk_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    redis_client,
    session_maker,
    _skip_delete_old_chunks: bool = False,
    **kwargs
):
    """实际的分块逻辑

    Args:
        kb_doc_id: 文档 ID
        raw_text: 原始文本
        metadata: 元数据
        chunk_strategy: 分块策略
        chunk_size: 分块大小
        chunk_overlap: 重叠大小
        redis_client: Redis 客户端（必须在当前 event loop 中创建）
        session_maker: 数据库 session 工厂（必须在当前 event loop 中创建）
        _skip_delete_old_chunks: 是否跳过清理旧 chunk（大表分片非首分片设为 True，追加模式）
    """
    
    async with session_maker() as session:
        try:
            # 1. 获取文档信息
            stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id == kb_doc_id)
            result = await session.execute(stmt)
            kb_doc = result.scalar_one_or_none()
            
            if not kb_doc:
                logger.error(f"[ChunkTask] KnowledgeBaseDocument {kb_doc_id} 不存在")
                return

            kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_doc.kb_id)
            kb_result = await session.execute(kb_stmt)
            kb = kb_result.scalar_one_or_none()
            
            # 检查取消标志
            if await check_cancel(redis_client, kb_doc_id):
                logger.info(f"[ChunkTask] 文档 {kb_doc_id} 收到取消请求，停止分块")
                await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                return
            
            # 2. 更新状态
            set_runtime_stage(kb_doc, "chunking")
            await add_log(session, kb_doc, "CHUNK", f"执行分块策略 (size={chunk_size})...", "processing")
            await sync_latest_attempt_snapshot(
                session,
                kb_doc,
                runtime_stage="chunking",
                chunk_strategy=chunk_strategy,
                config_snapshot=build_effective_config(
                    kb_doc,
                    {
                        "chunk_strategy": chunk_strategy,
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                    },
                    kb=kb,
                ),
                stats={"text_length": len(raw_text)},
            )
            await upsert_kb_doc_runtime(
                session,
                kb_doc,
                pipeline_task_id=kb_doc.task_id,
                effective_config=build_effective_config(
                    kb_doc,
                    {
                        "chunk_strategy": chunk_strategy,
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                    },
                    kb=kb,
                ),
                stats={"text_length": len(raw_text)},
            )
            await session.commit()
            
            # 3. 创建分块器
            if chunk_strategy == "qa":
                metadata = {
                    **(metadata or {}),
                    "qa_items": await _load_qa_items_for_chunking(session, kb_doc_id),
                }
            chunker = ChunkerFactory.create_chunker(
                ChunkStrategy(chunk_strategy),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                **kwargs
            )
            logger.info(
                "[ChunkTask] 创建分块器: kb_doc_id=%s, chunker=%s, strategy=%s, chunk_size=%s, "
                "chunk_overlap=%s, extra_keys=%s",
                kb_doc_id,
                chunker.__class__.__name__,
                chunk_strategy,
                chunk_size,
                chunk_overlap,
                sorted(kwargs.keys()),
            )
            await add_log(
                session,
                kb_doc,
                "CHUNK",
                (
                    f"已创建分块器: {chunker.__class__.__name__}, strategy={chunk_strategy}, "
                    f"chunk_size={chunk_size}, overlap={chunk_overlap}"
                ),
                "processing",
            )
            
            # 4. 执行分块（同步执行）
            final_chunks = chunker.chunk(raw_text, metadata)
            final_chunks = _attach_pdf_source_anchors(final_chunks, metadata)
            
            logger.info(f"[ChunkTask] 分块完成: {len(final_chunks)} 个分块")
            
            # 🔧 分块完成后再次检查取消标志（分块可能耗时较长）
            if await check_cancel(redis_client, kb_doc_id):
                logger.info(f"[ChunkTask] 文档 {kb_doc_id} 分块后收到取消请求，停止处理")
                await mark_cancelled(session, kb_doc, redis_client, kb_doc_id)
                return
            
            # 5. 保存分块结果到 Chunks 表
            await add_log(session, kb_doc, "CHUNK", f"正在持久化 {len(final_chunks)} 个切片...", "processing")
            
            # 清理旧切片（防御性删除：虽然 API 层已删除，但这里再次确保清理）
            # 大表分片模式下，非首分片跳过此步骤（追加写入，避免误删已写入的分片）
            if not _skip_delete_old_chunks:
                existing_chunk_result = await session.execute(
                    select(Chunk.id).where(Chunk.kb_doc_id == kb_doc_id)
                )
                existing_chunk_ids = [int(chunk_id) for chunk_id in existing_chunk_result.scalars().all()]
                await delete_search_projections_for_chunk_ids(session, existing_chunk_ids)
                del_stmt = delete(Chunk).where(Chunk.kb_doc_id == kb_doc_id)
                await session.execute(del_stmt)
            
            # 批量插入
            from rag.utils.token_utils import count_tokens
            new_chunks = []
            for idx, fc in enumerate(final_chunks):
                content = fc["text"]
                chunk_type = fc.get("type", ChunkType.TEXT.value)
                chunk_metadata = _slim_chunk_metadata(
                    metadata,
                    fc.get("metadata", {}),
                    chunk_strategy,
                )
                content_blocks = _build_standard_chunk_content_blocks(
                    fc,
                    content,
                    chunk_type,
                    chunk_metadata,
                    metadata,
                )
                structure_version = _resolve_chunk_structure_version(fc)
                chunk_parent_id = _resolve_chunk_parent_id(fc)
                chunk_path = _resolve_chunk_path(fc, chunk_metadata)
                chunk_content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                chunk_source_type = _resolve_chunk_source_type(str(kb.type or "").strip(), chunk_metadata, metadata or {})
                chunk_group_id = _resolve_chunk_content_group_id(chunk_metadata)
                chunk = Chunk(
                    tenant_id=kb_doc.tenant_id,
                    kb_id=kb_doc.kb_id,
                    document_id=kb_doc.document_id,
                    kb_doc_id=kb_doc.id,
                    content=content,
                    original_content=None,
                    content_hash=chunk_content_hash,
                    content_blocks=content_blocks,
                    structure_version=structure_version,
                    token_count=count_tokens(content),
                    text_length=len(content),
                    chunk_type=chunk_type,
                    position=idx,
                    path=chunk_path,
                    parent_id=chunk_parent_id,
                    source_type=chunk_source_type,
                    content_group_id=chunk_group_id,
                    metadata_info=chunk_metadata,
                    status="success",
                    is_active=True,
                    display_enabled=True,
                    is_content_edited=False,
                )
                new_chunks.append(chunk)
            
            session.add_all(new_chunks)
            await session.flush()

            new_search_units = build_search_units_for_chunks(
                chunks=new_chunks,
                kb_type=str(kb.type or "").strip(),
                retrieval_config=dict(kb.retrieval_config or {}),
                kb_doc_summary=str(kb_doc.summary or "").strip() or None,
            )
            if new_search_units:
                session.add_all(new_search_units)
            
            # 6. 更新文档状态
            if _skip_delete_old_chunks:
                total_chunk_count = await session.scalar(
                    select(func.count()).select_from(Chunk).where(Chunk.kb_doc_id == kb_doc_id)
                )
                kb_doc.chunk_count = int(total_chunk_count or 0)
            else:
                kb_doc.chunk_count = len(final_chunks)
            kb_doc.updated_at = datetime.now()
            await add_log(session, kb_doc, "CHUNK", f"分块完成，生成 {len(final_chunks)} 个切片", "done")
            set_runtime_stage(kb_doc, "enhancing")
            await sync_latest_attempt_snapshot(
                session,
                kb_doc,
                runtime_stage="enhancing",
                chunk_strategy=chunk_strategy,
                stats={
                    "chunk_count": len(final_chunks),
                    "text_length": len(raw_text),
                },
            )
            await upsert_kb_doc_runtime(
                session,
                kb_doc,
                pipeline_task_id=kb_doc.task_id,
                effective_config=build_effective_config(
                    kb_doc,
                    {
                        "chunk_strategy": chunk_strategy,
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                    },
                    kb=kb,
                ),
                chunk_context={
                    "chunk_strategy": chunk_strategy,
                    "chunk_count": len(final_chunks),
                },
                stats={
                    "chunk_count": len(final_chunks),
                },
                error_detail={},
            )
            await session.commit()
            
            # 7. 获取 segment_ids（chunk 的 ID）
            segment_ids = [str(chunk.id) for chunk in new_chunks]
            
            # 8. 触发增强任务
            logger.info(f"[ChunkTask] 触发增强任务: {kb_doc_id}")
            from .enhance_task import enhance_chunks_task
            enhance_chunks_task.delay(str(kb_doc_id), segment_ids)
            
        except Exception as e:
            logger.exception(f"[ChunkTask] 分块失败: {kb_doc_id}, 错误: {str(e)}")
            await session.rollback()
            raise


# ============================================================
# Excel 表格模式大表分片调度
# ============================================================

def should_shard_excel_table(metadata: Dict[str, Any]) -> bool:
    """
    判断是否需要对 Excel 表格模式进行大表行窗口分片。

    当任意 Sheet 的数据行数超过 TABLE_BATCH_SIZE 时返回 True。
    """
    sheets_info = metadata.get("sheets", [])
    for sheet in sheets_info:
        row_count = sheet.get("row_count", 0)
        if row_count > TABLE_BATCH_SIZE:
            return True
    return False


def build_excel_table_shard_tasks(
    kb_doc_id: str,
    metadata: Dict[str, Any],
    chunk_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    将 Excel 表格模式大表拆分为多个分片任务描述。

    每个分片任务描述包含：
    {
        "row_from": int,       # 数据行起始（0-based）
        "row_to": int | None,  # 数据行结束（不含），None 表示读到末尾
        "emit_summary": bool,  # 是否为该 Sheet 生成 summary 根节点
        "clear_existing": bool,# 是否负责清理旧 chunk（仅首个任务）
        "sheet_name": str,     # 工作表名称
        "sheet_root_node_id": str,  # 该 Sheet 的稳定根节点 ID
    }

    调用方（如 parse_task 或上层 orchestrator）负责为每个分片下发独立的 chunk_document_task，
    并在 kwargs 中传入 {"row_from": ..., "row_to": ..., "is_first_shard": ...}。
    """
    shards: List[Dict[str, Any]] = []
    sheets_info = metadata.get("sheets", [])
    first_task = True

    for sheet in sheets_info:
        sheet_name = sheet.get("sheet_name", "Sheet")
        row_count = sheet.get("row_count", 0)
        sheet_root_node_id = uuid5(NAMESPACE_DNS, f"excel-sheet-root:{kb_doc_id}:{sheet_name}").hex

        if row_count <= TABLE_BATCH_SIZE:
            # 无需分片，单任务处理
            shards.append({
                "sheet_name": sheet_name,
                "row_from": 0,
                "row_to": None,
                "emit_summary": True,
                "clear_existing": first_task,
                "sheet_root_node_id": sheet_root_node_id,
            })
            first_task = False
        else:
            # 按 TABLE_BATCH_SIZE 切分
            batch_idx = 0
            for row_start in range(0, row_count, TABLE_BATCH_SIZE):
                row_end = min(row_start + TABLE_BATCH_SIZE, row_count)
                shards.append({
                    "sheet_name": sheet_name,
                    "row_from": row_start,
                    "row_to": row_end,
                    "emit_summary": (batch_idx == 0),
                    "clear_existing": first_task,
                    "sheet_root_node_id": sheet_root_node_id,
                })
                first_task = False
                batch_idx += 1

    logger.info(
        f"[ChunkTask] Excel 大表分片: kb_doc_id={kb_doc_id}, "
        f"共 {len(shards)} 个分片任务"
    )
    return shards


@celery_app.task(
    name="rag.ingestion.tasks.chunk_excel_table_shard_task",
    bind=True,
    max_retries=3,
    soft_time_limit=600,
    time_limit=720,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
)
def chunk_excel_table_shard_task(
    self,
    kb_doc_id: str,
    raw_text: str,
    metadata: Dict[str, Any],
    chunk_strategy: str = "excel_table",
    chunk_size: int = 512,
    chunk_overlap: int = 0,
    sheet_name: Optional[str] = None,
    sheet_root_node_id: Optional[str] = None,
    row_from: int = 0,
    row_to: Optional[int] = None,
    emit_summary: bool = True,
    clear_existing: bool = False,
    **kwargs,
):
    """
    Excel 表格模式大表分片 Chunk 任务。

    每个分片只处理 [row_from, row_to) 范围内的数据行，
    避免单任务加载整张大表导致 OOM。

    第一个分片（is_first_shard=True）额外负责：
    - 清理该文档的旧 chunk（防止重复）
    - 生成 summary chunk（作为行级 chunk 的父节点）

    Args:
        kb_doc_id: 知识库文档 ID
        raw_text: 原始文本（表格模式通常为空字符串）
        metadata: ExcelTableParser 输出的 metadata（含 table_rows）
        chunk_strategy: 分块策略（应为 "excel_table"）
        chunk_size: 分块大小（ExcelTableChunker 不使用，保留接口兼容）
        chunk_overlap: 重叠大小（保留接口兼容）
        sheet_name: 当前分片所属工作表名称
        sheet_root_node_id: 当前工作表稳定根节点 ID
        row_from: 本分片数据行起始（0-based，相对于数据区域）
        row_to: 本分片数据行结束（不含，None 表示读到末尾）
        emit_summary: 是否为该 Sheet 输出根节点
        clear_existing: 是否负责清理旧 chunk
    """
    logger.info(
        f"[ChunkShardTask] 开始分片分块: kb_doc_id={kb_doc_id}, "
        f"sheet_name={sheet_name}, row_from={row_from}, row_to={row_to}, "
        f"emit_summary={emit_summary}, clear_existing={clear_existing}"
    )

    # 过滤 table_rows 只保留当前 Sheet 的本分片范围内的行
    all_rows: List[Dict[str, Any]] = metadata.get("table_rows", [])
    normalized_sheet_name = str(sheet_name or "").strip()
    row_upper = row_to if row_to is not None else 10**18
    shard_rows = [
        r for r in all_rows
        if str(r.get("sheet_name") or "").strip() == normalized_sheet_name
        and row_from <= int(r.get("row_index", 1) or 1) - 1 < row_upper
    ]
    shard_metadata = dict(metadata)
    shard_metadata["table_rows"] = shard_rows
    shard_metadata["sheets"] = [
        sheet for sheet in list(metadata.get("sheets") or [])
        if str(sheet.get("sheet_name") or "").strip() == normalized_sheet_name
    ]
    if normalized_sheet_name and sheet_root_node_id:
        shard_metadata["sheet_root_node_ids"] = {normalized_sheet_name: str(sheet_root_node_id)}

    # 同一 Sheet 只有首个分片负责生成根节点，后续分片复用稳定 root id 作为 parent。
    if not emit_summary:
        kwargs["enable_summary_chunk"] = False

    async def _run():
        task_engine, task_sm = create_task_session_maker()
        redis_client = create_task_redis_client()
        try:
            await _do_chunk_document(
                UUID(kb_doc_id),
                raw_text,
                shard_metadata,
                chunk_strategy,
                chunk_size,
                chunk_overlap,
                redis_client,
                task_sm,
                # 仅首个任务清理旧 chunk；其余任务追加写入。
                _skip_delete_old_chunks=not clear_existing,
                **kwargs,
            )
        finally:
            await close_task_redis_client(redis_client)
            await close_task_db_engine(task_engine)

    try:
        asyncio.run(_run())
        logger.info(
            f"[ChunkShardTask] 分片完成: kb_doc_id={kb_doc_id}, "
            f"sheet_name={sheet_name}, row_from={row_from}, row_to={row_to}"
        )
        return {
            "status": "success",
            "kb_doc_id": kb_doc_id,
            "sheet_name": sheet_name,
            "row_from": row_from,
            "row_to": row_to,
        }
    except Exception as e:
        logger.error(f"[ChunkShardTask] 分片失败: kb_doc_id={kb_doc_id}, row_from={row_from}, 错误: {str(e)}", exc_info=True)
        is_timeout = isinstance(e, (redis_exc.TimeoutError, redis_exc.ConnectionError, TimeoutError))
        countdown = min(60, 10 * (2 ** self.request.retries)) if is_timeout else (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)
