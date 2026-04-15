import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from rag.utils.token_utils import count_tokens

# 获取数据路径（默认使用完整元素 demo，含 Front matter、定义列表等；可改为 数据库设计_v2.md）
data_path = project_root / "tests" / "data" / "markdown_elements_demo.md"
# data_path = project_root / "tests" / "data" / "数据库设计_v2.md"

# 输出文件路径
output_dir = current_dir / "output"
output_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = output_dir / f"markdown_it_demo2_详细解析_{timestamp}.txt"

print(f"Current dir: {current_dir}")
print(f"Project root: {project_root}")
print(f"Data path: {data_path}")
print(f"File exists: {data_path.exists()}")
print(f"Output file: {output_file}")
print("=" * 100)


def create_markdown_parser():
    """
    创建配置完整的 markdown-it 解析器
    
    Returns:
        配置好的 MarkdownIt 实例
    """
    md = (
        MarkdownIt("gfm-like", {"html": True})  # GFM 风格 + 允许 HTML
        .use(front_matter_plugin)  # 前置元数据
        .use(footnote_plugin)      # 脚注
        .use(deflist_plugin)       # 定义列表
        .use(tasklists_plugin)     # 任务列表
        .use(dollarmath_plugin)    # 数学公式
    )
    return md


def extract_code_blocks(tokens: List) -> List[Dict[str, Any]]:
    """提取代码块"""
    code_blocks = []
    for i, token in enumerate(tokens):
        if token.type == "fence" or token.type == "code_block":
            code_blocks.append({
                "index": len(code_blocks) + 1,
                "type": token.type,
                "language": token.info if token.type == "fence" else "plain",
                "content": token.content,
                "line_start": token.map[0] if token.map else None,
                "line_end": token.map[1] if token.map else None,
                "token_count": count_tokens(token.content),
                "line_count": len(token.content.splitlines())
            })
    return code_blocks


def extract_tables(tokens: List) -> List[Dict[str, Any]]:
    """提取表格"""
    tables = []
    i = 0
    while i < len(tokens):
        if tokens[i].type == "table_open":
            # 找到对应的 table_close
            table_tokens = []
            depth = 1
            j = i + 1
            while j < len(tokens) and depth > 0:
                if tokens[j].type == "table_open":
                    depth += 1
                elif tokens[j].type == "table_close":
                    depth -= 1
                table_tokens.append(tokens[j])
                j += 1
            
            # 解析表格结构
            rows = []
            current_row = []
            in_header = False
            
            for token in table_tokens:
                if token.type == "thead_open":
                    in_header = True
                elif token.type == "thead_close":
                    in_header = False
                elif token.type == "tr_open":
                    current_row = []
                elif token.type == "tr_close":
                    if current_row:
                        rows.append({
                            "cells": current_row,
                            "is_header": in_header
                        })
                elif token.type == "inline":
                    current_row.append(token.content)
            
            # 构建 Markdown 表格
            markdown_table = ""
            if rows:
                # 表头
                if rows[0]["is_header"]:
                    header = rows[0]["cells"]
                    markdown_table += "| " + " | ".join(header) + " |\n"
                    markdown_table += "| " + " | ".join(["---"] * len(header)) + " |\n"
                    data_rows = rows[1:]
                else:
                    data_rows = rows
                
                # 数据行
                for row in data_rows:
                    markdown_table += "| " + " | ".join(row["cells"]) + " |\n"
            
            tables.append({
                "index": len(tables) + 1,
                "num_rows": len(rows),
                "num_cols": len(rows[0]["cells"]) if rows else 0,
                "markdown": markdown_table,
                "line_start": tokens[i].map[0] if tokens[i].map else None,
                "line_end": tokens[j-1].map[1] if j > 0 and tokens[j-1].map else None
            })
            
            i = j
        else:
            i += 1
    
    return tables


