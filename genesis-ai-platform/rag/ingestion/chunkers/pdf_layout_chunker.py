"""
PDF layout-aware chunker.

This chunker consumes parser metadata["elements"] (with page_no + bbox) and
builds chunks directly from PDF layout elements, then emits source anchors
without touching markdown split/merge logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from rag.ingestion.chunkers.base import BaseChunker
from rag.utils.token_utils import count_tokens


class PdfLayoutChunker(BaseChunker):
    """Layout-first chunking for PDFs."""

    _TEXT_TYPES = {"text", "title", "code", "table", "image"}

    def chunk(self, text: str, metadata: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        metadata = metadata or {}
        elements = metadata.get("elements")
        if not isinstance(elements, list) or not elements:
            # If no layout elements available, degrade gracefully to a single chunk.
            content = (text or "").strip()
            if not content:
                return []
            return [
                {
                    "text": content,
                    "metadata": {
                        **metadata,
                        "chunk_strategy": "pdf_layout",
                        "source_anchor_engine": "pdf_layout_elements_v1",
                    },
                    "type": "text",
                }
            ]

        normalized = self._normalize_elements(elements)
        if not normalized:
            content = (text or "").strip()
            if not content:
                return []
            return [
                {
                    "text": content,
                    "metadata": {
                        **metadata,
                        "chunk_strategy": "pdf_layout",
                        "source_anchor_engine": "pdf_layout_elements_v1",
                    },
                    "type": "text",
                }
            ]

        chunks: List[Dict[str, Any]] = []
        current_texts: List[str] = []
        current_elements: List[Dict[str, Any]] = []
        current_tokens = 0

        target = max(80, int(self.chunk_size))
        overlap_target = max(0, min(int(self.chunk_overlap), int(target * 0.3)))

        for el in normalized:
            el_tokens = max(1, count_tokens(el["text"]))

            if current_texts and current_tokens + el_tokens > target:
                chunks.append(self._build_chunk(metadata, current_texts, current_elements))
                if overlap_target > 0:
                    current_texts, current_elements, current_tokens = self._build_overlap_tail(
                        current_texts, current_elements, overlap_target
                    )
                else:
                    current_texts, current_elements, current_tokens = [], [], 0

            current_texts.append(el["text"])
            current_elements.append(el)
            current_tokens += el_tokens

        if current_texts:
            chunks.append(self._build_chunk(metadata, current_texts, current_elements))

        return chunks

    def _normalize_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for idx, el in enumerate(elements):
            if not isinstance(el, dict):
                continue
            et = str(el.get("type") or "").lower()
            if et not in self._TEXT_TYPES:
                continue

            raw_content = str(el.get("content") or "").strip()
            if not raw_content:
                continue

            # Keep image references visible in chunk text for frontend markdown rendering.
            content = f"![image]({raw_content})" if et == "image" else raw_content

            page_no = el.get("page_no")
            bbox = el.get("bbox")
            if not isinstance(page_no, int):
                continue
            if not (isinstance(bbox, list) and len(bbox) == 4):
                continue

            try:
                x0, y0, x1, y1 = [float(v) for v in bbox]
            except Exception:
                continue
            if x1 <= x0 or y1 <= y0:
                continue

            out.append(
                {
                    "idx": idx,
                    "type": et,
                    "text": content,
                    "raw_content": raw_content,
                    "page_no": page_no,
                    "bbox": [x0, y0, x1, y1],
                    # 保留原始元数据，用于前端区分图片类型（source/modality/caption 等）
                    "metadata": el.get("metadata") or {},
                }
            )

        out.sort(key=lambda x: (x["page_no"], x["bbox"][1], x["bbox"][0], x["idx"]))
        return out

    def _build_overlap_tail(
        self,
        texts: List[str],
        elements: List[Dict[str, Any]],
        overlap_target: int,
    ) -> Tuple[List[str], List[Dict[str, Any]], int]:
        tail_texts: List[str] = []
        tail_elements: List[Dict[str, Any]] = []
        tail_tokens = 0
        for txt, el in reversed(list(zip(texts, elements))):
            tks = max(1, count_tokens(txt))
            if tail_texts and tail_tokens + tks > overlap_target:
                break
            tail_texts.insert(0, txt)
            tail_elements.insert(0, el)
            tail_tokens += tks
        return tail_texts, tail_elements, tail_tokens

    def _build_chunk(
        self,
        base_metadata: Dict[str, Any],
        texts: List[str],
        elements: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        chunk_text = "\n".join([t for t in texts if t]).strip()
        anchors = self._build_anchors(elements)
        page_numbers = [int(anchor["page_number"]) for anchor in anchors]
        meta = {
            **base_metadata,
            "chunk_strategy": "pdf_layout",
            "source_anchor_engine": "pdf_layout_elements_v1",
            "source_anchor_confidence": "high",
            "source_anchor_coordinate_system": "top_left_pdf_points",
            "source_anchors": anchors,
            "source_element_indices": [int(e["idx"]) for e in elements],
            "page_numbers": page_numbers,
        }
        if page_numbers:
            meta["primary_page_number"] = page_numbers[0]

        content_blocks: List[Dict[str, Any]] = []
        for block_idx, e in enumerate(elements, start=1):
            block_type = str(e["type"])
            block_ref = {
                "page_no": int(e["page_no"]),
                "page_number": int(e["page_no"]) + 1,
                "bbox": [float(e["bbox"][0]), float(e["bbox"][1]), float(e["bbox"][2]), float(e["bbox"][3])],
                "element_index": int(e["idx"]),
                "element_type": block_type,
            }
            block: Dict[str, Any] = {
                "block_id": f"b{block_idx}",
                "type": block_type,
                "source_refs": [block_ref],
            }
            if block_type == "image":
                block["url"] = str(e.get("raw_content") or e["text"]).strip()
                el_meta = e.get("metadata") or {}
                # 图片块统一输出为 origin + analysis，避免前端依赖零散字段推断语义。
                block["origin"] = {
                    "parser": str(el_meta.get("source") or "").strip() or None,
                    "modality": str(el_meta.get("modality") or "").strip() or None,
                }
                block["analysis"] = self._build_image_analysis(el_meta)
            else:
                block["text"] = str(e["text"]).strip()
            content_blocks.append(block)

        return {
            "text": chunk_text,
            "metadata": meta,
            "type": "text",
            "content_blocks": content_blocks,
        }

    def _build_image_analysis(self, element_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """统一构造图片分析结果，供前端稳定区分 pure/caption/ocr/vision。"""
        raw_caption = element_metadata.get("image_caption")
        caption = [str(item).strip() for item in raw_caption if str(item).strip()] if isinstance(raw_caption, list) else []
        ocr_text = str(element_metadata.get("ocr_text") or "").strip()
        vision_text = str(element_metadata.get("vision_text") or "").strip()

        status = "none"
        if ocr_text and vision_text:
            status = "ocr_vision"
        elif vision_text:
            status = "vision"
        elif ocr_text:
            status = "ocr"
        elif caption:
            status = "caption"

        return {
            "status": status,
            "caption": caption,
            "ocr_text": ocr_text or None,
            "vision_text": vision_text or None,
        }

    def _build_anchors(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_page: Dict[int, List[List[float]]] = {}
        for el in elements:
            by_page.setdefault(int(el["page_no"]), []).append(el["bbox"])

        anchors: List[Dict[str, Any]] = []
        for page_no in sorted(by_page.keys()):
            boxes = by_page[page_no]
            x0 = min(b[0] for b in boxes)
            y0 = min(b[1] for b in boxes)
            x1 = max(b[2] for b in boxes)
            y1 = max(b[3] for b in boxes)
            anchors.append(
                {
                    "page_no": page_no,
                    "page_number": page_no + 1,
                    "bbox": [x0, y0, x1, y1],
                }
            )
        return anchors
