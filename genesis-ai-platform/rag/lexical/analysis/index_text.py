"""
全文检索索引文本构建适配器。
"""

from __future__ import annotations

from rag.lexical.analysis.factory import get_default_lexical_analyzer
from rag.lexical.analysis.types import LexicalAnalyzerInput


def build_lexical_index_text(
    text: str,
    *,
    priority_terms: list[str] | None = None,
    priority_phrases: list[str] | None = None,
    synonym_terms: list[str] | None = None,
    glossary_terms: list[str] | None = None,
    retrieval_stopwords: list[str] | None = None,
) -> str:
    """构建后端无关的全文索引文本。"""

    analysis = get_default_lexical_analyzer().analyze(
        LexicalAnalyzerInput(
            text=text,
            mode="index",
            priority_terms=list(priority_terms or []),
            priority_phrases=list(priority_phrases or []),
            synonym_terms=list(synonym_terms or []),
            glossary_terms=list(glossary_terms or []),
            retrieval_stopwords=list(retrieval_stopwords or []),
        )
    )
    if not analysis.normalized_text:
        return ""

    parts = [analysis.normalized_text]
    for token in analysis.ordered_tokens(include_fallback=True):
        if token.text not in parts:
            parts.append(token.text)
    return " ".join(parts)
