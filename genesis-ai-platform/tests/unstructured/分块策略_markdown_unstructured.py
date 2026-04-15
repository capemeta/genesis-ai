import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core import SimpleDirectoryReader
from unstructured.partition.md import partition_md
from unstructured.chunking.basic import chunk_elements
from rag.utils.token_utils import count_tokens

# 获取数据路径（向上两级到项目根目录，再进入 doc 目录）
# genesis-ai-platform/tests/unstructured/ -> genesis-ai-platform/ -> 根目录 -> doc/
workspace_root = project_root.parent  # 从 genesis-ai-platform 向上一级到工作区根目录
data_path = workspace_root / "doc" / "增删改查指南.md"

# 输出文件路径
output_dir = current_dir / "output"
output_dir.mkdir(exist_ok=True)
output_file = output_dir / f"分块结果-混合策略-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

print(f"Current dir: {current_dir}")
print(f"Project root: {project_root}")
print(f"Workspace root: {workspace_root}")
print(f"Data path: {data_path}")
print(f"File exists: {data_path.exists()}")
print(f"Output file: {output_file}")
print("=" * 100)

def get_max_characters(max_tokens: int) -> int:
    """
    根据 token 数计算最大字符数
    
    对于中文嵌入模型（如 bge, m3e 等）：
    - 1 token ≈ 1 字符
    - 安全系数：0.9（避免边界情况超出限制）
    
    Args:
        max_tokens: 最大 token 数
        
    Returns:
        最大字符数
    """
    return int(max_tokens * 0.9)


