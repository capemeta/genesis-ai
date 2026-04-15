import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class OCREnhancerConfig:
    preprocess_enabled: bool = True
    red_seal_suppression_enabled: bool = True
    post_correction_enabled: bool = True
    variant_strategy: str = "conservative"  # minimal, conservative, balanced, aggressive
    # 🔧 新增：智能文本修正
    enable_smart_correction: bool = True  # 启用智能文本修正
    enable_digit_correction: bool = True  # 启用数字修正
    enable_seal_filtering: bool = True  # 启用印章区域过滤


class OCREnhancer:
    """Engine-agnostic OCR image/text enhancer."""

    _AMOUNT_CHAR_HINT = re.compile(r"[万仟佰拾元圆角分整]")
    _SPACING_BETWEEN_CJK = re.compile(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])")
    _PERCENT_TAIL = re.compile(r"\b(\d{1,3})5[%％]\s*[6６]\b")
    _BROKEN_PERCENT = re.compile(r"(\d)\s*[%％]\s*[6６]\b")

    def __init__(self, config: OCREnhancerConfig):
        self.config = config

    def build_variants(self, image, strategy: Optional[str] = None) -> List[Tuple[str, object]]:
        """
        根据策略生成图像变体，避免不必要的预处理计算
        
        Args:
            image: 原始图像
            strategy: 变体生成策略，优先级高于 config 中的设置
                - "minimal": 只返回原图（最快，适合高质量扫描件）
                - "conservative": 原图 + 二值化（默认，平衡性能和效果）
                - "balanced": 原图 + 二值化 + 去红章（适合有印章的文档）
                - "aggressive": 所有变体（最慢，适合低质量扫描件）
        
        Returns:
            变体列表 [(变体名称, 图像对象), ...]
        """
        # 优先使用传入的策略，否则使用配置中的策略
        effective_strategy = strategy or self.config.variant_strategy
        
        # 如果预处理被禁用或策略为 minimal，只返回原图
        if not self.config.preprocess_enabled or effective_strategy == "minimal":
            return [("original", image)]

        variants: List[Tuple[str, object]] = [("original", image)]

        # Conservative: 原图 + 二值化
        if effective_strategy in ("conservative", "balanced", "aggressive"):
            binary = self._to_binary(image)
            if binary is not None:
                variants.append(("binary", binary))

        # Balanced: 原图 + 二值化 + 去红章
        if effective_strategy in ("balanced", "aggressive") and self.config.red_seal_suppression_enabled:
            stamp_free = self._suppress_red_stamp(image)
            if stamp_free is not None:
                variants.append(("stamp_suppressed", stamp_free))
                
                # Aggressive: 还包括去红章后的二值化
                if effective_strategy == "aggressive":
                    stamp_free_binary = self._to_binary(stamp_free)
                    if stamp_free_binary is not None:
                        variants.append(("stamp_suppressed_binary", stamp_free_binary))

        return variants

    def post_correct_text(self, text: str) -> str:
        if not text:
            return text

        out = str(text).strip()
        out = self._SPACING_BETWEEN_CJK.sub("", out)
        out = out.replace("％", "%")

        if self.config.post_correction_enabled:
            out = self._PERCENT_TAIL.sub(r"\1%", out)
            out = self._BROKEN_PERCENT.sub(r"\1%", out)
            out = self._fix_amount_context(out)

        return out

    def _fix_amount_context(self, text: str) -> str:
        if not self._AMOUNT_CHAR_HINT.search(text):
            return text

        replacements = {
            "歇": "叁",
            "陸": "陆",
            "園": "圆",
            "员": "圆",
        }
        out = text
        for src, dst in replacements.items():
            out = out.replace(src, dst)
        return out

    def _to_binary(self, image):
        try:
            import numpy as np
            from PIL import Image, ImageFilter, ImageOps

            gray = ImageOps.grayscale(image)
            gray = ImageOps.autocontrast(gray)
            gray = gray.filter(ImageFilter.MedianFilter(size=3))

            arr = np.array(gray, dtype=np.uint8)
            threshold = int(arr.mean())
            binary = (arr > threshold).astype(np.uint8) * 255
            return Image.fromarray(binary, mode="L")
        except Exception:
            return None

    def _suppress_red_stamp(self, image):
        try:
            import numpy as np
            from PIL import Image

            arr = np.array(image.convert("RGB"), dtype=np.uint8)
            r = arr[:, :, 0].astype(float)
            g = arr[:, :, 1].astype(float)
            b = arr[:, :, 2].astype(float)

            mask = (r > 120) & (r > g * 1.2) & (r > b * 1.2)
            if not mask.any():
                return image

            arr[mask] = [255, 255, 255]
            return Image.fromarray(arr, mode="RGB")
        except Exception:
            return None
