"""
规则型中文全文检索分析器。

当前默认分析器已切换为 `JiebaLexicalAnalyzer`；本模块保留规范化、ASCII 抽取、
CJK fallback ngram 与规则型 analyzer，供兼容入口、兜底策略和后续对照测试使用。
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from rag.lexical.analysis.base import LexicalAnalyzer
from rag.lexical.analysis.stopwords import merge_stopwords
from rag.lexical.analysis.types import LexicalAnalysisResult, LexicalAnalyzerInput, LexicalToken

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_ASCII_TERM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:-]*")
_LEXICAL_PUNCTUATION = "，。；：！？、（）【】《》“”‘’`~!@#$%^&*+=|\\/<>{}[],;:?\"'()"
_LEXICAL_PUNCT_TRANSLATION = str.maketrans({char: " " for char in _LEXICAL_PUNCTUATION})
_MAX_DEBUG_STOPWORDS = 80


def normalize_lexical_text(text: str) -> str:
    """统一全文检索文本归一化口径。"""

    normalized = str(text or "").strip().lower()
    if not normalized:
        return ""
    normalized = re.sub(r"[\r\n\t]+", " ", normalized)
    normalized = normalized.translate(_LEXICAL_PUNCT_TRANSLATION)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_ascii_terms(text: str) -> list[str]:
    """提取英文、数字和混合术语。"""

    normalized = normalize_lexical_text(text)
    if not normalized:
        return []

    terms: list[str] = []
    for match in _ASCII_TERM_RE.finditer(normalized):
        term = match.group(0).strip(".:/-_")
        if len(term) < 2:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def extract_cjk_fallback_terms(text: str, *, stopwords: Iterable[str] = ()) -> tuple[list[str], list[str]]:
    """提取中文连续片段及二字 fallback ngram，并记录被忽略词。"""

    normalized = normalize_lexical_text(text)
    normalized_stopwords = [normalize_lexical_text(item) for item in stopwords if normalize_lexical_text(item)]
    stopword_set = set(normalized_stopwords)
    if not normalized:
        return [], []

    terms: list[str] = []
    ignored_terms: list[str] = []
    for match in _CJK_RE.finditer(normalized):
        chunk = match.group(0).strip()
        if len(chunk) < 2:
            continue
        stopword_spans: list[tuple[int, int]] = []
        for stopword in normalized_stopwords:
            start = chunk.find(stopword)
            while start >= 0:
                stopword_spans.append((start, start + len(stopword)))
                start = chunk.find(stopword, start + 1)
        if chunk not in stopword_set and chunk not in terms:
            terms.append(chunk)
        elif chunk not in ignored_terms:
            ignored_terms.append(chunk)
        if len(chunk) == 2:
            continue
        for index in range(len(chunk) - 1):
            gram = chunk[index : index + 2]
            gram_span = (index, index + 2)
            overlaps_stopword = any(gram_span[0] < span[1] and gram_span[1] > span[0] for span in stopword_spans)
            if gram in stopword_set or overlaps_stopword:
                # 只记录真实停用词；因单字停用词重叠而被压制的 fallback bigram 不进入诊断。
                if gram in stopword_set and gram not in ignored_terms:
                    ignored_terms.append(gram)
                continue
            if gram not in terms:
                terms.append(gram)
    return terms, ignored_terms


def _append_unique_token(tokens: list[LexicalToken], token: LexicalToken) -> None:
    """按文本去重追加 token，避免同一词项反复污染检索串。"""

    normalized = normalize_lexical_text(token.text)
    if not normalized:
        return
    if any(item.text == normalized for item in tokens):
        return
    tokens.append(
        LexicalToken(
            text=normalized,
            kind=token.kind,
            weight=token.weight,
            source=token.source,
        )
    )


def _build_stopword_debug(stopwords: list[str]) -> dict[str, object]:
    """调试输出只保留停用词预览，避免大词表撑大检索 payload。"""

    unique_stopwords = sorted(dict.fromkeys(stopwords))
    return {
        "stopword_count": len(unique_stopwords),
        "stopwords": unique_stopwords[:_MAX_DEBUG_STOPWORDS],
    }


def _collect_stopword_hits(normalized_text: str, stopwords: list[str]) -> list[str]:
    """收集本次文本中实际触发的停用词。"""

    unique_stopwords = sorted(dict.fromkeys(stopwords), key=lambda item: (-len(item), item))
    hits: list[str] = []
    occupied_spans: list[tuple[int, int]] = []
    for stopword in unique_stopwords:
        start = normalized_text.find(stopword)
        while start >= 0:
            span = (start, start + len(stopword))
            overlaps = any(span[0] < item[1] and span[1] > item[0] for item in occupied_spans)
            if not overlaps:
                hits.append(stopword)
                occupied_spans.append(span)
                break
            start = normalized_text.find(stopword, start + 1)
        if len(hits) >= _MAX_DEBUG_STOPWORDS:
            break
    return hits


class RuleBasedLexicalAnalyzer(LexicalAnalyzer):
    """规则型全文检索分析器。"""

    analyzer_type = "rule_based"

    def analyze(self, payload: LexicalAnalyzerInput) -> LexicalAnalysisResult:
        """执行规则型全文检索分析。"""

        normalized = normalize_lexical_text(payload.text)
        if not normalized:
            return LexicalAnalysisResult(normalized_text="", debug={"analyzer": self.analyzer_type})

        stopwords = [
            normalize_lexical_text(item)
            for item in merge_stopwords(payload.mode, payload.retrieval_stopwords)
            if normalize_lexical_text(item)
        ]
        phrases: list[LexicalToken] = []
        terms: list[LexicalToken] = []
        aliases: list[LexicalToken] = []

        # 业务短语、同义词和专业术语优先级高于 fallback ngram，后端可据此单独加权。
        if len(normalized) >= 2:
            _append_unique_token(phrases, LexicalToken(normalized, "phrase", 1.0, "normalized_text"))
        for item in payload.priority_phrases:
            _append_unique_token(phrases, LexicalToken(item, "phrase", 1.18, "priority_phrase"))
        for item in payload.priority_terms:
            _append_unique_token(terms, LexicalToken(item, "term", 1.1, "priority_term"))
        for item in payload.glossary_terms:
            _append_unique_token(terms, LexicalToken(item, "term", 1.04, "glossary"))
        for item in payload.synonym_terms:
            _append_unique_token(aliases, LexicalToken(item, "alias", 1.02, "synonym"))
        for item in extract_ascii_terms(normalized):
            _append_unique_token(terms, LexicalToken(item, "term", 1.0, "ascii"))

        fallback_terms, ignored_terms = extract_cjk_fallback_terms(normalized, stopwords=stopwords)
        fallback_tokens: list[LexicalToken] = []
        high_priority_texts = {token.text for token in [*phrases, *terms, *aliases]}
        for item in fallback_terms:
            if item in high_priority_texts:
                continue
            _append_unique_token(fallback_tokens, LexicalToken(item, "fallback_ngram", 0.35, "cjk_fallback"))

        return LexicalAnalysisResult(
            normalized_text=normalized,
            phrases=phrases,
            terms=terms,
            aliases=aliases,
            fallback_ngrams=fallback_tokens,
            ignored_terms=list(dict.fromkeys(ignored_terms)),
            debug={
                "analyzer": self.analyzer_type,
                "normalized_query": normalized,
                "ascii_terms": extract_ascii_terms(normalized),
                "cjk_fallback_terms": [token.text for token in fallback_tokens],
                "priority_terms": [token.text for token in terms if token.source in {"priority_term", "glossary"}],
                "priority_phrases": [token.text for token in phrases if token.source == "priority_phrase"],
                "synonym_terms": [token.text for token in aliases],
                "ignored_terms": list(dict.fromkeys(ignored_terms)),
                "stopword_hits": _collect_stopword_hits(normalized, stopwords),
            }
            | _build_stopword_debug(stopwords),
        )
