"""
全文检索分析器抽象接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from rag.lexical.analysis.types import LexicalAnalysisResult, LexicalAnalyzerInput


class LexicalAnalyzer(ABC):
    """全文检索分析器基类。"""

    analyzer_type: str

    @abstractmethod
    def analyze(self, payload: LexicalAnalyzerInput) -> LexicalAnalysisResult:
        """执行全文检索分析。"""
        raise NotImplementedError

