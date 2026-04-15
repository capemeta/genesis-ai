"""
知识库自定义路由

在 CRUD 工厂生成的标准路由基础上，添加文档管理相关的自定义路由：
- 关联文档到知识库
- 列出知识库中的文档
- 从知识库移除文档
"""
import logging
import hashlib
import json
from types import SimpleNamespace
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from uuid import UUID as PyUUID

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from redis.asyncio import Redis
from sqlalchemy import select, and_, func, delete, or_, text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_async_session, get_redis
from core.response import ResponseBuilder
from core.security.auth import get_current_user
from core.storage import get_storage_driver
from models.user import User
from models.document import Document
from models.chunk import Chunk
from models.kb_qa_row import KBQARow
from models.kb_web_page import KBWebPage
from models.kb_web_page_version import KBWebPageVersion
from models.kb_web_sync_run import KBWebSyncRun
from models.kb_web_sync_schedule import KBWebSyncSchedule
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.kb_table_row import KBTableRow
from rag.ingestion.parsers.qa import QAParser
from rag.ingestion.parsers.csv.csv_parser import CSVParser
from rag.ingestion.parsers.excel.excel_table_parser import ExcelTableParser
from rag.ingestion.tasks.common import (
    build_effective_config,
    load_recent_parse_attempt_logs,
)
from rag.retrieval.hybrid import HybridRetrievalService
from services.kb_document_parse_service import (
    KBDocumentParseService,
    dispatch_parse_pipeline,
    prepare_parse_pipeline_submission,
)
from api.crud_registry import crud_factory

logger = logging.getLogger(__name__)

# 从 CRUD 工厂获取已生成的 router
router = crud_factory.get_router("KnowledgeBase")


# ==================== Schemas ====================

class AttachDocumentsRequest(BaseModel):
    """关联文档到知识库请求"""
    kb_id: UUID  # 知识库ID
    document_ids: List[UUID]  # 文档ID列表
    folder_id: Optional[UUID] = None  # 文件夹ID（可选）
    parse_immediately: bool = True  # 是否立即执行解析


class AttachDocumentsResponse(BaseModel):
    """关联文档响应"""
    success_count: int  # 成功关联数量
    duplicate_count: int  # 重复跳过数量
    failed_count: int  # 失败数量
    details: List[dict]  # 详细信息
    table_schema_initialized: bool = False  # 是否自动初始化表格结构
    table_schema_source_document_id: Optional[str] = None  # 自动初始化结构使用的文档ID
    table_schema_column_count: int = 0  # 自动初始化得到的字段数


class TableImportPrecheckRequest(BaseModel):
    """表格导入预检请求。"""
    kb_doc_id: UUID


class TableDocumentImportPrecheckRequest(BaseModel):
    """表格文件导入预检请求（导入前）。"""
    kb_id: UUID
    document_id: UUID


class TableImportPrecheckResponse(BaseModel):
    """表格导入预检响应。"""
    kb_doc_id: str
    kb_id: str
    document_id: str
    decision: str
    compatible: bool
    summary: str
    sheet_name: Optional[str] = None
    detected_header: List[str] = []
    schema_columns: List[str] = []
    missing_columns: List[str] = []
    required_missing_columns: List[str] = []
    extra_columns: List[str] = []
    warnings: List[str] = []


class ConfirmTableStructureRequest(BaseModel):
    """确认表格结构请求。"""
    kb_id: UUID
    retrieval_config: Dict[str, Any]


class RetrievalTestFilterRequest(BaseModel):
    """检索测试的硬过滤条件。"""

    kb_doc_ids: List[UUID] = Field(default_factory=list)
    document_ids: List[UUID] = Field(default_factory=list)
    folder_ids: List[UUID] = Field(default_factory=list)
    tag_ids: List[UUID] = Field(default_factory=list)
    folder_tag_ids: List[UUID] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    search_unit_metadata: Dict[str, Any] = Field(default_factory=dict)
    filter_expression: Dict[str, Any] = Field(default_factory=dict)
    include_descendant_folders: bool = True
    only_tagged: bool = False


class RetrievalTestConfigRequest(BaseModel):
    """检索测试参数。

    说明：
    - 与前端检索测试页一一对应
    - 额外兼容聊天会话里的 search_depth_k / min_score / rerank_top_n
    """

    vector_similarity_threshold: Optional[float] = None
    keyword_relevance_threshold: Optional[float] = None
    final_score_threshold: Optional[float] = None
    vector_weight: Optional[float] = None
    top_k: Optional[int] = None
    vector_top_k: Optional[int] = None
    keyword_top_k: Optional[int] = None
    rerank_top_n: Optional[int] = None
    enable_rerank: Optional[bool] = None
    rerank_model: Optional[str] = None
    metadata_filter: Optional[str] = None
    use_knowledge_graph: Optional[bool] = None
    enable_query_rewrite: Optional[bool] = None
    enable_synonym_rewrite: Optional[bool] = None
    auto_filter_mode: Optional[str] = None
    enable_llm_filter_expression: Optional[bool] = None
    metadata_fields: List[Dict[str, Any]] = Field(default_factory=list)
    extra_metadata_fields: List[Dict[str, Any]] = Field(default_factory=list)
    override_metadata_fields: List[Dict[str, Any]] = Field(default_factory=list)
    search_depth_k: Optional[int] = None
    min_score: Optional[float] = None
    search_scopes: List[str] = Field(default_factory=list)
    enable_parent_context: Optional[bool] = None
    hierarchical_retrieval_mode: Optional[str] = None
    neighbor_window_size: Optional[int] = None
    group_by_content_group: Optional[bool] = None
    debug_trace_level: Optional[str] = None

    @model_validator(mode="after")
    def validate_rerank_config(self):
        """校验检索测试配置约束。"""

        if bool(self.enable_rerank) and not str(self.rerank_model or "").strip():
            raise ValueError("已开启重排序，请先选择一个 rerank 模型")
        hierarchical_mode = str(self.hierarchical_retrieval_mode or "recursive").strip().lower() or "recursive"
        if hierarchical_mode not in {"leaf_only", "recursive", "auto_merge"}:
            raise ValueError("层级召回策略仅支持 leaf_only、recursive、auto_merge")
        if self.neighbor_window_size is not None and not 0 <= int(self.neighbor_window_size) <= 5:
            raise ValueError("邻近块补充数量必须在 0 到 5 之间")
        return self


class RetrievalTestRequest(BaseModel):
    """检索测试请求。"""

    kb_id: UUID
    query: str
    config: RetrievalTestConfigRequest = Field(default_factory=RetrievalTestConfigRequest)
    filters: Optional[RetrievalTestFilterRequest] = None
    query_rewrite_context: List[Dict[str, str]] = Field(default_factory=list)


def _get_table_retrieval_config(retrieval_config: Dict[str, Any]) -> Dict[str, Any]:
    """读取 retrieval_config.table 配置，统一表格配置命名空间。"""
    return dict((retrieval_config or {}).get("table") or {})


def _has_table_schema(kb: KnowledgeBase) -> bool:
    """判断当前知识库是否已经定义表格结构。"""
    retrieval_config = dict(kb.retrieval_config or {})
    table_retrieval = _get_table_retrieval_config(retrieval_config)
    table_schema = dict(table_retrieval.get("schema") or {})
    columns = list(table_schema.get("columns") or [])
    return len(columns) > 0


def _get_table_schema_status(
    kb: KnowledgeBase,
    *,
    has_attached_documents: bool = False,
) -> str:
    """获取表格结构状态，缺省时按当前上下文推导。"""
    retrieval_config = dict(kb.retrieval_config or {})
    table_retrieval = _get_table_retrieval_config(retrieval_config)
    status = str(table_retrieval.get("schema_status") or "").strip().lower()
    if status in {"draft", "confirmed"}:
        return status
    if _has_table_schema(kb) and has_attached_documents:
        return "confirmed"
    return "draft"


def _validate_table_schema_columns(columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """校验并规范化表格字段定义。"""
    normalized_columns: List[Dict[str, Any]] = []
    seen_names: set[str] = set()

    def _normalize_string_list(raw_values: Any) -> List[str]:
        """统一规范化字符串数组，供别名和枚举值复用。"""

        return [
            str(item).strip()
            for item in list(raw_values or [])
            if str(item or "").strip()
        ]

    for index, column in enumerate(columns):
        name = str((column or {}).get("name") or "").strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"第 {index + 1} 个字段名称不能为空",
            )
        if name in seen_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"字段名称不能重复：{name}",
            )
        seen_names.add(name)

        role = str((column or {}).get("role") or "content").strip() or "content"
        if role == "dimension":
            role = "entity"
        if role not in {"entity", "content", "identifier"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"字段 {name} 的用途配置无效",
            )

        normalized_columns.append({
            "name": name,
            "type": "text",
            "nullable": bool((column or {}).get("nullable", True)),
            "role": role,
            "filterable": bool((column or {}).get("filterable", False)),
            "aggregatable": bool((column or {}).get("aggregatable", False)),
            "searchable": bool((column or {}).get("searchable", True)),
            "aliases": _normalize_string_list((column or {}).get("aliases")),
            "enum_values": _normalize_string_list((column or {}).get("enum_values")),
        })

    if not normalized_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少定义 1 个字段后再确认结构",
        )

    return normalized_columns


def _validate_table_metadata_rules(metadata: Dict[str, Any]) -> Optional[str]:
    """校验表格知识库的固定导入规范。"""
    detected_sheets = list(metadata.get("sheets") or [])
    first_sheet = detected_sheets[0] if detected_sheets else {}
    detected_header = [str(item).strip() for item in list(first_sheet.get("header") or []) if str(item).strip()]
    if not detected_header:
        return "未识别到有效表头，请确认第 1 行为表头且列名完整"

    header_row_number = int(first_sheet.get("header_row_number") or 1)
    if header_row_number != 1:
        return "表格知识库要求第 1 行必须为表头"

    return None


