"""
检索过滤边界测试。
"""

from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4
import os
import sys

import pytest
from sqlalchemy.dialects import postgresql


# 本测试不访问真实数据库，仅为业务模块导入提供最小配置。
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

# 兼容直接执行本文件：python tests/rag/test_retrieval_filters.py
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import rag  # noqa: F401  # 先加载真实 rag 包，避免子模块桩污染父包识别。

# 避免本测试导入检索服务时初始化 LLM / 模型平台重依赖链路。
_llm_executor_stub = ModuleType("rag.llm.executor")


class _LLMExecutorStub:
    pass


class _LLMRequestStub:
    pass


class _LLMResponseStub:
    pass


setattr(_llm_executor_stub, "LLMExecutor", _LLMExecutorStub)
setattr(_llm_executor_stub, "LLMRequest", _LLMRequestStub)
setattr(_llm_executor_stub, "LLMResponse", _LLMResponseStub)
sys.modules.setdefault("rag.llm.executor", _llm_executor_stub)

_model_platform_service_stub = ModuleType("services.model_platform_service")


class _ModelInvocationServiceStub:
    pass


setattr(_model_platform_service_stub, "ModelInvocationService", _ModelInvocationServiceStub)
sys.modules.setdefault("services.model_platform_service", _model_platform_service_stub)

_search_units_stub = ModuleType("rag.search_units")
setattr(_search_units_stub, "normalize_qa_retrieval_config", lambda _config=None: {})
sys.modules.setdefault("rag.search_units", _search_units_stub)

from rag.retrieval.hybrid import HybridRetrievalService
from rag.retrieval.filter_expression import (
    build_search_unit_expression_sql,
    build_jsonb_expression_sql,
    collect_expanding_param_names,
    filter_expression_has_field,
    normalize_filter_expression,
)
from rag.retrieval.types import RetrievalFilterSet, SearchHit
from rag.query_analysis.service import QueryAnalysisService
from rag.query_analysis.types import QueryAnalysisConfig, QueryAnalysisFilterCandidate


class _FailingSession:
    """确保目录标签未命中时不会继续查询主文档表。"""

    async def execute(self, *_args, **_kwargs):
        raise AssertionError("文件夹标签未命中时不应继续执行文档候选查询")


class _ScalarResult:
    """模拟 SQLAlchemy execute().scalars().all() 的最小结果对象。"""

    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _ExecuteResult:
    """模拟 SQLAlchemy execute() 返回结果。"""

    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def scalars(self):
        return _ScalarResult(self._rows)


@pytest.mark.asyncio
async def test_folder_tag_filter_without_matching_folders_returns_empty_candidate_scope() -> None:
    """只有文件夹标签过滤且标签未命中目录时，应返回空候选范围而不是放开到全库。"""

    service = HybridRetrievalService.__new__(HybridRetrievalService)
    service.session = _FailingSession()

    async def _resolve_folder_ids_by_tags(**_kwargs):
        return []

    async def _expand_folder_ids(**_kwargs):
        return []

    service._resolve_folder_ids_by_tags = _resolve_folder_ids_by_tags  # type: ignore[method-assign]
    service._expand_folder_ids = _expand_folder_ids  # type: ignore[method-assign]

    result = await service._resolve_candidate_filters(
        current_user=SimpleNamespace(tenant_id=uuid4()),
        kb=SimpleNamespace(id=uuid4(), tenant_id=uuid4(), type="general"),
        filters=RetrievalFilterSet(folder_tag_ids=[uuid4()]),
    )

    assert result.filter_applied is True
    assert result.kb_doc_ids == []
    assert result.document_ids == []
    assert result.content_group_ids == []
    assert result.expression_debug["requested"] is False


