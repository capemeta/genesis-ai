from typing import Any, Dict, List, Tuple

from .base import OCREngine


class PaddleOCREngine(OCREngine):
    def __init__(self):
        self._client = None

    def is_available(self) -> bool:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-not-found,import-untyped]  # noqa: F401
            return True
        except Exception:
            return False

    def _get_client(self):
        if self._client is not None:
            return self._client
        from paddleocr import PaddleOCR  # type: ignore[import-not-found,import-untyped]

        self._client = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        return self._client

    def recognize(
        self,
        image: Any,
        languages: List[str],
        legacy_mode: bool,
        enhancer: Any,
        psm_list: List[int],
        min_confidence: float,
        enable_parallel: bool = False,
        parallel_executor: Any = None,
    ) -> List[Dict[str, Any]]:
        import numpy as np

        client = self._get_client()
        if legacy_mode:
            result = client.ocr(np.array(image), cls=True)
            return self._extract_paddle_lines(result, enhancer=None, min_confidence=min_confidence)

        # 生成变体
        variants = enhancer.build_variants(image, strategy="minimal")
        
        # 🔧 并行处理：如果启用并行且有多个变体
        if enable_parallel and parallel_executor and len(variants) > 1:
            return self._recognize_parallel(variants, enhancer, min_confidence, parallel_executor)
        
        # 串行处理（默认）
        all_lines: List[Dict[str, Any]] = []
        for variant_name, variant_image in variants:
            result = client.ocr(np.array(variant_image), cls=True)
            lines = self._extract_paddle_lines(result, enhancer=enhancer, min_confidence=min_confidence)
            for line in lines:
                line["variant"] = variant_name
                all_lines.append(line)
        return all_lines
    
    def _recognize_parallel(
        self,
        variants: List[Tuple[str, Any]],
        enhancer: Any,
        min_confidence: float,
        parallel_executor: Any,
    ) -> List[Dict[str, Any]]:
        """并行识别多个变体"""
        import numpy as np
        
        client = self._get_client()
        
        def recognize_single(variant_image, variant_name):
            """单个识别任务"""
            result = client.ocr(np.array(variant_image), cls=True)
            lines = self._extract_paddle_lines(result, enhancer=enhancer, min_confidence=min_confidence)
            for line in lines:
                line["variant"] = variant_name
            return lines
        
        # 构建任务列表
        tasks: List[Tuple[str, Any, Tuple[Any, str], Dict[str, Any]]] = []
        for variant_name, variant_image in variants:
            task_id = f"variant_{variant_name}"
            tasks.append((
                task_id,
                recognize_single,
                (variant_image, variant_name),
                {}
            ))
        
        # 并行执行
        results = parallel_executor.execute_parallel(tasks)
        
        # 合并结果
        all_lines: List[Dict[str, Any]] = []
        for task_id, result, error in results:
            if error is None and result:
                all_lines.extend(result)
        
        return all_lines

    def _extract_paddle_lines(self, result: Any, enhancer: Any, min_confidence: float) -> List[Dict[str, Any]]:
        if not result:
            return []
        out: List[Dict[str, Any]] = []
        for entry in (result[0] if isinstance(result, list) and result else []):
            if not entry or len(entry) < 2:
                continue
            points = entry[0] or []
            rec = entry[1] or ("", 0.0)
            text = str(rec[0] or "").strip()
            if enhancer is not None:
                text = enhancer.post_correct_text(text)
            confidence = float(rec[1] or 0.0)
            if not text or not points or confidence < float(min_confidence):
                continue
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            out.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "bbox": [min(xs), min(ys), max(xs), max(ys)],
                }
            )
        out.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
        return out
