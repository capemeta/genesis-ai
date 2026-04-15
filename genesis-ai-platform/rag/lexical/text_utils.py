"""
全文检索文本优化工具兼容入口。

新代码优先使用 `rag.lexical.analysis` 下的分析器与适配器；本文件保留旧函数名，
避免调用方在 PG -> Qdrant / Milvus 迁移前发生大面积 import 变更。
"""

from __future__ import annotations

from typing import Any, cast

from rag.lexical.analysis import (
    build_lexical_index_text as _build_lexical_index_text,
    build_pg_fts_query_payload as _build_pg_fts_query_payload,
    extract_ascii_terms,
    extract_cjk_fallback_terms,
    normalize_lexical_text,
)

__all__ = [
    "build_lexical_index_text",
    "build_pg_fts_query_payload",
    "extract_ascii_terms",
    "extract_cjk_terms",
    "normalize_lexical_text",
]


def extract_cjk_terms(text: str) -> list[str]:
    """提取中文 fallback 词项。

    兼容旧调试字段命名；现在这些词项语义上是低权重兜底 ngram，不是专业中文分词。
    """

    terms, _ignored_terms = extract_cjk_fallback_terms(text)
    return cast(list[str], terms)


def build_lexical_index_text(
    text: str,
    *,
    priority_terms: list[str] | None = None,
    priority_phrases: list[str] | None = None,
    synonym_terms: list[str] | None = None,
    glossary_terms: list[str] | None = None,
    retrieval_stopwords: list[str] | None = None,
) -> str:
    """构建更适合全文后端索引的文本。"""

    return cast(str, _build_lexical_index_text(
        text,
        priority_terms=priority_terms,
        priority_phrases=priority_phrases,
        synonym_terms=synonym_terms,
        glossary_terms=glossary_terms,
        retrieval_stopwords=retrieval_stopwords,
    ))


def build_pg_fts_query_payload(
    query: str,
    *,
    priority_terms: list[str] | None = None,
    priority_phrases: list[str] | None = None,
    synonym_terms: list[str] | None = None,
    glossary_terms: list[str] | None = None,
    retrieval_stopwords: list[str] | None = None,
    lexicon_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """构建 PostgreSQL FTS 查询载荷。"""

    return cast(dict[str, Any], _build_pg_fts_query_payload(
        query,
        priority_terms=priority_terms,
        priority_phrases=priority_phrases,
        synonym_terms=synonym_terms,
        glossary_terms=glossary_terms,
        retrieval_stopwords=retrieval_stopwords,
        lexicon_weights=lexicon_weights,
    ))