def test_filter_metadata_fields_do_not_contribute_metadata_bonus() -> None:
    """过滤型元数据只做范围约束，不应进入轻量评分加分。"""

    service = HybridRetrievalService.__new__(HybridRetrievalService)
    common_ids = {
        "kb_id": uuid4(),
        "kb_doc_id": uuid4(),
        "document_id": uuid4(),
        "content_group_id": uuid4(),
    }
    query_characteristics = {"query_terms": ["南康", "地区"]}

    qa_hit = SearchHit(
        search_unit_id=1,
        chunk_id=1,
        search_scope="question",
        score=0.8,
        backend_type="vector",
        metadata={"qa_fields": {"category": "南康", "tags": ["地区"]}},
        **common_ids,
    )
    assert service._compute_metadata_bonus(
        kb=SimpleNamespace(type="qa"),
        hit=qa_hit,
        query_characteristics=query_characteristics,
    ) == 0.0

    table_filter_hit = SearchHit(
        search_unit_id=2,
        chunk_id=2,
        search_scope="row",
        score=0.8,
        backend_type="vector",
        metadata={"filter_fields": {"地区": "南康"}},
        **common_ids,
    )
    assert service._compute_metadata_bonus(
        kb=SimpleNamespace(type="table"),
        hit=table_filter_hit,
        query_characteristics=query_characteristics,
    ) == 0.0

    table_projection_hit = SearchHit(
        search_unit_id=3,
        chunk_id=3,
        search_scope="row",
        score=0.8,
        backend_type="vector",
        metadata={"field_names": ["地区"], "row_identity_text": "南康 服务窗口"},
        **common_ids,
    )
    assert service._compute_metadata_bonus(
        kb=SimpleNamespace(type="table"),
        hit=table_projection_hit,
        query_characteristics=query_characteristics,
    ) > 0.0


@pytest.mark.asyncio
async def test_query_analysis_metadata_fields_can_fallback_to_kb_doc_custom_metadata() -> None:
    """未显式配置 metadata_fields 时，应从知识库文档元数据中兜底发现字段。"""

    rows = [
        ({"region": "南康", "brand": "ThinkPad", "nested": {"city": "赣州"}},),
        ({"region": "赣州", "brand": "ThinkPad", "nested": {"city": "南康"}},),
        ({"region": "南康", "product_line": ["T14", "X1 Carbon"]},),
    ]

    class _Session:
        async def execute(self, *_args, **_kwargs):
            return _ExecuteResult(rows)

    service = HybridRetrievalService.__new__(HybridRetrievalService)
    service.session = _Session()

    fields = await service._build_query_analysis_metadata_fields(
        kb=SimpleNamespace(id=uuid4(), tenant_id=uuid4(), type="general"),
        raw_config={},
    )

    field_map = {str(item.get("key")): item for item in fields}
    assert field_map["region"]["metadata_path"] == ["region"]
    assert field_map["region"]["target"] == "document_metadata"
    assert field_map["region"]["source"] == "runtime:kbd_custom_metadata"
    assert field_map["region"]["enum_values"] == ["南康", "赣州"]
    assert field_map["nested.city"]["metadata_path"] == ["nested", "city"]
    assert field_map["product_line"]["enum_values"] == ["T14", "X1 Carbon"]


@pytest.mark.asyncio
async def test_rule_tag_matching_only_uses_tags_still_bound_in_kb() -> None:
    """规则标签候选应只匹配当前知识库里仍被资源使用中的标签。"""

    class _Session:
        async def execute(self, stmt, *_args, **_kwargs):
            compiled = str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": False},
                )
            )
            assert "EXISTS" in compiled
            assert "resource_tags" in compiled
            return _ExecuteResult([])

    service = QueryAnalysisService.__new__(QueryAnalysisService)
    service.session = _Session()

    result = await service._match_tags(
        tenant_id=uuid4(),
        kb_id=uuid4(),
        query="南康地区政策",
        allowed_target_type="kb_doc",
    )

    assert result == []


@pytest.mark.asyncio
async def test_query_rewrite_runs_before_synonym_rewrite() -> None:
    """查询改写应先产出独立问题，再在其基础上做同义词改写。"""

    service = QueryAnalysisService.__new__(QueryAnalysisService)
    service.session = SimpleNamespace()

    async def _rewrite_query_by_llm(**_kwargs):
        return "南康怎么办理", {"enabled": True, "status": "success"}

    async def _rewrite_query_by_synonyms(**kwargs):
        assert kwargs["query"] == "南康怎么办理"
        return "南康如何办理", []

    async def _resolve_glossary_entries(**_kwargs):
        return []

    async def _build_resolved_filter_labels(**_kwargs):
        return {}

    service._rewrite_query_by_llm = _rewrite_query_by_llm  # type: ignore[method-assign]
    service._rewrite_query_by_synonyms = _rewrite_query_by_synonyms  # type: ignore[method-assign]
    service._resolve_glossary_entries = _resolve_glossary_entries  # type: ignore[method-assign]
    service._build_resolved_filter_labels = _build_resolved_filter_labels  # type: ignore[method-assign]
    service._clone_filters = QueryAnalysisService._clone_filters.__get__(service, QueryAnalysisService)
    service._apply_retrieval_lexicon = QueryAnalysisService._apply_retrieval_lexicon.__get__(service, QueryAnalysisService)
    service._normalize_retrieval_stopwords = QueryAnalysisService._normalize_retrieval_stopwords.__get__(service, QueryAnalysisService)
    service._build_lexical_query = QueryAnalysisService._build_lexical_query.__get__(service, QueryAnalysisService)
    service._collect_ignored_lexical_terms = QueryAnalysisService._collect_ignored_lexical_terms.__get__(service, QueryAnalysisService)
    service._build_priority_lexical_hints = QueryAnalysisService._build_priority_lexical_hints.__get__(service, QueryAnalysisService)
    service._build_auto_filter_signals = QueryAnalysisService._build_auto_filter_signals.__get__(service, QueryAnalysisService)

    analyzed = await service.analyze(
        current_user=SimpleNamespace(tenant_id=uuid4()),
        kb=SimpleNamespace(id=uuid4(), type="general"),
        query="这个怎么办理",
        filters=RetrievalFilterSet(),
        config=QueryAnalysisConfig(enable_query_rewrite=True, enable_synonym_rewrite=True),
    )

    assert analyzed.standalone_query == "南康怎么办理"
    assert analyzed.rewritten_query == "南康如何办理"
    assert analyzed.query_rewrite_debug["status"] == "success"