def extract_lists(tokens: List) -> List[Dict[str, Any]]:
    """提取列表"""
    lists = []
    i = 0
    while i < len(tokens):
        if tokens[i].type in ["bullet_list_open", "ordered_list_open"]:
            list_type = "unordered" if tokens[i].type == "bullet_list_open" else "ordered"
            
            # 找到对应的 list_close
            list_tokens = []
            depth = 1
            j = i + 1
            while j < len(tokens) and depth > 0:
                if tokens[j].type in ["bullet_list_open", "ordered_list_open"]:
                    depth += 1
                elif tokens[j].type in ["bullet_list_close", "ordered_list_close"]:
                    depth -= 1
                list_tokens.append(tokens[j])
                j += 1
            
            # 提取列表项
            items = []
            for token in list_tokens:
                if token.type == "inline":
                    items.append(token.content)
            
            lists.append({
                "index": len(lists) + 1,
                "type": list_type,
                "num_items": len(items),
                "items": items,
                "line_start": tokens[i].map[0] if tokens[i].map else None,
                "line_end": tokens[j-1].map[1] if j > 0 and tokens[j-1].map else None
            })
            
            i = j
        else:
            i += 1
    
    return lists


def extract_math(tokens: List) -> List[Dict[str, Any]]:
    """提取数学公式"""
    math_blocks = []
    for token in tokens:
        if token.type in ["math_inline", "math_block", "math_block_eqno"]:
            math_blocks.append({
                "index": len(math_blocks) + 1,
                "type": "inline" if token.type == "math_inline" else "block",
                "content": token.content,
                "line_start": token.map[0] if token.map else None,
                "line_end": token.map[1] if token.map else None
            })
    return math_blocks


def extract_blockquotes(tokens: List) -> List[Dict[str, Any]]:
    """提取引用块"""
    blockquotes = []
    i = 0
    while i < len(tokens):
        if tokens[i].type == "blockquote_open":
            # 找到对应的 blockquote_close
            quote_tokens = []
            depth = 1
            j = i + 1
            while j < len(tokens) and depth > 0:
                if tokens[j].type == "blockquote_open":
                    depth += 1
                elif tokens[j].type == "blockquote_close":
                    depth -= 1
                quote_tokens.append(tokens[j])
                j += 1
            
            # 提取引用内容
            content_parts = []
            for token in quote_tokens:
                if token.type == "inline":
                    content_parts.append(token.content)
            
            content = "\n".join(content_parts)
            
            blockquotes.append({
                "index": len(blockquotes) + 1,
                "content": content,
                "token_count": count_tokens(content),
                "line_start": tokens[i].map[0] if tokens[i].map else None,
                "line_end": tokens[j-1].map[1] if j > 0 and tokens[j-1].map else None
            })
            
            i = j
        else:
            i += 1
    
    return blockquotes


def extract_html_blocks(tokens: List) -> List[Dict[str, Any]]:
    """提取 HTML 块"""
    html_blocks = []
    for token in tokens:
        if token.type == "html_block":
            html_blocks.append({
                "index": len(html_blocks) + 1,
                "content": token.content,
                "line_start": token.map[0] if token.map else None,
                "line_end": token.map[1] if token.map else None
            })
    return html_blocks


def extract_front_matter(tokens: List) -> List[Dict[str, Any]]:
    """提取 Front matter（YAML 前置元数据，需 front_matter 插件）"""
    front_matters = []
    for token in tokens:
        if token.type == "front_matter":
            front_matters.append({
                "index": len(front_matters) + 1,
                "content": token.content,
                "line_start": token.map[0] if token.map else None,
                "line_end": token.map[1] if token.map else None,
                "token_count": count_tokens(token.content),
            })
    return front_matters


def extract_def_lists(tokens: List) -> List[Dict[str, Any]]:
    """提取定义列表（需 deflist 插件，dl_open/dl_close + dt/dd）"""
    def_lists = []
    i = 0
    while i < len(tokens):
        if tokens[i].type == "dl_open":
            list_tokens = []
            depth = 1
            j = i + 1
            while j < len(tokens) and depth > 0:
                if tokens[j].type == "dl_open":
                    depth += 1
                elif tokens[j].type == "dl_close":
                    depth -= 1
                list_tokens.append(tokens[j])
                j += 1
            content_parts = []
            for token in list_tokens:
                if token.type == "inline":
                    content_parts.append(token.content)
            content = "\n".join(content_parts) if content_parts else ""
            def_lists.append({
                "index": len(def_lists) + 1,
                "content": content,
                "line_start": tokens[i].map[0] if tokens[i].map else None,
                "line_end": tokens[j - 1].map[1] if j > 0 and tokens[j - 1].map else None,
                "token_count": count_tokens(content),
            })
            i = j
        else:
            i += 1
    return def_lists


