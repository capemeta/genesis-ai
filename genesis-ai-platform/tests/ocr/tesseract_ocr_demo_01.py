"""
Tesseract OCR demo
- Read tesseract path only from env var TESSERACT_HOME
- Run single-page OCR and full parse
- Export markdown to tests/ocr/out
"""

import logging
import os
import sys
from pathlib import Path

_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PDF_PATH = _current_dir.parent / "data" / "标识标牌合同-扫描版.pdf"

OUT_DIR = _current_dir / "out"
OUT_MD_NAME = "标识标牌合同-扫描版_tesseract_ocr.md"

PDF_PATH = _current_dir.parent / "data" / "2014年广东省中考化学试题(清晰扫描版).pdf"
OUT_MD_NAME = "2014年广东省中考化学试题(清晰扫描版)_tesseract_ocr.md"

# OCR paragraph merge controls (easy to tweak here)
OCR_REFLOW_ENABLED = False
OCR_MERGE_PROFILE = "balanced"  # conservative / balanced / aggressive
OCR_MERGE_MIN_SCORE = None  # e.g. 2.0, None uses profile default
OCR_PREPROCESS_ENABLED = True
OCR_RED_SEAL_SUPPRESSION = True
OCR_POST_CORRECTION_ENABLED = True
OCR_TESSERACT_PSM_LIST = [6]
OCR_MIN_CONFIDENCE = 45.0
OCR_LEGACY_MODE = False


def elements_to_markdown(elements, asset_dir_name=None):
    md_lines = []
    in_code_block = False
    for i, el in enumerate(elements):
        el_type = el["type"]
        content = el["content"]
        metadata = el.get("metadata", {})

        if el_type == "code":
            if not in_code_block:
                md_lines.append("```")
                in_code_block = True
            md_lines.append(content)
            is_next_code = i + 1 < len(elements) and elements[i + 1]["type"] == "code"
            if not is_next_code:
                md_lines.append("```")
                in_code_block = False
            continue

        if in_code_block:
            md_lines.append("```")
            in_code_block = False

        if el_type == "title":
            level = metadata.get("level", 1)
            md_lines.append(f"\n{'#' * level} {content.strip()}")
        elif el_type.startswith("h") and el_type[1:].isdigit():
            level = int(el_type[1:])
            md_lines.append(f"\n{'#' * level} {content.strip()}")
        elif el_type == "table":
            md_lines.append(f"\n{content}\n")
        elif el_type == "image":
            image_bytes = metadata.get("blob") or metadata.get("image_bytes")
            if image_bytes and asset_dir_name:
                img_ref = f"{asset_dir_name}/{content}"
                md_lines.append(f"\n![{content}]({img_ref})\n")
            else:
                md_lines.append(f"\n![{content}]({content})\n")
        else:
            md_lines.append(content)

    return "\n".join(md_lines)


def ensure_tesseract_cmd():
    from rag.ingestion.parsers.ocr import get_tesseract_exe_path, TESSERACT_SETUP_HINT, ensure_tesseract_cmd as _ensure
    import pytesseract

    exe = get_tesseract_exe_path()
    if exe:
        _ensure(pytesseract)
        logger.info("set pytesseract.tesseract_cmd = %s", exe)
    else:
        logger.warning("%s", TESSERACT_SETUP_HINT)


def build_native_parser():
    from rag.ingestion.parsers.pdf.native.parser import NativePDFParser

    return NativePDFParser(
        enable_ocr=True,
        ocr_engine="tesseract",
        ocr_languages=["ch"],
        ocr_reflow_enabled=OCR_REFLOW_ENABLED,
        ocr_merge_profile=OCR_MERGE_PROFILE,
        ocr_merge_min_score=OCR_MERGE_MIN_SCORE,
        ocr_legacy_mode=OCR_LEGACY_MODE,
        ocr_preprocess_enabled=OCR_PREPROCESS_ENABLED,
        ocr_red_seal_suppression=OCR_RED_SEAL_SUPPRESSION,
        ocr_post_correction_enabled=OCR_POST_CORRECTION_ENABLED,
        ocr_tesseract_psm_list=OCR_TESSERACT_PSM_LIST,
        ocr_min_confidence=OCR_MIN_CONFIDENCE,
    )


