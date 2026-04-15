import os
from config import Settings # 从 base 导入 Settings，确保了 base 被执行且 Settings 可用
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# 获取数据路径
current_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(current_dir, "../data")

# 加载数据
documents = SimpleDirectoryReader(data_path).load_data()

print(documents)

# 创建索引 (会自动使用 base 中配置好的 Settings.embed_model)
index = VectorStoreIndex.from_documents(documents)

# 启动聊天引擎 (会自动使用 base 中配置好的 Settings.llm)
chat_engine = index.as_chat_engine(chat_mode="condense_question", verbose=True)
response = chat_engine.chat("上下文说了什么?")

print("\n--- AI 回复 ---")
print(response)