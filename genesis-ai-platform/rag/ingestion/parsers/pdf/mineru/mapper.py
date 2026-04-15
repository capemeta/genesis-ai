from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models import ParserElement


logger = logging.getLogger(__name__)


def load_json_field(val: Any) -> Any:
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val
    return val


def _to_bbox(raw_bbox: Any) -> List[float]:
    if isinstance(raw_bbox, list) and len(raw_bbox) == 4:
        try:
            return [float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3])]
        except Exception:
            return [0.0, 0.0, 0.0, 0.0]
    return [0.0, 0.0, 0.0, 0.0]


def extract_page_sizes_from_middle_json(middle_json: Any) -> Dict[int, Tuple[float, float]]:
    """从 middle_json 中提取每页真实尺寸，供 bbox 回算使用。"""
    if not isinstance(middle_json, dict):
        return {}

    pdf_info = middle_json.get("pdf_info")
    if not isinstance(pdf_info, list):
        return {}

    page_sizes: Dict[int, Tuple[float, float]] = {}
    for item in pdf_info:
        if not isinstance(item, dict):
            continue
        page_idx = item.get("page_idx")
        page_size = item.get("page_size")
        if not isinstance(page_idx, (int, str)):
            continue
        if not isinstance(page_size, (list, tuple)) or len(page_size) < 2:
            continue
        try:
            page_no = int(page_idx)
            width = float(page_size[0])
            height = float(page_size[1])
        except Exception:
            continue
        if page_no < 0 or width <= 0 or height <= 0:
            continue
        page_sizes[page_no] = (width, height)
    return page_sizes


def infer_normalized_pages_from_content_list(
    content_list: Any,
    page_sizes: Dict[int, Tuple[float, float]] | None,
) -> Dict[int, bool]:
    """
    按页推断 content_list 是否使用了归一化画布坐标。

    经验规则：
    - 只要该页出现明显超出真实页尺寸的 bbox，就认为这一页的 content_list bbox
      整体处于归一化画布空间，而不是 PDF points。
    - 之所以按“页”而不是按“单个 bbox”判断，是因为某些归一化后的文本框数值
      仍可能落在真实页尺寸范围内，但其比例依然是错的。
    """
    if not isinstance(content_list, list) or not page_sizes:
        return {}

    normalized_pages: Dict[int, bool] = {}
    for item in content_list:
        if not isinstance(item, dict):
            continue
        page_no = _page_no_from_item(item)
        if page_no not in page_sizes:
            continue
        page_width, page_height = page_sizes[page_no]
        bbox = _to_bbox(item.get("bbox"))
        if len(bbox) != 4:
            continue
        max_x = max(bbox[0], bbox[2])
        max_y = max(bbox[1], bbox[3])
        if max_x > page_width * 1.2 or max_y > page_height * 1.2:
            normalized_pages[page_no] = True
        else:
            normalized_pages.setdefault(page_no, False)
    return normalized_pages


def _normalize_bbox_to_pdf_points(
    raw_bbox: Any,
    page_no: int,
    page_sizes: Dict[int, Tuple[float, float]] | None,
    normalized_canvas_size: float | None,
    normalized_pages: Dict[int, bool] | None,
) -> Tuple[List[float], Dict[str, Any]]:
    """
    将 MinerU content_list bbox 尽量归一化回真实 PDF points。

    当前线上样例里，content_list 的 bbox 常落在接近 1000x1000 的归一化画布，
    而 middle_json.pdf_info[].page_size 才是真实页面尺寸。这里优先做一次回算，
    保持 content_list 仍然作为文本来源，但坐标回到统一协议要求的 PDF points。
    """
    bbox = _to_bbox(raw_bbox)
    meta: Dict[str, Any] = {
        "bbox_normalized": False,
        "bbox_source_space": "content_list_raw",
    }
    if len(bbox) != 4:
        return bbox, meta

    if not page_sizes or page_no not in page_sizes:
        return bbox, meta

    page_width, page_height = page_sizes[page_no]
    if page_width <= 0 or page_height <= 0:
        return bbox, meta

    x0, y0, x1, y1 = bbox

    # 先做页级判定：若该页没有表现出归一化特征，则认为是原始 PDF points。
    if not (normalized_pages or {}).get(page_no, False):
        meta["bbox_source_space"] = "pdf_points"
        return bbox, meta

    canvas_size = float(normalized_canvas_size or 0.0)
    if canvas_size <= 0:
        return bbox, meta

    normalized_bbox = [
        x0 / canvas_size * page_width,
        y0 / canvas_size * page_height,
        x1 / canvas_size * page_width,
        y1 / canvas_size * page_height,
    ]
    meta.update(
        {
            "bbox_normalized": True,
            "bbox_source_space": f"content_list_canvas_{int(canvas_size)}",
            "bbox_target_space": "pdf_points",
            "page_width": page_width,
            "page_height": page_height,
            "bbox_normalized_canvas_size": canvas_size,
            "raw_bbox": bbox,
        }
    )
    return normalized_bbox, meta


