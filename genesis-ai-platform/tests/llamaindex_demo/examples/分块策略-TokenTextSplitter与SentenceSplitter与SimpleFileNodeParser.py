import os
from datetime import datetime
from llama_index.core.node_parser import SentenceSplitter, SimpleFileNodeParser
from llama_index.core.node_parser.text.token import TokenTextSplitter
from config import Settings
from llama_index.core import SimpleDirectoryReader

# 获取数据路径（使用相对路径，确保跨平台兼容）
current_dir = os.path.dirname(os.path.abspath(__file__))
# 当前文件位置：genesis-ai-platform/tests/llamaindex_demo/examples/分块策略-markdown.py
# 需要回到项目根目录（genesis-ai），向上 4 级
project_root = os.path.normpath(os.path.join(current_dir, "../../../.."))
data_path = os.path.join(project_root, "doc", "增删改查指南.md")

# 输出文件路径
output_dir = os.path.join(current_dir, "../output")
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, f"分块结果-markdown-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

print(f"Current dir: {current_dir}")
print(f"Project root: {project_root}")
print(f"Data path: {data_path}")
print(f"File exists: {os.path.exists(data_path)}")
print(f"Output file: {output_file}")
print("=" * 100)

# 加载数据（使用 input_files 参数传入单个文件）
documents = SimpleDirectoryReader(input_files=[data_path]).load_data()

# 打开输出文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"分块策略测试结果 - Markdown 文件\n")
    f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"源文件: {data_path}\n")
    f.write("=" * 100 + "\n\n")
    
    # ========== TokenTextSplitter ==========
    print("\n" + "=" * 100)
    print("测试 1: TokenTextSplitter")
    print("=" * 100)
    
    token_text_splitter = TokenTextSplitter(
        chunk_size=500, 
        chunk_overlap=100,
        separator="\n\n"
    )
    nodes = token_text_splitter.get_nodes_from_documents(documents)
    
    print(f"✅ 总块数: {len(nodes)}")
    f.write("=" * 100 + "\n")
    f.write("测试 1: TokenTextSplitter\n")
    f.write(f"参数: chunk_size=500, chunk_overlap=100, separator='\\n\\n'\n")
    f.write(f"总块数: {len(nodes)}\n")
    f.write("=" * 100 + "\n\n")
    
    for i, node in enumerate(nodes, 1):
        f.write(f"【块 {i}/{len(nodes)}】(长度: {len(node.text)} 字符)\n")
        f.write("-" * 100 + "\n")
        f.write(node.text)
        f.write("\n" + "-" * 100 + "\n\n")
    
    # ========== SentenceSplitter ==========
    print("\n" + "=" * 100)
    print("测试 2: SentenceSplitter")
    print("=" * 100)
    
    sentence_splitter = SentenceSplitter(
        chunk_size=500, 
        chunk_overlap=100,
        paragraph_separator="\n\n",
        secondary_chunking_regex="[^。！？]+[。！？]?"
    )
    nodes = sentence_splitter.get_nodes_from_documents(documents)
    
    print(f"✅ 总块数: {len(nodes)}")
    f.write("\n" + "=" * 100 + "\n")
    f.write("测试 2: SentenceSplitter\n")
    f.write(f"参数: chunk_size=500, chunk_overlap=100, paragraph_separator='\\n\\n'\n")
    f.write(f"总块数: {len(nodes)}\n")
    f.write("=" * 100 + "\n\n")
    
    for i, node in enumerate(nodes, 1):
        f.write(f"【块 {i}/{len(nodes)}】(长度: {len(node.text)} 字符)\n")
        f.write("-" * 100 + "\n")
        f.write(node.text)
        f.write("\n" + "-" * 100 + "\n\n")
    
    # ========== SimpleFileNodeParser ==========
    print("\n" + "=" * 100)
    print("测试 3: SimpleFileNodeParser")
    print("=" * 100)
    
    simple_file_node_parser = SimpleFileNodeParser(
        chunk_size=500, 
        chunk_overlap=100
    )
    nodes = simple_file_node_parser.get_nodes_from_documents(documents)
    
    print(f"✅ 总块数: {len(nodes)}")
    f.write("\n" + "=" * 100 + "\n")
    f.write("测试 3: SimpleFileNodeParser\n")
    f.write(f"参数: chunk_size=500, chunk_overlap=100\n")
    f.write(f"总块数: {len(nodes)}\n")
    f.write("=" * 100 + "\n\n")
    
    for i, node in enumerate(nodes, 1):
        content = node.get_content()
        f.write(f"【块 {i}/{len(nodes)}】(长度: {len(content)} 字符)\n")
        f.write("-" * 100 + "\n")
        f.write(content)
        f.write("\n" + "-" * 100 + "\n\n")

print("\n" + "=" * 100)
print(f"✅ 所有测试完成！结果已保存到: {output_file}")
print("=" * 100)
