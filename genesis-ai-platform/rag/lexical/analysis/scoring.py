"""
全文检索评分工具。
"""

from __future__ import annotations


def normalize_lexical_score(raw_score: float) -> float:
    """将全文检索原始加和分压到 0-1 区间，保持排序单调。"""

    score = max(0.0, float(raw_score or 0.0))
    if score <= 0:
        return 0.0
    return round(min(1.0, score / (score + 0.8)), 4)
