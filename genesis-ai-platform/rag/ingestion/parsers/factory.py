"""
解析器工厂

根据解析策略和文件类型选择合适的解析器
"""

from typing import Dict, Optional, Type
from rag.enums import ParseStrategy
from .base import BaseParser
from .basic_parser import BasicParser
from .vision import VisionParser
from .qa import QAParser


class ParserFactory:
    """
    解析器工厂
    
    负责：
    1. 注册解析器
    2. 根据策略选择解析器
    3. 自动选择最优解析策略
    """
    
    _parsers: Dict[ParseStrategy, Type[BaseParser]] = {
        ParseStrategy.BASIC: BasicParser,
        ParseStrategy.QA: QAParser,
        ParseStrategy.VISION: VisionParser,
    }
    
    @classmethod
    def create_parser(cls, strategy: ParseStrategy, **kwargs) -> BaseParser:
        """
        创建解析器实例
        
        Args:
            strategy: 解析策略
            **kwargs: 解析器配置参数
        
        Returns:
            BaseParser: 解析器实例
        
        Raises:
            ValueError: 不支持的解析策略
        """
        parser_class = cls._parsers.get(strategy)
        if parser_class is None:
            parser_class = cls._resolve_optional_parser(strategy)
        if not parser_class:
            raise ValueError(f"不支持的解析策略: {strategy}")
        
        return parser_class(**kwargs)

    @classmethod
    def _resolve_optional_parser(cls, strategy: ParseStrategy) -> Optional[type[BaseParser]]:
        """
        按需加载可选解析器，避免在默认安装下提前触发重依赖导入。
        """
        if strategy == ParseStrategy.MINERU:
            from .pdf import MinerUParser

            return MinerUParser
        if strategy == ParseStrategy.DOCLING:
            from .pdf import DoclingParser

            return DoclingParser
        if strategy == ParseStrategy.TCADP:
            from .pdf import TCADPParser

            return TCADPParser
        if strategy == ParseStrategy.OCR:
            from .ocr import OCRParser

            return OCRParser
        return None
    
    @classmethod
    def auto_select_strategy(
        cls,
        file_buffer: bytes,
        file_extension: str
    ) -> ParseStrategy:
        """
        自动选择解析策略
        
        规则：
        1. 扫描件 PDF → OCR
        2. 复杂布局 PDF → MinerU
        3. 图片 → OCR
        4. 其他 → Basic
        
        Args:
            file_buffer: 文件二进制内容
            file_extension: 文件扩展名
        
        Returns:
            ParseStrategy: 推荐的解析策略
        """
        print(f"[ParserFactory] 自动选择解析策略，文件类型: {file_extension}")
        
        ext = file_extension.lower()
        
        # 图片文件 → OCR
        if ext in {".jpg", ".jpeg", ".png", ".bmp"}:
            print("[ParserFactory] 选择 OCR 策略（图片文件）")
            return ParseStrategy.OCR
        
        # PDF 文件
        if ext == ".pdf":
            # TODO: 实现 PDF 特征检测
            # - 检测是否为扫描件
            # - 检测布局复杂度
            
            # 占位逻辑
            is_scanned = cls._is_scanned_pdf(file_buffer)
            if is_scanned:
                print("[ParserFactory] 选择 OCR 策略（扫描件 PDF）")
                return ParseStrategy.OCR
            
            is_complex = cls._is_complex_layout(file_buffer)
            if is_complex:
                print("[ParserFactory] 选择 MinerU 策略（复杂布局 PDF）")
                return ParseStrategy.MINERU
        
        # 默认使用基础解析
        print("[ParserFactory] 选择 Basic 策略（默认）")
        return ParseStrategy.BASIC
    
    @classmethod
    def _is_scanned_pdf(cls, file_buffer: bytes) -> bool:
        """
        
        检测是否为扫描件 PDF
        TODO: 实现检测逻辑
        """
        # TODO: 实现扫描件检测
        # - 检查是否包含文本层
        # - 检查图片占比
        return False
    
    @classmethod
    def _is_complex_layout(cls, file_buffer: bytes) -> bool:
        """
        检测是否为复杂布局
        
        TODO: 实现检测逻辑
        """
        # TODO: 实现布局复杂度检测
        # - 检查表格数量
        # - 检查多栏布局
        # - 检查公式数量
        return False
    
    @classmethod
    def register_parser(cls, strategy: ParseStrategy, parser_class: Type[BaseParser]) -> None:
        """
        注册自定义解析器
        
        Args:
            strategy: 解析策略
            parser_class: 解析器类
        """
        cls._parsers[strategy] = parser_class
        print(f"[ParserFactory] 注册解析器: {strategy} -> {parser_class.__name__}")
