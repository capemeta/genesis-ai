from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_minimal_pdf_bytes() -> bytes:
    # A tiny valid 1-page PDF with plain text.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\n"
        b"BT /F1 18 Tf 36 90 Td (Docling smoke test) Tj ET\n"
        b"endstream\n"
        b"endobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000239 00000 n \n"
        b"0000000333 00000 n \n"
        b"trailer<</Root 1 0 R/Size 6>>\n"
        b"startxref\n"
        b"403\n"
        b"%%EOF\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Docling Hub auto-download smoke test")
    parser.add_argument(
        "--pdf",
        type=str,
        default="",
        help="Optional PDF path. If not provided, a tiny in-memory PDF is used.",
    )
    parser.add_argument(
        "--ocr-engine",
        type=str,
        default="tesseract",
        choices=["auto", "tesseract", "rapidocr", "paddleocr"],
        help="Requested OCR engine for docling parser config.",
    )
    parser.add_argument(
        "--enable-ocr",
        action="store_true",
        help="Enable OCR in docling pipeline (default: disabled).",
    )
    args = parser.parse_args()

    project_root = _project_root()
    sys.path.insert(0, str(project_root))

    from rag.ingestion.parsers.pdf.docling.parser import DoclingParser

    input_bytes: bytes
    input_name: str
    if args.pdf:
        pdf_path = Path(args.pdf).expanduser().resolve()
        if not pdf_path.exists():
            print(f"[FAIL] PDF not found: {pdf_path}")
            return 2
        input_bytes = pdf_path.read_bytes()
        input_name = str(pdf_path)
    else:
        input_bytes = _build_minimal_pdf_bytes()
        input_name = "<in-memory minimal pdf>"

    print("=" * 90)
    print("Docling Hub Download Smoke Test")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Input: {input_name}")
    print(f"Input bytes: {len(input_bytes)}")
    print(
        f"Config: enable_ocr={args.enable_ocr}, ocr_engine={args.ocr_engine}, "
        "fallback_to_native=False"
    )
    print("=" * 90)

    docling = DoclingParser(
        enable_ocr=args.enable_ocr,
        ocr_engine=args.ocr_engine,
        ocr_languages=["ch", "en"],
        extract_tables=True,
        fallback_to_native=False,  # Force pure docling, so hub/model issues are visible.
    )

    try:
        text, metadata = docling.parse(input_bytes, ".pdf")
    except Exception as exc:
        print(f"[FAIL] Docling parse failed: {exc}")
        return 1

    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_md = output_dir / f"docling_hub_smoke_{stamp}.md"
    output_md.write_text(text or "", encoding="utf-8")

    print("[OK] Docling parse succeeded.")
    print(f"parse_method={metadata.get('parse_method')}")
    print(f"parser={metadata.get('parser')}")
    print(f"element_count={metadata.get('element_count')}")
    print(f"output={output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

