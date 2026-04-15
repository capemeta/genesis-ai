"""
增强质量工具测试。
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENHANCER_DIR = PROJECT_ROOT / "rag" / "ingestion" / "enhancers"


def _load_quality_utils_module():
    """按文件路径加载质量工具模块，避免测试期触发整套应用初始化。"""
    sys.modules.setdefault("rag", types.ModuleType("rag"))
    sys.modules.setdefault("rag.ingestion", types.ModuleType("rag.ingestion"))
    sys.modules.setdefault("rag.ingestion.enhancers", types.ModuleType("rag.ingestion.enhancers"))

    spec = importlib.util.spec_from_file_location(
        "rag.ingestion.enhancers.quality_utils",
        ENHANCER_DIR / "quality_utils.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rag.ingestion.enhancers.quality_utils"] = module
    spec.loader.exec_module(module)
    return module


quality_utils = _load_quality_utils_module()


def test_strip_json_fence_handles_plain_and_fenced_json() -> None:
    """应兼容裸 JSON 和带 json 代码块的结果。"""
    assert quality_utils.strip_json_fence('{"summary":"ok"}') == '{"summary":"ok"}'
    assert quality_utils.strip_json_fence("```json\n{\"summary\":\"ok\"}\n```") == '{"summary":"ok"}'
    assert quality_utils.strip_json_fence("```JSON\n{\"summary\":\"ok\"}\n```") == '{"summary":"ok"}'


def test_is_low_value_summary_recognizes_short_or_template_summary() -> None:
    """应识别空洞摘要。"""
    assert quality_utils.is_low_value_summary("")
    assert quality_utils.is_low_value_summary("无")
    assert quality_utils.is_low_value_summary("本文介绍了系统。")
    assert not quality_utils.is_low_value_summary("系统说明了权限控制、鉴权流程和令牌校验关系。")


def test_normalize_keywords_filters_generic_and_sentence_like_values() -> None:
    """应过滤泛词、重复项和整句。"""
    result = quality_utils.normalize_keywords(
        ["介绍", "权限控制", "接口鉴权", "接口鉴权", "这是一个完整句子。", " 模块设计 "],
        limit=3,
    )
    assert result == ["权限控制", "接口鉴权", "模块设计"]


def test_normalize_questions_filters_weak_questions_and_appends_question_mark() -> None:
    """应过滤弱问题并自动补问号。"""
    result = quality_utils.normalize_questions(
        ["它是什么", "接口鉴权流程是什么", "接口鉴权流程是什么？", "令牌如何校验"],
        limit=3,
    )
    assert result == ["接口鉴权流程是什么？", "令牌如何校验？"]
