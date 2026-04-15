"""
Excel 行级层级分块构建器。

统一输出三类节点：
1. sheet 根节点：`excel_sheet_root`
2. 行节点：`excel_row`
3. 行子片段：`excel_row_fragment`
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from .excel_token_handler import ExcelTokenHandler, count_tokens
from rag.ingestion.parsers.excel.excel_parser_utils import single_row_to_markdown

logger = logging.getLogger(__name__)


class ExcelRowChunkBuilder:
    """负责构建 Excel 的统一层级节点。"""

    def __init__(
        self,
        *,
        strategy_name: str,
        token_handler: ExcelTokenHandler,
        max_embed_tokens: int,
        token_count_method: str,
        key_columns: Optional[Sequence[str]] = None,
        leaf_chunk_token_limit: Optional[int] = None,
    ) -> None:
        self.strategy_name = strategy_name
        self.token_handler = token_handler
        self.max_embed_tokens = max_embed_tokens
        self.token_count_method = token_count_method
        self.key_columns = [str(item) for item in (key_columns or []) if str(item).strip()]
        # 叶子块预算优先尊重业务分块大小；未显式传入时回退到向量模型预算。
        self.leaf_chunk_token_limit = max(1, int(leaf_chunk_token_limit or max_embed_tokens))

    def _should_emit_source_ref_field_names(self) -> bool:
        """仅通用型 Excel 保留块级字段范围；表格型知识库避免重复存储。"""
        return self.strategy_name != "excel_table"

    def build_sheet_root_chunk(
        self,
        *,
        sheet_name: str,
        field_names: List[str],
        row_count: int,
        filter_column_names: Optional[Sequence[str]] = None,
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """构建工作表级根节点，统一两种 Excel 策略的顶层结构。"""
        node_id = str(node_id or self._new_node_id())
        filter_names = [str(item) for item in (filter_column_names or []) if str(item).strip()]
        content = self._build_sheet_root_text(
            sheet_name=sheet_name,
            field_names=field_names,
            row_count=row_count,
            filter_column_names=filter_names,
        )
        metadata: Dict[str, Any] = {
            "node_id": node_id,
            "parent_id": None,
            "child_ids": [],
            "depth": 0,
            "is_root": True,
            "is_leaf": False,
            "is_hierarchical": True,
            "should_vectorize": False,
            "exclude_from_retrieval": True,
            "chunk_strategy": self.strategy_name,
            "chunk_role": "excel_sheet_root",
            "sheet_name": sheet_name,
            "field_names": list(field_names),
            "row_count": row_count,
            "source_anchors": [sheet_name] if sheet_name else [],
            "page_numbers": [],
            "source_element_indices": [],
        }
        if filter_names:
            metadata["filter_column_names"] = filter_names

        return {
            "text": content,
            "type": "summary",
            "content_blocks": [
                {
                    "block_id": "b1",
                    "type": "table",
                    "text": content,
                    "source_refs": [],
                }
            ],
            "metadata": metadata,
        }

    def build_row_chunk_family(
        self,
        *,
        sheet_name: str,
        row_index: int,
        row_uid: Optional[str] = None,
        table_row_id: Optional[str] = None,
        header: List[str],
        values: List[str],
        parent_node_id: Optional[str] = None,
        parent_depth: int = 0,
        filter_fields: Optional[Dict[str, str]] = None,
        always_create_parent: bool = True,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        构建单行分块家族。

        返回：
        1. 家族根节点：未拆分时为 `excel_row` 叶子节点；拆分时为 `excel_row` 中间节点
        2. 后代节点：仅在拆分后返回 `excel_row_fragment`
        """
        normalized_pairs = self._build_non_empty_pairs(header, values)
        if not normalized_pairs:
            raise ValueError("行数据为空，无法构建 Excel 分块家族")

        key_pairs, payload_pairs = self._split_key_pairs(normalized_pairs)
        identity_text = self._build_identity_text(sheet_name, row_index, key_pairs)
        safe_prefix = self._build_safe_prefix(identity_text)
        fragment_groups = self._build_fragment_groups(
            payload_pairs=payload_pairs or key_pairs,
            safe_prefix=safe_prefix,
        )

        if self._should_emit_row_leaf(
            fragment_groups=fragment_groups,
            always_create_parent=always_create_parent,
        ):
            row_leaf_chunk = self._build_row_chunk(
                row_node_id=self._new_node_id(),
                parent_node_id=parent_node_id,
                depth=parent_depth,
                sheet_name=sheet_name,
                row_index=row_index,
                row_uid=row_uid,
                table_row_id=table_row_id,
                field_names=header,
                values=values,
                identity_text=identity_text,
                key_pairs=key_pairs,
                filter_fields=filter_fields,
                child_ids=[],
                should_vectorize=True,
                is_leaf=True,
                content_text=self._build_group_text("", normalized_pairs),
            )
            return row_leaf_chunk, []

        row_node_id = self._new_node_id()
        fragment_chunks = self._build_fragment_chunks(
            row_node_id=row_node_id,
            fragment_groups=fragment_groups,
            sheet_name=sheet_name,
            row_index=row_index,
            row_uid=row_uid,
            table_row_id=table_row_id,
            identity_text=identity_text,
            key_pairs=key_pairs,
            filter_fields=filter_fields,
            depth=parent_depth + 1,
        )
        row_chunk = self._build_row_chunk(
            row_node_id=row_node_id,
            parent_node_id=parent_node_id,
            depth=parent_depth,
            sheet_name=sheet_name,
            row_index=row_index,
            row_uid=row_uid,
            table_row_id=table_row_id,
            field_names=header,
            values=values,
            identity_text=identity_text,
            key_pairs=key_pairs,
            filter_fields=filter_fields,
            child_ids=[chunk["metadata"]["node_id"] for chunk in fragment_chunks],
            should_vectorize=False,
            is_leaf=False,
            content_text=f"{identity_text}\n{single_row_to_markdown(header, values)}".strip(),
        )
        return row_chunk, fragment_chunks

    def _build_sheet_root_text(
        self,
        *,
        sheet_name: str,
        field_names: Sequence[str],
        row_count: int,
        filter_column_names: Sequence[str],
    ) -> str:
        """构建工作表根节点文本。"""
        parts = [f"工作表: {sheet_name}"]
        if row_count > 0:
            parts.append(f"行数: {row_count}")
        if field_names:
            parts.append(f"字段: {'、'.join(field_names)}")
        if filter_column_names:
            parts.append(f"过滤列: {'、'.join(filter_column_names)}")
        return "；".join(parts)

    def _build_non_empty_pairs(
        self,
        header: Sequence[str],
        values: Sequence[str],
    ) -> List[Tuple[str, str]]:
        """仅保留非空字段，减少元数据和检索文本噪音。"""
        pairs: List[Tuple[str, str]] = []
        for col, val in zip(header, values):
            col_name = str(col).strip()
            cell_value = str(val or "").strip()
            if not col_name or not cell_value:
                continue
            pairs.append((col_name, cell_value))
        return pairs

    def _split_key_pairs(
        self,
        pairs: Sequence[Tuple[str, str]],
    ) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """按配置拆分身份字段和正文负载字段。"""
        if not self.key_columns:
            return [], list(pairs)

        key_name_set = {item for item in self.key_columns}
        key_pairs = [item for item in pairs if item[0] in key_name_set]
        payload_pairs = [item for item in pairs if item[0] not in key_name_set]
        return key_pairs, payload_pairs

    def _build_identity_text(
        self,
        sheet_name: str,
        row_index: int,
        key_pairs: Sequence[Tuple[str, str]],
    ) -> str:
        """构建行身份文本，便于跨片段聚合和人工定位。"""
        base = f"[{sheet_name}] 第{row_index}行"
        if not key_pairs:
            return base

        key_text = "; ".join(f"{name}: {value}" for name, value in key_pairs)
        return f"{base}; {key_text}"

    def _build_safe_prefix(self, identity_text: str) -> str:
        """控制身份前缀长度，避免子片段被前缀挤爆预算。"""
        candidates = [
            f"{identity_text}; ",
            f"{identity_text.split(';', 1)[0]}; ",
            "",
        ]

        for candidate in candidates:
            if not candidate:
                return ""
            token_size = count_tokens(candidate, self.token_count_method, self.token_handler.tokenizer)
            if token_size <= max(32, int(self.leaf_chunk_token_limit * 0.35)):
                return candidate

        return ""

    def _build_fragment_groups(
        self,
        *,
        payload_pairs: Sequence[Tuple[str, str]],
        safe_prefix: str,
    ) -> List[Dict[str, Any]]:
        """按预算聚合字段，必要时继续拆分超长字段。"""
        groups: List[Dict[str, Any]] = []
        current_pairs: List[Tuple[str, str]] = []

        def flush_current_group() -> None:
            if not current_pairs:
                return
            groups.append(self._make_group_from_pairs(current_pairs, safe_prefix))
            current_pairs.clear()

        for field_name, field_value in payload_pairs:
            field_text = self._build_group_text(safe_prefix, current_pairs + [(field_name, field_value)])
            token_size = count_tokens(
                field_text,
                self.token_count_method,
                self.token_handler.tokenizer,
            )

            if token_size <= self.leaf_chunk_token_limit:
                current_pairs.append((field_name, field_value))
                continue

            flush_current_group()

            single_field_text = self._build_group_text(safe_prefix, [(field_name, field_value)])
            single_field_tokens = count_tokens(
                single_field_text,
                self.token_count_method,
                self.token_handler.tokenizer,
            )
            if single_field_tokens <= self.leaf_chunk_token_limit:
                current_pairs.append((field_name, field_value))
                continue

            groups.extend(
                self._split_oversized_field(
                    field_name=field_name,
                    field_value=field_value,
                    safe_prefix=safe_prefix,
                )
            )

        flush_current_group()
        return groups

    def _make_group_from_pairs(
        self,
        pairs: Sequence[Tuple[str, str]],
        safe_prefix: str,
    ) -> Dict[str, Any]:
        """将若干字段合成一个行子片段描述。"""
        field_names = [name for name, _ in pairs]
        values = [value for _, value in pairs]
        return {
            "field_names": field_names,
            "values": values,
            "content": self._build_group_text(safe_prefix, pairs),
            "is_overflow": False,
        }

    def _split_oversized_field(
        self,
        *,
        field_name: str,
        field_value: str,
        safe_prefix: str,
    ) -> List[Dict[str, Any]]:
        """当单个字段也超限时，继续拆成多个子片段。"""
        parts = self.token_handler.handle_row(
            header=[field_name],
            values=[field_value],
            text_prefix=safe_prefix,
            repeat_prefix_each_chunk=True,
        )

        if not parts:
            logger.warning("[ExcelRowChunkBuilder] 超长字段拆分失败，字段=%s", field_name)
            return [
                {
                    "field_names": [field_name],
                    "values": [field_value],
                    "content": self._build_group_text(safe_prefix, [(field_name, field_value)]),
                    "is_overflow": True,
                }
            ]

        split_groups: List[Dict[str, Any]] = []
        total_parts = len(parts)
        field_prefix = f"{field_name}: "
        for index, part in enumerate(parts, start=1):
            content = str(part.get("content") or "")
            value_text = content
            if safe_prefix and value_text.startswith(safe_prefix):
                value_text = value_text[len(safe_prefix):]
            if value_text.startswith(field_prefix):
                value_text = value_text[len(field_prefix):]

            split_groups.append(
                {
                    "field_names": [field_name if total_parts == 1 else f"{field_name}_{index}"],
                    "values": [value_text],
                    "content": content,
                    "is_overflow": True,
                }
            )
        return split_groups

    def _should_emit_row_leaf(
        self,
        *,
        fragment_groups: Sequence[Dict[str, Any]],
        always_create_parent: bool,
    ) -> bool:
        """整行本身可直接检索时，不额外生成中间节点。"""
        if always_create_parent:
            return False
        if len(fragment_groups) != 1:
            return False
        return not bool(fragment_groups[0].get("is_overflow"))

    def _build_group_text(
        self,
        safe_prefix: str,
        pairs: Sequence[Tuple[str, str]],
    ) -> str:
        """构建向量化文本。"""
        kv_text = "; ".join(f"{name}: {value}" for name, value in pairs)
        return f"{safe_prefix}{kv_text}" if safe_prefix else kv_text

    def _build_row_chunk(
        self,
        *,
        row_node_id: str,
        parent_node_id: Optional[str],
        depth: int,
        sheet_name: str,
        row_index: int,
        row_uid: Optional[str],
        table_row_id: Optional[str],
        field_names: List[str],
        values: List[str],
        identity_text: str,
        key_pairs: Sequence[Tuple[str, str]],
        filter_fields: Optional[Dict[str, str]],
        child_ids: List[str],
        should_vectorize: bool,
        is_leaf: bool,
        content_text: str,
    ) -> Dict[str, Any]:
        """构建行节点。"""
        row_table_markdown = single_row_to_markdown(field_names, values)
        metadata: Dict[str, Any] = {
            "node_id": row_node_id,
            "row_id": row_node_id,
            "parent_id": parent_node_id,
            "child_ids": list(child_ids),
            "depth": depth,
            "is_root": parent_node_id is None,
            "is_leaf": is_leaf,
            "is_hierarchical": True,
            "should_vectorize": should_vectorize,
            "chunk_strategy": self.strategy_name,
            "chunk_role": "excel_row",
            "sheet_name": sheet_name,
            "row_index": row_index,
            "row_identity_text": identity_text,
            "identity_field_names": [name for name, _ in key_pairs],
            "source_anchors": [self._build_row_anchor(sheet_name, row_index)],
            "page_numbers": [],
            "source_element_indices": [row_index],
        }
        if filter_fields:
            metadata["filter_fields"] = filter_fields
        if row_uid:
            metadata["row_uid"] = row_uid
        if table_row_id:
            metadata["table_row_id"] = table_row_id

        return {
            "text": content_text,
            "type": "table",
            "content_blocks": [
                {
                    "block_id": "b1",
                    "type": "table",
                    "text": row_table_markdown,
                    "source_refs": [
                        {
                            **{
                                "ref_type": "excel_row",
                                "sheet_name": sheet_name,
                                "row_index": row_index,
                                "row_uid": row_uid,
                                "table_row_id": table_row_id,
                                "element_index": row_index,
                                "element_type": "table_row",
                            },
                            **(
                                {"field_names": list(field_names)}
                                if self._should_emit_source_ref_field_names()
                                else {}
                            ),
                        }
                    ],
                }
            ],
            "metadata": metadata,
        }

    def _build_fragment_chunks(
        self,
        *,
        row_node_id: str,
        fragment_groups: Sequence[Dict[str, Any]],
        sheet_name: str,
        row_index: int,
        row_uid: Optional[str],
        table_row_id: Optional[str],
        identity_text: str,
        key_pairs: Sequence[Tuple[str, str]],
        filter_fields: Optional[Dict[str, str]],
        depth: int,
    ) -> List[Dict[str, Any]]:
        """构建行子片段叶子节点。"""
        fragment_chunks: List[Dict[str, Any]] = []
        for group in fragment_groups:
            field_names = [str(item) for item in group.get("field_names", [])]
            values = [str(item) for item in group.get("values", [])]
            content = str(group.get("content") or "").strip()
            if not content or not field_names or not values:
                continue

            metadata: Dict[str, Any] = {
                "node_id": self._new_node_id(),
                "row_id": row_node_id,
                "parent_id": row_node_id,
                "child_ids": [],
                "depth": depth,
                "is_root": False,
                "is_leaf": True,
                "is_hierarchical": True,
                "should_vectorize": True,
                "chunk_strategy": self.strategy_name,
                "chunk_role": "excel_row_fragment",
                "sheet_name": sheet_name,
                "row_index": row_index,
                "row_identity_text": identity_text,
                "identity_field_names": [name for name, _ in key_pairs],
                "is_row_overflow": bool(group.get("is_overflow")),
                "source_anchors": [self._build_row_anchor(sheet_name, row_index)],
                "page_numbers": [],
                "source_element_indices": [row_index],
            }
            if filter_fields:
                metadata["filter_fields"] = filter_fields
            if row_uid:
                metadata["row_uid"] = row_uid
            if table_row_id:
                metadata["table_row_id"] = table_row_id

            fragment_chunks.append(
                {
                    "text": content,
                    "type": "table",
                    "content_blocks": [
                        {
                            "block_id": "b1",
                            "type": "table",
                            "text": single_row_to_markdown(field_names, values),
                            "source_refs": [
                                {
                                    **{
                                        "ref_type": "excel_row",
                                        "sheet_name": sheet_name,
                                        "row_index": row_index,
                                        "row_uid": row_uid,
                                        "table_row_id": table_row_id,
                                        "element_index": row_index,
                                        "element_type": "table_row_fragment",
                                    },
                                    **(
                                        {"field_names": list(field_names)}
                                        if self._should_emit_source_ref_field_names()
                                        else {}
                                    ),
                                }
                            ],
                        }
                    ],
                    "metadata": metadata,
                }
            )

        return fragment_chunks

    def _build_row_anchor(self, sheet_name: str, row_index: int) -> str:
        """为非 PDF 行节点生成稳定锚点。"""
        return f"{sheet_name}!R{row_index}"

    def _new_node_id(self) -> str:
        """生成节点 ID。"""
        return uuid4().hex
