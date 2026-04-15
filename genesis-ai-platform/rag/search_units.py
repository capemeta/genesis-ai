"""
检索投影生成与清理工具

当前阶段先负责：
- 从 canonical chunks 派生 chunk_search_units
- 清理 chunk 对应的检索投影

暂不负责：
- PG 向量表写入
- PG 全文索引表写入
"""
import hashlib
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID as PyUUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.chunk import Chunk
from models.chunk_search_unit import ChunkSearchUnit
from rag.doc_summary_utils import prepare_doc_summary_text
from rag.utils.token_utils import count_tokens
from utils.qa_markdown import build_qa_markdown_text


def normalize_qa_retrieval_config(retrieval_config: Dict[str, Any]) -> Dict[str, Any]:
    """规范化 QA 检索配置，避免各调用方重复兜底。"""
    qa_cfg = dict((retrieval_config or {}).get("qa") or {})
    index_mode = str(qa_cfg.get("index_mode") or "question_only").strip()
    if index_mode not in {"question_only", "question_answer"}:
        index_mode = "question_only"

    def _to_weight(value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, number))

    query_weight = _to_weight(qa_cfg.get("query_weight"), 1.0 if index_mode == "question_only" else 0.8)
    answer_weight = _to_weight(qa_cfg.get("answer_weight"), 0.0 if index_mode == "question_only" else 0.2)
    total = query_weight + answer_weight
    if index_mode == "question_only":
        query_weight = 1.0
        answer_weight = 0.0
    elif total > 0:
        query_weight = query_weight / total
        answer_weight = answer_weight / total
    else:
        query_weight = 0.8
        answer_weight = 0.2

    return {
        "index_mode": index_mode,
        "query_weight": round(query_weight, 4),
        "answer_weight": round(answer_weight, 4),
        "enable_keyword_recall": qa_cfg.get("enable_keyword_recall") is not False,
        "enable_category_filter": qa_cfg.get("enable_category_filter") is not False,
        "enable_tag_filter": qa_cfg.get("enable_tag_filter") is not False,
    }


def build_search_units_for_chunks(
    *,
    chunks: Iterable[Chunk],
    kb_type: str,
    retrieval_config: Optional[Dict[str, Any]] = None,
    kb_doc_summary: Optional[str] = None,
) -> List[ChunkSearchUnit]:
    """根据 chunk 列表派生检索投影。"""
    chunk_list = [chunk for chunk in chunks if chunk.id is not None and bool(chunk.is_active)]
    if not chunk_list:
        return []

    if str(kb_type or "").strip() == "qa":
        units = _build_qa_search_units(chunk_list, retrieval_config or {})
    else:
        units = _build_default_search_units(
            chunk_list,
            kb_type=str(kb_type or "").strip(),
            retrieval_config=retrieval_config or {},
        )
    units.extend(
        _build_doc_summary_search_units(
            chunk_list,
            kb_doc_summary=kb_doc_summary,
            retrieval_config=retrieval_config,
        )
    )
    return units


async def delete_search_projections_for_chunk_ids(
    session: AsyncSession,
    chunk_ids: List[int],
) -> None:
    """删除 chunk 对应的检索投影，避免遗留孤儿数据。"""
    if not chunk_ids:
        return

    params = {"chunk_ids": chunk_ids}
    subquery = "SELECT id FROM chunk_search_units WHERE chunk_id IN :chunk_ids"
    for sql in [
        f"DELETE FROM pg_chunk_search_unit_vectors WHERE search_unit_id IN ({subquery})",
        f"DELETE FROM pg_chunk_search_unit_lexical_indexes WHERE search_unit_id IN ({subquery})",
        "DELETE FROM chunk_search_units WHERE chunk_id IN :chunk_ids",
    ]:
        stmt = text(sql).bindparams(bindparam("chunk_ids", expanding=True))
        await session.execute(stmt, params)

    # 历史上如果 search_unit 先被删、索引表后删失败，会遗留 search_unit_id 对不上的孤儿索引。
    # 这类脏数据会让“索引表有记录，但检索 join 不到任何结果”，因此在重建阶段顺手做一次兜底清理。
    orphan_cleanup_sqls = [
        """
        DELETE FROM pg_chunk_search_unit_vectors vec
        WHERE NOT EXISTS (
            SELECT 1
            FROM chunk_search_units su
            WHERE su.id = vec.search_unit_id
        )
        """,
        """
        DELETE FROM pg_chunk_search_unit_lexical_indexes lex
        WHERE NOT EXISTS (
            SELECT 1
            FROM chunk_search_units su
            WHERE su.id = lex.search_unit_id
        )
        """,
    ]
    for sql in orphan_cleanup_sqls:
        await session.execute(text(sql))


