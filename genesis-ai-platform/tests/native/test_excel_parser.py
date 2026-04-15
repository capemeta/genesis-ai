import json
import logging
import sys
from collections import Counter
from pathlib import Path

# 添加项目根目录到 sys.path，确保可以直接导入 rag 模块
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
sys.path.append(str(PROJECT_ROOT))

from rag.ingestion.chunkers.excel_general_chunker import ExcelGeneralChunker
from rag.ingestion.chunkers.excel_table_chunker import ExcelTableChunker
from rag.ingestion.parsers.excel.excel_parser import ExcelParser
from rag.ingestion.parsers.excel.excel_table_parser import ExcelTableParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = PROJECT_ROOT / "tests" / "data"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "native" / "output"
SAMPLE_FILE = next(DATA_DIR.glob("19*.xlsx"))


def _dump_json(file_name: str, payload: object) -> None:
    """将诊断结果落盘，便于人工检查。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / file_name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _summarize_roles(chunks: list[dict]) -> dict[str, int]:
    """统计不同 chunk_role 的数量。"""
    counter: Counter[str] = Counter()
    for chunk in chunks:
        role = str(chunk.get("metadata", {}).get("chunk_role") or "unknown")
        counter[role] += 1
    return dict(counter)


def _extract_first_block_field_names(chunk: dict) -> list[str] | None:
    """提取首个 block/source_ref 的字段列表，便于诊断输出。"""
    content_blocks = chunk.get("content_blocks", [])
    if not content_blocks:
        return None
    source_refs = content_blocks[0].get("source_refs", [])
    if not source_refs:
        return None
    field_names = source_refs[0].get("field_names")
    return field_names if isinstance(field_names, list) else None


def _extract_block_source_refs(chunk: dict) -> list[dict]:
    """提取首个内容块的 source_refs，简化断言。"""
    content_blocks = chunk.get("content_blocks", [])
    if not content_blocks:
        return []
    source_refs = content_blocks[0].get("source_refs", [])
    return source_refs if isinstance(source_refs, list) else []


def test_excel_chunk_parent_child_structure() -> None:
    """
    验证 Excel 两种模式的层级策略符合当前协议。

    目标：
    1. 样例文件仍然只解析出 3 行有效记录
    2. general 模式按 chunk_size 聚合完整多行
    3. table 模式在“单行未超限”时保持一行一个叶子块，不额外复制父子块
    3. tokenizer + 400 的 general 模式不再出现 7959 级别爆炸
    """
    file_bytes = SAMPLE_FILE.read_bytes()

    general_text, general_metadata = ExcelParser().parse(file_bytes, ".xlsx")
    table_text, table_metadata = ExcelTableParser().parse(file_bytes, ".xlsx")

    general_chunker_chars = ExcelGeneralChunker(max_embed_tokens=512, token_count_method="chars")
    general_chunks_chars = general_chunker_chars.chunk(general_text, general_metadata)

    general_chunker_tokenizer = ExcelGeneralChunker(
        max_embed_tokens=400,
        token_count_method="tokenizer",
    )
    general_chunks_tokenizer = general_chunker_tokenizer.chunk(general_text, general_metadata)

    table_chunker = ExcelTableChunker(
        max_embed_tokens=400,
        token_count_method="tokenizer",
    )
    table_chunks = table_chunker.chunk(table_text, table_metadata)

    report = {
        "sample_file": SAMPLE_FILE.name,
        "general_rows": len(general_metadata.get("sheets_data", [])[0].get("rows", [])),
        "table_rows": len(table_metadata.get("table_rows", [])),
        "general_chars_roles": _summarize_roles(general_chunks_chars),
        "general_tokenizer_roles": _summarize_roles(general_chunks_tokenizer),
        "table_roles": _summarize_roles(table_chunks),
        "general_tokenizer_chunk_count": len(general_chunks_tokenizer),
        "table_chunk_count": len(table_chunks),
        "general_tokenizer_examples": [
            {
                "chunk_role": chunk.get("metadata", {}).get("chunk_role"),
                "row_index": chunk.get("metadata", {}).get("row_index"),
                "field_names": _extract_first_block_field_names(chunk),
                "text_preview": str(chunk.get("text") or "")[:220],
            }
            for chunk in general_chunks_tokenizer[:8]
        ],
        "table_examples": [
            {
                "chunk_role": chunk.get("metadata", {}).get("chunk_role"),
                "row_index": chunk.get("metadata", {}).get("row_index"),
                "field_names": _extract_first_block_field_names(chunk),
                "text_preview": str(chunk.get("text") or "")[:220],
            }
            for chunk in table_chunks[:8]
        ],
    }

    logger.info("Excel 父子块诊断报告: %s", json.dumps(report, ensure_ascii=False, indent=2))
    _dump_json("excel_chunk_parent_child_report.json", report)
    _dump_json("excel_general_chunks_inspect.json", general_chunks_tokenizer)
    _dump_json("excel_table_chunks_inspect.json", table_chunks)

    assert general_metadata.get("sheet_count") == 1
    assert len(general_metadata.get("sheets_data", [])[0].get("rows", [])) == 3
    assert len(table_metadata.get("table_rows", [])) == 3

    general_roles = _summarize_roles(general_chunks_tokenizer)
    table_roles = _summarize_roles(table_chunks)

    assert general_roles.get("excel_sheet_root", 0) == 1
    assert (
        general_roles.get("excel_general_group", 0) >= 1
        or general_roles.get("excel_row", 0) >= 1
    )
    assert table_roles.get("excel_sheet_root", 0) == 1
    assert table_roles.get("excel_row", 0) == 3
    assert table_roles.get("excel_row_fragment", 0) >= 0

    # 修复后，general + tokenizer + 400 不应再出现几千级爆炸分块
    assert len(general_chunks_tokenizer) < 200

    for chunk in general_chunks_tokenizer:
        chunk_meta = chunk.get("metadata", {})
        chunk_role = chunk_meta.get("chunk_role")
        if chunk_role == "excel_sheet_root":
            assert chunk_meta["should_vectorize"] is False
            assert chunk_meta["is_root"] is True
            assert chunk_meta["is_leaf"] is False
            assert chunk_meta["child_ids"]
            assert "row_count" in chunk_meta
            assert "field_names" in chunk_meta
        elif chunk_role == "excel_general_group":
            assert chunk_meta["should_vectorize"] is True
            assert chunk_meta["is_leaf"] is True
            assert chunk_meta["is_root"] is False
            assert isinstance(chunk_meta.get("parent_id"), str) and chunk_meta["parent_id"]
            assert chunk_meta["row_start"] >= 1
            assert chunk_meta["row_end"] >= chunk_meta["row_start"]
            assert chunk_meta["row_count"] == (
                chunk_meta["row_end"] - chunk_meta["row_start"] + 1
            )
            assert "header" not in chunk_meta
            assert "column_types" not in chunk_meta
            block_refs = chunk.get("content_blocks", [])[0].get("source_refs", [])
            assert block_refs
            assert len(block_refs) == chunk_meta["row_count"]
            first_ref_field_names = block_refs[0].get("field_names")
            assert first_ref_field_names
            for ref in block_refs:
                assert ref.get("ref_type") == "excel_row"
                assert ref.get("sheet_name") == chunk_meta["sheet_name"]
                assert chunk_meta["row_start"] <= ref.get("row_index") <= chunk_meta["row_end"]
                assert ref.get("field_names") == first_ref_field_names
                assert "page_no" not in ref
                assert "page_number" not in ref
        elif chunk_role == "excel_row":
            has_children = bool(chunk_meta.get("child_ids"))
            if has_children:
                assert chunk_meta["should_vectorize"] is False
                assert chunk_meta["is_leaf"] is False
            else:
                assert chunk_meta["should_vectorize"] is True
                assert chunk_meta["is_leaf"] is True
            assert chunk_meta["row_index"] >= 1
            assert isinstance(chunk_meta.get("parent_id"), str) and chunk_meta["parent_id"]
            block_refs = _extract_block_source_refs(chunk)
            assert block_refs
            if chunk_meta.get("chunk_strategy") == "excel_general":
                assert block_refs[0].get("field_names")
            else:
                assert "field_names" not in block_refs[0]
        elif chunk_role == "excel_row_fragment":
            assert chunk_meta["should_vectorize"] is True
            assert chunk_meta["is_leaf"] is True
            assert isinstance(chunk_meta.get("parent_id"), str) and chunk_meta["parent_id"]
            assert isinstance(chunk_meta.get("row_id"), str) and chunk_meta["row_id"]
            assert "row_start" not in chunk_meta
            assert "row_end" not in chunk_meta
            assert "header" not in chunk_meta
            assert "column_types" not in chunk_meta
            block_refs = _extract_block_source_refs(chunk)
            assert block_refs
            assert block_refs[0].get("ref_type") == "excel_row"
            assert block_refs[0].get("sheet_name") == chunk_meta["sheet_name"]
            assert block_refs[0].get("row_index") == chunk_meta["row_index"]
            if chunk_meta.get("chunk_strategy") == "excel_general":
                assert block_refs[0].get("field_names")
            else:
                assert "field_names" not in block_refs[0]
            assert "page_no" not in block_refs[0]
            assert "page_number" not in block_refs[0]


def test_excel_table_chunker_only_splits_oversized_row() -> None:
    """
    验证 table 模式只在单行超限时生成父子块。
    """
    chunker = ExcelTableChunker(
        max_embed_tokens=80,
        token_count_method="chars",
        key_columns=["事项名称"],
    )

    metadata = {
        "table_rows": [
            {
                "sheet_name": "Sheet1",
                "row_index": 1,
                "header": ["事项名称", "办理流程"],
                "values": ["简短事项", "简短说明"],
            },
            {
                "sheet_name": "Sheet1",
                "row_index": 2,
                "header": ["事项名称", "办理流程"],
                "values": ["超长事项", "A" * 240],
            },
        ],
        "sheets": [
            {
                "sheet_name": "Sheet1",
                "row_count": 2,
            }
        ],
    }

    chunks = chunker.chunk("", metadata)
    role_counter = _summarize_roles(chunks)

    assert role_counter.get("excel_sheet_root", 0) == 1
    assert role_counter.get("excel_row", 0) == 2
    assert role_counter.get("excel_row_fragment", 0) >= 1

    short_row_chunk = next(
        chunk
        for chunk in chunks
        if chunk.get("metadata", {}).get("chunk_role") == "excel_row"
        and chunk.get("metadata", {}).get("row_index") == 1
    )
    assert short_row_chunk["metadata"]["is_leaf"] is True
    assert short_row_chunk["metadata"]["should_vectorize"] is True
    assert short_row_chunk["metadata"]["child_ids"] == []
    assert "field_names" not in _extract_block_source_refs(short_row_chunk)[0]

    long_row_chunk = next(
        chunk
        for chunk in chunks
        if chunk.get("metadata", {}).get("chunk_role") == "excel_row"
        and chunk.get("metadata", {}).get("row_index") == 2
    )
    assert long_row_chunk["metadata"]["is_leaf"] is False
    assert long_row_chunk["metadata"]["should_vectorize"] is False
    assert len(long_row_chunk["metadata"]["child_ids"]) >= 1

    long_row_fragments = [
        chunk
        for chunk in chunks
        if chunk.get("metadata", {}).get("chunk_role") == "excel_row_fragment"
        and chunk.get("metadata", {}).get("row_index") == 2
    ]
    assert long_row_fragments
    assert all("field_names" not in _extract_block_source_refs(chunk)[0] for chunk in long_row_fragments)
    assert all(
        chunk.get("metadata", {}).get("parent_id") == long_row_chunk["metadata"]["node_id"]
        for chunk in long_row_fragments
    )
