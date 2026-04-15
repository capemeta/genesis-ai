"""测试 NativePDFParser 支持 bytes 输入"""
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))

from rag.ingestion.parsers.pdf.native.parser import NativePDFParser

def test_bytes_input():
    """测试使用 bytes 输入解析 PDF"""
    # 读取 PDF 文件为 bytes
    pdf_path = Path(r"d:\workspace\python\genesis-ai\genesis-ai-platform\tests\data\数据要素大赛申报书（字数删减）.pdf")
    
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    print(f"PDF 文件大小: {len(pdf_bytes)} bytes")
    print(f"PDF 文件头: {pdf_bytes[:50]}")
    
    # 测试 1: 使用 bytes 解析（元素模式）
    print("\n=== 测试 1: 元素模式 ===")
    parser = NativePDFParser(enable_ocr=False)
    elements = parser.parse(pdf_bytes)
    
    print(f"解析成功！")
    print(f"元素数量: {len(elements)}")
    print(f"前 5 个元素:")
    for i, el in enumerate(elements[:5]):
        print(f"  {i+1}. type={el['type']}, content={el['content'][:50]}...")
    
    # 检查图片元素
    image_elements = [el for el in elements if el['type'] == 'image']
    print(f"\n图片元素数量: {len(image_elements)}")
    if image_elements:
        print(f"第一张图片信息:")
        img = image_elements[0]
        metadata = img.get('metadata', {})
        print(f"  文件名: {img['content']}")
        print(f"  图片ID: {metadata.get('image_id')}")
        print(f"  格式: {metadata.get('ext')}")
        print(f"  大小: {len(metadata.get('blob', b''))} bytes")
        print(f"  页码: {img.get('page_no')}")
        print(f"  是否矢量图: {metadata.get('is_vector')}")

if __name__ == "__main__":
    test_bytes_input()
