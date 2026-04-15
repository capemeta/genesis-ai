"""
全文检索分析器类型定义。

这些类型不绑定 PostgreSQL / Qdrant / Milvus，目的是把“如何切词与扩展”
从具体检索后端中拆出来，便于后续统一迁移全文检索引擎。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


LexicalTermKind = Literal["phrase", "term", "alias", "fallback_ngram"]
LexicalAnalyzeMode = Literal["index", "query"]


@dataclass(slots=True)
class LexicalAnalyzerInput:
    """全文分析器输入。"""

    text: str
    mode: LexicalAnalyzeMode
    priority_terms: list[str] = field(default_factory=list)
    priority_phrases: list[str] = field(default_factory=list)
    synonym_terms: list[str] = field(default_factory=list)
    glossary_terms: list[str] = field(default_factory=list)
    retrieval_stopwords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LexicalToken:
    """全文检索词项。"""

    text: str
    kind: LexicalTermKind
    weight: float = 1.0
    source: str = "rule"


@dataclass(slots=True)
class LexicalAnalysisResult:
    """全文分析器输出。"""

    normalized_text: str
    phrases: list[LexicalToken] = field(default_factory=list)
    terms: list[LexicalToken] = field(default_factory=list)
    aliases: list[LexicalToken] = field(default_factory=list)
    fallback_ngrams: list[LexicalToken] = field(default_factory=list)
    ignored_terms: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)

    def ordered_tokens(self, *, include_fallback: bool = True) -> list[LexicalToken]:
        """按后端消费优先级返回去重后的 token。"""

        tokens = [*self.phrases, *self.terms, *self.aliases]
        if include_fallback:
            tokens.extend(self.fallback_ngrams)

        deduped: list[LexicalToken] = []
        seen: set[str] = set()
        for token in tokens:
            normalized = str(token.text or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(token)
        return deduped

