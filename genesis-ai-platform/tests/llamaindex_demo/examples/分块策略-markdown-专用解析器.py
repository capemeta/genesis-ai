import os
from datetime import datetime
from llama_index.core.node_parser import (
    MarkdownNodeParser,
    MarkdownElementNodeParser,
    SentenceSplitter,
    TokenTextSplitter,
)
from config import Settings
from llama_index.core import SimpleDirectoryReader

# 获取数据路径（使用相对路径，确保跨平台兼容）
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(current_dir, "../../../.."))
data_path = os.path.join(project_root, "doc", "前端技术-设计软件.md")

# 输出文件路径
output_dir = os.path.join(current_dir, "../output")
os.makedirs(output_dir, exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file_markdown = os.path.join(output_dir, f"分块结果-markdown专用-{timestamp}_MarkdownNodeParser.txt")
output_file_element = os.path.join(output_dir, f"分块结果-markdown专用-{timestamp}_MarkdownElement.txt")
output_file_sentence = os.path.join(output_dir, f"分块结果-markdown专用-{timestamp}_SentenceSplitter.txt")

print(f"Data path: {data_path}")
print(f"File exists: {os.path.exists(data_path)}")
print(f"Output file (MarkdownNodeParser): {output_file_markdown}")
print(f"Output file (MarkdownElement): {output_file_element}")
print(f"Output file (SentenceSplitter): {output_file_sentence}")
print("=" * 100)

# 加载数据
documents = SimpleDirectoryReader(input_files=[data_path]).load_data()

# ========== MarkdownNodeParser（按标题分块）==========
print("\n" + "=" * 100)
print("测试 1: MarkdownNodeParser（按 Markdown 标题层级分块）")
print("=" * 100)

markdown_parser = MarkdownNodeParser(
    include_metadata=True,
    include_prev_next_rel=True,
    header_path_separator="/"  # 标题路径分隔符
)
nodes = markdown_parser.get_nodes_from_documents(documents)

print(f"✅ 总块数: {len(nodes)}")

# 写入独立文件（MarkdownNodeParser）
with open(output_file_markdown, "w", encoding="utf-8") as f_markdown:
    f_markdown.write(f"MarkdownNodeParser 测试结果\n")
    f_markdown.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f_markdown.write(f"源文件: {data_path}\n")
    f_markdown.write("=" * 100 + "\n\n")
    
    f_markdown.write("=" * 100 + "\n")
    f_markdown.write("MarkdownNodeParser（按 Markdown 标题层级分块）\n")
    f_markdown.write(f"说明: 根据 Markdown 标题（# ## ### 等）自动分块，每个块包含一个完整的章节\n")
    f_markdown.write(f"总块数: {len(nodes)}\n")
    f_markdown.write("=" * 100 + "\n\n")
    
    for i, node in enumerate(nodes, 1):
        header_path = node.metadata.get("header_path", "/")
        f_markdown.write(f"【块 {i}/{len(nodes)}】\n")
        f_markdown.write(f"标题路径: {header_path}\n")
        f_markdown.write(f"长度: {len(node.text)} 字符\n")
        f_markdown.write("-" * 100 + "\n")
        f_markdown.write(node.text)
        f_markdown.write("\n" + "-" * 100 + "\n\n")
    
# ========== MarkdownElementNodeParser（提取表格等元素）==========
print("\n" + "=" * 100)
print("测试 2: MarkdownElementNodeParser（提取表格、代码块等元素）")
print("=" * 100)

try:
    # 临时保存全局 LLM 配置
    from llama_index.core import Settings as LlamaSettings
    original_llm = LlamaSettings.llm
    
    # 临时禁用全局 LLM
    LlamaSettings.llm = None
    
    # 创建解析器（不使用 LLM）
    markdown_element_parser = MarkdownElementNodeParser(llm=None)
    nodes_element = markdown_element_parser.get_nodes_from_documents(documents)
    
    # 恢复全局 LLM 配置
    LlamaSettings.llm = original_llm
    
    print(f"✅ 总块数: {len(nodes_element)}")
    
    # 写入独立文件（MarkdownElement）
    with open(output_file_element, "w", encoding="utf-8") as f_element:
        f_element.write(f"MarkdownElementNodeParser 测试结果\n")
        f_element.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f_element.write(f"源文件: {data_path}\n")
        f_element.write("=" * 100 + "\n\n")
        
        f_element.write("=" * 100 + "\n")
        f_element.write("MarkdownElementNodeParser（提取表格、代码块等元素）\n")
        f_element.write(f"说明: 识别并单独提取 Markdown 中的表格、代码块等结构化元素（禁用 LLM）\n")
        f_element.write(f"总块数: {len(nodes_element)}\n")
        f_element.write("=" * 100 + "\n\n")
        
        for i, node in enumerate(nodes_element, 1):
            node_type = type(node).__name__
            f_element.write(f"【块 {i}/{len(nodes_element)}】类型: {node_type}\n")
            f_element.write(f"长度: {len(node.get_content())} 字符\n")
            f_element.write("-" * 100 + "\n")
            f_element.write(node.get_content())
            f_element.write("\n" + "-" * 100 + "\n\n")
except Exception as e:
    print(f"⚠️ MarkdownElementNodeParser 测试失败: {e}")
    
    # 恢复全局 LLM 配置（如果出错）
    try:
        LlamaSettings.llm = original_llm
    except:
        pass
    
    # 即使失败也创建文件，记录错误信息
    with open(output_file_element, "w", encoding="utf-8") as f_element:
        f_element.write(f"MarkdownElementNodeParser 测试结果\n")
        f_element.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f_element.write(f"源文件: {data_path}\n")
        f_element.write("=" * 100 + "\n\n")
        
        f_element.write("⚠️ 测试失败\n")
        f_element.write("=" * 100 + "\n\n")
        f_element.write(f"错误信息: {str(e)}\n\n")
        f_element.write("可能的原因:\n")
        f_element.write("1. MarkdownElementNodeParser 需要调用 LLM 来提取和分类元素\n")
        f_element.write("2. 当前配置的 DeepSeek v3.1 模型在启用思考模式时不支持函数调用\n")
        f_element.write("3. 建议切换到其他模型或禁用思考模式\n")
    
# ========== SentenceSplitter（对比：通用句子分块）==========
print("\n" + "=" * 100)
print("测试 3: SentenceSplitter（对比：通用句子分块）")
print("=" * 100)

sentence_splitter = SentenceSplitter(
    chunk_size=500,
    chunk_overlap=100,
    paragraph_separator="\n\n"
)
nodes_sentence = sentence_splitter.get_nodes_from_documents(documents)

print(f"✅ 总块数: {len(nodes_sentence)}")

# 写入独立文件（SentenceSplitter）
with open(output_file_sentence, "w", encoding="utf-8") as f_sentence:
    f_sentence.write(f"SentenceSplitter 测试结果\n")
    f_sentence.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f_sentence.write(f"源文件: {data_path}\n")
    f_sentence.write("=" * 100 + "\n\n")
    
    f_sentence.write("=" * 100 + "\n")
    f_sentence.write("SentenceSplitter（对比：通用句子分块）\n")
    f_sentence.write(f"参数: chunk_size=500, chunk_overlap=100\n")
    f_sentence.write(f"说明: 不考虑 Markdown 结构，按句子和段落分块\n")
    f_sentence.write(f"总块数: {len(nodes_sentence)}\n")
    f_sentence.write("=" * 100 + "\n\n")
    
    for i, node in enumerate(nodes_sentence, 1):
        f_sentence.write(f"【块 {i}/{len(nodes_sentence)}】(长度: {len(node.text)} 字符)\n")
        f_sentence.write("-" * 100 + "\n")
        f_sentence.write(node.text)
        f_sentence.write("\n" + "-" * 100 + "\n\n")

print("\n" + "=" * 100)
print(f"✅ 所有测试完成！")
print(f"MarkdownNodeParser: {output_file_markdown}")
print(f"MarkdownElement: {output_file_element}")
print(f"SentenceSplitter: {output_file_sentence}")
print("=" * 100)
print("\n📊 对比总结:")
print("1. MarkdownNodeParser: 按标题层级分块，保留文档结构，适合技术文档")
print("2. MarkdownElementNodeParser: 提取表格、代码块等元素，适合结构化内容")
print("3. SentenceSplitter: 通用分块，不考虑 Markdown 结构")
