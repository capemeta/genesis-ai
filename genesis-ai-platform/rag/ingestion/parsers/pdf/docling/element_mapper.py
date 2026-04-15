from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..models import ParserElement


class DoclingElementMapper:
    """Map docling document objects to normalized ParserElement structures."""

    def extract_text_elements(self, doc: Any) -> List[ParserElement]:
        elements: List[ParserElement] = []
        for text_item in (getattr(doc, "texts", []) or []):
            text = str(getattr(text_item, "text", "") or "").strip()
            if not text:
                continue

            label = str(getattr(text_item, "label", "") or "").lower()
            if "title" in label or "heading" in label:
                el_type = "title"
                level = self._infer_heading_level(text)
                metadata: Dict[str, Any] = {
                    "source": "docling",
                    "modality": "docling_text",
                    "label": str(getattr(text_item, "label", "") or ""),
                    "level": level,
                }
            else:
                el_type = "text"
                metadata = {
                    "source": "docling",
                    "modality": "docling_text",
                    "label": str(getattr(text_item, "label", "") or ""),
                }

            page_no = self.extract_page_no(text_item)
            bbox = self.extract_bbox(text_item)
            elements.append(
                ParserElement(
                    type=el_type,
                    content=text,
                    page_no=page_no,
                    bbox=bbox,
                    metadata=metadata,
                )
            )
        return elements

    def extract_table_elements(self, doc: Any) -> List[ParserElement]:
        elements: List[ParserElement] = []
        for idx, table in enumerate((getattr(doc, "tables", []) or []), start=1):
            markdown = self._table_to_markdown(table)
            if not markdown:
                continue
            page_no = self.extract_page_no(table)
            bbox = self.extract_bbox(table)
            elements.append(
                ParserElement(
                    type="table",
                    content=markdown,
                    page_no=page_no,
                    bbox=bbox,
                    metadata={
                        "source": "docling",
                        "modality": "docling_table",
                        "label": str(getattr(table, "label", "") or ""),
                        "table_index": idx,
                    },
                )
            )
        return elements

    def extract_image_elements(self, doc: Any) -> Tuple[List[ParserElement], List[Dict[str, Any]]]:
        elements: List[ParserElement] = []
        embedded_images: List[Dict[str, Any]] = []
        for idx, pic in enumerate((getattr(doc, "pictures", []) or []), start=1):
            image_id = f"docling_image_{idx}"
            page_no = self.extract_page_no(pic)
            bbox = self.extract_bbox(pic)
            image_bytes = self.extract_image_bytes(pic)
            ext = ".png"
            content_type = "image/png"
            if not image_bytes:
                elements.append(
                    ParserElement(
                        type="image",
                        content=f"pdf://embedded/{image_id}",
                        page_no=page_no,
                        bbox=bbox,
                        metadata={
                            "source": "docling",
                            "modality": "docling_image",
                            "image_id": image_id,
                            "unavailable_blob": True,
                        },
                    )
                )
                continue

            embedded_images.append(
                {
                    "id": image_id,
                    "content_type": content_type,
                    "ext": ext,
                    "size": len(image_bytes),
                    "blob": image_bytes,
                    "page_no": page_no,
                    "bbox": bbox,
                }
            )
            elements.append(
                ParserElement(
                    type="image",
                    content=f"pdf://embedded/{image_id}",
                    page_no=page_no,
                    bbox=bbox,
                    metadata={
                        "source": "docling",
                        "modality": "docling_image",
                        "image_id": image_id,
                    },
                )
            )
        return elements, embedded_images

    def extract_page_no(self, item: Any) -> int:
        prov = getattr(item, "prov", None)
        if isinstance(prov, list) and prov:
            first = prov[0]
            for key in ("page_no", "page", "page_number"):
                val = getattr(first, key, None)
                if isinstance(val, int):
                    return self._to_zero_based_page_no(val)
        for key in ("page_no", "page", "page_number"):
            val = getattr(item, key, None)
            if isinstance(val, int):
                return self._to_zero_based_page_no(val)
        return 0

    def _to_zero_based_page_no(self, raw_page: int) -> int:
        # 统一规范：内部 page_no 一律为 0-based；展示层使用 page_number=page_no+1。
        if raw_page <= 0:
            return 0
        return raw_page - 1

    def extract_bbox(self, item: Any) -> List[float]:
        prov = getattr(item, "prov", None)
        if isinstance(prov, list) and prov:
            bbox_obj = getattr(prov[0], "bbox", None)
            bbox = self._bbox_from_obj(bbox_obj)
            if bbox:
                return bbox
        bbox = self._bbox_from_obj(getattr(item, "bbox", None))
        if bbox:
            return bbox
        return [0.0, 0.0, 0.0, 0.0]

    def _bbox_from_obj(self, bbox_obj: Any) -> Optional[List[float]]:
        if bbox_obj is None:
            return None
        if isinstance(bbox_obj, (list, tuple)) and len(bbox_obj) >= 4:
            return [float(bbox_obj[0]), float(bbox_obj[1]), float(bbox_obj[2]), float(bbox_obj[3])]
        attrs = [
            ("l", "t", "r", "b"),
            ("x0", "y0", "x1", "y1"),
            ("left", "top", "right", "bottom"),
        ]
        for a0, a1, a2, a3 in attrs:
            if all(hasattr(bbox_obj, a) for a in (a0, a1, a2, a3)):
                return [
                    float(getattr(bbox_obj, a0)),
                    float(getattr(bbox_obj, a1)),
                    float(getattr(bbox_obj, a2)),
                    float(getattr(bbox_obj, a3)),
                ]
        return None

    def _table_to_markdown(self, table: Any) -> str:
        table_data = getattr(table, "data", None)
        grid = getattr(table_data, "grid", None) if table_data is not None else None
        num_rows = int(getattr(table_data, "num_rows", 0) or 0) if table_data is not None else 0
        num_cols = int(getattr(table_data, "num_cols", 0) or 0) if table_data is not None else 0
        if not grid or num_rows <= 0 or num_cols <= 0:
            return ""

        rows: List[List[str]] = []
        for row_idx in range(num_rows):
            row_cells: List[str] = []
            row_obj = grid[row_idx] if row_idx < len(grid) else []
            for col_idx in range(num_cols):
                cell = row_obj[col_idx] if col_idx < len(row_obj) else ""
                cell_text = str(getattr(cell, "text", cell) or "").replace("|", r"\|").strip()
                row_cells.append(cell_text)
            rows.append(row_cells)

        if not rows:
            return ""
        header = rows[0]
        body_rows = rows[1:] if len(rows) > 1 else []
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * len(header)) + " |",
        ]
        for row in body_rows:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def extract_image_bytes(self, pic: Any) -> Optional[bytes]:
        for key in ("blob", "image", "bytes", "data"):
            val = getattr(pic, key, None)
            if isinstance(val, (bytes, bytearray)):
                return bytes(val)
        for method_name in ("get_image", "to_pil"):
            method = getattr(pic, method_name, None)
            if callable(method):
                try:
                    out = method()
                    if isinstance(out, (bytes, bytearray)):
                        return bytes(out)
                    try:
                        from io import BytesIO

                        bio = BytesIO()
                        out.save(bio, format="PNG")
                        return bio.getvalue()
                    except Exception:
                        continue
                except Exception:
                    continue
        return None

    def _infer_heading_level(self, text: str) -> int:
        stripped = text.strip()
        if not stripped:
            return 1
        if len(stripped) <= 18:
            return 2
        if len(stripped) <= 36:
            return 3
        return 4
