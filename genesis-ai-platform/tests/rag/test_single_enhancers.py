"""
单能力增强器测试。
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


def _load_enhancer_module(module_name: str):
    """按文件路径加载增强器模块，避免测试期触发整套应用初始化。"""
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

    spec = importlib.util.spec_from_file_location(
        f"rag.ingestion.enhancers.{module_name}",
        ENHANCER_DIR / f"{module_name}.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"rag.ingestion.enhancers.{module_name}"] = module
    spec.loader.exec_module(module)
    return module


SummaryEnhancer = _load_enhancer_module("summary_enhancer").SummaryEnhancer
KeywordEnhancer = _load_enhancer_module("keyword_enhancer").KeywordEnhancer
QuestionEnhancer = _load_enhancer_module("question_enhancer").QuestionEnhancer


class _FakeResponse:
    """模拟 LLM 响应对象。"""

    def __init__(self, content: str):
        self.content = content


class _FakeExecutor:
    """模拟 LLM 执行器，便于稳定测试 prompt 与结果清洗。"""

    def __init__(self, content: str):
        self.content = content
        self.last_request = None

    async def chat(self, request):
        self.last_request = request
        return _FakeResponse(self.content)


@pytest.mark.asyncio
async def test_summary_enhancer_keeps_high_value_summary() -> None:
    """高质量摘要应写回顶层与 enhancement 命名空间。"""
    enhancer = SummaryEnhancer(max_length=30)
    executor = _FakeExecutor(json.dumps({"summary": "系统描述了权限控制和鉴权校验流程。"}, ensure_ascii=False))
    enhancer.executor = executor

    chunk = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "kb_id": "22222222-2222-2222-2222-222222222222",
        "kb_doc_id": "33333333-3333-3333-3333-333333333333",
        "text": "系统描述了权限控制和鉴权校验流程。",
        "metadata": {},
    }

    result = await enhancer.enhance(chunk)

    assert result["summary"] == "系统描述了权限控制和鉴权校验流程。"
    assert result["metadata"]["enhancement"]["summary"] == "系统描述了权限控制和鉴权校验流程。"
    assert "返回空字符串" in executor.last_request.messages[1]["content"]


@pytest.mark.asyncio
async def test_summary_enhancer_clears_stale_summary_when_result_is_low_value() -> None:
    """低价值摘要应被视为空结果并清理旧值。"""
    enhancer = SummaryEnhancer(max_length=30)
    enhancer.executor = _FakeExecutor(json.dumps({"summary": "本文介绍了系统。"}, ensure_ascii=False))

    chunk = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "kb_id": "22222222-2222-2222-2222-222222222222",
        "kb_doc_id": "33333333-3333-3333-3333-333333333333",
        "text": "系统说明",
        "summary": "旧摘要",
        "metadata": {"enhancement": {"summary": "旧摘要"}},
    }

    result = await enhancer.enhance(chunk)

    assert "summary" not in result
    assert result["metadata"]["enhancement"] == {}


@pytest.mark.asyncio
async def test_keyword_enhancer_filters_low_value_keywords() -> None:
    """关键词增强器应保留高价值项并过滤泛词噪声。"""
    enhancer = KeywordEnhancer(topn=3)
    executor = _FakeExecutor(
        """```json
        {"keywords": ["介绍", "权限控制", "接口鉴权", "接口鉴权", "这是一个完整句子。"]}
        ```"""
    )
    enhancer.executor = executor

    chunk = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "kb_id": "22222222-2222-2222-2222-222222222222",
        "kb_doc_id": "33333333-3333-3333-3333-333333333333",
        "text": "系统通过权限控制和接口鉴权保障安全。",
        "metadata": {},
    }

    result = await enhancer.enhance(chunk)

    assert result["metadata"]["enhancement"]["keywords"] == ["权限控制", "接口鉴权"]
    assert "返回空数组" in executor.last_request.messages[1]["content"]


@pytest.mark.asyncio
async def test_keyword_enhancer_clears_stale_keywords_when_result_is_empty() -> None:
    """低价值关键词应被视为空结果并清理旧值。"""
    enhancer = KeywordEnhancer(topn=3)
    enhancer.executor = _FakeExecutor(json.dumps({"keywords": ["介绍", "内容", "摘要"]}, ensure_ascii=False))

    chunk = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "kb_id": "22222222-2222-2222-2222-222222222222",
        "kb_doc_id": "33333333-3333-3333-3333-333333333333",
        "text": "系统说明",
        "metadata": {"enhancement": {"keywords": ["旧关键词"]}},
    }

    result = await enhancer.enhance(chunk)

    assert result["metadata"]["enhancement"] == {}


@pytest.mark.asyncio
async def test_question_enhancer_filters_low_value_questions() -> None:
    """问题增强器应保留有效问句并自动补齐问号。"""
    enhancer = QuestionEnhancer(topn=2)
    executor = _FakeExecutor(
        """```json
        {"questions": ["它是什么", "接口鉴权流程是什么", "令牌如何校验"]}
        ```"""
    )
    enhancer.executor = executor

    chunk = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "kb_id": "22222222-2222-2222-2222-222222222222",
        "kb_doc_id": "33333333-3333-3333-3333-333333333333",
        "text": "系统通过接口鉴权流程和令牌校验保障安全。",
        "metadata": {},
    }

    result = await enhancer.enhance(chunk)

    assert result["metadata"]["enhancement"]["questions"] == ["接口鉴权流程是什么？", "令牌如何校验？"]
    assert "返回空数组" in executor.last_request.messages[1]["content"]


@pytest.mark.asyncio
async def test_question_enhancer_clears_stale_questions_when_result_is_empty() -> None:
    """低价值问题应被视为空结果并清理旧值。"""
    enhancer = QuestionEnhancer(topn=2)
    enhancer.executor = _FakeExecutor(json.dumps({"questions": ["它是什么", "这是什么"]}, ensure_ascii=False))

    chunk = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "kb_id": "22222222-2222-2222-2222-222222222222",
        "kb_doc_id": "33333333-3333-3333-3333-333333333333",
        "text": "系统说明",
        "metadata": {"enhancement": {"questions": ["旧问题？"]}},
    }

    result = await enhancer.enhance(chunk)

    assert result["metadata"]["enhancement"] == {}