def _build_default_search_units(
    chunks: List[Chunk],
    *,
    kb_type: str,
    retrieval_config: Dict[str, Any],
) -> List[ChunkSearchUnit]:
    """为通用文档 / 表格 / 网页等知识库生成默认检索投影。"""
    units: List[ChunkSearchUnit] = []
    table_schema_context = _build_table_schema_context(retrieval_config) if kb_type == "table" else {}
    for chunk in chunks:
        metadata = dict(chunk.metadata_info or {})
        if not _should_emit_search_unit(metadata):
            continue

        search_text = str(chunk.content or "").strip()
        if not search_text:
            continue

        search_scope = _resolve_default_scope(chunk, metadata, kb_type=kb_type)
        search_unit_metadata = {
            "source_type": chunk.source_type,
            "source_chunk_role": metadata.get("chunk_role"),
            "source_node_id": metadata.get("node_id"),
            "source_parent_node_id": metadata.get("parent_id"),
            "parent_chunk_id": chunk.parent_id,
            "is_leaf": bool(metadata.get("is_leaf", True)),
            "display_enabled": bool(chunk.display_enabled),
            "chunk_strategy": metadata.get("chunk_strategy"),
            "should_vectorize": bool(metadata.get("should_vectorize", True)),
            "exclude_from_retrieval": bool(metadata.get("exclude_from_retrieval", False)),
        }
        if str(kb_type or "").strip() == "table":
            search_text = _build_table_contextual_search_text(
                chunk=chunk,
                metadata=metadata,
                schema_context=table_schema_context,
                base_text=search_text,
            )
            # 表格知识库的过滤应作用于行级检索投影，而不是仅停留在文档级 metadata。
            filter_fields = dict(metadata.get("filter_fields") or {})
            if filter_fields:
                search_unit_metadata["filter_fields"] = {
                    str(key): str(value).strip()
                    for key, value in filter_fields.items()
                    if str(key).strip() and str(value or "").strip()
                }
            if metadata.get("sheet_name"):
                search_unit_metadata["sheet_name"] = str(metadata.get("sheet_name"))
            if metadata.get("row_index") is not None:
                search_unit_metadata["row_index"] = int(metadata.get("row_index") or 0)
            if isinstance(metadata.get("field_names"), list):
                search_unit_metadata["field_names"] = [
                    str(item).strip()
                    for item in list(metadata.get("field_names") or [])
                    if str(item).strip()
                ]
            if metadata.get("row_identity_text"):
                search_unit_metadata["row_identity_text"] = str(metadata.get("row_identity_text"))
            if table_schema_context:
                search_unit_metadata.update(table_schema_context)
            search_unit_metadata["contextual_retrieval_version"] = "table_v1"
        units.append(
            _build_search_unit_record(
                chunk=chunk,
                search_scope=search_scope,
                search_text=search_text,
                is_primary=bool(metadata.get("is_leaf", True)),
                priority=_resolve_default_priority(search_scope),
                metadata=search_unit_metadata,
            )
        )
        units.extend(_build_enhancement_search_units(chunk, metadata, kb_type=kb_type))
    if kb_type == "table":
        units.extend(_build_table_row_group_search_units(chunks, retrieval_config=retrieval_config))
    return units


