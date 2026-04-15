"""
查询分析层通用类型定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from rag.retrieval.types import RetrievalFilterSet


@dataclass(slots=True)
class QueryAnalysisConfig:
    """查询分析配置。"""

    enable_query_rewrite: bool = False
    enable_synonym_rewrite: bool = True
    auto_filter_mode: str = "disabled"
    max_glossary_terms: int = 8
    metadata_fields: list[dict[str, Any]] = field(default_factory=list)
    retrieval_lexicon: list[dict[str, Any]] = field(default_factory=list)
    retrieval_stopwords: list[str] = field(default_factory=list)
    extra_retrieval_stopwords: list[str] = field(default_factory=list)
    enable_llm_candidate_extraction: bool = False
    enable_llm_filter_expression: bool = True
    llm_candidate_min_confidence: float = 0.55
    llm_upgrade_confidence_threshold: float = 0.82
    llm_max_upgrade_count: int = 2
    query_rewrite_context: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class QueryAnalysisSynonymMatch:
    """同义词改写命中。"""

    user_term: str
    professional_term: str
    synonym_id: UUID
    variant_id: UUID
    scope: str
    expansion_terms: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QueryAnalysisGlossaryEntry:
    """术语上下文条目。"""

    term: str
    definition: str
    examples: Optional[str]
    scope: str


@dataclass(slots=True)
class QueryAnalysisLexiconMatch:
    """知识库级检索词表命中。"""

    term: str
    matched_text: str
    aliases: list[str] = field(default_factory=list)
    is_phrase: bool = False
    weight: float = 1.0
    source: str = "custom"


@dataclass(slots=True)
class QueryAnalysisFilterCandidate:
    """规则型过滤候选。"""

    filter_type: str
    filter_value: str
    target_id: UUID | str | list[str]
    confidence: float
    source: str
    layer: str = "rule"
    validation_status: str = "unknown"
    validation_reason: Optional[str] = None
    upgraded_to_hard_filter: bool = False
    applied: bool = False
    model_reason: Optional[str] = None
    evidence_type: Optional[str] = None
    evidence_text: Optional[str] = None
    evidence_query_source: Optional[str] = None
    matched_alias: Optional[str] = None
    candidate_terms: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QueryAnalysisAutoFilterSignal:
    """自动过滤 / 加权信号。

    自动信号不直接等同硬过滤：
    - tag_boost 用于排序加权
    - match_or_missing / match_only 用于自动元数据过滤
    """

    signal_type: str
    target_id: str
    filter_value: str
    confidence: float
    source: str
    usage: str
    match_mode: str = "boost"
    target_path: list[str] = field(default_factory=list)
    layer: str = "rule"
    metadata_target: str | None = None
    applied: bool = False
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalyzedQuery:
    """查询分析结果。"""

    raw_query: str
    standalone_query: str
    rewritten_query: str
    lexical_query: str
    retrieval_filters: RetrievalFilterSet
    synonym_matches: list[QueryAnalysisSynonymMatch] = field(default_factory=list)
    glossary_entries: list[QueryAnalysisGlossaryEntry] = field(default_factory=list)
    retrieval_lexicon_matches: list[QueryAnalysisLexiconMatch] = field(default_factory=list)
    ignored_lexical_terms: list[str] = field(default_factory=list)
    retrieval_stopwords: list[str] = field(default_factory=list)
    extra_retrieval_stopwords: list[str] = field(default_factory=list)
    priority_lexical_terms: list[str] = field(default_factory=list)
    priority_lexical_phrases: list[str] = field(default_factory=list)
    lexicon_weights: dict[str, float] = field(default_factory=dict)
    filter_candidates: list[QueryAnalysisFilterCandidate] = field(default_factory=list)
    auto_filter_signals: list[QueryAnalysisAutoFilterSignal] = field(default_factory=list)
    query_rewrite_debug: dict[str, Any] | None = None
    llm_debug: dict[str, Any] | None = None
    resolved_filter_labels: dict[str, Any] = field(default_factory=dict)

    def to_debug_dict(self) -> dict[str, Any]:
        """序列化为调试信息。"""

        def _build_label_map(items: Any) -> dict[str, dict[str, Any]]:
            result: dict[str, dict[str, Any]] = {}
            for item in list(items or []):
                if not isinstance(item, dict):
                    continue
                target_id = str(item.get("id") or "").strip()
                if target_id:
                    result[target_id] = dict(item)
            return result

        resolved_labels = dict(self.resolved_filter_labels or {})
        folder_label_map = _build_label_map(resolved_labels.get("folders"))
        doc_tag_label_map = _build_label_map(resolved_labels.get("doc_tags"))
        folder_tag_label_map = _build_label_map(resolved_labels.get("folder_tags"))
        kb_doc_label_map = _build_label_map(resolved_labels.get("kb_docs"))

        def _serialize_candidate(item: Any) -> dict[str, Any]:
            target_key = ".".join(item.target_id) if isinstance(item.target_id, list) else str(item.target_id)
            payload = {
                "filter_type": item.filter_type,
                "filter_value": item.filter_value,
                "target_id": target_key,
                "confidence": round(item.confidence, 4),
                "source": item.source,
                "model_reason": item.model_reason,
                "validation_status": item.validation_status,
                "validation_reason": item.validation_reason,
                "evidence_type": item.evidence_type,
                "evidence_text": item.evidence_text,
                "evidence_query_source": item.evidence_query_source,
                "matched_alias": item.matched_alias,
                "applied": item.applied,
            }
            label_item = {}
            if item.filter_type == "folder_id":
                label_item = dict(folder_label_map.get(target_key) or {})
            elif item.filter_type == "tag_id":
                label_item = dict(doc_tag_label_map.get(target_key) or {})
            elif item.filter_type == "folder_tag_id":
                label_item = dict(folder_tag_label_map.get(target_key) or {})
            elif item.filter_type == "kb_doc_id":
                label_item = dict(kb_doc_label_map.get(target_key) or {})
            if label_item:
                payload["display_name"] = str(label_item.get("name") or "").strip() or None
                if str(label_item.get("path") or "").strip():
                    payload["display_path"] = str(label_item.get("path") or "").strip()
                if list(label_item.get("matched_terms") or []):
                    payload["matched_terms"] = list(label_item.get("matched_terms") or [])
            return payload

        return {
            "raw_query": self.raw_query,
            "standalone_query": self.standalone_query,
            "rewritten_query": self.rewritten_query,
            "lexical_query": self.lexical_query,
            "query_rewrite_debug": dict(self.query_rewrite_debug or {}),
            "candidate_breakdown": {
                "rule_candidates": [
                    _serialize_candidate(item)
                    for item in self.filter_candidates
                    if item.layer == "rule"
                ],
                "llm_candidates": [
                    {
                        **_serialize_candidate(item),
                        "upgraded_to_hard_filter": item.upgraded_to_hard_filter,
                    }
                    for item in self.filter_candidates
                    if item.layer == "llm"
                ],
                "corrected_rule_candidates": [
                    _serialize_candidate(item)
                    for item in self.filter_candidates
                    if item.layer == "rule" and item.validation_status == "corrected_by_llm"
                ],
            },
            "synonym_matches": [
                {
                    "user_term": item.user_term,
                    "professional_term": item.professional_term,
                    "expansion_terms": list(item.expansion_terms),
                    "synonym_id": str(item.synonym_id),
                    "variant_id": str(item.variant_id),
                    "scope": item.scope,
                }
                for item in self.synonym_matches
            ],
            "glossary_entries": [
                {
                    "term": item.term,
                    "definition": item.definition,
                    "examples": item.examples,
                    "scope": item.scope,
                }
                for item in self.glossary_entries
            ],
            "retrieval_lexicon_matches": [
                {
                    "term": item.term,
                    "matched_text": item.matched_text,
                    "aliases": list(item.aliases),
                    "is_phrase": item.is_phrase,
                    "weight": round(item.weight, 4),
                    "source": item.source,
                }
                for item in self.retrieval_lexicon_matches
            ],
            "ignored_lexical_terms": list(self.ignored_lexical_terms),
            "retrieval_stopwords": list(self.extra_retrieval_stopwords),
            "merged_retrieval_stopword_count": len(self.retrieval_stopwords),
            "priority_lexical_terms": list(self.priority_lexical_terms),
            "priority_lexical_phrases": list(self.priority_lexical_phrases),
            "lexicon_weights": {k: round(v, 4) for k, v in self.lexicon_weights.items()},
            "filter_candidates": [
                {
                    "filter_type": item.filter_type,
                    "filter_value": item.filter_value,
                    "target_id": ".".join(item.target_id) if isinstance(item.target_id, list) else str(item.target_id),
                    "confidence": round(item.confidence, 4),
                    "source": item.source,
                    "model_reason": item.model_reason,
                    "layer": item.layer,
                    "validation_status": item.validation_status,
                    "validation_reason": item.validation_reason,
                    "evidence_type": item.evidence_type,
                    "evidence_text": item.evidence_text,
                    "evidence_query_source": item.evidence_query_source,
                    "matched_alias": item.matched_alias,
                    "upgraded_to_hard_filter": item.upgraded_to_hard_filter,
                    "applied": item.applied,
                }
                for item in self.filter_candidates
            ],
            "auto_filter_signals": [
                {
                    "signal_type": item.signal_type,
                    "target_id": item.target_id,
                    "target_path": list(item.target_path),
                    "filter_value": item.filter_value,
                    "confidence": round(item.confidence, 4),
                    "source": item.source,
                    "usage": item.usage,
                    "match_mode": item.match_mode,
                    "layer": item.layer,
                    "metadata_target": item.metadata_target,
                    "applied": item.applied,
                    "debug": dict(item.debug or {}),
                }
                for item in self.auto_filter_signals
            ],
            "llm_debug": dict(self.llm_debug or {}),
            "resolved_filter_labels": dict(self.resolved_filter_labels or {}),
            "resolved_filters": {
                "kb_doc_ids": [str(item) for item in self.retrieval_filters.kb_doc_ids],
                "document_ids": [str(item) for item in self.retrieval_filters.document_ids],
                "content_group_ids": [str(item) for item in self.retrieval_filters.content_group_ids],
                "folder_ids": [str(item) for item in self.retrieval_filters.folder_ids],
                "tag_ids": [str(item) for item in self.retrieval_filters.tag_ids],
                "folder_tag_ids": [str(item) for item in self.retrieval_filters.folder_tag_ids],
                "document_metadata": dict(self.retrieval_filters.document_metadata),
                "search_unit_metadata": dict(self.retrieval_filters.search_unit_metadata),
                "filter_expression": dict(self.retrieval_filters.filter_expression),
                "include_descendant_folders": self.retrieval_filters.include_descendant_folders,
                "only_tagged": self.retrieval_filters.only_tagged,
                "latest_days": self.retrieval_filters.latest_days,
            },
        }