def _decode_image(image_data: Any, fallback_name: str) -> Optional[Tuple[bytes, str, str]]:
    if isinstance(image_data, (bytes, bytearray)):
        blob = bytes(image_data)
        guessed_ct = mimetypes.guess_type(fallback_name)[0] or "application/octet-stream"
        ext = Path(fallback_name).suffix or (mimetypes.guess_extension(guessed_ct) or ".bin")
        return blob, guessed_ct, ext

    if not isinstance(image_data, str):
        return None

    payload = image_data
    content_type = mimetypes.guess_type(fallback_name)[0] or "application/octet-stream"
    m = re.match(r"^data:(?P<ct>[^;]+);base64,(?P<b64>.+)$", image_data, flags=re.IGNORECASE | re.DOTALL)
    if m:
        content_type = str(m.group("ct")).strip() or content_type
        payload = m.group("b64")

    try:
        blob = base64.b64decode(payload)
    except Exception:
        return None

    ext = Path(fallback_name).suffix or (mimetypes.guess_extension(content_type) or ".bin")
    return blob, content_type, ext


def build_image_assets(images: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(images, dict):
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for image_name, image_data in images.items():
        image_id = Path(str(image_name)).name.strip()
        if not image_id:
            continue
        decoded = _decode_image(image_data, image_id)
        if decoded is None:
            continue
        blob, content_type, ext = decoded
        out[image_id] = {
            "id": image_id,
            "content_type": content_type,
            "ext": ext,
            "size": len(blob),
            "blob": blob,
        }
    return out


def _page_no_from_item(item: Dict[str, Any]) -> int:
    raw = item.get("page_idx", item.get("page_no", 0))
    try:
        page_idx = int(raw)
    except Exception:
        page_idx = 0
    # 统一规范：内部 page_no 一律使用 0-based。
    return page_idx if page_idx >= 0 else 0


def _list_to_text(raw_items: Any) -> str:
    if not isinstance(raw_items, list):
        return ""
    lines: List[str] = []
    for one in raw_items:
        if isinstance(one, dict):
            text = str(one.get("text") or "").strip()
            if text:
                lines.append(f"- {text}")
            continue
        text = str(one or "").strip()
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)