async def _parse_table_metadata_from_document(document: Document) -> Dict[str, Any]:
    """从物理文件解析表格 metadata，用于结构草稿生成与预检。"""
    file_type = str(document.file_type or "").lower()
    if file_type not in {"xlsx", "xls", "csv"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前文件类型不支持表格预检，仅支持 xlsx/xls/csv",
        )

    storage = get_storage_driver(document.storage_driver)
    file_buffer = await storage.get_content(document.file_key)
    if file_type == "csv":
        _, metadata = CSVParser().parse_table(file_buffer)
    else:
        _, metadata = ExcelTableParser().parse(file_buffer, f".{file_type}")
    return metadata


async def _parse_qa_metadata_from_document(document: Document) -> Dict[str, Any]:
    """从物理文件解析 QA metadata，用于挂载阶段预检与立即落库。"""
    file_type = str(document.file_type or "").lower()
    if file_type not in {"xlsx", "csv"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前文件类型不支持 QA 导入，仅支持 xlsx/csv",
        )

    storage = get_storage_driver(document.storage_driver)
    file_buffer = await storage.get_content(document.file_key)
    parser = QAParser()
    try:
        _, metadata = parser.parse(file_buffer=file_buffer, file_extension=f".{file_type}")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{document.name} 预检未通过：{str(exc)}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{document.name} 解析失败：{str(exc)}",
        ) from exc
    return metadata


def _evaluate_table_import_precheck(
    kb: KnowledgeBase,
    metadata: Dict[str, Any],
    *,
    has_attached_documents: bool = False,
) -> Dict[str, Any]:
    """根据知识库 schema 评估表格导入兼容性。"""
    retrieval_config = dict(kb.retrieval_config or {})
    table_retrieval = _get_table_retrieval_config(retrieval_config)
    table_schema = dict(table_retrieval.get("schema") or {})
    schema_columns_meta = list(table_schema.get("columns") or [])
    detected_sheets = list(metadata.get("sheets") or [])
    first_sheet = detected_sheets[0] if detected_sheets else {}
    detected_header = [str(item) for item in list(first_sheet.get("header") or [])]
    schema_column_names = [str(col.get("name")) for col in schema_columns_meta if str(col.get("name") or "").strip()]
    fixed_rule_error = _validate_table_metadata_rules(metadata)
    schema_status = _get_table_schema_status(kb, has_attached_documents=has_attached_documents)

    logger.info(
        "[TABLE_PRECHECK] 开始预检 kb=%s schema_status=%s has_attached_documents=%s sheet=%s schema_columns=%s detected_header=%s",
        kb.id,
        schema_status,
        has_attached_documents,
        first_sheet.get("sheet_name"),
        schema_column_names,
        detected_header,
    )

    if fixed_rule_error:
        logger.warning(
            "[TABLE_PRECHECK] 固定布局校验失败 kb=%s sheet=%s error=%s",
            kb.id,
            first_sheet.get("sheet_name"),
            fixed_rule_error,
        )
        return {
            "decision": "invalid_layout",
            "compatible": False,
            "summary": fixed_rule_error,
            "detected_header": detected_header,
            "schema_columns": schema_column_names,
            "missing_columns": [],
            "required_missing_columns": [],
            "extra_columns": [],
            "warnings": [],
            "sheet_name": first_sheet.get("sheet_name"),
        }

    if not schema_column_names:
        logger.info(
            "[TABLE_PRECHECK] 当前知识库尚未定义结构 kb=%s sheet=%s，可作为结构草稿来源",
            kb.id,
            first_sheet.get("sheet_name"),
        )
        return {
            "decision": "no_schema",
            "compatible": True,
            "summary": "当前知识库尚未定义结构，可将本文件作为首个结构草稿来源",
            "detected_header": detected_header,
            "schema_columns": [],
            "missing_columns": [],
            "required_missing_columns": [],
            "extra_columns": [],
            "warnings": [],
            "sheet_name": first_sheet.get("sheet_name"),
        }

    schema_lookup = {str(col.get("name")): col for col in schema_columns_meta if str(col.get("name") or "").strip()}
    header_order_matches = detected_header == schema_column_names
    header_position_mismatches: List[str] = []
    missing_columns = []
    extra_columns = []
    required_missing_columns = []
    if not header_order_matches:
        schema_name_set = set(schema_column_names)
        detected_name_set = set(detected_header)
        missing_columns = [name for name in schema_column_names if name not in detected_name_set]
        extra_columns = [name for name in detected_header if name not in schema_name_set]
        compare_length = max(len(schema_column_names), len(detected_header))
        for index in range(compare_length):
            expected_name = schema_column_names[index] if index < len(schema_column_names) else "<缺失>"
            actual_name = detected_header[index] if index < len(detected_header) else "<缺失>"
            if expected_name != actual_name:
                header_position_mismatches.append(
                    f"第 {index + 1} 列应为“{expected_name}”，当前为“{actual_name}”"
                )
            if len(header_position_mismatches) >= 5:
                break
        for name in missing_columns:
            column_meta = schema_lookup.get(name) or {}
            nullable = bool(column_meta.get("nullable", True))
            if not nullable:
                required_missing_columns.append(name)

    required_empty_value_rows: List[str] = []
    table_rows = list(metadata.get("table_rows") or [])
    required_columns = [
        name
        for name in schema_column_names
        if not bool((schema_lookup.get(name) or {}).get("nullable", True))
    ]
    for row_dict in table_rows:
        if not isinstance(row_dict, dict):
            continue
        row_index = int(row_dict.get("row_index") or 0)
        header = [str(item) for item in list(row_dict.get("header") or [])]
        values = list(row_dict.get("values") or [])
        row_data = {
            column_name: str(values[idx]).strip() if idx < len(values) and values[idx] is not None else ""
            for idx, column_name in enumerate(header)
        }
        for column_name in required_columns:
            if column_name in row_data and not row_data[column_name]:
                required_empty_value_rows.append(f"第 {row_index} 行的“{column_name}”为空")
        if len(required_empty_value_rows) >= 5:
            break

    warnings: List[str] = []
    decision = "exact"
    compatible = True
    summary = "当前文件列结构与知识库定义完全一致，可直接导入"

    if not header_order_matches:
        decision = "header_mismatch"
        compatible = False
        expected_count = len(schema_column_names)
        actual_count = len(detected_header)
        if expected_count != actual_count:
            summary = f"列数量不一致：结构定义为 {expected_count} 列，当前文件为 {actual_count} 列"
        else:
            mismatch_preview = "；".join(header_position_mismatches[:3])
            summary = f"表头不匹配，必须按相同顺序逐列完全匹配。{mismatch_preview}" if mismatch_preview else "当前文件表头与结构定义不一致，必须按相同顺序逐列完全匹配"
        if missing_columns:
            warnings.append(f"缺少列：{', '.join(missing_columns)}")
        if extra_columns:
            warnings.append(f"新增列：{', '.join(extra_columns)}")
        warnings.extend(header_position_mismatches)
        if not missing_columns and not extra_columns and not header_position_mismatches:
            warnings.append("列名集合一致，但列顺序不一致")
    elif required_missing_columns:
        decision = "required_missing"
        compatible = False
        summary = f"当前文件缺少必填字段：{', '.join(required_missing_columns)}"
    elif required_empty_value_rows:
        decision = "required_values_empty"
        compatible = False
        summary = f"当前文件中存在必填字段空值，例如：{required_empty_value_rows[0]}"
        warnings.extend(required_empty_value_rows)

    if schema_status != "confirmed":
        if has_attached_documents:
            compatible = False
            decision = "schema_draft"
            summary = "当前结构草稿尚未定稿，请先确认结构后再继续导入其他文档"
        elif compatible:
            summary = "当前文件符合结构草稿，可作为首个样例文档导入；导入后请先确认结构"
            warnings.append("结构草稿尚未定稿，首个文档导入后请先确认结构，再继续导入其他文档")

    logger.info(
        "[TABLE_PRECHECK] 预检完成 kb=%s decision=%s compatible=%s summary=%s missing=%s extra=%s required_missing=%s warnings=%s",
        kb.id,
        decision,
        compatible,
        summary,
        missing_columns,
        extra_columns,
        required_missing_columns,
        warnings,
    )

    return {
        "decision": decision,
        "compatible": compatible,
        "summary": summary,
        "detected_header": detected_header,
        "schema_columns": schema_column_names,
        "missing_columns": missing_columns,
        "required_missing_columns": required_missing_columns,
        "extra_columns": extra_columns,
        "warnings": warnings,
        "sheet_name": first_sheet.get("sheet_name"),
    }


