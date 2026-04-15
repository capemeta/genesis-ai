import os
from config import Settings # 从 base 导入 Settings，确保了 base 被执行且 Settings 可用
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.storage.index_store import SimpleIndexStore
from llama_index.core.vector_stores import SimpleVectorStore
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.storage import StorageContext
from llama_index.core.ingestion import IngestionPipeline, IngestionCache
# 获取数据路径
current_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(current_dir, "../data")

# 加载数据
documents = SimpleDirectoryReader(data_path).load_data()
embedding_mode = Settings.embed_model
llm = Settings.llm

print(documents)

sentence_splitter =  SentenceSplitter(
    chunk_size=500, 
    chunk_overlap=100,
    paragraph_separator="\n\n",  # 中文常用双换行
    secondary_chunking_regex="[^。！？]+[。！？]?"  # 中文标点分割
)
nodes = sentence_splitter.get_nodes_from_documents(documents)
print(f"Total chunks: {len(nodes)}")
embedding_mode
for i,node in enumerate(nodes):
    print(f"Chunk {i+1} (Length: {len(node.text)}): {node.text}")
    print("-" * 100)

print("***" * 30 + "完毕" + "***" * 30)

storage_context = StorageContext.from_defaults(

    docstore=SimpleDocumentStore(),
    vector_store=SimpleVectorStore(),
    index_store=SimpleIndexStore(),
)



# 创建索引 (会自动使用 base 中配置好的 Settings.embed_model)
index = VectorStoreIndex.from_documents(documents, storage_context= storage_context,embed_model=Settings.embed_model)

# 启动聊天引擎
chat_engine = index.as_chat_engine(llm = llm, chat_mode="condense_question", verbose=True)
response = chat_engine.chat("上下文说了什么?")

print("\n--- AI 回复 ---")

print(response)