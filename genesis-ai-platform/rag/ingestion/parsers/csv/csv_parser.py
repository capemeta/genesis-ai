"""
CSV 文档解析器

支持 .csv 格式，转换为 Markdown 表格
"""

import csv
import logging
from io import StringIO
from typing import Tuple, Dict, Any, List
from ..encoding_utils import decode_with_encoding_detection
from ..excel.excel_parser_utils import infer_column_types

logger = logging.getLogger(__name__)


class CSVParser:
    """
    CSV 文档解析器
    
    特点：
    - 支持 .csv 格式
    - 自动检测编码（UTF-8, GBK, GB2312, Big5 等）
    - 自动检测分隔符（逗号、分号、制表符等）
    - 转换为 Markdown 表格格式
    
    输出格式：
    - 第一行作为表头
    - 转换为 Markdown 表格
    - 空单元格保留为空字符串
    """
    
    def __init__(self, max_rows: int = 10000, max_cols: int = 100):
        """
        初始化 CSV 解析器
        
        Args:
            max_rows: 最大行数（防止内存溢出）
            max_cols: 最大列数
        """
        self.max_rows = max_rows
        self.max_cols = max_cols
    
    def is_available(self) -> bool:
        """检查 CSV 模块是否可用（Python 内置）"""
        return True
    
    def parse(self, file_buffer: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        解析 CSV 文档
        
        Args:
            file_buffer: CSV 文件字节内容
        
        Returns:
            (markdown_text, metadata): Markdown 文本和元数据
        """
        logger.info("[CSVParser] 开始解析 CSV 文档")
        
        # 1. 自动检测编码
        text, encoding = decode_with_encoding_detection(file_buffer)
        logger.info(f"[CSVParser] 编码检测结果: {encoding}")
        
        # 2. 自动检测分隔符
        delimiter = self._detect_delimiter(text)
        logger.info(f"[CSVParser] 分隔符检测结果: {repr(delimiter)}")
        
        # 3. 解析 CSV
        rows = self._parse_csv_text(text, delimiter)
        
        # 4. 转换为 Markdown
        markdown = self._rows_to_markdown(rows)
        
        metadata = {
            "parse_method": "csv",
            "parser": "csv (builtin)",
            "encoding": encoding,
            "delimiter": delimiter,
            "row_count": len(rows),
            "col_count": len(rows[0]) if rows else 0,
        }
        
        logger.info(f"[CSVParser] 解析完成，行数: {len(rows)}, 列数: {len(rows[0]) if rows else 0}")
        
        return markdown, metadata

    def parse_table(self, file_buffer: bytes, sheet_name: str = "CSV") -> Tuple[str, Dict[str, Any]]:
        """
        以“结构化表格知识库”模式解析 CSV。

        输出与 ExcelTableParser 对齐的 `table_rows` / `sheets` / `field_map`，
        便于复用 `ExcelTableChunker`。
        """
        markdown, metadata = self.parse(file_buffer)
        text, encoding = decode_with_encoding_detection(file_buffer)
        delimiter = metadata.get("delimiter") or self._detect_delimiter(text)
        rows = self._parse_csv_text(text, delimiter)

        if not rows:
            return markdown, {
                "parse_method": "csv_table",
                "parser": "csv (builtin)",
                "format": "csv",
                "encoding": encoding,
                "delimiter": delimiter,
                "sheet_count": 0,
                "sheets": [],
                "table_rows": [],
                "field_map": {},
            }

        header = rows[0]
        data_rows = rows[1:]
        if not any(cell.strip() for cell in header):
            header = [f"列{i+1}" for i in range(len(header))]

        normalized_rows: List[List[str]] = []
        for row in data_rows:
            padded = row[:len(header)] + [""] * max(0, len(header) - len(row))
            if any(cell for cell in padded):
                normalized_rows.append(padded)

        column_types = infer_column_types(header, normalized_rows[:100]) if normalized_rows else {
            col: "text" for col in header
        }

        table_rows = [
            {
                "sheet_name": sheet_name,
                "row_index": idx + 1,
                "header": header,
                "values": row,
                "column_types": column_types,
            }
            for idx, row in enumerate(normalized_rows)
        ]

        return markdown, {
            "parse_method": "csv_table",
            "parser": "csv (builtin)",
            "format": "csv",
            "encoding": encoding,
            "delimiter": delimiter,
            "sheet_count": 1 if table_rows else 0,
            "sheets": [
                {
                    "sheet_name": sheet_name,
                    "header": header,
                    "row_count": len(normalized_rows),
                    "column_types": column_types,
                }
            ] if table_rows else [],
            "table_rows": table_rows,
            "field_map": column_types,
        }
    
    def _detect_delimiter(self, text: str) -> str:
        """
        自动检测 CSV 分隔符
        
        尝试顺序：
        1. 逗号（,）- 最常见
        2. 分号（;）- 欧洲常用
        3. 制表符（\t）- TSV 格式
        4. 竖线（|）- 某些系统导出格式
        
        Args:
            text: CSV 文本内容
        
        Returns:
            检测到的分隔符
        """
        # 取前几行进行检测
        sample_lines = text.split('\n')[:5]
        sample_text = '\n'.join(sample_lines)
        
        try:
            # 使用 csv.Sniffer 自动检测
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample_text).delimiter
            logger.debug(f"[CSVParser] Sniffer 检测到分隔符: {repr(delimiter)}")
            return delimiter
        except Exception as e:
            logger.debug(f"[CSVParser] Sniffer 检测失败: {e}，使用手动检测")
        
        # 手动检测：统计各分隔符出现次数
        delimiters = [',', ';', '\t', '|']
        delimiter_counts: Dict[str, int] = {}
        
        for line in sample_lines:
            if not line.strip():
                continue
            for delim in delimiters:
                count = line.count(delim)
                delimiter_counts[delim] = delimiter_counts.get(delim, 0) + count
        
        # 选择出现次数最多的分隔符
        if delimiter_counts:
            detected_delimiter = max(delimiter_counts, key=lambda delimiter: delimiter_counts[delimiter])
            logger.debug(f"[CSVParser] 手动检测到分隔符: {repr(detected_delimiter)}")
            return detected_delimiter
        
        # 默认使用逗号
        logger.debug("[CSVParser] 无法检测分隔符，使用默认逗号")
        return ','
    
    def _parse_csv_text(self, text: str, delimiter: str) -> List[List[str]]:
        """
        解析 CSV 文本
        
        Args:
            text: CSV 文本内容
            delimiter: 分隔符
        
        Returns:
            行数据列表
        """
        rows = []
        reader = csv.reader(StringIO(text), delimiter=delimiter)
        
        for i, row in enumerate(reader):
            if i >= self.max_rows:
                logger.warning(f"[CSVParser] 达到最大行数限制 {self.max_rows}，停止解析")
                break
            
            # 限制列数
            if len(row) > self.max_cols:
                logger.warning(f"[CSVParser] 第 {i+1} 行超过最大列数 {self.max_cols}，截断")
                row = row[:self.max_cols]
            
            # 清理单元格内容
            cleaned_row = [cell.strip() for cell in row]
            rows.append(cleaned_row)
        
        # 过滤全空行
        non_empty_rows = [row for row in rows if any(cell for cell in row)]
        
        return non_empty_rows
    
    def _rows_to_markdown(self, rows: List[List[str]]) -> str:
        """
        将行数据转换为 Markdown 表格
        
        Args:
            rows: 行数据列表
        
        Returns:
            Markdown 格式的表格
        """
        if not rows:
            return ""
        
        # 第一行作为表头
        header = rows[0]
        data_rows = rows[1:]
        
        # 如果第一行全空，使用列号作为表头
        if not any(cell.strip() for cell in header):
            header = [f"列{i+1}" for i in range(len(header))]
        
        # 转义表格单元格
        header = [self._escape_cell(cell) for cell in header]
        
        # 构建表格
        lines = []
        header_line = "| " + " | ".join(header) + " |"
        separator_line = "| " + " | ".join(["---"] * len(header)) + " |"
        
        lines.append(header_line)
        lines.append(separator_line)
        
        # 数据行
        for row in data_rows:
            # 补齐列数
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            elif len(row) > len(header):
                row = row[:len(header)]
            
            # 转义单元格
            row = [self._escape_cell(cell) for cell in row]
            
            row_line = "| " + " | ".join(row) + " |"
            lines.append(row_line)
        
        return "\n".join(lines)
    
    @staticmethod
    def _escape_cell(value: str) -> str:
        """
        转义 Markdown 表格单元格
        
        Args:
            value: 单元格值
        
        Returns:
            转义后的值
        """
        # 替换管道符
        value = (value or "").replace("|", "\\|")
        
        # 替换换行符为 <br>
        value = value.replace("\n", "<br>").replace("\r", "")
        
        # 去除首尾空格
        return value.strip()
