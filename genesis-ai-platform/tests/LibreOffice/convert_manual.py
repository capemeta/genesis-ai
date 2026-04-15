"""
LibreOffice DOCX 转 PDF 测试工具

功能：
1. 转换 DOCX 文件到 PDF
2. 支持多个测试案例
3. 显示详细的转换统计信息

使用方法：
    python convert_manual.py
"""

import os
import time
import subprocess
from pathlib import Path
from typing import Optional


# ============ 配置区域 ============

# LibreOffice 路径
LIBREOFFICE_PATH = r"D:\Software\system\LibreOffice\program\soffice.exe"

# 测试案例配置
TEST_CASES = [
    {
        "name": "云视频客服操作手册",
        "docx_path": r"C:\Users\csl2021\Downloads\云视频视频客服（客服端）操作手册V1.0.docx",
        "output_dir": None,  # None 表示输出到源文件同目录
    },
    # 可以添加更多测试案例
    # {
    #     "name": "测试文档2",
    #     "docx_path": r"C:\path\to\document2.docx",
    #     "output_dir": r"C:\output\folder",
    # },
]

# ===================================


class LibreOfficeConverter:
    """LibreOffice DOCX 转 PDF 转换器"""
    
    def __init__(self, libreoffice_path: str):
        """
        初始化转换器
        
        Args:
            libreoffice_path: LibreOffice 可执行文件路径
        """
        self.libreoffice_path = libreoffice_path
        
        if not os.path.exists(self.libreoffice_path):
            raise FileNotFoundError(
                f"LibreOffice 未找到: {self.libreoffice_path}\n"
                "请检查路径或安装 LibreOffice"
            )
    
    def get_version(self) -> str:
        """获取 LibreOffice 版本"""
        try:
            result = subprocess.run(
                [self.libreoffice_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            return result.stdout.strip()
        except Exception as e:
            return f"无法获取版本: {e}"
    
    def convert_to_pdf(
        self,
        docx_path: str,
        output_dir: Optional[str] = None,
        timeout: int = 120
    ) -> str:
        """
        转换 DOCX 到 PDF
        
        Args:
            docx_path: DOCX 文件路径
            output_dir: 输出目录（默认与源文件同目录）
            timeout: 超时时间（秒）
            
        Returns:
            PDF 文件路径
        """
        # 验证输入文件
        docx_path = Path(docx_path).resolve()
        if not docx_path.exists():
            raise FileNotFoundError(f"DOCX 文件不存在: {docx_path}")
        
        # 确定输出目录
        if output_dir is None:
            output_dir = docx_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建命令
        cmd = [
            self.libreoffice_path,
            '--headless',              # 无界面模式
            '--convert-to', 'pdf',     # 转换为 PDF
            '--outdir', str(output_dir),  # 输出目录
            str(docx_path)             # 输入文件
        ]
        
        # 执行转换
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            
            # 计算输出文件路径
            pdf_path = output_dir / f"{docx_path.stem}.pdf"
            
            if not pdf_path.exists():
                raise RuntimeError(
                    f"PDF 文件未生成: {pdf_path}\n"
                    f"LibreOffice 输出: {result.stdout}\n"
                    f"错误信息: {result.stderr}"
                )
            
            return str(pdf_path)
            
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"转换超时（{timeout}秒）")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"转换失败\n"
                f"返回码: {e.returncode}\n"
                f"输出: {e.stdout}\n"
                f"错误: {e.stderr}"
            )


def run_test_case(converter: LibreOfficeConverter, test_case: dict, case_num: int, total: int):
    """运行单个测试案例"""
    
    print("\n" + "=" * 80)
    print(f"测试案例 {case_num}/{total}: {test_case['name']}")
    print("=" * 80)
    
    docx_path = test_case['docx_path']
    output_dir = test_case.get('output_dir')
    
    # 1. 检查文件
    print(f"\n1. 检查输入文件...")
    if not os.path.exists(docx_path):
        print(f"   ❌ 文件不存在: {docx_path}")
        return False
    
    file_size = os.path.getsize(docx_path)
    print(f"   ✅ 文件存在")
    print(f"   路径: {docx_path}")
    print(f"   大小: {file_size:,} 字节 ({file_size / 1024:.2f} KB)")
    
    # 2. 执行转换
    print(f"\n2. 开始转换 DOCX → PDF...")
    print(f"   这可能需要几秒钟，请稍候...")
    
    try:
        start_time = time.time()
        pdf_path = converter.convert_to_pdf(docx_path, output_dir)
        duration = time.time() - start_time
        
        print(f"   ✅ 转换成功!")
        
    except Exception as e:
        print(f"   ❌ 转换失败: {e}")
        return False
    
    # 3. 验证输出
    print(f"\n3. 验证输出文件...")
    if not os.path.exists(pdf_path):
        print(f"   ❌ PDF 文件未生成: {pdf_path}")
        return False
    
    pdf_size = os.path.getsize(pdf_path)
    print(f"   ✅ PDF 文件已生成")
    print(f"   路径: {pdf_path}")
    print(f"   大小: {pdf_size:,} 字节 ({pdf_size / 1024:.2f} KB)")
    
    # 4. 统计信息
    print(f"\n4. 转换统计:")
    print(f"   转换耗时: {duration:.2f} 秒")
    print(f"   DOCX 大小: {file_size:,} 字节")
    print(f"   PDF 大小: {pdf_size:,} 字节")
    print(f"   大小比例: {pdf_size / file_size:.2f}x")
    print(f"   转换速度: {file_size / duration / 1024:.2f} KB/秒")
    
    # 5. 打开 PDF
    print(f"\n5. 打开 PDF 文件...")
    try:
        os.startfile(pdf_path)
        print(f"   ✅ 已在默认 PDF 阅读器中打开")
        print(f"\n   📋 请检查以下内容:")
        print(f"      - 页码是否正确递增（不是所有页都显示 2）")
        print(f"      - 版本记录和目录是否在正确的页面")
        print(f"      - 页眉页脚是否正确显示")
        print(f"      - 图片和表格是否正常")
        print(f"      - 分页位置是否合理")
    except Exception as e:
        print(f"   ⚠️  无法自动打开，请手动打开: {pdf_path}")
    
    return True


def main():
    """主函数 - 运行所有测试案例"""
    
    print("=" * 80)
    print("LibreOffice DOCX 转 PDF 测试工具")
    print("=" * 80)
    
    # 1. 初始化转换器
    print(f"\n📦 初始化 LibreOffice 转换器...")
    try:
        converter = LibreOfficeConverter(LIBREOFFICE_PATH)
        print(f"   ✅ 初始化成功")
        print(f"   路径: {converter.libreoffice_path}")
        
        version = converter.get_version()
        print(f"   版本: {version}")
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        return
    
    # 2. 运行测试案例
    total_cases = len(TEST_CASES)
    success_count = 0
    
    for i, test_case in enumerate(TEST_CASES, 1):
        success = run_test_case(converter, test_case, i, total_cases)
        if success:
            success_count += 1
        
        # 案例之间暂停
        if i < total_cases:
            print("\n" + "-" * 80)
            input("按 Enter 继续下一个测试案例...")
    
    # 3. 总结
    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)
    print(f"\n总计: {total_cases} 个测试案例")
    print(f"成功: {success_count} 个")
    print(f"失败: {total_cases - success_count} 个")
    
    if success_count == total_cases:
        print("\n🎉 所有测试案例都成功!")
    else:
        print(f"\n⚠️  有 {total_cases - success_count} 个测试案例失败")


if __name__ == "__main__":
    main()
