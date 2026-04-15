from pathlib import Path
import importlib.util
import sys
import types


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


rag_pkg = types.ModuleType("rag")
rag_pkg.__path__ = [str(PROJECT_ROOT / "rag")]
sys.modules.setdefault("rag", rag_pkg)

rag_utils_pkg = types.ModuleType("rag.utils")
rag_utils_pkg.__path__ = [str(PROJECT_ROOT / "rag" / "utils")]
sys.modules.setdefault("rag.utils", rag_utils_pkg)

rag_ingestion_pkg = types.ModuleType("rag.ingestion")
rag_ingestion_pkg.__path__ = [str(PROJECT_ROOT / "rag" / "ingestion")]
sys.modules.setdefault("rag.ingestion", rag_ingestion_pkg)

rag_chunkers_pkg = types.ModuleType("rag.ingestion.chunkers")
rag_chunkers_pkg.__path__ = [str(PROJECT_ROOT / "rag" / "ingestion" / "chunkers")]
sys.modules.setdefault("rag.ingestion.chunkers", rag_chunkers_pkg)

_load_module("rag.utils.model_utils", PROJECT_ROOT / "rag" / "utils" / "model_utils.py")
token_utils_module = _load_module("rag.utils.token_utils", PROJECT_ROOT / "rag" / "utils" / "token_utils.py")
_load_module("rag.ingestion.chunkers.base", PROJECT_ROOT / "rag" / "ingestion" / "chunkers" / "base.py")
web_chunker_module = _load_module(
    "rag.ingestion.chunkers.web_page_chunker",
    PROJECT_ROOT / "rag" / "ingestion" / "chunkers" / "web_page_chunker.py",
)

WebPageChunker = web_chunker_module.WebPageChunker
count_tokens = token_utils_module.count_tokens


def test_web_page_chunker_preserves_table_parent_and_splits_leaf_fragments() -> None:
    """超限表格应保留完整父块，并继续拆成可向量化的子块。"""
    chunker = WebPageChunker(chunk_size=120, chunk_overlap=0, embedding_model_limit=120, max_embed_tokens=120)
    body_rows = [f"| 第{i}项 | {'很长的内容' * 12} |" for i in range(1, 7)]
    table_markdown = "\n".join(["| 字段 | 值 |", "| --- | --- |", *body_rows])
    structured_sections = [
        {
            "section_id": "s1",
            "section_type": "table_section",
            "title": "基本信息",
            "heading_path": ["事项指南", "基本信息"],
            "markdown": table_markdown,
            "blocks": [
                {
                    "block_id": "b1",
                    "type": "table",
                    "text": table_markdown,
                    "table_format": "markdown",
                    "dom_index": 1,
                    "source_refs": [{"ref_type": "web_anchor", "heading_path": ["事项指南", "基本信息"]}],
                }
            ],
        }
    ]

    chunks = chunker.chunk(
        text=table_markdown,
        metadata={"structured_sections": structured_sections, "source_url": "https://example.com"},
    )

    table_parent = next(chunk for chunk in chunks if chunk["metadata"].get("chunk_role") == "web_table_parent")
    table_fragments = [chunk for chunk in chunks if chunk["metadata"].get("chunk_role") == "web_table_fragment"]

    assert table_parent["metadata"]["child_ids"]
    assert len(table_fragments) >= 2
    assert all(fragment["metadata"]["parent_id"] == table_parent["metadata"]["node_id"] for fragment in table_fragments)
    assert all(count_tokens(fragment["text"]) <= chunker.effective_leaf_limit for fragment in table_fragments)
    assert all("事项指南 > 基本信息" in fragment["text"] for fragment in table_fragments)


def test_web_page_chunker_uses_page_level_budget_for_text_leaves() -> None:
    """文本叶子块也必须满足页面级 max_embed_tokens 预算。"""
    chunker = WebPageChunker(chunk_size=220, chunk_overlap=0, embedding_model_limit=300, max_embed_tokens=90)
    long_paragraph = "第一段内容。" * 40
    structured_sections = [
        {
            "section_id": "s1",
            "section_type": "main_content",
            "title": "办理说明",
            "heading_path": ["事项指南", "办理说明"],
            "markdown": long_paragraph,
            "blocks": [
                {
                    "block_id": "b1",
                    "type": "text",
                    "text": long_paragraph,
                    "dom_index": 2,
                    "source_refs": [{"ref_type": "web_anchor", "heading_path": ["事项指南", "办理说明"]}],
                }
            ],
        }
    ]

    chunks = chunker.chunk(
        text=long_paragraph,
        metadata={"structured_sections": structured_sections, "source_url": "https://example.com"},
    )
    text_leaves = [chunk for chunk in chunks if chunk["metadata"].get("chunk_role") == "web_text_leaf"]

    assert len(text_leaves) >= 2
    assert all(count_tokens(chunk["text"]) <= chunker.effective_leaf_limit for chunk in text_leaves)
    assert all(chunk["metadata"].get("header_path") == "事项指南 > 办理说明" for chunk in text_leaves)
