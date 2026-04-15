import re
from typing import List, Dict, Any, Optional
from ..base_pdf_parser import ParserElement


class ReflowEngine:
    """Paragraph reflow engine for parsed PDF elements."""

    PARA_END_PUNC = re.compile(r"[。！？?!]$")
    LIST_OR_CODE_START = re.compile(r"^([#{}\[\]\"'\-]|\d+\.|\w+\s*[:=])")

    def reflow(
        self,
        elements: List[ParserElement],
        ocr_reflow_enabled: bool = False,
        ocr_merge_profile: str = "balanced",
        ocr_merge_min_score: Optional[float] = None,
    ) -> List[ParserElement]:
        if not elements:
            return []

        result: List[ParserElement] = []
        current_el: Optional[ParserElement] = None

        for el in elements:
            if el["type"] != "text":
                if current_el:
                    result.append(current_el)
                    current_el = None
                result.append(el)
                continue

            if current_el is None:
                current_el = el
                continue

            if (
                ocr_reflow_enabled
                and self._is_ocr_text(current_el)
                and self._is_ocr_text(el)
            ):
                should_merge = self._should_merge_ocr(
                    current_el,
                    el,
                    profile=ocr_merge_profile,
                    min_score=ocr_merge_min_score,
                )
            else:
                should_merge = self._should_merge(current_el, el)

            if should_merge:
                current_el = self._merge_two_elements(current_el, el)
            else:
                result.append(current_el)
                current_el = el

        if current_el:
            result.append(current_el)

        return result

    def _should_merge(self, prev: ParserElement, curr: ParserElement) -> bool:
        """Legacy merge logic kept for non-OCR text."""
        prev_text = prev["content"].strip()
        curr_text = curr["content"].strip()

        if self.LIST_OR_CODE_START.match(curr_text):
            return False

        if self.PARA_END_PUNC.search(prev_text):
            return False

        gap = curr["bbox"][1] - prev["bbox"][3]
        if gap > 4:
            return False

        prev_size = prev["metadata"].get("size", 0)
        curr_size = curr["metadata"].get("size", 0)
        if abs(prev_size - curr_size) > 0.3:
            return False

        if abs(curr["bbox"][0] - prev["bbox"][0]) > 2:
            return False

        return True

    def _should_merge_ocr(
        self,
        prev: ParserElement,
        curr: ParserElement,
        profile: str = "balanced",
        min_score: Optional[float] = None,
    ) -> bool:
        conf = self._resolve_ocr_profile(profile)
        score = 0.0

        prev_text = (prev.get("content") or "").strip()
        curr_text = (curr.get("content") or "").strip()
        if not prev_text or not curr_text:
            return False

        if self.PARA_END_PUNC.search(prev_text):
            return False
        if self.LIST_OR_CODE_START.match(curr_text):
            return False

        prev_bbox = prev.get("bbox") or [0.0, 0.0, 0.0, 0.0]
        curr_bbox = curr.get("bbox") or [0.0, 0.0, 0.0, 0.0]

        line_height = max(float(prev_bbox[3]) - float(prev_bbox[1]), 1.0)
        gap = float(curr_bbox[1]) - float(prev_bbox[3])
        if gap > conf["max_gap"]:
            return False
        if gap <= line_height * 0.6:
            score += 1.0

        indent_delta = abs(float(curr_bbox[0]) - float(prev_bbox[0]))
        if indent_delta <= conf["max_indent_delta"]:
            score += 1.0
        else:
            score -= 1.0

        prev_w = max(float(prev_bbox[2]) - float(prev_bbox[0]), 0.0)
        curr_w = max(float(curr_bbox[2]) - float(curr_bbox[0]), 0.0)
        if prev_w > 0 and curr_w > 0:
            width_ratio = curr_w / prev_w
            if conf["min_width_ratio"] <= width_ratio <= conf["max_width_ratio"]:
                score += 1.0

        if self._is_probable_sentence_continue(curr_text):
            score += 1.0

        threshold = float(min_score) if min_score is not None else conf["min_score"]
        return score >= threshold

    def _resolve_ocr_profile(self, profile: str) -> Dict[str, float]:
        p = (profile or "balanced").lower()
        conf_map = {
            "conservative": {
                "max_gap": 2.5,
                "max_indent_delta": 1.5,
                "min_width_ratio": 0.55,
                "max_width_ratio": 1.60,
                "min_score": 3.0,
            },
            "balanced": {
                "max_gap": 4.0,
                "max_indent_delta": 2.5,
                "min_width_ratio": 0.45,
                "max_width_ratio": 1.90,
                "min_score": 2.0,
            },
            "aggressive": {
                "max_gap": 6.0,
                "max_indent_delta": 4.0,
                "min_width_ratio": 0.35,
                "max_width_ratio": 2.30,
                "min_score": 1.0,
            },
        }
        return conf_map.get(p, conf_map["balanced"])

    def _is_probable_sentence_continue(self, text: str) -> bool:
        if not text:
            return False
        if text[0] in "，,、。；;：:)]}）】》\"'":
            return True
        if re.match(r"^[a-z0-9]", text):
            return True
        return False

    def _is_ocr_text(self, element: ParserElement) -> bool:
        meta = element.get("metadata") or {}
        return str(meta.get("source") or "").lower() == "ocr"

    def _merge_two_elements(self, prev: ParserElement, curr: ParserElement) -> ParserElement:
        p_text = prev["content"].strip()
        c_text = curr["content"].strip()

        if p_text.endswith('-'):
            new_content = p_text[:-1] + c_text
        else:
            if not p_text or not c_text:
                new_content = p_text + c_text
            else:
                last_char = p_text[-1]
                first_char = c_text[0]
                if self._is_chinese(last_char) or self._is_chinese(first_char):
                    new_content = p_text + c_text
                else:
                    new_content = p_text + " " + c_text

        new_bbox = [
            min(prev["bbox"][0], curr["bbox"][0]),
            min(prev["bbox"][1], curr["bbox"][1]),
            max(prev["bbox"][2], curr["bbox"][2]),
            max(prev["bbox"][3], curr["bbox"][3]),
        ]

        prev["content"] = new_content
        prev["bbox"] = new_bbox
        return prev

    @staticmethod
    def _is_chinese(char: str) -> bool:
        return "\u4e00" <= char <= "\u9fff"