def _extract_text_payload(item: Dict[str, Any]) -> str:
    # MinerU 不同版本字段名可能不一致，按优先级兜底提取文本载荷。
    for key in ("text", "content", "code", "code_body", "md", "markdown", "body"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _looks_like_code(raw_type: str, sub_type: str, text: str) -> bool:
    rt = str(raw_type or "").strip().lower()
    st = str(sub_type or "").strip().lower()
    if rt in {"code", "code_block", "fenced_code", "pre"}:
        return True
    if st in {"code", "code_block", "fenced_code", "pre"}:
        return True
    stripped = str(text or "").strip()
    if not stripped:
        return False
    # 兼容 Markdown 围栏代码块。
    if "```" in stripped:
        return True
    return False


def map_content_list_to_elements(
    content_list: Any,
    image_assets: Dict[str, Dict[str, Any]],
    page_sizes: Dict[int, Tuple[float, float]] | None = None,
    normalized_canvas_size: float | None = None,
) -> List[ParserElement]:
    if not isinstance(content_list, list):
        return []

    normalized_pages = infer_normalized_pages_from_content_list(
        content_list=content_list,
        page_sizes=page_sizes,
    )
    logger.info(
        "[MinerUMapper] page_sizes=%s normalized_pages=%s canvas_size=%s",
        {k: [round(v[0], 2), round(v[1], 2)] for k, v in (page_sizes or {}).items()},
        normalized_pages,
        normalized_canvas_size,
    )
    elements: List[ParserElement] = []
    for item in content_list:
        if not isinstance(item, dict):
            continue

        raw_type = str(item.get("type") or "text").strip().lower()
        if raw_type == "page_number":
            continue

        page_no = _page_no_from_item(item)
        bbox, bbox_meta = _normalize_bbox_to_pdf_points(
            raw_bbox=item.get("bbox"),
            page_no=page_no,
            page_sizes=page_sizes,
            normalized_canvas_size=normalized_canvas_size,
            normalized_pages=normalized_pages,
        )

        if raw_type == "image":
            img_path = str(item.get("img_path") or "").strip()
            image_id = Path(img_path).name if img_path else ""
            if not image_id:
                continue
            elements.append(
                ParserElement(
                    type="image",
                    content=f"pdf://embedded/{image_id}",
                    page_no=page_no,
                    bbox=bbox,
                    metadata={
                        "source": "mineru",
                        "modality": "mineru_image",
                        "image_id": image_id,
                        "image_caption": item.get("image_caption") or [],
                        "image_footnote": item.get("image_footnote") or [],
                        **bbox_meta,
                    },
                )
            )
            continue

        if raw_type == "table":
            table_content = str(item.get("table_body") or "").strip()
            if not table_content:
                continue
            elements.append(
                ParserElement(
                    type="table",
                    content=table_content,
                    page_no=page_no,
                    bbox=bbox,
                    metadata={
                        "source": "mineru",
                        "modality": "mineru_table",
                        "table_caption": item.get("table_caption") or [],
                        "table_footnote": item.get("table_footnote") or [],
                        **bbox_meta,
                    },
                )
            )
            continue

        if raw_type == "list":
            text = _list_to_text(item.get("list_items"))
            if not text:
                continue
            elements.append(
                ParserElement(
                    type="text",
                    content=text,
                    page_no=page_no,
                    bbox=bbox,
                    metadata={
                        "source": "mineru",
                        "modality": "mineru_list",
                        "structure_type": "list_item",
                        "sub_type": item.get("sub_type"),
                        **bbox_meta,
                    },
                )
            )
            continue

        if raw_type == "formula":
            formula_text = str(item.get("text") or item.get("latex") or "").strip()
            if not formula_text:
                continue
            elements.append(
                ParserElement(
                    type="text",
                    content=f"[公式] {formula_text}",
                    page_no=page_no,
                    bbox=bbox,
                    metadata={
                        "source": "mineru",
                        "modality": "mineru_formula",
                        "formula": True,
                        **bbox_meta,
                    },
                )
            )
            continue

        text = _extract_text_payload(item)
        if not text:
            continue

        sub_type = str(item.get("sub_type") or "").strip().lower()
        text_level = item.get("text_level")
        level: Optional[int] = None
        try:
            if text_level is not None:
                level = max(1, min(int(text_level), 6))
        except Exception:
            level = None

        # 先判定代码块，再判定标题，避免代码误判成普通文本/标题。
        is_code = _looks_like_code(raw_type=raw_type, sub_type=sub_type, text=text)
        is_title = (not is_code) and (raw_type in {"title", "header"} or level is not None)
        el_type = "code" if is_code else ("title" if is_title else "text")
        metadata: Dict[str, Any] = {
            "source": "mineru",
            "modality": "mineru_code" if is_code else "mineru_text",
            "raw_type": raw_type,
            **bbox_meta,
        }
        if sub_type:
            metadata["sub_type"] = sub_type
        if is_code:
            # 保留代码相关上下文，便于前端渲染和后续调试语言识别质量。
            metadata["guess_lang"] = str(item.get("guess_lang") or "").strip().lower() or None
            metadata["code_caption"] = item.get("code_caption") or []
        if level is not None:
            metadata["level"] = level
        elements.append(
            ParserElement(
                type=el_type,
                content=text,
                page_no=page_no,
                bbox=bbox,
                metadata=metadata,
            )
        )

    elements.sort(
        key=lambda e: (
            int(e.get("page_no", 0)),
            float((e.get("bbox") or [0.0, 0.0, 0.0, 0.0])[1]),
            float((e.get("bbox") or [0.0, 0.0, 0.0, 0.0])[0]),
        )
    )
    return elements


def rewrite_markdown_image_links(markdown: str, image_assets: Dict[str, Dict[str, Any]]) -> str:
    if not markdown:
        return ""
    out = markdown
    for image_id in image_assets.keys():
        out = out.replace(f"images/{image_id}", f"pdf://embedded/{image_id}")
        out = out.replace(f"./images/{image_id}", f"pdf://embedded/{image_id}")
    return out
