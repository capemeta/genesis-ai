"""
OCR 引擎自动选择器

根据系统资源和用户配置自动选择最合适的 OCR 引擎

参考文档：doc/analysis/PDF_解析流程方案.md
"""

import psutil  # type: ignore[import-untyped]
from typing import Literal
from loguru import logger  # type: ignore[import-not-found]


OCREngine = Literal["paddleocr", "tesseract"]


class OCREngineSelector:
    """
    OCR 引擎选择器
    
    选择策略（基于 PDF 解析流程方案 v3）：
    1. 用户选择 'auto' → 检测可用内存
       - >= 4GB → PaddleOCR（高质量，95%+ 准确率）
       - < 4GB → Tesseract（轻量级，80-85% 准确率）
    2. 用户选择 'paddleocr' → 强制使用 PaddleOCR
       - 失败时自动降级到 Tesseract
    3. 用户选择 'tesseract' → 强制使用 Tesseract
    
    性能对比（单张 A4 页面）：
    - PaddleOCR (GPU): 0.1-0.3秒，准确率 95%+
    - PaddleOCR (CPU): 1-3秒，准确率 95%+
    - Tesseract (CPU): 2-5秒，准确率 80-85%
    
    资源占用：
    - PaddleOCR: 2-4GB 内存，模型 15-25MB
    - Tesseract: 1-2GB 内存，模型 10-50MB
    """
    
    # 内存阈值（字节）
    MEMORY_THRESHOLD_GB = 4
    MEMORY_THRESHOLD_BYTES = MEMORY_THRESHOLD_GB * 1024 * 1024 * 1024
    
    @classmethod
    def select_engine(
        cls,
        user_choice: str = "auto",
        allow_fallback: bool = True
    ) -> OCREngine:
        """
        选择 OCR 引擎
        
        Args:
            user_choice: 用户选择（'auto', 'paddleocr', 'tesseract'）
            allow_fallback: 是否允许降级（仅对 paddleocr 生效）
        
        Returns:
            选择的 OCR 引擎
        """
        if user_choice == "auto":
            return cls._auto_select()
        elif user_choice == "paddleocr":
            return "paddleocr"
        elif user_choice == "tesseract":
            return "tesseract"
        else:
            logger.warning(f"未知的 OCR 引擎选择: {user_choice}，使用自动选择")
            return cls._auto_select()
    
    @classmethod
    def _auto_select(cls) -> OCREngine:
        """
        自动选择 OCR 引擎（基于可用内存）
        
        策略：
        - 内存 >= 4GB → PaddleOCR（中文准确率 95%+，速度快）
        - 内存 < 4GB → Tesseract（轻量级，准确率 80-85%）
        
        Returns:
            选择的 OCR 引擎
        """
        try:
            # 获取可用内存
            memory = psutil.virtual_memory()
            available_memory = memory.available
            
            logger.info(
                f"[OCR 引擎选择] 可用内存: {available_memory / (1024**3):.2f} GB, "
                f"阈值: {cls.MEMORY_THRESHOLD_GB} GB"
            )
            
            if available_memory >= cls.MEMORY_THRESHOLD_BYTES:
                logger.info("[OCR 引擎选择] 选择 PaddleOCR（高质量模式）")
                logger.info("  - 中文准确率: 95%+")
                logger.info("  - GPU 模式: 0.1-0.3秒/图")
                logger.info("  - CPU 模式: 1-3秒/图")
                return "paddleocr"
            else:
                logger.info("[OCR 引擎选择] 选择 Tesseract（轻量级模式）")
                logger.info("  - 准确率: 80-85%")
                logger.info("  - 速度: 2-5秒/图")
                logger.info("  - 内存占用: 1-2GB")
                return "tesseract"
        
        except Exception as e:
            logger.error(f"[OCR 引擎选择] 检测内存失败: {e}，默认使用 Tesseract")
            return "tesseract"
    
    @classmethod
    def get_fallback_engine(cls, failed_engine: OCREngine) -> OCREngine:
        """
        获取降级引擎
        
        降级策略：
        - PaddleOCR 失败 → Tesseract（轻量级备选）
        - Tesseract 失败 → 无可用降级引擎
        
        Args:
            failed_engine: 失败的引擎
        
        Returns:
            降级引擎
        """
        if failed_engine == "paddleocr":
            logger.warning("[OCR 引擎降级] PaddleOCR 失败，降级到 Tesseract")
            logger.info("  - 准确率可能下降 10-15%")
            logger.info("  - 速度可能变慢 1-2 倍")
            return "tesseract"
        else:
            # Tesseract 失败无法降级
            logger.error("[OCR 引擎降级] Tesseract 失败，无可用降级引擎")
            raise RuntimeError("所有 OCR 引擎均不可用")
    
    @classmethod
    def check_engine_available(cls, engine: OCREngine) -> bool:
        """
        检查 OCR 引擎是否可用
        
        Args:
            engine: OCR 引擎
        
        Returns:
            是否可用
        """
        try:
            if engine == "paddleocr":
                # 检查 PaddleOCR 是否可用
                try:
                    from paddleocr import PaddleOCR  # type: ignore[import-not-found,import-untyped]
                    logger.info("[OCR 引擎检查] PaddleOCR 可用")
                    return True
                except ImportError:
                    logger.warning("[OCR 引擎检查] PaddleOCR 未安装")
                    logger.info("  安装命令: pip install paddleocr paddlepaddle")
                    return False
            
            elif engine == "tesseract":
                # 检查 Tesseract 是否可用
                try:
                    import pytesseract  # type: ignore[import-untyped]
                    # 尝试获取版本（验证 tesseract 可执行文件）
                    pytesseract.get_tesseract_version()
                    logger.info("[OCR 引擎检查] Tesseract 可用")
                    return True
                except Exception as e:
                    logger.warning(f"[OCR 引擎检查] Tesseract 不可用: {e}")
                    logger.info("  安装指南: https://github.com/tesseract-ocr/tesseract")
                    return False
            
            else:
                logger.error(f"[OCR 引擎检查] 未知引擎: {engine}")
                return False
        
        except Exception as e:
            logger.error(f"[OCR 引擎检查] 检查失败: {e}")
            return False
    
    @classmethod
    def select_with_validation(
        cls,
        user_choice: str = "auto",
        allow_fallback: bool = True
    ) -> OCREngine:
        """
        选择并验证 OCR 引擎
        
        Args:
            user_choice: 用户选择
            allow_fallback: 是否允许降级
        
        Returns:
            可用的 OCR 引擎
        
        Raises:
            RuntimeError: 所有引擎均不可用
        """
        # 1. 选择引擎
        engine = cls.select_engine(user_choice, allow_fallback)
        
        # 2. 验证可用性
        if cls.check_engine_available(engine):
            return engine
        
        # 3. 尝试降级
        if allow_fallback and engine == "paddleocr":
            fallback_engine = cls.get_fallback_engine(engine)
            if cls.check_engine_available(fallback_engine):
                return fallback_engine
        
        # 4. 所有引擎均不可用
        raise RuntimeError(
            f"OCR 引擎 {engine} 不可用，且无可用降级引擎。\n"
            "请安装 PaddleOCR 或 Tesseract：\n"
            "  - PaddleOCR: pip install paddleocr paddlepaddle\n"
            "  - Tesseract: https://github.com/tesseract-ocr/tesseract"
        )
    
    @classmethod
    def get_engine_info(cls, engine: OCREngine) -> dict:
        """
        获取引擎详细信息
        
        Args:
            engine: OCR 引擎
        
        Returns:
            引擎信息字典
        """
        if engine == "paddleocr":
            return {
                "name": "PaddleOCR",
                "accuracy": "95%+",
                "speed_gpu": "0.1-0.3秒/图",
                "speed_cpu": "1-3秒/图",
                "memory": "2-4GB",
                "model_size": "15-25MB",
                "languages": "80+ 语言",
                "chinese_support": "优秀",
                "recommended_for": "中文文档、生产环境、高质量要求"
            }
        elif engine == "tesseract":
            return {
                "name": "Tesseract",
                "accuracy": "80-85%",
                "speed_cpu": "2-5秒/图",
                "memory": "1-2GB",
                "model_size": "10-50MB",
                "languages": "100+ 语言",
                "chinese_support": "一般",
                "recommended_for": "资源受限、英文文档、快速原型"
            }
        else:
            return {}


# 便捷函数
def select_ocr_engine(user_choice: str = "auto") -> OCREngine:
    """
    选择 OCR 引擎（便捷函数）
    
    Args:
        user_choice: 用户选择（'auto', 'paddleocr', 'tesseract'）
    
    Returns:
        选择的 OCR 引擎
    
    Examples:
        >>> # 自动选择（推荐）
        >>> engine = select_ocr_engine("auto")
        >>> 
        >>> # 强制使用 PaddleOCR（失败时降级）
        >>> engine = select_ocr_engine("paddleocr")
        >>> 
        >>> # 强制使用 Tesseract
        >>> engine = select_ocr_engine("tesseract")
    """
    return OCREngineSelector.select_with_validation(user_choice, allow_fallback=True)
