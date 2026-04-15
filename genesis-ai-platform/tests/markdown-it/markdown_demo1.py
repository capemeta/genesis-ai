import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from rag.utils.token_utils import count_tokens

# 获取数据路径
workspace_root = project_root.parent
data_path = workspace_root / "genesis-ai-platform/tests/data" / "数据库设计_v2.md"

# 输出文件路径
output_dir = current_dir / "output"
output_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = output_dir / f"docling_markdown_demo1_详细解析_{timestamp}.txt"

print(f"Current dir: {current_dir}")
print(f"Project root: {project_root}")
print(f"Workspace root: {workspace_root}")
print(f"Data path: {data_path}")
print(f"File exists: {data_path.exists()}")
print(f"Output file: {output_file}")
print("=" * 100)


def analyze_markdown_with_docling(file_path: str):
    """
    直接使用 docling 解析 Markdown 文件
    
    Args:
        file_path: Markdown 文件路径
        
    Returns:
        解析结果字典
    """
    try:
        # 配置：禁用 AI 模型（Markdown 不需要）
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False  # 禁用 OCR
        pipeline_options.do_table_structure = False  # 禁用表格结构识别
        
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        print(f"\n🔄 使用 docling 解析文件...")
        result = converter.convert(file_path)
        doc = result.document
        
        print(f"\n📊 Docling 解析结果:")
        print(f"   - texts: {len(doc.texts)} 个")
        print(f"   - groups: {len(doc.groups)} 个")
        print(f"   - tables: {len(doc.tables)} 个")
        
        # 导出为 Markdown 查看 docling 的理解
        try:
            markdown_export = doc.export_to_markdown()
            print(f"\n📝 Docling 导出的 Markdown 预览（前 500 字符）:")
            print(markdown_export[:500])
        except Exception as e:
            print(f"⚠️ 无法导出 Markdown: {e}")
            markdown_export = None
        
        # 提取所有元素的详细信息
        texts_info = []
        for i, text_item in enumerate(doc.texts, 1):
            item_text = text_item.text.strip()
            if item_text:
                texts_info.append({
                    "index": i,
                    "text": item_text,
                    "token_count": count_tokens(item_text),
                    "char_count": len(item_text),
                    "label": str(text_item.label) if hasattr(text_item, 'label') else "unknown"
                })
        
        groups_info = []
        for i, group in enumerate(doc.groups, 1):
            groups_info.append({
                "index": i,
                "group": str(group),
                "type": type(group).__name__
            })
        
        tables_info = []
        for i, table in enumerate(doc.tables, 1):
            # 提取表格数据
            table_data = table.data if hasattr(table, 'data') else None
            
            # 转换为 Markdown 表格格式
            markdown_table = ""
            csv_table = ""
            
            if table_data and hasattr(table_data, 'grid'):
                grid = table_data.grid
                num_rows = table_data.num_rows
                num_cols = table_data.num_cols
                
                # 构建 Markdown 表格
                if num_rows > 0 and num_cols > 0:
                    # 表头
                    header_row = []
                    for col_idx in range(num_cols):
                        if col_idx < len(grid[0]):
                            cell = grid[0][col_idx]
                            cell_text = cell.text if hasattr(cell, 'text') else str(cell)
                            header_row.append(cell_text.replace('|', '\\|'))  # 转义管道符
                        else:
                            header_row.append("")
                    markdown_table += "| " + " | ".join(header_row) + " |\n"
                    csv_table += ",".join(f'"{cell}"' for cell in header_row) + "\n"
                    
                    # 分隔线
                    markdown_table += "| " + " | ".join(["---"] * num_cols) + " |\n"
                    
                    # 数据行
                    for row_idx in range(1, num_rows):
                        if row_idx < len(grid):
                            row_data = []
                            for col_idx in range(num_cols):
                                if col_idx < len(grid[row_idx]):
                                    cell = grid[row_idx][col_idx]
                                    cell_text = cell.text if hasattr(cell, 'text') else str(cell)
                                    row_data.append(cell_text.replace('|', '\\|'))
                                else:
                                    row_data.append("")
                            markdown_table += "| " + " | ".join(row_data) + " |\n"
                            csv_table += ",".join(f'"{cell}"' for cell in row_data) + "\n"
            
            # 提取表格的标签和位置信息
            label = str(table.label) if hasattr(table, 'label') else "unknown"
            parent = str(table.parent) if hasattr(table, 'parent') else "unknown"
            
            tables_info.append({
                "index": i,
                "markdown_table": markdown_table,
                "csv_table": csv_table,
                "num_rows": table_data.num_rows if table_data else 0,
                "num_cols": table_data.num_cols if table_data else 0,
                "label": label,
                "parent": parent,
                "raw_data": str(table)[:500] + "..." if len(str(table)) > 500 else str(table),
                "type": type(table).__name__
            })
        
        return {
            "texts": texts_info,
            "groups": groups_info,
            "tables": tables_info,
            "markdown_export": markdown_export,
            "success": True,
            "total_texts": len(texts_info),
            "total_groups": len(groups_info),
            "total_tables": len(tables_info)
        }
        
    except Exception as e:
        print(f"⚠️ Docling 处理失败: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "texts": [],
            "groups": [],
            "tables": [],
            "markdown_export": None,
            "success": False,
            "error": str(e)
        }


