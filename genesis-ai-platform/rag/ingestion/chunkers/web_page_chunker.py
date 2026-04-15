"""
网页专用分块器

目标：
1. 优先消费 structured_sections，按 DOM 分区输出层级 chunk
2. 表格块始终先保留完整父块；超限时再拆成子块
3. 子块大小严格满足 min(模型上下文限制, max_embed_tokens)
4. 子块文本必须携带标题路径，保证脱离原文后仍可理解
5. 结构定义参考 Markdown / Excel 表格分块的父子关系约定
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Sequence
from uuid import uuid4

from lxml import html as lxml_html  # type: ignore[import-untyped]

from rag.utils.token_utils import count_tokens

from .base import BaseChunker

logger = logging.getLogger(__name__)


class WebPageChunker(BaseChunker):
    """网页专用分块器。"""

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        embedding_model_limit: int = 512,
        max_embed_tokens: int | None = None,
        **kwargs,
    ):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs)
        self.embedding_model_limit = max(128, int(embedding_model_limit or 512))
        requested_max_embed_tokens = int(max_embed_tokens or self.embedding_model_limit)
        self.max_embed_tokens = max(128, requested_max_embed_tokens)
        # 网页结构化分块的叶子预算只受模型安全上限与 max_embed_tokens 共同控制；
        # chunk_size 在这里退化为内部组织参数，不再参与最终叶子块上限收口。
        self.effective_leaf_limit = max(64, min(self.embedding_model_limit, self.max_embed_tokens))

    def chunk(self, text: str, metadata: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        metadata = metadata or {}
        structured_sections = list(metadata.get("structured_sections") or [])
        logger.info(
            "[WebPageChunker] 开始分块: text_length=%s, section_count=%s, chunk_size=%s, overlap=%s, embedding_limit=%s, max_embed_tokens=%s",
            len(str(text or "")),
            len(structured_sections),
            self.chunk_size,
            self.chunk_overlap,
            self.embedding_model_limit,
            self.max_embed_tokens,
        )

        if structured_sections:
            chunks = self._chunk_structured_sections(structured_sections, metadata)
            if chunks:
                logger.info("[WebPageChunker] 使用 structured_sections 完成分块: chunk_count=%s", len(chunks))
                return chunks

        fallback_chunks = self._chunk_plain_text(str(text or ""), metadata)
        logger.info("[WebPageChunker] 退化为纯文本分块: chunk_count=%s", len(fallback_chunks))
        return fallback_chunks

    def _chunk_structured_sections(
        self,
        structured_sections: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        for section_index, section in enumerate(structured_sections):
            section_markdown = self._normalize_text(section.get("markdown") or "")
            section_blocks = list(section.get("blocks") or [])
            if not section_markdown and not section_blocks:
                continue

            heading_path = [str(item).strip() for item in list(section.get("heading_path") or []) if str(item).strip()]
            title = str(section.get("title") or "").strip()
            if title and not heading_path:
                heading_path = [title]

            section_chunk = self._build_section_root_chunk(
                section=section,
                metadata=metadata,
                heading_path=heading_path,
                section_markdown=section_markdown,
                section_index=section_index,
            )
            chunks.append(section_chunk)

            child_chunks: List[Dict[str, Any]] = []
            pending_text_blocks: List[Dict[str, Any]] = []

            def flush_text_blocks() -> None:
                nonlocal pending_text_blocks
                if not pending_text_blocks:
                    return
                child_chunks.extend(
                    self._build_text_child_chunks(
                        pending_text_blocks,
                        heading_path=heading_path,
                        metadata=metadata,
                        section_index=section_index,
                    )
                )
                pending_text_blocks = []

            for block in section_blocks:
                block_type = str(block.get("type") or "text").strip().lower()
                if block_type == "table":
                    flush_text_blocks()
                    child_chunks.extend(
                        self._build_table_chunk_family(
                            block=block,
                            heading_path=heading_path,
                            metadata=metadata,
                            section_index=section_index,
                        )
                    )
                elif block_type != "heading":
                    pending_text_blocks.append(block)
            flush_text_blocks()

            root_child_ids = [
                child["metadata"]["node_id"]
                for child in child_chunks
                if child["metadata"].get("parent_id") is None
            ]
            section_chunk["metadata"]["child_ids"] = root_child_ids
            section_chunk["metadata"]["is_leaf"] = not bool(root_child_ids)
            for child in child_chunks:
                if not child["metadata"].get("parent_id"):
                    child["metadata"]["parent_id"] = section_chunk["metadata"]["node_id"]
                    child["metadata"]["depth"] = 1
                    child["metadata"]["is_root"] = False
                child["metadata"]["section_id"] = section_chunk["metadata"]["node_id"]
            chunks.extend(child_chunks)

        self._refresh_topology(chunks)
        return chunks

    def _build_section_root_chunk(
        self,
        *,
        section: Dict[str, Any],
        metadata: Dict[str, Any],
        heading_path: List[str],
        section_markdown: str,
        section_index: int,
    ) -> Dict[str, Any]:
        source_refs = self._extract_block_source_refs(section.get("blocks") or [], metadata)
        node_id = uuid4().hex
        return {
            "text": section_markdown,
            "type": "summary",
            "content_blocks": [
                {
                    "block_id": "b1",
                    "type": "text",
                    "text": section_markdown,
                    "source_refs": source_refs,
                }
            ],
            "metadata": {
                "node_id": node_id,
                "parent_id": None,
                "child_ids": [],
                "depth": 0,
                "is_root": True,
                "is_leaf": False,
                "is_hierarchical": True,
                "should_vectorize": False,
                "exclude_from_retrieval": True,
                "chunk_strategy": "web_page",
                "chunk_role": "web_section_root",
                "heading": heading_path[-1] if heading_path else str(section.get("title") or "").strip(),
                "header_path": " > ".join(heading_path),
                "section_type": str(section.get("section_type") or "section"),
                "source_anchors": heading_path,
                "page_numbers": [],
                "source_element_indices": self._extract_section_dom_indices(section.get("blocks") or []),
                "source_refs": source_refs,
                "source_mode": "web_sync",
                "section_index": section_index,
            },
        }

    def _build_text_child_chunks(
        self,
        blocks: List[Dict[str, Any]],
        *,
        heading_path: List[str],
        metadata: Dict[str, Any],
        section_index: int,
    ) -> List[Dict[str, Any]]:
        paragraphs = [self._normalize_text(block.get("text") or "") for block in blocks]
        paragraphs = [paragraph for paragraph in paragraphs if self._is_meaningful_paragraph(paragraph)]
        if not paragraphs:
            return []

        windows = self._assemble_text_windows(paragraphs, heading_path)
        source_refs = self._extract_block_source_refs(blocks, metadata)
        source_indices = self._extract_section_dom_indices(blocks)
        child_chunks: List[Dict[str, Any]] = []
        heading_context = self._build_heading_context(heading_path)
        for piece_index, piece in enumerate(windows, start=1):
            node_id = uuid4().hex
            child_chunks.append(
                {
                    "text": piece,
                    "type": "text",
                    "content_blocks": [
                        {
                            "block_id": "b1",
                            "type": "text",
                            "text": piece,
                            "source_refs": source_refs,
                        }
                    ],
                    "metadata": {
                        "node_id": node_id,
                        "parent_id": None,
                        "child_ids": [],
                        "depth": 1,
                        "is_root": False,
                        "is_leaf": True,
                        "is_hierarchical": True,
                        "should_vectorize": True,
                        "chunk_strategy": "web_page",
                        "chunk_role": "web_text_leaf",
                        "heading": heading_path[-1] if heading_path else "",
                        "header_path": heading_context,
                        "source_anchors": heading_path,
                        "page_numbers": [],
                        "source_element_indices": source_indices,
                        "source_refs": source_refs,
                        "source_mode": "web_sync",
                        "section_index": section_index,
                        "piece_index": piece_index,
                    },
                }
            )
        return child_chunks

    def _build_table_chunk_family(
        self,
        *,
        block: Dict[str, Any],
        heading_path: List[str],
        metadata: Dict[str, Any],
        section_index: int,
    ) -> List[Dict[str, Any]]:
        table_text = self._normalize_text(block.get("text") or "")
        if not table_text:
            return []
        source_refs = self._extract_block_source_refs([block], metadata)
        source_indices = self._extract_section_dom_indices([block])
        block_title = heading_path[-1] if heading_path else ""
        heading_context = self._build_heading_context(heading_path)
        composed_full_text = self._compose_budgeted_text(heading_context, table_text)
        is_within_limit = count_tokens(composed_full_text) <= self.effective_leaf_limit

        if is_within_limit:
            node_id = uuid4().hex
            return [
                {
                    "text": composed_full_text,
                    "type": "table",
                    "content_blocks": [
                        {
                            "block_id": "b1",
                            "type": "table",
                            "text": table_text,
                            "source_refs": source_refs,
                        }
                    ],
                    "metadata": {
                        "node_id": node_id,
                        "parent_id": None,
                        "child_ids": [],
                        "depth": 1,
                        "is_root": False,
                        "is_leaf": True,
                        "is_hierarchical": True,
                        "should_vectorize": True,
                        "chunk_strategy": "web_page",
                        "chunk_role": "web_table_leaf",
                        "heading": block_title,
                        "header_path": heading_context,
                        "source_anchors": heading_path,
                        "page_numbers": [],
                        "source_element_indices": source_indices,
                        "source_refs": source_refs,
                        "source_mode": "web_sync",
                        "section_index": section_index,
                        "table_format": str(block.get("table_format") or "html"),
                    },
                }
            ]

        parent_node_id = uuid4().hex
        fragment_texts = self._split_table_block(
            table_text,
            table_format=str(block.get("table_format") or "html"),
            heading_path=heading_path,
        )
        fragment_chunks: List[Dict[str, Any]] = []
        for fragment_index, fragment_text in enumerate(fragment_texts, start=1):
            fragment_node_id = uuid4().hex
            fragment_chunks.append(
                {
                    "text": fragment_text,
                    "type": "table",
                    "content_blocks": [
                        {
                            "block_id": "b1",
                            "type": "table",
                            "text": self._strip_heading_prefix(fragment_text, heading_context),
                            "source_refs": source_refs,
                        }
                    ],
                    "metadata": {
                        "node_id": fragment_node_id,
                        "parent_id": parent_node_id,
                        "child_ids": [],
                        "depth": 2,
                        "is_root": False,
                        "is_leaf": True,
                        "is_hierarchical": True,
                        "should_vectorize": True,
                        "chunk_strategy": "web_page",
                        "chunk_role": "web_table_fragment",
                        "heading": block_title,
                        "header_path": heading_context,
                        "source_anchors": heading_path,
                        "page_numbers": [],
                        "source_element_indices": source_indices,
                        "source_refs": source_refs,
                        "source_mode": "web_sync",
                        "section_index": section_index,
                        "table_format": str(block.get("table_format") or "html"),
                        "overflow_part_index": fragment_index,
                        "overflow_part_total": len(fragment_texts),
                    },
                }
            )

        parent_chunk = {
            "text": composed_full_text,
            "type": "table",
            "content_blocks": [
                {
                    "block_id": "b1",
                    "type": "table",
                    "text": table_text,
                    "source_refs": source_refs,
                }
            ],
            "metadata": {
                "node_id": parent_node_id,
                "parent_id": None,
                "child_ids": [chunk["metadata"]["node_id"] for chunk in fragment_chunks],
                "depth": 1,
                "is_root": False,
                "is_leaf": False,
                "is_hierarchical": True,
                "should_vectorize": False,
                "exclude_from_retrieval": True,
                "chunk_strategy": "web_page",
                "chunk_role": "web_table_parent",
                "heading": block_title,
                "header_path": heading_context,
                "source_anchors": heading_path,
                "page_numbers": [],
                "source_element_indices": source_indices,
                "source_refs": source_refs,
                "source_mode": "web_sync",
                "section_index": section_index,
                "table_format": str(block.get("table_format") or "html"),
            },
        }
        return [parent_chunk, *fragment_chunks]

    def _split_table_block(
        self,
        table_text: str,
        *,
        table_format: str,
        heading_path: Sequence[str],
    ) -> List[str]:
        if table_format == "markdown":
            fragments = self._split_markdown_table(table_text, heading_path)
            if fragments:
                return fragments
        if table_format == "html":
            fragments = self._split_html_table(table_text, heading_path)
            if fragments:
                return fragments
        return self._split_plain_text_with_heading(table_text, heading_path)

    def _split_markdown_table(self, table_text: str, heading_path: Sequence[str]) -> List[str]:
        lines = [line.rstrip() for line in str(table_text or "").splitlines() if line.strip()]
        if len(lines) < 3:
            return []
        header_line = lines[0]
        separator_line = lines[1]
        body_lines = lines[2:]
        if "|" not in header_line or "|" not in separator_line:
            return []
        fragments: List[str] = []
        current_rows: List[str] = []
        heading_context = self._build_heading_context(heading_path)
        for row_line in body_lines:
            row_segments = self._split_plain_table_row(row_line, heading_context)
            for row_segment in row_segments:
                candidate_rows = current_rows + [row_segment]
                candidate_table = "\n".join([header_line, separator_line, *candidate_rows])
                candidate_text = self._compose_budgeted_text(heading_context, candidate_table)
                if current_rows and count_tokens(candidate_text) > self.effective_leaf_limit:
                    fragments.append(
                        self._compose_budgeted_text(
                            heading_context,
                            "\n".join([header_line, separator_line, *current_rows]),
                        )
                    )
                    current_rows = [row_segment]
                    continue
                current_rows = candidate_rows
        if current_rows:
            fragments.append(
                self._compose_budgeted_text(
                    heading_context,
                    "\n".join([header_line, separator_line, *current_rows]),
                )
            )
        return fragments

    def _split_html_table(self, table_text: str, heading_path: Sequence[str]) -> List[str]:
        try:
            wrapper = lxml_html.fragment_fromstring(table_text, create_parent="div")
        except Exception:
            return []
        table_elements = wrapper.xpath(".//table")
        if not table_elements:
            return []
        table_element = table_elements[0]
        rows = table_element.xpath(".//tr")
        if len(rows) <= 1:
            return []

        header_rows = []
        body_rows = []
        header_phase = True
        for row in rows:
            if header_phase and row.xpath("./th") and not row.xpath("./td"):
                header_rows.append(row)
                continue
            header_phase = False
            body_rows.append(row)
        if not body_rows:
            body_rows = rows

        fragments: List[str] = []
        current_body_rows: List[Any] = []
        heading_context = self._build_heading_context(heading_path)
        for row in body_rows:
            row_fragments = self._split_html_table_row(row, heading_context)
            for row_fragment in row_fragments:
                candidate_rows = current_body_rows + [row_fragment]
                candidate_table_html = self._build_html_table_fragment(header_rows, candidate_rows)
                candidate_text = self._compose_budgeted_text(heading_context, candidate_table_html)
                if current_body_rows and count_tokens(candidate_text) > self.effective_leaf_limit:
                    fragments.append(
                        self._compose_budgeted_text(
                            heading_context,
                            self._build_html_table_fragment(header_rows, current_body_rows),
                        )
                    )
                    current_body_rows = [row_fragment]
                    continue
                current_body_rows = candidate_rows
        if current_body_rows:
            fragments.append(
                self._compose_budgeted_text(
                    heading_context,
                    self._build_html_table_fragment(header_rows, current_body_rows),
                )
            )
        return fragments

    def _build_html_table_fragment(self, header_rows: Sequence[Any], body_rows: Sequence[Any]) -> str:
        table = lxml_html.Element("table")
        if header_rows:
            thead = lxml_html.Element("thead")
            for row in header_rows:
                thead.append(self._clone_html_node(row))
            table.append(thead)
        tbody = lxml_html.Element("tbody")
        for row in body_rows:
            tbody.append(self._clone_html_node(row))
        table.append(tbody)
        return self._normalize_text(lxml_html.tostring(table, encoding="unicode", method="html"))

    def _clone_html_node(self, node: Any):
        return lxml_html.fragment_fromstring(lxml_html.tostring(node, encoding="unicode", method="html"))

    def _split_plain_text_with_heading(self, text: str, heading_path: Sequence[str]) -> List[str]:
        paragraphs = [paragraph for paragraph in re.split(r"\n{2,}", self._normalize_text(text)) if paragraph.strip()]
        if not paragraphs:
            return []
        return self._assemble_text_windows(paragraphs, list(heading_path))

    def _assemble_text_windows(self, paragraphs: List[str], heading_path: List[str]) -> List[str]:
        windows: List[str] = []
        current: List[str] = []
        heading_context = self._build_heading_context(heading_path)
        for paragraph in paragraphs:
            for paragraph_piece in self._split_oversized_paragraph(paragraph, heading_context):
                candidate = current + [paragraph_piece]
                candidate_text = self._compose_budgeted_text(heading_context, "\n\n".join(candidate))
                if current and count_tokens(candidate_text) > self.effective_leaf_limit:
                    windows.append(self._compose_budgeted_text(heading_context, "\n\n".join(current)))
                    current = self._build_overlap_tail(current) + [paragraph_piece]
                    continue
                current = candidate
        if current:
            windows.append(self._compose_budgeted_text(heading_context, "\n\n".join(current)))
        return windows

    def _chunk_plain_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        cleaned_text = self._normalize_text(text)
        if not cleaned_text:
            return []
        pieces = self._split_plain_text_with_heading(cleaned_text, [])
        url = str(metadata.get("source_url") or metadata.get("url") or "").strip()
        canonical_url = str(metadata.get("canonical_url") or metadata.get("final_url") or url).strip()
        source_ref = {
            "ref_type": "web_anchor",
            "url": url,
            "canonical_url": canonical_url,
            "heading_path": [],
            "anchor_text": "",
            "dom_index": 0,
        }
        chunks: List[Dict[str, Any]] = []
        for index, piece in enumerate(pieces, start=1):
            chunks.append(
                {
                    "text": piece,
                    "type": "text",
                    "content_blocks": [
                        {
                            "block_id": "b1",
                            "type": "text",
                            "text": piece,
                            "source_refs": [source_ref],
                        }
                    ],
                    "metadata": {
                        "node_id": uuid4().hex,
                        "parent_id": None,
                        "child_ids": [],
                        "depth": 0,
                        "is_root": True,
                        "is_leaf": True,
                        "is_hierarchical": False,
                        "should_vectorize": True,
                        "chunk_strategy": "web_page",
                        "chunk_role": "web_text_leaf",
                        "heading": "",
                        "header_path": "",
                        "source_anchors": [],
                        "page_numbers": [],
                        "source_element_indices": [index - 1],
                        "source_refs": [source_ref],
                        "source_mode": "web_sync",
                    },
                }
            )
        return chunks

    def _build_overlap_tail(self, paragraphs: List[str]) -> List[str]:
        if self.chunk_overlap <= 0:
            return []
        overlap_parts: List[str] = []
        total = 0
        for paragraph in reversed(paragraphs):
            total += len(paragraph)
            overlap_parts.insert(0, paragraph)
            if total >= self.chunk_overlap:
                break
        return overlap_parts

    @staticmethod
    def _normalize_text(text: Any) -> str:
        normalized = re.sub(r"\r\n?", "\n", str(text or ""))
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def _is_meaningful_paragraph(paragraph: str) -> bool:
        stripped = paragraph.strip()
        if not stripped:
            return False
        low = stripped.lower()
        noisy_prefixes = ("导航", "目录", "menu", "navigation", "footer", "版权", "copyright")
        noisy_contains = ("©", "all rights reserved", "上一篇", "下一篇", "返回顶部")
        if any(low.startswith(prefix) for prefix in noisy_prefixes):
            return False
        if any(token in low for token in noisy_contains):
            return False
        return True

    @staticmethod
    def _extract_block_source_refs(blocks: Sequence[Any], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = str(metadata.get("source_url") or metadata.get("url") or "").strip()
        canonical_url = str(metadata.get("canonical_url") or metadata.get("final_url") or url).strip()
        refs: List[Dict[str, Any]] = []
        for block in blocks:
            for ref in list((block or {}).get("source_refs") or []):
                if not isinstance(ref, dict):
                    continue
                normalized_ref = dict(ref)
                if not normalized_ref.get("url"):
                    normalized_ref["url"] = url
                if not normalized_ref.get("canonical_url"):
                    normalized_ref["canonical_url"] = canonical_url
                refs.append(normalized_ref)
        if refs:
            return refs
        return [{
            "ref_type": "web_anchor",
            "url": url,
            "canonical_url": canonical_url,
            "heading_path": [],
            "anchor_text": "",
            "dom_index": 0,
        }]

    @staticmethod
    def _extract_section_dom_indices(blocks: Sequence[Any]) -> List[int]:
        indices: List[int] = []
        for block in blocks:
            dom_index = (block or {}).get("dom_index")
            if isinstance(dom_index, int):
                indices.append(dom_index)
        return indices

    @staticmethod
    def _build_heading_context(heading_path: Sequence[str]) -> str:
        return " > ".join(str(item).strip() for item in heading_path if str(item).strip())

    @staticmethod
    def _compose_budgeted_text(title: str, content: str) -> str:
        title_text = str(title or "").strip()
        body = str(content or "").strip()
        if title_text and body:
            return f"{title_text}\n\n{body}"
        return title_text or body

    def _split_oversized_paragraph(self, paragraph: str, heading_context: str) -> List[str]:
        """按预算拆分超长段落，保证叶子块不会被单段文本顶爆。"""
        normalized = self._normalize_text(paragraph)
        if not normalized:
            return []
        candidate_text = self._compose_budgeted_text(heading_context, normalized)
        if count_tokens(candidate_text) <= self.effective_leaf_limit:
            return [normalized]

        segments: List[str] = []
        current = ""
        for sentence in re.split(r"(?<=[。！？；;.!?])\s*", normalized):
            sentence = sentence.strip()
            if not sentence:
                continue
            tentative = f"{current}{sentence}" if current else sentence
            tentative_text = self._compose_budgeted_text(heading_context, tentative)
            if current and count_tokens(tentative_text) > self.effective_leaf_limit:
                segments.append(current)
                current = sentence
                continue
            current = tentative

        if current:
            segments.append(current)
        if len(segments) == 1 and count_tokens(self._compose_budgeted_text(heading_context, segments[0])) > self.effective_leaf_limit:
            return self._split_by_character_budget(segments[0], heading_context)
        return segments or [normalized]

    def _split_plain_table_row(self, row_line: str, heading_context: str) -> List[str]:
        row_text = self._normalize_text(row_line)
        candidate = self._compose_budgeted_text(heading_context, row_text)
        if count_tokens(candidate) <= self.effective_leaf_limit:
            return [row_text]
        return self._split_by_character_budget(row_text, heading_context)

    def _split_html_table_row(self, row: Any, heading_context: str) -> List[Any]:
        candidate = self._compose_budgeted_text(
            heading_context,
            self._build_html_table_fragment([], [row]),
        )
        if count_tokens(candidate) <= self.effective_leaf_limit:
            return [row]

        cell_texts = [
            self._normalize_text("".join(cell.itertext()))
            for cell in row.xpath("./th|./td")
        ]
        if len(cell_texts) <= 1:
            return [row]

        split_rows: List[Any] = []
        for index, _cell_text in enumerate(cell_texts, start=1):
            row_clone = self._clone_html_node(row)
            row_cells = row_clone.xpath("./th|./td")
            for cell_index, cell in enumerate(row_cells):
                if cell_index != index - 1:
                    cell.text = ""
                    for child in list(cell):
                        cell.remove(child)
            split_rows.append(row_clone)
        return split_rows or [row]

    def _split_by_character_budget(self, text: str, heading_context: str) -> List[str]:
        segments: List[str] = []
        current = ""
        for char in str(text or ""):
            tentative = f"{current}{char}"
            if current and count_tokens(self._compose_budgeted_text(heading_context, tentative)) > self.effective_leaf_limit:
                segments.append(current)
                current = char
                continue
            current = tentative
        if current:
            segments.append(current)
        return [segment.strip() for segment in segments if segment.strip()]

    @staticmethod
    def _strip_heading_prefix(text: str, title: str) -> str:
        normalized_text = str(text or "")
        normalized_title = str(title or "").strip()
        if not normalized_title:
            return normalized_text
        prefix = f"{normalized_title}\n\n"
        if normalized_text.startswith(prefix):
            return normalized_text[len(prefix):]
        return normalized_text

    @staticmethod
    def _refresh_topology(chunks: List[Dict[str, Any]]) -> None:
        chunk_map = {chunk["metadata"]["node_id"]: chunk for chunk in chunks}
        for chunk in chunks:
            metadata = chunk["metadata"]
            child_ids = [child_id for child_id in list(metadata.get("child_ids") or []) if child_id in chunk_map]
            metadata["child_ids"] = child_ids
            metadata["is_leaf"] = not bool(child_ids)
            metadata["is_root"] = metadata.get("parent_id") is None
            if child_ids:
                metadata["should_vectorize"] = False
