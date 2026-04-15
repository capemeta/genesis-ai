"""
jieba 中文全文检索分析器。

设计目标：
- 索引侧和查询侧使用同一套中文分词逻辑
- 知识库检索词表、专业术语进入分词词典；同义词仅在查询命中后参与扩展
- 停用词在 analyzer 层过滤
- fallback bigram 仅保留为极低频兜底，默认不与 jieba 主词项竞争
"""

from __future__ import annotations

from threading import Lock

import jieba  # type: ignore[import-untyped]

from rag.lexical.analysis.base import LexicalAnalyzer
from rag.lexical.analysis.rule_based import (
    _append_unique_token,
    extract_ascii_terms,
    extract_cjk_fallback_terms,
    normalize_lexical_text,
)
from rag.lexical.analysis.stopwords import merge_stopwords
from rag.lexical.analysis.types import LexicalAnalysisResult, LexicalAnalyzerInput, LexicalToken

_MAX_CUSTOM_WORDS = 80
_MAX_REGISTERED_CUSTOM_WORDS = 10_000
_MAX_QUERY_TERMS = 48
_MAX_INDEX_TERMS = 256
_MAX_QUERY_FALLBACK_TERMS = 16
_MAX_INDEX_FALLBACK_TERMS = 80
_MAX_TERM_CHARS = 64
_MAX_DEBUG_STOPWORDS = 80
_CUSTOM_WORD_LOCK = Lock()
_REGISTERED_CUSTOM_WORDS: set[str] = set()


def _normalize_terms(items: list[str], *, limit: int | None = None) -> list[str]:
    """规范化词典项，保持稳定顺序去重。"""

    terms: list[str] = []
    for item in items:
        normalized = normalize_lexical_text(item)
        if len(normalized) < 2 or len(normalized) > _MAX_TERM_CHARS:
            continue
        if normalized not in terms:
            terms.append(normalized)
        if limit is not None and len(terms) >= limit:
            break
    return terms


def _normalize_stopword_terms(items: list[str]) -> list[str]:
    """规范化停用词，允许单字词用于阻断中文 fallback 片段。"""

    terms: list[str] = []
    for item in items:
        normalized = normalize_lexical_text(item)
        if not normalized or len(normalized) > _MAX_TERM_CHARS:
            continue
        if normalized not in terms:
            terms.append(normalized)
    return terms


def _ensure_custom_words(custom_words: tuple[str, ...]) -> tuple[str, ...]:
    """将动态业务词注册到进程级 jieba 词典，避免为每次查询复制完整词典。"""

    registered_now: list[str] = []
    with _CUSTOM_WORD_LOCK:
        if len(_REGISTERED_CUSTOM_WORDS) >= _MAX_REGISTERED_CUSTOM_WORDS:
            return tuple()
        for word in custom_words:
            if word in _REGISTERED_CUSTOM_WORDS:
                continue
            jieba.add_word(word, freq=20_000)
            _REGISTERED_CUSTOM_WORDS.add(word)
            registered_now.append(word)
            if len(_REGISTERED_CUSTOM_WORDS) >= _MAX_REGISTERED_CUSTOM_WORDS:
                break
    return tuple(registered_now)


def _append_debug_term(items: list[str], item: str, *, limit: int) -> None:
    """记录调试词项，并限制体积。"""

    if item not in items and len(items) < limit:
        items.append(item)


def _build_stopword_debug(stopwords: set[str]) -> dict[str, object]:
    """调试输出只保留停用词预览，避免大词表撑大检索 payload。"""

    return {
        "stopword_count": len(stopwords),
        "stopwords": sorted(stopwords)[:_MAX_DEBUG_STOPWORDS],
    }


def _collect_stopword_hits(normalized_text: str, stopwords: set[str]) -> list[str]:
    """收集本次文本中实际触发的停用词。"""

    hits: list[str] = []
    occupied_spans: list[tuple[int, int]] = []
    for stopword in sorted(stopwords, key=lambda item: (-len(item), item)):
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


def _term_limit(mode: str) -> int:
    """按索引 / 查询场景限制高置信词项数量。"""

    return _MAX_INDEX_TERMS if mode == "index" else _MAX_QUERY_TERMS


def _fallback_limit(mode: str) -> int:
    """按索引 / 查询场景限制 fallback 词项数量。"""

    return _MAX_INDEX_FALLBACK_TERMS if mode == "index" else _MAX_QUERY_FALLBACK_TERMS


