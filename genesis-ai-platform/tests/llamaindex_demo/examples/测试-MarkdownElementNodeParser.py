import os
from datetime import datetime
from llama_index.core.node_parser import MarkdownElementNodeParser
from llama_index.core.schema import TextNode, IndexNode
from config import Settings
from llama_index.core import SimpleDirectoryReader

# 获取数据路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(current_dir, "../../../.."))
data_path = os.path.join(project_root, "doc", "增删改查指南.md")

# 输出文件路径
output_dir = os.path.join(current_dir, "../output")
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(
    output_dir, 
    f"MarkdownElementNodeParser-详细分析-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
)

print(f"Data path: {data_path}")
print(f"File exists: {os.path.exists(data_path)}")
print(f"Output file: {output_file}")
print("=" * 100)

# 加载数据
documents = SimpleDirectoryReader(input_files=[data_path]).load_data()

print("\n开始使用 MarkdownElementNodeParser 解析...")
print("=" * 100)

# 创建解析器（不使用 LLM，避免 API 调用）
parser = MarkdownElementNodeParser(
    llm=None,  # 不使用 LLM 生成表格摘要
)

# 解析文档
nodes = parser.get_nodes_from_documents(documents)

print(f"\n✅ 解析完成！总共生成 {len(nodes)} 个节点")
print("=" * 100)

# 统计不同类型的节点
node_types = {}
table_nodes = []
text_nodes = []
other_nodes = []

for node in nodes:
    node_type = type(node).__name__
    node_types[node_type] = node_types.get(node_type, 0) + 1
    
    if isinstance(node, IndexNode):
        table_nodes.append(node)
    elif isinstance(node, TextNode):
        text_nodes.append(node)
    else:
        other_nodes.append(node)

print("\n📊 节点类型统计:")
for node_type, count in node_types.items():
    print(f"  - {node_type}: {count} 个")

print(f"\n📋 详细分类:")
print(f"  - 表格节点 (IndexNode): {len(table_nodes)} 个")
print(f"  - 文本节点 (TextNode): {len(text_nodes)} 个")
print(f"  - 其他节点: {len(other_nodes)} 个")

