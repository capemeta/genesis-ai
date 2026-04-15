"""
PaddleOCR demo
- Test PaddleOCR engine for Chinese document recognition
- Run single-page OCR and full parse
- Export markdown to tests/ocr/out
"""

import logging
import os
import sys
from pathlib import Path

# 设置环境变量（必须在导入 paddleocr 之前）
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PDF_PATH = _current_dir.parent / "data" / "标识标牌合同-扫描版.pdf"
OUT_DIR = _current_dir / "out"
OUT_MD_NAME = "标识标牌合同-扫描版_paddleocr.md"

# OCR paragraph merge controls (easy to tweak here)
OCR_REFLOW_ENABLED = False
OCR_MERGE_PROFILE = "balanced"  # conservative / balanced / aggressive
OCR_MERGE_MIN_SCORE = None  # e.g. 2.0, None uses profile default
OCR_PREPROCESS_ENABLED = True
OCR_RED_SEAL_SUPPRESSION = True
OCR_POST_CORRECTION_ENABLED = True
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


def build_native_parser():
    from rag.ingestion.parsers.pdf.native.parser import NativePDFParser

    return NativePDFParser(
        enable_ocr=True,
        ocr_engine="paddleocr",  # 使用 PaddleOCR
        ocr_languages=["ch"],
        ocr_reflow_enabled=OCR_REFLOW_ENABLED,
        ocr_merge_profile=OCR_MERGE_PROFILE,
        ocr_merge_min_score=OCR_MERGE_MIN_SCORE,
        ocr_legacy_mode=OCR_LEGACY_MODE,
        ocr_preprocess_enabled=OCR_PREPROCESS_ENABLED,
        ocr_red_seal_suppression=OCR_RED_SEAL_SUPPRESSION,
        ocr_post_correction_enabled=OCR_POST_CORRECTION_ENABLED,
        ocr_min_confidence=OCR_MIN_CONFIDENCE,
    )


def test_paddleocr_available() -> bool:
    """测试 PaddleOCR 是否可用"""
    try:
        from paddleocr import PaddleOCR
        
        # 初始化 PaddleOCR（会下载模型，首次较慢）
        logger.info("初始化 PaddleOCR...")
        # ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        ocr = PaddleOCR(
            device="cpu",
            lang="ch",
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
            cpu_threads=1,
        )

        logger.info("PaddleOCR 初始化成功")
        logger.info("支持的语言: ch (中文), en (英文)")
        return True
    except ModuleNotFoundError as e:
        logger.error("PaddleOCR 依赖缺失: %s", e)
        if "langchain" in str(e):
            logger.error("请安装: pip install langchain-community")
        else:
            logger.error("请安装: pip install paddleocr")
        return False
    except ImportError as e:
        logger.error("PaddleOCR 导入失败: %s", e)
        logger.error("请安装: pip install paddleocr")
        return False
    except Exception as e:
        logger.error("PaddleOCR 初始化失败: %s", e)
        logger.error("可能的原因:")
        logger.error("  1. 缺少依赖包")
        logger.error("  2. 网络问题（首次使用需要下载模型）")
        return False


def test_ocr_with_paddleocr_single_image():
    """测试单页 OCR 识别"""
    if not PDF_PATH.exists():
        logger.warning("skip: test PDF does not exist: %s", PDF_PATH)
        return

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
    engine = parser.ocr_pipeline.resolve_engine("paddleocr")
    lines = parser.ocr_pipeline.recognize(image=image, engine=engine, languages=["ch", "en"]) if engine else []
    logger.info("ocr_pipeline(paddleocr) returned %d lines", len(lines))
    for i, line in enumerate(lines[:5]):
        logger.info("  line %d: %s (conf=%.2f)", i + 1, (line.get("text") or "")[:60], line.get("confidence", 0))
    if len(lines) > 5:
        logger.info("  ... total lines: %d", len(lines))


def test_full_parse_scan_pdf_with_paddleocr():
    """测试完整 PDF 解析"""
    if not PDF_PATH.exists():
        logger.warning("skip: test PDF does not exist: %s", PDF_PATH)
        return None

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
    print("=" * 60)
    print("PaddleOCR demo")
    print("=" * 60)
    print("Test PDF:", PDF_PATH, "exists:", PDF_PATH.exists())
    print(
        "OCR reflow:",
        f"enabled={OCR_REFLOW_ENABLED}, profile={OCR_MERGE_PROFILE}, min_score={OCR_MERGE_MIN_SCORE}",
    )
    print(
        "PaddleOCR enhance:",
        (
            f"preprocess={OCR_PREPROCESS_ENABLED}, "
            f"seal_suppression={OCR_RED_SEAL_SUPPRESSION}, "
            f"post_correction={OCR_POST_CORRECTION_ENABLED}, "
            f"min_conf={OCR_MIN_CONFIDENCE}, "
            f"legacy_mode={OCR_LEGACY_MODE}"
        ),
    )
    print()

    ok1 = test_paddleocr_available()
    if not ok1:
        print("\n修复建议:")
        print("1. 安装 PaddleOCR: pip install paddleocr")
        print("2. 安装缺失依赖: pip install langchain-community")
        print("3. 或者使用 Tesseract: python tests/ocr/tesseract_ocr_demo_01.py")
        return 1

    test_ocr_with_paddleocr_single_image()
    test_full_parse_scan_pdf_with_paddleocr()

    print()
    print("Markdown output:", OUT_DIR / OUT_MD_NAME)
    print("=" * 60)
    print("Done")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
