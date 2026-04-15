from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ...base import BaseParser
from ..base_pdf_parser import BasePDFParser
from ..models import ParserElement
from .client import MinerUClient
from .mapper import (
    build_image_assets,
    extract_page_sizes_from_middle_json,
    infer_normalized_pages_from_content_list,
    load_json_field,
    map_content_list_to_elements,
    rewrite_markdown_image_links,
)

logger = logging.getLogger(__name__)


class MinerUParser(BaseParser):
    SUPPORTED_EXTENSIONS = {".pdf"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = self._normalize_config(self.config)
        self.client = MinerUClient(self.config)

    @staticmethod
    def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = dict(config or {})
        nested = merged.get("pdf_parser_config")
        if isinstance(nested, dict):
            merged.update(nested)
        return merged

    def supports(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS

    def _resolve_preview_md_source(self) -> str:
        """
        控制“预览 Markdown 来源”的策略：
        - auto:        优先用 MinerU 返回的 md_content；若为空则回退 content_list 转换
        - api_md:      强制优先用 md_content；若为空仍回退 content_list 转换（避免无预览）
        - content_list:始终基于 content_list/elements 生成 Markdown，保证与入库块更一致

        可通过两种方式配置（优先级从高到低）：
        1) pdf_parser_config.mineru_preview_md_source
        2) 环境变量 MINERU_PREVIEW_MD_SOURCE
        """
        raw = self.config.get("mineru_preview_md_source", os.getenv("MINERU_PREVIEW_MD_SOURCE", "auto"))
        mode = str(raw or "auto").strip().lower()
        if mode not in {"auto", "api_md", "content_list"}:
            return "auto"
        return mode

    def parse(self, file_buffer: bytes, file_extension: str) -> Tuple[str, Dict[str, Any]]:
        elements, metadata = self.parse_to_elements(file_buffer=file_buffer, file_extension=file_extension)
        md_from_api = str(metadata.get("mineru_markdown") or "").strip()
        md_from_content_list = BasePDFParser.to_markdown(elements)

        preview_mode = self._resolve_preview_md_source()
        preview_source_used = "content_list"
        if preview_mode in {"auto", "api_md"} and md_from_api:
            markdown = md_from_api
            preview_source_used = "api_md"
        else:
            markdown = md_from_content_list
            preview_source_used = "content_list"

        # 记录当前预览策略与实际命中的来源，便于后续排查“为什么预览和分块不一致”
        metadata["preview_md_mode"] = preview_mode
        metadata["preview_md_source_used"] = preview_source_used
        return markdown, metadata

    def parse_to_elements(
        self,
        file_buffer: bytes,
        file_extension: str = ".pdf",
    ) -> Tuple[List[ParserElement], Dict[str, Any]]:
        if not self.supports(file_extension):
            raise ValueError(f"MinerUParser does not support: {file_extension}")

        logger.info("[MinerUParser] start parsing with MinerU /file_parse")
        file_name = str(self.config.get("mineru_file_name") or f"document{file_extension}")
        payload = self.client.parse_pdf(file_buffer=file_buffer, file_name=file_name)

        backend = payload.get("backend")
        version = payload.get("version")
        results = payload.get("results")
        if not isinstance(results, dict) or not results:
            raise RuntimeError("MinerU response missing results")

        requested_key = Path(file_name).stem
        result_key = requested_key
        item = results.get(requested_key)
        if not isinstance(item, dict):
            first_valid = next(((k, v) for k, v in results.items() if isinstance(v, dict)), None)
            if first_valid is not None:
                result_key, item = first_valid
            else:
                item = None
        if not isinstance(item, dict):
            raise RuntimeError("MinerU response contains invalid result item")

        raw_content_list = load_json_field(item.get("content_list"))
        content_list = raw_content_list if isinstance(raw_content_list, list) else []
        middle_json = load_json_field(item.get("middle_json"))
        page_sizes = extract_page_sizes_from_middle_json(middle_json)
        normalized_canvas_size = float(self.config.get("mineru_content_bbox_canvas_size", 1000.0))
        normalized_pages = infer_normalized_pages_from_content_list(
            content_list=content_list,
            page_sizes=page_sizes,
        )

        image_assets_map = build_image_assets(item.get("images") or item.get("image_list") or item.get("imgs"))
        elements = map_content_list_to_elements(
            content_list=content_list,
            image_assets=image_assets_map,
            page_sizes=page_sizes,
            # 当前样例里 MinerU content_list bbox 明显落在近似 1000x1000 归一化空间。
            normalized_canvas_size=normalized_canvas_size,
        )
        logger.info(
            "[MinerUParser] bbox normalization probe: content_items=%d page_sizes=%s normalized_pages=%s canvas=%s",
            len(content_list),
            {k: [round(v[0], 2), round(v[1], 2)] for k, v in page_sizes.items()},
            normalized_pages,
            normalized_canvas_size,
        )
        for idx, raw_item in enumerate(content_list[:5]):
            if not isinstance(raw_item, dict):
                continue
            raw_bbox = raw_item.get("bbox")
            page_no = raw_item.get("page_idx", raw_item.get("page_no"))
            if idx >= len(elements):
                logger.info(
                    "[MinerUParser] sample[%d] raw_page=%s raw_bbox=%s -> no_mapped_element",
                    idx,
                    page_no,
                    raw_bbox,
                )
                continue
            mapped = elements[idx]
            logger.info(
                "[MinerUParser] sample[%d] raw_page=%s raw_bbox=%s -> mapped_bbox=%s normalized=%s source_space=%s",
                idx,
                page_no,
                raw_bbox,
                mapped.get("bbox"),
                (mapped.get("metadata") or {}).get("bbox_normalized"),
                (mapped.get("metadata") or {}).get("bbox_source_space"),
            )

        # Fallback when content_list is empty but md_content exists.
        md_content = str(item.get("md_content") or "")
        rewritten_md = rewrite_markdown_image_links(md_content, image_assets_map)
        if not elements and rewritten_md.strip():
            elements = [
                ParserElement(
                    type="text",
                    content=rewritten_md,
                    page_no=0,
                    bbox=[0.0, 0.0, 0.0, 0.0],
                    metadata={"source": "mineru", "fallback": True, "modality": "mineru_markdown"},
                )
            ]

        pdf_embedded_images = []
        for image_id, asset in image_assets_map.items():
            matched_page = None
            matched_bbox = None
            for el in elements:
                meta = el.get("metadata") or {}
                if str(meta.get("image_id") or "") != image_id:
                    continue
                matched_page = int(el.get("page_no", 0))
                matched_bbox = el.get("bbox")
                break
            pdf_embedded_images.append(
                {
                    "id": image_id,
                    "content_type": asset.get("content_type") or "application/octet-stream",
                    "ext": asset.get("ext") or ".bin",
                    "size": int(asset.get("size") or 0),
                    "blob": asset.get("blob"),
                    "page_no": matched_page,
                    "bbox": matched_bbox,
                }
            )

        metadata: Dict[str, Any] = {
            "parser": "mineru",
            "parse_method": "mineru_file_parse_api",
            "element_count": len(elements),
            "elements": elements,
            "pdf_embedded_images": pdf_embedded_images,
            "ocr": {
                "enabled": True,
                "element_count": len(elements),
                "page_count": len({int(el.get("page_no", 0)) for el in elements}),
                "engines": ["mineru"],
            },
            "vision": {
                "enabled": False,
                "element_count": 0,
                "page_count": 0,
            },
            "mineru": {
                "backend": backend,
                "version": version,
                "result_key": result_key,
                "content_list_count": len(content_list),
                "image_count": len(pdf_embedded_images),
                "return_md": bool(md_content),
            },
            "mineru_markdown": rewritten_md,
        }

        # Keep these fields for debug compatibility with MinerU official response shape.
        model_output = load_json_field(item.get("model_output"))
        if isinstance(middle_json, (dict, list)):
            metadata["mineru_middle_json"] = middle_json
        if isinstance(model_output, (dict, list)):
            metadata["mineru_model_output"] = model_output

        logger.info(
            "[MinerUParser] parse complete: backend=%s version=%s elements=%d images=%d",
            backend,
            version,
            len(elements),
            len(pdf_embedded_images),
        )
        return elements, metadata