def extract_hr(tokens: List) -> List[Dict[str, Any]]:
    """提取分隔线（hr）"""
    hrs = []
    for token in tokens:
        if token.type == "hr":
            hrs.append({
                "index": len(hrs) + 1,
                "line_start": token.map[0] if token.map else None,
                "line_end": token.map[1] if token.map else None,
            })
    return hrs


def analyze_markdown_with_markdown_it(file_path: str):
    """
    使用 markdown-it-py 解析 Markdown 文件
    
    Args:
        file_path: Markdown 文件路径
        
    Returns:
        解析结果字典
    """
    try:
        # 读取文件
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        
        # 创建解析器
        md = create_markdown_parser()
        
        print(f"\n🔄 使用 markdown-it-py 解析文件...")
        
        # 解析为 tokens
        tokens = md.parse(text)
        
        print(f"\n📊 解析结果:")
        print(f"   - 总 tokens: {len(tokens)} 个")
        
        # 提取各类元素
        code_blocks = extract_code_blocks(tokens)
        tables = extract_tables(tokens)
        lists = extract_lists(tokens)
        math_blocks = extract_math(tokens)
        blockquotes = extract_blockquotes(tokens)
        html_blocks = extract_html_blocks(tokens)
        front_matters = extract_front_matter(tokens)
        def_lists = extract_def_lists(tokens)
        hrs = extract_hr(tokens)
        
        print(f"   - 代码块: {len(code_blocks)} 个")
        print(f"   - 表格: {len(tables)} 个")
        print(f"   - 列表: {len(lists)} 个")
        print(f"   - 数学公式: {len(math_blocks)} 个")
        print(f"   - 引用块: {len(blockquotes)} 个")
        print(f"   - HTML 块: {len(html_blocks)} 个")
        print(f"   - Front matter: {len(front_matters)} 个")
        print(f"   - 定义列表: {len(def_lists)} 个")
        print(f"   - 分隔线: {len(hrs)} 个")
        
        # 渲染为 HTML
        html_output = md.render(text)
        
        return {
            "tokens": tokens,
            "code_blocks": code_blocks,
            "tables": tables,
            "lists": lists,
            "math_blocks": math_blocks,
            "blockquotes": blockquotes,
            "html_blocks": html_blocks,
            "front_matters": front_matters,
            "def_lists": def_lists,
            "hrs": hrs,
            "html_output": html_output,
            "success": True
        }
        
    except Exception as e:
        print(f"⚠️ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "error": str(e)
        }


