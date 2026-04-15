"""
PDF 解析器模块

支持多种 PDF 解析策略：
- Native:  快速解析
- Docling: 智能布局分析
- MinerU: 高精度 OCR
- TCADP: 腾讯云服务
"""

from .base_pdf_parser import BasePDFParser
from .native import NativePDFParser
from .pdf_router import PDFRouter
from .docling import DoclingParser
from .mineru import MinerUParser
from .tcadp_parser import TCADPParser


__all__ = [
    "BasePDFParser",
    "NativePDFParser",
    "PDFRouter",
    "DoclingParser",
    "MinerUParser",
    "TCADPParser",
]
