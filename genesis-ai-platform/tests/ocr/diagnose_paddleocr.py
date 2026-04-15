"""
诊断 PaddleOCR 安装问题
"""

import sys
import os

# 设置环境变量
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

print("=" * 60)
print("PaddleOCR 安装诊断")
print("=" * 60)

# 1. 检查 Python 版本
print(f"\n1. Python 版本: {sys.version}")

# 2. 检查 paddleocr 是否安装
print("\n2. 检查 paddleocr...")
try:
    import paddleocr
    print(f"   ✓ paddleocr 已安装: {paddleocr.__version__}")
except ImportError as e:
    print(f"   ✗ paddleocr 未安装: {e}")
    sys.exit(1)

# 3. 检查 langchain
print("\n3. 检查 langchain...")
try:
    import langchain
    print(f"   ✓ langchain 已安装: {langchain.__version__}")
except ImportError:
    print("   ✗ langchain 未安装")

# 4. 检查 langchain-community
print("\n4. 检查 langchain-community...")
try:
    import langchain_community
    print(f"   ✓ langchain-community 已安装: {langchain_community.__version__}")
except ImportError:
    print("   ✗ langchain-community 未安装")

# 5. 检查 langchain.docstore
print("\n5. 检查 langchain.docstore...")
try:
    from langchain.docstore.document import Document
    print("   ✓ langchain.docstore.document 可用")
except ImportError as e:
    print(f"   ✗ langchain.docstore.document 不可用: {e}")
    print("   尝试从 langchain_community 导入...")
    try:
        from langchain_community.docstore.document import Document
        print("   ✓ langchain_community.docstore.document 可用")
    except ImportError as e2:
        print(f"   ✗ langchain_community.docstore.document 也不可用: {e2}")

# 6. 尝试导入 PaddleOCR
print("\n6. 尝试导入 PaddleOCR...")
try:
    from paddleocr import PaddleOCR
    print("   ✓ PaddleOCR 导入成功")
    
    # 7. 尝试初始化
    print("\n7. 尝试初始化 PaddleOCR...")
    try:
        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        print("   ✓ PaddleOCR 初始化成功")
        print("\n✅ PaddleOCR 可以正常使用！")
    except Exception as e:
        print(f"   ✗ PaddleOCR 初始化失败: {e}")
        print("\n❌ PaddleOCR 初始化失败")
        
except ImportError as e:
    print(f"   ✗ PaddleOCR 导入失败: {e}")
    print("\n❌ PaddleOCR 导入失败")
    
    # 显示详细错误
    import traceback
    print("\n详细错误信息:")
    print("-" * 60)
    traceback.print_exc()
    print("-" * 60)
    
    # 给出修复建议
    print("\n修复建议:")
    print("1. 卸载并重新安装 paddleocr:")
    print("   uv remove paddleocr")
    print("   uv add paddleocr")
    print("\n2. 或者使用旧版本的 paddleocr (不依赖 langchain):")
    print("   uv add paddleocr==2.7.0.3")
    print("\n3. 或者使用 Tesseract 代替:")
    print("   python tests/ocr/tesseract_ocr_demo_01.py")

print("\n" + "=" * 60)
