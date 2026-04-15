import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .enhancer import OCREnhancer, OCREnhancerConfig
from .engines import OCREngine, PaddleOCREngine, TesseractOCREngine
from .engines.tesseract_engine import (
    TESSERACT_SETUP_HINT,
    ensure_tesseract_cmd,
    get_tesseract_exe_path,
)
from .cache import get_global_cache, compute_image_hash
from .parallel import get_global_executor

logger = logging.getLogger(__name__)


@dataclass
class OCRPipelineConfig:
    legacy_mode: bool = False
    preprocess_enabled: bool = True
    red_seal_suppression_enabled: bool = True
    post_correction_enabled: bool = True
    tesseract_psm_list: Optional[List[int]] = None
    min_confidence: float = 45.0
    # 默认关闭 PaddleOCR，避免未安装可选依赖时优先探测重引擎。
    enable_paddle_ocr: bool = False
    variant_strategy: str = "conservative"  # minimal, conservative, balanced, aggressive
    # 🔧 新增：并行和缓存配置
    enable_parallel: bool = False  # 是否启用并行处理（多变体/多 PSM 时）
    parallel_max_workers: int = 4  # 并行线程数
    enable_cache: bool = True  # 是否启用结果缓存
    cache_max_size: int = 100  # 缓存最大条目数
    cache_ttl_seconds: int = 3600  # 缓存过期时间（秒）


class OCRPipeline:
    def __init__(self, config: OCRPipelineConfig):
        self.config = config
        self.enhancer = OCREnhancer(
            OCREnhancerConfig(
                preprocess_enabled=(False if config.legacy_mode else config.preprocess_enabled),
                red_seal_suppression_enabled=(False if config.legacy_mode else config.red_seal_suppression_enabled),
                post_correction_enabled=(False if config.legacy_mode else config.post_correction_enabled),
                variant_strategy=(config.variant_strategy if not config.legacy_mode else "minimal"),
            )
        )
        self._tesseract_psm_list = [6] if config.legacy_mode else self._normalize_tesseract_psm_list(config.tesseract_psm_list)
        self._engines: Dict[str, OCREngine] = {
            "tesseract": TesseractOCREngine(),
        }
        if config.enable_paddle_ocr:
            self._engines["paddleocr"] = PaddleOCREngine()
        
        # 🔧 初始化缓存和并行执行器
        self._cache = None
        self._parallel_executor = None
        if config.enable_cache:
            self._cache = get_global_cache(
                max_size=config.cache_max_size,
                ttl_seconds=config.cache_ttl_seconds
            )
        if config.enable_parallel:
            self._parallel_executor = get_global_executor(
                max_workers=config.parallel_max_workers,
                timeout_seconds=30
            )

    def resolve_engine(self, preferred_engine: str) -> Optional[str]:
        if preferred_engine == "auto":
            # 默认优先轻量依赖，只有显式开启后才尝试 PaddleOCR。
            candidates = ["tesseract", "paddleocr"] if self.config.enable_paddle_ocr else ["tesseract"]
        elif preferred_engine == "paddleocr" and not self.config.enable_paddle_ocr:
            logger.warning("[OCRPipeline] 已请求 paddleocr，但当前配置未启用，自动降级为 tesseract")
            candidates = ["tesseract"]
        else:
            candidates = [preferred_engine]
        for candidate in candidates:
            engine = self._engines.get(candidate)
            if engine and engine.is_available():
                return candidate
        return None

    def recognize(
        self,
        image,
        engine: str,
        languages: List[str],
    ) -> List[Dict[str, Any]]:
        impl = self._engines.get(engine)
        if impl is None:
            return []

        # 🔧 缓存支持：计算图像哈希
        image_hash = None
        if self._cache is not None:
            image_hash = compute_image_hash(image)
            
            # 尝试从缓存获取结果
            cached_result = self._cache.get(
                image_hash=image_hash,
                engine=engine,
                languages=languages,
                variant="combined",  # 缓存合并后的结果
                min_confidence=self.config.min_confidence,
            )
            if cached_result is not None:
                logger.debug(f"[OCRPipeline] 缓存命中: engine={engine}, lines={len(cached_result)}")
                return cached_result

        # 执行识别
        lines = impl.recognize(
            image=image,
            languages=languages,
            legacy_mode=self.config.legacy_mode,
            enhancer=self.enhancer,
            psm_list=self._tesseract_psm_list,
            min_confidence=self.config.min_confidence,
            enable_parallel=self.config.enable_parallel,
            parallel_executor=self._parallel_executor,
        )
        
        # 合并结果
        if self.config.legacy_mode:
            final_lines = lines
        else:
            final_lines = self._fuse_lines(lines)
        
        # 🔧 缓存结果
        if self._cache is not None and image_hash is not None:
            self._cache.put(
                image_hash=image_hash,
                engine=engine,
                languages=languages,
                result=final_lines,
                variant="combined",
                min_confidence=self.config.min_confidence,
            )
            logger.debug(f"[OCRPipeline] 结果已缓存: engine={engine}, lines={len(final_lines)}")
        
        return final_lines

    def _normalize_tesseract_psm_list(self, raw_value: Optional[List[int]]) -> List[int]:
        default = [6]
        if raw_value is None:
            return default
        vals = raw_value if isinstance(raw_value, (list, tuple)) else re.split(r"[,\s]+", str(raw_value).strip())
        out: List[int] = []
        for x in vals:
            if x is None or str(x).strip() == "":
                continue
            try:
                psm = int(x)
            except Exception:
                continue
            if 0 <= psm <= 13 and psm not in out:
                out.append(psm)
        return out or default

    def _fuse_lines(self, lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not lines:
            return []
        best_by_bucket: Dict[Tuple[int, int, int], Dict[str, Any]] = {}
        for line in lines:
            text = str(line.get("text") or "").strip()
            if not text:
                continue
            conf = float(line.get("confidence") or 0.0)
            x0, y0, x1, y1 = [float(v) for v in (line.get("bbox") or [0.0, 0.0, 0.0, 0.0])]
            h = max(y1 - y0, 1.0)
            bucket = (round(y0 / 8.0), round(x0 / 14.0), round(h / 4.0))
            variant = str(line.get("variant") or "")
            score = conf + (3.0 if variant == "original" else 0.0)
            current = best_by_bucket.get(bucket)
            if not current or score > float(current.get("_score", 0.0)):
                best_by_bucket[bucket] = {
                    "text": text,
                    "confidence": conf,
                    "bbox": [x0, y0, x1, y1],
                    "_score": score,
                }
        out = []
        for row in best_by_bucket.values():
            row.pop("_score", None)
            out.append(row)
        out.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
        return out
    
    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计字典，如果未启用缓存则返回 None
        """
        if self._cache is None:
            return None
        return self._cache.get_stats()
    
    def clear_cache(self) -> None:
        """清空缓存"""
        if self._cache is not None:
            self._cache.clear()
    
    def cleanup_expired_cache(self) -> int:
        """
        清理过期的缓存条目
        
        Returns:
            清理的条目数
        """
        if self._cache is None:
            return 0
        return self._cache.cleanup_expired()
