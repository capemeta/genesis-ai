"""
全文检索停用词资源加载器。

停用词拆为索引侧与查询侧两份：
- doc_stopwords.txt：用于索引构建，保持更保守，避免破坏长期索引资产
- query_stopwords.txt：用于查询构造，可更偏向过滤问句引导词和低价值泛词

知识库仍可通过 retrieval_stopwords 追加业务级停用词。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal


StopwordMode = Literal["index", "query"]

_STOPWORD_DIR = Path(__file__).resolve().parents[1] / "resources" / "stopwords"
_STOPWORD_FILES: dict[StopwordMode, str] = {
    "index": "doc_stopwords.txt",
    "query": "query_stopwords.txt",
}

# 文件缺失时的兜底词表。正常运行应以 resources/stopwords/*.txt 为准。
_FALLBACK_QUERY_STOPWORDS: tuple[str, ...] = (
    "相关",
    "内容",
    "介绍",
    "说明",
    "的",
    "了",
    "吗",
    "呢",
    "和",
    "与",
    "及",
    "或",
    "以及",
)
_FALLBACK_DOC_STOPWORDS: tuple[str, ...] = (
    "相关",
    "内容",
    "的",
    "了",
    "和",
    "与",
    "及",
    "以及",
)


def _normalize_stopword_line(line: str) -> str:
    """规范化单行停用词。"""

    return str(line or "").strip().lstrip("\ufeff").strip()


@lru_cache(maxsize=2)
def load_stopwords(mode: StopwordMode) -> tuple[str, ...]:
    """加载指定模式的停用词文件，保持稳定顺序去重。"""

    filename = _STOPWORD_FILES[mode]
    path = _STOPWORD_DIR / filename
    if not path.exists():
        return _FALLBACK_DOC_STOPWORDS if mode == "index" else _FALLBACK_QUERY_STOPWORDS

    terms: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        term = _normalize_stopword_line(raw_line)
        if not term:
            continue
        # 允许使用 "# 说明" 写注释；单独的 "#" 仍可作为停用词。
        if term.startswith("# "):
            continue
        if term not in terms:
            terms.append(term)
    return tuple(terms)


def load_doc_stopwords() -> tuple[str, ...]:
    """加载索引侧停用词。"""

    return load_stopwords("index")


def load_query_stopwords() -> tuple[str, ...]:
    """加载查询侧停用词。"""

    return load_stopwords("query")


def merge_stopwords(mode: StopwordMode, extra_terms: list[str] | tuple[str, ...] | None = None) -> list[str]:
    """合并默认资源停用词与知识库级停用词。"""

    terms: list[str] = []
    for item in [*load_stopwords(mode), *list(extra_terms or [])]:
        term = _normalize_stopword_line(item)
        if term and term not in terms:
            terms.append(term)
    return terms


def filter_exact_stopword_terms(
    *,
    terms: list[str] | tuple[str, ...],
    stopwords: list[str] | tuple[str, ...],
) -> list[str]:
    """只按完整词项过滤停用词，避免在中文整句内部做子串删除。"""

    ignored_terms = {" ".join(str(item or "").strip().split()).lower() for item in stopwords if str(item or "").strip()}
    filtered_terms: list[str] = []
    for raw_term in terms:
        normalized_term = " ".join(str(raw_term or "").strip().split())
        lowered_term = normalized_term.lower()
        if not normalized_term or lowered_term in ignored_terms:
            continue
        if normalized_term not in filtered_terms:
            filtered_terms.append(normalized_term)
    return filtered_terms


# 兼容旧导入名；查询侧默认停用词用于 query_analysis。
DEFAULT_RETRIEVAL_STOPWORDS = load_query_stopwords()