def _build_table_schema_columns(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """根据解析结果生成表格结构草稿。"""
    sheets = list(metadata.get("sheets") or [])
    first_sheet = sheets[0] if sheets else {}
    header = list(first_sheet.get("header") or [])
    field_map = dict(metadata.get("field_map") or {})
    columns: List[Dict[str, Any]] = []

    for index, column_name in enumerate(header):
        inferred_type = str(field_map.get(column_name) or "text")
        role = "content"
        if index == 0:
            role = "dimension"
        elif index == 1:
            role = "entity"

        filterable = role in {"dimension", "entity"}
        aggregatable = role in {"dimension", "entity"}
        searchable = role in {"dimension", "entity", "content", "identifier"}

        columns.append({
            "name": str(column_name),
            "type": inferred_type if inferred_type in {"text", "int", "float", "datetime", "bool"} else "text",
            "nullable": True,
            "role": role,
            "filterable": filterable,
            "aggregatable": aggregatable,
            "searchable": searchable,
            "aliases": [],
            "enum_values": [],
        })

    return columns


def _extract_detected_header_from_metadata(metadata: Dict[str, Any]) -> List[str]:
    """提取首个工作表识别到的表头。"""
    sheets = list(metadata.get("sheets") or [])
    first_sheet = sheets[0] if sheets else {}
    return [str(item) for item in list(first_sheet.get("header") or [])]


async def _try_initialize_table_schema_from_document(
    session: AsyncSession,
    kb: KnowledgeBase,
    document: Document,
    current_user: User,
) -> Dict[str, Any]:
    """
    尝试从首个表格文件生成结构草稿并写回知识库配置。

    当前策略：
    - 仅对 table 类型知识库生效
    - 仅在尚未定义 schema.columns 时触发
    - 仅处理 xlsx/xls/csv
    """
    if kb.type != "table" or _has_table_schema(kb):
        return {"initialized": False, "column_count": 0}

    file_type = str(document.file_type or "").lower()
    if file_type not in {"xlsx", "xls", "csv"}:
        return {"initialized": False, "column_count": 0}

    storage = get_storage_driver(document.storage_driver)
    file_buffer = await storage.get_content(document.file_key)

    if file_type == "csv":
        _, metadata = CSVParser().parse_table(file_buffer)
    else:
        _, metadata = ExcelTableParser().parse(file_buffer, f".{file_type}")

    columns = _build_table_schema_columns(metadata)
    if not columns:
        return {"initialized": False, "column_count": 0}

    retrieval_config = dict(kb.retrieval_config or {})
    table_retrieval = _get_table_retrieval_config(retrieval_config)
    table_retrieval["schema"] = {"columns": columns}
    table_retrieval["field_map"] = {}
    table_retrieval["key_columns"] = []
    table_retrieval.setdefault("include_sheets", [])
    table_retrieval.setdefault("text_prefix_template", "")
    table_retrieval.setdefault("overflow_strategy", "key_columns_first")
    table_retrieval["import_validation"] = {}
    table_retrieval["schema_status"] = "draft"
    table_retrieval["schema_source_document_id"] = str(document.id)
    retrieval_config["table"] = table_retrieval
    kb.retrieval_config = retrieval_config

    chunking_config = dict(kb.chunking_config or {})
    chunking_config.setdefault("chunk_strategy", "excel_table")
    chunking_config.setdefault("max_embed_tokens", 512)
    # 表格模式统一使用 tokenizer 与 summary 根节点，不再作为可变配置暴露。
    chunking_config["token_count_method"] = "tokenizer"
    chunking_config["enable_summary_chunk"] = True
    kb.chunking_config = chunking_config
    kb.updated_by_id = current_user.id
    kb.updated_by_name = current_user.nickname
    kb.updated_at = datetime.now()

    await session.flush()
    logger.info(
        "[KB] 表格知识库 %s 已根据文档 %s 自动生成结构草稿，字段数=%s",
        kb.id,
        document.id,
        len(columns),
    )
    return {
        "initialized": True,
        "column_count": len(columns),
        "source_document_id": str(document.id),
    }


def _build_table_row_hash(row_data: Dict[str, Any]) -> str:
    """计算表格行内容哈希。"""
    payload = json.dumps(row_data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _persist_table_rows_immediately(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    kb: KnowledgeBase,
    document: Document,
) -> Dict[str, Any]:
    """
    在文档挂载阶段立即解析并落库 kb_table_rows。

    设计意图：
    - 让数据视图尽快可见，不依赖后续 chunk/embedding 异步任务
    - 后续 parse_task 仍可继续复用完整解析链，负责重建 chunk
    """
    if kb.type != "table":
        return {"persisted": False, "row_count": 0}

    file_type = str(document.file_type or "").lower()
    if file_type not in {"xlsx", "xls", "csv"}:
        return {"persisted": False, "row_count": 0}

    metadata = await _parse_table_metadata_from_document(document)
    table_rows = list(metadata.get("table_rows") or [])
    sheets = list(metadata.get("sheets") or [])
    sheet_map = {
        str(sheet.get("sheet_name") or "Sheet"): sheet
        for sheet in sheets
        if isinstance(sheet, dict)
    }

    await session.execute(delete(KBTableRow).where(KBTableRow.kb_doc_id == kb_doc.id))
    await session.flush()

    new_rows: List[KBTableRow] = []
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

        new_rows.append(
            KBTableRow(
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
                source_meta={
                    "sheet_name": sheet_name,
                    "header": header,
                    "header_row_number": header_row_number,
                    "source_anchor": f"{sheet_name}!R{row_index}",
                },
                created_by_id=kb_doc.created_by_id,
                created_by_name=kb_doc.created_by_name,
                updated_by_id=kb_doc.updated_by_id,
                updated_by_name=kb_doc.updated_by_name,
            )
        )

    if new_rows:
        session.add_all(new_rows)
        await session.flush()

    custom_metadata = dict(kb_doc.custom_metadata or {})
    custom_metadata["content_kind"] = "table_dataset"
    custom_metadata["table_rows_ready"] = True
    custom_metadata["table_row_count"] = len(new_rows)
    custom_metadata["table_rows_updated_at"] = datetime.utcnow().isoformat()
    kb_doc.custom_metadata = custom_metadata
    kb_doc.updated_at = datetime.utcnow()

    logger.info(
        "[KB] 表格知识库文档 %s 已在挂载阶段落库 %s 条 kb_table_rows",
        kb_doc.id,
        len(new_rows),
    )
    return {"persisted": True, "row_count": len(new_rows)}


async def _persist_qa_rows_immediately(
    session: AsyncSession,
    kb_doc: KnowledgeBaseDocument,
    kb: KnowledgeBase,
    document: Document,
) -> Dict[str, Any]:
    """
    在文档挂载阶段立即解析并落库 kb_qa_rows。

    设计意图：
    - 与表格型知识库保持一致，主事实表先落库
    - 后续 parse/chunk/train 统一从 kb_qa_rows 出发
    """
    if kb.type != "qa":
        return {"persisted": False, "row_count": 0}

    metadata = await _parse_qa_metadata_from_document(document)
    qa_items = list(metadata.get("qa_items") or [])

    await session.execute(delete(KBQARow).where(KBQARow.kb_doc_id == kb_doc.id))
    await session.flush()

    new_rows: List[KBQARow] = []
    for position, item in enumerate(qa_items):
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        similar_questions = [str(v).strip() for v in (item.get("similar_questions") or []) if str(v).strip()]
        tags = [str(v).strip() for v in (item.get("tags") or []) if str(v).strip()]
        category = str(item.get("category") or "").strip() or None
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

        new_rows.append(
            KBQARow(
                tenant_id=kb_doc.tenant_id,
                kb_id=kb_doc.kb_id,
                document_id=kb_doc.document_id,
                kb_doc_id=kb_doc.id,
                source_row_id=str(item.get("record_id") or f"qa-{position + 1}"),
                position=position,
                question=question,
                answer=answer,
                similar_questions=similar_questions,
                category=category,
                tags=tags,
                source_mode="imported",
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
        )

    if new_rows:
        session.add_all(new_rows)
        await session.flush()

    custom_metadata = dict(kb_doc.custom_metadata or {})
    custom_metadata["content_kind"] = "qa_dataset"
    custom_metadata["qa_rows_ready"] = True
    custom_metadata["qa_row_count"] = len(new_rows)
    custom_metadata["qa_rows_updated_at"] = datetime.utcnow().isoformat()
    custom_metadata["source_mode"] = "imported"
    custom_metadata["source_file_type"] = str(document.file_type or "").lower()
    custom_metadata["qa_template_version"] = metadata.get("template_version")
    kb_doc.custom_metadata = custom_metadata
    kb_doc.updated_at = datetime.utcnow()

    logger.info(
        "[KB] QA 知识库文档 %s 已在挂载阶段落库 %s 条 kb_qa_rows",
        kb_doc.id,
        len(new_rows),
    )
    return {"persisted": True, "row_count": len(new_rows)}


class ListKBDocumentsRequest(BaseModel):
    """获取知识库文档列表请求"""
    kb_id: UUID  # 知识库ID
    folder_id: Optional[UUID] = None  # 文件夹ID（None表示根目录）
    include_subfolders: bool = False  # 是否包含子文件夹
    page: int = 1
    page_size: int = 20
    search: Optional[str] = None  # 搜索关键词（文件名）
    parse_status: Optional[str] = None  # 解析状态过滤
    is_enabled: Optional[bool] = None  # 是否启用过滤
    sort_by: Optional[str] = None  # 仅当前端显式选择排序时才生效
    sort_order: str = "desc"  # 排序方向：asc / desc


def _apply_kb_document_sort(query, request: ListKBDocumentsRequest):
    """为文档列表应用稳定排序，避免轮询刷新时顺序抖动。"""
    sort_field = (request.sort_by or "").strip()
    sort_order = (request.sort_order or "desc").lower()
    if sort_order not in {"asc", "desc"}:
        sort_order = "desc"

    # 只支持明确允许的字段，避免被意外参数改变默认顺序。
    sort_field_map = {
        "created_at": KnowledgeBaseDocument.created_at,
        "updated_at": KnowledgeBaseDocument.updated_at,
        "parse_status": KnowledgeBaseDocument.parse_status,
        "status": KnowledgeBaseDocument.parse_status,
        "chunk_count": KnowledgeBaseDocument.chunk_count,
        "is_enabled": KnowledgeBaseDocument.is_enabled,
    }

    if not sort_field:
        # 默认按新到旧展示，并使用 ID 作为二级排序保证结果稳定。
        return query.order_by(
            KnowledgeBaseDocument.created_at.desc(),
            KnowledgeBaseDocument.id.desc(),
        )

    sort_column = sort_field_map.get(sort_field)
    if sort_column is None:
        return query.order_by(
            KnowledgeBaseDocument.created_at.desc(),
            KnowledgeBaseDocument.id.desc(),
        )

    if sort_order == "asc":
        return query.order_by(sort_column.asc(), KnowledgeBaseDocument.id.asc())
    return query.order_by(sort_column.desc(), KnowledgeBaseDocument.id.desc())


class DetachDocumentsRequest(BaseModel):
    """从知识库移除文档请求"""
    kb_id: UUID  # 知识库ID
    kb_document_ids: List[UUID]  # 知识库文档关联ID列表（knowledge_base_documents 表的 ID）


class DocumentToggleEnabledRequest(BaseModel):
    """文档启用/禁用请求（支持单个和批量）"""
    kb_document_ids: List[UUID]  # 支持单个或多个
    enabled: bool


class ReparseDocumentRequest(BaseModel):
    """重新解析文档请求"""
    kb_document_ids: List[UUID]


# ==================== 自定义路由 ====================

@router.post(
    "/documents/attach",
    response_model=dict,
    summary="关联文档到知识库",
    description="将已上传的文档关联到知识库，创建 knowledge_base_documents 记录，触发解析任务"
)
async def attach_documents_to_kb(
    request: AttachDocumentsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    关联文档到知识库 API
    
    流程：
    1. 验证知识库是否存在
    2. 验证文档是否存在
    3. 检查是否已关联（去重）
    4. 批量创建 knowledge_base_documents 记录
    5. 触发异步解析任务
    
    注意：此 API 在用户点击"保存"时调用，是 RAG 业务的入口
    """
    
    kb_id = request.kb_id
    
    # 1. 验证知识库是否存在
    kb = await session.get(KnowledgeBase, kb_id)
    if not kb or kb.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在"
        )
    
    # 2. 验证文档是否存在
    docs_stmt = select(Document).where(
        Document.id.in_(request.document_ids),
        Document.tenant_id == current_user.tenant_id
    )
    docs_result = await session.execute(docs_stmt)
    docs = docs_result.scalars().all()
    
    if len(docs) != len(request.document_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="部分文档不存在或无权访问"
        )
    
    # 3. 检查已关联的文档（去重）
    existing_stmt = select(KnowledgeBaseDocument).where(
        KnowledgeBaseDocument.kb_id == kb_id,
        KnowledgeBaseDocument.document_id.in_(request.document_ids),
        KnowledgeBaseDocument.folder_id == request.folder_id
    )
    existing_result = await session.execute(existing_stmt)
    existing_relations = existing_result.scalars().all()
    existing_doc_ids = {rel.document_id for rel in existing_relations}
    existing_doc_count_result = await session.execute(
        select(func.count()).select_from(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.kb_id == kb_id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
        )
    )
    existing_doc_count = int(existing_doc_count_result.scalar() or 0)

    if kb.type == "table":
        has_table_schema = _has_table_schema(kb)
        schema_status = _get_table_schema_status(kb, has_attached_documents=existing_doc_count > 0)
        candidate_docs = [doc for doc in docs if doc.id not in existing_doc_ids]
        logger.info(
            "[TABLE_ATTACH] 开始关联表格文档 kb=%s existing_doc_count=%s has_table_schema=%s schema_status=%s request_document_ids=%s",
            kb.id,
            existing_doc_count,
            has_table_schema,
            schema_status,
            [str(doc_id) for doc_id in request.document_ids],
        )
        if has_table_schema and schema_status != "confirmed" and existing_doc_count > 0:
            logger.warning(
                "[TABLE_ATTACH] 拒绝关联 kb=%s 原因=结构草稿未定稿且已有样例文档",
                kb.id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前结构草稿尚未定稿，请先在结构定义中确认结构后再继续导入",
            )
        if not has_table_schema and candidate_docs:
            baseline_header: Optional[List[str]] = None
            baseline_doc_name: Optional[str] = None
            for doc in candidate_docs:
                metadata = await _parse_table_metadata_from_document(doc)
                fixed_rule_error = _validate_table_metadata_rules(metadata)
                if fixed_rule_error:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"{doc.name} 预检未通过：{fixed_rule_error}",
                    )
                detected_header = _extract_detected_header_from_metadata(metadata)
                if baseline_header is None:
                    baseline_header = detected_header
                    baseline_doc_name = doc.name
                    continue
                if detected_header != baseline_header:
                    logger.warning(
                        "[TABLE_ATTACH] 首批文件表头不一致 kb=%s baseline_doc=%s baseline_header=%s current_doc=%s current_header=%s",
                        kb.id,
                        baseline_doc_name,
                        baseline_header,
                        doc.name,
                        detected_header,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"{doc.name} 与首个文件 {baseline_doc_name} 的表头不一致，"
                            "首批导入的多个文件必须列名称和顺序完全一致"
                        ),
                    )
        for doc in candidate_docs:
            metadata = await _parse_table_metadata_from_document(doc)
            precheck_result = _evaluate_table_import_precheck(
                kb,
                metadata,
                has_attached_documents=existing_doc_count > 0,
            )
            if not bool(precheck_result.get("compatible")):
                logger.warning(
                    "[TABLE_ATTACH] 预检未通过 kb=%s document_id=%s name=%s decision=%s summary=%s detected_header=%s schema_columns=%s warnings=%s",
                    kb.id,
                    doc.id,
                    doc.name,
                    precheck_result.get("decision"),
                    precheck_result.get("summary"),
                    precheck_result.get("detected_header"),
                    precheck_result.get("schema_columns"),
                    precheck_result.get("warnings"),
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{doc.name} 预检未通过：{str(precheck_result.get('summary') or '表格结构预检未通过')}",
                )
            logger.info(
                "[TABLE_ATTACH] 预检通过 kb=%s document_id=%s name=%s decision=%s summary=%s",
                kb.id,
                doc.id,
                doc.name,
                precheck_result.get("decision"),
                precheck_result.get("summary"),
            )
    elif kb.type == "qa":
        candidate_docs = [doc for doc in docs if doc.id not in existing_doc_ids]
        for doc in candidate_docs:
            metadata = await _parse_qa_metadata_from_document(doc)
            logger.info(
                "[QA_ATTACH] 预检通过 kb=%s document_id=%s name=%s qa_item_count=%s",
                kb.id,
                doc.id,
                doc.name,
                len(metadata.get("qa_items") or []),
            )
    
    # 4. 批量创建 knowledge_base_documents 记录
    success_count = 0
    duplicate_count = len(existing_doc_ids)
    failed_count = 0
    details = []
    pending_parse_signatures = []
    table_schema_init_result = {
        "initialized": False,
        "column_count": 0,
        "source_document_id": None,
    }
    
    for doc in docs:
        if doc.id in existing_doc_ids:
            # 已关联，跳过
            details.append({
                "document_id": str(doc.id),
                "name": doc.name,
                "status": "duplicate",
                "message": "文档已存在于当前位置"
            })
            continue
        
        try:
            # 创建关联记录
            kb_doc = KnowledgeBaseDocument(
                tenant_id=current_user.tenant_id,
                kb_id=kb_id,
                document_id=doc.id,
                folder_id=request.folder_id,
                owner_id=current_user.id,
                display_name=doc.name,  # 初始化时设置为 document.name
                parse_status="pending",
                chunk_count=0,
                is_enabled=True,
                created_by_id=current_user.id,
                created_by_name=current_user.nickname
            )
            session.add(kb_doc)
            await session.flush()

            if kb.type == "table":
                try:
                    await _persist_table_rows_immediately(
                        session=session,
                        kb_doc=kb_doc,
                        kb=kb,
                        document=doc,
                    )
                except Exception as e:
                    logger.warning(
                        "表格知识库文档挂载后立即落库 kb_table_rows 失败，kb=%s, kb_doc=%s, document=%s, error=%s",
                        kb.id,
                        kb_doc.id,
                        doc.id,
                        e,
                    )
            elif kb.type == "qa":
                try:
                    await _persist_qa_rows_immediately(
                        session=session,
                        kb_doc=kb_doc,
                        kb=kb,
                        document=doc,
                    )
                except Exception as e:
                    logger.warning(
                        "QA 知识库文档挂载后立即落库 kb_qa_rows 失败，kb=%s, kb_doc=%s, document=%s, error=%s",
                        kb.id,
                        kb_doc.id,
                        doc.id,
                        e,
                    )

            success_count += 1
            existing_doc_count += 1
            details.append({
                "document_id": str(doc.id),
                "name": doc.name,
                "status": "success",
                "kb_doc_id": str(kb_doc.id),
                "message": "关联成功"
            })

            if not table_schema_init_result["initialized"]:
                try:
                    table_schema_init_result = await _try_initialize_table_schema_from_document(
                        session=session,
                        kb=kb,
                        document=doc,
                        current_user=current_user,
                    )
                except Exception as e:
                    logger.warning(
                        "表格知识库自动生成结构草稿失败，kb=%s, document=%s, error=%s",
                        kb.id,
                        doc.id,
                        e,
                    )
            
            # 触发异步解析任务
            if request.parse_immediately:
                signature = await prepare_parse_pipeline_submission(
                    session,
                    kb_doc,
                    reset_chunk_count=True,
                    effective_config=build_effective_config(kb_doc),
                )
                pending_parse_signatures.append(signature)


            
        except Exception as e:
            failed_count += 1
            details.append({
                "document_id": str(doc.id),
                "name": doc.name,
                "status": "failed",
                "message": f"关联失败: {str(e)}"
            })
            logger.error(f"关联文档失败: {doc.id}, 错误: {e}")
    
    await session.commit()
    for signature in pending_parse_signatures:
        dispatch_parse_pipeline(signature)

    logger.info(f"关联文档到知识库 {kb_id}: 成功 {success_count}, 重复 {duplicate_count}, 失败 {failed_count}")
    
    # 5. 返回响应
    return {
        "success": True,
        "message": f"关联完成：成功 {success_count} 个，跳过 {duplicate_count} 个，失败 {failed_count} 个",
        "data": AttachDocumentsResponse(
            success_count=success_count,
            duplicate_count=duplicate_count,
            failed_count=failed_count,
            details=details,
            table_schema_initialized=bool(table_schema_init_result["initialized"]),
            table_schema_source_document_id=table_schema_init_result.get("source_document_id"),
            table_schema_column_count=int(table_schema_init_result["column_count"] or 0),
        )
    }


@router.post(
    "/documents/precheck-table-import",
    response_model=dict,
    summary="表格文件导入预检",
    description="针对表格知识库中的单个文件执行列结构预检，返回字段差异与建议动作",
)
async def precheck_table_import(
    request: TableImportPrecheckRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """执行表格导入预检。"""
    kb_doc = await session.get(KnowledgeBaseDocument, request.kb_doc_id)
    if not kb_doc or kb_doc.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库文档不存在")

    kb = await session.get(KnowledgeBase, kb_doc.kb_id)
    if not kb or kb.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    if kb.type != "table":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前知识库不是表格知识库")

    document = await session.get(Document, kb_doc.document_id)
    if not document or document.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联文档不存在")

    metadata = await _parse_table_metadata_from_document(document)
    attached_count_result = await session.execute(
        select(func.count()).select_from(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.kb_id == kb.id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
        )
    )
    result = _evaluate_table_import_precheck(
        kb,
        metadata,
        has_attached_documents=int(attached_count_result.scalar() or 0) > 0,
    )
    return {
        "success": True,
        "data": TableImportPrecheckResponse(
            kb_doc_id=str(kb_doc.id),
            kb_id=str(kb.id),
            document_id=str(document.id),
            decision=result["decision"],
            compatible=bool(result["compatible"]),
            summary=str(result["summary"]),
            sheet_name=result.get("sheet_name"),
            detected_header=list(result.get("detected_header") or []),
            schema_columns=list(result.get("schema_columns") or []),
            missing_columns=list(result.get("missing_columns") or []),
            required_missing_columns=list(result.get("required_missing_columns") or []),
            extra_columns=list(result.get("extra_columns") or []),
            warnings=list(result.get("warnings") or []),
        ),
    }


@router.post(
    "/documents/precheck-table-document",
    response_model=dict,
    summary="表格物理文件导入预检",
    description="在关联到表格知识库之前，针对物理文件执行列结构预检",
)
async def precheck_table_document_import(
    request: TableDocumentImportPrecheckRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """执行导入前表格预检。"""
    kb = await session.get(KnowledgeBase, request.kb_id)
    if not kb or kb.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    if kb.type != "table":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前知识库不是表格知识库")

    document = await session.get(Document, request.document_id)
    if not document or document.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联文档不存在")

    metadata = await _parse_table_metadata_from_document(document)
    attached_count_result = await session.execute(
        select(func.count()).select_from(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.kb_id == kb.id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
        )
    )
    result = _evaluate_table_import_precheck(
        kb,
        metadata,
        has_attached_documents=int(attached_count_result.scalar() or 0) > 0,
    )
    return {
        "success": True,
        "data": {
            "kb_id": str(kb.id),
            "document_id": str(document.id),
            "decision": result["decision"],
            "compatible": bool(result["compatible"]),
            "summary": str(result["summary"]),
            "sheet_name": result.get("sheet_name"),
            "detected_header": list(result.get("detected_header") or []),
            "schema_columns": list(result.get("schema_columns") or []),
            "missing_columns": list(result.get("missing_columns") or []),
            "required_missing_columns": list(result.get("required_missing_columns") or []),
            "extra_columns": list(result.get("extra_columns") or []),
            "warnings": list(result.get("warnings") or []),
        },
    }


@router.post(
    "/confirm-table-structure",
    response_model=dict,
    summary="确认表格结构",
    description="将当前表格结构草稿确认成正式结构，确认后才允许继续正式导入文档",
)
async def confirm_table_structure(
    request: ConfirmTableStructureRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """确认表格结构。"""
    kb = await session.get(KnowledgeBase, request.kb_id)
    if not kb or kb.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    if kb.type != "table":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前知识库不是表格知识库")

    retrieval_config = dict(request.retrieval_config or {})
    table_retrieval = _get_table_retrieval_config(retrieval_config)
    table_schema = dict(table_retrieval.get("schema") or {})
    columns = _validate_table_schema_columns(list(table_schema.get("columns") or []))

    next_retrieval_config = dict(kb.retrieval_config or {})
    next_retrieval_config.update(retrieval_config)
    next_table_retrieval = _get_table_retrieval_config(next_retrieval_config)
    next_table_retrieval.update(table_retrieval)
    next_table_retrieval["schema"] = {"columns": columns}
    next_table_retrieval["field_map"] = {}
    next_table_retrieval["table_header_row"] = None
    next_table_retrieval["table_data_start_row"] = None
    next_table_retrieval["import_validation"] = {}
    next_table_retrieval["schema_status"] = "confirmed"
    next_table_retrieval["schema_source_document_id"] = table_retrieval.get(
        "schema_source_document_id"
    ) or next_table_retrieval.get("schema_source_document_id")
    next_retrieval_config["table"] = next_table_retrieval

    existing_docs_result = await session.execute(
        select(KnowledgeBaseDocument, Document)
        .join(Document, Document.id == KnowledgeBaseDocument.document_id)
        .where(
            KnowledgeBaseDocument.kb_id == kb.id,
            KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
            Document.tenant_id == current_user.tenant_id,
        )
    )
    existing_doc_pairs = existing_docs_result.all()
    if existing_doc_pairs:
        candidate_kb = SimpleNamespace(id=kb.id, retrieval_config=next_retrieval_config)
        for kb_doc, document in existing_doc_pairs:
            metadata = await _parse_table_metadata_from_document(document)
            precheck_result = _evaluate_table_import_precheck(
                candidate_kb,
                metadata,
                has_attached_documents=False,
            )
            if not bool(precheck_result.get("compatible")):
                logger.warning(
                    "[TABLE_CONFIRM] 定稿失败 kb=%s kb_doc=%s document_id=%s name=%s summary=%s",
                    kb.id,
                    kb_doc.id,
                    document.id,
                    document.name,
                    precheck_result.get("summary"),
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"已有文档 {document.name} 与待定稿结构不一致：{str(precheck_result.get('summary') or '校验未通过')}",
                )

    kb.retrieval_config = next_retrieval_config
    kb.updated_by_id = current_user.id
    kb.updated_by_name = current_user.nickname
    kb.updated_at = datetime.utcnow()
    await session.commit()

    return {
        "success": True,
        "message": "表格结构已确认，后续上传将按该结构严格校验",
        "data": {
            "kb_id": str(kb.id),
            "schema_status": "confirmed",
        },
    }


@router.post(
    "/documents/list",
    response_model=dict,
    summary="获取知识库文档列表",
    description="获取知识库中的文档列表，支持分页、搜索、过滤"
)
async def list_kb_documents(
    request: ListKBDocumentsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    获取知识库文档列表 API
    
    流程：
    1. 验证知识库是否存在
    2. 构建查询条件（文件夹、搜索、状态过滤）
    3. 分页查询
    4. 关联查询 document 信息
    5. 返回结果
    """
    
    kb_id = request.kb_id
    
    # 1. 验证知识库是否存在
    kb = await session.get(KnowledgeBase, kb_id)
    if not kb or kb.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在"
        )
    
    # 2. 构建基础查询
    query = select(KnowledgeBaseDocument).where(
        KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
        KnowledgeBaseDocument.kb_id == kb_id
    )
    
    # 3. 文件夹过滤
    if request.folder_id is not None:
        if request.include_subfolders:
            # 递归查询：查询当前文件夹及其所有子文件夹的文档
            # 使用 ltree 查询所有子文件夹
            from models.folder import Folder
            
            # 先获取当前文件夹的 path
            folder_stmt = select(Folder.path).where(
                Folder.id == request.folder_id,
                Folder.tenant_id == current_user.tenant_id
            )
            folder_result = await session.execute(folder_stmt)
            folder_path = folder_result.scalar_one_or_none()
            
            if not folder_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件夹不存在"
                )
            
            # 查询所有子文件夹（包括当前文件夹）
            # ltree 查询：path <@ 'parent.path' 或 path ~ 'parent.path.*'
            subfolder_stmt = select(Folder.id).where(
                Folder.tenant_id == current_user.tenant_id,
                Folder.kb_id == kb_id,
                text(f"path <@ '{folder_path}' OR path ~ '{folder_path}.*'::lquery")
            )
            subfolder_result = await session.execute(subfolder_stmt)
            subfolder_ids = [row[0] for row in subfolder_result.all()]
            
            # 查询这些文件夹中的文档（包括当前文件夹）
            if subfolder_ids:
                query = query.where(
                    or_(
                        KnowledgeBaseDocument.folder_id.in_(subfolder_ids),
                        KnowledgeBaseDocument.folder_id == request.folder_id
                    )
                )
            else:
                # 如果没有子文件夹，只查询当前文件夹
                query = query.where(KnowledgeBaseDocument.folder_id == request.folder_id)
        else:
            # 只查询当前文件夹
            query = query.where(KnowledgeBaseDocument.folder_id == request.folder_id)
    elif request.folder_id is None and not request.include_subfolders:
        # 只查询根目录（folder_id 为 NULL）
        query = query.where(KnowledgeBaseDocument.folder_id.is_(None))
    # 如果 folder_id 为 None 且 include_subfolders 为 True，则查询所有文档（不添加过滤条件）
    
    # 4. 解析状态过滤
    if request.parse_status:
        query = query.where(KnowledgeBaseDocument.parse_status == request.parse_status)
    
    # 5. 启用状态过滤
    if request.is_enabled is not None:
        query = query.where(KnowledgeBaseDocument.is_enabled == request.is_enabled)
    
    # 6. 关联查询 document、folder 和 tags 信息（用于搜索和返回）
    from models.folder import Folder
    from models.resource_tag import ResourceTag
    from models.tag import Tag
    query = query.options(
        selectinload(KnowledgeBaseDocument.document),
        selectinload(KnowledgeBaseDocument.folder),  # 关联查询 folder
        selectinload(KnowledgeBaseDocument.runtime),
    )
    
    # 7. 搜索过滤（文件名）
    if request.search:
        # 需要 join document 表进行搜索
        query = query.join(Document, KnowledgeBaseDocument.document_id == Document.id)
        query = query.where(Document.name.ilike(f"%{request.search}%"))
    
    # 8. 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # 9. 分页
    offset = (request.page - 1) * request.page_size
    query = _apply_kb_document_sort(query, request)
    query = query.offset(offset).limit(request.page_size)
    
    # 10. 执行查询
    result = await session.execute(query)
    kb_docs = result.scalars().all()
    
    # 11. 批量获取所有文档的标签信息（避免 N+1 查询）
    kb_doc_ids = [kb_doc.id for kb_doc in kb_docs]
    tags_map = {}
    web_error_map = {}
    parsing_logs_map = await load_recent_parse_attempt_logs(session, kb_doc_ids, per_doc_limit=5)
    
    if kb_doc_ids:
        web_error_stmt = select(
            KBWebPage.kb_doc_id,
            KBWebPage.last_error,
            KBWebPage.last_http_status,
            KBWebPage.url,
            KBWebPage.sync_status,
        ).where(
            KBWebPage.tenant_id == current_user.tenant_id,
            KBWebPage.kb_doc_id.in_(kb_doc_ids),
        )
        web_error_result = await session.execute(web_error_stmt)
        for kb_doc_id, last_error, last_http_status, url, sync_status in web_error_result.all():
            web_error_map[kb_doc_id] = {
                "last_error": last_error,
                "last_http_status": last_http_status,
                "url": url,
                "sync_status": sync_status,
            }

        # 一次性查询所有文档的标签
        from models.resource_tag import ResourceTag, TARGET_TYPE_KB_DOC
        tags_stmt = (
            select(ResourceTag.target_id, Tag)
            .join(Tag, ResourceTag.tag_id == Tag.id)
            .where(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.target_id.in_(kb_doc_ids),
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.action == "add"
            )
            .order_by(Tag.name)  # 按标签名称排序
        )
        tags_result = await session.execute(tags_stmt)
        
        # 构建标签映射：{kb_doc_id: [tag1, tag2, ...]}
        for target_id, tag in tags_result.all():
            if target_id not in tags_map:
                tags_map[target_id] = []
            tags_map[target_id].append({
                "id": str(tag.id),
                "name": tag.name,
                "description": tag.description,
                "color": tag.color,
                "aliases": tag.aliases,  # JSONB 数组字段
                "kb_id": str(tag.kb_id) if tag.kb_id else None,
                "created_by_name": tag.created_by_name,
                "created_at": tag.created_at.isoformat() if tag.created_at else None,
                "updated_at": tag.updated_at.isoformat() if tag.updated_at else None
            })
    
    # 12. 构建响应数据
    data = []
    
    for kb_doc in kb_docs:
        # 确保 document 已加载
        if not kb_doc.document:
            logger.warning(f"KnowledgeBaseDocument {kb_doc.id} 缺少关联的 document")
            continue

        web_error_info = web_error_map.get(kb_doc.id, {})
        display_error = web_error_info.get("last_error") or kb_doc.parse_error
        
        # 构建文件夹信息
        folder_info = None
        if kb_doc.folder:
            # 构建文件夹路径数组（包含每一级的 ID 和名称）
            # 使用 ltree 查询获取所有祖先文件夹
            
            # 查询所有祖先文件夹（包括当前文件夹）
            ancestor_stmt = select(Folder).where(
                Folder.tenant_id == current_user.tenant_id,
                Folder.kb_id == kb_doc.kb_id,
                text(f"path @> '{kb_doc.folder.path}'::ltree")
            ).order_by(Folder.level)
            
            ancestor_result = await session.execute(ancestor_stmt)
            ancestors = ancestor_result.scalars().all()
            
            # 构建路径数组
            folder_path_array = [
                {
                    "id": str(ancestor.id),
                    "name": ancestor.name,
                    "level": ancestor.level
                }
                for ancestor in ancestors
            ]
            
            folder_info = {
                "id": kb_doc.folder.id,
                "name": kb_doc.folder.name,
                "path": str(kb_doc.folder.path),  # ltree 原始路径
                "full_name_path": kb_doc.folder.full_name_path or kb_doc.folder.name,  # 完整名称路径
                "level": kb_doc.folder.level,
                "path_array": folder_path_array,  # 路径数组（包含每一级的 ID 和名称）
            }
        
        data.append({
            "id": kb_doc.id,
            "tenant_id": kb_doc.tenant_id,
            "kb_id": kb_doc.kb_id,
            "document_id": kb_doc.document_id,
            "folder_id": kb_doc.folder_id,
            "display_name": kb_doc.display_name,  # 显示名称
            "parse_status": kb_doc.parse_status,
            "parse_error": display_error,
            "last_error": display_error,
            "error_source": "web_sync" if web_error_info.get("last_error") else ("pipeline" if kb_doc.parse_error else None),
            "parse_progress": kb_doc.parse_progress,  # 解析进度百分比（0-100）
            "runtime_stage": kb_doc.runtime_stage,
            "runtime_updated_at": kb_doc.runtime_updated_at.isoformat() if kb_doc.runtime_updated_at else None,
            "runtime_models": dict((kb_doc.runtime.effective_config or {}).get("runtime_models") or {})
            if kb_doc.runtime
            else {},
            "chunk_count": kb_doc.chunk_count,
            "summary": kb_doc.summary,
            "metadata": kb_doc.custom_metadata,  # 知识库文档的业务元数据
            "parse_config": kb_doc.parse_config,
            "chunking_config": kb_doc.chunking_config,
            "intelligence_config": kb_doc.intelligence_config,
            "parsing_logs": parsing_logs_map.get(kb_doc.id, []),
            "parse_started_at": kb_doc.parse_started_at.isoformat() if kb_doc.parse_started_at else None,
            "parse_ended_at": kb_doc.parse_ended_at.isoformat() if kb_doc.parse_ended_at else None,
            "parse_duration_milliseconds": kb_doc.parse_duration_milliseconds,
            "markdown_document_id": str(kb_doc.markdown_document_id) if kb_doc.markdown_document_id else None,  # Markdown 文档 ID（用于预览）
            "display_order": kb_doc.display_order,
            "is_enabled": kb_doc.is_enabled,
            "owner_id": kb_doc.owner_id,
            "created_by_id": kb_doc.created_by_id,
            "created_by_name": kb_doc.created_by_name,
            "updated_by_id": kb_doc.updated_by_id,
            "updated_by_name": kb_doc.updated_by_name,
            "created_at": kb_doc.created_at.isoformat() if kb_doc.created_at else None,
            "updated_at": kb_doc.updated_at.isoformat() if kb_doc.updated_at else None,
            "document": {
                "id": kb_doc.document.id,
                "name": kb_doc.document.name,
                "file_type": kb_doc.document.file_type,
                "file_size": kb_doc.document.file_size,
                "mime_type": kb_doc.document.mime_type,
                "content_hash": kb_doc.document.content_hash,
                "metadata": kb_doc.document.metadata_info,  # 物理文档的全局元数据
            },
            "web_sync": (
                {
                    "url": web_error_info.get("url"),
                    "sync_status": web_error_info.get("sync_status"),
                    "last_http_status": web_error_info.get("last_http_status"),
                    "last_error": web_error_info.get("last_error"),
                }
                if web_error_info
                else None
            ),
            # 添加 folder 信息（用于显示文件夹路径）
            "folder": folder_info,
            # 添加标签信息（完整的标签定义）
            "tags": tags_map.get(kb_doc.id, [])  # 获取该文档的所有标签
        })
    
    logger.info(f"查询知识库文档列表: kb_id={kb_id}, total={total}, page={request.page}, tags_loaded={len(tags_map)}")
    
    # 13. 返回响应（标准 REST 格式）
    return {
        "data": data,
        "total": total
    }


@router.post(
    "/documents/detach",
    response_model=dict,
    summary="从知识库移除文档",
    description="从知识库移除文档关联，不会删除文档本身。支持单个或批量操作。"
)
async def detach_documents_from_kb(
    request: DetachDocumentsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    从知识库移除文档关联（统一接口，支持单个和批量）
    
    注意：
    - 只删除 knowledge_base_documents 表的关联记录
    - 不删除 documents 表的物理文档（物理文档可能被其他知识库引用）
    - 会同步清理当前 kb_doc 关联的检索投影与类型化业务表，避免孤儿数据
    
    Args:
        request: 包含 kb_id 和 kb_document_ids
        current_user: 当前用户
        session: 数据库会话
        
    Returns:
        操作结果
        
    Examples:
        单个操作: {"kb_id": "uuid", "kb_document_ids": ["uuid1"]}
        批量操作: {"kb_id": "uuid", "kb_document_ids": ["uuid1", "uuid2", "uuid3"]}
    """
    
    kb_id = request.kb_id
    kb_document_ids = request.kb_document_ids
    
    if not kb_document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少选择一个文档"
        )
    
    # 1. 验证知识库存在且用户有权限
    kb_stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.tenant_id == current_user.tenant_id
    )
    kb_result = await session.execute(kb_stmt)
    kb = kb_result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在"
        )
    
    # 2. 查询所有文档记录（验证存在性和权限）
    stmt = select(KnowledgeBaseDocument).where(
        KnowledgeBaseDocument.id.in_(kb_document_ids),
        KnowledgeBaseDocument.kb_id == kb_id,
        KnowledgeBaseDocument.tenant_id == current_user.tenant_id
    )
    result = await session.execute(stmt)
    kb_docs = result.scalars().all()
    
    if not kb_docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何文档"
        )
    
    # 3. 权限检查：只有所有者可以删除
    # TODO: 后续可以扩展为检查知识库权限
    unauthorized_docs = [doc for doc in kb_docs if doc.owner_id != current_user.id]
    if unauthorized_docs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"无权删除 {len(unauthorized_docs)} 个文档"
        )
    
    # 4. 统一清理类型化业务数据（QA / 表格 / 网页）与检索投影（chunks / embeddings）
    kb_doc_ids = [doc.id for doc in kb_docs]

    # 4.1 Web 类型链路：先删除子表，再删除主表（避免部分环境未配置 FK 约束时残留）
    web_page_rows = (
        await session.execute(
            select(KBWebPage.id).where(
                KBWebPage.tenant_id == current_user.tenant_id,
                KBWebPage.kb_id == kb_id,
                KBWebPage.kb_doc_id.in_(kb_doc_ids),
            )
        )
    ).scalars().all()
    if web_page_rows:
        await session.execute(
            delete(KBWebSyncRun).where(
                KBWebSyncRun.tenant_id == current_user.tenant_id,
                KBWebSyncRun.kb_id == kb_id,
                KBWebSyncRun.kb_web_page_id.in_(web_page_rows),
            )
        )
        await session.execute(
            delete(KBWebSyncSchedule).where(
                KBWebSyncSchedule.tenant_id == current_user.tenant_id,
                KBWebSyncSchedule.kb_id == kb_id,
                KBWebSyncSchedule.kb_web_page_id.in_(web_page_rows),
            )
        )
        await session.execute(
            delete(KBWebPageVersion).where(
                KBWebPageVersion.tenant_id == current_user.tenant_id,
                KBWebPageVersion.kb_id == kb_id,
                KBWebPageVersion.kb_web_page_id.in_(web_page_rows),
            )
        )
        await session.execute(
            delete(KBWebPage).where(
                KBWebPage.tenant_id == current_user.tenant_id,
                KBWebPage.kb_id == kb_id,
                KBWebPage.id.in_(web_page_rows),
            )
        )

    # 4.2 QA / 表格主事实表
    await session.execute(
        delete(KBQARow).where(
            KBQARow.tenant_id == current_user.tenant_id,
            KBQARow.kb_id == kb_id,
            KBQARow.kb_doc_id.in_(kb_doc_ids),
        )
    )
    await session.execute(
        delete(KBTableRow).where(
            KBTableRow.tenant_id == current_user.tenant_id,
            KBTableRow.kb_id == kb_id,
            KBTableRow.kb_doc_id.in_(kb_doc_ids),
        )
    )

    # 4.3 chunks + 检索投影（检索索引无外键，需显式清理）
    chunk_ids = (
        await session.execute(
            select(Chunk.id).where(
                Chunk.tenant_id == current_user.tenant_id,
                Chunk.kb_id == kb_id,
                Chunk.kb_doc_id.in_(kb_doc_ids),
            )
        )
    ).scalars().all()
    if chunk_ids:
        params = {"chunk_ids": list(chunk_ids)}
        subquery = "SELECT id FROM chunk_search_units WHERE chunk_id IN :chunk_ids"
        for sql in [
            f"DELETE FROM pg_chunk_search_unit_vectors WHERE search_unit_id IN ({subquery})",
            f"DELETE FROM pg_chunk_search_unit_lexical_indexes WHERE search_unit_id IN ({subquery})",
            "DELETE FROM chunk_search_units WHERE chunk_id IN :chunk_ids",
        ]:
            delete_stmt = text(sql).bindparams(bindparam("chunk_ids", expanding=True))
            await session.execute(delete_stmt, params)
    await session.execute(
        delete(Chunk).where(
            Chunk.tenant_id == current_user.tenant_id,
            Chunk.kb_id == kb_id,
            Chunk.kb_doc_id.in_(kb_doc_ids),
        )
    )

    # 4.4 删除知识库文档关联记录
    delete_stmt = delete(KnowledgeBaseDocument).where(
        KnowledgeBaseDocument.id.in_(kb_document_ids)
    )
    delete_result = await session.execute(delete_stmt)
    await session.commit()
    
    deleted_count = delete_result.rowcount
    
    logger.info(
        f"从知识库 {kb_id} 移除 {deleted_count} 个文档关联, "
        f"kb_document_ids={kb_document_ids}, user={current_user.id}"
    )
    
    # 5. 返回响应（根据数量调整消息）
    if len(kb_document_ids) == 1:
        message = "文档已从知识库中移除"
    else:
        message = f"已从知识库中移除 {deleted_count} 个文档"
    
    return {
        "success": True,
        "message": message,
        "data": {
            "kb_id": str(kb_id),
            "detached_count": deleted_count,
            "kb_document_ids": [str(id) for id in kb_document_ids]
        }
    }
@router.post(
    "/toggle-enabled",
    summary="启用/禁用文档（支持单个和批量）",
    description="启用或禁用知识库中的文档，禁用后不参与检索。支持单个或批量操作。"
)
async def toggle_documents_enabled(
    request: DocumentToggleEnabledRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    启用/禁用文档（统一接口，支持单个和批量）
    
    Args:
        request: 包含 kb_document_ids 列表和 enabled 状态
        current_user: 当前用户
        session: 数据库会话
        
    Returns:
        操作结果
        
    Examples:
        单个操作: {"kb_document_ids": ["uuid1"], "enabled": true}
        批量操作: {"kb_document_ids": ["uuid1", "uuid2", "uuid3"], "enabled": false}
    """
    from sqlalchemy import update
    
    if not request.kb_document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少选择一个文档"
        )
    
    # 1. 查询所有文档记录（验证权限）
    stmt = select(KnowledgeBaseDocument).where(
        KnowledgeBaseDocument.id.in_(request.kb_document_ids),
        KnowledgeBaseDocument.tenant_id == current_user.tenant_id
    )
    result = await session.execute(stmt)
    kb_docs = result.scalars().all()
    
    if not kb_docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何文档"
        )
    
    # 2. 权限检查：只有所有者可以操作
    # TODO: 后续可以扩展为检查知识库权限
    unauthorized_docs = [doc for doc in kb_docs if doc.owner_id != current_user.id]
    if unauthorized_docs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"无权操作 {len(unauthorized_docs)} 个文档"
        )
    
    # 3. 批量更新启用状态
    stmt = (
        update(KnowledgeBaseDocument)
        .where(KnowledgeBaseDocument.id.in_(request.kb_document_ids))
        .values(
            is_enabled=request.enabled,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
            updated_at=datetime.utcnow()
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    
    updated_count = result.rowcount
    
    logger.info(
        f"更新文档启用状态: count={updated_count}, "
        f"enabled={request.enabled}, user={current_user.id}"
    )
    
    # 4. 返回响应（根据数量调整消息）
    if len(request.kb_document_ids) == 1:
        message = f"文档已{'启用' if request.enabled else '禁用'}"
    else:
        message = f"已{'启用' if request.enabled else '禁用'} {updated_count} 个文档"
    
    return {
        "success": True,
        "message": message,
        "data": {
            "updated_count": updated_count,
            "enabled": request.enabled,
            "kb_document_ids": [str(id) for id in request.kb_document_ids]
        }
    }


class RenameDocumentRequest(BaseModel):
    """重命名文档请求（设置显示名称）"""
    kb_document_id: UUID  # 知识库文档ID
    display_name: str  # 新的显示名称


@router.post(
    "/documents/rename",
    summary="重命名文档（设置显示名称）",
    description="设置文档在当前知识库中的显示名称，不影响物理文件名和其他知识库"
)
async def rename_document(
    request: RenameDocumentRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    重命名文档（设置显示名称）
    
    注意：
    - 只修改 knowledge_base_documents.display_name 字段
    - 不修改 documents.name（物理文件名）
    - 只影响当前知识库的显示，不影响其他知识库
    
    Args:
        request: 包含 kb_document_id 和 display_name
        current_user: 当前用户
        session: 数据库会话
        
    Returns:
        操作结果
    """
    from sqlalchemy import update
    
    # 1. 查询文档记录（验证权限）
    stmt = select(KnowledgeBaseDocument).where(
        KnowledgeBaseDocument.id == request.kb_document_id,
        KnowledgeBaseDocument.tenant_id == current_user.tenant_id
    )
    result = await session.execute(stmt)
    kb_doc = result.scalar_one_or_none()
    
    if not kb_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )
    
    # 2. 权限检查：只有所有者可以重命名
    if kb_doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此文档"
        )
    
    # 3. 验证新名称
    new_name = request.display_name.strip()
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="显示名称不能为空"
        )
    
    if len(new_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="显示名称不能超过255个字符"
        )
    
    # 4. 更新显示名称
    stmt = (
        update(KnowledgeBaseDocument)
        .where(KnowledgeBaseDocument.id == request.kb_document_id)
        .values(
            display_name=new_name,
            updated_by_id=current_user.id,
            updated_by_name=current_user.nickname,
            updated_at=datetime.utcnow()
        )
    )
    await session.execute(stmt)
    await session.commit()
    
    logger.info(
        f"重命名文档: kb_document_id={request.kb_document_id}, "
        f"new_name={new_name}, user={current_user.id}"
    )
    
    return {
        "success": True,
        "message": "重命名成功",
        "data": {
            "kb_document_id": str(request.kb_document_id),
            "display_name": new_name
        }
    }


class UpdateDocumentTagsRequest(BaseModel):
    """更新文档标签请求"""
    kb_document_id: UUID  # 知识库文档ID
    tag_ids: List[UUID]  # 标签ID列表（全量替换）


class UpdateDocumentMetadataRequest(BaseModel):
    """更新文档元数据请求"""
    kb_document_id: UUID  # 知识库文档ID
    metadata: dict  # 自定义元数据键值对
    merge_metadata: bool = False  # 是否合并元数据（False=全量覆盖，True=合并模式）


class UpdateDocumentTagsAndMetadataRequest(BaseModel):
    """更新文档标签和元数据请求"""
    kb_document_id: UUID  # 知识库文档ID
    metadata: dict  # 自定义元数据键值对
    tag_ids: List[UUID]  # 标签ID列表（全量替换）
    intelligence_config: Optional[dict] = None  # 文档级智能配置（如文档补充说明）
    merge_metadata: bool = False  # 是否合并元数据（False=全量覆盖，True=合并模式）


@router.post(
    "/documents/update-tags",
    summary="更新文档标签",
    description="更新知识库文档的标签，全量替换模式。"
)
async def update_document_tags(
    request: UpdateDocumentTagsRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    更新文档标签（只更新标签）
    """
    from services.document_service import KBDocumentService
    
    service = KBDocumentService(session)
    
    try:
        result = await service.update_tags(
            kb_doc_id=request.kb_document_id,
            tag_ids=request.tag_ids,
            current_user=current_user,
            session=session
        )
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )

        await session.commit()

        logger.info(
            f"更新文档标签: kb_document_id={request.kb_document_id}, "
            f"user={current_user.id}, tag_count={len(request.tag_ids)}"
        )

        return {
            "success": True,
            "message": "文档标签已更新",
            "data": result
        }

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"更新文档标签失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )


@router.post(
    "/documents/update-metadata",
    summary="更新文档元数据",
    description="更新知识库文档的元数据。支持全量覆盖和合并两种模式。"
)
async def update_document_metadata(
    request: UpdateDocumentMetadataRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    更新文档元数据（只更新元数据）
    """
    from services.document_service import KBDocumentService
    
    service = KBDocumentService(session)
    
    try:
        result = await service.update_metadata(
            kb_doc_id=request.kb_document_id,
            metadata=request.metadata,
            current_user=current_user,
            session=session,
            merge_metadata=request.merge_metadata
        )
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )

        await session.commit()

        logger.info(
            f"更新文档元数据: kb_document_id={request.kb_document_id}, "
            f"user={current_user.id}, merge_mode={request.merge_metadata}"
        )

        return {
            "success": True,
            "message": "文档元数据已更新",
            "data": result
        }

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"更新文档元数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )


@router.post(
    "/documents/update-tags-and-metadata",
    summary="更新文档标签和元数据",
    description="同时更新知识库文档的标签和元数据。元数据支持全量覆盖和合并两种模式，标签始终为全量替换。"
)
async def update_document_tags_and_metadata(
    request: UpdateDocumentTagsAndMetadataRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    更新文档标签和元数据（同时更新两者）
    """
    from services.document_service import KBDocumentService
    
    service = KBDocumentService(session)
    
    try:
        result = await service.update_tags_and_metadata(
            kb_doc_id=request.kb_document_id,
            metadata=request.metadata,
            tag_ids=request.tag_ids,
            intelligence_config=request.intelligence_config,
            current_user=current_user,
            session=session,
            merge_metadata=request.merge_metadata
        )
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )

        await session.commit()

        logger.info(
            f"更新文档标签和元数据: kb_document_id={request.kb_document_id}, "
            f"user={current_user.id}, merge_mode={request.merge_metadata}"
        )

        return {
            "success": True,
            "message": "文档标签和元数据已更新",
            "data": result
        }

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"更新文档标签和元数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )
@router.post(
    "/documents/reparse",
    summary="重新解析文档",
    description="针对指定的知识库文档，重新触发异步解析任务。会清除旧的切片。"
)
async def reparse_documents(
    request: ReparseDocumentRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    redis: Redis = Depends(get_redis)
):
    """重新解析文档。"""
    service = KBDocumentParseService(session)
    return await service.reparse_documents(
        kb_document_ids=request.kb_document_ids,
        current_user=current_user,
        redis=redis,
    )


class CancelParseRequest(BaseModel):
    """取消解析请求"""
    kb_document_ids: List[UUID]


@router.post(
    "/documents/cancel-parse",
    summary="取消解析任务",
    description="取消正在进行的解析任务。queued 状态立即取消，processing 状态优雅取消。"
)
async def cancel_parse(
    request: CancelParseRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    redis: Redis = Depends(get_redis)
):
    """
    取消解析任务（混合方案）

    - queued 状态：立即取消（任务还未开始执行）
    - processing 状态：优雅取消（设置取消标志，Worker 自己检查并退出）
    """
    service = KBDocumentParseService(session)
    return await service.cancel_parse(
        kb_document_ids=request.kb_document_ids,
        current_user=current_user,
        redis=redis,
    )


# ==================== Markdown 预览 API ====================

class GetMarkdownPreviewRequest(BaseModel):
    """获取 Markdown 预览请求"""
    kb_doc_id: UUID


@router.post(
    "/retrieval-test",
    summary="执行知识库检索测试",
    description="按当前检索参数执行一次真实检索，支持目录树、标签、元数据等硬过滤。"
)
async def run_retrieval_test(
    request: RetrievalTestRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """执行知识库检索测试。"""

    kb_stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == request.kb_id,
        KnowledgeBase.tenant_id == current_user.tenant_id,
    )
    kb = (await session.execute(kb_stmt)).scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")

    service = HybridRetrievalService(session)
    raw_config = request.config.model_dump(exclude_none=True)
    raw_config.setdefault("debug_trace_level", "detailed")
    result = await service.search(
        current_user=current_user,
        kb=kb,
        query=request.query,
        raw_config=raw_config,
        raw_filters=request.filters.model_dump(exclude_none=True) if request.filters else None,
        query_rewrite_context=request.query_rewrite_context,
    )
    # 检索测试 API 面向调试与审计，主结果只返回完整上下文内容，避免 preview 字段造成误解。
    response_items = [{key: value for key, value in item.items() if key != "snippet"} for item in result["items"]]
    return ResponseBuilder.build_success(
        data={
            "items": response_items,
            "elapsed_ms": result["elapsed_ms"],
            "query_analysis": result.get("query_analysis") or {},
            "debug": result.get("debug") or {},
        },
        message="检索测试完成",
    )


@router.post(
    "/documents/get-markdown-preview",
    response_model=dict,
    summary="获取文档的 Markdown 预览",
    description="获取转换后的 Markdown 文档内容，用于前端预览（适用于 Word、Excel、PPT 等文档）"
)
async def get_markdown_preview(
    request: GetMarkdownPreviewRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    获取文档的 Markdown 预览内容
    
    流程：
    1. 查询 KnowledgeBaseDocument
    2. 检查是否有 markdown_document_id
    3. 查询 Markdown 文档记录
    4. 从存储获取 Markdown 内容
    5. 返回内容
    """
    from core.storage import get_storage_driver
    
    kb_doc_id = request.kb_doc_id
    
    # 1. 查询 KnowledgeBaseDocument
    stmt = select(KnowledgeBaseDocument).where(
        KnowledgeBaseDocument.id == kb_doc_id,
        KnowledgeBaseDocument.tenant_id == current_user.tenant_id
    )
    result = await session.execute(stmt)
    kb_doc = result.scalar_one_or_none()
    
    if not kb_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )
    
    # 2. 检查是否有 markdown_document_id
    if not kb_doc.markdown_document_id:
        return {
            "data": {
                "has_markdown": False,
                "message": "该文档类型不支持 Markdown 预览"
            }
        }
    
    # 3. 查询 Markdown 文档
    md_stmt = select(Document).where(
        Document.id == kb_doc.markdown_document_id,
        Document.tenant_id == current_user.tenant_id
    )
    md_result = await session.execute(md_stmt)
    md_doc = md_result.scalar_one_or_none()
    
    if not md_doc:
        return {
            "data": {
                "has_markdown": False,
                "message": "Markdown 文档不存在"
            }
        }
    
    # 4. 从存储获取 Markdown 内容
    storage = get_storage_driver()
    try:
        content_bytes = await storage.get_content(md_doc.file_key)
        markdown_content = content_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"获取 Markdown 内容失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 Markdown 内容失败: {str(e)}"
        )
    
    # 5. 返回内容（标准 REST 响应格式）
    return {
        "data": {
            "has_markdown": True,
            "markdown_content": markdown_content,
            "markdown_document_id": str(md_doc.id),
            "file_name": md_doc.name,
            "file_size": md_doc.file_size,
            "created_at": md_doc.created_at.isoformat() if md_doc.created_at else None
        }
    }
