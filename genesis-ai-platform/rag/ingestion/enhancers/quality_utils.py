"""
增强结果质量控制工具。
"""

from __future__ import annotations

import re
from typing import Iterable


def strip_json_fence(raw_text: str) -> str:
    """剥离常见的 ```json 代码块包裹，便于后续统一 JSON 解析。"""
    normalized = str(raw_text or "").strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`").strip()
        if normalized.lower().startswith("json"):
            normalized = normalized[4:].strip()
    return normalized


def is_low_value_summary(summary: str) -> bool:
    """判断摘要是否缺乏稳定检索价值。"""
    normalized = re.sub(r"\s+", " ", str(summary or "")).strip()
    if not normalized:
        return True
    if len(normalized) < 8:
        return True
    if normalized in {"暂无摘要", "无", "未知", "未提及"}:
        return True
    if normalized.startswith(("本文介绍了", "这段内容介绍了", "主要介绍了", "这是关于")) and len(normalized) <= 18:
        return True
    return False


def normalize_keywords(values: Iterable[str], *, limit: int) -> list[str]:
    """过滤低价值关键词，避免写入泛词噪声。"""
    generic_terms = {
        "介绍",
        "说明",
        "相关内容",
        "内容",
        "文本",
        "文档",
        "资料",
        "信息",
        "问题",
        "答案",
        "总结",
        "摘要",
    }
    filtered: list[str] = []
    seen: set[str] = set()
    for item in list(values or []):
        keyword = re.sub(r"\s+", " ", str(item or "")).strip(" ,;:|/\\-")
        if not keyword:
            continue
        dedupe_key = keyword.lower()
        if dedupe_key in seen:
            continue
        if keyword in generic_terms:
            continue
        if len(keyword) == 1 and not keyword.isascii():
            continue
        if len(keyword) > 40:
            continue
        if re.search(r"[。！？；\n\r]", keyword):
            continue
        seen.add(dedupe_key)
        filtered.append(keyword)
        if len(filtered) >= limit:
            break
    return filtered


def normalize_questions(values: Iterable[str], *, limit: int) -> list[str]:
    """过滤低质量问题，避免写入弱检索问句。"""
    filtered: list[str] = []
    seen: set[str] = set()
    low_value_patterns = [
        "它是什么",
        "这个问题如何处理",
        "这是什么",
        "如何处理这个问题",
    ]

    for item in list(values or []):
        question = re.sub(r"\s+", " ", str(item or "")).strip()
        if not question:
            continue
        dedupe_key = question.lower()
        if dedupe_key in seen:
            continue
        if len(question) < 6:
            continue
        if any(pattern in question for pattern in low_value_patterns):
            continue
        if question[-1] not in {"?", "？"}:
            question = f"{question}？"
            dedupe_key = question.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        filtered.append(question)
        if len(filtered) >= limit:
            break
    return filtered