def _build_table_row_group_search_units(
    chunks: List[Chunk],
    *,
    retrieval_config: Dict[str, Any],
) -> List[ChunkSearchUnit]:
    """为表格知识库生成 row_group 检索投影。"""

    grouped_chunks: Dict[str, List[Chunk]] = {}
    for chunk in chunks:
        if str(chunk.source_type or "").strip() != "table":
            continue
        group_key = str(chunk.content_group_id or dict(chunk.metadata_info or {}).get("table_row_id") or "").strip()
        if not group_key:
            continue
        grouped_chunks.setdefault(group_key, []).append(chunk)

    if not grouped_chunks:
        return []

    schema_context = _build_table_schema_context(retrieval_config)
    units: List[ChunkSearchUnit] = []
    for group_chunks in grouped_chunks.values():
        ordered_chunks = sorted(
            group_chunks,
            key=lambda item: (
                0 if bool(dict(item.metadata_info or {}).get("is_leaf", True)) else 1,
                int(item.id),
            ),
        )
        anchor_chunk = ordered_chunks[0]
        anchor_metadata = dict(anchor_chunk.metadata_info or {})
        search_text = _build_table_row_group_text(group_chunks, schema_context=schema_context)
        if not search_text:
            continue
        metadata = {
            "source_type": "table",
            "projection_type": "row_group",
            "contextual_retrieval_version": "table_v1",
            "sheet_name": str(anchor_metadata.get("sheet_name") or "").strip() or None,
            "row_identity_text": str(anchor_metadata.get("row_identity_text") or "").strip() or None,
            "field_names": [
                str(item).strip()
                for item in list(anchor_metadata.get("field_names") or [])
                if str(item).strip()
            ],
            "filter_fields": {
                str(key): str(value).strip()
                for key, value in dict(anchor_metadata.get("filter_fields") or {}).items()
                if str(key).strip() and str(value or "").strip()
            },
            "table_context_text": schema_context.get("table_context_text"),
            "dimension_field_names": list(schema_context.get("dimension_field_names") or []),
            "metric_field_names": list(schema_context.get("metric_field_names") or []),
            "identifier_field_names": list(schema_context.get("identifier_field_names") or []),
            "row_explanation_text": schema_context.get("row_explanation_text"),
            "dimension_explanation_text": schema_context.get("dimension_explanation_text"),
            "metric_explanation_text": schema_context.get("metric_explanation_text"),
            "header_context_text": schema_context.get("header_context_text"),
            "row_group_chunk_count": len(group_chunks),
            # row_group 当前先只走全文辅路，避免过早扩大表格向量噪声。
            "should_vectorize": False,
            "display_enabled": bool(anchor_chunk.display_enabled),
        }
        units.append(
            _build_search_unit_record(
                chunk=anchor_chunk,
                search_scope="row_group",
                search_text=search_text,
                is_primary=False,
                priority=26,
                metadata=metadata,
            )
        )
    return units


def _build_doc_summary_search_units(
    chunks: List[Chunk],
    *,
    kb_doc_summary: Optional[str],
    retrieval_config: Optional[Dict[str, Any]] = None,
) -> List[ChunkSearchUnit]:
    """为文档摘要生成正式检索投影。"""

    summary_text = prepare_doc_summary_text(
        kb_doc_summary,
        retrieval_config=retrieval_config,
    )
    if not summary_text or not chunks:
        return []

    # 使用稳定 anchor chunk 挂载 doc_summary，避免新增独立表或虚拟 chunk。
    anchor_chunk = min(chunks, key=lambda item: int(item.id))
    return [
        _build_search_unit_record(
            chunk=anchor_chunk,
            search_scope="doc_summary",
            search_text=summary_text,
            is_primary=False,
            priority=35,
            metadata={
                "source_type": str(anchor_chunk.source_type or "document"),
                "projection_type": "kb_doc_summary",
                "should_vectorize": False,
                "display_enabled": bool(anchor_chunk.display_enabled),
            },
        )
    ]