# 写入详细分析到文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write("=" * 100 + "\n")
    f.write("MarkdownElementNodeParser 详细分析报告\n")
    f.write("=" * 100 + "\n")
    f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"源文件: {data_path}\n")
    f.write(f"总节点数: {len(nodes)}\n")
    f.write("\n节点类型统计:\n")
    for node_type, count in node_types.items():
        f.write(f"  - {node_type}: {count} 个\n")
    f.write("\n" + "=" * 100 + "\n\n")
    
    # ========== 表格节点详细分析 ==========
    if table_nodes:
        f.write("\n" + "=" * 100 + "\n")
        f.write(f"📊 表格节点详细分析 (共 {len(table_nodes)} 个)\n")
        f.write("=" * 100 + "\n\n")
        
        for i, node in enumerate(table_nodes, 1):
            f.write(f"\n{'=' * 80}\n")
            f.write(f"表格 {i}/{len(table_nodes)}\n")
            f.write(f"{'=' * 80}\n")
            f.write(f"节点 ID: {node.node_id}\n")
            f.write(f"节点类型: {type(node).__name__}\n")
            
            # 检查是否有表格数据
            if hasattr(node, 'metadata') and 'table_df' in node.metadata:
                f.write(f"\n✅ 包含结构化表格数据 (DataFrame)\n")
                f.write(f"\n表格内容:\n")
                f.write(str(node.metadata['table_df']))
                f.write("\n")
            
            # 原始文本
            f.write(f"\n原始 Markdown 表格:\n")
            f.write("-" * 80 + "\n")
            f.write(node.get_content())
            f.write("\n" + "-" * 80 + "\n")
            
            # 元数据
            if node.metadata:
                f.write(f"\n元数据:\n")
                for key, value in node.metadata.items():
                    if key != 'table_df':  # DataFrame 已经单独显示
                        f.write(f"  - {key}: {value}\n")
            
            f.write("\n")
    else:
        f.write("\n⚠️ 未检测到表格节点\n\n")
    
    # ========== 文本节点详细分析 ==========
    f.write("\n" + "=" * 100 + "\n")
    f.write(f"📝 文本节点详细分析 (共 {len(text_nodes)} 个)\n")
    f.write("=" * 100 + "\n\n")
    
    # 只显示前 10 个文本节点，避免文件过大
    display_count = min(10, len(text_nodes))
    f.write(f"显示前 {display_count} 个文本节点（共 {len(text_nodes)} 个）\n\n")
    
    for i, node in enumerate(text_nodes[:display_count], 1):
        f.write(f"\n{'=' * 80}\n")
        f.write(f"文本节点 {i}/{display_count}\n")
        f.write(f"{'=' * 80}\n")
        f.write(f"节点 ID: {node.node_id}\n")
        f.write(f"内容长度: {len(node.text)} 字符\n")
        
        # 内容预览
        content = node.text
        if len(content) > 500:
            f.write(f"\n内容预览（前 500 字符）:\n")
            f.write("-" * 80 + "\n")
            f.write(content[:500] + "...\n")
        else:
            f.write(f"\n完整内容:\n")
            f.write("-" * 80 + "\n")
            f.write(content + "\n")
        f.write("-" * 80 + "\n")
        
        # 元数据
        if node.metadata:
            f.write(f"\n元数据:\n")
            for key, value in node.metadata.items():
                f.write(f"  - {key}: {value}\n")
        
        f.write("\n")
    
    if len(text_nodes) > display_count:
        f.write(f"\n... 还有 {len(text_nodes) - display_count} 个文本节点未显示\n\n")
    
    # ========== 完整节点列表 ==========
    f.write("\n" + "=" * 100 + "\n")
    f.write(f"📋 完整节点列表 (共 {len(nodes)} 个)\n")
    f.write("=" * 100 + "\n\n")
    
    for i, node in enumerate(nodes, 1):
        node_type = type(node).__name__
        content_preview = node.get_content()[:100].replace('\n', ' ')
        f.write(f"{i}. [{node_type}] {content_preview}...\n")
    
    # ========== 分析总结 ==========
    f.write("\n" + "=" * 100 + "\n")
    f.write("📊 分析总结\n")
    f.write("=" * 100 + "\n\n")
    
    f.write(f"1. 总节点数: {len(nodes)}\n")
    f.write(f"2. 表格节点: {len(table_nodes)} 个\n")
    f.write(f"3. 文本节点: {len(text_nodes)} 个\n")
    f.write(f"4. 其他节点: {len(other_nodes)} 个\n\n")
    
    if table_nodes:
        f.write("✅ 优势:\n")
        f.write("  - 成功识别并提取了表格\n")
        f.write("  - 表格可以转换为结构化数据（DataFrame）\n")
        f.write("  - 适合需要对表格进行结构化查询的场景\n\n")
    else:
        f.write("⚠️ 注意:\n")
        f.write("  - 未检测到表格节点\n")
        f.write("  - 可能文档中没有 Markdown 表格\n")
        f.write("  - 或者表格格式不符合解析器要求\n\n")
    
    f.write("💡 建议:\n")
    if table_nodes:
        f.write("  - 如果需要对表格进行结构化查询，MarkdownElementNodeParser 是好选择\n")
        f.write("  - 如果只需要按章节检索，MarkdownNodeParser 更简单高效\n")
    else:
        f.write("  - 该文档没有表格，建议使用 MarkdownNodeParser\n")
        f.write("  - MarkdownNodeParser 能更好地保留文档的章节结构\n")

print(f"\n✅ 详细分析已保存到: {output_file}")
print("=" * 100)

# 在控制台显示摘要
print("\n📊 快速摘要:")
print(f"  - 总节点数: {len(nodes)}")
print(f"  - 表格节点: {len(table_nodes)} 个")
print(f"  - 文本节点: {len(text_nodes)} 个")

if table_nodes:
    print("\n✅ 检测到表格！")
    print("  MarkdownElementNodeParser 成功提取了表格数据")
    print("  适合需要对表格进行结构化查询的场景")
else:
    print("\n⚠️ 未检测到表格")
    print("  建议使用 MarkdownNodeParser 以获得更好的章节结构")

print("\n💡 查看详细分析请打开输出文件")
