"""
调试: 直接模拟 parser 的逻辑，看图片是否被正确识别
"""
import sys, fitz
from pathlib import Path
sys.path.insert(0, str(Path(r'd:\workspace\python\genesis-ai\genesis-ai-platform')))

from rag.ingestion.parsers.pdf.native.parser import NativePDFParser
from rag.ingestion.parsers.pdf.native.layout import LayoutEngine

PDF_PATH = r"d:\workspace\python\genesis-ai\genesis-ai-platform\tests\data\江西开普元AI中台对外接口规范_v1.2.pdf"

doc = fitz.open(PDF_PATH)
page = doc[2]  # 第3页

print(f"Page rect: {page.rect}")

img_info = page.get_image_info()
print(f"Total images from get_image_info: {len(img_info)}")
for i, img in enumerate(img_info):
    bbox = img["bbox"]
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    pct_w = w / page.rect.width * 100
    pct_h = h / page.rect.height * 100
    print(f"  img[{i}]: size={round(w)}x{round(h)}, pct={pct_w:.1f}%w x {pct_h:.1f}%h")
    print(f"         cond1(>5%w): {w > page.rect.width * 0.05}")
    print(f"         cond2(>3%h): {h > page.rect.height * 0.03}")
    valid = (w > page.rect.width * 0.05) and (h > page.rect.height * 0.03)
    print(f"         VALID: {valid}")

valid_images = [
    img for img in img_info
    if img["bbox"][2] - img["bbox"][0] > page.rect.width * 0.05
    and img["bbox"][3] - img["bbox"][1] > page.rect.height * 0.03
]
print(f"\nvalid_images count: {len(valid_images)}")

doc.close()

print("\n--- Now running full parser and checking for image elements ---")
parser = NativePDFParser()
elements = parser.parse(PDF_PATH)
img_elements = [e for e in elements if e['type'] == 'image']
print(f"Image elements found: {len(img_elements)}")
for el in img_elements:
    print(f"  {el}")