def _build_qa_search_units(
    chunks: List[Chunk],
    retrieval_config: Dict[str, Any],
) -> List[ChunkSearchUnit]:
    """为 QA chunk 生成 question / answer 检索投影。"""
    qa_config = normalize_qa_retrieval_config(retrieval_config)
    grouped: Dict[str, List[Chunk]] = {}
    for chunk in chunks:
        metadata = dict(chunk.metadata_info or {})
        qa_row_id = str(metadata.get("qa_row_id") or chunk.content_group_id or "").strip()
        if not qa_row_id:
            continue
        grouped.setdefault(qa_row_id, []).append(chunk)

    units: List[ChunkSearchUnit] = []
    for qa_row_id, group_chunks in grouped.items():
        row_chunks = [
            chunk for chunk in group_chunks
            if str(dict(chunk.metadata_info or {}).get("chunk_role") or "") == "qa_row"
        ]
        if not row_chunks:
            continue

        row_chunks.sort(key=lambda item: 0 if bool(dict(item.metadata_info or {}).get("is_leaf", False)) else 1)
        row_chunk = row_chunks[0]
        row_meta = dict(row_chunk.metadata_info or {})
        question = str(row_meta.get("question") or "").strip()
        aliases = [str(v).strip() for v in (row_meta.get("similar_questions") or []) if str(v).strip()]
        tags = [str(v).strip() for v in (row_meta.get("tags") or []) if str(v).strip()]
        category = str(row_meta.get("category") or "").strip()

        question_text = _build_qa_question_text(
            question=question,
            aliases=aliases,
            tags=tags,
            category=category,
        )
        if question_text:
            units.append(
                _build_search_unit_record(
                    chunk=row_chunk,
                    search_scope="question",
                    search_text=question_text,
                    is_primary=True,
                    priority=10,
                    metadata={
                        "source_type": "qa",
                        "source_chunk_role": row_meta.get("chunk_role"),
                        "source_node_id": row_meta.get("node_id"),
                        "qa_row_id": qa_row_id,
                        "qa_fields": {
                            "category": category or None,
                            "tags": list(tags),
                        },
                        # QA 问句向量只使用纯问题文本，避免被相似问题/分类/标签稀释语义中心。
                        "vector_text": question,
                        # QA 问句全文检索同样优先使用纯问题文本，避免完全同问被辅助字段稀释。
                        "lexical_text": question,
                        "question_text": question,
                        "similar_questions": list(aliases),
                        "index_mode_snapshot": qa_config["index_mode"],
                        "query_weight_snapshot": qa_config["query_weight"],
                        "answer_weight_snapshot": qa_config["answer_weight"],
                        "enable_keyword_recall_snapshot": bool(qa_config["enable_keyword_recall"]),
                        "enable_category_filter_snapshot": bool(qa_config["enable_category_filter"]),
                        "enable_tag_filter_snapshot": bool(qa_config["enable_tag_filter"]),
                    },
                )
            )

        if qa_config["index_mode"] != "question_answer":
            continue

        answer_source_chunks = [
            chunk for chunk in group_chunks
            if str(dict(chunk.metadata_info or {}).get("chunk_role") or "") == "qa_answer_fragment"
        ]
        if not answer_source_chunks:
            answer_source_chunks = [row_chunk]

        answer_source_chunks.sort(
            key=lambda item: int(dict(item.metadata_info or {}).get("answer_part_index") or 0)
        )
        for chunk in answer_source_chunks:
            metadata = dict(chunk.metadata_info or {})
            answer_text = _build_qa_answer_text(
                question=question,
                chunk=chunk,
            )
            if not answer_text:
                continue
            units.append(
                _build_search_unit_record(
                    chunk=chunk,
                    search_scope="answer",
                    search_text=answer_text,
                    is_primary=False,
                    priority=20,
                    metadata={
                        "source_type": "qa",
                        "source_chunk_role": metadata.get("chunk_role"),
                        "source_node_id": metadata.get("node_id"),
                        "source_parent_node_id": metadata.get("parent_id"),
                        "qa_row_id": qa_row_id,
                        "qa_fields": {
                            "category": category or None,
                            "tags": list(tags),
                        },
                        "lexical_text": answer_text,
                        "question_text": question,
                        "answer_part_index": metadata.get("answer_part_index"),
                        "answer_part_total": metadata.get("answer_part_total"),
                        "index_mode_snapshot": qa_config["index_mode"],
                        "query_weight_snapshot": qa_config["query_weight"],
                        "answer_weight_snapshot": qa_config["answer_weight"],
                        "enable_keyword_recall_snapshot": bool(qa_config["enable_keyword_recall"]),
                        "enable_category_filter_snapshot": bool(qa_config["enable_category_filter"]),
                        "enable_tag_filter_snapshot": bool(qa_config["enable_tag_filter"]),
                    },
                )
            )

    return units