def reconstruct_markdown_from_tokens(tokens: List) -> str:
    """
    从 tokens 重新构建 Markdown 文本
    
    Args:
        tokens: markdown-it 解析的 token 列表
        
    Returns:
        重新构建的 Markdown 文本
    """
    output = []
    in_table = False
    in_thead = False
    table_col_count = 0
    list_depth = 0  # 列表嵌套深度
    ordered_list_counters = []  # 有序列表计数器栈
    in_list_item = False  # 是否在列表项内部
    
    for i, token in enumerate(tokens):
        # 标题
        if token.type == "heading_open":
            level = int(token.tag[1])  # h1 -> 1, h2 -> 2
            output.append("#" * level + " ")
        elif token.type == "heading_close":
            output.append("\n\n")
        
        # 段落
        elif token.type == "paragraph_open":
            pass  # 段落开始不需要特殊处理
        elif token.type == "paragraph_close":
            # 如果不在列表中，添加双换行
            # 在列表中，段落结束不添加额外换行（由 list_item_close 处理）
            if list_depth == 0:
                output.append("\n\n")
        
        # 代码块
        elif token.type == "fence":
            lang = token.info or ""
            output.append(f"```{lang}\n{token.content}```\n\n")
        elif token.type == "code_block":
            output.append(f"```\n{token.content}```\n\n")
        
        # 表格
        elif token.type == "table_open":
            in_table = True
            table_col_count = 0
        elif token.type == "table_close":
            in_table = False
            output.append("\n")
        elif token.type == "thead_open":
            in_thead = True
        elif token.type == "thead_close":
            in_thead = False
            # 添加分隔线
            if table_col_count > 0:
                output.append("| " + " | ".join(["---"] * table_col_count) + " |\n")
        elif token.type == "tbody_open":
            pass
        elif token.type == "tbody_close":
            pass
        elif token.type == "tr_open":
            output.append("| ")
        elif token.type == "tr_close":
            # 移除最后的 " | "，添加 " |" 和换行
            if output and output[-1].endswith(" | "):
                output[-1] = output[-1][:-3] + " |\n"
            else:
                output.append("|\n")
        elif token.type == "th_open":
            pass
        elif token.type == "th_close":
            output.append(" | ")
            if in_thead:
                table_col_count += 1
        elif token.type == "td_open":
            pass
        elif token.type == "td_close":
            output.append(" | ")
        
        # 列表
        elif token.type == "bullet_list_open":
            list_depth += 1
        elif token.type == "bullet_list_close":
            list_depth -= 1
            if list_depth == 0:
                output.append("\n")
        elif token.type == "ordered_list_open":
            list_depth += 1
            ordered_list_counters.append(1)
        elif token.type == "ordered_list_close":
            list_depth -= 1
            if ordered_list_counters:
                ordered_list_counters.pop()
            if list_depth == 0:
                output.append("\n")
        elif token.type == "list_item_open":
            in_list_item = True
            # 添加缩进
            indent = "  " * (list_depth - 1)
            output.append(indent)
            
            # 判断列表类型
            if token.markup in ["-", "*", "+"]:
                output.append("- ")
            else:
                # 有序列表
                if ordered_list_counters:
                    counter = ordered_list_counters[-1]
                    output.append(f"{counter}. ")
                    ordered_list_counters[-1] += 1
                else:
                    output.append("1. ")
        elif token.type == "list_item_close":
            in_list_item = False
            output.append("\n")
        
        # 引用块
        elif token.type == "blockquote_open":
            output.append("> ")
        elif token.type == "blockquote_close":
            output.append("\n\n")
        
        # 数学公式
        elif token.type == "math_inline":
            output.append(f"${token.content}$")
        elif token.type == "math_block" or token.type == "math_block_eqno":
            output.append(f"$$\n{token.content}$$\n\n")
        
        # HTML 块
        elif token.type == "html_block":
            output.append(token.content)
            if not token.content.endswith("\n"):
                output.append("\n")
        
        # Front matter（需 front_matter 插件）
        elif token.type == "front_matter":
            output.append("---\n")
            output.append(token.content)
            if not token.content.endswith("\n"):
                output.append("\n")
            output.append("---\n\n")
        
        # 分隔线
        elif token.type == "hr":
            output.append("---\n\n")
        
        # 行内内容
        elif token.type == "inline":
            output.append(token.content)
        
        # 软换行和硬换行
        elif token.type == "softbreak":
            # 在列表项内部，软换行只是换行，不添加缩进
            # 因为这是同一个列表项的延续
            output.append("\n")
        elif token.type == "hardbreak":
            output.append("  \n")
        
        # 代码（行内）
        elif token.type == "code_inline":
            output.append(f"`{token.content}`")
        
        # 强调
        elif token.type == "em_open":
            output.append("*")
        elif token.type == "em_close":
            output.append("*")
        elif token.type == "strong_open":
            output.append("**")
        elif token.type == "strong_close":
            output.append("**")
        
        # 删除线
        elif token.type == "s_open":
            output.append("~~")
        elif token.type == "s_close":
            output.append("~~")
        
        # 链接
        elif token.type == "link_open":
            output.append("[")
        elif token.type == "link_close":
            # 从前一个 token 的 attrs 获取 href
            href = ""
            for j in range(i-1, max(0, i-10), -1):
                if tokens[j].type == "link_open":
                    for attr in tokens[j].attrs or []:
                        if attr[0] == "href":
                            href = attr[1]
                            break
                    break
            output.append(f"]({href})")
        
        # 图片
        elif token.type == "image":
            alt = token.content
            src = ""
            title = ""
            for attr in token.attrs or []:
                if attr[0] == "src":
                    src = attr[1]
                elif attr[0] == "title":
                    title = attr[1]
            if title:
                output.append(f'![{alt}]({src} "{title}")')
            else:
                output.append(f"![{alt}]({src})")
    
    return "".join(output)


