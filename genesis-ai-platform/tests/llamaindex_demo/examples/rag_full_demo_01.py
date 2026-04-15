import os
from typing import List
from config import Settings # 从 base 导入 Settings，确保了 base 被执行且 Settings 可用
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    get_response_synthesizer,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.core.extractors import TitleExtractor
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core import Response

import chromadb

# ==================== 配置部分 ====================
# 获取数据路径
current_dir = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(current_dir, "../data") # 你的文档文件夹路径
CHROMA_PATH = "../data_vector/chroma_db"          # Chroma 持久化存储路径
COLLECTION_NAME = "rag_full_demo_01"
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 200
SIMILARITY_TOP_K = 8                 # 融合后最终返回的 chunk 数量
VECTOR_TOP_K = 12                    # 向量检索先多拿一些
BM25_TOP_K = 12                      # BM25 先多拿一些

# LLM & Embedding 模型
embed_model = Settings.embed_model
llm = Settings.llm

# ==================== 1. 加载文档 ====================
print("正在加载文档...")
docs = SimpleDirectoryReader(
    input_dir=DATA_DIR,
    required_exts=[".pdf", ".md", ".txt", ".docx"],  # 可根据需要增减
).load_data()

# ==================== 2. 分块 ====================
node_parser = SentenceSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    paragraph_separator="\n\n\n",
)

print("正在分块...")
nodes = node_parser.get_nodes_from_documents(docs, show_progress=True)

# ==================== 3. 使用 LLM 提取标题（元数据增强） ====================
print("正在提取标题（可能较慢）...")
title_extractor = TitleExtractor(
    llm=llm,
    nodes=5,           # 每次看几个节点来推标题
    num_workers=2      # 建议不要开太大，避免 API rate limit
)

for i, node in enumerate(nodes, 1):
    try:
        metadata_list = title_extractor.extract([node])
        if metadata_list and isinstance(metadata_list, list) and len(metadata_list) > 0:
            node.metadata.update(metadata_list[0])
        print(f"\r提取标题进度: {i}/{len(nodes)}", end="")
    except Exception as e:
        print(f"\n提取标题出错（跳过此节点）: {e}")
print("\n标题提取完成！")

# ==================== 4. 建立/连接 Chroma 向量存储 ====================
print("正在连接/创建 Chroma 向量数据库...")
db = chromadb.PersistentClient(path=CHROMA_PATH)
chroma_collection = db.get_or_create_collection(COLLECTION_NAME)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# ==================== 5. 构建向量索引 ====================
print("正在构建向量索引（如果已存在会直接使用）...")
vector_index = VectorStoreIndex(
    nodes=nodes,
    storage_context=storage_context,
    embed_model=embed_model,
    show_progress=True,
)

# ==================== 6. 建立两个检索器 ====================
vector_retriever = VectorIndexRetriever(
    index=vector_index,
    similarity_top_k=VECTOR_TOP_K,
)

bm25_retriever = BM25Retriever.from_defaults(
    nodes=nodes,  # BM25 需要原始 nodes 来构建倒排索引
    similarity_top_k=BM25_TOP_K,
    # language="zh"   # 如果数据主要是中文可以尝试打开，但目前 BM25 中文分词效果一般
)

# ==================== 7. 融合检索器（RRF - Reciprocal Rank Fusion） ====================
fusion_retriever = QueryFusionRetriever(
    [vector_retriever, bm25_retriever],
    similarity_top_k=SIMILARITY_TOP_K,
    num_queries=1,
    mode="reciprocal_rerank",  # 最推荐的融合方式
    use_async=False, # 设置为 False 以确保 print 在控制台顺序正确
    verbose=True,
)

# ==================== 8. 创建查询引擎 ====================
query_engine = RetrieverQueryEngine.from_args(
    retriever=fusion_retriever,
    llm=llm,
)

# ==================== 实用函数：对比不同检索器的结果 ====================
def print_comparison_retrieval(query: str, top_k: int = 5):
    """对比 Vector, BM25 和 Fusion 的检索结果"""
    print(f"\n{'='*20} 检索对比 (查询: {query}) {'='*20}")
    
    # 1. Vector Retriever
    print(f"\n--- [1] Vector Retriever (TOP {top_k}) ---")
    vector_results = vector_retriever.retrieve(query)
    for i, res in enumerate(vector_results[:top_k], 1):
        content = res.node.text.strip().replace("\n", " ")[:150]
        print(f"{i}. [Score: {res.score:.4f}] {content}...")

    # 2. BM25 Retriever
    print(f"\n--- [2] BM25 Retriever (TOP {top_k}) ---")
    bm25_results = bm25_retriever.retrieve(query)
    for i, res in enumerate(bm25_results[:top_k], 1):
        content = res.node.text.strip().replace("\n", " ")[:150]
        print(f"{i}. [Score: {res.score:.4f}] {content}...")

    # 3. Fusion Retriever
    print(f"\n--- [3] Query Fusion Retriever (TOP {top_k}) ---")
    fusion_results = fusion_retriever.retrieve(query)
    for i, res in enumerate(fusion_results[:top_k], 1):
        content = res.node.text.strip().replace("\n", " ")[:150]
        print(f"{i}. [Score: {res.score:.4f}] {content}...")
    
    print(f"\n{'='*60}\n")

# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 方式1：直接看纯检索结果（推荐先跑这个！）
    test_query = "你的核心问题是什么？例如：公司2024年的主要战略目标是什么？"
    print_comparison_retrieval(test_query, top_k=5)
    
    # 方式2：完整问答（检索 + 生成）
    # response: Response = query_engine.query(test_query)
    # print("\n=== 完整回答 ===\n")
    # print(response.response)
    # print("\n来源：")
    # for src in response.source_nodes:
    #     print(f"[{src.score:.3f}] {src.node.get_text()[:180]}...")