def _should_emit_search_unit(metadata: Dict[str, Any]) -> bool:
    """判断当前 chunk 是否应派生检索投影。"""
    if bool(metadata.get("exclude_from_retrieval", False)):
        return False
    return bool(metadata.get("should_vectorize", True))


def _resolve_default_scope(chunk: Chunk, metadata: Dict[str, Any], *, kb_type: str) -> str:
    """根据类型与 chunk 角色确定默认检索域。"""
    if chunk.source_type == "table" or kb_type == "table":
        role = str(metadata.get("chunk_role") or "").strip()
        if role == "excel_row_fragment":
            return "row_fragment"
        return "row"
    if chunk.source_type == "web" or kb_type == "web":
        return "page_body"
    return "default"


def _resolve_default_priority(search_scope: str) -> int:
    """默认检索优先级。"""
    priority_map = {
        "question": 10,
        "answer": 20,
        "summary": 25,
        "keyword": 35,
        "row": 30,
        "row_group": 26,
        "row_fragment": 40,
        "page_body": 50,
        "default": 100,
    }
    return priority_map.get(search_scope, 100)


def _build_enhancement_search_units(
    chunk: Chunk,
    metadata: Dict[str, Any],
    *,
    kb_type: str,
) -> List[ChunkSearchUnit]:
    """基于 enhancement 元数据派生附加检索投影。"""
    enhancement = dict(metadata.get("enhancement") or {})
    units: List[ChunkSearchUnit] = []
    should_vectorize = bool(metadata.get("should_vectorize", True))
    exclude_from_retrieval = bool(metadata.get("exclude_from_retrieval", False))
    base_metadata = {
        "source_type": chunk.source_type,
        "source_chunk_role": metadata.get("chunk_role"),
        "source_node_id": metadata.get("node_id"),
        "source_parent_node_id": metadata.get("parent_id"),
        "parent_chunk_id": chunk.parent_id,
        "is_leaf": bool(metadata.get("is_leaf", True)),
        "display_enabled": bool(chunk.display_enabled),
        "chunk_strategy": metadata.get("chunk_strategy"),
        "source_scope": "enhancement",
        "should_vectorize": should_vectorize,
        "exclude_from_retrieval": exclude_from_retrieval,
    }

    summary_text = str(chunk.summary or enhancement.get("summary") or "").strip()
    if summary_text:
        units.append(
            _build_search_unit_record(
                chunk=chunk,
                search_scope="summary",
                search_text=summary_text,
                is_primary=False,
                priority=_resolve_default_priority("summary"),
                metadata={
                    **base_metadata,
                    "projection_type": "summary",
                    "should_vectorize": should_vectorize,
                },
            )
        )

    if str(kb_type or "").strip() != "qa":
        for index, question in enumerate(list(enhancement.get("questions") or []), start=1):
            question_text = str(question or "").strip()
            if not question_text:
                continue
            units.append(
                _build_search_unit_record(
                    chunk=chunk,
                    search_scope="question",
                    search_text=question_text,
                    is_primary=False,
                    priority=_resolve_default_priority("question"),
                    metadata={
                        **base_metadata,
                        "projection_type": "enhancement_question",
                        "question_index": index,
                        "should_vectorize": should_vectorize,
                    },
                )
            )

    keyword_values = [str(item).strip() for item in list(enhancement.get("keywords") or []) if str(item).strip()]
    if keyword_values:
        units.append(
            _build_search_unit_record(
                chunk=chunk,
                search_scope="keyword",
                search_text="\n".join(keyword_values),
                is_primary=False,
                priority=_resolve_default_priority("keyword"),
                metadata={
                    **base_metadata,
                    "projection_type": "keyword",
                    "keyword_count": len(keyword_values),
                    # 关键词投影默认只参与全文检索，不参与向量化。
                    "should_vectorize": False,
                },
            )
        )

    return units