def test_query_rewrite_folder_routing_disabled_when_only_root_folder() -> None:
    """只有根目录时，不应启用目录建议。"""

    service = QueryAnalysisService.__new__(QueryAnalysisService)

    assert service._has_meaningful_folder_hierarchy(
        [
            {
                "id": str(uuid4()),
                "name": "根目录",
                "path": "根目录",
            }
        ]
    ) is False


def test_auto_tag_candidates_do_not_become_hard_filters() -> None:
    """自动标签候选只产生加权信号，不应写入硬过滤集合。"""

    service = QueryAnalysisService.__new__(QueryAnalysisService)
    tag_id = uuid4()
    folder_tag_id = uuid4()
    filters = RetrievalFilterSet()
    candidates = [
        QueryAnalysisFilterCandidate(
            filter_type="tag_id",
            filter_value="南康",
            target_id=tag_id,
            confidence=0.95,
            source="tag_name",
            layer="rule",
            validation_status="validated",
        ),
        QueryAnalysisFilterCandidate(
            filter_type="folder_tag_id",
            filter_value="政务",
            target_id=folder_tag_id,
            confidence=0.95,
            source="tag_name",
            layer="rule",
            validation_status="validated",
        ),
    ]

    resolved = service._apply_filter_candidates(filters=filters, candidates=candidates)
    signals = service._build_auto_filter_signals(candidates=candidates, metadata_fields=[])

    assert resolved.tag_ids == []
    assert resolved.folder_tag_ids == []
    assert [signal.signal_type for signal in signals] == ["doc_tag", "folder_tag"]
    assert all(signal.usage == "tag_boost" for signal in signals)


def test_hybrid_llm_can_correct_rule_tag_candidate() -> None:
    """hybrid 模式下，高置信 LLM 候选可以纠偏同目标规则候选。"""

    service = QueryAnalysisService.__new__(QueryAnalysisService)
    rule_candidates = [
        QueryAnalysisFilterCandidate(
            filter_type="tag_id",
            filter_value="南康",
            target_id="tag-1",
            confidence=0.95,
            source="rule",
            layer="rule",
            validation_status="validated",
        )
    ]
    llm_candidates = [
        QueryAnalysisFilterCandidate(
            filter_type="tag_id",
            filter_value="赣州",
            target_id="tag-1",
            confidence=0.9,
            source="llm",
            layer="llm",
            validation_status="validated",
        )
    ]

    reconciled = service._reconcile_rule_candidates_with_llm(
        rule_candidates=rule_candidates,
        llm_candidates=llm_candidates,
        correction_confidence_threshold=0.82,
    )

    assert reconciled[0].validation_status == "corrected_by_llm"
    assert "赣州" in str(reconciled[0].validation_reason or "")


def test_merge_filter_expressions_uses_and_append() -> None:
    """显式表达式与 LLM 表达式合并时，应以 AND 追加方式收紧。"""

    service = QueryAnalysisService.__new__(QueryAnalysisService)
    merged = service._merge_filter_expressions(
        locked_expression={"field": "tag", "op": "in", "values": ["tag-1"]},
        additive_expression={"field": "metadata", "path": ["region"], "op": "in", "values": ["南康"]},
    )

    assert merged == {
        "op": "and",
        "items": [
            {"field": "tag", "op": "in", "path": [], "values": ["tag-1"]},
            {"field": "metadata", "op": "in", "path": ["region"], "values": ["南康"]},
        ],
    }


