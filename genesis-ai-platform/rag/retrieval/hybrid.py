"""
混合检索服务。

当前实现目标：
- 把“硬过滤”和“软检索”明确拆层
- 统一承接知识库检索测试页与后续聊天检索的参数
- 支持向量 + 全文双路召回
- 支持基于 content_group_id / chunk_id 的聚合
- 在命中子块后补充父块上下文，兼顾层级分块
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import Select, and_, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_redis
from core.model_platform.kb_model_resolver import resolve_kb_runtime_model
from models.chunk import Chunk
from models.document import Document
from models.folder import Folder
from models.kb_qa_row import KBQARow
from models.kb_table_row import KBTableRow
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.platform_model import PlatformModel
from models.resource_tag import TARGET_TYPE_FOLDER, TARGET_TYPE_KB_DOC, ResourceTag
from models.tag import Tag
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider
from models.user import User
from rag.query_analysis import QueryAnalysisAutoFilterSignal, QueryAnalysisConfig, QueryAnalysisService
from rag.retrieval.service import RetrievalExecutionService
from rag.retrieval.filter_expression import (
    filter_expression_has_field,
    normalize_filter_expression,
    serialize_filter_value,
)
from rag.retrieval.types import (
    HybridSearchConfig,
    LexicalSearchRequest,
    RetrievalFilterSet,
    SearchHit,
    VectorSearchRequest,
)
from rag.doc_summary_utils import prepare_doc_summary_text
from rag.lexical.text_utils import build_pg_fts_query_payload, extract_ascii_terms, extract_cjk_terms, normalize_lexical_text
from rag.pgvector_utils import ensure_pgvector_dimension_compatible, get_pgvector_embedding_dimension
from rag.search_units import normalize_qa_retrieval_config
from rag.utils.token_utils import count_tokens
from services.model_platform_service import ModelInvocationService

QUERY_EMBED_CACHE_VERSION = "v1"
QUERY_EMBED_CACHE_NAMESPACE = "rag:query-embed-cache"
QUERY_EMBED_CACHE_INDEX_KEY = f"{QUERY_EMBED_CACHE_NAMESPACE}:index"
QUERY_EMBED_CACHE_LOCK_NAMESPACE = f"{QUERY_EMBED_CACHE_NAMESPACE}:lock"
QUERY_EMBED_CACHE_LOCK_TTL_SECONDS = 30
QUERY_EMBED_CACHE_LOCK_WAIT_SECONDS = 5
QUERY_EMBED_CACHE_LOCK_POLL_SECONDS = 0.1


DEFAULT_VECTOR_SCOPES = ("default", "summary", "question", "answer", "row", "page_body")
DEFAULT_LEXICAL_SCOPES = (
    "default",
    "summary",
    "doc_summary",
    "question",
    "keyword",
    "answer",
    "row",
    "row_fragment",
    "page_body",
)
SEARCH_SCOPE_WEIGHTS = {
    "default": 1.00,
    "question": 0.96,
    "answer": 0.94,
    "summary": 0.90,
    "doc_summary": 0.72,
    "keyword": 0.76,
    "row": 0.92,
    "row_group": 0.88,
    "row_fragment": 0.84,
    "page_body": 0.88,
}

TABLE_VECTOR_SCOPES = ("row",)
TABLE_LEXICAL_SCOPES = ("row", "row_group", "row_fragment", "keyword")


def _collect_synonym_expansion_terms(synonym_matches: Sequence[Any]) -> list[str]:
    """收集查询命中的同义词扩展词，保持顺序去重。"""

    terms: list[str] = []
    for item in list(synonym_matches or []):
        for raw_term in [getattr(item, "professional_term", ""), *list(getattr(item, "expansion_terms", []) or [])]:
            term = str(raw_term or "").strip()
            if term and term not in terms:
                terms.append(term)
    return terms[:12]


def _build_query_phrase_hints(analyzed_query: Any) -> list[str]:
    """把原始问句、改写问句和业务短语一起作为全文短语候选。"""

    phrases: list[str] = []
    for raw_phrase in [
        getattr(analyzed_query, "raw_query", ""),
        getattr(analyzed_query, "rewritten_query", ""),
        *list(getattr(analyzed_query, "priority_lexical_phrases", []) or []),
    ]:
        phrase = str(raw_phrase or "").strip()
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    return phrases[:8]


@dataclass(slots=True)
class ResolvedCandidateFilter:
    """过滤层解析后的候选约束。"""

    kb_doc_ids: list[UUID] = field(default_factory=list)
    document_ids: list[UUID] = field(default_factory=list)
    content_group_ids: list[UUID] = field(default_factory=list)
    filter_applied: bool = False
    auto_metadata_debug: dict[str, Any] = field(default_factory=dict)
    filter_expression: dict[str, Any] = field(default_factory=dict)
    expression_debug: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GroupedHit:
    """按业务聚合键归并后的命中。"""

    group_key: str
    anchor_chunk_id: int
    kb_doc_id: UUID
    document_id: UUID
    content_group_id: Optional[UUID]
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    final_score: float = 0.0
    scope_weight: float = 0.0
    repeated_hit_bonus: float = 0.0
    query_intent_bonus: float = 0.0
    metadata_bonus: float = 0.0
    auto_tag_boost: float = 0.0
    auto_tag_boost_debug: dict[str, Any] = field(default_factory=dict)
    matched_scopes: set[str] = field(default_factory=set)
    matched_backend_types: set[str] = field(default_factory=set)
    hits: list[SearchHit] = field(default_factory=list)


@dataclass(slots=True)
class QueryEmbeddingModelSnapshot:
    """查询向量化使用的模型快照。"""

    tenant_model_id: UUID
    raw_model_name: str
    cache_signature: str


def normalize_hybrid_search_config(raw_config: Mapping[str, Any] | None) -> HybridSearchConfig:
    """统一规范化检索参数。

    兼容两类来源：
    - 检索测试页：top_k / vector_top_k / keyword_top_k / vector_weight ...
    - 聊天会话：search_depth_k / rerank_top_n / min_score
    """

    config = dict(raw_config or {})

    def _to_int(value: Any, default: int, *, minimum: int = 1, maximum: int = 500) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, number))

    def _to_float(value: Any, default: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, number))

    top_k = _to_int(
        config.get("top_k", config.get("rerank_top_n", config.get("search_depth_k", 8))),
        8,
        minimum=1,
        maximum=100,
    )
    rerank_top_n = _to_int(config.get("rerank_top_n", top_k), top_k, minimum=1, maximum=200)
    top_k = min(top_k, rerank_top_n)
    vector_top_k = _to_int(config.get("vector_top_k", max(top_k * 6, top_k)), max(top_k * 6, top_k), minimum=1, maximum=500)
    keyword_top_k = _to_int(config.get("keyword_top_k", max(top_k * 4, top_k)), max(top_k * 4, top_k), minimum=1, maximum=500)

    search_scopes_raw = config.get("search_scopes") or []
    search_scopes = [
        str(item).strip()
        for item in search_scopes_raw
        if str(item).strip()
    ]

    return HybridSearchConfig(
        top_k=top_k,
        vector_top_k=vector_top_k,
        keyword_top_k=keyword_top_k,
        rerank_top_n=rerank_top_n,
        vector_similarity_threshold=_to_float(config.get("vector_similarity_threshold"), 0.25),
        keyword_relevance_threshold=_to_float(config.get("keyword_relevance_threshold"), 0.2),
        final_score_threshold=_to_float(config.get("final_score_threshold", config.get("min_score", 0.3)), 0.3),
        vector_weight=_to_float(config.get("vector_weight"), 0.55),
        enable_rerank=bool(config.get("enable_rerank", True)),
        rerank_model=str(config.get("rerank_model") or "").strip() or None,
        metadata_filter_mode=str(config.get("metadata_filter") or "all").strip().lower() or "all",
        use_knowledge_graph=bool(config.get("use_knowledge_graph", False)),
        enable_query_rewrite=bool(config.get("enable_query_rewrite", False)),
        enable_synonym_rewrite=bool(config.get("enable_synonym_rewrite", True)),
        auto_filter_mode=str(config.get("auto_filter_mode") or "disabled").strip().lower() or "disabled",
        enable_doc_summary_retrieval=bool(config.get("enable_doc_summary_retrieval", False)),
        search_scopes=search_scopes,
        enable_parent_context=bool(config.get("enable_parent_context", True)),
        hierarchical_retrieval_mode=str(config.get("hierarchical_retrieval_mode") or "recursive").strip().lower() or "recursive",
        neighbor_window_size=_to_int(config.get("neighbor_window_size"), 0, minimum=0, maximum=5),
        group_by_content_group=bool(config.get("group_by_content_group", True)),
        max_snippet_length=_to_int(config.get("max_snippet_length"), 280, minimum=80, maximum=2000),
        debug_trace_level=str(config.get("debug_trace_level") or "off").strip().lower() or "off",
    )


def normalize_retrieval_filter_set(
    raw_filters: Mapping[str, Any] | None,
    *,
    metadata_filter_mode: str,
) -> RetrievalFilterSet:
    """规范化过滤条件。"""

    filters = dict(raw_filters or {})

    latest_days: Optional[int] = None
    only_tagged = bool(filters.get("only_tagged", False))
    if metadata_filter_mode == "latest":
        latest_days = 90
    elif metadata_filter_mode == "tagged":
        only_tagged = True

    return RetrievalFilterSet(
        kb_doc_ids=_coerce_uuid_list(filters.get("kb_doc_ids")),
        document_ids=_coerce_uuid_list(filters.get("document_ids")),
        content_group_ids=_coerce_uuid_list(filters.get("content_group_ids")),
        folder_ids=_coerce_uuid_list(filters.get("folder_ids") or filters.get("folder_id")),
        tag_ids=_coerce_uuid_list(filters.get("tag_ids") or filters.get("tag_id")),
        folder_tag_ids=_coerce_uuid_list(filters.get("folder_tag_ids") or filters.get("folder_tag_id")),
        document_metadata=_normalize_metadata_dict(filters.get("metadata") or filters.get("document_metadata")),
        search_unit_metadata=_normalize_metadata_dict(filters.get("search_unit_metadata")),
        filter_expression=normalize_filter_expression(filters.get("filter_expression") or filters.get("expression")),
        include_descendant_folders=bool(filters.get("include_descendant_folders", True)),
        only_tagged=only_tagged,
        latest_days=latest_days,
    )


class HybridRetrievalService:
    """统一混合检索服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.execution_service = RetrievalExecutionService(session)
        self.model_invocation_service = ModelInvocationService(session)

    async def search(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        query: str,
        raw_config: Mapping[str, Any] | None = None,
        raw_filters: Mapping[str, Any] | None = None,
        query_rewrite_context: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """执行完整检索链路。"""

        normalized_query = str(query or "").strip()
        if not normalized_query:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="检索问题不能为空")

        started_at = time.perf_counter()
        merged_raw_config = self._merge_query_analysis_defaults(kb=kb, raw_config=raw_config)
        config = normalize_hybrid_search_config(merged_raw_config)
        config.hierarchical_retrieval_mode = self._resolve_hierarchical_retrieval_mode(
            kb=kb,
            hierarchical_retrieval_mode=config.hierarchical_retrieval_mode,
        )
        config.group_by_content_group = self._resolve_group_by_content_group(
            kb=kb,
            group_by_content_group=config.group_by_content_group,
        )
        rerank_model_id = _coerce_optional_uuid(config.rerank_model)
        if config.enable_rerank and not str(config.rerank_model or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已开启重排序，请先选择一个 rerank 模型",
            )
        if config.enable_rerank and rerank_model_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前 rerank 模型配置无效，请重新选择一个有效的 rerank 模型",
            )
        if config.hierarchical_retrieval_mode == "leaf_only":
            config.enable_parent_context = False
        debug_trace_level = str(merged_raw_config.get("debug_trace_level") or "basic").strip().lower() or "basic"
        explicit_filters = normalize_retrieval_filter_set(
            raw_filters,
            metadata_filter_mode=config.metadata_filter_mode,
        )
        explicit_filters = self._apply_table_filter_mapping(
            kb=kb,
            filters=explicit_filters,
            raw_config=merged_raw_config,
        )
        explicit_filters = self._apply_qa_filter_mapping(
            kb=kb,
            filters=explicit_filters,
        )
        analyzed_query = await QueryAnalysisService(self.session).analyze(
            current_user=current_user,
            kb=kb,
            query=normalized_query,
            filters=explicit_filters,
            config=QueryAnalysisConfig(
                enable_query_rewrite=config.enable_query_rewrite,
                enable_synonym_rewrite=config.enable_synonym_rewrite,
                auto_filter_mode=config.auto_filter_mode,
                enable_llm_candidate_extraction=config.auto_filter_mode in {"llm_candidate", "hybrid"},
                enable_llm_filter_expression=bool(merged_raw_config.get("enable_llm_filter_expression", True)),
                metadata_fields=await self._build_query_analysis_metadata_fields(
                    kb=kb,
                    raw_config=merged_raw_config,
                ),
                retrieval_lexicon=self._build_query_analysis_retrieval_lexicon(
                    kb=kb,
                    raw_config=merged_raw_config,
                ),
                retrieval_stopwords=list(merged_raw_config.get("retrieval_stopwords") or []),
                extra_retrieval_stopwords=list(
                    self._extract_query_analysis_extra_stopwords(
                        kb=kb,
                        raw_config=raw_config,
                    )
                ),
                llm_candidate_min_confidence=float(merged_raw_config.get("llm_candidate_min_confidence") or 0.55),
                llm_upgrade_confidence_threshold=float(
                    merged_raw_config.get("llm_upgrade_confidence_threshold") or 0.82
                ),
                llm_max_upgrade_count=int(merged_raw_config.get("llm_max_upgrade_count") or 2),
                query_rewrite_context=[
                    {
                        "role": str(item.get("role") or "").strip(),
                        "content": str(item.get("content") or "").strip(),
                    }
                    for item in list(query_rewrite_context or [])
                    if isinstance(item, Mapping)
                ],
            ),
        )
        lexical_query_debug = build_pg_fts_query_payload(
            analyzed_query.lexical_query,
            priority_terms=analyzed_query.priority_lexical_terms,
            priority_phrases=_build_query_phrase_hints(analyzed_query),
            synonym_terms=_collect_synonym_expansion_terms(analyzed_query.synonym_matches),
            glossary_terms=[item.term for item in analyzed_query.glossary_entries],
            retrieval_stopwords=analyzed_query.retrieval_stopwords,
        )
        resolved_filters = await self._resolve_candidate_filters(
            current_user=current_user,
            kb=kb,
            filters=analyzed_query.retrieval_filters,
            auto_filter_signals=analyzed_query.auto_filter_signals,
        )

        row_filter_applied = bool(analyzed_query.retrieval_filters.search_unit_metadata) or filter_expression_has_field(
            analyzed_query.retrieval_filters.filter_expression,
            {"search_unit_metadata"},
        )
        filter_debug_summary = await self._build_filter_debug_summary(
            current_user=current_user,
            kb=kb,
            analyzed_filters=analyzed_query.retrieval_filters,
            resolved_filters=resolved_filters,
            auto_filter_signals=analyzed_query.auto_filter_signals,
        )
        if resolved_filters.filter_applied and (
            (
                not resolved_filters.kb_doc_ids
                and not resolved_filters.document_ids
                and not resolved_filters.content_group_ids
            )
            or (row_filter_applied and not resolved_filters.content_group_ids)
        ):
            return {
                "items": [],
                "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
                "query_analysis": analyzed_query.to_debug_dict(),
                "debug": {
                    "vector_hit_count": 0,
                    "lexical_hit_count": 0,
                    "grouped_hit_count": 0,
                    "filter_applied": True,
                    "lexical_query_debug": dict(lexical_query_debug.get("debug") or {}),
                    "filter_debug_summary": filter_debug_summary,
                },
            }

        query_embedding, query_embedding_dimension = await self._embed_query(
            current_user=current_user,
            kb=kb,
            query=analyzed_query.rewritten_query,
        )
        index_dimension = await get_pgvector_embedding_dimension(self.session)
        try:
            ensure_pgvector_dimension_compatible(
                actual_dimension=query_embedding_dimension,
                index_dimension=index_dimension,
                scene="检索测试",
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        qa_runtime_config = normalize_qa_retrieval_config(kb.retrieval_config or {}) if str(kb.type or "").strip() == "qa" else {}
        vector_scopes = self._resolve_vector_scopes(config, kb=kb, qa_config=qa_runtime_config)
        lexical_scopes = self._resolve_lexical_scopes(config, kb=kb, qa_config=qa_runtime_config)
        scope_weights = self._resolve_scope_weights(kb=kb, qa_config=qa_runtime_config)

        vector_hits: list[SearchHit] = []
        if config.vector_top_k > 0 and vector_scopes:
            vector_hits = await self.execution_service.vector_search(
                VectorSearchRequest(
                    tenant_id=current_user.tenant_id,
                    kb_id=kb.id,
                    query=analyzed_query.rewritten_query,
                    query_embedding=query_embedding,
                    query_embedding_dimension=query_embedding_dimension,
                    top_k=config.vector_top_k,
                    search_scopes=vector_scopes,
                    metadata_filters=analyzed_query.retrieval_filters.search_unit_metadata,
                    metadata_filter_expression=resolved_filters.filter_expression,
                    kb_doc_ids=resolved_filters.kb_doc_ids,
                    document_ids=resolved_filters.document_ids,
                    content_group_ids=resolved_filters.content_group_ids,
                    display_only=True,
                    leaf_only=True,
                )
            )

        lexical_hits: list[SearchHit] = []
        if config.keyword_top_k > 0 and lexical_scopes:
            lexical_hits = await self.execution_service.lexical_search(
                LexicalSearchRequest(
                    tenant_id=current_user.tenant_id,
                    kb_id=kb.id,
                    query=analyzed_query.lexical_query,
                    priority_terms=analyzed_query.priority_lexical_terms,
                    priority_phrases=_build_query_phrase_hints(analyzed_query),
                    synonym_terms=_collect_synonym_expansion_terms(analyzed_query.synonym_matches),
                    glossary_terms=[item.term for item in analyzed_query.glossary_entries],
                    retrieval_stopwords=analyzed_query.retrieval_stopwords,
                    lexicon_weights=analyzed_query.lexicon_weights,
                    top_k=config.keyword_top_k,
                    search_scopes=lexical_scopes,
                    metadata_filters=analyzed_query.retrieval_filters.search_unit_metadata,
                    metadata_filter_expression=resolved_filters.filter_expression,
                    kb_doc_ids=resolved_filters.kb_doc_ids,
                    document_ids=resolved_filters.document_ids,
                    content_group_ids=resolved_filters.content_group_ids,
                    display_only=True,
                    leaf_only=True,
                )
            )

        has_indexed_doc_summary = any(hit.search_scope == "doc_summary" for hit in lexical_hits)
        if config.enable_doc_summary_retrieval and not resolved_filters.content_group_ids and not has_indexed_doc_summary:
            lexical_hits.extend(
                await self._search_doc_summary_hits(
                    current_user=current_user,
                    kb=kb,
                    query=analyzed_query.lexical_query,
                    resolved_filters=resolved_filters,
                    top_k=min(max(config.keyword_top_k, config.top_k), 20),
                )
            )

        auto_tag_boosts = await self._build_auto_tag_boosts(
            current_user=current_user,
            kb=kb,
            hits=[*vector_hits, *lexical_hits],
            auto_filter_signals=analyzed_query.auto_filter_signals,
        )
        grouped_hits = self._fuse_hits(
            config=config,
            kb=kb,
            query=analyzed_query.rewritten_query,
            raw_query=analyzed_query.raw_query,
            vector_hits=vector_hits,
            lexical_hits=lexical_hits,
            scope_weights=scope_weights,
            auto_tag_boosts=auto_tag_boosts,
        )
        items = await self._hydrate_results(
            kb=kb,
            config=config,
            grouped_hits=grouped_hits,
        )
        items = await self._apply_rerank_if_needed(
            current_user=current_user,
            query=analyzed_query.rewritten_query,
            config=config,
            items=items,
            rerank_model_id=rerank_model_id,
        )

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        extension_branch_context = self._build_extension_branch_context(
            kb=kb,
            config=config,
            analyzed_query=analyzed_query,
        )
        return {
            "items": items,
            "elapsed_ms": elapsed_ms,
            "query_analysis": analyzed_query.to_debug_dict(),
            "debug": {
                "vector_hit_count": len(vector_hits),
                "lexical_hit_count": len(lexical_hits),
                "doc_summary_hit_count": len([item for item in lexical_hits if item.search_scope == "doc_summary"]),
                "grouped_hit_count": len(grouped_hits),
                "kb_type": str(kb.type or "").strip(),
                "vector_scopes": vector_scopes,
                "lexical_scopes": lexical_scopes,
                "lexical_query_debug": dict(lexical_query_debug.get("debug") or {}),
                "filter_applied": resolved_filters.filter_applied,
                "filter_debug_summary": filter_debug_summary,
                "result_debug_summary": self._build_result_debug_summary(items=items),
                "query_analysis_template_summary": self._build_query_analysis_template_summary(
                    kb=kb,
                    retrieval_lexicon_matches=analyzed_query.retrieval_lexicon_matches,
                    ignored_lexical_terms=analyzed_query.ignored_lexical_terms,
                ),
                "pipeline_trace": self._build_pipeline_trace(
                    debug_trace_level=debug_trace_level,
                    kb=kb,
                    raw_config=merged_raw_config,
                    config=config,
                    analyzed_query=analyzed_query,
                    lexical_query_debug=dict(lexical_query_debug.get("debug") or {}),
                    explicit_filters=explicit_filters,
                    resolved_filters=resolved_filters,
                    filter_debug_summary=filter_debug_summary,
                    vector_scopes=vector_scopes,
                    lexical_scopes=lexical_scopes,
                    vector_hits=vector_hits,
                    lexical_hits=lexical_hits,
                    grouped_hits=grouped_hits,
                    items=items,
                    qa_runtime_config=qa_runtime_config,
                ),
                "extension_branch_context": extension_branch_context,
                "qa_runtime_config": qa_runtime_config if qa_runtime_config else None,
            },
        }

    def _resolve_hierarchical_retrieval_mode(
        self,
        *,
        kb: KnowledgeBase,
        hierarchical_retrieval_mode: str,
    ) -> str:
        """校验层级召回策略，并按知识库类型限制非法组合。"""

        normalized_mode = str(hierarchical_retrieval_mode or "recursive").strip().lower() or "recursive"
        if normalized_mode not in {"leaf_only", "recursive", "auto_merge"}:
            normalized_mode = "recursive"

        kb_type = str(kb.type or "").strip().lower()
        if kb_type in {"qa", "table"} and normalized_mode == "leaf_only":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前知识库类型不支持仅叶子块召回，请改用递归父上下文或自动父块合并",
            )
        return normalized_mode

    def _resolve_group_by_content_group(
        self,
        *,
        kb: KnowledgeBase,
        group_by_content_group: bool,
    ) -> bool:
        """校验业务聚合开关，并明确其不参与层级召回决策。"""

        _ = kb  # 预留知识库类型特定校验入口，当前统一按布尔语义处理。
        return bool(group_by_content_group)

    def _requires_complete_unit_from_metadata(
        self,
        *,
        kb: KnowledgeBase,
        metadata: Mapping[str, Any],
        search_scope: str | None = None,
    ) -> bool:
        """判断当前命中是否必须回收到完整业务单元。"""

        kb_type = str(kb.type or "").strip().lower()
        source_type = str(metadata.get("source_type") or "").strip().lower()
        chunk_role = str(metadata.get("source_chunk_role") or metadata.get("chunk_role") or "").strip().lower()
        normalized_scope = str(search_scope or "").strip().lower()

        if kb_type in {"qa", "table"}:
            return True
        if source_type == "table":
            return True
        if normalized_scope in {"row", "row_group", "row_fragment", "answer"}:
            return True
        if chunk_role in {"excel_row_fragment", "excel_row", "web_table_fragment", "web_table_parent", "web_table_leaf", "qa_answer_fragment", "qa_row"}:
            return True
        return False

    def _is_general_hierarchical_leaf(self, metadata: Mapping[str, Any]) -> bool:
        """判断是否为普通层级叶子块，可用于 auto_merge 聚合到父块。"""

        return bool(metadata.get("is_hierarchical")) and bool(metadata.get("is_leaf", True)) and metadata.get("parent_chunk_id") is not None

    def _resolve_result_unit_group_key(
        self,
        *,
        kb: KnowledgeBase,
        config: HybridSearchConfig,
        hit: SearchHit,
    ) -> str:
        """根据层级召回策略解析“自然结果单元”键。"""

        if hit.search_scope == "doc_summary":
            return f"doc_summary:{hit.kb_doc_id}"

        metadata = dict(hit.metadata or {})
        parent_chunk_id = metadata.get("parent_chunk_id")
        if self._requires_complete_unit_from_metadata(kb=kb, metadata=metadata, search_scope=hit.search_scope):
            if hit.content_group_id:
                return f"unit:{hit.content_group_id}"
            if parent_chunk_id is not None:
                return f"parent:{parent_chunk_id}"

        if config.hierarchical_retrieval_mode == "auto_merge" and self._is_general_hierarchical_leaf(metadata):
            return f"parent:{parent_chunk_id}"

        return str(hit.chunk_id)

    def _resolve_hit_group_key(
        self,
        *,
        kb: KnowledgeBase,
        config: HybridSearchConfig,
        hit: SearchHit,
    ) -> str:
        """根据业务聚合开关，决定命中最终落在哪个分组键。"""

        result_unit_key = self._resolve_result_unit_group_key(
            kb=kb,
            config=config,
            hit=hit,
        )
        if hit.search_scope == "doc_summary":
            return result_unit_key
        if config.group_by_content_group and hit.content_group_id:
            return f"biz:{hit.content_group_id}"
        return result_unit_key

    def _resolve_grouping_strategy_label(self, config: HybridSearchConfig) -> str:
        """返回当前结果分组策略标签，便于调试和前端理解。"""

        return "business_content_group" if config.group_by_content_group else "result_unit_only"

    def _resolve_chunk_topology_type(self, chunk: Chunk | None) -> str | None:
        """根据块元数据判断当前块在层级中的拓扑类型。"""

        if chunk is None:
            return None
        metadata = dict(chunk.metadata_info or {})
        is_hierarchical = bool(metadata.get("is_hierarchical"))
        is_leaf = bool(metadata.get("is_leaf", True))

        if "is_root" in metadata:
            is_root = bool(metadata.get("is_root"))
        elif is_hierarchical:
            is_root = chunk.parent_id is None
        else:
            is_root = bool(chunk.parent_id is None)
        if is_root and not is_leaf:
            return "root"
        if is_root and is_leaf:
            return "root_leaf"
        if is_leaf:
            return "leaf"
        return "intermediate"

    def _resolve_full_result_content(
        self,
        *,
        display_chunk: Chunk | None,
        kb_doc: KnowledgeBaseDocument,
        grouped_hit: GroupedHit,
    ) -> str:
        """返回当前结果对应的完整展示内容。"""

        if display_chunk is not None:
            return str(display_chunk.summary or display_chunk.content or "").strip()
        if "doc_summary" in grouped_hit.matched_scopes:
            return str(kb_doc.summary or "").strip()
        return ""

    def _build_chunk_debug_view(
        self,
        *,
        chunk: Chunk | None,
        fallback_content: str = "",
        fallback_label: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构造分块调试视图，便于前端稳定展示不同层级内容。"""

        payload: dict[str, Any] = {
            "label": str(fallback_label or "").strip() or None,
            "chunk_id": None,
            "parent_chunk_id": None,
            "topology_type": None,
            "content": str(fallback_content or "").strip(),
            "summary": "",
            "page_numbers": [],
            "token_count": count_tokens(str(fallback_content or "").strip()),
            "text_length": len(str(fallback_content or "").strip()),
        }
        if chunk is not None:
            chunk_metadata = dict(chunk.metadata_info or {})
            payload.update(
                {
                    "chunk_id": int(chunk.id) if chunk.id is not None else None,
                    "parent_chunk_id": int(chunk.parent_id) if chunk.parent_id is not None else None,
                    "topology_type": self._resolve_chunk_topology_type(chunk),
                    # 调试视图优先保留原始 content，避免被 summary 替代后看不出真实分块边界。
                    "content": str(chunk.content or "").strip(),
                    "summary": str(chunk.summary or "").strip(),
                    "page_numbers": [int(item) for item in list(chunk_metadata.get("page_numbers") or []) if isinstance(item, int)],
                    "token_count": int(chunk.token_count or 0),
                    "text_length": int(chunk.text_length or len(str(chunk.content or "").strip())),
                    "topology_flags": {
                        "is_hierarchical": bool(chunk_metadata.get("is_hierarchical")),
                        "is_leaf": chunk_metadata.get("is_leaf"),
                        "is_root": chunk_metadata.get("is_root"),
                        "should_vectorize": chunk_metadata.get("should_vectorize"),
                        "child_count": len([item for item in list(chunk_metadata.get("child_ids") or []) if str(item).strip()]),
                        "metadata_parent_id": chunk_metadata.get("parent_id"),
                    },
                }
            )
        if extra:
            payload.update(dict(extra))
        return payload

    def _build_result_context_text(
        self,
        *,
        chunk: Chunk,
        parent_chunk: Optional[Chunk],
        enable_parent_context: bool,
        previous_neighbors: Sequence[Chunk] = (),
        next_neighbors: Sequence[Chunk] = (),
    ) -> str:
        """构造真正传给模型的上下文文本，不做预览裁剪。"""

        child_text = str(chunk.content or "").strip()
        if str(chunk.source_type or "").strip() == "table":
            metadata = dict(chunk.metadata_info or {})
            table_context_parts = []
            sheet_name = str(metadata.get("sheet_name") or "").strip()
            row_identity_text = str(metadata.get("row_identity_text") or "").strip()
            field_names = [str(item).strip() for item in list(metadata.get("field_names") or []) if str(item).strip()]
            table_context_text = str(metadata.get("table_context_text") or "").strip()
            if sheet_name:
                table_context_parts.append(f"工作表: {sheet_name}")
            if row_identity_text:
                table_context_parts.append(f"定位: {row_identity_text}")
            if field_names:
                table_context_parts.append(f"字段: {'、'.join(field_names[:6])}")
            if table_context_text:
                table_context_parts.append(table_context_text)
            table_context = "\n".join(table_context_parts).strip()
            if table_context:
                child_text = f"{table_context}\n{child_text}".strip()

        chunk_role = str((chunk.metadata_info or {}).get("chunk_role") or "").strip()
        if chunk_role == "qa_answer_fragment":
            question = str((chunk.metadata_info or {}).get("question") or "").strip()
            if enable_parent_context and parent_chunk is not None:
                parent_answer = str(parent_chunk.summary or parent_chunk.content or "").strip()
                if question and parent_answer:
                    return self._merge_neighbor_context(
                        core_text=f"[问题] {question}\n[完整答案] {parent_answer}",
                        previous_neighbors=previous_neighbors,
                        next_neighbors=next_neighbors,
                    )
            if question:
                return self._merge_neighbor_context(
                    core_text=f"[问题] {question}\n[命中答案片段] {child_text}",
                    previous_neighbors=previous_neighbors,
                    next_neighbors=next_neighbors,
                )
        if not enable_parent_context or parent_chunk is None:
            return self._merge_neighbor_context(
                core_text=child_text,
                previous_neighbors=previous_neighbors,
                next_neighbors=next_neighbors,
            )

        parent_preview = str(parent_chunk.summary or parent_chunk.content or "").strip()
        if not parent_preview:
            return self._merge_neighbor_context(
                core_text=child_text,
                previous_neighbors=previous_neighbors,
                next_neighbors=next_neighbors,
            )

        merged = f"[父块上下文] {parent_preview}\n[命中子块] {child_text}"
        return self._merge_neighbor_context(
            core_text=merged,
            previous_neighbors=previous_neighbors,
            next_neighbors=next_neighbors,
        )

    def _build_pipeline_trace(
        self,
        *,
        debug_trace_level: str,
        kb: KnowledgeBase,
        raw_config: Mapping[str, Any],
        config: HybridSearchConfig,
        analyzed_query: Any,
        lexical_query_debug: Mapping[str, Any],
        explicit_filters: RetrievalFilterSet,
        resolved_filters: ResolvedCandidateFilter,
        filter_debug_summary: Mapping[str, Any],
        vector_scopes: Sequence[str],
        lexical_scopes: Sequence[str],
        vector_hits: Sequence[SearchHit],
        lexical_hits: Sequence[SearchHit],
        grouped_hits: Sequence[GroupedHit],
        items: Sequence[dict[str, Any]],
        qa_runtime_config: Mapping[str, Any],
    ) -> dict[str, Any]:
        """构造可直接给前端展示的检索调试轨迹。"""

        if debug_trace_level in {"off", "none", "disabled"}:
            return {}

        hit_limit = 12 if debug_trace_level == "detailed" else 5
        grouped_limit = 12 if debug_trace_level == "detailed" else 5
        item_limit = 12 if debug_trace_level == "detailed" else 5
        return {
            "level": debug_trace_level,
            "input": {
                "kb_type": str(kb.type or "").strip(),
                "raw_query": analyzed_query.raw_query,
                "standalone_query": getattr(analyzed_query, "standalone_query", analyzed_query.raw_query),
                "rewritten_query": analyzed_query.rewritten_query,
                "lexical_query": analyzed_query.lexical_query,
                "query_rewritten": analyzed_query.raw_query != analyzed_query.rewritten_query,
            },
            "config": {
                "raw_config": dict(raw_config or {}),
                "normalized_config": {
                    "top_k": config.top_k,
                    "vector_top_k": config.vector_top_k,
                    "keyword_top_k": config.keyword_top_k,
                    "rerank_top_n": config.rerank_top_n,
                    "vector_similarity_threshold": round(config.vector_similarity_threshold, 4),
                    "keyword_relevance_threshold": round(config.keyword_relevance_threshold, 4),
                    "final_score_threshold": round(config.final_score_threshold, 4),
                    "vector_weight": round(config.vector_weight, 4),
                    "lexical_weight": round(max(0.0, 1.0 - config.vector_weight), 4),
                    "rerank_model": config.rerank_model,
                    "metadata_filter_mode": config.metadata_filter_mode,
                    "enable_query_rewrite": config.enable_query_rewrite,
                    "enable_synonym_rewrite": config.enable_synonym_rewrite,
                    "auto_filter_mode": config.auto_filter_mode,
                    "enable_doc_summary_retrieval": config.enable_doc_summary_retrieval,
                    "enable_parent_context": config.enable_parent_context,
                    "hierarchical_retrieval_mode": config.hierarchical_retrieval_mode,
                    "neighbor_window_size": config.neighbor_window_size,
                    "group_by_content_group": config.group_by_content_group,
                    "grouping_strategy": self._resolve_grouping_strategy_label(config),
                    "vector_scopes": list(vector_scopes),
                    "lexical_scopes": list(lexical_scopes),
                },
                "qa_runtime_config": dict(qa_runtime_config or {}),
            },
            "filters": {
                "explicit_filters": self._serialize_filter_set(explicit_filters),
                "resolved_filters": {
                    "kb_doc_ids": [str(item) for item in list(resolved_filters.kb_doc_ids or [])],
                    "document_ids": [str(item) for item in list(resolved_filters.document_ids or [])],
                    "content_group_ids": [str(item) for item in list(resolved_filters.content_group_ids or [])],
                    "filter_applied": resolved_filters.filter_applied,
                    "filter_expression": dict(resolved_filters.filter_expression or {}),
                    "expression_debug": dict(resolved_filters.expression_debug or {}),
                },
                "debug_summary": dict(filter_debug_summary or {}),
            },
            "retrieval": {
                "vector_hit_count": len(vector_hits),
                "lexical_hit_count": len(lexical_hits),
                "lexical_query_debug": dict(lexical_query_debug or {}),
                "vector_hits": [self._build_search_hit_trace(hit) for hit in list(vector_hits)[:hit_limit]],
                "lexical_hits": [self._build_search_hit_trace(hit) for hit in list(lexical_hits)[:hit_limit]],
            },
            "fusion": {
                "grouped_hit_count": len(grouped_hits),
                "groups": [self._build_grouped_hit_trace(hit) for hit in list(grouped_hits)[:grouped_limit]],
            },
            "results": {
                "item_count": len(items),
                "items": [self._build_result_item_trace(item) for item in list(items)[:item_limit]],
            },
        }

    def _serialize_filter_set(self, filters: RetrievalFilterSet) -> dict[str, Any]:
        """把过滤条件稳定序列化为调试结构。"""

        return {
            "kb_doc_ids": [str(item) for item in list(filters.kb_doc_ids or [])],
            "document_ids": [str(item) for item in list(filters.document_ids or [])],
            "content_group_ids": [str(item) for item in list(filters.content_group_ids or [])],
            "folder_ids": [str(item) for item in list(filters.folder_ids or [])],
            "tag_ids": [str(item) for item in list(filters.tag_ids or [])],
            "folder_tag_ids": [str(item) for item in list(filters.folder_tag_ids or [])],
            "document_metadata": dict(filters.document_metadata or {}),
            "search_unit_metadata": dict(filters.search_unit_metadata or {}),
            "filter_expression": dict(filters.filter_expression or {}),
            "include_descendant_folders": bool(filters.include_descendant_folders),
            "only_tagged": bool(filters.only_tagged),
            "latest_days": filters.latest_days,
        }

    def _build_search_hit_trace(self, hit: SearchHit) -> dict[str, Any]:
        """提取单条召回命中的关键调试信息。"""

        metadata = dict(hit.metadata or {})
        trace: dict[str, Any] = {
            "search_unit_id": int(hit.search_unit_id),
            "chunk_id": int(hit.chunk_id),
            "content_group_id": str(hit.content_group_id) if hit.content_group_id else None,
            "search_scope": str(hit.search_scope or "").strip(),
            "backend_type": str(hit.backend_type or "").strip(),
            "score": round(float(hit.score or 0.0), 4),
            "question_text": str(metadata.get("question_text") or "").strip() or None,
            "qa_fields": dict(metadata.get("qa_fields") or {}),
        }
        if metadata.get("lexical_raw_score") is not None:
            trace["lexical_raw_score"] = round(float(metadata.get("lexical_raw_score") or 0.0), 4)
        if metadata.get("lexical_structured_score") is not None:
            trace["lexical_structured_score"] = round(float(metadata.get("lexical_structured_score") or 0.0), 4)
        if metadata.get("lexical_structured_candidates") is not None:
            trace["lexical_structured_candidates"] = list(metadata.get("lexical_structured_candidates") or [])
        return trace

    def _build_grouped_hit_trace(self, grouped_hit: GroupedHit) -> dict[str, Any]:
        """提取融合分组后的评分轨迹。"""

        return {
            "group_key": grouped_hit.group_key,
            "anchor_chunk_id": int(grouped_hit.anchor_chunk_id),
            "content_group_id": str(grouped_hit.content_group_id) if grouped_hit.content_group_id else None,
            "vector_score": round(float(grouped_hit.vector_score or 0.0), 4) if grouped_hit.vector_score is not None else None,
            "keyword_score": round(float(grouped_hit.keyword_score or 0.0), 4) if grouped_hit.keyword_score is not None else None,
            "final_score": round(float(grouped_hit.final_score or 0.0), 4),
            "scope_weight": round(float(grouped_hit.scope_weight or 0.0), 4),
            "repeated_hit_bonus": round(float(grouped_hit.repeated_hit_bonus or 0.0), 4),
            "query_intent_bonus": round(float(grouped_hit.query_intent_bonus or 0.0), 4),
            "metadata_bonus": round(float(grouped_hit.metadata_bonus or 0.0), 4),
            "matched_scopes": sorted(grouped_hit.matched_scopes),
            "matched_backends": sorted(grouped_hit.matched_backend_types),
            "hits": [self._build_search_hit_trace(hit) for hit in list(grouped_hit.hits or [])[:8]],
        }

    def _build_result_item_trace(self, item: Mapping[str, Any]) -> dict[str, Any]:
        """提取最终结果项的前端调试视图。"""

        metadata = dict(item.get("metadata") or {})
        return {
            "id": str(item.get("id") or "").strip(),
            "title": str(item.get("title") or "").strip(),
            "score": round(float(item.get("score") or 0.0), 4),
            "vector_score": round(float(item.get("vector_score") or 0.0), 4) if item.get("vector_score") is not None else None,
            "keyword_score": round(float(item.get("keyword_score") or 0.0), 4) if item.get("keyword_score") is not None else None,
            "matched_scopes": list(metadata.get("matched_scopes") or []),
            "matched_backends": list(metadata.get("matched_backends") or []),
            "question_text": str(metadata.get("question_text") or "").strip() or None,
            "group_by_content_group": bool(metadata.get("group_by_content_group")),
            "grouping_strategy": str(metadata.get("grouping_strategy") or "").strip() or None,
            "hierarchical_retrieval_mode": str(metadata.get("hierarchical_retrieval_mode") or "").strip() or None,
            "strategy_contributions": dict(metadata.get("strategy_contributions") or {}),
            "score_trace": dict(metadata.get("score_trace") or {}),
            "hit_score_details": list(metadata.get("hit_score_details") or []),
        }

    def _build_extension_branch_context(
        self,
        *,
        kb: KnowledgeBase,
        config: HybridSearchConfig,
        analyzed_query: Any,
    ) -> dict[str, Any]:
        """为 KG / RAPTOR 等后续分支构造统一预留输入。"""

        intelligence_config = dict(kb.intelligence_config or {})
        knowledge_graph_config = dict(intelligence_config.get("knowledge_graph") or {})
        raptor_config = dict(intelligence_config.get("raptor") or {})
        shared_filters = {
            "kb_doc_ids": [str(item) for item in list(analyzed_query.retrieval_filters.kb_doc_ids or [])],
            "folder_ids": [str(item) for item in list(analyzed_query.retrieval_filters.folder_ids or [])],
            "tag_ids": [str(item) for item in list(analyzed_query.retrieval_filters.tag_ids or [])],
            "folder_tag_ids": [str(item) for item in list(analyzed_query.retrieval_filters.folder_tag_ids or [])],
            "document_metadata": dict(analyzed_query.retrieval_filters.document_metadata or {}),
            "search_unit_metadata": dict(analyzed_query.retrieval_filters.search_unit_metadata or {}),
            "filter_expression": dict(analyzed_query.retrieval_filters.filter_expression or {}),
        }
        return {
            "shared_query_context": {
                "raw_query": analyzed_query.raw_query,
                "rewritten_query": analyzed_query.rewritten_query,
                "lexical_query": analyzed_query.lexical_query,
                "priority_terms": list(analyzed_query.priority_lexical_terms or []),
                "priority_phrases": list(analyzed_query.priority_lexical_phrases or []),
                "synonym_terms": _collect_synonym_expansion_terms(analyzed_query.synonym_matches),
                "glossary_terms": [item.term for item in list(analyzed_query.glossary_entries or [])],
                "retrieval_stopwords": list(analyzed_query.retrieval_stopwords or []),
                "retrieval_filters": shared_filters,
            },
            "branches": {
                "default_retrieval": {
                    "enabled": True,
                    "consumes": ["rewritten_query", "lexical_query", "priority_terms", "priority_phrases", "retrieval_filters"],
                },
                "knowledge_graph": {
                    "reserved": True,
                    "enabled": bool(config.use_knowledge_graph),
                    "kb_enabled": bool(knowledge_graph_config.get("enabled", False)),
                    "consumes": ["rewritten_query", "priority_terms", "priority_phrases", "retrieval_filters"],
                    "notes": [
                        "统一复用 query analysis 输出，不重复做 query rewrite",
                        "后续由 KG 分支自行决定实体抽取与图谱召回",
                    ],
                },
                "raptor": {
                    "reserved": True,
                    "enabled": bool(raptor_config.get("enabled", False)),
                    "scope": str(raptor_config.get("scope") or "file"),
                    "consumes": ["rewritten_query", "lexical_query", "priority_terms", "priority_phrases"],
                    "notes": [
                        "统一复用 query analysis 输出，不重复做过滤抽取",
                        "后续由 RAPTOR 摘要召回分支决定如何消费 summary-friendly query",
                    ],
                },
            },
        }

    def _build_query_analysis_template_summary(
        self,
        *,
        kb: KnowledgeBase,
        retrieval_lexicon_matches: Sequence[Any],
        ignored_lexical_terms: Sequence[str],
    ) -> dict[str, Any]:
        """汇总默认模板命中情况，帮助判断模板是否真的带来收益。"""

        template_match_count = 0
        template_sources: dict[str, int] = {}
        for item in retrieval_lexicon_matches:
            source = str(getattr(item, "source", "") or "").strip()
            if not source.startswith("template:"):
                continue
            template_match_count += 1
            template_sources[source] = template_sources.get(source, 0) + 1
        return {
            "kb_type": str(kb.type or "").strip(),
            "default_template_term_count": len(self._build_default_retrieval_lexicon_template(kb=kb)),
            "default_stopword_count": len(self._build_default_retrieval_stopwords(kb=kb)),
            "template_match_count": template_match_count,
            "template_source_distribution": template_sources,
            "ignored_term_count": len([item for item in ignored_lexical_terms if str(item).strip()]),
        }

    def _merge_query_analysis_defaults(
        self,
        *,
        kb: KnowledgeBase,
        raw_config: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """合并知识库级 query_analysis 默认配置。"""

        merged = dict(raw_config or {})
        kb_query_analysis = dict((kb.retrieval_config or {}).get("query_analysis") or {})
        if kb_query_analysis:
            if "enable_query_rewrite" not in merged and "enable_query_rewrite" in kb_query_analysis:
                merged["enable_query_rewrite"] = kb_query_analysis.get("enable_query_rewrite")
            if "enable_synonym_rewrite" not in merged and "enable_synonym_rewrite" in kb_query_analysis:
                merged["enable_synonym_rewrite"] = kb_query_analysis.get("enable_synonym_rewrite")
            if "auto_filter_mode" not in merged and "auto_filter_mode" in kb_query_analysis:
                merged["auto_filter_mode"] = kb_query_analysis.get("auto_filter_mode")
            if "retrieval_lexicon" not in merged and isinstance(kb_query_analysis.get("retrieval_lexicon"), list):
                merged["retrieval_lexicon"] = list(kb_query_analysis.get("retrieval_lexicon") or [])
            if "retrieval_stopwords" not in merged and isinstance(kb_query_analysis.get("retrieval_stopwords"), list):
                merged["retrieval_stopwords"] = list(kb_query_analysis.get("retrieval_stopwords") or [])
            for key in (
                "llm_candidate_min_confidence",
                "llm_upgrade_confidence_threshold",
                "llm_max_upgrade_count",
            ):
                if key not in merged and key in kb_query_analysis:
                    merged[key] = kb_query_analysis.get(key)
        kb_metadata_fields = list(kb_query_analysis.get("metadata_fields") or []) if isinstance(kb_query_analysis.get("metadata_fields"), list) else []
        request_metadata_fields = list(merged.get("metadata_fields") or []) if isinstance(merged.get("metadata_fields"), list) else []
        extra_metadata_fields = list(merged.get("extra_metadata_fields") or []) if isinstance(merged.get("extra_metadata_fields"), list) else []
        override_metadata_fields = list(merged.get("override_metadata_fields") or []) if isinstance(merged.get("override_metadata_fields"), list) else []
        if override_metadata_fields:
            merged["metadata_fields"] = override_metadata_fields
        else:
            merged["metadata_fields"] = [*(request_metadata_fields or kb_metadata_fields), *extra_metadata_fields]
        kb_persistent_context = dict((kb.retrieval_config or {}).get("persistent_context") or {})
        if "enable_doc_summary_retrieval" not in merged and "enable_doc_summary_retrieval" in kb_persistent_context:
            merged["enable_doc_summary_retrieval"] = kb_persistent_context.get("enable_doc_summary_retrieval")
        merged["retrieval_lexicon"] = self._merge_retrieval_lexicon_templates(
            kb=kb,
            raw_items=list(merged.get("retrieval_lexicon") or []),
        )
        merged["retrieval_stopwords"] = self._merge_retrieval_stopword_templates(
            kb=kb,
            raw_terms=list(merged.get("retrieval_stopwords") or []),
        )
        return merged

    def _merge_retrieval_lexicon_templates(
        self,
        *,
        kb: KnowledgeBase,
        raw_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """按知识库类型合并默认检索词表模板。"""

        merged_items: dict[str, dict[str, Any]] = {}
        for item in list(self._build_default_retrieval_lexicon_template(kb=kb)) + list(raw_items or []):
            normalized_item = dict(item or {})
            term = str(normalized_item.get("term") or "").strip()
            if not term:
                continue
            key = term.lower()
            existing = dict(merged_items.get(key) or {})
            aliases = [
                str(value).strip()
                for value in [*(existing.get("aliases") or []), *(normalized_item.get("aliases") or [])]
                if str(value or "").strip()
            ]
            merged_items[key] = {
                "term": term,
                "aliases": list(dict.fromkeys(aliases)),
                "is_phrase": bool(normalized_item.get("is_phrase", existing.get("is_phrase", True))),
                "weight": max(float(existing.get("weight") or 0), float(normalized_item.get("weight") or 0)),
                "enabled": normalized_item.get("enabled", existing.get("enabled", True)),
                "source": str(normalized_item.get("source") or existing.get("source") or "custom").strip() or "custom",
            }
        return list(merged_items.values())

    def _merge_retrieval_stopword_templates(
        self,
        *,
        kb: KnowledgeBase,
        raw_terms: list[str],
    ) -> list[str]:
        """按知识库类型合并默认忽略词模板。"""

        merged_terms: list[str] = []
        for term in [*self._build_default_retrieval_stopwords(kb=kb), *list(raw_terms or [])]:
            normalized = str(term or "").strip()
            if normalized and normalized not in merged_terms:
                merged_terms.append(normalized)
        return merged_terms

    def _extract_query_analysis_extra_stopwords(
        self,
        *,
        kb: KnowledgeBase,
        raw_config: Mapping[str, Any] | None,
    ) -> list[str]:
        """提取知识库/请求侧显式配置的额外停用词，不包含默认模板词。"""

        kb_query_analysis = dict((kb.retrieval_config or {}).get("query_analysis") or {})
        raw_terms = []
        if isinstance(kb_query_analysis.get("retrieval_stopwords"), list):
            raw_terms.extend(list(kb_query_analysis.get("retrieval_stopwords") or []))
        if isinstance((raw_config or {}).get("retrieval_stopwords"), list):
            raw_terms.extend(list((raw_config or {}).get("retrieval_stopwords") or []))
        result: list[str] = []
        for term in raw_terms:
            normalized = str(term or "").strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def _build_default_retrieval_lexicon_template(self, *, kb: KnowledgeBase) -> list[dict[str, Any]]:
        """根据知识库类型提供轻量默认检索词表模板。"""

        kb_type = str(kb.type or "").strip()
        if kb_type == "qa":
            return [
                {"term": "如何", "aliases": ["怎么", "怎样"], "is_phrase": True, "weight": 0.92, "enabled": True, "source": "template:qa"},
                {"term": "原因", "aliases": ["为什么", "为何"], "is_phrase": True, "weight": 0.9, "enabled": True, "source": "template:qa"},
                {"term": "步骤", "aliases": ["流程", "操作步骤"], "is_phrase": True, "weight": 0.88, "enabled": True, "source": "template:qa"},
                {"term": "配置", "aliases": ["设置"], "is_phrase": False, "weight": 0.86, "enabled": True, "source": "template:qa"},
                {"term": "报错", "aliases": ["错误", "异常"], "is_phrase": False, "weight": 0.9, "enabled": True, "source": "template:qa"},
                {"term": "排查", "aliases": ["定位问题", "问题排查"], "is_phrase": True, "weight": 0.88, "enabled": True, "source": "template:qa"},
            ]
        if kb_type == "table":
            return [
                {"term": "地区", "aliases": ["区域", "大区"], "is_phrase": False, "weight": 0.9, "enabled": True, "source": "template:table"},
                {"term": "年份", "aliases": ["年度"], "is_phrase": False, "weight": 0.9, "enabled": True, "source": "template:table"},
                {"term": "产品", "aliases": ["产品线"], "is_phrase": False, "weight": 0.88, "enabled": True, "source": "template:table"},
                {"term": "同比", "aliases": ["同比增长"], "is_phrase": True, "weight": 0.86, "enabled": True, "source": "template:table"},
                {"term": "环比", "aliases": ["环比增长"], "is_phrase": True, "weight": 0.86, "enabled": True, "source": "template:table"},
                {"term": "合计", "aliases": ["总计", "汇总"], "is_phrase": False, "weight": 0.88, "enabled": True, "source": "template:table"},
                {"term": "排名", "aliases": ["排行", "top"], "is_phrase": False, "weight": 0.86, "enabled": True, "source": "template:table"},
            ]
        return [
            {"term": "SLA", "aliases": ["服务等级协议"], "is_phrase": True, "weight": 0.88, "enabled": True, "source": "template:general"},
            {"term": "灰度发布", "aliases": ["灰度"], "is_phrase": True, "weight": 0.86, "enabled": True, "source": "template:general"},
            {"term": "回滚策略", "aliases": ["回滚"], "is_phrase": True, "weight": 0.84, "enabled": True, "source": "template:general"},
            {"term": "多租户隔离", "aliases": ["租户隔离"], "is_phrase": True, "weight": 0.9, "enabled": True, "source": "template:general"},
            {"term": "权限模型", "aliases": ["权限设计", "权限控制模型"], "is_phrase": True, "weight": 0.84, "enabled": True, "source": "template:general"},
        ]

    def _build_default_retrieval_stopwords(self, *, kb: KnowledgeBase) -> list[str]:
        """根据知识库类型提供轻量默认忽略词。"""

        kb_type = str(kb.type or "").strip()
        if kb_type == "qa":
            return ["问题", "知识", "内容", "一下", "请问"]
        if kb_type == "table":
            return ["数据", "表格", "记录", "信息", "看一下"]
        return ["介绍", "说明", "相关内容", "资料", "文档", "看一下"]

    async def _build_query_analysis_metadata_fields(
        self,
        *,
        kb: KnowledgeBase,
        raw_config: Mapping[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """构建查询分析可识别的字段定义。"""

        merged_fields: dict[str, dict[str, Any]] = {}
        for field in list((raw_config or {}).get("metadata_fields") or []):
            key = str((field or {}).get("key") or (field or {}).get("name") or "").strip()
            if key:
                merged_fields[key] = dict(field or {})

        if str(kb.type or "").strip() == "table":
            table_retrieval = dict((kb.retrieval_config or {}).get("table") or {})
            table_schema = dict(table_retrieval.get("schema") or {})
            for column in list(table_schema.get("columns") or []):
                column_name = str((column or {}).get("name") or "").strip()
                if not column_name or not bool((column or {}).get("filterable")):
                    continue
                current = dict(merged_fields.get(column_name) or {})
                current.setdefault("key", column_name)
                current.setdefault("name", column_name)
                if not current.get("aliases"):
                    current["aliases"] = [
                        str(item).strip()
                        for item in list((column or {}).get("aliases") or [])
                        if str(item or "").strip()
                    ]
                if not current.get("enum_values"):
                    current["enum_values"] = list((column or {}).get("enum_values") or [])
                current["target"] = "search_unit_metadata"
                current["metadata_path"] = ["filter_fields", column_name]
                merged_fields[column_name] = current

        if str(kb.type or "").strip() == "qa":
            for field in await self._build_qa_query_analysis_metadata_fields(kb=kb):
                key = str((field or {}).get("key") or "").strip()
                if not key:
                    continue
                merged_fields[key] = {**field, **dict(merged_fields.get(key) or {})}

        if not merged_fields:
            for field in await self._build_runtime_kb_doc_metadata_fields(kb=kb):
                key = str((field or {}).get("key") or "").strip()
                if not key:
                    continue
                merged_fields[key] = dict(field or {})

        return list(merged_fields.values())

    async def _build_runtime_kb_doc_metadata_fields(self, *, kb: KnowledgeBase) -> list[dict[str, Any]]:
        """从知识库文档元数据中兜底推导查询分析字段定义。"""

        if str(kb.type or "").strip() in {"table", "qa"}:
            return []

        stmt = (
            select(KnowledgeBaseDocument.custom_metadata)
            .where(
                KnowledgeBaseDocument.tenant_id == kb.tenant_id,
                KnowledgeBaseDocument.kb_id == kb.id,
                KnowledgeBaseDocument.is_enabled.is_(True),
                KnowledgeBaseDocument.custom_metadata.is_not(None),
            )
            .order_by(KnowledgeBaseDocument.updated_at.desc())
            .limit(200)
        )
        rows = (await self.session.execute(stmt)).all()
        discovered: dict[tuple[str, ...], dict[str, Any]] = {}
        for row in rows:
            payload = row[0] if row else None
            if not isinstance(payload, dict):
                continue
            self._collect_runtime_metadata_field_stats(
                payload=payload,
                path_prefix=[],
                discovered=discovered,
            )

        items: list[dict[str, Any]] = []
        for path, stats in discovered.items():
            if not path:
                continue
            key = ".".join(path)
            enum_values = list(stats.get("enum_values") or [])
            item: dict[str, Any] = {
                "key": key,
                "name": key,
                "target": "document_metadata",
                "metadata_path": list(path),
                "source": "runtime:kbd_custom_metadata",
            }
            if enum_values:
                item["enum_values"] = enum_values
                item["options"] = list(enum_values)
            items.append(item)
        return items

    def _collect_runtime_metadata_field_stats(
        self,
        *,
        payload: Mapping[str, Any],
        path_prefix: Sequence[str],
        discovered: dict[tuple[str, ...], dict[str, Any]],
    ) -> None:
        """递归收集可用于查询分析的 metadata 字段与枚举候选。"""

        for raw_key, raw_value in payload.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            path = [*path_prefix, key]
            if isinstance(raw_value, Mapping):
                self._collect_runtime_metadata_field_stats(
                    payload=raw_value,
                    path_prefix=path,
                    discovered=discovered,
                )
                continue
            if isinstance(raw_value, list):
                scalar_values: list[str] = []
                for item in raw_value:
                    normalized_item = self._normalize_runtime_metadata_scalar(item)
                    if normalized_item is not None:
                        scalar_values.append(normalized_item)
                if not scalar_values:
                    continue
                stats = discovered.setdefault(tuple(path), {"enum_values": []})
                enum_values = list(stats.get("enum_values") or [])
                for value in scalar_values:
                    if value not in enum_values:
                        enum_values.append(value)
                    if len(enum_values) >= 20:
                        break
                stats["enum_values"] = enum_values[:20]
                continue

            scalar_value = self._normalize_runtime_metadata_scalar(raw_value)
            if scalar_value is None:
                continue
            stats = discovered.setdefault(tuple(path), {"enum_values": []})
            enum_values = list(stats.get("enum_values") or [])
            if scalar_value not in enum_values:
                enum_values.append(scalar_value)
            stats["enum_values"] = enum_values[:20]

    def _normalize_runtime_metadata_scalar(self, value: Any) -> str | None:
        """把文档元数据中的标量值标准化为可展示的字符串。"""

        if value is None or isinstance(value, (dict, tuple, set)):
            return None
        normalized = str(value).strip()
        return normalized or None

    def _build_query_analysis_retrieval_lexicon(
        self,
        *,
        kb: KnowledgeBase,
        raw_config: Mapping[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """构建查询分析阶段的检索词表，并按知识库类型补充运行时词条。"""

        merged_items: dict[str, dict[str, Any]] = {}
        for raw_item in list((raw_config or {}).get("retrieval_lexicon") or []):
            item = dict(raw_item or {})
            term = str(item.get("term") or "").strip()
            if not term:
                continue
            merged_items[term.lower()] = item

        if str(kb.type or "").strip() == "table":
            table_retrieval = dict((kb.retrieval_config or {}).get("table") or {})
            table_schema = dict(table_retrieval.get("schema") or {})
            for column in list(table_schema.get("columns") or []):
                column_name = str((column or {}).get("name") or "").strip()
                if not column_name:
                    continue

                self._upsert_runtime_lexicon_item(
                    merged_items=merged_items,
                    term=column_name,
                    aliases=[
                        str(item).strip()
                        for item in list((column or {}).get("aliases") or [])
                        if str(item or "").strip()
                    ],
                    weight=1.15 if bool((column or {}).get("filterable")) else 1.0,
                    source="runtime:table_schema",
                )
                for enum_value in list((column or {}).get("enum_values") or []):
                    normalized_enum = self._extract_query_analysis_option_value(enum_value)
                    if not normalized_enum:
                        continue
                    self._upsert_runtime_lexicon_item(
                        merged_items=merged_items,
                        term=normalized_enum,
                        aliases=self._extract_query_analysis_option_aliases(enum_value),
                        weight=0.92,
                        source="runtime:table_enum",
                    )

        return list(merged_items.values())

    def _upsert_runtime_lexicon_item(
        self,
        *,
        merged_items: dict[str, dict[str, Any]],
        term: str,
        aliases: list[str],
        weight: float,
        source: str,
    ) -> None:
        """将运行时推导出的检索词条合并到最终词表。"""

        normalized_term = str(term or "").strip()
        if not normalized_term:
            return

        item_key = normalized_term.lower()
        existing = dict(merged_items.get(item_key) or {})
        merged_aliases = [
            str(item).strip()
            for item in [*(existing.get("aliases") or []), *aliases]
            if str(item or "").strip()
        ]
        merged_items[item_key] = {
            "term": normalized_term,
            "aliases": list(dict.fromkeys(merged_aliases)),
            "is_phrase": bool(existing.get("is_phrase", True)),
            "weight": max(float(existing.get("weight") or 0), float(weight)),
            "enabled": existing.get("enabled", True),
            "source": str(existing.get("source") or source).strip() or source,
        }

    def _extract_query_analysis_option_value(self, option: Any) -> str:
        """提取 schema 选项的标准值，统一兼容字符串与对象格式。"""

        if isinstance(option, dict):
            return str(option.get("value") or option.get("id") or option.get("label") or option.get("name") or "").strip()
        return str(option or "").strip()

    def _extract_query_analysis_option_aliases(self, option: Any) -> list[str]:
        """提取 schema 选项别名，避免表格列枚举维护两套词表。"""

        if not isinstance(option, dict):
            return []
        return [
            str(item).strip()
            for item in list(option.get("aliases") or [])
            if str(item or "").strip()
        ]

    async def _build_qa_query_analysis_metadata_fields(
        self,
        *,
        kb: KnowledgeBase,
    ) -> list[dict[str, Any]]:
        """基于 QA 主事实表生成分类/标签过滤字段定义。"""

        if str(kb.type or "").strip() != "qa":
            return []

        qa_config = normalize_qa_retrieval_config(kb.retrieval_config or {})
        fields: list[dict[str, Any]] = []

        if qa_config.get("enable_category_filter"):
            category_stmt = (
                select(KBQARow.category)
                .where(
                    KBQARow.tenant_id == kb.tenant_id,
                    KBQARow.kb_id == kb.id,
                    KBQARow.is_enabled.is_(True),
                    KBQARow.category.is_not(None),
                    KBQARow.category != "",
                )
                .distinct()
                .order_by(KBQARow.category.asc())
                .limit(80)
            )
            categories = [
                str(row[0]).strip()
                for row in (await self.session.execute(category_stmt)).all()
                if str(row[0] or "").strip()
            ]
            if categories:
                fields.append(
                    {
                        "key": "category",
                        "name": "分类",
                        "aliases": ["分类", "类别", "问题分类"],
                        "enum_values": categories,
                        "target": "search_unit_metadata",
                        "metadata_path": ["qa_fields", "category"],
                    }
                )

        if qa_config.get("enable_tag_filter"):
            tag_stmt = select(KBQARow.tags).where(
                KBQARow.tenant_id == kb.tenant_id,
                KBQARow.kb_id == kb.id,
                KBQARow.is_enabled.is_(True),
            )
            qa_tags = self._collect_distinct_json_tags(
                (row[0] for row in (await self.session.execute(tag_stmt)).all()),
                limit=120,
            )
            if qa_tags:
                fields.append(
                    {
                        "key": "tag",
                        "name": "问答标签",
                        "aliases": ["标签", "问答标签", "知识标签"],
                        "enum_values": qa_tags,
                        "target": "search_unit_metadata",
                        "metadata_path": ["qa_fields", "tag"],
                    }
                )

        return fields

    async def _build_filter_debug_summary(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        analyzed_filters: RetrievalFilterSet,
        resolved_filters: ResolvedCandidateFilter,
        auto_filter_signals: Sequence[QueryAnalysisAutoFilterSignal] = (),
    ) -> dict[str, Any]:
        """构建更适合前端阅读的过滤命中摘要。"""

        matched_docs: list[dict[str, str]] = []
        if resolved_filters.kb_doc_ids:
            stmt = (
                select(KnowledgeBaseDocument, Document)
                .join(
                    Document,
                    and_(
                        Document.id == KnowledgeBaseDocument.document_id,
                        Document.tenant_id == current_user.tenant_id,
                    ),
                )
                .where(
                    KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
                    KnowledgeBaseDocument.kb_id == kb.id,
                    KnowledgeBaseDocument.id.in_(resolved_filters.kb_doc_ids[:8]),
                )
            )
            rows = (await self.session.execute(stmt)).all()
            matched_docs = [
                {
                    "kb_doc_id": str(kb_doc.id),
                    "document_id": str(document.id),
                    "name": str(kb_doc.display_name or document.name or "未命名文档"),
                }
                for kb_doc, document in rows
                if kb_doc.id is not None
            ]

        return {
            "requested_filter_counts": {
                "kb_doc_ids": len(analyzed_filters.kb_doc_ids),
                "folder_ids": len(analyzed_filters.folder_ids),
                "folder_tag_ids": len(analyzed_filters.folder_tag_ids),
                "tag_ids": len(analyzed_filters.tag_ids),
                "document_metadata_keys": len(analyzed_filters.document_metadata),
                "search_unit_metadata_keys": len(analyzed_filters.search_unit_metadata),
                "filter_expression": 1 if analyzed_filters.filter_expression else 0,
            },
            "applied_filter_counts": {
                "kb_doc_ids": len(resolved_filters.kb_doc_ids),
                "document_ids": len(resolved_filters.document_ids),
                "content_group_ids": len(resolved_filters.content_group_ids),
            },
            "requested_document_metadata": dict(analyzed_filters.document_metadata),
            "requested_search_unit_metadata": dict(analyzed_filters.search_unit_metadata),
            "requested_filter_expression": dict(analyzed_filters.filter_expression or {}),
            "resolved_filter_expression": dict(resolved_filters.filter_expression or {}),
            "expression_debug": dict(resolved_filters.expression_debug or {}),
            "matched_documents": matched_docs,
            "matched_document_count": len(resolved_filters.kb_doc_ids),
            "matched_content_group_count": len(resolved_filters.content_group_ids),
            "filter_applied": resolved_filters.filter_applied,
            "auto_filter_signal_counts": {
                "doc_tag": len([item for item in auto_filter_signals if item.signal_type == "doc_tag"]),
                "folder_tag": len([item for item in auto_filter_signals if item.signal_type == "folder_tag"]),
                "document_metadata": len([item for item in auto_filter_signals if item.signal_type == "document_metadata"]),
                "search_unit_metadata": len([item for item in auto_filter_signals if item.signal_type == "search_unit_metadata"]),
            },
            "auto_metadata_debug": dict(resolved_filters.auto_metadata_debug or {}),
        }

    def _build_result_debug_summary(self, *, items: list[dict[str, Any]]) -> dict[str, Any]:
        """汇总结果侧命中解释，方便前端直接渲染。"""

        scope_distribution: dict[str, int] = {}
        document_names: list[str] = []
        doc_summary_count = 0
        table_hit_explanations: list[dict[str, Any]] = []
        qa_hit_explanations: list[dict[str, Any]] = []
        strategy_contribution_summary = {
            "query_intent_bonus_result_count": 0,
            "metadata_bonus_result_count": 0,
            "repeated_hit_bonus_result_count": 0,
            "table_context_result_count": 0,
            "qa_answer_result_count": 0,
            "qa_question_result_count": 0,
        }
        for item in items:
            metadata = dict(item.get("metadata") or {})
            for scope in list(metadata.get("matched_scopes") or []):
                normalized_scope = str(scope or "").strip()
                if not normalized_scope:
                    continue
                scope_distribution[normalized_scope] = scope_distribution.get(normalized_scope, 0) + 1
            if metadata.get("doc_summary_hit"):
                doc_summary_count += 1
            contributions = dict(metadata.get("strategy_contributions") or {})
            if float(contributions.get("query_intent_bonus") or 0) > 0:
                strategy_contribution_summary["query_intent_bonus_result_count"] += 1
            if float(contributions.get("metadata_bonus") or 0) > 0:
                strategy_contribution_summary["metadata_bonus_result_count"] += 1
            if float(contributions.get("repeated_hit_bonus") or 0) > 0:
                strategy_contribution_summary["repeated_hit_bonus_result_count"] += 1
            document_name = str(((item.get("source") or {}).get("document_name")) or "").strip()
            if document_name and document_name not in document_names:
                document_names.append(document_name)
            if str(metadata.get("kb_type") or "").strip() == "table":
                table_hit_explanation = self._build_table_hit_explanation(item=item)
                if table_hit_explanation:
                    table_hit_explanations.append(table_hit_explanation)
                    strategy_contribution_summary["table_context_result_count"] += 1
            if str(metadata.get("kb_type") or "").strip() == "qa":
                qa_hit_explanation = self._build_qa_hit_explanation(item=item)
                if qa_hit_explanation:
                    qa_hit_explanations.append(qa_hit_explanation)
                    if "answer" in list(qa_hit_explanation.get("scopes") or []):
                        strategy_contribution_summary["qa_answer_result_count"] += 1
                    if "question" in list(qa_hit_explanation.get("scopes") or []):
                        strategy_contribution_summary["qa_question_result_count"] += 1

        return {
            "matched_scope_distribution": scope_distribution,
            "matched_document_names": document_names[:12],
            "matched_document_count": len(document_names),
            "doc_summary_result_count": doc_summary_count,
            "table_hit_explanations": table_hit_explanations[:8],
            "qa_hit_explanations": qa_hit_explanations[:8],
            "strategy_contribution_summary": strategy_contribution_summary,
        }

    def _build_table_hit_explanation(self, *, item: Mapping[str, Any]) -> dict[str, Any] | None:
        """为表格结果生成可读的命中原因摘要。"""

        metadata = dict(item.get("metadata") or {})
        scopes = [str(scope).strip() for scope in list(metadata.get("matched_scopes") or []) if str(scope).strip()]
        if not scopes:
            return None

        field_names = [str(value).strip() for value in list(metadata.get("field_names") or []) if str(value).strip()]
        dimension_field_names = [str(value).strip() for value in list(metadata.get("dimension_field_names") or []) if str(value).strip()]
        metric_field_names = [str(value).strip() for value in list(metadata.get("metric_field_names") or []) if str(value).strip()]
        identifier_field_names = [str(value).strip() for value in list(metadata.get("identifier_field_names") or []) if str(value).strip()]
        dimension_explanation_text = str(metadata.get("dimension_explanation_text") or "").strip()
        metric_explanation_text = str(metadata.get("metric_explanation_text") or "").strip()
        filter_fields = {
            str(key).strip(): str(value).strip()
            for key, value in dict(metadata.get("filter_fields") or {}).items()
            if str(key).strip() and str(value or "").strip()
        }
        reasons: list[str] = []
        if "row_group" in scopes:
            reasons.append("命中了增强后的表格上下文")
        if "row" in scopes:
            reasons.append("命中了完整行")
        if "row_fragment" in scopes:
            reasons.append("命中了行片段")
        if dimension_field_names:
            reasons.append(f"识别到维度字段: {' / '.join(dimension_field_names[:4])}")
        if metric_field_names:
            reasons.append(f"识别到指标字段: {' / '.join(metric_field_names[:4])}")
        if identifier_field_names:
            reasons.append(f"识别到唯一标识字段: {' / '.join(identifier_field_names[:4])}")
        if filter_fields:
            reasons.append(
                "当前行筛选值: "
                + " / ".join([f"{key}={value}" for key, value in list(filter_fields.items())[:4]])
            )
        if str(metadata.get("row_explanation_text") or "").strip():
            reasons.append(str(metadata.get("row_explanation_text") or "").strip())
        if dimension_explanation_text:
            reasons.append(dimension_explanation_text)
        if metric_explanation_text:
            reasons.append(metric_explanation_text)

        return {
            "title": str(item.get("title") or "").strip(),
            "scopes": scopes,
            "row_identity_text": str(metadata.get("row_identity_text") or "").strip() or None,
            "sheet_name": str(metadata.get("sheet_name") or "").strip() or None,
            "field_names": field_names[:8],
            "dimension_field_names": dimension_field_names[:8],
            "metric_field_names": metric_field_names[:8],
            "identifier_field_names": identifier_field_names[:8],
            "dimension_explanation_text": dimension_explanation_text or None,
            "metric_explanation_text": metric_explanation_text or None,
            "filter_fields": filter_fields,
            "reasons": reasons,
        }

    def _build_qa_hit_explanation(self, *, item: Mapping[str, Any]) -> dict[str, Any] | None:
        """为 QA 结果生成可读的命中原因摘要。"""

        metadata = dict(item.get("metadata") or {})
        scopes = [str(scope).strip() for scope in list(metadata.get("matched_scopes") or []) if str(scope).strip()]
        if not scopes:
            return None

        qa_fields = dict(metadata.get("qa_fields") or {})
        qa_runtime_config = dict(metadata.get("qa_runtime_config") or {})
        category = str(qa_fields.get("category") or "").strip()
        tags = [str(value).strip() for value in list(qa_fields.get("tags") or []) if str(value).strip()]
        reasons: list[str] = []
        if "question" in scopes:
            reasons.append("命中了问句投影")
        if "answer" in scopes:
            reasons.append("命中了答案投影")
        if category:
            reasons.append(f"分类字段参与理解: {category}")
        if tags:
            reasons.append(f"标签字段参与理解: {' / '.join(tags[:4])}")

        return {
            "title": str(item.get("title") or "").strip(),
            "scopes": scopes,
            "question_text": str(metadata.get("question_text") or "").strip() or None,
            "category": category or None,
            "tags": tags[:8],
            "qa_runtime_config": qa_runtime_config if qa_runtime_config else None,
            "reasons": reasons,
        }

    def _collect_distinct_json_tags(
        self,
        raw_values: Iterable[Any],
        *,
        limit: int,
    ) -> list[str]:
        """把 JSON 数组标签安全整理为稳定的候选值列表。"""

        seen: set[str] = set()
        ordered: list[str] = []
        for raw_value in raw_values:
            if not isinstance(raw_value, list):
                continue
            for item in raw_value:
                normalized = str(item or "").strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                ordered.append(normalized)
                if len(ordered) >= limit:
                    return sorted(ordered)
        return sorted(ordered)

    def _apply_table_filter_mapping(
        self,
        *,
        kb: KnowledgeBase,
        filters: RetrievalFilterSet,
        raw_config: Mapping[str, Any] | None,
    ) -> RetrievalFilterSet:
        """把表格字段过滤显式标记为行级过滤信号。"""

        if str(kb.type or "").strip() != "table" or not filters.document_metadata:
            return filters

        table_retrieval = dict((kb.retrieval_config or {}).get("table") or {})
        table_schema = dict(table_retrieval.get("schema") or {})
        table_field_names = {
            str((column or {}).get("name") or "").strip()
            for column in list(table_schema.get("columns") or [])
            if str((column or {}).get("name") or "").strip() and bool((column or {}).get("filterable"))
        }
        if not table_field_names:
            return filters

        mapped_document_metadata = dict(filters.document_metadata)
        mapped_search_unit_metadata = dict(filters.search_unit_metadata)
        filter_fields = dict(mapped_search_unit_metadata.get("filter_fields") or {})
        moved = False
        for key in list(mapped_document_metadata.keys()):
            if key not in table_field_names:
                continue
            value = mapped_document_metadata.pop(key)
            if value in (None, ""):
                continue
            filter_fields[key] = value
            moved = True

        if not moved:
            return filters

        mapped_search_unit_metadata["filter_fields"] = filter_fields
        return RetrievalFilterSet(
            kb_doc_ids=list(filters.kb_doc_ids),
            document_ids=list(filters.document_ids),
            content_group_ids=list(filters.content_group_ids),
            folder_ids=list(filters.folder_ids),
            tag_ids=list(filters.tag_ids),
            folder_tag_ids=list(filters.folder_tag_ids),
            document_metadata=mapped_document_metadata,
            search_unit_metadata=mapped_search_unit_metadata,
            filter_expression=dict(filters.filter_expression or {}),
            include_descendant_folders=filters.include_descendant_folders,
            only_tagged=filters.only_tagged,
            latest_days=filters.latest_days,
        )

    def _apply_qa_filter_mapping(
        self,
        *,
        kb: KnowledgeBase,
        filters: RetrievalFilterSet,
    ) -> RetrievalFilterSet:
        """把 QA 元数据过滤转成行级 QA 过滤信号。"""

        if str(kb.type or "").strip() != "qa" or not filters.document_metadata:
            return filters

        mapped_document_metadata = dict(filters.document_metadata)
        mapped_search_unit_metadata = dict(filters.search_unit_metadata)
        qa_fields = dict(mapped_search_unit_metadata.get("qa_fields") or {})
        moved = False

        for source_key, target_key in {"category": "category", "tag": "tag", "tags": "tag"}.items():
            if source_key not in mapped_document_metadata:
                continue
            value = mapped_document_metadata.pop(source_key)
            if value in (None, ""):
                continue
            qa_fields[target_key] = value
            moved = True

        if not moved:
            return filters

        mapped_search_unit_metadata["qa_fields"] = qa_fields
        return RetrievalFilterSet(
            kb_doc_ids=list(filters.kb_doc_ids),
            document_ids=list(filters.document_ids),
            content_group_ids=list(filters.content_group_ids),
            folder_ids=list(filters.folder_ids),
            tag_ids=list(filters.tag_ids),
            folder_tag_ids=list(filters.folder_tag_ids),
            document_metadata=mapped_document_metadata,
            search_unit_metadata=mapped_search_unit_metadata,
            filter_expression=dict(filters.filter_expression or {}),
            include_descendant_folders=filters.include_descendant_folders,
            only_tagged=filters.only_tagged,
            latest_days=filters.latest_days,
        )

    async def _resolve_candidate_filters(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        filters: RetrievalFilterSet,
        auto_filter_signals: Sequence[QueryAnalysisAutoFilterSignal] = (),
    ) -> ResolvedCandidateFilter:
        """先在文档层完成硬过滤，再把候选范围传给检索层。"""

        auto_document_metadata_filters = self._collect_auto_document_metadata_filters(auto_filter_signals)
        document_filter_expression = await self._prepare_document_filter_expression(
            kb=kb,
            expression=filters.filter_expression,
            include_descendants=filters.include_descendant_folders,
        )
        has_document_filter_expression = filter_expression_has_field(
            document_filter_expression,
            {
                "kb_doc",
                "kb_doc_id",
                "document",
                "document_id",
                "folder",
                "folder_id",
                "folder_tag",
                "folder_tag_id",
                "tag",
                "doc_tag",
                "tag_id",
                "metadata",
                "document_metadata",
            },
        )
        has_search_unit_filter_expression = filter_expression_has_field(
            document_filter_expression,
            {"search_unit_metadata"},
        )
        expression_debug = {
            "requested": bool(filters.filter_expression),
            "resolved": bool(document_filter_expression),
            "document_scope_applied": has_document_filter_expression,
            "search_unit_scope_applied": has_search_unit_filter_expression,
            "resolved_expression": dict(document_filter_expression or {}),
        }
        filter_applied = any(
            [
                bool(filters.kb_doc_ids),
                bool(filters.document_ids),
                bool(filters.content_group_ids),
                bool(filters.folder_ids),
                bool(filters.tag_ids),
                bool(filters.folder_tag_ids),
                bool(filters.document_metadata),
                bool(filters.search_unit_metadata),
                bool(filters.only_tagged),
                filters.latest_days is not None,
                bool(auto_document_metadata_filters),
                has_document_filter_expression,
                has_search_unit_filter_expression,
            ]
        )
        if not filter_applied:
            return ResolvedCandidateFilter(
                filter_applied=False,
                filter_expression=document_filter_expression,
                expression_debug=expression_debug,
            )
        if filters.content_group_ids:
            return ResolvedCandidateFilter(
                kb_doc_ids=list(filters.kb_doc_ids),
                document_ids=list(filters.document_ids),
                content_group_ids=list(filters.content_group_ids),
                filter_applied=True,
                filter_expression=document_filter_expression,
                expression_debug=expression_debug,
            )

        stmt: Select[Any] = (
            select(KnowledgeBaseDocument.id, KnowledgeBaseDocument.document_id)
            .join(
                Document,
                and_(
                    Document.id == KnowledgeBaseDocument.document_id,
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted.is_(False),
                ),
            )
            .where(
                KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
                KnowledgeBaseDocument.kb_id == kb.id,
                KnowledgeBaseDocument.parse_status == "completed",
                KnowledgeBaseDocument.is_enabled.is_(True),
            )
        )

        if filters.kb_doc_ids:
            stmt = stmt.where(KnowledgeBaseDocument.id.in_(filters.kb_doc_ids))
        if filters.document_ids:
            stmt = stmt.where(KnowledgeBaseDocument.document_id.in_(filters.document_ids))

        base_folder_ids = await self._resolve_folder_ids_by_tags(
            kb=kb,
            folder_ids=filters.folder_ids,
            folder_tag_ids=filters.folder_tag_ids,
        )
        folder_ids = await self._expand_folder_ids(
            kb=kb,
            folder_ids=base_folder_ids,
            include_descendants=filters.include_descendant_folders,
        )
        if (filters.folder_ids or filters.folder_tag_ids) and not folder_ids:
            return ResolvedCandidateFilter(
                filter_applied=True,
                filter_expression=document_filter_expression,
                expression_debug=expression_debug,
            )
        if folder_ids:
            stmt = stmt.where(KnowledgeBaseDocument.folder_id.in_(folder_ids))

        if filters.latest_days is not None:
            latest_threshold = datetime.now(timezone.utc) - timedelta(days=max(1, filters.latest_days))
            stmt = stmt.where(
                or_(
                    KnowledgeBaseDocument.parse_ended_at >= latest_threshold,
                    KnowledgeBaseDocument.updated_at >= latest_threshold,
                )
            )

        if filters.document_metadata:
            metadata_conditions = []
            for key, value in filters.document_metadata.items():
                serialized = self._serialize_metadata_filter_value(value)
                metadata_conditions.append(
                    or_(
                        KnowledgeBaseDocument.custom_metadata[key].astext == serialized,
                        Document.metadata_info[key].astext == serialized,
                    )
                )
            if metadata_conditions:
                stmt = stmt.where(and_(*metadata_conditions))

        expression_condition = (
            None
            if has_search_unit_filter_expression
            else self._build_document_filter_expression_condition(document_filter_expression)
        )
        if expression_condition is not None:
            stmt = stmt.where(expression_condition)

        auto_metadata_debug: dict[str, Any] = {}
        if auto_document_metadata_filters:
            auto_conditions = []
            for key, config in auto_document_metadata_filters.items():
                values = [
                    self._serialize_metadata_filter_value(value)
                    for value in list(config.get("values") or [])
                    if str(value or "").strip()
                ]
                values = list(dict.fromkeys(values))
                if not values:
                    continue
                kb_doc_value = KnowledgeBaseDocument.custom_metadata[key].astext
                doc_value = Document.metadata_info[key].astext
                match_condition = or_(kb_doc_value.in_(values), doc_value.in_(values))
                if str(config.get("match_mode") or "match_or_missing") == "match_only":
                    auto_conditions.append(match_condition)
                else:
                    auto_conditions.append(
                        or_(
                            match_condition,
                            and_(kb_doc_value.is_(None), doc_value.is_(None)),
                        )
                    )
                auto_metadata_debug[key] = {
                    "values": values,
                    "match_mode": str(config.get("match_mode") or "match_or_missing"),
                    "relation": "same_key_values_or__different_keys_and",
                }
            if auto_conditions:
                stmt = stmt.where(and_(*auto_conditions))

        if filters.tag_ids or filters.only_tagged:
            tag_stmt = select(ResourceTag.target_id).where(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.kb_id == kb.id,
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.action == "add",
            )
            if filters.tag_ids:
                unique_tag_ids = list(dict.fromkeys(filters.tag_ids))
                tag_stmt = (
                    tag_stmt.where(ResourceTag.tag_id.in_(unique_tag_ids))
                    .group_by(ResourceTag.target_id)
                    .having(func.count(func.distinct(ResourceTag.tag_id)) >= len(unique_tag_ids))
                )
            else:
                tag_stmt = tag_stmt.group_by(ResourceTag.target_id)
            stmt = stmt.where(KnowledgeBaseDocument.id.in_(tag_stmt))

        rows = (await self.session.execute(stmt)).all()
        kb_doc_ids = [row[0] for row in rows]
        document_ids = [row[1] for row in rows]
        content_group_ids: list[UUID] = []
        if str(kb.type or "").strip() == "table" and filters.search_unit_metadata:
            # 表格字段过滤先落在主事实表，再通过 content_group_id 约束检索层，
            # 避免仅依赖冗余 metadata 导致过滤口径漂移。
            content_group_ids = await self._resolve_table_content_group_ids(
                current_user=current_user,
                kb=kb,
                filters=filters,
                kb_doc_ids=kb_doc_ids,
            )
            if not content_group_ids:
                return ResolvedCandidateFilter(
                    filter_applied=True,
                    filter_expression=document_filter_expression,
                    expression_debug=expression_debug,
                )
        elif str(kb.type or "").strip() == "qa" and filters.search_unit_metadata:
            content_group_ids = await self._resolve_qa_content_group_ids(
                current_user=current_user,
                kb=kb,
                filters=filters,
                kb_doc_ids=kb_doc_ids,
            )
            if filters.search_unit_metadata.get("qa_fields") and not content_group_ids:
                return ResolvedCandidateFilter(
                    filter_applied=True,
                    filter_expression=document_filter_expression,
                    expression_debug=expression_debug,
                )
        return ResolvedCandidateFilter(
            kb_doc_ids=kb_doc_ids,
            document_ids=document_ids,
            content_group_ids=content_group_ids,
            filter_applied=True,
            auto_metadata_debug=auto_metadata_debug,
            filter_expression=document_filter_expression,
            expression_debug=expression_debug,
        )

    def _collect_auto_document_metadata_filters(
        self,
        auto_filter_signals: Sequence[QueryAnalysisAutoFilterSignal],
    ) -> dict[str, dict[str, Any]]:
        """整理自动文档元数据过滤信号，多个 key 为 AND，同 key 多值为 OR。"""

        result: dict[str, dict[str, Any]] = {}
        for signal in auto_filter_signals:
            if signal.signal_type != "document_metadata":
                continue
            key = str(signal.target_id or "").strip()
            value = str(signal.filter_value or "").strip()
            if not key or not value:
                continue
            bucket = result.setdefault(
                key,
                {
                    "values": [],
                    "match_mode": signal.match_mode if signal.match_mode in {"match_or_missing", "match_only"} else "match_or_missing",
                },
            )
            values = list(bucket.get("values") or [])
            if value not in values:
                values.append(value)
            bucket["values"] = values
            if bucket.get("match_mode") != "match_only" and signal.match_mode == "match_only":
                bucket["match_mode"] = "match_only"
        return result

    async def _prepare_document_filter_expression(
        self,
        *,
        kb: KnowledgeBase,
        expression: Mapping[str, Any] | None,
        include_descendants: bool,
    ) -> dict[str, Any]:
        """把表达式中的文件夹标签预解析为文件夹集合，保留 AND/OR/NOT 结构。"""

        if not isinstance(expression, Mapping) or not expression:
            return {}

        async def _prepare_node(node: Mapping[str, Any]) -> dict[str, Any]:
            op = str(node.get("op") or "").strip().lower()
            if op in {"and", "or"}:
                items = [
                    item
                    for item in [await _prepare_node(raw_item) for raw_item in list(node.get("items") or []) if isinstance(raw_item, Mapping)]
                    if item
                ]
                return {"op": op, "items": items} if items else {}
            if op == "not":
                items = [
                    item
                    for item in [await _prepare_node(raw_item) for raw_item in list(node.get("items") or [])[:1] if isinstance(raw_item, Mapping)]
                    if item
                ]
                return {"op": "not", "items": items} if items else {}

            field = str(node.get("field") or "").strip()
            if field not in {"folder_tag", "folder_tag_id"}:
                return dict(node)
            tag_ids = _coerce_uuid_list(node.get("values"))
            if not tag_ids:
                return {"field": "folder", "op": str(node.get("op") or "in"), "path": [], "values": []}
            folder_ids = await self._resolve_folder_ids_by_tags(kb=kb, folder_ids=[], folder_tag_ids=tag_ids)
            folder_ids = await self._expand_folder_ids(
                kb=kb,
                folder_ids=folder_ids,
                include_descendants=include_descendants,
            )
            return {
                "field": "folder",
                "op": str(node.get("op") or "in"),
                "path": [],
                "values": [str(item) for item in folder_ids],
            }

        return await _prepare_node(expression)

    def _extract_search_unit_filter_expression(self, expression: Mapping[str, Any] | None) -> dict[str, Any]:
        """只保留可由 search unit 后端落地的元数据表达式。"""

        if not isinstance(expression, Mapping) or not expression:
            return {}

        def _node(node: Mapping[str, Any]) -> dict[str, Any]:
            op = str(node.get("op") or "").strip().lower()
            if op in {"and", "or"}:
                items = [
                    item
                    for item in (_node(raw_item) for raw_item in list(node.get("items") or []) if isinstance(raw_item, Mapping))
                    if item
                ]
                if not items:
                    return {}
                return items[0] if len(items) == 1 else {"op": op, "items": items}
            if op == "not":
                items = [
                    item
                    for item in (_node(raw_item) for raw_item in list(node.get("items") or [])[:1] if isinstance(raw_item, Mapping))
                    if item
                ]
                return {"op": "not", "items": items} if items else {}
            field = str(node.get("field") or "").strip()
            return dict(node) if field in {"metadata", "search_unit_metadata"} else {}

        return _node(expression)

    def _build_document_filter_expression_condition(self, expression: Mapping[str, Any] | None) -> Any | None:
        """把文档级表达式树转换为 SQLAlchemy 条件。"""

        if not isinstance(expression, Mapping) or not expression:
            return None

        op = str(expression.get("op") or "").strip().lower()
        if op in {"and", "or"}:
            parts = [
                part
                for part in (
                    self._build_document_filter_expression_condition(item)
                    for item in list(expression.get("items") or [])
                    if isinstance(item, Mapping)
                )
                if part is not None
            ]
            if not parts:
                return None
            return and_(*parts) if op == "and" else or_(*parts)
        if op == "not":
            items = [item for item in list(expression.get("items") or [])[:1] if isinstance(item, Mapping)]
            if not items:
                return None
            child = self._build_document_filter_expression_condition(items[0])
            return ~child if child is not None else None

        field = str(expression.get("field") or "").strip()
        compare_op = op if op else "in"
        values = list(expression.get("values") or [])
        if field in {"kb_doc", "kb_doc_id"}:
            return self._build_uuid_column_condition(KnowledgeBaseDocument.id, compare_op, values)
        if field in {"document", "document_id"}:
            return self._build_uuid_column_condition(KnowledgeBaseDocument.document_id, compare_op, values)
        if field in {"folder", "folder_id"}:
            return self._build_uuid_column_condition(KnowledgeBaseDocument.folder_id, compare_op, values)
        if field in {"tag", "doc_tag", "tag_id"}:
            tag_ids = _coerce_uuid_list(values)
            tag_subq = select(ResourceTag.target_id).where(
                ResourceTag.tenant_id == KnowledgeBaseDocument.tenant_id,
                ResourceTag.kb_id == KnowledgeBaseDocument.kb_id,
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.action == "add",
                ResourceTag.tag_id.in_(tag_ids),
            )
            if compare_op in {"not_in", "ne"}:
                return ~KnowledgeBaseDocument.id.in_(tag_subq) if tag_ids else true()
            return KnowledgeBaseDocument.id.in_(tag_subq) if tag_ids else false()
        if field in {"metadata", "document_metadata"}:
            return self._build_document_metadata_expression_condition(expression)
        # search_unit_metadata 交给召回后端处理；文档候选层忽略。
        return None

    def _build_uuid_column_condition(self, column: Any, operator: str, values: Sequence[Any]) -> Any:
        """构建 UUID 列表达式条件。"""

        ids = _coerce_uuid_list(values)
        if operator in {"exists", "not_exists"}:
            return column.is_not(None) if operator == "exists" else column.is_(None)
        if operator in {"not_in", "ne"}:
            return ~column.in_(ids) if ids else true()
        return column.in_(ids) if ids else false()

    def _build_document_metadata_expression_condition(self, expression: Mapping[str, Any]) -> Any:
        """构建文档级 metadata 表达式条件。"""

        path = [str(item).strip() for item in list(expression.get("path") or []) if str(item).strip()]
        if not path:
            return false()
        operator = str(expression.get("op") or "in").strip().lower()
        values = [
            serialize_filter_value(item)
            for item in list(expression.get("values") or [])
            if item is not None and str(item).strip()
        ]
        kb_doc_value = self._json_text_path(KnowledgeBaseDocument.custom_metadata, path)
        doc_value = self._json_text_path(Document.metadata_info, path)
        if operator == "exists":
            return or_(kb_doc_value.is_not(None), doc_value.is_not(None))
        if operator == "not_exists":
            return and_(kb_doc_value.is_(None), doc_value.is_(None))
        if operator in {"eq", "in"}:
            return or_(kb_doc_value.in_(values), doc_value.in_(values)) if values else false()
        if operator in {"ne", "not_in"}:
            if not values:
                return true()
            return and_(
                or_(kb_doc_value.is_(None), ~kb_doc_value.in_(values)),
                or_(doc_value.is_(None), ~doc_value.in_(values)),
            )
        return false()

    def _json_text_path(self, column: Any, path: Sequence[str]) -> Any:
        """按路径读取 JSONB 文本值。"""

        expr = column
        for part in path:
            expr = expr[str(part)]
        return expr.astext

    async def _resolve_qa_content_group_ids(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        filters: RetrievalFilterSet,
        kb_doc_ids: list[UUID],
    ) -> list[UUID]:
        """先在 QA 主事实表中过滤，再映射为 content_group_id 约束检索层。"""

        qa_fields = dict((filters.search_unit_metadata or {}).get("qa_fields") or {})
        if not qa_fields:
            return []

        stmt: Select[Any] = select(KBQARow.id).where(
            KBQARow.tenant_id == current_user.tenant_id,
            KBQARow.kb_id == kb.id,
            KBQARow.is_enabled.is_(True),
        )
        if kb_doc_ids:
            stmt = stmt.where(KBQARow.kb_doc_id.in_(kb_doc_ids))

        category_value = str(qa_fields.get("category") or "").strip()
        if category_value:
            stmt = stmt.where(KBQARow.category == category_value)

        tag_value = str(qa_fields.get("tag") or "").strip()
        if tag_value:
            stmt = stmt.where(KBQARow.tags.contains([tag_value]))

        rows = (await self.session.execute(stmt)).all()
        return [row[0] for row in rows if row and row[0] is not None]

    async def _resolve_table_content_group_ids(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        filters: RetrievalFilterSet,
        kb_doc_ids: list[UUID],
    ) -> list[UUID]:
        """先在表格主事实表中过滤，再映射为 content_group_id 供检索层复用。"""

        filter_fields = dict((filters.search_unit_metadata or {}).get("filter_fields") or {})
        if not filter_fields:
            return []

        stmt: Select[Any] = select(KBTableRow.id).where(
            KBTableRow.tenant_id == current_user.tenant_id,
            KBTableRow.kb_id == kb.id,
            KBTableRow.is_deleted.is_(False),
        )
        if kb_doc_ids:
            stmt = stmt.where(KBTableRow.kb_doc_id.in_(kb_doc_ids))

        for key, value in filter_fields.items():
            serialized = self._serialize_metadata_filter_value(value)
            stmt = stmt.where(KBTableRow.row_data[str(key)].astext == serialized)

        rows = (await self.session.execute(stmt)).all()
        return [row[0] for row in rows if row and row[0] is not None]

    async def _expand_folder_ids(
        self,
        *,
        kb: KnowledgeBase,
        folder_ids: Iterable[UUID],
        include_descendants: bool,
    ) -> list[UUID]:
        """把目录树过滤扩展为最终 folder_id 集合。"""

        normalized_ids = list(dict.fromkeys(folder_ids))
        if not normalized_ids:
            return []
        if not include_descendants:
            return normalized_ids

        stmt = select(Folder.id, Folder.path).where(
            Folder.kb_id == kb.id,
            Folder.tenant_id == kb.tenant_id,
        )
        rows = (await self.session.execute(stmt)).all()
        path_map = {folder_id: str(path or "") for folder_id, path in rows}
        expanded_ids: set[UUID] = set(normalized_ids)
        selected_paths = [path_map.get(folder_id, "") for folder_id in normalized_ids]
        for folder_id, path in path_map.items():
            if not path:
                continue
            for selected_path in selected_paths:
                if not selected_path:
                    continue
                if path == selected_path or path.startswith(f"{selected_path}."):
                    expanded_ids.add(folder_id)
                    break
        return list(expanded_ids)

    async def _resolve_folder_ids_by_tags(
        self,
        *,
        kb: KnowledgeBase,
        folder_ids: list[UUID],
        folder_tag_ids: list[UUID],
    ) -> list[UUID]:
        """把文件夹标签过滤先解析成目录集合。"""

        if not folder_tag_ids:
            return folder_ids

        unique_tag_ids = list(dict.fromkeys(folder_tag_ids))
        stmt = (
            select(ResourceTag.target_id)
            .where(
                ResourceTag.tenant_id == kb.tenant_id,
                ResourceTag.kb_id == kb.id,
                ResourceTag.target_type == "folder",
                ResourceTag.action == "add",
                ResourceTag.tag_id.in_(unique_tag_ids),
            )
            .group_by(ResourceTag.target_id)
            .having(func.count(func.distinct(ResourceTag.tag_id)) >= len(unique_tag_ids))
        )
        tagged_folder_ids = [row[0] for row in (await self.session.execute(stmt)).all()]
        if folder_ids:
            folder_id_set = set(folder_ids)
            return [folder_id for folder_id in tagged_folder_ids if folder_id in folder_id_set]
        return tagged_folder_ids

    async def _embed_query(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        query: str,
    ) -> tuple[list[float], int]:
        """使用知识库当前生效的 embedding 模型向量化查询。"""

        resolved_model = await resolve_kb_runtime_model(
            self.session,
            kb=kb,
            capability_type="embedding",
        )
        model_snapshot = await self._resolve_query_embedding_model_snapshot(
            tenant_model_id=resolved_model.tenant_model_id,
        )
        redis = await get_redis()
        normalized_query = str(query or "").strip()
        cache_key = self._build_query_embed_cache_key(
            tenant_model_id=model_snapshot.tenant_model_id,
            cache_signature=model_snapshot.cache_signature,
            query=normalized_query,
        )
        should_use_cache = self._should_use_query_embed_cache(normalized_query, redis=redis)
        if should_use_cache:
            cached_embedding = await self._load_cached_query_embedding(
                redis=redis,
                cache_key=cache_key,
                expected_signature=model_snapshot.cache_signature,
            )
            if cached_embedding:
                return cached_embedding, len(cached_embedding)

        lock_key = self._build_query_embed_lock_key(cache_key)
        lock_token: str | None = None
        if should_use_cache:
            lock_token = await self._acquire_query_embed_lock(redis=redis, lock_key=lock_key)
            if lock_token is None:
                waited_embedding = await self._wait_for_cached_query_embedding(
                    redis=redis,
                    cache_key=cache_key,
                    expected_signature=model_snapshot.cache_signature,
                )
                if waited_embedding:
                    return waited_embedding, len(waited_embedding)

        try:
            response = await self.model_invocation_service.embed(
                current_user=current_user,
                tenant_model_id=resolved_model.tenant_model_id,
                capability_type="embedding",
                input_texts=[normalized_query],
                request_source="kb_retrieval",
            )
        finally:
            if lock_token is not None:
                await self._release_query_embed_lock(redis=redis, lock_key=lock_key, token=lock_token)

        data_items = list(response.get("data") or [])
        if not data_items:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="查询向量化失败")
        embedding = list(data_items[0].get("embedding") or [])
        if not embedding:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="查询向量为空")
        normalized_embedding = [float(value) for value in embedding]
        if should_use_cache:
            await self._cache_query_embedding(
                redis=redis,
                cache_key=cache_key,
                embedding=normalized_embedding,
                tenant_model_id=model_snapshot.tenant_model_id,
                cache_signature=model_snapshot.cache_signature,
            )
        return normalized_embedding, len(normalized_embedding)

    async def _resolve_query_embedding_model_snapshot(self, *, tenant_model_id: UUID) -> QueryEmbeddingModelSnapshot:
        """解析查询向量化模型快照，用于缓存失效控制。"""

        stmt = (
            select(TenantModel, PlatformModel, TenantModelProvider)
            .join(PlatformModel, PlatformModel.id == TenantModel.platform_model_id)
            .join(TenantModelProvider, TenantModelProvider.id == TenantModel.tenant_provider_id)
            .where(TenantModel.id == tenant_model_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到查询向量化模型")
        tenant_model, platform_model, tenant_provider = row
        payload = {
            "raw_model_name": str(platform_model.raw_model_name or "").strip(),
            "provider_base_url": str(tenant_provider.base_url or "").strip(),
            "provider_api_version": str(tenant_provider.api_version or "").strip(),
            "provider_region": str(tenant_provider.region or "").strip(),
            "provider_adapter_override_type": str(tenant_provider.adapter_override_type or "").strip(),
            "provider_request_defaults": tenant_provider.request_defaults or {},
            "embedding_capability_base_url": str((tenant_provider.capability_base_urls or {}).get("embedding") or "").strip(),
            "embedding_capability_override": dict((tenant_provider.capability_overrides or {}).get("embedding") or {}),
            "tenant_model_adapter_override_type": str(tenant_model.adapter_override_type or "").strip(),
            "tenant_model_implementation_key_override": str(tenant_model.implementation_key_override or "").strip(),
            "tenant_model_request_schema_override": str(tenant_model.request_schema_override or "").strip(),
            "tenant_model_endpoint_path_override": str(tenant_model.endpoint_path_override or "").strip(),
            "tenant_model_request_defaults": tenant_model.request_defaults or {},
            "tenant_model_runtime_config": tenant_model.model_runtime_config or {},
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return QueryEmbeddingModelSnapshot(
            tenant_model_id=tenant_model_id,
            raw_model_name=str(platform_model.raw_model_name or "").strip(),
            cache_signature=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        )

    def _build_query_embed_cache_key(self, *, tenant_model_id: UUID, cache_signature: str, query: str) -> str:
        """构造查询向量缓存键。"""

        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
        return f"{QUERY_EMBED_CACHE_NAMESPACE}:{QUERY_EMBED_CACHE_VERSION}:{tenant_model_id}:{cache_signature}:{digest}"

    def _build_query_embed_lock_key(self, cache_key: str) -> str:
        """为查询向量缓存构造单飞锁键。"""

        return f"{QUERY_EMBED_CACHE_LOCK_NAMESPACE}:{hashlib.sha256(cache_key.encode('utf-8')).hexdigest()}"

    def _should_use_query_embed_cache(self, query: str, *, redis: Redis | None) -> bool:
        """判断当前查询是否启用查询向量缓存。"""

        return redis is not None and settings.RAG_EMBED_CACHE_ENABLED and 0 < len(query) <= settings.RAG_EMBED_CACHE_MAX_TEXT_LENGTH

    async def _load_cached_query_embedding(
        self,
        *,
        redis: Redis,
        cache_key: str,
        expected_signature: str,
    ) -> list[float] | None:
        """读取已缓存的查询向量。"""

        cached = await redis.get(cache_key)
        if not cached:
            return None
        payload = json.loads(cached)
        cached_signature = str(payload.get("cache_signature") or "").strip()
        if cached_signature and cached_signature != expected_signature:
            return None
        embedding = [float(item) for item in list(payload.get("embedding") or [])]
        return embedding or None

    async def _cache_query_embedding(
        self,
        *,
        redis: Redis,
        cache_key: str,
        embedding: list[float],
        tenant_model_id: UUID,
        cache_signature: str,
    ) -> None:
        """写入查询向量热缓存。"""

        payload = json.dumps(
            {
                "embedding": embedding,
                "tenant_model_id": str(tenant_model_id),
                "cache_signature": cache_signature,
                "cached_at": int(time.time()),
            },
            ensure_ascii=False,
        )
        ttl_seconds = max(60, settings.RAG_EMBED_CACHE_TTL_SECONDS)
        now = time.time()
        async with redis.pipeline(transaction=True) as pipe:
            await pipe.setex(cache_key, ttl_seconds, payload)
            await pipe.zadd(QUERY_EMBED_CACHE_INDEX_KEY, {cache_key: now})
            await pipe.expire(QUERY_EMBED_CACHE_INDEX_KEY, ttl_seconds)
            await pipe.execute()
        await self._trim_query_embed_cache_if_needed(redis=redis)

    async def _trim_query_embed_cache_if_needed(self, *, redis: Redis) -> None:
        """控制查询向量缓存数量，避免无限增长。"""

        max_items = max(100, settings.RAG_EMBED_CACHE_MAX_ITEMS)
        current_size = await redis.zcard(QUERY_EMBED_CACHE_INDEX_KEY)
        overflow = current_size - max_items
        if overflow <= 0:
            return
        stale_keys = await redis.zrange(QUERY_EMBED_CACHE_INDEX_KEY, 0, overflow - 1)
        if not stale_keys:
            return
        async with redis.pipeline(transaction=True) as pipe:
            await pipe.delete(*stale_keys)
            await pipe.zrem(QUERY_EMBED_CACHE_INDEX_KEY, *stale_keys)
            await pipe.execute()

    async def _acquire_query_embed_lock(self, *, redis: Redis, lock_key: str) -> str | None:
        """尝试获取查询向量单飞锁。"""

        token = hashlib.sha256(f"{lock_key}:{time.time()}".encode("utf-8")).hexdigest()
        acquired = await redis.set(lock_key, token, ex=QUERY_EMBED_CACHE_LOCK_TTL_SECONDS, nx=True)
        return token if acquired else None

    async def _release_query_embed_lock(self, *, redis: Redis, lock_key: str, token: str) -> None:
        """只释放当前请求持有的查询向量单飞锁。"""

        current_value = await redis.get(lock_key)
        if current_value is None:
            return
        normalized_value = current_value.decode("utf-8") if isinstance(current_value, bytes) else str(current_value)
        if normalized_value == token:
            await redis.delete(lock_key)

    async def _wait_for_cached_query_embedding(
        self,
        *,
        redis: Redis,
        cache_key: str,
        expected_signature: str,
    ) -> list[float] | None:
        """等待并复用其他并发请求写入的查询向量缓存。"""

        deadline = time.perf_counter() + QUERY_EMBED_CACHE_LOCK_WAIT_SECONDS
        while time.perf_counter() < deadline:
            await asyncio.sleep(QUERY_EMBED_CACHE_LOCK_POLL_SECONDS)
            embedding = await self._load_cached_query_embedding(
                redis=redis,
                cache_key=cache_key,
                expected_signature=expected_signature,
            )
            if embedding:
                return embedding
        return None

    async def _search_doc_summary_hits(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        query: str,
        resolved_filters: ResolvedCandidateFilter,
        top_k: int,
    ) -> list[SearchHit]:
        """基于 kb_doc.summary 进行轻量辅助召回。"""

        normalized_query = " ".join(str(query or "").split()).strip()
        if not normalized_query or top_k <= 0:
            return []

        stmt = (
            select(KnowledgeBaseDocument, Document)
            .join(
                Document,
                and_(
                    Document.id == KnowledgeBaseDocument.document_id,
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted.is_(False),
                ),
            )
            .where(
                KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
                KnowledgeBaseDocument.kb_id == kb.id,
                KnowledgeBaseDocument.parse_status == "completed",
                KnowledgeBaseDocument.is_enabled.is_(True),
                KnowledgeBaseDocument.summary.is_not(None),
                KnowledgeBaseDocument.summary != "",
            )
        )
        if resolved_filters.filter_applied:
            if not resolved_filters.kb_doc_ids:
                return []
            stmt = stmt.where(KnowledgeBaseDocument.id.in_(resolved_filters.kb_doc_ids))

        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return []

        query_bigrams = self._build_bigrams(normalized_query)
        query_terms = self._tokenize_terms(normalized_query)
        hits: list[SearchHit] = []
        for kb_doc, document in rows:
            summary_text = prepare_doc_summary_text(
                kb_doc.summary,
                retrieval_config=kb.retrieval_config or {},
            )
            if not summary_text:
                continue
            title_text = str(kb_doc.display_name or document.name or "").strip()
            score = self._compute_doc_summary_score(
                query_bigrams=query_bigrams,
                query_terms=query_terms,
                summary_text=summary_text,
                title_text=title_text,
            )
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    search_unit_id=0,
                    chunk_id=0,
                    kb_id=kb.id,
                    kb_doc_id=kb_doc.id,
                    document_id=kb_doc.document_id,
                    content_group_id=None,
                    search_scope="doc_summary",
                    score=round(score, 4),
                    backend_type="doc_summary",
                    metadata={
                        "summary_text": summary_text,
                        "document_name": title_text,
                        "projection_type": "kb_doc_summary",
                    },
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    def _fuse_hits(
        self,
        *,
        config: HybridSearchConfig,
        kb: KnowledgeBase,
        query: str,
        raw_query: str | None = None,
        vector_hits: list[SearchHit],
        lexical_hits: list[SearchHit],
        scope_weights: Mapping[str, float] | None = None,
        auto_tag_boosts: Mapping[UUID, dict[str, Any]] | None = None,
    ) -> list[GroupedHit]:
        """融合双路召回结果，并按业务聚合键归并。"""

        grouped: dict[str, GroupedHit] = {}
        lexical_weight = max(0.0, 1.0 - config.vector_weight)
        query_characteristics = self._analyze_query_characteristics(query)

        def _apply(hit: SearchHit, *, backend_name: str) -> None:
            if backend_name == "lexical":
                hit = self._normalize_qa_lexical_hit_score(
                    kb=kb,
                    query=query,
                    raw_query=raw_query,
                    hit=hit,
                )
            threshold = (
                config.vector_similarity_threshold
                if backend_name == "vector"
                else config.keyword_relevance_threshold
            )
            if hit.score < threshold:
                return

            group_key = self._resolve_hit_group_key(
                kb=kb,
                config=config,
                hit=hit,
            )
            entry = grouped.get(group_key)
            if entry is None:
                entry = GroupedHit(
                    group_key=group_key,
                    anchor_chunk_id=hit.chunk_id,
                    kb_doc_id=hit.kb_doc_id,
                    document_id=hit.document_id,
                    content_group_id=hit.content_group_id,
                )
                grouped[group_key] = entry

            entry.hits.append(hit)
            entry.matched_scopes.add(hit.search_scope)
            entry.matched_backend_types.add(backend_name)

            if backend_name == "vector":
                entry.vector_score = max(entry.vector_score or 0.0, hit.score)
            else:
                entry.keyword_score = max(entry.keyword_score or 0.0, hit.score)

            current_scope_weight = dict(scope_weights or SEARCH_SCOPE_WEIGHTS).get(hit.search_scope, 0.82)
            repeated_hit_bonus = self._compute_repeated_hit_bonus(hit=hit, grouped=entry)
            query_intent_bonus = self._compute_query_intent_bonus(
                kb=kb,
                hit=hit,
                query_characteristics=query_characteristics,
            )
            metadata_bonus = self._compute_metadata_bonus(
                kb=kb,
                hit=hit,
                query_characteristics=query_characteristics,
            )
            auto_tag_payload = dict(auto_tag_boosts or {}).get(hit.kb_doc_id, {})
            auto_tag_boost = float(dict(auto_tag_payload).get("boost") or 0.0)
            current_final = self._compute_group_score(
                vector_score=entry.vector_score,
                keyword_score=entry.keyword_score,
                vector_weight=config.vector_weight,
                lexical_weight=lexical_weight,
                scope_weight=current_scope_weight,
                scope_count=len(entry.matched_scopes),
                backend_count=len(entry.matched_backend_types),
                repeated_hit_bonus=repeated_hit_bonus + query_intent_bonus + metadata_bonus,
                auto_tag_boost=auto_tag_boost,
            )
            if current_final >= entry.final_score:
                entry.final_score = current_final
                entry.anchor_chunk_id = hit.chunk_id
                entry.scope_weight = current_scope_weight
                entry.repeated_hit_bonus = repeated_hit_bonus
                entry.query_intent_bonus = query_intent_bonus
                entry.metadata_bonus = metadata_bonus
                entry.auto_tag_boost = self._compute_effective_auto_tag_boost(
                    vector_score=entry.vector_score,
                    keyword_score=entry.keyword_score,
                    vector_weight=config.vector_weight,
                    lexical_weight=lexical_weight,
                    scope_weight=current_scope_weight,
                    auto_tag_boost=auto_tag_boost,
                )
                entry.auto_tag_boost_debug = dict(auto_tag_payload)

        for hit in vector_hits:
            _apply(hit, backend_name="vector")
        for hit in lexical_hits:
            _apply(hit, backend_name="lexical")

        ordered = sorted(grouped.values(), key=lambda item: item.final_score, reverse=True)
        if config.rerank_top_n > 0:
            ordered = ordered[: config.rerank_top_n]
        ordered = [item for item in ordered if item.final_score >= config.final_score_threshold]
        return ordered

    def _normalize_qa_lexical_hit_score(
        self,
        *,
        kb: KnowledgeBase,
        query: str,
        raw_query: str | None,
        hit: SearchHit,
    ) -> SearchHit:
        """对 QA 问句命中的全文分做结构化归一化，提升完全同问的稳定性。"""

        if str(kb.type or "").strip() != "qa" or str(hit.search_scope or "").strip() != "question":
            return hit

        metadata = dict(hit.metadata or {})
        question_text = str(metadata.get("question_text") or "").strip()
        if not question_text:
            return hit

        normalized_question = normalize_lexical_text(question_text)
        if not normalized_question:
            return hit

        structured_score = 0.0
        debug_candidates: list[dict[str, float | str]] = []
        candidate_queries = [
            ("raw_query", str(raw_query or "").strip()),
            ("rewritten_query", str(query or "").strip()),
        ]
        for candidate_name, candidate_query in candidate_queries:
            normalized_query = normalize_lexical_text(candidate_query)
            if not normalized_query:
                continue

            exact_match_score = 1.0 if normalized_query == normalized_question else 0.0
            containment_score = 1.0 if (
                normalized_query in normalized_question or normalized_question in normalized_query
            ) else 0.0
            bigram_score = self._compute_bigram_overlap(
                self._build_bigrams(normalized_query),
                self._build_bigrams(normalized_question),
            )
            query_terms = [
                *extract_ascii_terms(normalized_query),
                *extract_cjk_terms(normalized_query),
            ]
            question_terms = set([
                *extract_ascii_terms(normalized_question),
                *extract_cjk_terms(normalized_question),
            ])
            term_overlap = 0.0
            if query_terms:
                hit_count = sum(1 for term in query_terms if term in question_terms)
                term_overlap = hit_count / max(1, len(query_terms))

            candidate_score = min(
                1.0,
                (exact_match_score * 0.45)
                + (containment_score * 0.2)
                + (bigram_score * 0.25)
                + (term_overlap * 0.1),
            )
            debug_candidates.append(
                {
                    "query_source": candidate_name,
                    "normalized_query": normalized_query,
                    "score": round(candidate_score, 4),
                }
            )
            structured_score = max(structured_score, candidate_score)

        adjusted_score = max(float(hit.score or 0.0), min(1.0, structured_score))
        if adjusted_score <= float(hit.score or 0.0):
            return hit

        metadata["lexical_raw_score"] = round(float(hit.score or 0.0), 4)
        metadata["lexical_structured_score"] = round(structured_score, 4)
        metadata["lexical_structured_candidates"] = debug_candidates
        return SearchHit(
            search_unit_id=hit.search_unit_id,
            chunk_id=hit.chunk_id,
            kb_id=hit.kb_id,
            kb_doc_id=hit.kb_doc_id,
            document_id=hit.document_id,
            content_group_id=hit.content_group_id,
            search_scope=hit.search_scope,
            score=round(adjusted_score, 4),
            backend_type=hit.backend_type,
            metadata=metadata,
        )

    def _compute_group_score(
        self,
        *,
        vector_score: Optional[float],
        keyword_score: Optional[float],
        vector_weight: float,
        lexical_weight: float,
        scope_weight: float,
        scope_count: int,
        backend_count: int,
        repeated_hit_bonus: float = 0.0,
        auto_tag_boost: float = 0.0,
    ) -> float:
        """计算融合后的最终分数。"""

        vector_component = max(0.0, float(vector_score or 0.0))
        keyword_component = max(0.0, float(keyword_score or 0.0))
        weighted = (vector_component * vector_weight) + (keyword_component * lexical_weight)
        coverage_bonus = min(0.12, max(0, scope_count - 1) * 0.03)
        backend_bonus = 0.05 if backend_count >= 2 else 0.0
        effective_auto_tag_boost = self._compute_effective_auto_tag_boost(
            vector_score=vector_score,
            keyword_score=keyword_score,
            vector_weight=vector_weight,
            lexical_weight=lexical_weight,
            scope_weight=scope_weight,
            auto_tag_boost=auto_tag_boost,
        )
        bonus_total = min(0.20, coverage_bonus + backend_bonus + repeated_hit_bonus + effective_auto_tag_boost)
        return min(1.0, (weighted * scope_weight) + bonus_total)

    def _compute_effective_auto_tag_boost(
        self,
        *,
        vector_score: Optional[float],
        keyword_score: Optional[float],
        vector_weight: float,
        lexical_weight: float,
        scope_weight: float,
        auto_tag_boost: float,
    ) -> float:
        """按语义地板折算自动标签加分，避免弱语义结果被标签救活。"""

        normalized_boost = max(0.0, min(0.10, float(auto_tag_boost or 0.0)))
        if normalized_boost <= 0:
            return 0.0
        vector_component = max(0.0, float(vector_score or 0.0))
        keyword_component = max(0.0, float(keyword_score or 0.0))
        semantic_score = ((vector_component * vector_weight) + (keyword_component * lexical_weight)) * scope_weight
        if semantic_score < 0.20:
            return 0.0
        if semantic_score < 0.35:
            return round(normalized_boost * 0.5, 4)
        return round(normalized_boost, 4)

    def _resolve_display_chunk_for_group(
        self,
        *,
        kb: KnowledgeBase,
        config: HybridSearchConfig,
        grouped_hit: GroupedHit,
        anchor_chunk: Chunk,
        parent_chunk: Optional[Chunk],
    ) -> tuple[Chunk, Optional[Chunk], bool]:
        """为当前结果决定最终展示块与其上下文块。"""

        anchor_metadata = dict(anchor_chunk.metadata_info or {})
        force_complete_unit = self._requires_complete_unit_from_metadata(
            kb=kb,
            metadata=anchor_metadata,
            search_scope=next((hit.search_scope for hit in grouped_hit.hits if hit.chunk_id == anchor_chunk.id), None),
        )
        if force_complete_unit and parent_chunk is not None:
            return parent_chunk, None, True
        if config.hierarchical_retrieval_mode == "auto_merge" and parent_chunk is not None and self._is_general_hierarchical_leaf(anchor_metadata):
            return parent_chunk, None, True
        if config.hierarchical_retrieval_mode == "leaf_only":
            return anchor_chunk, None, False
        if config.hierarchical_retrieval_mode == "recursive":
            return anchor_chunk, parent_chunk, False
        return anchor_chunk, parent_chunk, False

    async def _load_neighbor_chunks(
        self,
        *,
        chunk: Chunk,
        window_size: int,
    ) -> tuple[list[Chunk], list[Chunk]]:
        """按命中叶子块位置加载相邻块，增强局部连续上下文。"""

        if window_size <= 0:
            return [], []

        metadata = dict(chunk.metadata_info or {})
        if bool(metadata.get("is_hierarchical")) and chunk.parent_id:
            parent_filter = Chunk.parent_id == chunk.parent_id
        elif bool(metadata.get("is_hierarchical")):
            parent_filter = Chunk.parent_id.is_(None)
        else:
            parent_filter = True  # type: ignore[assignment]

        base_filters = [
            Chunk.kb_doc_id == chunk.kb_doc_id,
            Chunk.is_active.is_(True),
            Chunk.display_enabled.is_(True),
            Chunk.id != chunk.id,
        ]
        if parent_filter is not True:  # type: ignore[comparison-overlap]
            base_filters.append(parent_filter)

        previous_stmt = (
            select(Chunk)
            .where(
                *base_filters,
                Chunk.position < chunk.position,
            )
            .order_by(Chunk.position.desc(), Chunk.id.desc())
            .limit(window_size)
        )
        next_stmt = (
            select(Chunk)
            .where(
                *base_filters,
                Chunk.position > chunk.position,
            )
            .order_by(Chunk.position.asc(), Chunk.id.asc())
            .limit(window_size)
        )
        previous_chunks = list((await self.session.execute(previous_stmt)).scalars().all())
        next_chunks = list((await self.session.execute(next_stmt)).scalars().all())
        previous_chunks.reverse()
        return previous_chunks, next_chunks

    async def _hydrate_results(
        self,
        *,
        kb: KnowledgeBase,
        config: HybridSearchConfig,
        grouped_hits: list[GroupedHit],
    ) -> list[dict[str, Any]]:
        """把聚合后的命中补全为可直接返回前端的结果。"""

        if not grouped_hits:
            return []

        anchor_chunk_ids = [item.anchor_chunk_id for item in grouped_hits]
        chunk_stmt = select(Chunk).where(Chunk.id.in_(anchor_chunk_ids))
        chunks = (await self.session.execute(chunk_stmt)).scalars().all()
        chunk_map = {int(chunk.id): chunk for chunk in chunks if chunk.id is not None}

        parent_ids = [chunk.parent_id for chunk in chunks if chunk.parent_id]
        parent_map: dict[int, Chunk] = {}
        if parent_ids:
            parent_stmt = select(Chunk).where(Chunk.id.in_(list(dict.fromkeys(parent_ids))))
            parents = (await self.session.execute(parent_stmt)).scalars().all()
            parent_map = {int(chunk.id): chunk for chunk in parents if chunk.id is not None}

        kb_doc_ids = [item.kb_doc_id for item in grouped_hits]
        kb_doc_stmt = (
            select(KnowledgeBaseDocument, Document)
            .join(Document, Document.id == KnowledgeBaseDocument.document_id)
            .where(KnowledgeBaseDocument.id.in_(kb_doc_ids))
        )
        kb_doc_rows = (await self.session.execute(kb_doc_stmt)).all()
        kb_doc_map = {
            row[0].id: {"kb_doc": row[0], "document": row[1]}
            for row in kb_doc_rows
        }

        tag_map = await self._load_kb_doc_tags(kb=kb, kb_doc_ids=kb_doc_ids)
        items: list[dict[str, Any]] = []
        for index, grouped in enumerate(grouped_hits, start=1):
            chunk = chunk_map.get(grouped.anchor_chunk_id)
            kb_doc_bundle = kb_doc_map.get(grouped.kb_doc_id)
            if kb_doc_bundle is None:
                continue

            kb_doc = kb_doc_bundle["kb_doc"]
            document = kb_doc_bundle["document"]
            parent_chunk = parent_map.get(int(chunk.parent_id)) if chunk and chunk.parent_id else None
            group_metadata = self._collect_group_debug_metadata(grouped.hits)
            if chunk is None and "doc_summary" in grouped.matched_scopes:
                doc_summary_hit = next((hit for hit in grouped.hits if hit.search_scope == "doc_summary"), None)
                llm_context_content = str((doc_summary_hit.metadata if doc_summary_hit is not None else {}).get("summary_text") or kb_doc.summary or "").strip()
                snippet = self._truncate_text(llm_context_content, config.max_snippet_length)
                page_numbers: list[int] = []
                chunk_id_value: str | None = None
                display_chunk: Chunk | None = None
                effective_parent_chunk: Chunk | None = None
                result_unit_kind = "doc_summary"
            else:
                if chunk is None:
                    continue
                display_chunk, effective_parent_chunk, force_complete_unit = self._resolve_display_chunk_for_group(
                    kb=kb,
                    config=config,
                    grouped_hit=grouped,
                    anchor_chunk=chunk,
                    parent_chunk=parent_chunk,
                )
                result_unit_kind = "leaf"
                if force_complete_unit:
                    result_unit_kind = "complete_unit"
                elif display_chunk.id != chunk.id:
                    result_unit_kind = "promoted_parent"
                previous_neighbors: list[Chunk] = []
                next_neighbors: list[Chunk] = []
                if not force_complete_unit and config.hierarchical_retrieval_mode in {"leaf_only", "recursive"}:
                    previous_neighbors, next_neighbors = await self._load_neighbor_chunks(
                        chunk=chunk,
                        window_size=config.neighbor_window_size,
                    )
                llm_context_content = self._build_result_context_text(
                    chunk=display_chunk,
                    parent_chunk=effective_parent_chunk,
                    enable_parent_context=config.enable_parent_context and config.hierarchical_retrieval_mode == "recursive",
                    previous_neighbors=previous_neighbors,
                    next_neighbors=next_neighbors,
                )
                row_group_hit = next((hit for hit in grouped.hits if hit.search_scope == "row_group"), None)
                row_group_context = str((row_group_hit.metadata or {}).get("table_context_text") or "").strip() if row_group_hit else ""
                row_metric_explanation = str((row_group_hit.metadata or {}).get("metric_explanation_text") or "").strip() if row_group_hit else ""
                if row_group_context and str(kb.type or "").strip() == "table" and not force_complete_unit:
                    contextual_parts = [f"[表格上下文] {row_group_context}"]
                    if row_metric_explanation:
                        contextual_parts.append(f"[指标理解] {row_metric_explanation}")
                    llm_context_content = "\n".join(contextual_parts + [llm_context_content]).strip()
                snippet = self._truncate_text(llm_context_content, config.max_snippet_length)
                page_numbers = list((display_chunk.metadata_info or {}).get("page_numbers") or [])
                chunk_id_value = str(display_chunk.id)
            topology_type = self._resolve_chunk_topology_type(display_chunk)
            full_result_content = self._resolve_full_result_content(
                display_chunk=display_chunk,
                kb_doc=kb_doc,
                grouped_hit=grouped,
            )
            context_unit_content = str(display_chunk.content or "").strip() if display_chunk is not None else full_result_content
            raw_hit_chunk_view = self._build_chunk_debug_view(
                chunk=chunk,
                fallback_label="原始命中块",
                extra={
                    "matched_scopes": sorted(grouped.matched_scopes),
                    "matched_backend_types": sorted(grouped.matched_backend_types),
                },
            )
            context_unit_view = self._build_chunk_debug_view(
                chunk=display_chunk,
                fallback_content=context_unit_content,
                fallback_label="最终上下文块",
                extra={
                    "result_unit_kind": result_unit_kind,
                    "content_group_id": str(grouped.content_group_id) if grouped.content_group_id else None,
                    "hierarchical_retrieval_mode": config.hierarchical_retrieval_mode,
                },
            )
            llm_context_view = {
                "label": "传给 LLM 的最终上下文",
                "content": str(llm_context_content or "").strip(),
                "source_chunk_id": context_unit_view.get("chunk_id"),
                "assembly_strategy": result_unit_kind if result_unit_kind != "leaf" else "direct_chunk",
                "includes_parent": bool(effective_parent_chunk is not None and config.hierarchical_retrieval_mode == "recursive"),
                "includes_neighbors": bool(previous_neighbors or next_neighbors) if "previous_neighbors" in locals() else False,
                "neighbor_window_size": int(config.neighbor_window_size or 0),
                "token_count": count_tokens(str(llm_context_content or "").strip()),
                "text_length": len(str(llm_context_content or "").strip()),
            }
            include_content_debug = config.debug_trace_level in {"content", "detailed"}

            items.append(
                {
                    "id": grouped.group_key,
                    "rank": index,
                    "title": str(kb_doc.display_name or document.name or "未命名文档"),
                    "content": context_unit_content,
                    "snippet": snippet,
                    "score": round(grouped.final_score, 4),
                    "vector_score": round(grouped.vector_score, 4) if grouped.vector_score is not None else None,
                    "keyword_score": round(grouped.keyword_score, 4) if grouped.keyword_score is not None else None,
                    "tags": tag_map.get(grouped.kb_doc_id, []),
                    "source": {
                        "document_name": str(document.name or kb_doc.display_name or "未命名文档"),
                        "chunk_id": chunk_id_value,
                        "page_numbers": [int(item) for item in page_numbers if isinstance(item, int)],
                    },
                    "metadata": {
                        "matched_scopes": sorted(grouped.matched_scopes),
                        "matched_backends": sorted(grouped.matched_backend_types),
                        "kb_doc_id": str(grouped.kb_doc_id),
                        "document_id": str(grouped.document_id),
                        "kb_id": str(kb.id),
                        "kb_type": str(kb.type or "").strip(),
                        "content_group_id": str(grouped.content_group_id) if grouped.content_group_id else None,
                        "parent_chunk_id": int(effective_parent_chunk.id) if effective_parent_chunk and effective_parent_chunk.id is not None else None,
                        "doc_summary_hit": "doc_summary" in grouped.matched_scopes,
                        "result_unit_kind": result_unit_kind,
                        "chunk_topology_type": topology_type,
                        "full_result_content": full_result_content,
                        "raw_hit_chunk_id": raw_hit_chunk_view.get("chunk_id"),
                        "raw_hit_chunk_content": raw_hit_chunk_view.get("content"),
                        "raw_hit_chunk_token_count": raw_hit_chunk_view.get("token_count"),
                        "context_unit_id": context_unit_view.get("chunk_id"),
                        "context_unit_content": context_unit_view.get("content"),
                        "context_unit_token_count": context_unit_view.get("token_count"),
                        "llm_context_content": llm_context_view.get("content"),
                        "llm_context_token_count": llm_context_view.get("token_count"),
                        "hierarchical_retrieval_mode": config.hierarchical_retrieval_mode,
                        "neighbor_window_size": int(config.neighbor_window_size or 0),
                        "group_by_content_group": bool(config.group_by_content_group),
                        "grouping_strategy": self._resolve_grouping_strategy_label(config),
                        "strategy_contributions": {
                            "scope_weight": round(grouped.scope_weight, 4),
                            "repeated_hit_bonus": round(grouped.repeated_hit_bonus, 4),
                            "query_intent_bonus": round(grouped.query_intent_bonus, 4),
                            "metadata_bonus": round(grouped.metadata_bonus, 4),
                            "auto_tag_boost": round(grouped.auto_tag_boost, 4),
                            "auto_tag_boost_debug": dict(grouped.auto_tag_boost_debug or {}),
                        },
                        "score_trace": {
                            "final_score": round(grouped.final_score, 4),
                            "vector_score": round(grouped.vector_score, 4) if grouped.vector_score is not None else None,
                            "keyword_score": round(grouped.keyword_score, 4) if grouped.keyword_score is not None else None,
                            "scope_weight": round(grouped.scope_weight, 4),
                            "repeated_hit_bonus": round(grouped.repeated_hit_bonus, 4),
                            "query_intent_bonus": round(grouped.query_intent_bonus, 4),
                            "metadata_bonus": round(grouped.metadata_bonus, 4),
                            "auto_tag_boost": round(grouped.auto_tag_boost, 4),
                            "auto_tag_boost_debug": dict(grouped.auto_tag_boost_debug or {}),
                        },
                        "auto_tag_boost_debug": dict(grouped.auto_tag_boost_debug or {}),
                        **group_metadata,
                        **(
                            {
                                "debug": {
                                    "raw_hit_chunk": raw_hit_chunk_view,
                                    "context_unit": context_unit_view,
                                    "llm_context": llm_context_view,
                                },
                            }
                            if include_content_debug else {}
                        ),
                    },
                }
            )
        return items

    def _collect_group_debug_metadata(self, hits: Sequence[SearchHit]) -> dict[str, Any]:
        """汇总同一结果分组里的关键元数据，方便调试解释。"""

        sheet_name = ""
        row_identity_text = ""
        field_names: list[str] = []
        dimension_field_names: list[str] = []
        metric_field_names: list[str] = []
        identifier_field_names: list[str] = []
        filter_fields: dict[str, str] = {}
        table_context_text = ""
        row_explanation_text = ""
        dimension_explanation_text = ""
        metric_explanation_text = ""
        qa_fields: dict[str, Any] = {}
        question_text = ""
        qa_runtime_config: dict[str, Any] = {}
        lexical_raw_score: float | None = None
        lexical_structured_score: float | None = None
        lexical_structured_candidates: list[dict[str, Any]] = []
        hit_score_details: list[dict[str, Any]] = []
        for hit in hits:
            metadata = dict(hit.metadata or {})
            if not sheet_name:
                sheet_name = str(metadata.get("sheet_name") or "").strip()
            if not row_identity_text:
                row_identity_text = str(metadata.get("row_identity_text") or "").strip()
            if not table_context_text:
                table_context_text = str(metadata.get("table_context_text") or "").strip()
            if not row_explanation_text:
                row_explanation_text = str(metadata.get("row_explanation_text") or "").strip()
            if not dimension_explanation_text:
                dimension_explanation_text = str(metadata.get("dimension_explanation_text") or "").strip()
            if not metric_explanation_text:
                metric_explanation_text = str(metadata.get("metric_explanation_text") or "").strip()
            for value in list(metadata.get("field_names") or []):
                normalized = str(value).strip()
                if normalized and normalized not in field_names:
                    field_names.append(normalized)
            for value in list(metadata.get("dimension_field_names") or []):
                normalized = str(value).strip()
                if normalized and normalized not in dimension_field_names:
                    dimension_field_names.append(normalized)
            for value in list(metadata.get("metric_field_names") or []):
                normalized = str(value).strip()
                if normalized and normalized not in metric_field_names:
                    metric_field_names.append(normalized)
            for value in list(metadata.get("identifier_field_names") or []):
                normalized = str(value).strip()
                if normalized and normalized not in identifier_field_names:
                    identifier_field_names.append(normalized)
            for key, value in dict(metadata.get("filter_fields") or {}).items():
                normalized_key = str(key).strip()
                normalized_value = str(value).strip()
                if normalized_key and normalized_value and normalized_key not in filter_fields:
                    filter_fields[normalized_key] = normalized_value
            if not question_text:
                question_text = str(metadata.get("question_text") or "").strip()
            if not qa_fields:
                qa_fields = dict(metadata.get("qa_fields") or {})
            if not qa_runtime_config:
                qa_runtime_config = {
                    "index_mode": str(metadata.get("index_mode_snapshot") or "").strip() or None,
                    "query_weight": float(metadata.get("query_weight_snapshot") or 0.0) if metadata.get("query_weight_snapshot") is not None else None,
                    "answer_weight": float(metadata.get("answer_weight_snapshot") or 0.0) if metadata.get("answer_weight_snapshot") is not None else None,
                    "enable_keyword_recall": bool(metadata.get("enable_keyword_recall_snapshot"))
                    if metadata.get("enable_keyword_recall_snapshot") is not None else None,
                    "enable_category_filter": bool(metadata.get("enable_category_filter_snapshot"))
                    if metadata.get("enable_category_filter_snapshot") is not None else None,
                    "enable_tag_filter": bool(metadata.get("enable_tag_filter_snapshot"))
                    if metadata.get("enable_tag_filter_snapshot") is not None else None,
                }
            if lexical_raw_score is None and metadata.get("lexical_raw_score") is not None:
                lexical_raw_score = float(metadata.get("lexical_raw_score") or 0.0)
            if lexical_structured_score is None and metadata.get("lexical_structured_score") is not None:
                lexical_structured_score = float(metadata.get("lexical_structured_score") or 0.0)
            if not lexical_structured_candidates and metadata.get("lexical_structured_candidates") is not None:
                lexical_structured_candidates = list(metadata.get("lexical_structured_candidates") or [])
            hit_score_details.append(
                {
                    "backend_type": str(hit.backend_type or "").strip(),
                    "search_scope": str(hit.search_scope or "").strip(),
                    "score": round(float(hit.score or 0.0), 4),
                    "question_text": str(metadata.get("question_text") or "").strip() or None,
                    "lexical_raw_score": round(float(metadata.get("lexical_raw_score") or 0.0), 4)
                    if metadata.get("lexical_raw_score") is not None else None,
                    "lexical_structured_score": round(float(metadata.get("lexical_structured_score") or 0.0), 4)
                    if metadata.get("lexical_structured_score") is not None else None,
                }
            )

        return {
            "sheet_name": sheet_name or None,
            "row_identity_text": row_identity_text or None,
            "field_names": field_names[:12],
            "dimension_field_names": dimension_field_names[:12],
            "metric_field_names": metric_field_names[:12],
            "identifier_field_names": identifier_field_names[:12],
            "filter_fields": filter_fields,
            "table_context_text": table_context_text or None,
            "row_explanation_text": row_explanation_text or None,
            "dimension_explanation_text": dimension_explanation_text or None,
            "metric_explanation_text": metric_explanation_text or None,
            "qa_fields": qa_fields,
            "question_text": question_text or None,
            "qa_runtime_config": qa_runtime_config if any(value is not None for value in qa_runtime_config.values()) else {},
            "lexical_raw_score": round(lexical_raw_score, 4) if lexical_raw_score is not None else None,
            "lexical_structured_score": round(lexical_structured_score, 4) if lexical_structured_score is not None else None,
            "lexical_structured_candidates": lexical_structured_candidates[:6],
            "hit_score_details": hit_score_details[:10],
        }

    async def _apply_rerank_if_needed(
        self,
        *,
        current_user: User,
        query: str,
        config: HybridSearchConfig,
        items: list[dict[str, Any]],
        rerank_model_id: UUID | None,
    ) -> list[dict[str, Any]]:
        """应用二阶段模型重排序。"""

        if not items:
            return []

        if not config.enable_rerank:
            ordered = sorted(items, key=lambda current: float(current.get("score") or 0.0), reverse=True)
            ordered = ordered[: config.top_k]
            for index, item in enumerate(ordered, start=1):
                metadata = dict(item.get("metadata") or {})
                metadata["rerank_stage"] = "disabled"
                metadata["rerank_model"] = None
                item["metadata"] = metadata
                item["rank"] = index
            return ordered

        rerank_model = str(config.rerank_model or "").strip()
        if rerank_model_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前 rerank 模型配置无效，请重新选择一个有效的 rerank 模型",
            )
        rerank_model_display_name = await self._resolve_tenant_model_display_name(tenant_model_id=rerank_model_id)
        documents: list[str | dict[str, Any]] = [self._build_rerank_document(item) for item in items]
        rerank_response = await self.model_invocation_service.rerank(
            current_user=current_user,
            tenant_model_id=rerank_model_id,
            capability_type="rerank",
            query=query,
            documents=documents,
            top_n=min(max(config.top_k, 1), len(documents)),
            return_documents=False,
            request_source="kb_retrieval_rerank",
        )
        result_rows = list(rerank_response.get("results") or [])
        if not result_rows:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="重排序模型未返回有效结果",
            )

        reranked: list[dict[str, Any]] = []
        consumed_indexes: set[int] = set()
        for row in result_rows:
            try:
                result_index = int(row.get("index"))
            except (TypeError, ValueError):
                continue
            if result_index < 0 or result_index >= len(items) or result_index in consumed_indexes:
                continue

            consumed_indexes.add(result_index)
            item = dict(items[result_index])
            metadata = dict(item.get("metadata") or {})
            base_score = float(item.get("score") or 0.0)
            # 模型平台已经把上游不同协议统一归一为 score，
            # 这里优先读取统一字段，兼容极少数仍返回 relevance_score 的情况。
            rerank_score = float(row.get("score", row.get("relevance_score", 0.0)) or 0.0)
            score_trace = dict(metadata.get("score_trace") or {})
            metadata["fusion_score"] = round(base_score, 4)
            metadata["rerank_score"] = round(rerank_score, 4)
            metadata["rerank_stage"] = "model"
            metadata["rerank_model"] = rerank_model_display_name
            metadata["rerank_model_id"] = rerank_model
            score_trace.update(
                {
                    "fusion_score": round(base_score, 4),
                    "rerank_score": round(rerank_score, 4),
                    "rerank_model": rerank_model_display_name,
                    "rerank_model_id": rerank_model,
                }
            )
            metadata["score_trace"] = score_trace
            item["metadata"] = metadata
            item["score"] = round(rerank_score, 4)
            reranked.append(item)

        if not reranked:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="重排序模型返回结果无法映射到候选集",
            )

        reranked.sort(key=lambda current: float(current.get("score") or 0.0), reverse=True)
        reranked = reranked[: config.top_k]
        for index, item in enumerate(reranked, start=1):
            item["rank"] = index
        return reranked

    async def _resolve_tenant_model_display_name(self, *, tenant_model_id: UUID) -> str:
        """根据租户模型 ID 解析可读展示名。"""

        stmt = (
            select(TenantModel, PlatformModel)
            .join(PlatformModel, PlatformModel.id == TenantModel.platform_model_id)
            .where(TenantModel.id == tenant_model_id)
            .limit(1)
        )
        row = (await self.session.execute(stmt)).first()
        if not row:
            return str(tenant_model_id)
        tenant_model, platform_model = row
        return (
            str(tenant_model.model_alias or "").strip()
            or str(platform_model.display_name or "").strip()
            or str(platform_model.raw_model_name or "").strip()
            or str(tenant_model_id)
        )

    def _build_rerank_document(self, item: dict[str, Any]) -> str:
        """构造重排序模型的候选文本。"""

        title = str(item.get("title") or "").strip()
        snippet = str(item.get("content") or "").strip()
        metadata = dict(item.get("metadata") or {})
        question_text = str(metadata.get("question_text") or "").strip()
        table_context_text = str(metadata.get("table_context_text") or "").strip()
        field_names = [str(field).strip() for field in list(metadata.get("field_names") or []) if str(field).strip()]
        parts = [title]
        if question_text:
            parts.append(f"问题: {question_text}")
        if table_context_text:
            parts.append(f"表格上下文: {table_context_text}")
        if field_names:
            parts.append(f"字段: {'、'.join(field_names[:8])}")
        if snippet:
            parts.append(snippet)
        return "\n".join(part for part in parts if part).strip()

    async def _load_kb_doc_tags(
        self,
        *,
        kb: KnowledgeBase,
        kb_doc_ids: Iterable[UUID],
    ) -> dict[UUID, list[str]]:
        """批量加载知识库文档标签。"""

        normalized_ids = list(dict.fromkeys(kb_doc_ids))
        if not normalized_ids:
            return {}
        stmt = (
            select(ResourceTag.target_id, Tag.name)
            .join(Tag, Tag.id == ResourceTag.tag_id)
            .where(
                ResourceTag.tenant_id == kb.tenant_id,
                ResourceTag.kb_id == kb.id,
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.action == "add",
                ResourceTag.target_id.in_(normalized_ids),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        result: dict[UUID, list[str]] = defaultdict(list)
        for target_id, tag_name in rows:
            normalized_name = str(tag_name or "").strip()
            if normalized_name and normalized_name not in result[target_id]:
                result[target_id].append(normalized_name)
        return dict(result)

    async def _build_auto_tag_boosts(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        hits: Sequence[SearchHit],
        auto_filter_signals: Sequence[QueryAnalysisAutoFilterSignal],
    ) -> dict[UUID, dict[str, Any]]:
        """根据自动标签信号计算文档级轻量加分。"""

        doc_tag_signals = [item for item in auto_filter_signals if item.signal_type == "doc_tag"]
        folder_tag_signals = [item for item in auto_filter_signals if item.signal_type == "folder_tag"]
        if not doc_tag_signals and not folder_tag_signals:
            return {}

        kb_doc_ids = list(dict.fromkeys(hit.kb_doc_id for hit in hits if hit.kb_doc_id is not None))
        if not kb_doc_ids:
            return {}

        doc_tag_ids = self._coerce_signal_uuid_set(doc_tag_signals)
        folder_tag_ids = self._coerce_signal_uuid_set(folder_tag_signals)
        result: dict[UUID, dict[str, Any]] = {
            kb_doc_id: {
                "boost": 0.0,
                "doc_tag_boost": 0.0,
                "folder_tag_boost": 0.0,
                "matches": [],
            }
            for kb_doc_id in kb_doc_ids
        }

        if doc_tag_ids:
            stmt = select(ResourceTag.target_id, ResourceTag.tag_id).where(
                ResourceTag.tenant_id == current_user.tenant_id,
                ResourceTag.kb_id == kb.id,
                ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                ResourceTag.action == "add",
                ResourceTag.target_id.in_(kb_doc_ids),
                ResourceTag.tag_id.in_(list(doc_tag_ids)),
            )
            rows = (await self.session.execute(stmt)).all()
            signal_map = {str(signal.target_id): signal for signal in doc_tag_signals}
            per_doc_scores: dict[UUID, list[float]] = defaultdict(list)
            for target_id, tag_id in rows:
                signal = signal_map.get(str(tag_id))
                if signal is None:
                    continue
                source_weight = self._resolve_auto_tag_source_weight(signal)
                score = min(0.07, max(0.0, float(signal.confidence or 0.0)) * source_weight * 0.07)
                per_doc_scores[target_id].append(score)
                result.setdefault(target_id, {"boost": 0.0, "doc_tag_boost": 0.0, "folder_tag_boost": 0.0, "matches": []})
                result[target_id]["matches"].append(
                    {
                        "type": "doc_tag",
                        "tag_id": str(tag_id),
                        "filter_value": signal.filter_value,
                        "score": round(score, 4),
                    }
                )
            for target_id, scores in per_doc_scores.items():
                if not scores:
                    continue
                doc_boost = max(scores) + min(0.02, max(0, len(scores) - 1) * 0.01)
                result[target_id]["doc_tag_boost"] = round(min(0.07, doc_boost), 4)

        if folder_tag_ids:
            doc_rows = (
                await self.session.execute(
                    select(KnowledgeBaseDocument.id, KnowledgeBaseDocument.folder_id, Folder.path)
                    .join(Folder, Folder.id == KnowledgeBaseDocument.folder_id, isouter=True)
                    .where(
                        KnowledgeBaseDocument.tenant_id == current_user.tenant_id,
                        KnowledgeBaseDocument.kb_id == kb.id,
                        KnowledgeBaseDocument.id.in_(kb_doc_ids),
                    )
                )
            ).all()
            folder_ids: set[UUID] = set()
            doc_folder_paths: dict[UUID, list[UUID]] = {}
            for kb_doc_id, folder_id, folder_path in doc_rows:
                path_ids = self._parse_folder_path_ids(folder_path)
                if folder_id is not None and folder_id not in path_ids:
                    path_ids.append(folder_id)
                doc_folder_paths[kb_doc_id] = path_ids
                folder_ids.update(path_ids)
            if folder_ids:
                tag_rows = (
                    await self.session.execute(
                        select(ResourceTag.target_id, ResourceTag.tag_id).where(
                            ResourceTag.tenant_id == current_user.tenant_id,
                            ResourceTag.kb_id == kb.id,
                            ResourceTag.target_type == TARGET_TYPE_FOLDER,
                            ResourceTag.action == "add",
                            ResourceTag.target_id.in_(list(folder_ids)),
                            ResourceTag.tag_id.in_(list(folder_tag_ids)),
                        )
                    )
                ).all()
                folder_tag_map: dict[UUID, list[UUID]] = defaultdict(list)
                for folder_id, tag_id in tag_rows:
                    folder_tag_map[folder_id].append(tag_id)
                signal_map = {str(signal.target_id): signal for signal in folder_tag_signals}
                per_doc_folder_scores: dict[UUID, list[float]] = defaultdict(list)
                for kb_doc_id, path_ids in doc_folder_paths.items():
                    if not path_ids:
                        continue
                    last_index = len(path_ids) - 1
                    for index, folder_id in enumerate(path_ids):
                        distance = max(0, last_index - index)
                        distance_decay = self._resolve_folder_tag_distance_decay(distance)
                        for tag_id in folder_tag_map.get(folder_id, []):
                            signal = signal_map.get(str(tag_id))
                            if signal is None:
                                continue
                            source_weight = self._resolve_auto_tag_source_weight(signal)
                            score = min(0.09, max(0.0, float(signal.confidence or 0.0)) * source_weight * distance_decay * 0.09)
                            per_doc_folder_scores[kb_doc_id].append(score)
                            result.setdefault(kb_doc_id, {"boost": 0.0, "doc_tag_boost": 0.0, "folder_tag_boost": 0.0, "matches": []})
                            result[kb_doc_id]["matches"].append(
                                {
                                    "type": "folder_tag",
                                    "tag_id": str(tag_id),
                                    "folder_id": str(folder_id),
                                    "distance": distance,
                                    "filter_value": signal.filter_value,
                                    "score": round(score, 4),
                                }
                            )
                for kb_doc_id, scores in per_doc_folder_scores.items():
                    if not scores:
                        continue
                    folder_boost = max(scores) + min(0.015, max(0, len(scores) - 1) * 0.0075)
                    result[kb_doc_id]["folder_tag_boost"] = round(min(0.09, folder_boost), 4)

        for kb_doc_id, payload in result.items():
            payload["boost"] = round(
                min(0.10, float(payload.get("doc_tag_boost") or 0.0) + float(payload.get("folder_tag_boost") or 0.0)),
                4,
            )
        return {kb_doc_id: payload for kb_doc_id, payload in result.items() if float(payload.get("boost") or 0.0) > 0}

    def _coerce_signal_uuid_set(self, signals: Sequence[QueryAnalysisAutoFilterSignal]) -> set[UUID]:
        """提取自动信号中的 UUID。"""

        result: set[UUID] = set()
        for signal in signals:
            try:
                result.add(UUID(str(signal.target_id)))
            except ValueError:
                continue
        return result

    def _resolve_auto_tag_source_weight(self, signal: QueryAnalysisAutoFilterSignal) -> float:
        """按候选来源调整标签信号强度。"""

        source = str(signal.source or "").strip()
        if signal.layer == "llm":
            return 1.0
        if "tag_alias" in source:
            return 0.90
        return 0.95

    def _resolve_folder_tag_distance_decay(self, distance: int) -> float:
        """文件夹标签按祖先距离衰减。"""

        if distance <= 0:
            return 1.0
        if distance == 1:
            return 0.75
        if distance == 2:
            return 0.55
        return max(0.30, 0.75 ** distance)

    def _parse_folder_path_ids(self, folder_path: Any) -> list[UUID]:
        """解析 ltree 文件夹路径中的 UUID 片段。"""

        result: list[UUID] = []
        for segment in str(folder_path or "").split("."):
            if not segment.startswith(("kb_", "f_")):
                continue
            try:
                result.append(UUID(segment[3:]))
            except ValueError:
                continue
        return result

    def _resolve_vector_scopes(
        self,
        config: HybridSearchConfig,
        *,
        kb: KnowledgeBase | None = None,
        qa_config: Mapping[str, Any] | None = None,
    ) -> list[str]:
        """返回向量召回 scope。"""

        if kb is not None and str(kb.type or "").strip() == "qa":
            if str((qa_config or {}).get("index_mode") or "question_only").strip() == "question_answer":
                return ["question", "answer"]
            return ["question"]
        if kb is not None and str(kb.type or "").strip() == "table":
            return list(TABLE_VECTOR_SCOPES)

        if not config.search_scopes:
            return list(DEFAULT_VECTOR_SCOPES)
        return [
            scope for scope in config.search_scopes
            if scope not in {"keyword", "doc_summary"}
        ]

    def _resolve_lexical_scopes(
        self,
        config: HybridSearchConfig,
        *,
        kb: KnowledgeBase | None = None,
        qa_config: Mapping[str, Any] | None = None,
    ) -> list[str]:
        """返回全文召回 scope。"""

        if kb is not None and str(kb.type or "").strip() == "qa":
            scopes = ["question"]
            if str((qa_config or {}).get("index_mode") or "question_only").strip() == "question_answer":
                scopes.append("answer")
            if bool((qa_config or {}).get("enable_keyword_recall", True)):
                scopes.append("keyword")
            return scopes
        if kb is not None and str(kb.type or "").strip() == "table":
            return list(TABLE_LEXICAL_SCOPES)

        if not config.search_scopes:
            return list(DEFAULT_LEXICAL_SCOPES)
        return list(config.search_scopes)

    def _resolve_scope_weights(
        self,
        *,
        kb: KnowledgeBase,
        qa_config: Mapping[str, Any] | None,
    ) -> dict[str, float]:
        """按知识库类型调整检索投影权重。"""

        weights = dict(SEARCH_SCOPE_WEIGHTS)
        kb_type = str(kb.type or "").strip()
        if kb_type == "table":
            weights["row"] = 1.0
            weights["row_group"] = 0.94
            weights["row_fragment"] = 0.9
            weights["summary"] = 0.82
            weights["default"] = 0.84
            return weights

        if kb_type != "qa":
            return weights

        query_weight = float((qa_config or {}).get("query_weight") or 1.0)
        answer_weight = float((qa_config or {}).get("answer_weight") or 0.0)
        max_weight = max(query_weight, answer_weight, 0.0001)
        weights["question"] = SEARCH_SCOPE_WEIGHTS["question"] * (query_weight / max_weight)
        weights["answer"] = SEARCH_SCOPE_WEIGHTS["answer"] * (answer_weight / max_weight) if answer_weight > 0 else 0.0
        return weights

    def _build_result_snippet(
        self,
        *,
        chunk: Chunk,
        parent_chunk: Optional[Chunk],
        max_length: int,
        enable_parent_context: bool,
        previous_neighbors: Sequence[Chunk] = (),
        next_neighbors: Sequence[Chunk] = (),
    ) -> str:
        """构造前端展示摘要。"""
        return self._truncate_text(
            self._build_result_context_text(
                chunk=chunk,
                parent_chunk=parent_chunk,
                enable_parent_context=enable_parent_context,
                previous_neighbors=previous_neighbors,
                next_neighbors=next_neighbors,
            ),
            max_length,
        )

    def _merge_neighbor_context(
        self,
        *,
        core_text: str,
        previous_neighbors: Sequence[Chunk],
        next_neighbors: Sequence[Chunk],
    ) -> str:
        """将相邻叶子块上下文拼接到主命中块周围。"""

        parts: list[str] = []
        if previous_neighbors:
            previous_text = "\n".join(
                str(item.summary or item.content or "").strip()
                for item in previous_neighbors
                if str(item.summary or item.content or "").strip()
            ).strip()
            if previous_text:
                parts.append(f"[前文邻近块]\n{previous_text}")
        parts.append(str(core_text or "").strip())
        if next_neighbors:
            next_text = "\n".join(
                str(item.summary or item.content or "").strip()
                for item in next_neighbors
                if str(item.summary or item.content or "").strip()
            ).strip()
            if next_text:
                parts.append(f"[后文邻近块]\n{next_text}")
        return "\n".join(part for part in parts if part).strip()

    def _compute_repeated_hit_bonus(self, *, hit: SearchHit, grouped: GroupedHit) -> float:
        """针对表格行片段与 QA 答案碎片提供轻量重复命中奖励。"""

        same_scope_hits = [item for item in grouped.hits if item.search_scope == hit.search_scope]
        if len(same_scope_hits) <= 1:
            return 0.0
        if hit.search_scope == "answer":
            return min(0.08, (len(same_scope_hits) - 1) * 0.02)
        if hit.search_scope == "row_fragment":
            return min(0.05, (len(same_scope_hits) - 1) * 0.015)
        return 0.0

    def _analyze_query_characteristics(self, query: str) -> dict[str, Any]:
        """提取轻量查询意图，用于 QA / 表格第二阶段加权。"""

        normalized = normalize_lexical_text(query)
        ascii_terms = extract_ascii_terms(normalized)
        cjk_terms = extract_cjk_terms(normalized)
        short_query = len(normalized) <= 18
        question_like = any(token in normalized for token in ("如何", "怎么", "为什么", "原因", "是否", "能否", "哪些", "什么"))
        answer_like = any(token in normalized for token in ("步骤", "处理", "解决", "配置", "设置", "排查", "修复", "原因", "办法"))
        table_lookup_like = any(token in normalized for token in ("统计", "汇总", "合计", "平均", "同比", "环比", "筛选", "地区", "年份", "产品"))
        return {
            "normalized": normalized,
            "ascii_terms": ascii_terms,
            "cjk_terms": cjk_terms,
            "query_terms": list(dict.fromkeys([*ascii_terms, *cjk_terms])),
            "short_query": short_query,
            "question_like": question_like,
            "answer_like": answer_like,
            "table_lookup_like": table_lookup_like,
        }

    def _compute_query_intent_bonus(
        self,
        *,
        kb: KnowledgeBase,
        hit: SearchHit,
        query_characteristics: Mapping[str, Any],
    ) -> float:
        """按知识库类型和问题意图给不同 scope 小幅加权。"""

        kb_type = str(kb.type or "").strip()
        search_scope = str(hit.search_scope or "").strip()
        if kb_type == "qa":
            if search_scope == "question" and bool(query_characteristics.get("question_like")):
                return 0.035
            if search_scope == "answer" and bool(query_characteristics.get("answer_like")):
                return 0.03
            if search_scope == "question" and bool(query_characteristics.get("short_query")):
                return 0.015
            return 0.0

        if kb_type == "table":
            if search_scope == "row" and bool(query_characteristics.get("table_lookup_like")):
                return 0.035
            if search_scope == "row_group" and bool(query_characteristics.get("table_lookup_like")):
                return 0.025
            if search_scope == "row_fragment" and len(list(query_characteristics.get("query_terms") or [])) >= 3:
                return 0.02
        return 0.0

    def _compute_metadata_bonus(
        self,
        *,
        kb: KnowledgeBase,
        hit: SearchHit,
        query_characteristics: Mapping[str, Any],
    ) -> float:
        """基于非过滤型检索投影元数据做轻量词面加分。"""

        metadata = dict(hit.metadata or {})
        query_terms = [str(item).strip().lower() for item in list(query_characteristics.get("query_terms") or []) if str(item).strip()]
        if not metadata or not query_terms:
            return 0.0

        kb_type = str(kb.type or "").strip()
        candidate_texts: list[str] = []
        if kb_type == "qa":
            question_text = str(metadata.get("question_text") or "").strip()
            if question_text:
                candidate_texts.append(question_text)
        elif kb_type == "table":
            if metadata.get("sheet_name"):
                candidate_texts.append(str(metadata.get("sheet_name")))
            if metadata.get("row_identity_text"):
                candidate_texts.append(str(metadata.get("row_identity_text")))
            candidate_texts.extend([str(item).strip() for item in list(metadata.get("field_names") or []) if str(item).strip()])
            candidate_texts.extend([str(item).strip() for item in list(metadata.get("dimension_field_names") or []) if str(item).strip()])
            candidate_texts.extend([str(item).strip() for item in list(metadata.get("metric_field_names") or []) if str(item).strip()])
            if metadata.get("table_context_text"):
                candidate_texts.append(str(metadata.get("table_context_text")))

        if not candidate_texts:
            return 0.0

        haystack = "\n".join(candidate_texts).lower()
        hit_count = sum(1 for term in query_terms if term and term in haystack)
        if hit_count <= 0:
            return 0.0
        return min(0.04, hit_count * 0.01)

    def _truncate_text(self, text: str, max_length: int) -> str:
        """裁剪展示文本。"""

        normalized = " ".join(str(text or "").split()).strip()
        if len(normalized) <= max_length:
            return normalized
        return normalized[: max(0, max_length - 3)].rstrip() + "..."

    def _build_bigrams(self, text: str) -> set[str]:
        """构造中英文通用的二元片段集合。"""

        normalized = " ".join(str(text or "").lower().split()).strip()
        if not normalized:
            return set()
        if len(normalized) == 1:
            return {normalized}
        return {normalized[index:index + 2] for index in range(len(normalized) - 1)}

    def _tokenize_terms(self, text: str) -> list[str]:
        """提取简单查询词，用于轻量词面重合度计算。"""

        normalized = " ".join(str(text or "").lower().split()).strip()
        if not normalized:
            return []
        return list(dict.fromkeys([item for item in normalized.split(" ") if item]))

    def _compute_bigram_overlap(self, left: set[str], right: set[str]) -> float:
        """计算二元片段交并比。"""

        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _compute_doc_summary_score(
        self,
        *,
        query_bigrams: set[str],
        query_terms: list[str],
        summary_text: str,
        title_text: str,
    ) -> float:
        """计算文档摘要检索得分。"""

        haystack = "\n".join(item for item in [title_text, summary_text] if item).lower()
        if not haystack:
            return 0.0

        bigram_score = self._compute_bigram_overlap(query_bigrams, self._build_bigrams(haystack))
        term_overlap = 0.0
        if query_terms:
            hit_count = sum(1 for term in query_terms if term and term in haystack)
            term_overlap = hit_count / max(1, len(query_terms))

        score = (bigram_score * 0.75) + (term_overlap * 0.25)
        return min(1.0, score)

    def _serialize_metadata_filter_value(self, value: Any) -> str:
        """统一 metadata 过滤值比较口径。"""

        if isinstance(value, bool):
            return "true" if value else "false"
        return serialize_filter_value(value)


def _coerce_uuid_list(value: Any) -> list[UUID]:
    """把任意输入规范化为 UUID 列表。"""

    if value is None:
        return []
    raw_values = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[UUID] = []
    for item in raw_values:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            result.append(UUID(text))
        except ValueError:
            continue
    return list(dict.fromkeys(result))


def _normalize_metadata_dict(value: Any) -> dict[str, Any]:
    """规范化 metadata 字典。"""

    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        if item is None or item == "":
            continue
        result[normalized_key] = item
    return result


def _coerce_optional_uuid(value: Any) -> UUID | None:
    """把任意输入尽量解析为 UUID，失败时返回 None。"""

    text = str(value or "").strip()
    if not text:
        return None
    try:
        return UUID(text)
    except (TypeError, ValueError):
        return None
