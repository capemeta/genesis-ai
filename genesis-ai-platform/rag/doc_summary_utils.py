"""
doc_summary 质量治理工具。

职责：
- 统一清洗 kb_doc.summary 文本
- 在索引写入与热路径兜底两侧复用同一套质量门槛
- 避免低信息摘要进入检索链，降低噪声
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from rag.utils.token_utils import count_tokens

DEFAULT_DOC_SUMMARY_MIN_CHARS = 24
DEFAULT_DOC_SUMMARY_MIN_TOKENS = 8
DEFAULT_DOC_SUMMARY_MAX_CHARS = 1200
DEFAULT_DOC_SUMMARY_MIN_UNIQUE_TERMS = 3
DEFAULT_DOC_SUMMARY_EXCLUDED_PHRASES = {
    "暂无摘要",
    "无摘要",
    "暂无内容",
    "待补充",
    "敬请期待",
    "无",
    "暂无",
    "未提供摘要",
    "summary unavailable",
    "no summary",
}


def normalize_doc_summary_quality_config(raw_config: Mapping[str, Any] | None) -> dict[str, Any]:
    """规范化 doc_summary 质量门槛配置。"""

    persistent_context = dict((raw_config or {}).get("persistent_context") or {})
    excluded_phrases = [
        str(item).strip().lower()
        for item in list(persistent_context.get("doc_summary_excluded_phrases") or [])
        if str(item or "").strip()
    ]
    if not excluded_phrases:
        excluded_phrases = sorted(DEFAULT_DOC_SUMMARY_EXCLUDED_PHRASES)

    return {
        "min_chars": _to_int(
            persistent_context.get("doc_summary_min_chars"),
            DEFAULT_DOC_SUMMARY_MIN_CHARS,
            minimum=1,
            maximum=5000,
        ),
        "min_tokens": _to_int(
            persistent_context.get("doc_summary_min_tokens"),
            DEFAULT_DOC_SUMMARY_MIN_TOKENS,
            minimum=1,
            maximum=2000,
        ),
        "max_chars": _to_int(
            persistent_context.get("doc_summary_max_chars"),
            DEFAULT_DOC_SUMMARY_MAX_CHARS,
            minimum=32,
            maximum=10000,
        ),
        "min_unique_terms": _to_int(
            persistent_context.get("doc_summary_min_unique_terms"),
            DEFAULT_DOC_SUMMARY_MIN_UNIQUE_TERMS,
            minimum=1,
            maximum=50,
        ),
        "excluded_phrases": excluded_phrases,
    }


def prepare_doc_summary_text(
    summary_text: str | None,
    *,
    retrieval_config: Mapping[str, Any] | None,
) -> str | None:
    """清洗并校验 doc_summary，可用时返回标准化文本。"""

    config = normalize_doc_summary_quality_config(retrieval_config)
    normalized_text = _normalize_summary_text(summary_text, max_chars=config["max_chars"])
    if not normalized_text:
        return None
    if _is_excluded_summary(normalized_text, excluded_phrases=config["excluded_phrases"]):
        return None
    if len(normalized_text) < config["min_chars"]:
        return None
    if count_tokens(normalized_text) < config["min_tokens"]:
        return None
    if len(_extract_unique_terms(normalized_text)) < config["min_unique_terms"]:
        return None
    return normalized_text


def _normalize_summary_text(summary_text: str | None, *, max_chars: int) -> str:
    """归一化摘要文本，并限制最大长度。"""

    normalized = " ".join(str(summary_text or "").split()).strip(" \t\r\n-_:：;；|")
    if not normalized:
        return ""
    if len(normalized) <= max_chars:
        return normalized
    truncated = normalized[:max_chars].rstrip(" ，,。.;；:：!！?？、")
    return truncated or normalized[:max_chars]


def _is_excluded_summary(summary_text: str, *, excluded_phrases: list[str]) -> bool:
    """识别明显低信息的摘要文本。"""

    lowered = str(summary_text or "").strip().lower()
    if not lowered:
        return True
    if lowered in set(excluded_phrases):
        return True
    if re.fullmatch(r"[\W_]+", lowered):
        return True
    return False


def _extract_unique_terms(summary_text: str) -> set[str]:
    """提取简单唯一词项，用于过滤低信息摘要。"""

    matches = re.findall(r"[\u4e00-\u9fff]{1,}|[a-zA-Z0-9_]{2,}", str(summary_text or "").lower())
    return {item for item in matches if item}


def _to_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    """带边界的整数兜底。"""

    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))
