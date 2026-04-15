"""
Excel 通用模式分块器

当前版本采用“完整行父块 + 按列聚合子块”的统一策略：
1. 每一行都生成一个完整父块，保留整行原始数据
2. 检索子块按 token 预算聚合若干列
3. 单个超长单元格继续拆成列片段，避免前缀爆炸
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .base import BaseChunker
from .excel_row_chunk_builder import ExcelRowChunkBuilder
from .excel_token_handler import ExcelTokenHandler, count_tokens
from rag.ingestion.parsers.excel.excel_parser_utils import rows_to_markdown

logger = logging.getLogger(__name__)


class ExcelGeneralChunker(BaseChunker):
    """Excel 通用模式分块器。"""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 0,
        rows_per_chunk: int = 30,
        excel_mode: str = "markdown",
        use_title_prefix: bool = True,
        include_hidden_sheets: bool = False,
        max_embed_tokens: int = 512,
        token_count_method: str = "chars",
        **kwargs,
    ):
        """
        Args:
            chunk_size: 保留参数，与 BaseChunker 接口兼容
            chunk_overlap: 保留参数，与 BaseChunker 接口兼容
            rows_per_chunk: 历史参数，当前父子块模式下不再直接参与切分
            excel_mode: 保留参数，兼容配置
            use_title_prefix: 保留参数，兼容配置
            include_hidden_sheets: 保留参数，兼容配置
            max_embed_tokens: 向量化最大 token
            token_count_method: token 计数方式
        """
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs)
        self.rows_per_chunk = max(1, rows_per_chunk)
        self.excel_mode = excel_mode if excel_mode in ("markdown", "html") else "markdown"
        self.use_title_prefix = use_title_prefix
        self.include_hidden_sheets = include_hidden_sheets
        self.max_embed_tokens = max_embed_tokens
        self.token_count_method = token_count_method

        self._token_handler = ExcelTokenHandler(
            max_embed_tokens=max_embed_tokens,
            token_count_method=token_count_method,
        )
        self._row_builder = ExcelRowChunkBuilder(
            strategy_name="excel_general",
            token_handler=self._token_handler,
            max_embed_tokens=max_embed_tokens,
            token_count_method=token_count_method,
            leaf_chunk_token_limit=min(int(chunk_size), int(max_embed_tokens)),
        )
        logger.info(
            "[ExcelGeneralChunker] 初始化: chunk_size=%s, max_embed_tokens=%s, leaf_chunk_token_limit=%s, rows_per_chunk=%s",
            self.chunk_size,
            self.max_embed_tokens,
            self._row_builder.leaf_chunk_token_limit,
            self.rows_per_chunk,
        )

    def chunk(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """将 Excel 行数据转换为父子块结构。"""
        if metadata is None:
            metadata = {}

        sheets_data: List[Dict[str, Any]] = metadata.get("sheets_data", [])
        if not sheets_data:
            logger.warning("[ExcelGeneralChunker] metadata 中无 sheets_data，降级为单块输出")
            return self._fallback_single_chunk(text, metadata)

        chunks: List[Dict[str, Any]] = []
        logger.info(
            "[ExcelGeneralChunker] 开始分块: sheet_count=%s, chunk_size=%s, max_embed_tokens=%s, leaf_chunk_token_limit=%s",
            len(sheets_data),
            self.chunk_size,
            self.max_embed_tokens,
            self._row_builder.leaf_chunk_token_limit,
        )
        for sheet_info in sheets_data:
            sheet_name = str(sheet_info.get("sheet_name") or "Sheet")
            header: List[str] = list(sheet_info.get("header", []) or [])
            rows: List[List[str]] = list(sheet_info.get("rows", []) or [])

            if not header or not rows:
                logger.info("[ExcelGeneralChunker] Sheet '%s' 无有效数据，跳过", sheet_name)
                continue

            sheet_root_chunk = self._row_builder.build_sheet_root_chunk(
                sheet_name=sheet_name,
                field_names=header,
                row_count=len(rows),
            )
            chunks.append(sheet_root_chunk)

            grouped_chunks = self._build_group_chunks(
                sheet_name=sheet_name,
                header=header,
                rows=rows,
                parent_node_id=sheet_root_chunk["metadata"]["node_id"],
                formula_none_cells=sheet_info.get("formula_none_cells"),
            )
            chunks.extend(grouped_chunks)
            sheet_root_chunk["metadata"]["child_ids"].extend(
                chunk["metadata"]["node_id"] for chunk in grouped_chunks
            )

        logger.info(
            "[ExcelGeneralChunker] 生成 %s 个 chunk（%s 个 Sheet，max_embed_tokens=%s）",
            len(chunks),
            len(sheets_data),
            self.max_embed_tokens,
        )
        return chunks

    def _build_group_chunks(
        self,
        *,
        sheet_name: str,
        header: List[str],
        rows: List[List[str]],
        parent_node_id: str,
        formula_none_cells: Any = None,
    ) -> List[Dict[str, Any]]:
        """按 chunk_size 贪心聚合多行；单行自身超限时回退到原有拆分逻辑。"""
        built_chunks: List[Dict[str, Any]] = []
        current_group: List[tuple[int, List[str]]] = []

        def flush_current_group() -> None:
            nonlocal current_group
            if not current_group:
                return
            built_chunks.append(
                self._build_group_chunk(
                    sheet_name=sheet_name,
                    header=header,
                    grouped_rows=current_group,
                    parent_node_id=parent_node_id,
                    depth=1,
                    formula_none_cells=formula_none_cells,
                )
            )
            current_group = []

        for row_index, row_values in enumerate(rows, start=1):
            normalized_row = [str(value or "") for value in row_values]
            single_row_group = [(row_index, normalized_row)]
            single_row_tokens = self._count_group_tokens(
                sheet_name=sheet_name,
                header=header,
                grouped_rows=single_row_group,
            )

            if single_row_tokens > self.chunk_size:
                flush_current_group()
                row_chunk, fragment_chunks = self._row_builder.build_row_chunk_family(
                    sheet_name=sheet_name,
                    row_index=row_index,
                    header=header,
                    values=normalized_row,
                    parent_node_id=parent_node_id,
                    parent_depth=1,
                    always_create_parent=False,
                )
                built_chunks.append(row_chunk)
                built_chunks.extend(fragment_chunks)
                continue

            candidate_group = current_group + single_row_group
            exceeds_row_limit = (
                self.rows_per_chunk > 0 and len(candidate_group) > self.rows_per_chunk
            )
            exceeds_chunk_limit = False
            if current_group:
                exceeds_chunk_limit = self._count_group_tokens(
                    sheet_name=sheet_name,
                    header=header,
                    grouped_rows=candidate_group,
                ) > self.chunk_size

            if current_group and (exceeds_row_limit or exceeds_chunk_limit):
                flush_current_group()
                current_group = single_row_group
            else:
                current_group = candidate_group

        flush_current_group()

        return built_chunks

    def _count_group_tokens(
        self,
        *,
        sheet_name: str,
        header: List[str],
        grouped_rows: List[tuple[int, List[str]]],
    ) -> int:
        """统一按当前 token 口径估算候选分组大小。"""
        markdown = rows_to_markdown(
            sheet_name,
            header,
            [row_values for _, row_values in grouped_rows],
            row_start=grouped_rows[0][0],
        )
        return count_tokens(
            markdown,
            self.token_count_method,
            self._token_handler.tokenizer,
        )

    def _build_group_chunk(
        self,
        *,
        sheet_name: str,
        header: List[str],
        grouped_rows: List[tuple[int, List[str]]],
        parent_node_id: str,
        depth: int,
        formula_none_cells: Any = None,
    ) -> Dict[str, Any]:
        """构建 general 模式多行聚合块。"""
        row_start = grouped_rows[0][0]
        row_end = grouped_rows[-1][0]
        row_values = [row for _, row in grouped_rows]
        markdown = rows_to_markdown(
            sheet_name,
            header,
            row_values,
            row_start=row_start,
        )
        row_indices = [row_index for row_index, _ in grouped_rows]

        metadata: Dict[str, Any] = {
            "node_id": uuid4().hex,
            "parent_id": parent_node_id,
            "child_ids": [],
            "depth": depth,
            "is_root": False,
            "is_leaf": True,
            "is_hierarchical": True,
            "should_vectorize": True,
            "chunk_strategy": "excel_general",
            "chunk_role": "excel_general_group",
            "sheet_name": sheet_name,
            "row_start": row_start,
            "row_end": row_end,
            "row_count": len(grouped_rows),
            "source_anchors": [
                self._row_builder._build_row_anchor(sheet_name, row_index)
                for row_index in row_indices
            ],
            "page_numbers": [],
            "source_element_indices": row_indices,
        }
        if isinstance(formula_none_cells, int) and formula_none_cells > 0:
            metadata["formula_none_cells"] = formula_none_cells

        return {
            "text": markdown,
            "type": "table",
            "content_blocks": [
                {
                    "block_id": "b1",
                    "type": "table",
                    "text": markdown,
                    "source_refs": [
                        {
                            "ref_type": "excel_row",
                            "sheet_name": sheet_name,
                            "row_index": row_index,
                            "element_index": row_index,
                            "element_type": "table_row",
                            "field_names": list(header),
                        }
                        for row_index in row_indices
                    ],
                }
            ],
            "metadata": metadata,
        }

    def _fallback_single_chunk(
        self,
        text: str,
        metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """兜底：无结构化数据时将整体文本包成单块。"""
        if not text:
            return []

        safe_text = self._token_handler.handle_general_chunk(text)
        return [
            {
                "text": safe_text,
                "type": "table",
                "content_blocks": [
                    {
                        "block_id": "b1",
                        "type": "table",
                        "text": text,
                        "source_refs": [],
                    }
                ],
                "metadata": {
                    "chunk_strategy": "excel_general",
                    "chunk_role": "excel_general_fallback",
                    "content_truncated": safe_text != text,
                    "source_anchors": [],
                    "page_numbers": [],
                    "source_element_indices": [],
                },
            }
        ]