# 执行分析
print("\n" + "=" * 100)
print("Docling Markdown 详细解析")
print("=" * 100)

result = analyze_markdown_with_docling(str(data_path))

# 写入详细输出文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"Docling Markdown 详细解析结果\n")
    f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"源文件: {data_path}\n")
    f.write(f"说明: 直接使用 docling 解析 Markdown 文件，提取 texts, groups, tables 元素\n")
    f.write("=" * 100 + "\n\n")
    
    f.write(f"解析状态: {'✅ 成功' if result['success'] else '❌ 失败'}\n")
    
    if not result['success']:
        f.write(f"错误信息: {result.get('error', 'Unknown')}\n")
    else:
        f.write(f"总 texts 元素: {result['total_texts']}\n")
        f.write(f"总 groups 元素: {result['total_groups']}\n")
        f.write(f"总 tables 元素: {result['total_tables']}\n")
    
    f.write("\n")
    
    # 输出 Docling 导出的 Markdown
    if result.get('markdown_export'):
        f.write("=" * 100 + "\n")
        f.write("� Docling 导出的 Markdown（完整）\n")
        f.write("=" * 100 + "\n\n")
        f.write(result['markdown_export'])
        f.write("\n\n")
    
    # 输出 texts 元素
    if result['texts']:
        f.write("=" * 100 + "\n")
        f.write("📝 Texts 元素详情\n")
        f.write("=" * 100 + "\n\n")
        
        total_tokens = sum(t['token_count'] for t in result['texts'])
        total_chars = sum(t['char_count'] for t in result['texts'])
        
        f.write(f"统计信息:\n")
        f.write(f"  - 总数: {len(result['texts'])} 个\n")
        f.write(f"  - 总 Token 数: {total_tokens}\n")
        f.write(f"  - 总字符数: {total_chars}\n")
        f.write(f"  - 平均 Token 数: {total_tokens / len(result['texts']):.1f}\n")
        f.write(f"  - 平均字符数: {total_chars / len(result['texts']):.1f}\n")
        f.write("\n")
        
        for text_info in result['texts']:
            f.write(f"[Text {text_info['index']}/{len(result['texts'])}]\n")
            f.write(f"Label: {text_info['label']}\n")
            f.write(f"Token 数: {text_info['token_count']}\n")
            f.write(f"字符数: {text_info['char_count']}\n")
            f.write("-" * 100 + "\n")
            f.write(text_info['text'])
            f.write("\n" + "-" * 100 + "\n\n")
    
    # 输出 groups 元素
    if result['groups']:
        f.write("=" * 100 + "\n")
        f.write("📦 Groups 元素详情\n")
        f.write("=" * 100 + "\n\n")
        
        f.write(f"总数: {len(result['groups'])} 个\n\n")
        
        for group_info in result['groups']:
            f.write(f"[Group {group_info['index']}/{len(result['groups'])}]\n")
            f.write(f"类型: {group_info['type']}\n")
            f.write("-" * 100 + "\n")
            f.write(group_info['group'])
            f.write("\n" + "-" * 100 + "\n\n")
    
    # 输出 tables 元素
    if result['tables']:
        f.write("=" * 100 + "\n")
        f.write("📊 Tables 元素详情\n")
        f.write("=" * 100 + "\n\n")
        
        f.write(f"总数: {len(result['tables'])} 个\n")
        f.write(f"⚠️ 注意: 原始 Markdown 文件中只有 3 个表格，但 Docling 检测到 {len(result['tables'])} 个\n")
        f.write(f"   这可能是因为 Docling 将某些列表或结构化内容也识别为表格\n\n")
        
        for table_info in result['tables']:
            f.write(f"[Table {table_info['index']}/{len(result['tables'])}]\n")
            f.write(f"类型: {table_info['type']}\n")
            f.write(f"Label: {table_info['label']}\n")
            f.write(f"Parent: {table_info['parent']}\n")
            f.write(f"行数: {table_info['num_rows']}\n")
            f.write(f"列数: {table_info['num_cols']}\n")
            f.write("-" * 100 + "\n")
            
            # 输出 Markdown 格式的表格
            if table_info['markdown_table']:
                f.write("Markdown 格式:\n")
                f.write(table_info['markdown_table'])
                f.write("\n")
            else:
                f.write("⚠️ 无法转换为 Markdown 表格（可能是空表或格式异常）\n\n")
            
            # 输出 CSV 格式
            if table_info.get('csv_table'):
                f.write("CSV 格式:\n")
                f.write(table_info['csv_table'])
                f.write("\n")
            
            # 输出原始数据（折叠显示）
            f.write("\n原始数据结构（截断）:\n")
            f.write(table_info['raw_data'])
            f.write("\n" + "-" * 100 + "\n\n")

print("\n" + "=" * 100)
print(f"✅ 详细解析完成！")
print(f"   输出文件: {output_file}")
print("=" * 100)
print("\n📊 解析说明:")
print("1. 直接使用 docling 解析 Markdown 文件")
print("2. 提取所有 texts, groups, tables 元素")
print("3. 详细输出每个元素的内容和统计信息")
print("4. 禁用了 OCR 和表格结构识别（Markdown 不需要）")
