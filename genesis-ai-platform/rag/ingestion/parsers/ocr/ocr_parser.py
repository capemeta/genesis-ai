"""OCR parser implemented via OCRPipeline."""

from io import BytesIO
from typing import Any, Dict, Tuple

from PIL import Image

from ..base import BaseParser
from .pipeline import OCRPipeline, OCRPipelineConfig


class OCRParser(BaseParser):
    SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    def __init__(self, **kwargs):
        self.pipeline = OCRPipeline(
            OCRPipelineConfig(
                legacy_mode=bool(kwargs.get("ocr_legacy_mode", False)),
                preprocess_enabled=bool(kwargs.get("ocr_preprocess_enabled", True)),
                red_seal_suppression_enabled=bool(kwargs.get("ocr_red_seal_suppression", True)),
                post_correction_enabled=bool(kwargs.get("ocr_post_correction_enabled", True)),
                tesseract_psm_list=kwargs.get("ocr_tesseract_psm_list"),
                min_confidence=float(kwargs.get("ocr_min_confidence", 45.0)),
                enable_paddle_ocr=bool(kwargs.get("enable_paddle_ocr", False)),
            )
        )
        self.ocr_engine = str(kwargs.get("ocr_engine", "auto")).lower()
        self.ocr_languages = kwargs.get("ocr_languages", ["ch", "en"])

    def supports(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, file_buffer: bytes, file_extension: str) -> Tuple[str, Dict[str, Any]]:
        ext = file_extension.lower()
        if ext == ".pdf":
            lines = self._parse_pdf(file_buffer)
        else:
            lines = self._parse_image(file_buffer)

        text = "\n".join([str(x.get("text") or "").strip() for x in lines if str(x.get("text") or "").strip()])
        metadata = {
            "parse_method": "ocr_pipeline",
            "ocr_engine": self.ocr_engine,
            "line_count": len(lines),
        }
        return text, metadata

    def _parse_image(self, file_buffer: bytes):
        image = Image.open(BytesIO(file_buffer)).convert("RGB")
        engine = self.pipeline.resolve_engine(self.ocr_engine)
        if not engine:
            return []
        return self.pipeline.recognize(image=image, engine=engine, languages=self.ocr_languages)

    def _parse_pdf(self, file_buffer: bytes):
        try:
            import pypdfium2 as pdfium
        except Exception:
            return []

        out = []
        pdf = pdfium.PdfDocument(file_buffer)
        try:
            engine = self.pipeline.resolve_engine(self.ocr_engine)
            if not engine:
                return []
            for i in range(len(pdf)):
                bitmap = pdf[i].render(scale=2.0)
                image = bitmap.to_pil()
                out.extend(self.pipeline.recognize(image=image, engine=engine, languages=self.ocr_languages))
            return out
        finally:
            pdf.close()
