"""
PostgreSQL FTS 查询载荷适配器。
"""

from __future__ import annotations

from typing import Any

from rag.lexical.analysis.factory import get_default_lexical_analyzer
from rag.lexical.analysis.types import LexicalAnalyzerInput, LexicalToken


def _to_tsquery_operand(text: str) -> str:
    """将单个高置信词项转换成 `to_tsquery` 可消费的操作数。"""

    parts = [item.strip() for item in str(text or "").split() if item.strip()]
    return " & ".join(parts)


def _join_tsquery_or(tokens: list[LexicalToken]) -> str:
    """用 OR 拼接 `to_tsquery` 操作数，跳过空词项。"""

    operands = [_to_tsquery_operand(token.text) for token in tokens]
    return " | ".join(item for item in operands if item).strip()


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

    weights = dict(lexicon_weights or {})
    analysis = get_default_lexical_analyzer().analyze(
        LexicalAnalyzerInput(
            text=query,
            mode="query",
            priority_terms=list(priority_terms or []),
            priority_phrases=list(priority_phrases or []),
            synonym_terms=list(synonym_terms or []),
            glossary_terms=list(glossary_terms or []),
            retrieval_stopwords=list(retrieval_stopwords or []),
        )
    )
    normalized = analysis.normalized_text
    if not normalized:
        return {
            "normalized_query": "",
            "strict_query_text": "",
            "loose_query_text": "",
            "fallback_query_text": "",
            "phrase_pattern": None,
            "priority_term_pattern": None,
            "priority_phrase_pattern": None,
            "priority_term_weights": [],
            "priority_phrase_weights": [],
            "debug": {},
        }

    strict_tokens = analysis.ordered_tokens(include_fallback=False)
    fallback_tokens = analysis.fallback_ngrams
    loose_tokens = analysis.ordered_tokens(include_fallback=False)
    priority_term_tokens = [
        item
        for item in [*analysis.terms, *analysis.aliases]
        if item.source in {"priority_term", "glossary", "synonym"}
    ]
    priority_phrase_tokens = [
        *[item for item in analysis.phrases if item.source == "priority_phrase"],
        *[item for item in analysis.phrases if item.source != "priority_phrase"],
    ]

    priority_term_weights = [
        {"pattern": f"%{item.text}%", "weight": weights.get(item.text, 1.0)}
        for item in priority_term_tokens[:3]
    ]
    priority_phrase_weights = [
        {"pattern": f"%{item.text}%", "weight": weights.get(item.text, 1.0)}
        for item in priority_phrase_tokens[:3]
    ]

    return {
        "normalized_query": normalized,
        "strict_query_text": " ".join(token.text for token in strict_tokens).strip(),
        "loose_query_text": _join_tsquery_or(loose_tokens),
        "fallback_query_text": _join_tsquery_or(fallback_tokens),
        "phrase_pattern": f"%{normalized}%" if len(normalized) >= 2 else None,
        "priority_term_pattern": priority_term_weights[0]["pattern"] if priority_term_weights else None,
        "priority_phrase_pattern": priority_phrase_weights[0]["pattern"] if priority_phrase_weights else None,
        "priority_term_weights": priority_term_weights,
        "priority_phrase_weights": priority_phrase_weights,
        "debug": {
            **analysis.debug,
            "cjk_terms": [token.text for token in analysis.fallback_ngrams],
            "strict_terms": [token.text for token in strict_tokens],
            "loose_terms": [token.text for token in loose_tokens],
            "fallback_terms": [token.text for token in fallback_tokens],
            "has_phrase_pattern": len(normalized) >= 2,
            "priority_term_weights": priority_term_weights,
            "priority_phrase_weights": priority_phrase_weights,
        },
    }
