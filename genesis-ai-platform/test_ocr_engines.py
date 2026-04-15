"""
OCR 引擎测试脚本
用于验证 Tesseract 和 PaddleOCR 是否正确安装
"""
import sys
from pathlib import Path

def test_tesseract():
    """测试 Tesseract OCR"""
    print("=" * 60)
    print("测试 Tesseract OCR")
    print("=" * 60)
    
    try:
        import pytesseract
        from PIL import Image
        
        # 获取版本
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract 版本: {version}")
        
        # 测试语言包
        langs = pytesseract.get_languages()
        print(f"✅ 已安装语言包: {', '.join(langs)}")
        
        # 检查中文支持
        if 'chi_sim' in langs:
            print("✅ 中文支持: 已安装")
        else:
            print("⚠️  中文支持: 未安装（需要下载 chi_sim.traineddata）")
        
        return True
        
    except Exception as e:
        print(f"❌ Tesseract 测试失败: {e}")
        print("\n安装方法:")
        print("  Windows: choco install tesseract")
        print("  Ubuntu:  sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim")
        print("  macOS:   brew install tesseract tesseract-lang")
        return False


def test_paddleocr():
    """测试 PaddleOCR"""
    print("\n" + "=" * 60)
    print("测试 PaddleOCR")
    print("=" * 60)
    
    try:
        from paddleocr import PaddleOCR
        import paddle
        
        # 检查 PaddlePaddle 版本
        print(f"✅ PaddlePaddle 版本: {paddle.__version__}")
        
        # 检查 GPU 支持
        gpu_count = paddle.device.cuda.device_count()
        if gpu_count > 0:
            print(f"✅ GPU 支持: 检测到 {gpu_count} 个 GPU")
        else:
            print("⚠️  GPU 支持: 未检测到 GPU，将使用 CPU 模式")
        
        # 初始化 OCR（不下载模型，仅测试导入）
        print("✅ PaddleOCR 导入成功")
        print("⚠️  首次运行时会自动下载模型（约 15-25MB）")
        
        return True
        
    except Exception as e:
        print(f"❌ PaddleOCR 测试失败: {e}")
        print("\n安装方法:")
        print("  CPU 版本: uv pip install paddleocr paddlepaddle")
        print("  GPU 版本: uv pip install paddleocr paddlepaddle-gpu")
        return False


def test_pillow():
    """测试 Pillow"""
    print("\n" + "=" * 60)
    print("测试 Pillow（图像处理库）")
    print("=" * 60)
    
    try:
        from PIL import Image
        import PIL
        
        print(f"✅ Pillow 版本: {PIL.__version__}")
        return True
        
    except Exception as e:
        print(f"❌ Pillow 测试失败: {e}")
        print("\n安装方法:")
        print("  uv pip install Pillow")
        return False


def check_memory():
    """检查系统内存"""
    print("\n" + "=" * 60)
    print("系统资源检查")
    print("=" * 60)
    
    try:
        import psutil
        
        # 获取内存信息
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024**3)
        available_gb = mem.available / (1024**3)
        
        print(f"总内存: {total_gb:.2f} GB")
        print(f"可用内存: {available_gb:.2f} GB")
        
        # 推荐 OCR 引擎
        if available_gb >= 4:
            print("✅ 推荐使用: PaddleOCR（高质量）")
        else:
            print("⚠️  推荐使用: Tesseract（轻量级）")
        
    except ImportError:
        print("⚠️  psutil 未安装，无法检查内存")
        print("   安装: uv pip install psutil")
    except Exception as e:
        print(f"⚠️  内存检查失败: {e}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("启元 AI 平台 - OCR 引擎测试")
    print("=" * 60)
    
    results = {
        "Pillow": test_pillow(),
        "Tesseract": test_tesseract(),
        "PaddleOCR": test_paddleocr(),
    }
    
    check_memory()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name:15} {status}")
    
    # 建议
    print("\n" + "=" * 60)
    print("配置建议")
    print("=" * 60)
    
    if results["Tesseract"] and results["PaddleOCR"]:
        print("✅ 所有 OCR 引擎已安装，建议配置:")
        print("   - OCR 引擎: auto（自动选择）")
        print("   - 识别语言: ['ch', 'en']")
    elif results["PaddleOCR"]:
        print("✅ PaddleOCR 已安装，建议配置:")
        print("   - OCR 引擎: paddleocr")
        print("   - 识别语言: ['ch', 'en']")
    elif results["Tesseract"]:
        print("✅ Tesseract 已安装，建议配置:")
        print("   - OCR 引擎: tesseract")
        print("   - 识别语言: ['ch', 'en']")
    else:
        print("❌ 未检测到可用的 OCR 引擎，请先安装:")
        print("   1. 安装 Tesseract（轻量级）")
        print("   2. 或安装 PaddleOCR（高质量）")
        print("   3. 参考 INSTALL_OCR.md 获取详细安装步骤")
    
    print("\n" + "=" * 60)
    
    # 返回状态码
    if all(results.values()):
        print("✅ 所有测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查安装")
        return 1


if __name__ == "__main__":
    sys.exit(main())
