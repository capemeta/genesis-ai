"""OCR parser module."""

from .enhancer import OCREnhancer, OCREnhancerConfig
from .engines import OCREngine, PaddleOCREngine, TesseractOCREngine
from .ocr_parser import OCRParser
from .pipeline import OCRPipeline, OCRPipelineConfig, TESSERACT_SETUP_HINT, ensure_tesseract_cmd, get_tesseract_exe_path
from .cache import OCRCache, get_global_cache, clear_global_cache, compute_image_hash
from .parallel import ParallelOCRExecutor, get_global_executor

__all__ = [
    "OCRParser",
    "OCREnhancer",
    "OCREnhancerConfig",
    "OCRPipeline",
    "OCRPipelineConfig",
    "OCREngine",
    "PaddleOCREngine",
    "TesseractOCREngine",
    "TESSERACT_SETUP_HINT",
    "ensure_tesseract_cmd",
    "get_tesseract_exe_path",
    # 缓存和并行
    "OCRCache",
    "get_global_cache",
    "clear_global_cache",
    "compute_image_hash",
    "ParallelOCRExecutor",
    "get_global_executor",
]
