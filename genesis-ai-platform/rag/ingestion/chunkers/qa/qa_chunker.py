"""
QA 分块器

策略：
- 短答案：输出单个 QA 叶子块，完整携带问题与答案
- 长答案：输出 1 个 QA 父块 + N 个答案子块
- 分层协议与表格型知识库保持一致，便于前端统一展示层级内容
"""

import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from rag.enums import ChunkType
from utils.qa_markdown import build_qa_markdown_text

from ..base import BaseChunker

logger = logging.getLogger(__name__)


class QAChunker(BaseChunker):
    """QA 分块器。"""

    def chunk(self, text: str, metadata: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        qa_items = list((metadata or {}).get("qa_items") or [])
        if not qa_items:
            logger.warning("[QAChunker] metadata 中未找到 qa_items")
            return []

        chunks: List[Dict[str, Any]] = []
        for idx, item in enumerate(qa_items):
            qa_row_id = item.get("qa_row_id")
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            aliases = [str(v).strip() for v in (item.get("similar_questions") or []) if str(v).strip()]
            tags = [str(v).strip() for v in (item.get("tags") or []) if str(v).strip()]
            category = str(item.get("category") or "").strip()

            if not question or not answer:
                continue

            answer_parts = self._split_answer(answer)
            source_row = item.get("source_row")
            source_sheet_name = item.get("source_sheet_name")
            source_mode = str(item.get("source_mode") or "").strip() or None
            position = item.get("position")
            source_element_indices = self._build_source_element_indices(source_row, position)
            source_anchors = self._build_source_anchors(source_sheet_name, source_row, qa_row_id)

            if len(answer_parts) == 1:
                row_node_id = self._new_node_id()
                chunks.append(
                    self._build_leaf_chunk(
                        node_id=row_node_id,
                        qa_row_id=qa_row_id,
                        question=question,
                        answer=answer,
                        aliases=aliases,
                        tags=tags,
                        category=category,
                        source_row=source_row,
                        source_sheet_name=source_sheet_name,
                        source_mode=source_mode,
                        source_anchors=source_anchors,
                        source_element_indices=source_element_indices,
                    )
                )
                continue

            row_node_id = self._new_node_id()
            child_ids = [self._new_node_id() for _ in answer_parts]
            chunks.append(
                self._build_parent_chunk(
                    node_id=row_node_id,
                    child_ids=child_ids,
                    qa_row_id=qa_row_id,
                    question=question,
                    answer=answer,
                    aliases=aliases,
                    tags=tags,
                    category=category,
                    source_row=source_row,
                    source_sheet_name=source_sheet_name,
                    source_mode=source_mode,
                    source_anchors=source_anchors,
                    source_element_indices=source_element_indices,
                )
            )

            for part_index, (child_node_id, answer_part) in enumerate(zip(child_ids, answer_parts), start=1):
                chunks.append(
                    self._build_answer_fragment_chunk(
                        node_id=child_node_id,
                        parent_node_id=row_node_id,
                        qa_row_id=qa_row_id,
                        question=question,
                        answer_part=answer_part,
                        aliases=aliases,
                        tags=tags,
                        category=category,
                        source_row=source_row,
                        source_sheet_name=source_sheet_name,
                        source_mode=source_mode,
                        source_anchors=source_anchors,
                        source_element_indices=source_element_indices,
                        answer_part_index=part_index,
                        answer_part_total=len(answer_parts),
                    )
                )

        logger.info("[QAChunker] 处理完成，共 %s 个 QA 分块", len(chunks))
        return chunks

    @staticmethod
    def _build_full_row_text(question: str, answer: str, aliases: List[str], tags: List[str], category: str) -> str:
        return build_qa_markdown_text(
            question=question,
            answer=answer,
            similar_questions=aliases,
            category=category,
            tags=tags,
        )

    @staticmethod
    def _build_answer_fragment_text(question: str, answer_part: str) -> str:
        return build_qa_markdown_text(
            question=question,
            answer=answer_part,
            similar_questions=[],
            category="",
            tags=[],
        )

    def _build_leaf_chunk(
        self,
        *,
        node_id: str,
        qa_row_id: Optional[str],
        question: str,
        answer: str,
        aliases: List[str],
        tags: List[str],
        category: str,
        source_row: Any,
        source_sheet_name: Any,
        source_mode: Optional[str],
        source_anchors: List[str],
        source_element_indices: List[int],
    ) -> Dict[str, Any]:
        """构建短答案叶子块，直接参与检索。"""
        text = self._build_full_row_text(question, answer, aliases, tags, category)
        return {
            "text": text,
            "type": ChunkType.QA.value,
            "content_blocks": self._build_qa_content_blocks(
                question=question,
                answer=answer,
                aliases=aliases,
                tags=tags,
                category=category,
            ),
            "metadata": self._build_common_metadata(
                node_id=node_id,
                row_id=node_id,
                parent_id=None,
                child_ids=[],
                depth=0,
                is_leaf=True,
                should_vectorize=True,
                chunk_role="qa_row",
                qa_row_id=qa_row_id,
                question=question,
                aliases=aliases,
                tags=tags,
                category=category,
                source_row=source_row,
                source_sheet_name=source_sheet_name,
                source_mode=source_mode,
                source_anchors=source_anchors,
                source_element_indices=source_element_indices,
            ),
        }

    def _build_parent_chunk(
        self,
        *,
        node_id: str,
        child_ids: List[str],
        qa_row_id: Optional[str],
        question: str,
        answer: str,
        aliases: List[str],
        tags: List[str],
        category: str,
        source_row: Any,
        source_sheet_name: Any,
        source_mode: Optional[str],
        source_anchors: List[str],
        source_element_indices: List[int],
    ) -> Dict[str, Any]:
        """构建长答案父块，仅用于层级展示与聚合。"""
        text = self._build_full_row_text(question, answer, aliases, tags, category)
        return {
            "text": text,
            "type": ChunkType.QA.value,
            "content_blocks": self._build_qa_content_blocks(
                question=question,
                answer=answer,
                aliases=aliases,
                tags=tags,
                category=category,
            ),
            "metadata": self._build_common_metadata(
                node_id=node_id,
                row_id=node_id,
                parent_id=None,
                child_ids=child_ids,
                depth=0,
                is_leaf=False,
                should_vectorize=False,
                chunk_role="qa_row",
                qa_row_id=qa_row_id,
                question=question,
                aliases=aliases,
                tags=tags,
                category=category,
                source_row=source_row,
                source_sheet_name=source_sheet_name,
                source_mode=source_mode,
                source_anchors=source_anchors,
                source_element_indices=source_element_indices,
                exclude_from_retrieval=True,
            ),
        }

    def _build_answer_fragment_chunk(
        self,
        *,
        node_id: str,
        parent_node_id: str,
        qa_row_id: Optional[str],
        question: str,
        answer_part: str,
        aliases: List[str],
        tags: List[str],
        category: str,
        source_row: Any,
        source_sheet_name: Any,
        source_mode: Optional[str],
        source_anchors: List[str],
        source_element_indices: List[int],
        answer_part_index: int,
        answer_part_total: int,
    ) -> Dict[str, Any]:
        """构建长答案子块，负责检索召回。"""
        text = self._build_answer_fragment_text(question, answer_part)
        return {
            "text": text,
            "type": ChunkType.QA.value,
            "content_blocks": self._build_qa_content_blocks(
                question=question,
                answer=answer_part,
                aliases=[],
                tags=[],
                category="",
            ),
            "metadata": {
                **self._build_common_metadata(
                    node_id=node_id,
                    row_id=parent_node_id,
                    parent_id=parent_node_id,
                    child_ids=[],
                    depth=1,
                    is_leaf=True,
                    should_vectorize=True,
                    chunk_role="qa_answer_fragment",
                    qa_row_id=qa_row_id,
                    question=question,
                    aliases=aliases,
                    tags=tags,
                    category=category,
                    source_row=source_row,
                    source_sheet_name=source_sheet_name,
                    source_mode=source_mode,
                    source_anchors=source_anchors,
                    source_element_indices=source_element_indices,
                ),
                "answer_part_index": answer_part_index,
                "answer_part_total": answer_part_total,
            },
        }

    def _build_common_metadata(
        self,
        *,
        node_id: str,
        row_id: str,
        parent_id: Optional[str],
        child_ids: List[str],
        depth: int,
        is_leaf: bool,
        should_vectorize: bool,
        chunk_role: str,
        qa_row_id: Optional[str],
        question: str,
        aliases: List[str],
        tags: List[str],
        category: str,
        source_row: Any,
        source_sheet_name: Any,
        source_mode: Optional[str],
        source_anchors: List[str],
        source_element_indices: List[int],
        exclude_from_retrieval: bool = False,
    ) -> Dict[str, Any]:
        """统一构建 QA 层级元数据。"""
        metadata: Dict[str, Any] = {
            "node_id": node_id,
            "row_id": row_id,
            "parent_id": parent_id,
            "child_ids": list(child_ids),
            "depth": depth,
            "is_root": parent_id is None,
            "is_leaf": is_leaf,
            "is_hierarchical": True,
            "should_vectorize": should_vectorize,
            "chunk_strategy": "qa",
            "chunk_role": chunk_role,
            "qa_row_id": qa_row_id,
            "question": question,
            "similar_questions": list(aliases),
            "tags": list(tags),
            "category": category or None,
            "source_mode": source_mode,
            "source_row": source_row,
            "source_sheet_name": source_sheet_name,
            "source_anchors": list(source_anchors),
            "page_numbers": [],
            "source_element_indices": list(source_element_indices),
        }
        if exclude_from_retrieval:
            metadata["exclude_from_retrieval"] = True
        return metadata

    @staticmethod
    def _build_qa_content_blocks(
        *,
        question: str,
        answer: str,
        aliases: List[str],
        tags: List[str],
        category: str,
    ) -> List[Dict[str, Any]]:
        """统一生成 QA 结构化正文流。"""
        blocks: List[Dict[str, Any]] = [
            {
                "block_id": "b1",
                "type": "text",
                "text": "## 问题",
                "source_refs": [],
            },
            {
                "block_id": "b2",
                "type": "text",
                "text": question,
                "source_refs": [],
            }
        ]
        block_index = 3
        if aliases:
            blocks.append(
                {
                    "block_id": f"b{block_index}",
                    "type": "text",
                    "text": "## 相似问题",
                    "source_refs": [],
                }
            )
            block_index += 1
            for alias in aliases:
                blocks.append(
                    {
                        "block_id": f"b{block_index}",
                        "type": "text",
                        "text": f"- {alias}",
                        "source_refs": [],
                    }
                )
                block_index += 1
        if category:
            blocks.append(
                {
                    "block_id": f"b{block_index}",
                    "type": "text",
                    "text": "## 分类",
                    "source_refs": [],
                }
            )
            block_index += 1
            blocks.append(
                {
                    "block_id": f"b{block_index}",
                    "type": "text",
                    "text": category,
                    "source_refs": [],
                }
            )
            block_index += 1
        if tags:
            blocks.append(
                {
                    "block_id": f"b{block_index}",
                    "type": "text",
                    "text": "## 标签",
                    "source_refs": [],
                }
            )
            block_index += 1
            for tag in tags:
                blocks.append(
                    {
                        "block_id": f"b{block_index}",
                        "type": "text",
                        "text": f"- {tag}",
                        "source_refs": [],
                    }
                )
                block_index += 1
        blocks.append(
            {
                "block_id": f"b{block_index}",
                "type": "text",
                "text": "## 答案",
                "source_refs": [],
            }
        )
        block_index += 1
        blocks.append(
            {
                "block_id": f"b{block_index}",
                "type": "text",
                "text": answer,
                "source_refs": [],
            }
        )
        return blocks

    @staticmethod
    def _build_source_anchors(
        source_sheet_name: Any,
        source_row: Any,
        qa_row_id: Optional[str],
    ) -> List[str]:
        """为 QA 生成稳定锚点，导入型优先保留源行位置。"""
        if isinstance(source_sheet_name, str) and source_sheet_name.strip() and isinstance(source_row, int) and source_row > 0:
            return [f"{source_sheet_name}!R{source_row}"]
        if isinstance(source_row, int) and source_row > 0:
            return [f"R{source_row}"]
        if qa_row_id:
            return [f"qa:{qa_row_id}"]
        return []

    @staticmethod
    def _build_source_element_indices(source_row: Any, position: Any) -> List[int]:
        """QA 无页码时，使用源行号或稳定顺序做轻量定位。"""
        if isinstance(source_row, int) and source_row > 0:
            return [source_row]
        if isinstance(position, int) and position >= 0:
            return [position + 1]
        return []

    def _split_answer(self, answer: str) -> List[str]:
        """优先按段落/句子拆分，超限时再退化为定长切分。"""
        normalized = answer.strip()
        if not normalized:
            return []
        if len(normalized) <= self.chunk_size:
            return [normalized]

        semantic_units = self._split_semantic_units(normalized)
        merged_parts: List[str] = []
        current_part = ""
        for unit in semantic_units:
            unit = unit.strip()
            if not unit:
                continue
            candidate = f"{current_part}\n{unit}".strip() if current_part else unit
            if len(candidate) <= self.chunk_size:
                current_part = candidate
                continue

            if current_part:
                merged_parts.append(current_part)
                current_part = ""

            if len(unit) <= self.chunk_size:
                current_part = unit
            else:
                merged_parts.extend(self._slice_with_overlap(unit))

        if current_part:
            merged_parts.append(current_part)

        return [part for part in merged_parts if part.strip()]

    @staticmethod
    def _split_semantic_units(answer: str) -> List[str]:
        """先按段落，再按句子切分，尽量减少生硬断句。"""
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", answer) if part.strip()]
        if not paragraphs:
            paragraphs = [answer]

        units: List[str] = []
        for paragraph in paragraphs:
            if len(paragraph) <= 200:
                units.append(paragraph)
                continue
            sentences = [
                part.strip()
                for part in re.split(r"(?<=[。！？!?；;])|(?<=\.)\s+", paragraph)
                if part.strip()
            ]
            units.extend(sentences or [paragraph])
        return units

    def _slice_with_overlap(self, text: str) -> List[str]:
        """最后兜底的重叠切分，避免超长段落无法落盘。"""
        parts: List[str] = []
        start = 0
        step = max(1, self.chunk_size - self.chunk_overlap)
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            parts.append(text[start:end].strip())
            if end >= len(text):
                break
            start += step
        return [part for part in parts if part]

    @staticmethod
    def _new_node_id() -> str:
        """生成层级节点 ID。"""
        return uuid4().hex
