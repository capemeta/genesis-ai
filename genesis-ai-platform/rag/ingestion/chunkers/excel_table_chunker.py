"""
Excel 表格模式分块器

当前版本采用“Sheet 摘要块 + 行级叶子块/超限父子块”的统一策略：
1. Sheet 级 summary chunk 作为根节点
2. 行内容未超限时，直接生成一个 `excel_row` 叶子块
3. 仅当单行超过预算时，才生成 `excel_row` 父块 + `excel_row_fragment` 子块
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseChunker
from .excel_row_chunk_builder import ExcelRowChunkBuilder
from .excel_token_handler import ExcelTokenHandler

logger = logging.getLogger(__name__)


class ExcelTableChunker(BaseChunker):
    """Excel 表格模式分块器。"""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 0,
        filter_columns: Optional[List[str]] = None,
        key_columns: Optional[List[str]] = None,
        max_embed_tokens: int = 512,
        token_count_method: str = "chars",
        text_prefix_template: str = "",
        enable_summary_chunk: bool = True,
        **kwargs,
    ):
        """
        Args:
            chunk_size: 保留参数，与 BaseChunker 接口兼容
            chunk_overlap: 保留参数
            filter_columns: 过滤列，不参与检索文本，但保存在 metadata
            key_columns: 关键列，会附着到每个子块身份文本中
            max_embed_tokens: 向量化最大 token
            token_count_method: token 计数方式
            text_prefix_template: 保留参数，兼容现有配置
            enable_summary_chunk: 是否生成 Sheet 摘要块
        """
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs)
        self.filter_columns = list(filter_columns or [])
        self.key_columns = list(key_columns or [])
        self.max_embed_tokens = max_embed_tokens
        self.token_count_method = token_count_method
        self.text_prefix_template = text_prefix_template
        self.enable_summary_chunk = enable_summary_chunk

        self._token_handler = ExcelTokenHandler(
            max_embed_tokens=max_embed_tokens,
            token_count_method=token_count_method,
        )
        self._row_builder = ExcelRowChunkBuilder(
            strategy_name="excel_table",
            token_handler=self._token_handler,
            max_embed_tokens=max_embed_tokens,
            token_count_method=token_count_method,
            key_columns=self.key_columns,
        )

    def chunk(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """将表格行数据转换为摘要块 + 行级块结构。"""
        if metadata is None:
            metadata = {}

        table_rows: List[Dict[str, Any]] = metadata.get("table_rows", [])
        sheets_info: List[Dict[str, Any]] = metadata.get("sheets", [])
        sheet_root_node_ids: Dict[str, str] = {
            str(key): str(value)
            for key, value in dict(metadata.get("sheet_root_node_ids") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        if not table_rows:
            logger.warning("[ExcelTableChunker] metadata 中无 table_rows，返回空 chunk 列表")
            return []

        sheet_root_chunks: Dict[str, Dict[str, Any]] = {}
        chunks: List[Dict[str, Any]] = []

        for row_dict in table_rows:
            sheet_name = str(row_dict.get("sheet_name") or "Sheet")
            row_index = int(row_dict.get("row_index") or 0)
            row_uid = str(row_dict.get("row_uid") or "").strip() or None
            table_row_id = str(row_dict.get("table_row_id") or "").strip() or None
            header: List[str] = list(row_dict.get("header", []) or [])
            values: List[str] = list(row_dict.get("values", []) or [])

            if not header or not values or row_index <= 0:
                continue

            if self.enable_summary_chunk and sheet_name not in sheet_root_chunks:
                sheet_info = next((item for item in sheets_info if item.get("sheet_name") == sheet_name), None)
                summary_chunk = self._build_summary_chunk(
                    sheet_name,
                    header,
                    sheet_info,
                    node_id=sheet_root_node_ids.get(sheet_name),
                )
                sheet_root_chunks[sheet_name] = summary_chunk
                chunks.append(summary_chunk)

            filter_fields = self._extract_filter_fields(header, values)
            summary_node_id = (
                sheet_root_chunks.get(sheet_name, {}).get("metadata", {}).get("node_id")
                or sheet_root_node_ids.get(sheet_name)
            )

            row_chunk, fragment_chunks = self._row_builder.build_row_chunk_family(
                sheet_name=sheet_name,
                row_index=row_index,
                row_uid=row_uid,
                table_row_id=table_row_id,
                header=header,
                values=values,
                parent_node_id=summary_node_id if isinstance(summary_node_id, str) else None,
                parent_depth=1 if summary_node_id else 0,
                filter_fields=filter_fields,
                # table 模式要求“一行最多一个检索块”；
                # 只有单行超限时，才升级成父块 + 子片段结构。
                always_create_parent=False,
            )
            chunks.append(row_chunk)
            chunks.extend(fragment_chunks)

            if sheet_name in sheet_root_chunks:
                sheet_root_chunks[sheet_name]["metadata"]["child_ids"].append(
                    row_chunk["metadata"]["node_id"]
                )

        logger.info(
            "[ExcelTableChunker] 生成 %s 个 chunk （%s 行数据，%s 个 Sheet）",
            len(chunks),
            len(table_rows),
            len({row.get('sheet_name') for row in table_rows}),
        )
        return chunks

    def _extract_filter_fields(
        self,
        header: List[str],
        values: List[str],
    ) -> Dict[str, str]:
        """提取过滤列键值。"""
        filter_name_set = set(self.filter_columns)
        return {
            str(col): str(val)
            for col, val in zip(header, values)
            if str(col) in filter_name_set and str(val or "").strip()
        }

    def _build_summary_chunk(
        self,
        sheet_name: str,
        header: List[str],
        sheet_info: Optional[Dict[str, Any]],
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """为每个 Sheet 构建统一根节点。"""
        row_count = int(sheet_info.get("row_count", 0)) if sheet_info else 0
        return self._row_builder.build_sheet_root_chunk(
            sheet_name=sheet_name,
            field_names=header,
            row_count=row_count,
            filter_column_names=self.filter_columns,
            node_id=node_id,
        )