def test_tesseract_available() -> bool:
    from rag.ingestion.parsers.ocr import TESSERACT_SETUP_HINT

    ensure_tesseract_cmd()
    try:
        import pytesseract

        version = pytesseract.get_tesseract_version()
        logger.info("Tesseract version: %s", version)
        langs = pytesseract.get_languages()
        logger.info("Installed languages: %s", ", ".join(sorted(langs)))
        if "chi_sim" not in langs:
            logger.warning("chi_sim is not installed, Chinese OCR quality may be poor")
        return True
    except Exception as e:
        logger.error("Tesseract unavailable: %s", e)
        logger.error("%s", TESSERACT_SETUP_HINT)
        return False


def test_ocr_with_tesseract_single_image():
    if not PDF_PATH.exists():
        logger.warning("skip: test PDF does not exist: %s", PDF_PATH)
        return

    ensure_tesseract_cmd()
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(PDF_PATH))
    if len(pdf) == 0:
        logger.warning("PDF has no pages")
        return

    page = pdf[0]
    bitmap = page.render(scale=2.0)
    image = bitmap.to_pil()
    pdf.close()

    parser = build_native_parser()
    engine = parser.ocr_pipeline.resolve_engine("tesseract")
    lines = parser.ocr_pipeline.recognize(image=image, engine=engine, languages=["ch", "en"]) if engine else []
    logger.info("ocr_pipeline(tesseract) returned %d lines", len(lines))
    for i, line in enumerate(lines[:5]):
        logger.info("  line %d: %s (conf=%.2f)", i + 1, (line.get("text") or "")[:60], line.get("confidence", 0))
    if len(lines) > 5:
        logger.info("  ... total lines: %d", len(lines))


def test_full_parse_scan_pdf_with_tesseract():
    if not PDF_PATH.exists():
        logger.warning("skip: test PDF does not exist: %s", PDF_PATH)
        return None

    ensure_tesseract_cmd()
    parser = build_native_parser()
    elements = parser.parse(str(PDF_PATH))

    text_elements = [e for e in elements if e.get("type") in ("text", "title")]
    ocr_sourced = [e for e in text_elements if (e.get("metadata") or {}).get("source") == "ocr"]
    logger.info("elements=%d, text/title=%d, source=ocr=%d", len(elements), len(text_elements), len(ocr_sourced))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_md = OUT_DIR / OUT_MD_NAME
    md_text = elements_to_markdown(elements)
    out_md.write_text(md_text, encoding="utf-8")
    logger.info("markdown written: %s", out_md)

    return elements


def main():
    from rag.ingestion.parsers.ocr import TESSERACT_SETUP_HINT

    print("=" * 60)
    print("Tesseract OCR demo (env: TESSERACT_HOME)")
    print("=" * 60)
    print("TESSERACT_HOME:", os.environ.get("TESSERACT_HOME", "") or "(not set)")
    print("Test PDF:", PDF_PATH, "exists:", PDF_PATH.exists())
    print(
        "OCR reflow:",
        f"enabled={OCR_REFLOW_ENABLED}, profile={OCR_MERGE_PROFILE}, min_score={OCR_MERGE_MIN_SCORE}",
    )
    print(
        "Tesseract enhance:",
        (
            f"preprocess={OCR_PREPROCESS_ENABLED}, "
            f"seal_suppression={OCR_RED_SEAL_SUPPRESSION}, "
            f"post_correction={OCR_POST_CORRECTION_ENABLED}, "
            f"psm={OCR_TESSERACT_PSM_LIST}, "
            f"min_conf={OCR_MIN_CONFIDENCE}, "
            f"legacy_mode={OCR_LEGACY_MODE}"
        ),
    )
    print()

    ok1 = test_tesseract_available()
    if not ok1:
        print("\n" + TESSERACT_SETUP_HINT)
        return 1

    test_ocr_with_tesseract_single_image()
    test_full_parse_scan_pdf_with_tesseract()

    print()
    print("Markdown output:", OUT_DIR / OUT_MD_NAME)
    print("=" * 60)
    print("Done")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