def test_auto_document_metadata_signals_merge_same_key_as_or() -> None:
    """自动元数据多个 key 为 AND，同 key 多值在解析阶段合并为 OR 值列表。"""

    service = QueryAnalysisService.__new__(QueryAnalysisService)
    hybrid = HybridRetrievalService.__new__(HybridRetrievalService)
    candidates = [
        QueryAnalysisFilterCandidate(
            filter_type="document_metadata",
            filter_value="南康",
            target_id="region",
            confidence=0.86,
            source="llm:地区",
            layer="llm",
            validation_status="validated",
        ),
        QueryAnalysisFilterCandidate(
            filter_type="document_metadata",
            filter_value="赣州",
            target_id="region",
            confidence=0.84,
            source="llm:地区",
            layer="llm",
            validation_status="validated",
        ),
        QueryAnalysisFilterCandidate(
            filter_type="document_metadata",
            filter_value="2024",
            target_id="year",
            confidence=0.84,
            source="llm:年份",
            layer="llm",
            validation_status="validated",
        ),
    ]
    metadata_fields = [
        {
            "key": "地区",
            "target": "document_metadata",
            "metadata_path": ["region"],
            "match_mode": "match_or_missing",
            "options": ["南康", "赣州"],
        },
        {"key": "year", "target": "document_metadata", "match_mode": "match_only", "options": ["2024"]},
    ]

    signals = service._build_auto_filter_signals(candidates=candidates, metadata_fields=metadata_fields)
    merged = hybrid._collect_auto_document_metadata_filters(signals)

    assert merged["region"]["match_mode"] == "match_or_missing"
    assert merged["region"]["values"] == ["南康", "赣州"]
    assert merged["year"]["match_mode"] == "match_only"
    assert merged["year"]["values"] == ["2024"]


def test_auto_tag_boost_respects_semantic_floor() -> None:
    """自动标签加分必须受语义地板控制，不能救活弱语义命中。"""

    service = HybridRetrievalService.__new__(HybridRetrievalService)

    weak_boost = service._compute_effective_auto_tag_boost(
        vector_score=0.1,
        keyword_score=0.0,
        vector_weight=0.55,
        lexical_weight=0.45,
        scope_weight=1.0,
        auto_tag_boost=0.1,
    )
    partial_boost = service._compute_effective_auto_tag_boost(
        vector_score=0.5,
        keyword_score=0.0,
        vector_weight=0.55,
        lexical_weight=0.45,
        scope_weight=1.0,
        auto_tag_boost=0.1,
    )
    full_boost = service._compute_effective_auto_tag_boost(
        vector_score=0.7,
        keyword_score=0.0,
        vector_weight=0.55,
        lexical_weight=0.45,
        scope_weight=1.0,
        auto_tag_boost=0.1,
    )

    assert weak_boost == 0.0
    assert partial_boost == 0.05
    assert full_boost == 0.1


@pytest.mark.asyncio
async def test_llm_candidate_mode_can_apply_validated_filter_expression() -> None:
    """llm_candidate 模式也应支持 LLM 受控表达式落地。"""

    service = QueryAnalysisService.__new__(QueryAnalysisService)
    service._apply_retrieval_lexicon = lambda query, retrieval_lexicon: (query, [])
    service._normalize_retrieval_stopwords = lambda _stopwords: []
    service._build_auto_filter_signals = lambda candidates, metadata_fields: []
    service._build_lexical_query = lambda **kwargs: kwargs["rewritten_query"]
    service._collect_ignored_lexical_terms = lambda **_kwargs: []
    service._build_priority_lexical_hints = lambda **_kwargs: ([], [], {})
    service._validate_llm_candidates = lambda **kwargs: kwargs["candidates"]
    service._build_llm_candidate_metrics = lambda **_kwargs: {}

    async def _extract_llm_filter_candidates(**_kwargs):
        return [], {"filter_expression": {"field": "metadata", "op": "in", "path": ["region"], "values": ["南康"]}}

    async def _resolve_glossary_entries(**_kwargs):
        return []

    async def _build_resolved_filter_labels(**_kwargs):
        return {}

    service._extract_llm_filter_candidates = _extract_llm_filter_candidates  # type: ignore[method-assign]
    service._resolve_glossary_entries = _resolve_glossary_entries  # type: ignore[method-assign]
    service._build_resolved_filter_labels = _build_resolved_filter_labels  # type: ignore[method-assign]

    analyzed = await service.analyze(
        current_user=SimpleNamespace(tenant_id=uuid4()),
        kb=SimpleNamespace(id=uuid4()),
        query="南康维修点",
        filters=RetrievalFilterSet(),
        config=SimpleNamespace(
            enable_synonym_rewrite=False,
            auto_filter_mode="llm_candidate",
            max_glossary_terms=8,
            metadata_fields=[],
            retrieval_lexicon=[],
            retrieval_stopwords=[],
            enable_llm_candidate_extraction=True,
            enable_llm_filter_expression=True,
            llm_candidate_min_confidence=0.55,
            llm_upgrade_confidence_threshold=0.82,
            llm_max_upgrade_count=2,
        ),
    )

    assert analyzed.retrieval_filters.filter_expression == {
        "field": "metadata",
        "op": "in",
        "path": ["region"],
        "values": ["南康"],
    }
    assert analyzed.llm_debug["filter_expression_applied"] is True


