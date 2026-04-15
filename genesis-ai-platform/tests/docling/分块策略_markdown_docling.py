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
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.chunking import HybridChunker
from rag.utils.token_utils import count_tokens

# 获取数据路径（向上两级到项目根目录，再进入 doc 目录）
# genesis-ai-platform/tests/unstructured/ -> genesis-ai-platform/ -> 根目录 -> doc/
workspace_root = project_root.parent  # 从 genesis-ai-platform 向上一级到工作区根目录
data_path = workspace_root / "genesis-ai-platform/tests/data" / "数据库设计_v2.md"

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

print("\n" + "=" * 100)

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


def process_large_element_with_docling(text: str, max_tokens: int = 512) -> list:
    """
    使用 docling 处理超过 max_tokens 的元素
    
    Docling 会将文档解析成结构化元素（texts, groups, tables 等），
    类似 unstructured 的 elements
    
    Args:
        text: 要处理的文本
        max_tokens: token 限制
        
    Returns:
        分块后的文本列表
    """
    # 使用 docling 解析文档结构
    try:
        # 创建临时文件用于 docling 处理
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(text)
            tmp_path = tmp_file.name
        
        try:
            # 使用 docling 转换文档
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            
            # 配置：禁用 AI 模型（Markdown 不需要）
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False  # 禁用 OCR
            pipeline_options.do_table_structure = False  # 禁用表格结构识别
            
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            
            result = converter.convert(tmp_path)
            doc = result.document
            
            print(f"docling 解析结果:")
            print(f"  - texts: {len(doc.texts)} 个")
            print(f"  - groups: {len(doc.groups)} 个")
            print(f"  - tables: {len(doc.tables)} 个")
            
            # 方案：遍历所有 texts 元素，按 token 限制分块
            chunks_list = []
            current = []
            current_tokens = 0
            
            for text_item in doc.texts:
                # 获取文本内容
                item_text = text_item.text.strip()
                if not item_text:
                    continue
                
                item_tokens = count_tokens(item_text)
                
                # 如果单个元素就超过限制，需要进一步分割
                if item_tokens > max_tokens:
                    # 先保存当前累积的内容
                    if current:
                        chunks_list.append('\n\n'.join(current))
                        current = []
                        current_tokens = 0
                    
                    # 对超大元素进行段落级分割
                    paragraphs = item_text.split('\n\n')
                    for para in paragraphs:
                        if not para.strip():
                            continue
                        para_tokens = count_tokens(para)
                        if current_tokens + para_tokens <= max_tokens:
                            current.append(para)
                            current_tokens += para_tokens
                        else:
                            if current:
                                chunks_list.append('\n\n'.join(current))
                            current = [para]
                            current_tokens = para_tokens
                
                # 正常大小的元素
                elif current_tokens + item_tokens <= max_tokens:
                    current.append(item_text)
                    current_tokens += item_tokens
                else:
                    # 当前块已满，保存并开始新块
                    if current:
                        chunks_list.append('\n\n'.join(current))
                    current = [item_text]
                    current_tokens = item_tokens
            
            # 保存最后一块
            if current:
                chunks_list.append('\n\n'.join(current))
            
            print(f"  - 最终分块数: {len(chunks_list)}")
            
            return chunks_list if chunks_list else [text]
            
        finally:
            # 清理临时文件
            import os
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
    except Exception as e:
        print(f"⚠️ docling 处理失败: {e}")
        print(f"   使用简单分块策略作为回退方案")
        import traceback
        traceback.print_exc()
        
        # 回退：简单按段落分割（不需要下载任何模型）
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