# 执行分析
print("\n" + "=" * 100)
print("markdown-it-py 完整元素解析示例")
print("=" * 100)

result = analyze_markdown_with_markdown_it(str(data_path))

# 重新构建 Markdown - 使用 markdown-it 渲染为 HTML 再转回 Markdown
if result['success']:
    # 读取原始文本
    with open(data_path, "r", encoding="utf-8") as f:
        original_text = f.read()
    
    # 创建解析器
    md = create_markdown_parser()
    
    # 方法：使用 markdown-it 的 renderer 自定义输出为 Markdown
    # 这里我们使用一个技巧：利用已提取的元素重新组装
    
    reconstructed_parts = []
    
    # 按行号排序所有元素（先得到 lines，以便代码块用原文保留缩进）
    lines = original_text.split('\n')
    all_elements = []
    
    # 添加代码块：使用原始文件对应行范围的内容，保留代码块内原有缩进（不依赖解析后的 token.content）
    for block in result['code_blocks']:
        if block['line_start'] is not None and block['line_end'] is not None:
            start, end = block['line_start'], block['line_end']
            if start < len(lines) and end <= len(lines):
                original_block_content = '\n'.join(lines[start:end])
            else:
                original_block_content = f"```{block['language']}\n{block['content']}```"
            all_elements.append({
                'type': 'code',
                'start': start,
                'end': end,
                'content': original_block_content
            })
    
    # 添加表格
    for table in result['tables']:
        if table['line_start'] is not None and table['line_end'] is not None:
            all_elements.append({
                'type': 'table',
                'start': table['line_start'],
                'end': table['line_end'],
                'content': table['markdown']
            })
    
    # 添加数学公式
    for math in result['math_blocks']:
        if math['line_start'] is not None and math['line_end'] is not None and math['type'] == 'block':
            all_elements.append({
                'type': 'math',
                'start': math['line_start'],
                'end': math['line_end'],
                'content': f"$$\n{math['content']}$$"
            })
    
    # 添加 HTML 块
    for html in result['html_blocks']:
        if html['line_start'] is not None and html['line_end'] is not None:
            all_elements.append({
                'type': 'html',
                'start': html['line_start'],
                'end': html['line_end'],
                'content': html['content']
            })
    
    # 添加 Front matter、定义列表：用原文行范围保留格式
    for fm in result.get('front_matters', []):
        if fm.get('line_start') is not None and fm.get('line_end') is not None:
            start, end = fm['line_start'], fm['line_end']
            if start < len(lines) and end <= len(lines):
                all_elements.append({
                    'type': 'front_matter',
                    'start': start,
                    'end': end,
                    'content': '\n'.join(lines[start:end])
                })
    for dl in result.get('def_lists', []):
        if dl.get('line_start') is not None and dl.get('line_end') is not None:
            start, end = dl['line_start'], dl['line_end']
            if start < len(lines) and end <= len(lines):
                all_elements.append({
                    'type': 'def_list',
                    'start': start,
                    'end': end,
                    'content': '\n'.join(lines[start:end])
                })
    
    # 按起始行排序
    all_elements.sort(key=lambda x: x['start'])
    
    # 重新组装：使用原始文本，但用提取的元素替换对应行
    reconstructed_lines = []
    processed_lines = set()
    
    for elem in all_elements:
        for line_num in range(elem['start'], elem['end']):
            processed_lines.add(line_num)
    
    current_elem_idx = 0
    i = 0
    while i < len(lines):
        # 检查当前行是否是某个元素的开始
        if current_elem_idx < len(all_elements) and i == all_elements[current_elem_idx]['start']:
            elem = all_elements[current_elem_idx]
            reconstructed_lines.append(elem['content'])
            i = elem['end']
            current_elem_idx += 1
        else:
            # 不是特殊元素，直接使用原始行
            if i not in processed_lines:
                reconstructed_lines.append(lines[i])
            i += 1
    
    reconstructed_md = '\n'.join(reconstructed_lines)
    
    # 保存重构的 Markdown
    reconstructed_file = output_dir / f"markdown_it_demo2_重构_{timestamp}.md"
    with open(reconstructed_file, "w", encoding="utf-8") as f:
        f.write(reconstructed_md)
    
    print(f"\n✅ 已生成重构的 Markdown 文件: {reconstructed_file}")
    print(f"   可以与原始文件对比: {data_path}")

