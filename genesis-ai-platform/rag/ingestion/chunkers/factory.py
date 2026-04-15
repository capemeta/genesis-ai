"""
分块器工厂

根据分块策略选择合适的分块器
"""

from typing import Any, Dict, Type, cast
from rag.enums import ChunkStrategy
from .base import BaseChunker
from .fixed_size_chunker import FixedSizeChunker
from .semantic_chunker import SemanticChunker
from .markdown import MarkdownChunker
from .recursive_chunker import RecursiveChunker
from .general import GeneralChunker
from .pdf_layout_chunker import PdfLayoutChunker
from .excel_general_chunker import ExcelGeneralChunker
from .excel_table_chunker import ExcelTableChunker
from .qa import QAChunker
from .web_page_chunker import WebPageChunker
from .rule_based_chunker import RuleBasedChunker


class ChunkerFactory:
    """
    分块器工厂
    
    负责：
    1. 注册分块器
    2. 根据策略选择分块器
    """
    
    _chunkers: Dict[ChunkStrategy, Type[Any]] = {
        ChunkStrategy.QA: QAChunker,
        ChunkStrategy.FIXED_SIZE: FixedSizeChunker,
        ChunkStrategy.SEMANTIC: SemanticChunker,
        ChunkStrategy.MARKDOWN: MarkdownChunker,
        ChunkStrategy.RECURSIVE: RecursiveChunker,
        ChunkStrategy.GENERAL: GeneralChunker,
        ChunkStrategy.PDF_LAYOUT: PdfLayoutChunker,
        ChunkStrategy.SMART: GeneralChunker,      # 默认智能策略指向通用分块器
        ChunkStrategy.EXCEL_GENERAL: ExcelGeneralChunker,  # Excel 通用模式
        ChunkStrategy.EXCEL_TABLE: ExcelTableChunker,       # Excel 表格模式
        ChunkStrategy.WEB_PAGE: WebPageChunker,             # 网页分块策略
        ChunkStrategy.RULE_BASED: RuleBasedChunker,         # 用户规则分块策略
    }
    
    @classmethod
    def create_chunker(
        cls,
        strategy: ChunkStrategy,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        **kwargs
    ) -> BaseChunker:
        """
        创建分块器实例
        
        Args:
            strategy: 分块策略
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
            **kwargs: 其他配置参数
        
        Returns:
            BaseChunker: 分块器实例
        
        Raises:
            ValueError: 不支持的分块策略
        """
        chunker_class = cls._chunkers.get(strategy)
        if not chunker_class:
            raise ValueError(f"不支持的分块策略: {strategy}")
        
        return cast(BaseChunker, chunker_class(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            **kwargs
        ))
    
    @classmethod
    def register_chunker(cls, strategy: ChunkStrategy, chunker_class: Type[Any]) -> None:
        """
        注册自定义分块器
        
        Args:
            strategy: 分块策略
            chunker_class: 分块器类
        """
        cls._chunkers[strategy] = chunker_class
        print(f"[ChunkerFactory] 注册分块器: {strategy} -> {chunker_class.__name__}")