def _build_search_unit_record(
    *,
    chunk: Chunk,
    search_scope: str,
    search_text: str,
    is_primary: bool,
    priority: int,
    metadata: Dict[str, Any],
) -> ChunkSearchUnit:
    """构建检索投影 ORM 对象。"""
    normalized_text = str(search_text or "").strip()
    return ChunkSearchUnit(
        tenant_id=chunk.tenant_id,
        kb_id=chunk.kb_id,
        chunk_id=int(chunk.id),
        kb_doc_id=chunk.kb_doc_id,
        document_id=chunk.document_id,
        content_group_id=chunk.content_group_id,
        search_scope=search_scope,
        search_text=normalized_text,
        search_text_hash=hashlib.sha256(normalized_text.encode("utf-8")).hexdigest(),
        token_count=count_tokens(normalized_text),
        text_length=len(normalized_text),
        is_active=True,
        is_primary=is_primary,
        priority=priority,
        metadata_info=metadata,
    )


def _build_qa_question_text(
    *,
    question: str,
    aliases: List[str],
    tags: List[str],
    category: str,
) -> str:
    """构造 QA 问题侧检索文本。"""
    parts: List[str] = []
    if question:
        parts.extend(["## 问题", question])
    if aliases:
        parts.append("")
        parts.append("## 相似问题")
        parts.extend([f"- {item}" for item in aliases])
    if category:
        parts.extend(["", "## 分类", category])
    if tags:
        parts.append("")
        parts.append("## 标签")
        parts.extend([f"- {item}" for item in tags])
    return "\n".join(parts).strip()


def _build_qa_answer_text(
    *,
    question: str,
    chunk: Chunk,
) -> str:
    """构造 QA 答案侧检索文本。"""
    answer = _extract_qa_answer_from_blocks(chunk.content_blocks)
    if not answer:
        answer = str(chunk.content or "").strip()
    if not answer:
        return ""
    return build_qa_markdown_text(
        question=question,
        answer=answer,
        similar_questions=[],
        category="",
        tags=[],
    )


def _extract_qa_answer_from_blocks(content_blocks: Any) -> str:
    """从 QA content_blocks 中提取答案正文，避免答案检索文本混入多余元数据。"""
    blocks = list(content_blocks or [])
    answer_lines: List[str] = []
    in_answer_section = False
    for block in blocks:
        text = str((block or {}).get("text") or "").strip()
        if not text:
            continue
        if text == "## 答案":
            in_answer_section = True
            continue
        if in_answer_section and text.startswith("## "):
            break
        if in_answer_section:
            answer_lines.append(text)
    return "\n".join(answer_lines).strip()


