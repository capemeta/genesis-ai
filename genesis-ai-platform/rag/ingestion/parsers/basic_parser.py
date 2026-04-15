"""
基础解析器

支持常见文档格式的基础解析
"""

import logging
import mimetypes
import re
from io import BytesIO
from pathlib import Path
from typing import Tuple, Dict, Any
from .base import BaseParser
from .encoding_utils import decode_with_encoding_detection

logger = logging.getLogger(__name__)


class BasicParser(BaseParser):
    """
    基础解析器
    
    支持格式：
    - 文档：PDF, Word (.docx), Excel (.xlsx, .xls)
    - 纯文本：TXT, Markdown, CSV
    - 代码：Python, JavaScript, Java, C/C++, Go, Rust 等
    - 配置：JSON, YAML, TOML, XML, HTML 等
    - 脚本：Shell, Batch, PowerShell
    - 日志：LOG
    - 数据库：SQL
    
    注意：Celery Worker 本身是独立进程，不受 GIL 限制
    直接同步执行即可，无需 asyncio.to_thread
    """
    
    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {
        # 文档格式
        ".pdf", ".docx", ".doc", ".xlsx", ".xls",
        # 纯文本格式
        ".md", ".txt", ".csv",
        # 代码文件
        ".py", ".js", ".java", ".c", ".cpp", ".h", ".hpp",
        ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".php",
        ".cs", ".swift", ".kt", ".scala", ".r", ".m", ".mm",
        # 配置文件
        ".json", ".yaml", ".yml", ".toml", ".ini", ".conf", ".cfg",
        ".xml", ".html", ".htm",
        # 脚本文件
        ".sh", ".bat", ".ps1", ".cmd",
        # 日志文件
        ".log",
        # SQL 文件
        ".sql",
    }
    
    def supports(self, file_extension: str) -> bool:
        """检查是否支持该文件类型"""
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def parse(self, file_buffer: bytes, file_extension: str) -> Tuple[str, Dict[str, Any]]:
        """
        解析文件（同步方法）
        
        ⚠️ 重要设计原则：
        1. 解析任务是 CPU 密集型（文本提取、格式转换）
        2. 使用同步方法，简单直接
        3. Celery Worker 本身是独立进程，不受主应用 GIL 限制
        4. 部署时使用 prefork Worker：
           celery -A tasks worker -Q parse --pool=prefork --concurrency=4
        """
        logger.info(f"[BasicParser] 开始解析文件，类型: {file_extension}")
        
        # 统一调用 _parse_by_extension，由它处理所有文件类型
        text, ext_metadata = self._parse_by_extension(file_buffer, file_extension)

        metadata = {
            "file_extension": file_extension,
            "text_length": len(text),
            **ext_metadata,
        }
        metadata.setdefault("parse_method", "basic")
        
        logger.info(f"[BasicParser] 解析完成，文本长度: {len(text)}")
        
        return text, metadata
    
    def _parse_by_extension(self, file_buffer: bytes, file_extension: str) -> Tuple[str, Dict[str, Any]]:
        """
        根据扩展名选择解析方法
        
        返回：(text, extra_metadata)
        - text: 解析后的文本
        - extra_metadata: 额外的元数据（如 docx 的图片信息）
        """
        ext = file_extension.lower()
        logger.info(f"[BasicParser] 正在解析文件类型: {ext}")
        
        # 文档格式
        if ext == ".pdf":
            return self._parse_pdf(file_buffer)
        elif ext == ".docx":
            return self._parse_docx(file_buffer)
        elif ext == ".doc":
            raise ValueError("暂不支持 .doc，请先转换为 .docx 后再上传")
        elif ext in {".xlsx", ".xls"}:
            return self._parse_excel(file_buffer, ext)
        
        # CSV 格式
        elif ext == ".csv":
            return self._parse_csv(file_buffer)
        
        # 纯文本格式（需要编码检测）
        elif ext in {".md", ".markdown"}:
            return self._parse_markdown(file_buffer), {}
        elif ext == ".txt":
            return self._parse_txt(file_buffer), {}
        
        # 代码文件（需要编码检测）
        elif ext in {".py", ".js", ".java", ".c", ".cpp", ".h", ".hpp",
                     ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".php",
                     ".cs", ".swift", ".kt", ".scala", ".r", ".m", ".mm"}:
            return self._parse_code_file(file_buffer, ext), {}
        
        # 配置文件（需要编码检测）
        elif ext in {".json", ".yaml", ".yml", ".toml", ".ini", ".conf", ".cfg"}:
            return self._parse_config_file(file_buffer, ext), {}
        
        # 标记语言（需要编码检测）
        elif ext in {".xml", ".html", ".htm"}:
            return self._parse_markup_file(file_buffer, ext), {}
        
        # 脚本文件（需要编码检测）
        elif ext in {".sh", ".bat", ".ps1", ".cmd"}:
            return self._parse_script_file(file_buffer, ext), {}
        
        # 日志文件（需要编码检测）
        elif ext == ".log":
            return self._parse_log_file(file_buffer), {}
        
        # SQL 文件（需要编码检测）
        elif ext == ".sql":
            return self._parse_sql_file(file_buffer), {}
        
        else:
            raise ValueError(f"不支持的文件类型: {file_extension}")
    
    def _parse_pdf(self, file_buffer: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        解析 PDF
        
        使用新的模块化 PDF 解析架构：
        - 智能路由：根据文档特征选择最佳解析器
        - 支持多种解析策略：Native, Docling, MinerU, TCADP
        - 自动降级：解析失败时自动切换到备选方案
        """
        logger.info("[BasicParser] 解析 PDF（使用 PDFRouter）")
        
        try:
            from .pdf import PDFRouter
            
            # 创建路由器（传递配置）
            router = PDFRouter(config=self._get_pdf_config())
            
            # 路由并解析
            text, metadata = router.route(file_buffer)
            
            logger.info(f"[BasicParser] PDF 解析完成，使用解析器: {metadata.get('parser', 'unknown')}")
            
            return text, metadata
        
        except ImportError as e:
            logger.error(f"[BasicParser] PDF 解析模块导入失败: {e}")
            return "PDF 解析失败：缺少必要的依赖库", {}
        except Exception as e:
            logger.error(f"[BasicParser] PDF 解析失败: {e}")
            return f"PDF 解析失败：{str(e)}", {}
    
    def _get_pdf_config(self) -> Dict[str, Any]:
        """
        获取 PDF 解析配置
        
        可以从环境变量、配置文件或数据库中读取
        这里提供默认配置
        """
        default_config = {
            "parser": "auto",  # auto, native, docling, mineru, tcadp
            "enable_docling": False,
            "enable_ocr": True,
            "enable_paddle_ocr": False,
            "ocr_engine": "auto",  # auto, paddleocr, tesseract
            "ocr_languages": ["ch", "en"],
            "ocr_min_text_chars": 50,
            "ocr_render_scale": 2.0,
            "enable_vision": False,
            "extract_images": False,
            "extract_tables": True,
        }

        config = self.config or {}

        pdf_parser_config = config.get("pdf_parser_config")
        if isinstance(pdf_parser_config, dict):
            merged = {**default_config, **pdf_parser_config}
            return merged

        flattened = {k: v for k, v in config.items() if k in default_config and v is not None}
        merged = {**default_config, **flattened}
        return merged
    
    def _parse_docx(self, file_buffer: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        解析 docx 并返回文本与元数据
        
        使用新的模块化 WordParser：
        - 生成图片占位符
        - 输出图片元数据（包含 blob），供后续存储到对象存储
        
        注意：blob 会在 parse_task.py 的 _persist_docx_images_and_rewrite_markdown 中处理并移除
        """
        logger.info("[BasicParser] 解析 docx（带图片元数据）")
        
        try:
            from .word import WordParser
            
            # 创建解析器（生成图片占位符）
            parser = WordParser(with_image_placeholder=True)
            
            # 解析
            markdown_text, metadata = parser.parse(file_buffer)
            
            # 添加额外的处理信息
            metadata["image_processing"] = {
                "status": "reserved",
                "ocr_enabled": False,
                "vision_enabled": False,
                "next_step": "后续可基于 image_placeholders 接入 OCR/Vision 解析流水线",
            }
            
            logger.info(f"[BasicParser] docx 解析完成，图片数量: {metadata.get('image_count', 0)}")
            
            return markdown_text, metadata
        
        except ImportError as e:
            logger.error(f"[BasicParser] Word 解析模块导入失败: {e}")
            return "Word 解析失败：缺少必要的依赖库", {}
        except Exception as e:
            logger.error(f"[BasicParser] docx 解析失败: {e}")
            return f"Word 解析失败：{str(e)}", {}

    
    def _parse_excel(self, file_buffer: bytes, file_extension: str = ".xlsx") -> Tuple[str, Dict[str, Any]]:
        """
        解析 Excel
        
        使用新的模块化 Excel 解析器：
        - 通用知识库：ExcelParser → Markdown + sheets_data
        - 结构化表格知识库：ExcelTableParser → table_rows
        """
        logger.info(f"[BasicParser] 解析 Excel（使用 ExcelParser），格式: {file_extension}")
        
        try:
            from .excel import ExcelParser, ExcelTableParser

            excel_mode = str(self.config.get("excel_mode") or "general").lower()
            if excel_mode == "table":
                parser: Any = ExcelTableParser()
            else:
                parser = ExcelParser()
            
            # 解析
            text, metadata = parser.parse(file_buffer, file_extension)
            
            logger.info(f"[BasicParser] Excel 解析完成，工作表数量: {metadata.get('sheet_count', 0)}")
            
            return text, metadata
        
        except ImportError as e:
            logger.error(f"[BasicParser] Excel 解析模块导入失败: {e}")
            return "Excel 解析失败：缺少必要的依赖库", {
                "parse_method": "excel_error",
                "parser": "basic_excel_import_error",
            }
        except Exception as e:
            logger.error(f"[BasicParser] Excel 解析失败: {e}")
            return f"Excel 解析失败：{str(e)}", {
                "parse_method": "excel_error",
                "parser": "basic_excel_runtime_error",
            }
    
    def _parse_markdown(self, file_buffer: bytes) -> str:
        """
        解析 Markdown
        
        自动检测编码，支持多种中文编码
        """
        logger.info("[BasicParser] 解析 Markdown")
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[BasicParser] Markdown 编码检测结果: {encoding}")
        return text
    
    def _parse_txt(self, file_buffer: bytes) -> str:
        """
        解析 TXT
        
        自动检测编码，支持多种中文编码
        """
        logger.info("[BasicParser] 解析 TXT")
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[BasicParser] TXT 编码检测结果: {encoding}")
        return text
    
    def _parse_code_file(self, file_buffer: bytes, file_extension: str) -> str:
        """
        解析代码文件
        
        支持：Python, JavaScript, Java, C/C++, Go, Rust 等
        自动检测编码
        """
        logger.info(f"[BasicParser] 解析代码文件: {file_extension}")
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[BasicParser] 代码文件编码检测结果: {encoding}")
        return text
    
    def _parse_config_file(self, file_buffer: bytes, file_extension: str) -> str:
        """
        解析配置文件
        
        支持：JSON, YAML, TOML, INI 等
        自动检测编码
        """
        logger.info(f"[BasicParser] 解析配置文件: {file_extension}")
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[BasicParser] 配置文件编码检测结果: {encoding}")
        return text
    
    def _parse_markup_file(self, file_buffer: bytes, file_extension: str) -> str:
        """
        解析标记语言文件
        
        支持：XML, HTML 等
        自动检测编码
        """
        logger.info(f"[BasicParser] 解析标记语言文件: {file_extension}")
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[BasicParser] 标记语言文件编码检测结果: {encoding}")
        return text
    
    def _parse_script_file(self, file_buffer: bytes, file_extension: str) -> str:
        """
        解析脚本文件
        
        支持：Shell, Batch, PowerShell 等
        自动检测编码
        """
        logger.info(f"[BasicParser] 解析脚本文件: {file_extension}")
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[BasicParser] 脚本文件编码检测结果: {encoding}")
        return text
    
    def _parse_log_file(self, file_buffer: bytes) -> str:
        """
        解析日志文件
        
        自动检测编码
        """
        logger.info("[BasicParser] 解析日志文件")
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[BasicParser] 日志文件编码检测结果: {encoding}")
        return text
    
    def _parse_sql_file(self, file_buffer: bytes) -> str:
        """
        解析 SQL 文件
        
        自动检测编码
        """
        logger.info("[BasicParser] 解析 SQL 文件")
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[BasicParser] SQL 文件编码检测结果: {encoding}")
        return text
    
    def _parse_csv(self, file_buffer: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        解析 CSV
        
        使用新的模块化 CSVParser：
        - 自动检测编码
        - 自动检测分隔符
        - 转换为 Markdown 表格
        """
        logger.info("[BasicParser] 解析 CSV（使用 CSVParser）")
        
        try:
            from .csv import CSVParser
            
            # 创建解析器
            parser = CSVParser()
            excel_mode = str(self.config.get("excel_mode") or "general").lower()
            
            # 结构化表格知识库中的 CSV 复用表格模式输出协议。
            if excel_mode == "table":
                text, metadata = parser.parse_table(file_buffer, sheet_name="CSV")
            else:
                text, metadata = parser.parse(file_buffer)
            
            logger.info(f"[BasicParser] CSV 解析完成，行数: {metadata.get('row_count', 0)}")
            
            return text, metadata
        
        except ImportError as e:
            logger.error(f"[BasicParser] CSV 解析模块导入失败: {e}")
            return "CSV 解析失败：缺少必要的依赖库", {
                "parse_method": "csv_error",
                "parser": "basic_csv_import_error",
            }
        except Exception as e:
            logger.error(f"[BasicParser] CSV 解析失败: {e}")
            return f"CSV 解析失败：{str(e)}", {
                "parse_method": "csv_error",
                "parser": "basic_csv_runtime_error",
            }
    
    def _decode_with_encoding_detection(self, content: bytes) -> Tuple[str, str]:
        """
        自动检测编码并解码
        
        尝试编码顺序（参考 WeKnora）：
        1. utf-8（最常用，优先尝试）
        2. gb18030（中文国标，兼容 GBK 和 GB2312）
        3. gb2312（简体中文）
        4. gbk（简体中文扩展）
        5. big5（繁体中文）
        6. ascii（纯英文）
        7. latin-1（西欧语言，兜底方案，不会抛出异常）
        
        返回：(解码后的文本, 使用的编码)
        """
        encodings = ["utf-8", "gb18030", "gb2312", "gbk", "big5", "ascii", "latin-1"]
        
        for encoding in encodings:
            try:
                text = content.decode(encoding)
                logger.debug(f"[BasicParser] 编码检测成功: {encoding}")
                return text, encoding
            except (UnicodeDecodeError, LookupError):
                continue
        
        # 理论上不会到这里（latin-1 不会抛出异常）
        logger.warning("[BasicParser] 所有编码尝试失败，使用 utf-8 并忽略错误")
        return content.decode("utf-8", errors="ignore"), "utf-8-fallback"
