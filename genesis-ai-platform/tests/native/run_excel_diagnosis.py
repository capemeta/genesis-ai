"""
独立运行脚本，不依赖 pytest，直接诊断 Excel 分块情况。
运行方式：
    .venv\Scripts\python.exe tests/native/run_excel_diagnosis.py
"""
import json
import logging
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.ingestion.chunkers.excel_general_chunker import ExcelGeneralChunker
from rag.ingestion.chunkers.excel_table_chunker import ExcelTableChunker
from rag.ingestion.parsers.excel.excel_parser import ExcelParser
from rag.ingestion.parsers.excel.excel_table_parser import ExcelTableParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = PROJECT_ROOT / "tests" / "data"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "native" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_FILE = next(DATA_DIR.glob("19*.xlsx"))


def main():
    logger.info("读取文件: %s", SAMPLE_FILE.name)
    file_bytes = SAMPLE_FILE.read_bytes()

    # ---- 通用模式（chars 口径，与本地测试一致）----
    general_text, general_metadata = ExcelParser().parse(file_bytes, ".xlsx")
    general_chunker_chars = ExcelGeneralChunker(max_embed_tokens=512, token_count_method="chars")
    general_chunks_chars = general_chunker_chars.chunk(general_text, general_metadata)

    # ---- 通用模式（tokenizer 口径，与生产一致）----
    general_chunker_tok = ExcelGeneralChunker(max_embed_tokens=512, token_count_method="tokenizer")
    general_chunks_tok = general_chunker_tok.chunk(general_text, general_metadata)

    # ---- 表格模式（chars 口径）----
    table_text, table_metadata = ExcelTableParser().parse(file_bytes, ".xlsx")
    table_chunker_chars = ExcelTableChunker(max_embed_tokens=512, token_count_method="chars")
    table_chunks_chars = table_chunker_chars.chunk(table_text, table_metadata)

    # ---- 表格模式（tokenizer 口径，与生产一致）----
    table_chunker_tok = ExcelTableChunker(max_embed_tokens=512, token_count_method="tokenizer")
    table_chunks_tok = table_chunker_tok.chunk(table_text, table_metadata)

    # 以 tokenizer 模式作为主要分析对象（与生产一致）
    general_chunks = general_chunks_tok
    table_chunks = table_chunks_tok

    # ---- 诊断：每行的 token 估算 ----
    row_diagnostics = []
    for sheet_info in general_metadata.get("sheets_data", []):
        sheet_name = sheet_info["sheet_name"]
        header = sheet_info["header"]
        rows = sheet_info["rows"]
        for row_idx, row in enumerate(rows):
            kv = "; ".join(f"{k}: {v}" for k, v in zip(header, row) if v and v.strip())
            estimated_tokens = max(1, int(len(kv) / 2.0 + 0.5))
            row_diagnostics.append({
                "sheet_name": sheet_name,
                "row_index": row_idx + 1,
                "col_count": len(header),
                "non_empty_cols": sum(1 for v in row if v and v.strip()),
                "kv_text_length_chars": len(kv),
                "estimated_tokens_chars": estimated_tokens,
                "over_512": estimated_tokens > 512,
                "kv_preview": kv[:300] + ("..." if len(kv) > 300 else ""),
            })

    # ---- overflow 统计 ----
    general_overflow = sum(1 for c in general_chunks if c.get("metadata", {}).get("is_row_overflow"))
    table_overflow = sum(1 for c in table_chunks if c.get("metadata", {}).get("is_row_overflow"))

    diagnosis_report = {
        "sample_file": SAMPLE_FILE.name,
        "sheets_summary": [
            {
                "sheet_name": s["sheet_name"],
                "header_count": len(s["header"]),
                "row_count": len(s["rows"]),
                "header_preview": s["header"][:10],
            }
            for s in general_metadata.get("sheets_data", [])
        ],
        "row_diagnostics": row_diagnostics,
        "general_mode": {
            "total_chunks": len(general_chunks),
            "overflow_chunks": general_overflow,
            "detail": [
                {
                    "sheet_name": c.get("metadata", {}).get("sheet_name"),
                    "row_start": c.get("metadata", {}).get("row_start"),
                    "row_end": c.get("metadata", {}).get("row_end"),
                    "is_row_overflow": c.get("metadata", {}).get("is_row_overflow", False),
                    "overflow_part_index": c.get("metadata", {}).get("overflow_part_index"),
                    "overflow_part_total": c.get("metadata", {}).get("overflow_part_total"),
                    "content_len": len(c.get("text", "")),
                }
                for c in general_chunks
            ],
        },
        "table_mode": {
            "total_chunks": len(table_chunks),
            "overflow_chunks": table_overflow,
            "summary_chunks": sum(1 for c in table_chunks if c.get("type") == "summary"),
            "detail": [
                {
                    "sheet_name": c.get("metadata", {}).get("sheet_name"),
                    "row_index": c.get("metadata", {}).get("row_index"),
                    "chunk_type": c.get("type"),
                    "is_row_overflow": c.get("metadata", {}).get("is_row_overflow", False),
                    "overflow_part_index": c.get("metadata", {}).get("overflow_part_index"),
                    "overflow_part_total": c.get("metadata", {}).get("overflow_part_total"),
                    "content_len": len(c.get("text", "")),
                }
                for c in table_chunks
            ],
        },
    }

    # 打印到控制台
    print("\n===== Excel 分块诊断报告 =====")
    print(f"文件: {SAMPLE_FILE.name}")
    print(f"\n[Sheet 结构]")
    for s in diagnosis_report["sheets_summary"]:
        print(f"  Sheet={s['sheet_name']} | 列数={s['header_count']} | 数据行数={s['row_count']}")
        print(f"  表头前10列: {s['header_preview']}")

    print(f"\n[每行 token 估算]")
    for rd in row_diagnostics:
        flag = " <<<< OVER 512!" if rd["over_512"] else ""
        print(f"  行{rd['row_index']} | 列数={rd['col_count']} 非空={rd['non_empty_cols']} | "
              f"KV字符数={rd['kv_text_length_chars']} 估算tokens={rd['estimated_tokens_chars']}{flag}")
        print(f"    预览: {rd['kv_preview'][:150]}")

    print(f"\n[两种 token 口径对比]")
    print(f"  通用模式 chars={len(general_chunks_chars)} chunks | tokenizer={len(general_chunks_tok)} chunks")
    print(f"  表格模式 chars={len(table_chunks_chars)} chunks | tokenizer={len(table_chunks_tok)} chunks")

    print(f"\n[通用模式 tokenizer 口径] 总分块数={len(general_chunks)}, overflow={sum(1 for c in general_chunks if c.get('metadata', {}).get('is_row_overflow'))}")
    for i, c in enumerate(general_chunks[:20]):
        m = c.get("metadata", {})
        print(f"  chunk[{i}] row_start={m.get('row_start')} row_end={m.get('row_end')} "
              f"overflow={m.get('is_row_overflow',False)} part={m.get('overflow_part_index')}/{m.get('overflow_part_total')} "
              f"content_len={len(c.get('text',''))}")
    if len(general_chunks) > 20:
        print(f"  ... 共 {len(general_chunks)} 条，仅显示前20条")

    print(f"\n[表格模式 tokenizer 口径] 总分块数={len(table_chunks)}, overflow={sum(1 for c in table_chunks if c.get('metadata', {}).get('is_row_overflow'))}, summary={sum(1 for c in table_chunks if c.get('type') == 'summary')}")
    for i, c in enumerate(table_chunks[:20]):
        m = c.get("metadata", {})
        print(f"  chunk[{i}] type={c.get('type')} row_index={m.get('row_index')} "
              f"overflow={m.get('is_row_overflow',False)} part={m.get('overflow_part_index')}/{m.get('overflow_part_total')} "
              f"content_len={len(c.get('text',''))}")
    if len(table_chunks) > 20:
        print(f"  ... 共 {len(table_chunks)} 条，仅显示前20条")

    # 落盘完整报告
    out_path = OUTPUT_DIR / "excel_diagnosis_report.json"
    out_path.write_text(json.dumps(diagnosis_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完整报告已写入: {out_path}")


if __name__ == "__main__":
    main()
