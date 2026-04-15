"""Markdown 生产级拆分边界用例。

这些测试验证完整 MarkdownChunker 在超大独立元素上的父子块语义：
完整大元素应保留在非向量化父/中间块里，向量化叶子块则用于检索。
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest


def _count_words(text: str) -> int:
    """使用确定性的词数计数，让超限场景不受真实 tokenizer 版本影响。"""
    return len(str(text).split())


def _load_module(module_name: str, path: Path) -> Any:
    """按文件路径加载模块，避免应用包初始化带来的外部依赖。"""
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_package_stub(name: str, path: Path | None = None) -> None:
    """安装最小包桩，避免导入 rag 顶层时触发数据库/服务初始化。"""
    module = types.ModuleType(name)
    module.__path__ = [str(path)] if path else []
    sys.modules[name] = module


def _load_markdown_chunker() -> type:
    """加载完整 MarkdownChunker，同时隔离应用级初始化副作用。"""
    project_root = Path(__file__).resolve().parents[2]

    _install_package_stub("rag", project_root / "rag")
    _install_package_stub("rag.ingestion", project_root / "rag" / "ingestion")
    _install_package_stub("rag.ingestion.chunkers", project_root / "rag" / "ingestion" / "chunkers")
    _install_package_stub(
        "rag.ingestion.chunkers.markdown",
        project_root / "rag" / "ingestion" / "chunkers" / "markdown",
    )
    _install_package_stub("rag.utils", project_root / "rag" / "utils")

    token_utils = types.ModuleType("rag.utils.token_utils")
    token_utils.count_tokens = _count_words
    sys.modules["rag.utils.token_utils"] = token_utils

    for module_name, relative_path in [
        ("rag.ingestion.chunkers.base", "rag/ingestion/chunkers/base.py"),
        ("rag.ingestion.chunkers.markdown.config", "rag/ingestion/chunkers/markdown/config.py"),
        ("rag.ingestion.chunkers.markdown.detector", "rag/ingestion/chunkers/markdown/detector.py"),
        ("rag.ingestion.chunkers.markdown.splitter", "rag/ingestion/chunkers/markdown/splitter.py"),
        ("rag.ingestion.chunkers.markdown.syntax_parser", "rag/ingestion/chunkers/markdown/syntax_parser.py"),
        ("rag.ingestion.chunkers.markdown.chunker", "rag/ingestion/chunkers/markdown/chunker.py"),
    ]:
        _load_module(module_name, project_root / relative_path)

    return sys.modules["rag.ingestion.chunkers.markdown.chunker"].MarkdownChunker


MarkdownChunker = _load_markdown_chunker()


def _chunker(limit: int = 80) -> Any:
    """构造小窗口 chunker，用于稳定复现超限边界。"""
    return MarkdownChunker(
        chunk_size=limit,
        embedding_model_limit=limit,
        enable_hierarchy=True,
        min_chunk_size=1,
    )


def _table_text() -> tuple[str, str]:
    long_cell_marker = "OVERSIZED_TABLE_ROW_MUST_NOT_BE_DROPPED"
    long_cell = " ".join([long_cell_marker, *["长单元格"] * 70])
    return long_cell_marker, "\n".join(
        [
            "# 生产表格",
            "",
            "| 字段 | 描述 |",
            "| --- | --- |",
            "| 正常字段 | 正常描述 |",
            f"| 超长字段 | {long_cell} |",
            "| 末尾字段 | 末尾描述 |",
        ]
    )


def _list_text() -> tuple[str, str]:
    long_item_marker = "OVERSIZED_LIST_ITEM_MUST_NOT_BE_DROPPED"
    long_item = " ".join([long_item_marker, *["长列表项"] * 120])
    return long_item_marker, "\n".join(
        [
            "# 生产列表",
            "",
            "- 正常项",
            f"- {long_item}",
            "- 末尾项",
        ]
    )


def test_table_chunker_keeps_oversized_row_in_non_vectorized_parent() -> None:
    """表格单行超限时，完整表格仍保留在非向量化父/中间块里。"""
    marker, text = _table_text()

    chunks = _chunker().chunk(text, {})
    retained_chunks = [
        chunk
        for chunk in chunks
        if marker in chunk["text"] and not chunk["metadata"].get("should_vectorize", True)
    ]

    assert retained_chunks
    assert any(chunk["metadata"].get("child_ids") for chunk in retained_chunks)


def test_list_chunker_keeps_oversized_item_in_non_vectorized_parent() -> None:
    """列表单行项超限时，完整列表仍保留在非向量化父/中间块里。"""
    marker, text = _list_text()

    chunks = _chunker().chunk(text, {})
    retained_chunks = [
        chunk
        for chunk in chunks
        if marker in chunk["text"] and not chunk["metadata"].get("should_vectorize", True)
    ]

    assert retained_chunks
    assert any(chunk["metadata"].get("child_ids") for chunk in retained_chunks)


@pytest.mark.xfail(
    strict=True,
    reason="当前表格超长行保留在父/中间块，但没有出现在可向量化叶子块中，检索覆盖可能不足。",
)
def test_table_vectorized_leaf_chunks_cover_oversized_row_content() -> None:
    """表格超长行最终也应进入某个可向量化叶子块。"""
    marker, text = _table_text()

    chunks = _chunker().chunk(text, {})
    vectorized_text = "\n".join(
        chunk["text"]
        for chunk in chunks
        if chunk["metadata"].get("should_vectorize", False)
    )

    assert marker in vectorized_text


@pytest.mark.xfail(
    strict=True,
    reason="当前列表超长单行项保留在父/中间块，但没有出现在可向量化叶子块中，检索覆盖可能不足。",
)
def test_list_vectorized_leaf_chunks_cover_oversized_single_line_item() -> None:
    """列表超长单行项最终也应进入某个可向量化叶子块。"""
    marker, text = _list_text()

    chunks = _chunker().chunk(text, {})
    vectorized_text = "\n".join(
        chunk["text"]
        for chunk in chunks
        if chunk["metadata"].get("should_vectorize", False)
    )

    assert marker in vectorized_text
