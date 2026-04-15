"""
全文检索分析器测试。
"""

from pathlib import Path
import sys


# 兼容直接执行本文件：python tests/rag/test_lexical_analysis.py
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from rag.lexical.analysis.stopwords import filter_exact_stopword_terms
from rag.lexical.analysis.scoring import normalize_lexical_score
from rag.lexical.text_utils import build_lexical_index_text, build_pg_fts_query_payload, normalize_lexical_text


def test_pg_fts_payload_splits_high_confidence_and_fallback_terms() -> None:
    """jieba 主词项应替代 noisy bigram 成为高置信词项。"""

    payload = build_pg_fts_query_payload("如何上传剪映空间")

    assert payload["debug"]["analyzer"] == "jieba"
    assert payload["debug"]["jieba_terms"] == ["如何", "上传", "剪映", "空间"]
    assert payload["loose_query_text"] == "如何上传剪映空间 | 如何 | 上传 | 剪映 | 空间"
    assert payload["fallback_query_text"] == ""
    assert payload["debug"]["fallback_terms"] == []


def test_pg_fts_payload_uses_stopwords_to_reduce_cjk_fallback_noise() -> None:
    """停用词应下沉到 jieba 和 fallback 层，过滤低价值片段。"""

    payload = build_pg_fts_query_payload("如何上传剪映空间", retrieval_stopwords=["如何"])

    assert payload["debug"]["loose_terms"][0] == "如何上传剪映空间"
    assert "如何" not in payload["debug"]["jieba_terms"]
    assert payload["debug"]["stopword_hits"] == ["如何"]
    assert "如何" not in payload["debug"]["loose_terms"][1:]
    assert "何上" not in payload["fallback_query_text"]
    assert "上传" in payload["debug"]["jieba_terms"]
    assert "如何" in payload["debug"]["ignored_terms"]


def test_pg_fts_payload_keeps_to_tsquery_operands_valid_for_spaced_terms() -> None:
    """含空格的高置信词项应转换成合法的 to_tsquery 操作数。"""

    payload = build_pg_fts_query_payload("open ai 上传")

    assert "open & ai & 上传" in payload["loose_query_text"]
    assert "open ai 上传" in payload["debug"]["loose_terms"]


def test_normalize_lexical_text_removes_cjk_punctuation() -> None:
    """中文标点应被归一为空白，避免完整短语匹配被问号破坏。"""

    assert normalize_lexical_text("如何使用剪映素材库中的素材？") == "如何使用剪映素材库中的素材"


def test_pg_fts_payload_prioritizes_original_query_phrase() -> None:
    """原始问句短语应优先进入结构化短语加分。"""

    payload = build_pg_fts_query_payload(
        "使用剪映素材库中 素材",
        priority_phrases=["如何使用剪映素材库中的素材？", "使用剪映素材库中 素材"],
    )

    assert payload["priority_phrase_weights"][0]["pattern"] == "%如何使用剪映素材库中的素材%"
    assert payload["priority_phrase_weights"][1]["pattern"] == "%使用剪映素材库中 素材%"


def test_priority_query_phrase_does_not_hide_jieba_subterms() -> None:
    """原始整句用于短语补分，但不应注册成 jieba 自定义词压住子词。"""

    payload = build_pg_fts_query_payload(
        "如何使用剪映素材库中的素材？",
        priority_phrases=["如何使用剪映素材库中的素材？"],
    )

    assert payload["priority_phrase_weights"][0]["pattern"] == "%如何使用剪映素材库中的素材%"
    assert "剪映" in payload["debug"]["jieba_terms"]
    assert "素材库" in payload["debug"]["jieba_terms"]
    assert "如何使用剪映素材库中的素材" not in payload["debug"]["custom_words"]


def test_query_analysis_stopwords_do_not_rewrite_inside_sentence() -> None:
    """查询分析层不应在整句内部按子串删除停用词，避免破坏原始短语。"""

    filtered = filter_exact_stopword_terms(
        terms=["如何使用剪映素材库中的素材"],
        stopwords=["如", "何", "的"],
    )

    assert filtered == ["如何使用剪映素材库中的素材"]


def test_pg_fts_payload_reports_single_character_stopword_hits() -> None:
    """查询诊断应展示真实命中的单字停用词。"""

    payload = build_pg_fts_query_payload("如何使用剪映素材库中的素材？")

    assert {"如", "何", "的"}.issubset(set(payload["debug"]["stopword_hits"]))
    assert payload["debug"]["ignored_terms"] == []


def test_lexical_index_text_only_adds_matched_dictionary_terms() -> None:
    """索引文本支持词典项，但应由调用方只传入当前文本命中的词项。"""

    index_text = build_lexical_index_text("剪映空间上传入口", priority_terms=["剪映空间"])

    assert "剪映空间" in index_text
    assert "剪映" in index_text
    assert "上传" in index_text


def test_lexical_index_text_does_not_default_to_synonym_dictionary() -> None:
    """索引侧不应把同义词组默认写入正文索引词典。"""

    index_text = build_lexical_index_text("剪映空间上传入口")

    assert "剪映云空间" not in index_text


def test_pg_fts_payload_uses_synonym_terms_only_as_query_expansion() -> None:
    """查询侧命中同义词后仍可限量扩展 synonym_terms。"""

    payload = build_pg_fts_query_payload("剪映空间怎么上传", synonym_terms=["剪映云空间"])

    assert "剪映云空间" in payload["debug"]["synonym_terms"]
    assert "剪映云空间" in payload["loose_query_text"]


def test_pg_fts_score_normalization_is_bounded_and_monotonic() -> None:
    """PG FTS 原始分应归一化展示，避免裸加和分超过 1。"""

    assert normalize_lexical_score(0.0) == 0.0
    assert normalize_lexical_score(1.5) == 0.6522
    assert normalize_lexical_score(3.0) > normalize_lexical_score(1.5)
    assert normalize_lexical_score(1_000.0) <= 1.0


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
