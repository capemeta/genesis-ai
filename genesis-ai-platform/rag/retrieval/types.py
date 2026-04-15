"""
检索层通用类型定义
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass(slots=True)
class RetrievalFilterSet:
    """统一过滤层配置。

    设计原则：
    - 目录树、标签、文档元数据等属于硬过滤条件
    - LLM 生成的摘要 / 问题 / 关键词不参与硬过滤，只参与召回与排序
    """

    kb_doc_ids: List[UUID] = field(default_factory=list)
    document_ids: List[UUID] = field(default_factory=list)
    content_group_ids: List[UUID] = field(default_factory=list)
    folder_ids: List[UUID] = field(default_factory=list)
    tag_ids: List[UUID] = field(default_factory=list)
    folder_tag_ids: List[UUID] = field(default_factory=list)
    document_metadata: Dict[str, Any] = field(default_factory=dict)
    search_unit_metadata: Dict[str, Any] = field(default_factory=dict)
    filter_expression: Dict[str, Any] = field(default_factory=dict)
    include_descendant_folders: bool = True
    only_tagged: bool = False
    latest_days: Optional[int] = None


@dataclass(slots=True)
class HybridSearchConfig:
    """统一混合检索参数。

    同时兼容：
    - 知识库检索测试页的显式参数
    - 聊天会话中的 search_depth_k / rerank_top_n / min_score
    """

    top_k: int = 8
    vector_top_k: int = 60
    keyword_top_k: int = 40
    rerank_top_n: int = 30
    vector_similarity_threshold: float = 0.25
    keyword_relevance_threshold: float = 0.2
    final_score_threshold: float = 0.3
    vector_weight: float = 0.55
    enable_rerank: bool = True
    rerank_model: Optional[str] = None
    metadata_filter_mode: str = "all"
    use_knowledge_graph: bool = False
    enable_query_rewrite: bool = False
    enable_synonym_rewrite: bool = True
    auto_filter_mode: str = "disabled"
    enable_doc_summary_retrieval: bool = False
    search_scopes: List[str] = field(default_factory=list)
    enable_parent_context: bool = True
    hierarchical_retrieval_mode: str = "recursive"
    neighbor_window_size: int = 0
    group_by_content_group: bool = True
    max_snippet_length: int = 280
    debug_trace_level: str = "off"


@dataclass(slots=True)
class VectorSearchRequest:
    """向量检索请求。"""

    tenant_id: UUID
    kb_id: UUID
    query: str
    query_embedding: List[float]
    query_embedding_dimension: int | None = None
    top_k: int = 10
    search_scopes: List[str] = field(default_factory=list)
    metadata_filters: Dict[str, Any] = field(default_factory=dict)
    metadata_filter_expression: Dict[str, Any] = field(default_factory=dict)
    kb_doc_ids: List[UUID] = field(default_factory=list)
    document_ids: List[UUID] = field(default_factory=list)
    content_group_ids: List[UUID] = field(default_factory=list)
    display_only: bool = True
    leaf_only: bool = True


@dataclass(slots=True)
class LexicalSearchRequest:
    """全文检索请求。"""

    tenant_id: UUID
    kb_id: UUID
    query: str
    priority_terms: List[str] = field(default_factory=list)
    priority_phrases: List[str] = field(default_factory=list)
    synonym_terms: List[str] = field(default_factory=list)
    glossary_terms: List[str] = field(default_factory=list)
    retrieval_stopwords: List[str] = field(default_factory=list)
    lexicon_weights: Dict[str, float] = field(default_factory=dict)
    top_k: int = 10
    search_scopes: List[str] = field(default_factory=list)
    metadata_filters: Dict[str, Any] = field(default_factory=dict)
    metadata_filter_expression: Dict[str, Any] = field(default_factory=dict)
    kb_doc_ids: List[UUID] = field(default_factory=list)
    document_ids: List[UUID] = field(default_factory=list)
    content_group_ids: List[UUID] = field(default_factory=list)
    display_only: bool = True
    leaf_only: bool = True


@dataclass(slots=True)
class SearchHit:
    """统一检索命中结果。"""

    search_unit_id: int
    chunk_id: int
    kb_id: UUID
    kb_doc_id: UUID
    document_id: UUID
    content_group_id: Optional[UUID]
    search_scope: str
    score: float
    backend_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