def hybrid_chunk_markdown(file_path: str, max_tokens: int = 512):
    """
    混合策略：先用 markdown_parser 处理，超过 512 token 的用 docling 处理
    
    Args:
        file_path: Markdown 文件路径
        max_tokens: token 限制（默认 512）
        
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
            # 超过限制，使用 docling 处理
            large_chunks_count += 1
            print(f"  ⚠️ 章节 {i} 超过 {max_tokens} tokens ({token_count} tokens)，使用 docling 处理")
            
            sub_chunks = process_large_element_with_docling(text, max_tokens)
            
            for j, sub_text in enumerate(sub_chunks, 1):
                sub_token_count = count_tokens(sub_text)
                final_chunks.append({
                    "text": sub_text,
                    "header_path": f"{header_path} [子块 {j}/{len(sub_chunks)}]",
                    "token_count": sub_token_count,
                    "source": "docling",
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
print("混合策略：MarkdownNodeParser + Docling")
print("=" * 100)

chunks = hybrid_chunk_markdown(str(data_path), max_tokens=512)

# 生成第二个文件名（只包含 docling 处理的块）
output_file_docling = output_dir / f"分块结果-混合策略-docling-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

# 写入完整输出文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"混合策略分块结果\n")
    f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"源文件: {data_path}\n")
    f.write(f"策略: 先用 MarkdownNodeParser 按标题分块，超过 512 token 的用 docling 处理\n")
    f.write("=" * 100 + "\n\n")
    

    f.write(f"总块数: {len(chunks)}\n")
    f.write(f"Token 限制: 512\n\n")
    
    # 统计信息
    markdown_chunks = [c for c in chunks if c["source"] == "markdown_parser"]
    docling_chunks = [c for c in chunks if c["source"] == "docling"]
    
    f.write("=" * 100 + "\n")
    f.write("统计信息\n")
    f.write("=" * 100 + "\n")
    f.write(f"直接使用的章节（markdown_parser）: {len(markdown_chunks)}\n")
    f.write(f"二次分块的子块（docling）: {len(docling_chunks)}\n")
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
        
        if chunk["source"] == "docling":
            f.write(f"父章节索引: {chunk['parent_chunk_index']}\n")
            f.write(f"子块索引: {chunk['sub_chunk_index']}\n")
        
        f.write("-" * 100 + "\n")
        f.write(chunk["text"])
        f.write("\n" + "-" * 100 + "\n\n")

# 写入 Docling 专用文件（只包含 docling 处理的块）
docling_chunks = [c for c in chunks if c["source"] == "docling"]

with open(output_file_docling, "w", encoding="utf-8") as f:
    f.write(f"Docling 处理的块（仅包含超过 512 token 的章节）\n")
    f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"源文件: {data_path}\n")
    f.write(f"说明: 这些块是原始章节超过 512 token，经过 docling 二次分块后的结果\n")
    f.write("=" * 100 + "\n\n")
    
    if docling_chunks:
        f.write(f"Docling 处理的块数: {len(docling_chunks)}\n")
        
        # 统计父章节
        parent_indices = set(c["parent_chunk_index"] for c in docling_chunks)
        f.write(f"涉及的父章节数: {len(parent_indices)}\n")
        f.write(f"平均 token 数: {sum(c['token_count'] for c in docling_chunks) / len(docling_chunks):.1f}\n")
        f.write(f"最大 token 数: {max(c['token_count'] for c in docling_chunks)}\n")
        f.write(f"最小 token 数: {min(c['token_count'] for c in docling_chunks)}\n")
        f.write("\n")
        
        # 详细块信息
        f.write("=" * 100 + "\n")
        f.write("详细块信息\n")
        f.write("=" * 100 + "\n\n")
        
        for i, chunk in enumerate(docling_chunks, 1):
            f.write(f"【Docling 块 {i}/{len(docling_chunks)}】\n")
            f.write(f"标题路径: {chunk['header_path']}\n")
            f.write(f"Token 数: {chunk['token_count']}\n")
            f.write(f"字符数: {len(chunk['text'])}\n")
            f.write(f"父章节索引: {chunk['parent_chunk_index']}\n")
            f.write(f"子块索引: {chunk['sub_chunk_index']}\n")
            f.write("-" * 100 + "\n")
            f.write(chunk["text"])
            f.write("\n" + "-" * 100 + "\n\n")
    else:
        f.write("没有需要 docling 处理的块（所有章节都 ≤ 512 tokens）\n")

print("\n" + "=" * 100)
print(f"✅ 混合策略分块完成！")
print(f"   完整结果: {output_file}")
print(f"   Docling 块: {output_file_docling}")
print("=" * 100)
print("\n📊 策略说明:")
print("1. 第一层：使用 MarkdownNodeParser 按标题分块，保留文档结构")
print("2. 第二层：检查每个块的 token 数")
print("   - ≤ 512 tokens: 直接使用")
print("   - > 512 tokens: 使用 docling 进一步分块")
print("3. 优点：既保留了 Markdown 结构，又确保了 token 限制")
