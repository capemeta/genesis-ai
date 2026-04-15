"""
Excel 解析共享工具函数

供 ExcelParser（通用模式）和 ExcelTableParser（表格模式）复用，
避免代码重复，保证行为一致。
"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 列类型枚举
COL_TYPE_INT = "int"
COL_TYPE_FLOAT = "float"
COL_TYPE_TEXT = "text"
COL_TYPE_DATETIME = "datetime"
COL_TYPE_BOOL = "bool"


def normalize_cell_value(value: Any, xlrd_wb: Any = None, xlrd_cell_type: Optional[int] = None) -> str:
    """
    将单元格值规范化为字符串。

    处理以下特殊情况：
    - None / 空值 → 空字符串
    - datetime / date 对象 → ISO 格式字符串
    - bool → "是" / "否"
    - xlrd 日期浮点序列号（cell_type=3）→ ISO 格式（需传入 xlrd_wb 和 xlrd_cell_type）
    - Excel 错误值（#DIV/0! / #N/A / #VALUE! 等）→ 空字符串
    - 其他 → str().strip()

    Args:
        value: 单元格原始值
        xlrd_wb: xlrd 工作簿对象（用于日期序列号转换，可为 None）
        xlrd_cell_type: xlrd cell.ctype（可为 None，传入时用于判断日期）

    Returns:
        规范化后的字符串
    """
    if value is None:
        return ""

    # xlrd 日期类型（ctype=3 表示 XL_CELL_DATE）
    if xlrd_cell_type == 3 and xlrd_wb is not None:
        try:
            import xlrd as xlrd_module  # type: ignore[import-untyped]
            date_tuple = xlrd_module.xldate_as_tuple(value, xlrd_wb.datemode)
            if date_tuple[3] == 0 and date_tuple[4] == 0 and date_tuple[5] == 0:
                # 纯日期（无时分秒）
                return datetime.date(*date_tuple[:3]).strftime("%Y-%m-%d")
            else:
                return datetime.datetime(*date_tuple).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)

    # Python datetime/date 对象（openpyxl 返回）
    if isinstance(value, datetime.datetime):
        if value.hour == 0 and value.minute == 0 and value.second == 0:
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")

    # bool 必须在 int 之前判断（Python 中 bool 是 int 子类）
    if isinstance(value, bool):
        return "是" if value else "否"

    # Excel 错误值：openpyxl 可能返回 openpyxl.utils.cell.CellErrorValue
    # 或字符串形如 "#DIV/0!"
    if hasattr(value, "error_code"):
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("#") and stripped.endswith("!"):
            return ""
        return stripped

    # 数值型：去除 .0 后缀（整数显示更干净）
    if isinstance(value, float) and value == int(value):
        return str(int(value))

    return str(value).strip()


def find_header_row(rows: List[List[Any]], scan_rows: int = 10) -> int:
    """
    智能表头检测（参考 Dify）。

    扫描前 scan_rows 行，优先选第一个有 >= 2 个非空列的行作为表头行，
    若无则选非空列数最多的行。

    Args:
        rows: 行数据列表（每行为原始值列表，未经规范化）
        scan_rows: 扫描的最大行数

    Returns:
        0-based 表头行索引
    """
    best_idx, best_count = 0, 0
    for row_idx, row in enumerate(rows[:scan_rows]):
        non_empty = sum(1 for cell in row if cell is not None and str(cell).strip())
        if non_empty >= 2:
            return row_idx  # 首选：第一个满足条件的行
        if non_empty > best_count:
            best_count = non_empty
            best_idx = row_idx
    return best_idx  # 兜底：非空列数最多的行


def backfill_merged_cells(sheet: Any) -> None:
    """
    回填 openpyxl 工作表中的合并单元格（参考 MaxKB / KnowFlow）。

    合并区域内非左上角的单元格值被设置为与左上角相同，
    避免表格解析后出现大量空格子破坏语义。

    注意：此函数只能在 read_only=False 模式下使用。

    Args:
        sheet: openpyxl worksheet 对象
    """
    try:
        for merge_range in list(sheet.merged_cells.ranges):
            # 取左上角值
            top_left = sheet.cell(merge_range.min_row, merge_range.min_col).value
            for row in range(merge_range.min_row, merge_range.max_row + 1):
                for col in range(merge_range.min_col, merge_range.max_col + 1):
                    if row == merge_range.min_row and col == merge_range.min_col:
                        continue
                    sheet.cell(row, col).value = top_left
    except Exception as e:
        logger.warning(f"[ExcelParserUtils] 合并单元格回填失败（忽略）: {e}")


def infer_column_types(
    header: List[str],
    rows: List[List[str]],
    sample_rows: int = 100,
) -> Dict[str, str]:
    """
    推断每列的数据类型（参考 KnowFlow）。

    扫描前 sample_rows 行数据，按投票机制决定每列类型。
    类型优先级：bool > datetime > int > float > text

    Args:
        header: 表头列名列表
        rows: 数据行列表（已规范化为字符串）
        sample_rows: 用于推断的样本行数

    Returns:
        {"列名": "int|float|text|datetime|bool"} 映射
    """
    if not header or not rows:
        return {}

    sample = rows[:sample_rows]
    result: Dict[str, str] = {}

    for col_idx, col_name in enumerate(header):
        values = []
        for row in sample:
            if col_idx < len(row):
                v = row[col_idx]
                if v and v.strip():
                    values.append(v.strip())

        if not values:
            result[col_name] = COL_TYPE_TEXT
            continue

        result[col_name] = _vote_column_type(values)

    return result


def _vote_column_type(values: List[str]) -> str:
    """对一列的值进行类型投票，返回得票最多的类型。"""
    type_counts = {
        COL_TYPE_BOOL: 0,
        COL_TYPE_DATETIME: 0,
        COL_TYPE_INT: 0,
        COL_TYPE_FLOAT: 0,
        COL_TYPE_TEXT: 0,
    }

    for v in values:
        t = _infer_single_value_type(v)
        type_counts[t] += 1

    # 若 text 占比超过 30%，直接判定为 text（避免混合列被误判）
    text_ratio = type_counts[COL_TYPE_TEXT] / len(values)
    if text_ratio > 0.3:
        return COL_TYPE_TEXT

    # 按优先级返回得票最多的非 text 类型
    for t in (COL_TYPE_BOOL, COL_TYPE_DATETIME, COL_TYPE_INT, COL_TYPE_FLOAT):
        if type_counts[t] > 0:
            return t

    return COL_TYPE_TEXT


def _infer_single_value_type(value: str) -> str:
    """推断单个字符串值的类型。"""
    if value in ("是", "否", "true", "false", "True", "False", "TRUE", "FALSE", "1", "0"):
        return COL_TYPE_BOOL

    # 尝试日期（先用 pandas，若不可用则用正则）
    if _looks_like_datetime(value):
        return COL_TYPE_DATETIME

    # 整数
    try:
        int(value)
        return COL_TYPE_INT
    except ValueError:
        pass

    # 浮点
    try:
        float(value)
        return COL_TYPE_FLOAT
    except ValueError:
        pass

    return COL_TYPE_TEXT


def _looks_like_datetime(value: str) -> bool:
    """判断字符串是否像日期时间（轻量实现，避免依赖 pandas）。"""
    import re
    # 常见日期格式：YYYY-MM-DD / YYYY/MM/DD / YYYYMMDD
    patterns = [
        r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}",       # 2024-01-01 / 2024/1/1
        r"^\d{8}$",                               # 20240101
        r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{2}:\d{2}",  # 带时间
    ]
    for pattern in patterns:
        if re.match(pattern, value):
            return True
    return False


def extract_hyperlink(cell: Any) -> Optional[str]:
    """
    提取 openpyxl 单元格的超链接（参考 Dify）。

    若单元格有超链接，返回 Markdown 格式 "[text](url)"，
    否则返回 None。

    注意：只在 read_only=False 模式下可访问 hyperlink 属性。

    Args:
        cell: openpyxl cell 对象

    Returns:
        Markdown 超链接字符串，或 None
    """
    try:
        if hasattr(cell, "hyperlink") and cell.hyperlink and cell.hyperlink.target:
            text = str(cell.value).strip() if cell.value is not None else ""
            url = cell.hyperlink.target
            if text:
                return f"[{text}]({url})"
            return url
    except Exception:
        pass
    return None


def rows_to_markdown(
    sheet_name: str,
    header: List[str],
    data_rows: List[List[str]],
    row_start: int = 1,
) -> str:
    """
    将表头和数据行转换为 Markdown 表格字符串（供通用模式使用）。

    Args:
        sheet_name: 工作表名称（用于标题行）
        header: 表头列名列表
        data_rows: 数据行列表（已规范化为字符串）
        row_start: 数据行的起始行号（1-based，用于生成标题注释）

    Returns:
        Markdown 表格字符串（含 ## 标题）
    """
    if not header:
        return ""

    row_end = row_start + len(data_rows) - 1
    lines = [f"## {sheet_name}（第 {row_start}–{row_end} 行）", ""]

    # 转义表头
    esc_header = [_escape_md_cell(h) for h in header]
    lines.append("| " + " | ".join(esc_header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    # 数据行
    for row in data_rows:
        # 补齐列数
        padded = list(row) + [""] * max(0, len(header) - len(row))
        padded = padded[:len(header)]
        esc_row = [_escape_md_cell(cell) for cell in padded]
        lines.append("| " + " | ".join(esc_row) + " |")

    return "\n".join(lines)


def rows_to_html(
    sheet_name: str,
    header: List[str],
    data_rows: List[List[str]],
    row_start: int = 1,
) -> str:
    """
    将表头和数据行转换为 HTML 表格字符串（参考 KnowFlow html4excel 模式）。

    Args:
        sheet_name: 工作表名称
        header: 表头列名列表
        data_rows: 数据行列表（已规范化为字符串）
        row_start: 数据行的起始行号（1-based）

    Returns:
        HTML 表格字符串（含注释标题）
    """
    import html as html_lib

    row_end = row_start + len(data_rows) - 1
    parts = [f"<!-- {sheet_name} 第 {row_start}–{row_end} 行 -->", "<table>", "<thead><tr>"]

    for h in header:
        parts.append(f"<th>{html_lib.escape(h)}</th>")
    parts.append("</tr></thead>", )
    parts.append("<tbody>")

    for row in data_rows:
        padded = list(row) + [""] * max(0, len(header) - len(row))
        padded = padded[:len(header)]
        parts.append("<tr>")
        for cell in padded:
            parts.append(f"<td>{html_lib.escape(cell)}</td>")
        parts.append("</tr>")

    parts.append("</tbody></table>")
    return "\n".join(parts)


def single_row_to_markdown(header: List[str], row: List[str]) -> str:
    """
    将单行数据转换为含表头的 Markdown 表格（表格模式 content_blocks 用）。

    Args:
        header: 表头列名列表
        row: 数据行（已规范化为字符串）

    Returns:
        含表头的单行 Markdown 表格字符串
    """
    esc_header = [_escape_md_cell(h) for h in header]
    padded = list(row) + [""] * max(0, len(header) - len(row))
    padded = padded[:len(header)]
    esc_row = [_escape_md_cell(cell) for cell in padded]

    lines = [
        "| " + " | ".join(esc_header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
        "| " + " | ".join(esc_row) + " |",
    ]
    return "\n".join(lines)


def _escape_md_cell(value: str) -> str:
    """转义 Markdown 表格单元格中的特殊字符。"""
    value = (value or "").replace("|", "\\|")
    value = value.replace("\n", " ").replace("\r", " ")
    return value.strip()
