"""
查询分析模块。

职责：
- 在正式检索前完成查询标准化
- 承载同义词改写、规则型过滤提取、术语上下文补充
- 为后续引入 LLM 查询分析保留统一入口
"""

from rag.query_analysis.service import QueryAnalysisService
from rag.query_analysis.types import (
    AnalyzedQuery,
    QueryAnalysisAutoFilterSignal,
    QueryAnalysisConfig,
    QueryAnalysisFilterCandidate,
    QueryAnalysisGlossaryEntry,
    QueryAnalysisSynonymMatch,
)

__all__ = [
    "AnalyzedQuery",
    "QueryAnalysisAutoFilterSignal",
    "QueryAnalysisConfig",
    "QueryAnalysisFilterCandidate",
    "QueryAnalysisGlossaryEntry",
    "QueryAnalysisService",
    "QueryAnalysisSynonymMatch",
]