def process_large_element_with_unstructured(text: str, max_tokens: int = 512, output_elements_file=None) -> list:
    """
    使用 unstructured 处理超过 max_tokens 的元素
    
    Args:
        text: 要处理的文本
        max_tokens: token 限制
        output_elements_file: 输出 elements 详情的文件对象（可选）
        
    Returns:
        分块后的文本列表
    """
    try:
        # 直接使用 partition_md 处理文本，不需要临时文件
        elements = partition_md(text=text)
        print(f"unstructured 解析结果:")
        print(f"  - elements 个数: {len(elements)}")
        
        # 打印每个 element 的类型和内容预览
        element_types = {}
        for elem in elements:
            elem_type = type(elem).__name__
            element_types[elem_type] = element_types.get(elem_type, 0) + 1
        
        print(f"  - 元素类型统计:")
        for elem_type, count in element_types.items():
            print(f"    - {elem_type}: {count} 个")
        
        # 打印前几个元素的详细信息
        print(f"\n  - 前 5 个元素详情:")
        for i, elem in enumerate(elements[:5], 1):
            elem_type = type(elem).__name__
            elem_text = str(elem).strip()
            preview = elem_text[:100] + "..." if len(elem_text) > 100 else elem_text
            print(f"    [{i}] {elem_type}: {preview}")
        
        # 如果提供了输出文件，写入所有 elements 的详细信息
        if output_elements_file:
            output_elements_file.write(f"\n{'='*100}\n")
            output_elements_file.write(f"Elements 总数: {len(elements)}\n")
            output_elements_file.write(f"{'='*100}\n\n")
            
            output_elements_file.write("元素类型统计:\n")
            for elem_type, count in element_types.items():
                output_elements_file.write(f"  - {elem_type}: {count} 个\n")
            output_elements_file.write("\n")
            
            output_elements_file.write(f"{'='*100}\n")
            output_elements_file.write("所有 Elements 详情:\n")
            output_elements_file.write(f"{'='*100}\n\n")
            
            for i, elem in enumerate(elements, 1):
                elem_type = type(elem).__name__
                elem_text = str(elem).strip()
                
                output_elements_file.write(f"【Element {i}/{len(elements)}】\n")
                output_elements_file.write(f"类型: {elem_type}\n")
                output_elements_file.write(f"字符数: {len(elem_text)}\n")
                output_elements_file.write(f"Token 数: {count_tokens(elem_text)}\n")
                output_elements_file.write(f"{'-'*100}\n")
                output_elements_file.write(f"{elem_text}\n")
                output_elements_file.write(f"{'-'*100}\n\n")
        
        # 计算最大字符数
        max_characters = get_max_characters(max_tokens)
        
        # 使用 unstructured 的分块功能
        # 参数说明：
        # - max_characters: 硬限制，块不会超过这个大小
        # - new_after_n_chars: 软限制，尽量在这个大小后开始新块（避免块太小）
        chunks = chunk_elements(
            elements,
            max_characters=max_characters,
            new_after_n_chars=int(max_characters * 0.6),  # 60% 作为软限制，避免块太小
            overlap=0
        )
        
        # 提取文本
        result = []
        for chunk in chunks:
            chunk_text = str(chunk)
            if chunk_text.strip():
                result.append(chunk_text)
        
        print(f"  - 最终分块数: {len(result)}")
        
        return result if result else [text]
        
    except Exception as e:
        print(f"⚠️ unstructured 处理失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 回退：简单按段落分割
        paragraphs = text.split('\n\n')
        result = []
        current = []
        current_tokens = 0
        
        for para in paragraphs:
            if not para.strip():
                continue
            para_tokens = count_tokens(para)
            if current_tokens + para_tokens <= max_tokens:
                current.append(para)
                current_tokens += para_tokens
            else:
                if current:
                    result.append('\n\n'.join(current))
                current = [para]
                current_tokens = para_tokens
        
        if current:
            result.append('\n\n'.join(current))
        
        return result if result else [text]


def hybrid_chunk_markdown(file_path: str, max_tokens: int = 512, elements_output_file=None):
    """
    混合策略：先用 markdown_parser 处理，超过 512 token 的用 unstructured 处理
    
    Args:
        file_path: Markdown 文件路径
        max_tokens: token 限制（默认 512）
        elements_output_file: 输出 elements 详情的文件对象（可选）
        
    Returns:
        分块结果列表
    """
    # 加载文档
    documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
    
    # 第一层：使用 MarkdownNodeParser 按标题分块
    markdown_parser = MarkdownNodeParser(
        include_metadata=True,
        include_prev_next_rel=False,
    )
    nodes = markdown_parser.get_nodes_from_documents(documents)
    
    print(f"📊 第一层分块（MarkdownNodeParser）: {len(nodes)} 个章节")
    
    # 第二层：检查每个块的 token 数，超过限制的用 unstructured 处理
    final_chunks = []
    large_chunks_count = 0
    
    for i, node in enumerate(nodes, 1):
        text = node.get_content()
        header_path = node.metadata.get("header_path", "")
        token_count = count_tokens(text)
        
        if token_count <= max_tokens:
            # 不超过限制，直接使用
            final_chunks.append({
                "text": text,
                "header_path": header_path,
                "token_count": token_count,
                "source": "markdown_parser",
                "chunk_index": i
            })
        else:
            # 超过限制，使用 unstructured 处理
            large_chunks_count += 1
            print(f"  ⚠️ 章节 {i} 超过 {max_tokens} tokens ({token_count} tokens)，使用 unstructured 处理")
            
            # 如果提供了 elements 输出文件，写入章节信息
            if elements_output_file:
                elements_output_file.write(f"\n{'#'*100}\n")
                elements_output_file.write(f"章节 {i}: {header_path}\n")
                elements_output_file.write(f"原始 Token 数: {token_count}\n")
                elements_output_file.write(f"{'#'*100}\n")
            
            sub_chunks = process_large_element_with_unstructured(text, max_tokens, elements_output_file)
            
            for j, sub_text in enumerate(sub_chunks, 1):
                sub_token_count = count_tokens(sub_text)
                final_chunks.append({
                    "text": sub_text,
                    "header_path": f"{header_path} [子块 {j}/{len(sub_chunks)}]",
                    "token_count": sub_token_count,
                    "source": "unstructured",
                    "parent_chunk_index": i,
                    "sub_chunk_index": j
                })
    
    print(f"📊 第二层处理完成:")
    print(f"  - 直接使用的章节: {len(nodes) - large_chunks_count}")
    print(f"  - 需要二次分块的章节: {large_chunks_count}")
    print(f"  - 最终块数: {len(final_chunks)}")
    
    return final_chunks


# 执行混合策略分块
print("\n" + "=" * 100)
print("混合策略：MarkdownNodeParser + Unstructured")
print("=" * 100)

# 创建 elements 输出文件
output_file_elements = output_dir / f"Unstructured - Elements详情-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

with open(output_file_elements, "w", encoding="utf-8") as elements_file:
    elements_file.write(f"Unstructured Elements 详情\n")
    elements_file.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    elements_file.write(f"源文件: {data_path}\n")
    elements_file.write(f"说明: 这是 unstructured 解析出的所有 elements 的详细信息\n")
    elements_file.write("=" * 100 + "\n")
    
    chunks = hybrid_chunk_markdown(str(data_path), max_tokens=512, elements_output_file=elements_file)

# 生成第二个文件名（只包含 unstructured 处理的块）
output_file_unstructured = output_dir / f"分块结果-混合策略__Unstructured-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

# 写入完整输出文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"混合策略分块结果\n")
    f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"源文件: {data_path}\n")
    f.write(f"策略: 先用 MarkdownNodeParser 按标题分块，超过 512 token 的用 unstructured 处理\n")
    f.write("=" * 100 + "\n\n")
    
    f.write(f"总块数: {len(chunks)}\n")
    f.write(f"Token 限制: 512\n\n")
    
    # 统计信息
    markdown_chunks = [c for c in chunks if c["source"] == "markdown_parser"]
    unstructured_chunks = [c for c in chunks if c["source"] == "unstructured"]
    
    f.write("=" * 100 + "\n")
    f.write("统计信息\n")
    f.write("=" * 100 + "\n")
    f.write(f"直接使用的章节（markdown_parser）: {len(markdown_chunks)}\n")
    f.write(f"二次分块的子块（unstructured）: {len(unstructured_chunks)}\n")
    f.write(f"平均 token 数: {sum(c['token_count'] for c in chunks) / len(chunks):.1f}\n")
    f.write(f"最大 token 数: {max(c['token_count'] for c in chunks)}\n")
    f.write(f"最小 token 数: {min(c['token_count'] for c in chunks)}\n")
    f.write("\n")
    
    # 详细块信息
    f.write("=" * 100 + "\n")
    f.write("详细块信息\n")
    f.write("=" * 100 + "\n\n")
    
    for i, chunk in enumerate(chunks, 1):
        f.write(f"【块 {i}/{len(chunks)}】\n")
        f.write(f"来源: {chunk['source']}\n")
        f.write(f"标题路径: {chunk['header_path']}\n")
        f.write(f"Token 数: {chunk['token_count']}\n")
        f.write(f"字符数: {len(chunk['text'])}\n")
        
        if chunk["source"] == "unstructured":
            f.write(f"父章节索引: {chunk['parent_chunk_index']}\n")
            f.write(f"子块索引: {chunk['sub_chunk_index']}\n")
        
        f.write("-" * 100 + "\n")
        f.write(chunk["text"])
        f.write("\n" + "-" * 100 + "\n\n")

