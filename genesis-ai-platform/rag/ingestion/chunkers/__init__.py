"""
分块器模块

支持多种分块策略：
- FixedSizeChunker: 固定长度分块
- SemanticChunker: 语义分块
- MarkdownChunker: Markdown 结构分块
- RecursiveChunker: 递归分块
- ExcelGeneralChunker: Excel 通用模式（表头+行累积）
- ExcelTableChunker: Excel 表格模式（一行一 chunk，过滤列）
"""

from .base import BaseChunker
from .factory import ChunkerFactory
from .fixed_size_chunker import FixedSizeChunker
from .semantic_chunker import SemanticChunker
from .markdown import MarkdownChunker
from .recursive_chunker import RecursiveChunker
from .pdf_layout_chunker import PdfLayoutChunker
from .excel_general_chunker import ExcelGeneralChunker
from .excel_table_chunker import ExcelTableChunker
from .excel_token_handler import ExcelTokenHandler
from .qa import QAChunker
from .web_page_chunker import WebPageChunker
from .rule_based_chunker import RuleBasedChunker

__all__ = [
    "BaseChunker",
    "ChunkerFactory",
    "FixedSizeChunker",
    "SemanticChunker",
    "MarkdownChunker",
    "RecursiveChunker",
    "PdfLayoutChunker",
    "ExcelGeneralChunker",
    "ExcelTableChunker",
    "ExcelTokenHandler",
    "QAChunker",
    "WebPageChunker",
    "RuleBasedChunker",
]
