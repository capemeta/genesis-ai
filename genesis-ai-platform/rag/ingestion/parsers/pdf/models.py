from typing import List, Dict, Any, TypedDict, Optional


class ParserElement(TypedDict):
    """
    PDF parser normalized element.
    """
    type: str
    content: str
    page_no: int  # 0-based page index
    bbox: List[float]  # [x0, y0, x1, y1] top-down page coordinates
    metadata: Dict[str, Any]
    # OCR metadata convention:
    # source: "native" | "ocr" | "vision"
    # modality: "pdf_text_layer" | "ocr_text" | "vision_text"
    # ocr_engine: "paddleocr" | "tesseract"
    # ocr_languages: List[str]
    # ocr_confidence: float
    # Vision reserved fields:
    # vision_enabled: bool
    # vision_model: Optional[str]
    # vision_text: Optional[str]
    # vision_confidence: Optional[float]