# 写入 Unstructured 专用文件（只包含 unstructured 处理的块）
unstructured_chunks = [c for c in chunks if c["source"] == "unstructured"]

with open(output_file_unstructured, "w", encoding="utf-8") as f:
    f.write(f"Unstructured 处理的块（仅包含超过 512 token 的章节）\n")
    f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"源文件: {data_path}\n")
    f.write(f"说明: 这些块是原始章节超过 512 token，经过 unstructured 二次分块后的结果\n")
    f.write("=" * 100 + "\n\n")
    
    if unstructured_chunks:
        f.write(f"Unstructured 处理的块数: {len(unstructured_chunks)}\n")
        
        # 统计父章节
        parent_indices = set(c["parent_chunk_index"] for c in unstructured_chunks)
        f.write(f"涉及的父章节数: {len(parent_indices)}\n")
        f.write(f"平均 token 数: {sum(c['token_count'] for c in unstructured_chunks) / len(unstructured_chunks):.1f}\n")
        f.write(f"最大 token 数: {max(c['token_count'] for c in unstructured_chunks)}\n")
        f.write(f"最小 token 数: {min(c['token_count'] for c in unstructured_chunks)}\n")
        f.write("\n")
        
        # 详细块信息
        f.write("=" * 100 + "\n")
        f.write("详细块信息\n")
        f.write("=" * 100 + "\n\n")
        
        for i, chunk in enumerate(unstructured_chunks, 1):
            f.write(f"【Unstructured 块 {i}/{len(unstructured_chunks)}】\n")
            f.write(f"标题路径: {chunk['header_path']}\n")
            f.write(f"Token 数: {chunk['token_count']}\n")
            f.write(f"字符数: {len(chunk['text'])}\n")
            f.write(f"父章节索引: {chunk['parent_chunk_index']}\n")
            f.write(f"子块索引: {chunk['sub_chunk_index']}\n")
            f.write("-" * 100 + "\n")
            f.write(chunk["text"])
            f.write("\n" + "-" * 100 + "\n\n")
    else:
        f.write("没有需要 unstructured 处理的块（所有章节都 ≤ 512 tokens）\n")

print("\n" + "=" * 100)
print(f"✅ 混合策略分块完成！")
print(f"   完整结果: {output_file}")
print(f"   Unstructured 块: {output_file_unstructured}")
print(f"   Elements 详情: {output_file_elements}")
print("=" * 100)
print("\n📊 策略说明:")
print("1. 第一层：使用 MarkdownNodeParser 按标题分块，保留文档结构")
print("2. 第二层：检查每个块的 token 数")
print("   - ≤ 512 tokens: 直接使用")
print("   - > 512 tokens: 使用 unstructured 进一步分块")
print("3. 优点：既保留了 Markdown 结构，又确保了 token 限制")
