from llama_index.core.schema import BaseNode


import os

from llama_index.core.node_parser import SentenceSplitter, SimpleFileNodeParser
from llama_index.core.node_parser.text.token import TokenTextSplitter
from config import Settings # 从 base 导入 Settings，确保了 base 被执行且 Settings 可用
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# 获取数据路径
current_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(current_dir, "../data")

# 加载数据
documents = SimpleDirectoryReader(data_path).load_data()

# print("***" * 30 + "TokenTextSplitter" + "***" * 30)
# token_text_splitter = TokenTextSplitter(chunk_size=500, chunk_overlap=100,separator="\n\n")
# nodes = token_text_splitter.get_nodes_from_documents(documents)
# print(f"Total chunks: {len(nodes)}")
# for i,node in enumerate(nodes):
#     print(f"Chunk {i+1} (Length: {len(node.text)}): {node.text}")
#     print("-" * 100)
# print("***" * 30 + "SentenceSplitter" + "***" * 30)

sentence_splitter =  SentenceSplitter(
    chunk_size=500, 
    chunk_overlap=50,
    paragraph_separator="\n\n",  # 中文常用双换行
    secondary_chunking_regex="[^。！？]+[。！？]?"  # 中文标点分割
)
nodes = sentence_splitter.get_nodes_from_documents(documents)
print(f"Total chunks: {len(nodes)}")
for i,node in enumerate(nodes):
    print(f"Chunk {i+1} (Length: {len(node.text)}): {node.text}")
    print("-" * 100)

# print("***" * 30 + "SimpleFileNodeParser" + "***" * 30)

# simple_file_node_parser = SimpleFileNodeParser(chunk_size=500, chunk_overlap=100)
# # simple_file_node_parser = SimpleFileNodeParser.from_defaults()
# nodes = simple_file_node_parser.get_nodes_from_documents(documents)
# print(f"Total chunks: {len(nodes)}")
# for i,node in enumerate(nodes):
#     print(f"Chunk {i+1} (Length: {len(node.get_content())}): {node.get_content()}")
#     print("-" * 100)

# print("***" * 30 + "SimpleFileNodeParser" + "***" * 30)