# 写入详细输出文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"markdown-it-py 完整元素解析结果\n")
    f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"源文件: {data_path}\n")
    f.write(f"说明: 使用 markdown-it-py 解析 Markdown，提取代码块、表格、列表、公式、引用块、HTML块\n")
    f.write("=" * 100 + "\n\n")
    
    if not result['success']:
        f.write(f"❌ 解析失败\n")
        f.write(f"错误信息: {result.get('error', 'Unknown')}\n")
    else:
        f.write(f"✅ 解析成功\n\n")
        
        # 统计信息
        f.write("=" * 100 + "\n")
        f.write("📊 统计信息\n")
        f.write("=" * 100 + "\n")
        f.write(f"总 Tokens: {len(result['tokens'])}\n")
        f.write(f"代码块: {len(result['code_blocks'])} 个\n")
        f.write(f"表格: {len(result['tables'])} 个\n")
        f.write(f"列表: {len(result['lists'])} 个\n")
        f.write(f"数学公式: {len(result['math_blocks'])} 个\n")
        f.write(f"引用块: {len(result['blockquotes'])} 个\n")
        f.write(f"HTML 块: {len(result['html_blocks'])} 个\n")
        f.write(f"Front matter: {len(result.get('front_matters', []))} 个\n")
        f.write(f"定义列表: {len(result.get('def_lists', []))} 个\n")
        f.write(f"分隔线: {len(result.get('hrs', []))} 个\n")
        f.write("\n")
        
        # 代码块详情
        if result['code_blocks']:
            f.write("=" * 100 + "\n")
            f.write("💻 代码块详情\n")
            f.write("=" * 100 + "\n\n")
            
            for block in result['code_blocks']:
                f.write(f"[代码块 {block['index']}/{len(result['code_blocks'])}]\n")
                f.write(f"类型: {block['type']}\n")
                f.write(f"语言: {block['language']}\n")
                f.write(f"行数: {block['line_count']}\n")
                f.write(f"Token 数: {block['token_count']}\n")
                f.write(f"位置: 第 {block['line_start']} - {block['line_end']} 行\n")
                f.write("-" * 100 + "\n")
                f.write(block['content'])
                f.write("\n" + "-" * 100 + "\n\n")
        
        # 表格详情
        if result['tables']:
            f.write("=" * 100 + "\n")
            f.write("📊 表格详情\n")
            f.write("=" * 100 + "\n\n")
            
            for table in result['tables']:
                f.write(f"[表格 {table['index']}/{len(result['tables'])}]\n")
                f.write(f"行数: {table['num_rows']}\n")
                f.write(f"列数: {table['num_cols']}\n")
                f.write(f"位置: 第 {table['line_start']} - {table['line_end']} 行\n")
                f.write("-" * 100 + "\n")
                f.write(table['markdown'])
                f.write("-" * 100 + "\n\n")
        
        # 列表详情
        if result['lists']:
            f.write("=" * 100 + "\n")
            f.write("📝 列表详情\n")
            f.write("=" * 100 + "\n\n")
            
            for lst in result['lists']:
                f.write(f"[列表 {lst['index']}/{len(result['lists'])}]\n")
                f.write(f"类型: {lst['type']}\n")
                f.write(f"项目数: {lst['num_items']}\n")
                f.write(f"位置: 第 {lst['line_start']} - {lst['line_end']} 行\n")
                f.write("-" * 100 + "\n")
                for i, item in enumerate(lst['items'], 1):
                    f.write(f"{i}. {item}\n")
                f.write("-" * 100 + "\n\n")
        
        # 数学公式详情
        if result['math_blocks']:
            f.write("=" * 100 + "\n")
            f.write("🔢 数学公式详情\n")
            f.write("=" * 100 + "\n\n")
            
            for math in result['math_blocks']:
                f.write(f"[公式 {math['index']}/{len(result['math_blocks'])}]\n")
                f.write(f"类型: {math['type']}\n")
                f.write(f"位置: 第 {math['line_start']} - {math['line_end']} 行\n")
                f.write("-" * 100 + "\n")
                f.write(math['content'])
                f.write("\n" + "-" * 100 + "\n\n")
        
        # 引用块详情
        if result['blockquotes']:
            f.write("=" * 100 + "\n")
            f.write("💬 引用块详情\n")
            f.write("=" * 100 + "\n\n")
            
            for quote in result['blockquotes']:
                f.write(f"[引用块 {quote['index']}/{len(result['blockquotes'])}]\n")
                f.write(f"Token 数: {quote['token_count']}\n")
                f.write(f"位置: 第 {quote['line_start']} - {quote['line_end']} 行\n")
                f.write("-" * 100 + "\n")
                f.write(quote['content'])
                f.write("\n" + "-" * 100 + "\n\n")
        
        # HTML 块详情
        if result['html_blocks']:
            f.write("=" * 100 + "\n")
            f.write("🌐 HTML 块详情\n")
            f.write("=" * 100 + "\n\n")
            
            for html in result['html_blocks']:
                f.write(f"[HTML 块 {html['index']}/{len(result['html_blocks'])}]\n")
                f.write(f"位置: 第 {html['line_start']} - {html['line_end']} 行\n")
                f.write("-" * 100 + "\n")
                f.write(html['content'])
                f.write("\n" + "-" * 100 + "\n\n")
        
        # Front matter 详情
        if result.get('front_matters'):
            f.write("=" * 100 + "\n")
            f.write("📄 Front matter 详情\n")
            f.write("=" * 100 + "\n\n")
            for fm in result['front_matters']:
                f.write(f"[Front matter {fm['index']}]\n")
                f.write(f"位置: 第 {fm['line_start']} - {fm['line_end']} 行\n")
                f.write("-" * 100 + "\n")
                f.write(fm['content'])
                f.write("\n" + "-" * 100 + "\n\n")
        
        # 定义列表详情
        if result.get('def_lists'):
            f.write("=" * 100 + "\n")
            f.write("📋 定义列表详情\n")
            f.write("=" * 100 + "\n\n")
            for dl in result['def_lists']:
                f.write(f"[定义列表 {dl['index']}]\n")
                f.write(f"位置: 第 {dl['line_start']} - {dl['line_end']} 行\n")
                f.write("-" * 100 + "\n")
                f.write(dl['content'])
                f.write("\n" + "-" * 100 + "\n\n")
        
        # Token 详情（可选，用于调试）
        f.write("=" * 100 + "\n")
        f.write("🔍 Token 详情（前 50 个）\n")
        f.write("=" * 100 + "\n\n")
        
        for i, token in enumerate(result['tokens'][:50], 1):
            f.write(f"[Token {i}] {token.type}")
            if token.tag:
                f.write(f" <{token.tag}>")
            if token.content:
                content_preview = token.content[:50].replace('\n', '\\n')
                f.write(f" | {content_preview}")
            if token.map:
                f.write(f" | 行 {token.map[0]}-{token.map[1]}")
            f.write("\n")
        
        if len(result['tokens']) > 50:
            f.write(f"\n... 还有 {len(result['tokens']) - 50} 个 tokens\n")

print("\n" + "=" * 100)
print(f"✅ 解析完成！")
print(f"   详细解析: {output_file}")
if result['success']:
    print(f"   参考文件: {reconstructed_file}")
    print(f"   原始文件: {data_path}")
print("=" * 100)
print("\n📊 解析说明:")
print("1. 使用 markdown-it-py 解析 Markdown 文件")
print("2. 提取所有主要元素：代码块、表格、列表、公式、引用块、HTML块")
print("3. 每个元素都包含详细的位置信息和内容")
print("4. 支持 GFM 扩展、数学公式、任务列表等")
print("5. markdown-it-py 的解析是无损的，可以完整还原文档结构")
print("\n💡 提示：")
print("   - 详细解析报告包含了所有提取的元素")
print("   - 可以通过 tokens 精确定位每个元素在原文中的位置")
print("   - 表格、列表、代码块等都被正确识别和提取")
