"""
PDF 解析器路由

根据文档特征和配置智能选择最合适的解析器
"""

import logging
from typing import Tuple, Dict, Any, Optional, List
from .base_pdf_parser import BasePDFParser
from .models import ParserElement
from .native import NativePDFParser

logger = logging.getLogger(__name__)


class PDFRouter:
    """
    PDF 解析器路由
    
    智能路由策略：
    1. 检测文档类型（扫描版/文本型）
    2. 评估复杂度（表格/公式/版面）
    3. 根据配置选择解析器
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化路由器
        
        Args:
            config: PDF 解析配置
        """
        self.config = config or {}
        
        # 解析器实例（延迟初始化）
        self._native_parser: Optional[NativePDFParser] = None
    
    def route(self, file_buffer: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        路由并解析 PDF
        
        Returns:
            (text, metadata): (Markdown字符串, 包含elements的元数据)
        """
        # 1. 获取用户指定的解析器
        parser_choice = self.config.get("parser", "native")
        
        # 2. 如果是 auto，则智能选择
        if parser_choice == "auto":
            parser_choice = self._auto_select(file_buffer)
        elif parser_choice == "docling" and not self._is_docling_enabled():
            # 默认发布配置下关闭 docling，避免可选依赖缺失时直接失败。
            logger.warning("[PDFRouter] docling 已关闭，自动降级为 native")
            parser_choice = "native"
        
        # 3. 调用对应解析器获取结构化元素
        logger.info(f"[PDFRouter] 使用解析引擎: {parser_choice}")
        
        elements: List[ParserElement] = []
        if parser_choice == "native":
            elements = self._parse_with_native(file_buffer)
        elif parser_choice == "docling":
            elements = self._parse_with_docling(file_buffer)
        elif parser_choice == "mineru":
            elements = self._parse_with_mineru(file_buffer)
        elif parser_choice == "tcadp":
            elements = self._parse_with_tcadp(file_buffer)
        else:
            raise ValueError(f"未知的解析器: {parser_choice}")

        # 4.1 聚合 PDF 图片资源（仿照 docx：占位符 + blob 在 metadata 里）
        # 注意：需要在生成 markdown 之前把 elements 中的 image content 统一成占位符路径。
        pdf_embedded_images: List[Dict[str, Any]] = []
        if elements:
            for el in elements:
                if el.get("type") != "image":
                    continue
                el_meta = el.get("metadata") or {}
                image_id = str(el_meta.get("image_id") or "").strip()
                image_blob = el_meta.get("blob")
                if image_id and isinstance(image_blob, (bytes, bytearray)):
                    pdf_embedded_images.append(
                        {
                            "id": image_id,
                            "content_type": str(el_meta.get("content_type") or "application/octet-stream"),
                            "ext": str(el_meta.get("ext") or ".bin"),
                            "size": int(el_meta.get("size") or len(image_blob)),
                            "blob": image_blob,
                            "page_no": el.get("page_no"),
                            "bbox": el.get("bbox"),
                        }
                    )

                # 元素内不保留 blob，避免 metadata 过大/序列化问题
                if "blob" in el_meta:
                    el_meta.pop("blob", None)
                    el["metadata"] = el_meta

                if image_id:
                    el["content"] = f"pdf://embedded/{image_id}"

        # 4. 转换输出 (规范化 Markdown)
        text = BasePDFParser.to_markdown(elements)

        ocr_elements = [
            el for el in elements
            if (el.get("metadata") or {}).get("source") == "ocr"
        ]
        vision_elements = [
            el for el in elements
            if (el.get("metadata") or {}).get("source") == "vision"
        ]

        metadata = {
            "parser": parser_choice,
            "element_count": len(elements),
            "elements": elements, 
            "parse_method": "pdf_unified_v1",
            "pdf_embedded_images": pdf_embedded_images,
            "ocr": {
                "enabled": bool(self.config.get("enable_ocr", True)),
                "element_count": len(ocr_elements),
                "page_count": len({int(el.get("page_no", -1)) for el in ocr_elements}),
                "engines": sorted(
                    {
                        str((el.get("metadata") or {}).get("ocr_engine"))
                        for el in ocr_elements
                        if (el.get("metadata") or {}).get("ocr_engine")
                    }
                ),
            },
            "vision": {
                "enabled": bool(self.config.get("enable_vision", False)),
                "element_count": len(vision_elements),
                "page_count": len({int(el.get("page_no", -1)) for el in vision_elements}),
            },
        }
        
        return text, metadata

    def _is_docling_enabled(self) -> bool:
        """
        是否启用 docling 解析。

        默认关闭，避免开源默认安装（未安装 docling）时误走重依赖路径。
        """
        return bool(self.config.get("enable_docling", False))


    def _auto_select(self, file_buffer: bytes) -> str:
        """Auto select parser based on PDF characteristics."""
        try:
            import fitz
        except ImportError:
            return "native"
        
        doc = fitz.open(stream=file_buffer, filetype="pdf")
        try:
            # 检测是否扫描版
            if self._is_scanned(doc):
                if self.config.get("enable_ocr", True):
                    return "mineru"
                return "native"
            
            # 检测复杂度
            complexity = self._assess_complexity(doc)
            if complexity == "complex" and self._is_docling_enabled():
                logger.info("[PDFRouter] 检测到复杂文档 -> Docling")
                return "docling"
            
            return "native"
        finally:
            doc.close()

    def _is_scanned(self, doc, sample_pages: int = 3) -> bool:
        sample_count = min(sample_pages, len(doc))
        text_lengths = []
        for i in range(sample_count):
            text = doc[i].get_text().strip()
            text_lengths.append(len(text))
        avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
        return avg_length < 50

    def _assess_complexity(self, doc) -> str:
        page_count = len(doc)
        first_page = doc[0]
        text = first_page.get_text()
        has_tables = text.count("\t") > 10 or "  " * 5 in text
        has_formulas = any(char in text for char in ["=", "+", "-", "∑", "∫", "√"])
        
        if has_tables or has_formulas:
            return "complex"
        elif page_count > 50:
            return "medium"
        return "simple"

    def _parse_with_native(self, file_buffer: bytes) -> List[ParserElement]:
        if self._native_parser is None:
            enable_ocr = self.config.get("enable_ocr", True)
            ocr_engine = self.config.get("ocr_engine", "auto")
            self._native_parser = NativePDFParser(
                enable_ocr=enable_ocr,
                ocr_engine=ocr_engine,
                ocr_languages=self.config.get("ocr_languages", ["ch", "en"]),
                extract_images=self.config.get("extract_images", False),
                extract_tables=self.config.get("extract_tables", True),
                ocr_reflow_enabled=self.config.get("ocr_reflow_enabled", False),
                ocr_merge_profile=self.config.get("ocr_merge_profile", "balanced"),
                ocr_merge_min_score=self.config.get("ocr_merge_min_score"),
                ocr_legacy_mode=self.config.get("ocr_legacy_mode", False),
                ocr_preprocess_enabled=self.config.get("ocr_preprocess_enabled", True),
                ocr_red_seal_suppression=self.config.get("ocr_red_seal_suppression", True),
                ocr_post_correction_enabled=self.config.get("ocr_post_correction_enabled", True),
                ocr_tesseract_psm_list=self.config.get("ocr_tesseract_psm_list"),
            )
            logger.info(
                "[PDFRouter] Native 解析器: enable_ocr=%s, ocr_engine=%s",
                enable_ocr,
                ocr_engine,
            )
        elements = self._native_parser.parse(file_buffer)
        ocr_els = [el for el in elements if (el.get("metadata") or {}).get("source") == "ocr"]
        if ocr_els:
            engines_used = sorted(
                {
                    str((el.get("metadata") or {}).get("ocr_engine"))
                    for el in ocr_els
                    if (el.get("metadata") or {}).get("ocr_engine")
                }
            )
            logger.info(
                "[PDFRouter] OCR 已使用: 引擎=%s, 识别元素数=%d, 涉及页数=%d",
                engines_used or ["unknown"],
                len(ocr_els),
                len({el.get("page_no") for el in ocr_els}),
            )
        return elements

    def _parse_with_docling(self, file_buffer: bytes) -> List[ParserElement]:
        from .docling import DoclingParser
        parser = DoclingParser(**self.config)
        if hasattr(parser, "parse_to_elements"):
            elements, _metadata = parser.parse_to_elements(file_buffer, ".pdf")
            if elements:
                return elements
        text, _metadata = parser.parse(file_buffer, ".pdf")
        return [
            {
                "type": "text",
                "content": text or "",
                "page_no": 0,
                "bbox": [0.0, 0.0, 0.0, 0.0],
                "metadata": {"source": "docling", "fallback": True},
            }
        ]

    def _parse_with_mineru(self, file_buffer: bytes) -> List[ParserElement]:
        from .mineru import MinerUParser
        parser = MinerUParser(**self.config)
        if hasattr(parser, "parse_to_elements"):
            elements, _metadata = parser.parse_to_elements(file_buffer, ".pdf")
            if elements:
                return elements
        text, _metadata = parser.parse(file_buffer, ".pdf")
        return [
            {
                "type": "text",
                "content": text or "",
                "page_no": 0,
                "bbox": [0.0, 0.0, 0.0, 0.0],
                "metadata": {"source": "mineru"},
            }
        ]

    def _parse_with_tcadp(self, file_buffer: bytes) -> List[ParserElement]:
        from .tcadp_parser import TCADPParser
        parser = TCADPParser(**self.config)
        text, _metadata = parser.parse(file_buffer, ".pdf")
        return [
            {
                "type": "text",
                "content": text or "",
                "page_no": 0,
                "bbox": [0.0, 0.0, 0.0, 0.0],
                "metadata": {"source": "tcadp"},
            }
        ]

