import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .base import OCREngine

TESSERACT_SETUP_HINT = (
    "Tesseract is not configured. Please set env var TESSERACT_HOME "
    "(e.g. D:\\Software\\Tesseract-OCR)."
)


def get_tesseract_exe_path() -> Optional[str]:
    home = (os.environ.get("TESSERACT_HOME") or "").strip()
    if not home:
        return None
    exe = os.path.join(home, "tesseract.exe")
    if os.path.isfile(exe):
        return exe
    return None


def ensure_tesseract_cmd(pytesseract: Any) -> None:
    exe = get_tesseract_exe_path()
    if exe:
        pytesseract.pytesseract.tesseract_cmd = exe


class TesseractOCREngine(OCREngine):
    def is_available(self) -> bool:
        try:
            import pytesseract  # type: ignore[import-untyped]  # noqa: F401
            return True
        except Exception:
            return False

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
        import pytesseract  # type: ignore[import-untyped]
        from pytesseract import Output

        ensure_tesseract_cmd(pytesseract)
        tesseract_lang = self._build_tesseract_lang(languages)

        if legacy_mode:
            data = pytesseract.image_to_data(
                image,
                lang=tesseract_lang,
                output_type=Output.DICT,
                config="--oem 1 --psm 6",
            )
            return self._extract_lines_legacy(data, min_confidence=min_confidence)

        # 生成变体
        variants = enhancer.build_variants(image, strategy="minimal")
        
        # 🔧 并行处理：如果启用并行且有多个变体或多个 PSM
        if enable_parallel and parallel_executor and (len(variants) > 1 or len(psm_list) > 1):
            return self._recognize_parallel(
                variants, psm_list, tesseract_lang, enhancer, min_confidence, parallel_executor
            )
        
        # 串行处理（默认）
        all_lines: List[Dict[str, Any]] = []
        for variant_name, variant_image in variants:
            for psm in psm_list:
                data = pytesseract.image_to_data(
                    variant_image,
                    lang=tesseract_lang,
                    output_type=Output.DICT,
                    config=f"--oem 1 --psm {psm}",
                )
                all_lines.extend(
                    self._extract_lines(
                        data,
                        variant_name,
                        psm,
                        enhancer,
                        min_confidence=min_confidence,
                    )
                )
        return all_lines
    
    def _recognize_parallel(
        self,
        variants: List[Tuple[str, Any]],
        psm_list: List[int],
        tesseract_lang: str,
        enhancer: Any,
        min_confidence: float,
        parallel_executor: Any,
    ) -> List[Dict[str, Any]]:
        """并行识别多个变体和 PSM"""
        import pytesseract  # type: ignore[import-untyped]
        from pytesseract import Output
        
        def recognize_single(variant_image, variant_name, psm):
            """单个识别任务"""
            data = pytesseract.image_to_data(
                variant_image,
                lang=tesseract_lang,
                output_type=Output.DICT,
                config=f"--oem 1 --psm {psm}",
            )
            return self._extract_lines(data, variant_name, psm, enhancer, min_confidence)
        
        # 构建任务列表
        tasks: List[Tuple[str, Any, Tuple[Any, str, int], Dict[str, Any]]] = []
        for variant_name, variant_image in variants:
            for psm in psm_list:
                task_id = f"variant_{variant_name}_psm_{psm}"
                tasks.append((
                    task_id,
                    recognize_single,
                    (variant_image, variant_name, psm),
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

    def _extract_lines(
        self,
        data: Dict[str, Any],
        variant_name: str,
        psm: int,
        enhancer: Any,
        min_confidence: float,
    ) -> List[Dict[str, Any]]:
        lines_map: Dict[Tuple[int, int, int], Dict[str, Any]] = {}
        n = len(data.get("text", []))
        for i in range(n):
            raw_text = enhancer.post_correct_text(str(data["text"][i] or "").strip())
            if not raw_text:
                continue
            try:
                conf = float(data["conf"][i])
            except Exception:
                conf = -1.0
            if conf < float(min_confidence):
                continue
            if self._is_gibberish(raw_text):
                continue
            key = (
                int(data.get("block_num", [0] * n)[i]),
                int(data.get("par_num", [0] * n)[i]),
                int(data.get("line_num", [0] * n)[i]),
            )
            left = float(data["left"][i])
            top = float(data["top"][i])
            width = float(data["width"][i])
            height = float(data["height"][i])
            x0, y0, x1, y1 = left, top, left + width, top + height
            if key not in lines_map:
                lines_map[key] = {
                    "text_parts": [raw_text],
                    "conf_sum": conf,
                    "conf_cnt": 1,
                    "bbox": [x0, y0, x1, y1],
                    "variant": variant_name,
                    "psm": psm,
                }
            else:
                line = lines_map[key]
                line["text_parts"].append(raw_text)
                line["conf_sum"] += conf
                line["conf_cnt"] += 1
                line_bbox = line["bbox"]
                line_bbox[0] = min(line_bbox[0], x0)
                line_bbox[1] = min(line_bbox[1], y0)
                line_bbox[2] = max(line_bbox[2], x1)
                line_bbox[3] = max(line_bbox[3], y1)

        out: List[Dict[str, Any]] = []
        for _, line in lines_map.items():
            conf_cnt = max(int(line["conf_cnt"]), 1)
            out.append(
                {
                    "text": enhancer.post_correct_text(" ".join(line["text_parts"]).strip()),
                    "confidence": float(line["conf_sum"]) / conf_cnt,
                    "bbox": line["bbox"],
                    "variant": line["variant"],
                    "psm": line["psm"],
                }
            )
        return out

    def _extract_lines_legacy(self, data: Dict[str, Any], min_confidence: float) -> List[Dict[str, Any]]:
        lines_map: Dict[Tuple[int, int, int], Dict[str, Any]] = {}
        n = len(data.get("text", []))
        for i in range(n):
            raw_text = str(data["text"][i] or "").strip()
            if not raw_text:
                continue
            try:
                conf = float(data["conf"][i])
            except Exception:
                conf = -1.0
            if conf < float(min_confidence):
                continue
            if self._is_gibberish(raw_text):
                continue
            key = (
                int(data.get("block_num", [0] * n)[i]),
                int(data.get("par_num", [0] * n)[i]),
                int(data.get("line_num", [0] * n)[i]),
            )
            left = float(data["left"][i])
            top = float(data["top"][i])
            width = float(data["width"][i])
            height = float(data["height"][i])
            x0, y0, x1, y1 = left, top, left + width, top + height
            if key not in lines_map:
                lines_map[key] = {
                    "text_parts": [raw_text],
                    "conf_sum": conf,
                    "conf_cnt": 1,
                    "bbox": [x0, y0, x1, y1],
                }
            else:
                line = lines_map[key]
                line["text_parts"].append(raw_text)
                line["conf_sum"] += conf
                line["conf_cnt"] += 1
                line_bbox = line["bbox"]
                line_bbox[0] = min(line_bbox[0], x0)
                line_bbox[1] = min(line_bbox[1], y0)
                line_bbox[2] = max(line_bbox[2], x1)
                line_bbox[3] = max(line_bbox[3], y1)

        out: List[Dict[str, Any]] = []
        for _, line in lines_map.items():
            conf_cnt = max(int(line["conf_cnt"]), 1)
            out.append(
                {
                    "text": " ".join(line["text_parts"]).strip(),
                    "confidence": float(line["conf_sum"]) / conf_cnt,
                    "bbox": line["bbox"],
                }
            )
        out.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
        return out

    def _is_gibberish(self, text: str) -> bool:
        s = (text or "").strip()
        if not s:
            return True
        if len(s) <= 2:
            return False

        symbol_cnt = len(re.findall(r"[^\w\u4e00-\u9fff\s]", s))
        alpha_num_cjk_cnt = len(re.findall(r"[\w\u4e00-\u9fff]", s))
        pipe_cnt = s.count("|")

        if pipe_cnt >= max(3, len(s) // 3):
            return True
        if alpha_num_cjk_cnt == 0:
            return True
        if symbol_cnt > alpha_num_cjk_cnt:
            return True
        return False

    def _build_tesseract_lang(self, languages: List[str]) -> str:
        lang_map = {"ch": "chi_sim", "zh": "chi_sim", "en": "eng"}
        mapped = []
        for lang in languages:
            code = lang_map.get(str(lang).lower())
            if code and code not in mapped:
                mapped.append(code)
        return "+".join(mapped or ["eng"])
