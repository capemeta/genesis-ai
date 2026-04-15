"""
统一增强器测试。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@127.0.0.1:5432/genesis_ai_test")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENHANCER_DIR = PROJECT_ROOT / "rag" / "ingestion" / "enhancers"


def _load_combined_enhancer_class():
    """按文件路径加载被测模块，避免测试期触发整套应用初始化。"""
    sys.modules.setdefault("rag", types.ModuleType("rag"))
    sys.modules.setdefault("rag.ingestion", types.ModuleType("rag.ingestion"))
    sys.modules.setdefault("rag.ingestion.enhancers", types.ModuleType("rag.ingestion.enhancers"))

    rag_llm_module = types.ModuleType("rag.llm")

    class _DummyLLMExecutor:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

    class _DummyLLMRequest:
        def __init__(self, **kwargs):
            self.messages = kwargs.get("messages", [])
            self.temperature = kwargs.get("temperature")
            self.max_tokens = kwargs.get("max_tokens")
            self.request_source = kwargs.get("request_source")
            self.workload_type = kwargs.get("workload_type")
            self.tenant_id = kwargs.get("tenant_id")
            self.kb_id = kwargs.get("kb_id")
            self.kb_doc_id = kwargs.get("kb_doc_id")

    rag_llm_module.LLMExecutor = _DummyLLMExecutor
    rag_llm_module.LLMRequest = _DummyLLMRequest
    sys.modules["rag.llm"] = rag_llm_module

    base_spec = importlib.util.spec_from_file_location(
        "rag.ingestion.enhancers.base",
        ENHANCER_DIR / "base.py",
    )
    assert base_spec is not None and base_spec.loader is not None
    base_module = importlib.util.module_from_spec(base_spec)
    sys.modules["rag.ingestion.enhancers.base"] = base_module
    base_spec.loader.exec_module(base_module)

    quality_spec = importlib.util.spec_from_file_location(
        "rag.ingestion.enhancers.quality_utils",
        ENHANCER_DIR / "quality_utils.py",
    )
    assert quality_spec is not None and quality_spec.loader is not None
    quality_module = importlib.util.module_from_spec(quality_spec)
    sys.modules["rag.ingestion.enhancers.quality_utils"] = quality_module
    quality_spec.loader.exec_module(quality_module)

    combined_spec = importlib.util.spec_from_file_location(
        "rag.ingestion.enhancers.combined_enhancer",
        ENHANCER_DIR / "combined_enhancer.py",
    )
    assert combined_spec is not None and combined_spec.loader is not None
    combined_module = importlib.util.module_from_spec(combined_spec)
    sys.modules["rag.ingestion.enhancers.combined_enhancer"] = combined_module
    combined_spec.loader.exec_module(combined_module)
    return combined_module.CombinedEnhancer


CombinedEnhancer = _load_combined_enhancer_class()


class _FakeResponse:
    """模拟 LLM 响应对象。"""

    def __init__(self, content: str):
        self.content = content


class _FakeExecutor:
    """模拟 LLM 执行器，便于稳定测试 prompt 与输出清洗。"""

    def __init__(self, content: str):
        self.content = content
        self.last_request = None

    async def chat(self, request):
        self.last_request = request
        return _FakeResponse(self.content)


@pytest.mark.asyncio
async def test_combined_enhancer_builds_strict_prompt_and_writes_result() -> None:
    """应生成带严格约束的 prompt，并把增强结果写回统一字段。"""
    enhancer = CombinedEnhancer(
        enable_summary=True,
        enable_keywords=True,
        enable_questions=True,
        summary_max_length=60,
        keyword_topn=3,
        question_topn=2,
    )
    executor = _FakeExecutor(
        json.dumps(
            {
                "summary": "这是一个关于权限控制与接口鉴权流程的摘要。",
                "keywords": ["权限控制", "接口鉴权", "令牌校验"],
                "questions": ["接口鉴权流程是什么？", "令牌如何校验？"],
            },
            ensure_ascii=False,
        )
    )
    enhancer.executor = executor

    chunk = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "kb_id": "22222222-2222-2222-2222-222222222222",
        "kb_doc_id": "33333333-3333-3333-3333-333333333333",
        "text": "系统通过权限控制、接口鉴权和令牌校验保障接口安全。",
        "metadata": {},
    }

    result = await enhancer.enhance(chunk)

    assert result["summary"] == "这是一个关于权限控制与接口鉴权流程的摘要。"
    assert result["metadata"]["enhancement"]["keywords"] == ["权限控制", "接口鉴权", "令牌校验"]
    assert result["metadata"]["enhancement"]["questions"] == ["接口鉴权流程是什么？", "令牌如何校验？"]

    assert executor.last_request is not None
    system_prompt = executor.last_request.messages[0]["content"]
    user_prompt = executor.last_request.messages[1]["content"]
    assert "必须严格遵循原文证据" in system_prompt
    assert "输出语言必须与原文主语言保持一致" in user_prompt
    assert "宁缺毋滥规则" in user_prompt
    assert "<<<CHUNK>>>" in user_prompt
    assert "字段细则" in user_prompt


@pytest.mark.asyncio
async def test_combined_enhancer_normalizes_keywords_and_questions() -> None:
    """应过滤低价值关键词、重复项与低质量问题，并自动补问号。"""
    enhancer = CombinedEnhancer(
        enable_summary=True,
        enable_keywords=True,
        enable_questions=True,
        summary_max_length=12,
        keyword_topn=3,
        question_topn=2,
    )
    enhancer.executor = _FakeExecutor(
        """```json
        {
          "summary": "这是一个很长的摘要，用于验证摘要会被截断到指定长度。",
          "keywords": ["介绍", "权限控制", "a", "接口鉴权", "接口鉴权", "这是一个完整句子。"],
          "questions": ["它是什么", "接口鉴权流程是什么", "接口鉴权流程是什么", "令牌如何校验"]
        }
        ```"""
    )

    result = await enhancer.enhance(
        {
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "kb_id": "22222222-2222-2222-2222-222222222222",
            "kb_doc_id": "33333333-3333-3333-3333-333333333333",
            "text": "系统通过权限控制、接口鉴权和令牌校验保障接口安全。",
            "metadata": {},
        }
    )

    assert result["summary"] == "这是一个很长的摘要，用于验证摘要会被截断"
    assert result["metadata"]["enhancement"]["keywords"] == ["权限控制", "a", "接口鉴权"]
    assert result["metadata"]["enhancement"]["questions"] == ["接口鉴权流程是什么？", "令牌如何校验？"]


@pytest.mark.asyncio
async def test_combined_enhancer_returns_original_chunk_when_text_is_empty() -> None:
    """空文本时应直接跳过，不触发模型调用。"""
    enhancer = CombinedEnhancer(enable_summary=True)
    executor = _FakeExecutor('{"summary":"不会被使用"}')
    enhancer.executor = executor

    chunk = {"tenant_id": "11111111-1111-1111-1111-111111111111", "text": "   ", "metadata": {}}
    result = await enhancer.enhance(chunk)

    assert result is chunk
    assert executor.last_request is None


@pytest.mark.asyncio
async def test_combined_enhancer_clears_stale_values_when_no_high_value_result() -> None:
    """低价值结果应被视为正常空结果，并清理旧增强字段而不是报错。"""
    enhancer = CombinedEnhancer(
        enable_summary=True,
        enable_keywords=True,
        enable_questions=True,
        summary_max_length=30,
        keyword_topn=3,
        question_topn=2,
    )
    enhancer.executor = _FakeExecutor(
        json.dumps(
            {
                "summary": "本文介绍了系统。",
                "keywords": ["介绍", "内容", "摘要"],
                "questions": ["它是什么", "这是什么"],
            },
            ensure_ascii=False,
        )
    )

    chunk = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "kb_id": "22222222-2222-2222-2222-222222222222",
        "kb_doc_id": "33333333-3333-3333-3333-333333333333",
        "text": "系统说明",
        "summary": "旧摘要",
        "metadata": {
            "enhancement": {
                "summary": "旧摘要",
                "keywords": ["旧关键词"],
                "questions": ["旧问题？"],
            }
        },
    }

    result = await enhancer.enhance(chunk)

    assert "summary" not in result
    assert result["metadata"]["enhancement"] == {}