def _build_table_schema_context(retrieval_config: Dict[str, Any]) -> Dict[str, Any]:
    """从表结构配置提炼表头、维度和指标解释，供表格检索增强复用。"""

    table_retrieval = dict((retrieval_config or {}).get("table") or {})
    table_schema = dict(table_retrieval.get("schema") or {})
    columns = list(table_schema.get("columns") or [])
    if not columns:
        return {}

    header_parts: List[str] = []
    dimension_fields: List[str] = []
    metric_fields: List[str] = []
    identifier_fields: List[str] = []
    for column in columns:
        column_name = str((column or {}).get("name") or "").strip()
        if not column_name:
            continue
        aliases = [
            str(item).strip()
            for item in list((column or {}).get("aliases") or [])
            if str(item or "").strip()
        ]
        role = str((column or {}).get("role") or "").strip().lower()
        if role in {"dimension", "entity", "identifier"}:
            dimension_fields.append(column_name)
        if role == "identifier":
            identifier_fields.append(column_name)
        if bool((column or {}).get("aggregatable")) or role == "content":
            metric_fields.append(column_name)
        alias_text = f"（别名: {'、'.join(aliases[:4])}）" if aliases else ""
        header_parts.append(f"{column_name}{alias_text}")

    header_context_text = f"表头: {'；'.join(header_parts[:12])}" if header_parts else ""
    table_context_parts: List[str] = []
    if header_context_text:
        table_context_parts.append(header_context_text)
    if dimension_fields:
        table_context_parts.append(f"维度字段: {'、'.join(dimension_fields[:8])}")
    if metric_fields:
        table_context_parts.append(f"指标字段: {'、'.join(metric_fields[:8])}")
    row_explanation_parts: List[str] = []
    dimension_explanation_parts: List[str] = []
    metric_explanation_parts: List[str] = []
    if identifier_fields:
        row_explanation_parts.append(f"唯一标识字段: {'、'.join(identifier_fields[:6])}")
    if dimension_fields:
        row_explanation_parts.append(f"这类记录通常通过维度字段定位: {'、'.join(dimension_fields[:6])}")
        dimension_explanation_parts.append(f"维度字段用于定位一条记录属于哪个对象、地区、时间或分类，例如：{'、'.join(dimension_fields[:6])}")
    if metric_fields:
        row_explanation_parts.append(f"这类记录通常通过指标字段回答数值或状态问题: {'、'.join(metric_fields[:6])}")
        metric_explanation_parts.append(f"指标字段用于回答数值、状态或结果问题，例如：{'、'.join(metric_fields[:6])}")
    if identifier_fields and dimension_fields:
        dimension_explanation_parts.append(
            f"查询时通常先用 {'、'.join(dimension_fields[:4])} 缩小范围，再用 {'、'.join(identifier_fields[:4])} 确认具体记录"
        )
    if dimension_fields and metric_fields:
        metric_explanation_parts.append(
            f"定位到 {'、'.join(dimension_fields[:4])} 后，更适合用 {'、'.join(metric_fields[:4])} 回答指标类问题"
        )
    return {
        "header_context_text": header_context_text,
        "dimension_field_names": list(dict.fromkeys(dimension_fields)),
        "metric_field_names": list(dict.fromkeys(metric_fields)),
        "identifier_field_names": list(dict.fromkeys(identifier_fields)),
        "table_context_text": "\n".join(table_context_parts).strip(),
        "row_explanation_text": "\n".join(row_explanation_parts).strip(),
        "dimension_explanation_text": "\n".join(dimension_explanation_parts).strip(),
        "metric_explanation_text": "\n".join(metric_explanation_parts).strip(),
    }


def _build_table_row_group_text(
    chunks: List[Chunk],
    *,
    schema_context: Dict[str, Any],
) -> str:
    """构造表格 row_group 投影文本，补充表头与指标维度解释。"""

    ordered_chunks = sorted(chunks, key=lambda item: int(item.id))
    anchor_metadata = dict(ordered_chunks[0].metadata_info or {})
    parts: List[str] = []
    sheet_name = str(anchor_metadata.get("sheet_name") or "").strip()
    row_identity_text = str(anchor_metadata.get("row_identity_text") or "").strip()
    field_names = [
        str(item).strip()
        for item in list(anchor_metadata.get("field_names") or [])
        if str(item).strip()
    ]
    if sheet_name:
        parts.append(f"工作表: {sheet_name}")
    if row_identity_text:
        parts.append(f"行定位: {row_identity_text}")
    if field_names:
        parts.append(f"当前行字段: {'、'.join(field_names[:12])}")
    if schema_context.get("table_context_text"):
        parts.append(str(schema_context.get("table_context_text")))
    if schema_context.get("row_explanation_text"):
        parts.append(str(schema_context.get("row_explanation_text")))
    if schema_context.get("dimension_explanation_text"):
        parts.append(str(schema_context.get("dimension_explanation_text")))
    if schema_context.get("metric_explanation_text"):
        parts.append(str(schema_context.get("metric_explanation_text")))

    combined_chunk_text = "\n".join(
        str(chunk.content or "").strip()
        for chunk in ordered_chunks
        if str(chunk.content or "").strip()
    ).strip()
    if combined_chunk_text:
        parts.append(combined_chunk_text)
    return "\n".join(part for part in parts if part).strip()


