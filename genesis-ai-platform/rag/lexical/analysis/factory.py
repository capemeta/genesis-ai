"""
全文检索分析器工厂。
"""

from __future__ import annotations

from rag.lexical.analysis.base import LexicalAnalyzer
from rag.lexical.analysis.jieba_analyzer import JiebaLexicalAnalyzer


def get_default_lexical_analyzer() -> LexicalAnalyzer:
    """返回当前默认全文检索分析器。"""

    return JiebaLexicalAnalyzer()

