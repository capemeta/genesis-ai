from __future__ import annotations

import io
import logging
import os
import re
import shutil
import tempfile
from typing import Any, Dict, List, Tuple

from ..base_pdf_parser import BasePDFParser
from ..models import ParserElement
from ..native import NativePDFParser
from ...base import BaseParser
from .element_mapper import DoclingElementMapper

logger = logging.getLogger(__name__)


class DoclingParser(BaseParser):
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".md"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = self._normalize_config(self.config)
        self.mapper = DoclingElementMapper()
        self._resolved_docling_ocr_engine = str(self.config.get("ocr_engine", "auto")).strip().lower()
        # Backend policy: always use external OCR path for docling parser.
        self._use_external_ocr = True

    @staticmethod
    def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = dict(config or {})
        nested = merged.get("pdf_parser_config")
        if isinstance(nested, dict):
            merged.update(nested)
        return merged

    def supports(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, file_buffer: bytes, file_extension: str) -> Tuple[str, Dict[str, Any]]:
        try:
            elements, metadata = self.parse_to_elements(file_buffer=file_buffer, file_extension=file_extension)
            markdown_text = BasePDFParser.to_markdown(elements)
            return markdown_text, metadata
        except Exception as e:
            logger.error("[DoclingParser] parse failed: %s", e)
            if self._should_fallback_to_native(e):
                logger.warning("[DoclingParser] fallback to NativePDFParser due to docling failure")
                return self._parse_with_native_fallback(file_buffer=file_buffer)
            # Never return error text as parsed content, otherwise it will be chunked and indexed.
            raise

    def parse_to_elements(self, file_buffer: bytes, file_extension: str) -> Tuple[List[ParserElement], Dict[str, Any]]:
        logger.info("[DoclingParser] start parsing, extension=%s", file_extension)
        from docling.document_converter import DocumentConverter

        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp:
            tmp.write(file_buffer)
            tmp_path = tmp.name

        try:
            converter = self._build_converter(DocumentConverter)
            result = converter.convert(tmp_path)
            doc = result.document

            elements: List[ParserElement] = []
            elements.extend(self.mapper.extract_text_elements(doc))
            elements.extend(self.mapper.extract_table_elements(doc))

            image_elements, embedded_images = self.mapper.extract_image_elements(doc)
            elements.extend(image_elements)
            embedded_images = self._hydrate_missing_embedded_images(
                file_buffer=file_buffer,
                elements=elements,
                embedded_images=embedded_images,
            )
            external_ocr_elements: List[ParserElement] = []
            if bool(self.config.get("enable_ocr", True)) and self._use_external_ocr:
                external_ocr_elements = self._collect_external_ocr_elements(file_buffer)
                if external_ocr_elements:
                    elements.extend(external_ocr_elements)

            elements.sort(key=lambda x: (int(x.get("page_no", 0)), float(x.get("bbox", [0.0, 0.0, 0.0, 0.0])[1])))

            doc_markdown = ""
            try:
                doc_markdown = doc.export_to_markdown() or ""
            except Exception:
                doc_markdown = ""

            ocr_elements = [el for el in elements if (el.get("metadata") or {}).get("source") == "ocr"]
            metadata: Dict[str, Any] = {
                "parser": "docling",
                "parse_method": "docling_external_ocr_hybrid" if self._use_external_ocr else "docling",
                "element_count": len(elements),
                "elements": elements,
                "pdf_embedded_images": embedded_images,
                "ocr": {
                    "enabled": bool(self.config.get("enable_ocr", True)),
                    "element_count": len(ocr_elements),
                    "page_count": len({int(el.get("page_no", -1)) for el in ocr_elements}),
                    "engines": sorted(
                        {
                            str((el.get("metadata") or {}).get("ocr_engine"))
                            for el in ocr_elements
                            if (el.get("metadata") or {}).get("ocr_engine")
                        }
                    ) if ocr_elements else (
                        [self._resolved_docling_ocr_engine] if bool(self.config.get("enable_ocr", True)) and not self._use_external_ocr else []
                    ),
                    "requested_engine": str(self.config.get("ocr_engine", "auto")).strip().lower(),
                    "resolved_engine": "external" if self._use_external_ocr else self._resolved_docling_ocr_engine,
                    "backend": "external" if self._use_external_ocr else "docling",
                },
                "vision": {
                    "enabled": False,
                    "element_count": 0,
                    "page_count": 0,
                },
                "docling": {
                    "page_count": len(getattr(doc, "pages", []) or []),
                    "table_count": len(getattr(doc, "tables", []) or []),
                    "image_count": len(getattr(doc, "pictures", []) or []),
                    "group_count": len(getattr(doc, "groups", []) or []),
                    "text_count": len(getattr(doc, "texts", []) or []),
                },
                "docling_markdown": doc_markdown,
            }
            return elements, metadata
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _build_converter(self, document_converter_cls: Any):
        try:
            from docling.document_converter import PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                OcrAutoOptions,
                PdfPipelineOptions,
                RapidOcrOptions,
                TesseractCliOcrOptions,
            )

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = bool(self.config.get("enable_ocr", True)) and (not self._use_external_ocr)
            pipeline_options.do_table_structure = bool(self.config.get("extract_tables", True))
            if pipeline_options.do_ocr:
                docling_ocr_options, resolved_engine = self._build_docling_ocr_options(
                    OcrAutoOptions=OcrAutoOptions,
                    RapidOcrOptions=RapidOcrOptions,
                    TesseractCliOcrOptions=TesseractCliOcrOptions,
                )
                pipeline_options.ocr_options = docling_ocr_options
                logger.info(
                    "[DoclingParser] OCR configured: requested=%s, resolved=%s",
                    str(self.config.get("ocr_engine", "auto")).lower(),
                    resolved_engine,
                )
                self._resolved_docling_ocr_engine = resolved_engine
            else:
                self._resolved_docling_ocr_engine = "external" if self._use_external_ocr else "disabled"
            return document_converter_cls(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        except Exception:
            return document_converter_cls()

    def _collect_external_ocr_elements(self, file_buffer: bytes) -> List[ParserElement]:
        parser = NativePDFParser(
            enable_ocr=True,
            ocr_engine=str(self.config.get("ocr_engine", "auto")).lower(),
            ocr_languages=self.config.get("ocr_languages", ["ch", "en"]),
            extract_images=False,
            extract_tables=False,
            ocr_reflow_enabled=False,
            ocr_legacy_mode=bool(self.config.get("ocr_legacy_mode", False)),
            ocr_preprocess_enabled=bool(self.config.get("ocr_preprocess_enabled", True)),
            ocr_red_seal_suppression=bool(self.config.get("ocr_red_seal_suppression", True)),
            ocr_post_correction_enabled=bool(self.config.get("ocr_post_correction_enabled", True)),
            ocr_tesseract_psm_list=self.config.get("ocr_tesseract_psm_list"),
            ocr_min_confidence=float(self.config.get("ocr_min_confidence", 45.0)),
        )
        native_elements = parser.parse(file_buffer)
        return [el for el in native_elements if (el.get("metadata") or {}).get("source") == "ocr"]

    def _hydrate_missing_embedded_images(
        self,
        file_buffer: bytes,
        elements: List[ParserElement],
        embedded_images: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        existing_ids = {str(img.get("id") or "") for img in (embedded_images or [])}
        target_images: List[Tuple[str, int, List[float]]] = []
        for el in elements:
            if str(el.get("type") or "").lower() != "image":
                continue
            meta = el.get("metadata") or {}
            image_id = str(meta.get("image_id") or "").strip()
            if not image_id or image_id in existing_ids:
                continue
            if not bool(meta.get("unavailable_blob", False)):
                continue
            page_no = int(el.get("page_no", -1))
            bbox = el.get("bbox")
            if page_no < 0 or not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            target_images.append((image_id, page_no, [float(v) for v in bbox]))

        if not target_images:
            return embedded_images

        try:
            import pypdfium2 as pdfium
        except Exception:
            logger.warning("[DoclingParser] cannot hydrate missing image blobs: pypdfium2 is unavailable")
            return embedded_images

        hydrated = list(embedded_images or [])
        pdf = pdfium.PdfDocument(file_buffer)
        try:
            for image_id, raw_page_no, bbox in target_images:
                page_index = raw_page_no
                if page_index < 0 or page_index >= len(pdf):
                    continue

                page = pdf[page_index]
                width, height = page.get_size()
                bitmap = page.render(scale=2.0)
                pil = bitmap.to_pil()

                x0, y0, x1, y1 = bbox
                left = max(0, min(int(x0 * 2), pil.width))
                top = max(0, min(int(y0 * 2), pil.height))
                right = max(0, min(int(x1 * 2), pil.width))
                bottom = max(0, min(int(y1 * 2), pil.height))

                # Fallback: if bbox is not usable, skip instead of storing invalid image.
                if right <= left or bottom <= top:
                    continue
                # Basic size guard to avoid tiny noise regions.
                if (right - left) < max(int(width * 0.01), 12) or (bottom - top) < max(int(height * 0.01), 12):
                    continue

                crop = pil.crop((left, top, right, bottom))
                bio = io.BytesIO()
                crop.save(bio, format="PNG")
                blob = bio.getvalue()
                if not blob:
                    continue
                hydrated.append(
                    {
                        "id": image_id,
                        "content_type": "image/png",
                        "ext": ".png",
                        "size": len(blob),
                        "blob": blob,
                        "page_no": page_index,
                        "bbox": [x0, y0, x1, y1],
                    }
                )
                existing_ids.add(image_id)
        except Exception as e:
            logger.warning("[DoclingParser] hydrate missing image blobs failed: %s", e)
        finally:
            pdf.close()

        return hydrated

    def _build_docling_ocr_options(
        self,
        OcrAutoOptions: Any,
        RapidOcrOptions: Any,
        TesseractCliOcrOptions: Any,
    ) -> Tuple[Any, str]:
        requested_engine = str(self.config.get("ocr_engine", "auto")).strip().lower()
        languages = self._to_docling_ocr_langs(self.config.get("ocr_languages") or [])

        if requested_engine == "tesseract":
            return self._build_tesseract_options(TesseractCliOcrOptions, languages), "tesseract"

        # Docling does not support PaddleOCR natively.
        if requested_engine == "paddleocr":
            if self._has_tesseract():
                logger.warning(
                    "[DoclingParser] requested ocr_engine=paddleocr, but docling has no paddleocr engine; "
                    "switching to tesseract."
                )
                return self._build_tesseract_options(TesseractCliOcrOptions, languages), "tesseract"
            logger.warning(
                "[DoclingParser] requested ocr_engine=paddleocr, but docling has no paddleocr engine; "
                "switching to rapidocr."
            )
            return RapidOcrOptions(), "rapidocr"

        if requested_engine == "rapidocr":
            return RapidOcrOptions(), "rapidocr"

        return OcrAutoOptions(), "auto"

    def _build_tesseract_options(self, TesseractCliOcrOptions: Any, languages: List[str]) -> Any:
        tesseract_cmd = self._resolve_tesseract_cmd()
        kwargs: Dict[str, Any] = {}
        if languages:
            kwargs["lang"] = languages
        if tesseract_cmd:
            kwargs["tesseract_cmd"] = tesseract_cmd
        return TesseractCliOcrOptions(**kwargs)

    def _resolve_tesseract_cmd(self) -> str | None:
        env_cmd = str(os.getenv("TESSERACT_CMD", "")).strip()
        if env_cmd:
            return env_cmd

        env_home = str(os.getenv("TESSERACT_HOME", "")).strip()
        if env_home:
            candidate = os.path.join(env_home, "tesseract.exe")
            if os.path.isfile(candidate):
                return candidate

        which_cmd = shutil.which("tesseract")
        if which_cmd:
            return which_cmd
        return None

    def _has_tesseract(self) -> bool:
        return self._resolve_tesseract_cmd() is not None

    def _to_docling_ocr_langs(self, langs: List[str]) -> List[str]:
        mapping = {
            "en": "eng",
            "eng": "eng",
            "ch": "chi_sim",
            "zh": "chi_sim",
            "zh-cn": "chi_sim",
            "chi_sim": "chi_sim",
        }
        out: List[str] = []
        for lang in langs:
            key = str(lang or "").strip().lower()
            if not key:
                continue
            mapped = mapping.get(key, key)
            if mapped not in out:
                out.append(mapped)
        return out

    def _should_fallback_to_native(self, err: Exception) -> bool:
        if not bool(self.config.get("fallback_to_native", True)):
            return False
        message = str(err or "").lower()
        # 依赖缺失时直接降级，确保在未安装 docling 的开源默认环境下也能稳定运行。
        if isinstance(err, (ImportError, ModuleNotFoundError)):
            return True
        if "no module named 'docling'" in message or 'no module named "docling"' in message:
            return True
        # Windows 上 docling 首次装载 layout 模型时，若虚拟内存不足会抛 1455。
        # 这类错误和文档本身无关，继续强制走 docling 成功率很低，直接退回 native 更稳。
        if "os error 1455" in message or "页面文件太小" in message or "paging file is too small" in message:
            return True
        if re.search(r"(out of memory|cannot allocate memory|not enough memory)", message):
            return True
        if "hub" in message and "snapshot" in message:
            return True
        if "internet connection" in message:
            return True
        # HF model cache miss / network related failures.
        if re.search(r"(hf|huggingface|download|offline|connection|timeout)", message):
            return True
        return False

    def _parse_with_native_fallback(self, file_buffer: bytes) -> Tuple[str, Dict[str, Any]]:
        parser = NativePDFParser(
            enable_ocr=bool(self.config.get("enable_ocr", True)),
            ocr_engine=str(self.config.get("ocr_engine", "auto")).lower(),
            ocr_languages=self.config.get("ocr_languages", ["ch", "en"]),
            extract_images=bool(self.config.get("extract_images", False)),
            extract_tables=bool(self.config.get("extract_tables", True)),
        )
        elements = parser.parse(file_buffer)
        text = BasePDFParser.to_markdown(elements)
        ocr_elements = [el for el in elements if (el.get("metadata") or {}).get("source") == "ocr"]
        metadata: Dict[str, Any] = {
            "parser": "docling",
            "effective_parser": "native",
            "fallback_from": "docling",
            "fallback_to": "native",
            "parse_method": "docling_with_native_fallback",
            "element_count": len(elements),
            "elements": elements,
            "pdf_embedded_images": [],
            "ocr": {
                "enabled": bool(self.config.get("enable_ocr", True)),
                "element_count": len(ocr_elements),
                "page_count": len({int(el.get("page_no", -1)) for el in ocr_elements}),
                "engines": sorted(
                    {
                        str((el.get("metadata") or {}).get("ocr_engine"))
                        for el in ocr_elements
                        if (el.get("metadata") or {}).get("ocr_engine")
                    }
                ),
            },
            "vision": {"enabled": False, "element_count": 0, "page_count": 0},
        }
        return text, metadata
