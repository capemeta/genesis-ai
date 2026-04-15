"""
文档解析器模块

支持多种解析策略：
- BasicParser: 基础解析（协调器，调用各专用解析器）
- PDF 解析器: Native, Docling, MinerU, TCADP
- Word 解析器: WordParser
- Excel 解析器: ExcelParser
- OCR 解析器: OCRParser
- Vision 解析器: VisionParser
"""

from .base import BaseParser
from .factory import ParserFactory
from .basic_parser import BasicParser

# PDF 解析器
from .pdf import (
    BasePDFParser,
    NativePDFParser,
    PDFRouter,
    DoclingParser,
    MinerUParser,
    TCADPParser,
)

# Word 解析器
from .word import WordParser

# Excel 解析器
from .excel import ExcelParser
from .qa import QAParser

# OCR 解析器
from .ocr import OCRParser

# Vision 解析器
from .vision import VisionParser

__all__ = [
    "BaseParser",
    "ParserFactory",
    "BasicParser",
    # PDF
    "BasePDFParser",
    "NativePDFParser",
    "PDFRouter",
    "DoclingParser",
    "MinerUParser",
    "TCADPParser",
    # Word
    "WordParser",
    # Excel
    "ExcelParser",
    # QA
    "QAParser",
    # OCR
    "OCRParser",
    # Vision
    "VisionParser",
]
