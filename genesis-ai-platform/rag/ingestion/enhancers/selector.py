"""
分块增强选择器。

职责：
- 规范化 enhancement 配置
- 判断当前 chunk 是否进入增强
- 给出 summary / keywords / questions 的能力开关
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict


@dataclass(slots=True)
class EnhancementDecision:
    """单个 chunk 的增强决策结果。"""

    should_enhance: bool
    enable_summary: bool
    enable_keywords: bool
    enable_questions: bool
    reason_code: str
    reason_detail: str = ""

    def enabled_count(self) -> int:
        """返回本次启用的能力数量。"""
        return int(self.enable_summary) + int(self.enable_keywords) + int(self.enable_questions)


def normalize_enhancement_config(raw_config: Dict[str, Any] | None) -> Dict[str, Any]:
    """规范化 enhancement 配置，避免下游重复判空。"""
    config = dict(raw_config or {})
    summary_cfg = dict(config.get("summary") or {})
    keywords_cfg = dict(config.get("keywords") or {})
    questions_cfg = dict(config.get("questions") or {})

    def _to_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        return max(minimum, min(maximum, number))

    return {
        "enabled": config.get("enabled") is not False,
        "min_text_length": _to_int(config.get("min_text_length"), 40, minimum=0, maximum=10000),
        "keywords_only_min_length": _to_int(config.get("keywords_only_min_length"), 40, minimum=0, maximum=10000),
        "summary_min_length": _to_int(config.get("summary_min_length"), 80, minimum=0, maximum=10000),
        "questions_min_length": _to_int(config.get("questions_min_length"), 150, minimum=0, maximum=10000),
        "summary": {
            "enabled": summary_cfg.get("enabled") is not False,
            "max_length": _to_int(summary_cfg.get("max_length"), 100, minimum=20, maximum=500),
        },
        "keywords": {
            "enabled": keywords_cfg.get("enabled") is not False,
            "top_n": _to_int(keywords_cfg.get("top_n"), 5, minimum=1, maximum=20),
        },
        "questions": {
            "enabled": bool(questions_cfg.get("enabled", False)),
            "top_n": _to_int(questions_cfg.get("top_n"), 3, minimum=1, maximum=20),
        },
    }


def decide_chunk_enhancement(
    *,
    chunk: Dict[str, Any],
    enhancement_config: Dict[str, Any] | None,
    kb_type: str = "",
) -> EnhancementDecision:
    """根据 chunk 属性与配置，判断增强策略。"""
    config = normalize_enhancement_config(enhancement_config)
    metadata = dict(chunk.get("metadata_info") or chunk.get("metadata") or {})
    chunk_type = str(chunk.get("chunk_type") or "").strip().lower()
    source_type = str(chunk.get("source_type") or "").strip().lower()
    chunk_role = str(metadata.get("chunk_role") or "").strip().lower()
    text = str(chunk.get("content") or chunk.get("text") or "").strip()
    text_length = int(chunk.get("text_length") or len(text))
    is_leaf = bool(metadata.get("is_leaf", True))
    should_vectorize = bool(metadata.get("should_vectorize", True))
    exclude_from_retrieval = bool(metadata.get("exclude_from_retrieval", False))

    if not config["enabled"]:
        return EnhancementDecision(False, False, False, False, "enhancement_disabled", "知识库未开启增强")

    if not text:
        return EnhancementDecision(False, False, False, False, "empty_content", "分块内容为空")

    if text_length < int(config["min_text_length"]):
        return EnhancementDecision(False, False, False, False, "too_short", "文本过短，跳过增强")

    if exclude_from_retrieval:
        return EnhancementDecision(False, False, False, False, "exclude_from_retrieval", "分块不参与检索")

    if not should_vectorize:
        return EnhancementDecision(False, False, False, False, "not_vectorized", "分块不参与主检索向量化")

    if not is_leaf:
        return EnhancementDecision(False, False, False, False, "non_leaf", "父块默认不做增强")

    if chunk_type in {"code", "json", "image", "media"}:
        return EnhancementDecision(False, False, False, False, "unsupported_chunk_type", f"不支持的块类型: {chunk_type}")

    if chunk_type == "qa" or source_type == "qa" or chunk_role in {"qa_row", "qa_answer_fragment"}:
        return EnhancementDecision(False, False, False, False, "qa_skip", "QA 检索已有独立问题投影，默认跳过增强")

    if chunk_role.endswith("_fragment") or chunk_role in {"excel_row_fragment", "web_table_fragment"}:
        return EnhancementDecision(False, False, False, False, "fragment_skip", "碎片块语义不稳定，默认跳过增强")

    if chunk_role.endswith("_root") or chunk_role.endswith("_parent"):
        return EnhancementDecision(False, False, False, False, "parent_role_skip", "父级结构块默认跳过增强")

    enable_keywords = config["keywords"]["enabled"] and text_length >= int(config["keywords_only_min_length"])
    enable_summary = config["summary"]["enabled"] and text_length >= int(config["summary_min_length"])
    enable_questions = config["questions"]["enabled"] and text_length >= int(config["questions_min_length"])

    if kb_type == "table" or source_type == "table" or chunk_type == "table" or chunk_role.startswith("excel_"):
        numeric_density = _estimate_numeric_density(text)
        if numeric_density >= 0.35:
            enable_summary = False
            enable_questions = False
        else:
            enable_questions = False

    if kb_type == "web" and chunk_role in {"web_table_leaf"}:
        enable_questions = False

    if not any([enable_summary, enable_keywords, enable_questions]):
        return EnhancementDecision(False, False, False, False, "capability_not_enabled", "当前分块未命中任何增强能力")

    return EnhancementDecision(
        True,
        enable_summary,
        enable_keywords,
        enable_questions,
        "selected",
        "命中增强选择条件",
    )


def build_enhancer_runtime_config(
    *,
    enhancement_config: Dict[str, Any] | None,
    decision: EnhancementDecision,
) -> Dict[str, Dict[str, Any]]:
    """将标准 enhancement 配置投影为 enhancer 工厂可消费的运行配置。"""
    config = normalize_enhancement_config(enhancement_config)
    runtime_config: Dict[str, Dict[str, Any]] = {}
    if decision.enable_summary:
        runtime_config["summary"] = {
            "max_length": int(config["summary"]["max_length"]),
        }
    if decision.enable_keywords:
        runtime_config["keyword"] = {
            "topn": int(config["keywords"]["top_n"]),
        }
    if decision.enable_questions:
        runtime_config["question"] = {
            "topn": int(config["questions"]["top_n"]),
        }
    return runtime_config


def _estimate_numeric_density(text: str) -> float:
    """估算文本中的数字密度，用于表格型分块的保守策略。"""
    normalized = re.sub(r"\s+", "", text or "")
    if not normalized:
        return 0.0
    numeric_chars = sum(1 for ch in normalized if ch.isdigit())
    return numeric_chars / max(1, len(normalized))