def test_filter_expression_normalizes_nested_or_and_not_in() -> None:
    """过滤表达式应保留括号语义和 not_in 操作符。"""

    expression = normalize_filter_expression(
        {
            "op": "and",
            "items": [
                {"field": "metadata", "path": "region", "op": "in", "values": ["南康", "赣州"]},
                {
                    "op": "or",
                    "items": [
                        {"field": "tag", "op": "not_in", "values": ["tag-1"]},
                        {"field": "search_unit_metadata", "path": ["qa_fields", "category"], "op": "eq", "value": "维修"},
                    ],
                },
            ],
        }
    )

    assert expression["op"] == "and"
    assert expression["items"][1]["op"] == "or"
    assert expression["items"][1]["items"][0]["op"] == "not_in"
    assert filter_expression_has_field(expression, {"metadata"})
    assert filter_expression_has_field(expression, {"search_unit_metadata"})


def test_jsonb_expression_sql_uses_not_in_expanding_param() -> None:
    """search unit 元数据表达式应真正生成 NOT IN SQL 条件。"""

    params: dict[str, object] = {}
    sql = build_jsonb_expression_sql(
        expression={
            "op": "and",
            "items": [
                {"field": "metadata", "path": ["region"], "op": "not_in", "values": ["赣州"]},
                {"field": "search_unit_metadata", "path": ["qa_fields", "category"], "op": "eq", "values": ["维修"]},
            ],
        },
        json_column="su.metadata",
        params=params,
        prefix="su_expr",
    )

    assert "NOT IN :su_expr_values_" in sql
    assert "= :su_expr_value_" in sql
    assert collect_expanding_param_names(sql, "su_expr") == ["su_expr_values_2"]
    assert params["su_expr_values_2"] == ["赣州"]


def test_search_unit_expression_sql_uses_kbd_metadata_column() -> None:
    """文档元数据表达式在召回 SQL 中必须落到 knowledge_base_documents.metadata。"""

    params: dict[str, object] = {}
    sql = build_search_unit_expression_sql(
        expression={"field": "metadata", "path": ["地区"], "op": "eq", "values": ["南康"]},
        params=params,
        prefix="su_expr",
    )

    assert "kbd.metadata #>>" in sql
    assert "kbd.custom_metadata" not in sql


def test_llm_filter_expression_is_constrained_to_declared_fields() -> None:
    """LLM 表达式只能保留声明过的字段与候选 ID。"""

    service = QueryAnalysisService.__new__(QueryAnalysisService)
    expression = service._normalize_llm_filter_expression(
        {
            "op": "or",
            "items": [
                {"field": "metadata", "path": ["region"], "op": "in", "values": ["南康", "未知地区"]},
                {"field": "metadata", "path": ["secret"], "op": "in", "values": ["x"]},
                {"field": "tag", "op": "in", "values": ["tag-1", "fake-tag"]},
            ],
        },
        folders=[],
        doc_tags=[{"id": "tag-1", "name": "品牌"}],
        folder_tags=[],
        metadata_fields=[
            {
                "key": "地区",
                "target": "document_metadata",
                "metadata_path": "region",
                "options": [{"value": "南康", "label": "南康"}],
            }
        ],
    )

    assert expression == {
        "op": "or",
        "items": [
            {"field": "metadata", "op": "in", "path": ["region"], "values": ["南康"]},
            {"field": "tag", "op": "in", "path": [], "values": ["tag-1"]},
        ],
    }