class JiebaLexicalAnalyzer(LexicalAnalyzer):
    """基于 jieba 的中文全文检索分析器。"""

    analyzer_type = "jieba"

    def analyze(self, payload: LexicalAnalyzerInput) -> LexicalAnalysisResult:
        """执行 jieba 分词分析。"""

        normalized = normalize_lexical_text(payload.text)
        if not normalized:
            return LexicalAnalysisResult(normalized_text="", debug={"analyzer": self.analyzer_type})

        stopwords = set(_normalize_stopword_terms(merge_stopwords(payload.mode, payload.retrieval_stopwords)))
        priority_phrases = _normalize_terms(payload.priority_phrases)
        priority_terms = _normalize_terms(payload.priority_terms)
        synonym_terms = _normalize_terms(payload.synonym_terms)
        glossary_terms = _normalize_terms(payload.glossary_terms)
        custom_words = tuple(
            sorted(
                # priority_phrases 只用于短语补分，不注册成进程级 jieba 自定义词。
                # 业务词典、专业术语、同义词扩展应通过 priority_terms / glossary_terms / synonym_terms 进词典。
                ({*priority_terms, *synonym_terms, *glossary_terms} - stopwords),
                key=lambda item: (-len(item), item),
            )[:_MAX_CUSTOM_WORDS]
        )
        registered_custom_words = _ensure_custom_words(custom_words)
        max_terms = _term_limit(payload.mode)
        max_fallback_terms = _fallback_limit(payload.mode)

        phrases: list[LexicalToken] = []
        terms: list[LexicalToken] = []
        aliases: list[LexicalToken] = []
        ignored_terms: list[str] = []

        if len(normalized) >= 2:
            _append_unique_token(phrases, LexicalToken(normalized, "phrase", 1.0, "normalized_text"))
        for item in priority_phrases:
            if item in stopwords:
                continue
            _append_unique_token(phrases, LexicalToken(item, "phrase", 1.18, "priority_phrase"))
        for item in priority_terms:
            if item in stopwords or len(terms) >= max_terms:
                continue
            _append_unique_token(terms, LexicalToken(item, "term", 1.1, "priority_term"))
        for item in glossary_terms:
            if item in stopwords or len(terms) >= max_terms:
                continue
            _append_unique_token(terms, LexicalToken(item, "term", 1.04, "glossary"))
        for item in synonym_terms:
            if item in stopwords or len(aliases) >= max_terms:
                continue
            _append_unique_token(aliases, LexicalToken(item, "alias", 1.02, "synonym"))

        jieba_tokens = [*jieba.cut(normalized, HMM=True), *jieba.cut_for_search(normalized, HMM=True)]
        jieba_terms: list[str] = []
        for raw_token in jieba_tokens:
            token = normalize_lexical_text(str(raw_token or ""))
            if len(token) < 2 or len(token) > _MAX_TERM_CHARS:
                continue
            if token in stopwords:
                ignored_terms.append(token)
                continue

            if token not in jieba_terms:
                _append_debug_term(jieba_terms, token, limit=max_terms)
                # 分词器产出的词项，如果是业务自定义词，给予 1.0 权重；如果是系统默认分词，给予 0.94 权重
                score = 1.0 if token in custom_words else 0.94
                source = "custom_jieba" if token in custom_words else "jieba"
                _append_unique_token(terms, LexicalToken(token, "term", score, source))

            if len(terms) >= max_terms:
                break

        # 对自定义业务词进行内部子项拆分（例如“剪映空间”拆分成“剪映”、“空间”作为低优先级补充）
        for custom_word in custom_words:
            if len(terms) >= max_terms:
                break
            for raw_token in jieba.cut_for_search(custom_word, HMM=True):
                token = normalize_lexical_text(str(raw_token or ""))
                if len(token) < 2 or len(token) > _MAX_TERM_CHARS or token == custom_word or token in stopwords:
                    continue
                if token not in jieba_terms:
                    _append_debug_term(jieba_terms, token, limit=max_terms)
                    _append_unique_token(terms, LexicalToken(token, "term", 0.92, "custom_subterm"))
                if len(terms) >= max_terms:
                    break

        for item in extract_ascii_terms(normalized):
            if item not in stopwords:
                _append_unique_token(terms, LexicalToken(item, "term", 1.0, "ascii"))
            if len(terms) >= max_terms:
                break

        fallback_raw_terms, fallback_ignored_terms = extract_cjk_fallback_terms(normalized, stopwords=stopwords)
        ignored_terms.extend(fallback_ignored_terms)
        high_confidence_texts = {token.text for token in [*phrases, *terms, *aliases]}
        fallback_tokens: list[LexicalToken] = []
        for item in fallback_raw_terms:
            # jieba 已经覆盖的词项不再重复进入 fallback；跨 jieba 边界的 bigram 默认不进入主查询。
            if item in high_confidence_texts:
                continue
            if payload.mode == "query" and len(jieba_terms) >= 2:
                continue
            _append_unique_token(fallback_tokens, LexicalToken(item, "fallback_ngram", 0.2, "cjk_fallback"))
            if len(fallback_tokens) >= max_fallback_terms:
                break

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
                "jieba_terms": jieba_terms,
                "cjk_fallback_terms": [token.text for token in fallback_tokens],
                "priority_terms": [token.text for token in terms if token.source in {"priority_term", "glossary"}],
                "priority_phrases": [token.text for token in phrases if token.source == "priority_phrase"],
                "synonym_terms": [token.text for token in aliases],
                "ignored_terms": list(dict.fromkeys(ignored_terms)),
                "stopword_hits": _collect_stopword_hits(normalized, stopwords),
                "custom_words": list(custom_words),
                "registered_custom_words": list(registered_custom_words),
            }
            | _build_stopword_debug(stopwords),
        )