def _build_table_contextual_search_text(
    *,
    chunk: Chunk,
    metadata: Dict[str, Any],
    schema_context: Dict[str, Any],
    base_text: str,
) -> str:
    """为表格检索投影补充表头、维度和指标上下文。"""

    parts: List[str] = []
    sheet_name = str(metadata.get("sheet_name") or "").strip()
    row_identity_text = str(metadata.get("row_identity_text") or "").strip()
    field_names = [
        str(item).strip()
        for item in list(metadata.get("field_names") or [])
        if str(item).strip()
    ]
    filter_fields = {
        str(key).strip(): str(value).strip()
        for key, value in dict(metadata.get("filter_fields") or {}).items()
        if str(key).strip() and str(value or "").strip()
    }
    chunk_role = str(metadata.get("chunk_role") or "").strip()

    if sheet_name:
        parts.append(f"工作表: {sheet_name}")
    if row_identity_text:
        parts.append(f"行定位: {row_identity_text}")
    if field_names:
        parts.append(f"当前字段: {'、'.join(field_names[:12])}")
    if filter_fields:
        parts.append("筛选值: " + "；".join(f"{key}={value}" for key, value in list(filter_fields.items())[:8]))
    if schema_context.get("header_context_text"):
        parts.append(str(schema_context.get("header_context_text")))
    if schema_context.get("dimension_field_names"):
        parts.append(f"维度字段: {'、'.join(list(schema_context.get('dimension_field_names') or [])[:8])}")
    if schema_context.get("metric_field_names"):
        parts.append(f"指标字段: {'、'.join(list(schema_context.get('metric_field_names') or [])[:8])}")
    if schema_context.get("identifier_field_names"):
        parts.append(f"唯一标识字段: {'、'.join(list(schema_context.get('identifier_field_names') or [])[:8])}")
    if schema_context.get("row_explanation_text"):
        parts.append(str(schema_context.get("row_explanation_text")))
    if schema_context.get("dimension_explanation_text"):
        parts.append(str(schema_context.get("dimension_explanation_text")))
    if schema_context.get("metric_explanation_text"):
        parts.append(str(schema_context.get("metric_explanation_text")))
    if field_names and schema_context.get("dimension_field_names"):
        matched_dimension_fields = [
            item for item in field_names
            if item in list(schema_context.get("dimension_field_names") or [])
        ]
        if matched_dimension_fields:
            parts.append(f"行解释: 这一行主要用于定位 {'、'.join(matched_dimension_fields[:6])}")
            parts.append(f"维度解释: 先根据 {'、'.join(matched_dimension_fields[:6])} 确定当前记录属于哪一类对象或范围")
    if field_names and schema_context.get("metric_field_names"):
        matched_metric_fields = [
            item for item in field_names
            if item in list(schema_context.get("metric_field_names") or [])
        ]
        if matched_metric_fields:
            parts.append(f"指标解释: 这一行更适合回答 {'、'.join(matched_metric_fields[:6])} 相关问题")
            parts.append(f"数值理解: 如果问题在问结果、数值或状态，优先关注 {'、'.join(matched_metric_fields[:6])}")
    if chunk_role == "excel_row_fragment":
        parts.append("命中视角: 行片段")
    else:
        parts.append("命中视角: 行")
    parts.append(base_text)
    return "\n".join(part for part in parts if part).strip()
