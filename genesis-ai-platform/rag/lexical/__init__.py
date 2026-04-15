"""
全文索引服务模块。
"""

from .analysis import (
    LexicalAnalysisResult,
    LexicalAnalyzer,
    LexicalAnalyzerInput,
    LexicalToken,
    JiebaLexicalAnalyzer,
    RuleBasedLexicalAnalyzer,
    build_pg_fts_query_payload,
)
from typing import Any


def __getattr__(name: str) -> Any:
    """按需加载索引服务，避免导入纯分析工具时初始化 ORM 依赖。"""

    if name == "SearchUnitLexicalIndexService":
        from .service import SearchUnitLexicalIndexService

        return SearchUnitLexicalIndexService
    raise AttributeError(f"module 'rag.lexical' has no attribute {name!r}")

__all__ = [
    "LexicalAnalysisResult",
    "LexicalAnalyzer",
    "LexicalAnalyzerInput",
    "LexicalToken",
    "JiebaLexicalAnalyzer",
    "RuleBasedLexicalAnalyzer",
    "SearchUnitLexicalIndexService",
    "build_pg_fts_query_payload",
]
