"""
Chat Engine - RAG 对话引擎
基于向量检索的问答系统
"""
from typing import Optional, List
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.schema import NodeWithScore
from .base import BaseEngine


class ChatEngine(BaseEngine):
    """RAG 对话引擎 - 基于向量检索的问答"""
    
    def __init__(self, data_dir: Optional[str] = None, similarity_top_k: int = 3):
        """
        初始化 RAG 引擎
        
        Args:
            data_dir: 数据目录路径
            similarity_top_k: 检索时返回的相似文档数量
        """
        super().__init__(data_dir)
        self.similarity_top_k = similarity_top_k
        self.index = None
        self.chat_engine = None
        self._initialize()
    
    def _initialize(self):
        """初始化索引和聊天引擎"""
        print(f"📚 加载数据目录: {self.data_dir}")
        documents = SimpleDirectoryReader(self.data_dir).load_data()
        print(f"✅ 已加载 {len(documents)} 个文档")
        
        # 创建索引（自动使用 Settings 中的 embed_model）
        self.index = VectorStoreIndex.from_documents(documents)
        
        # 创建聊天引擎（自动使用 Settings 中的 llm）
        self.chat_engine = self.index.as_chat_engine(
            chat_mode="condense_question",
            verbose=True
        )
        print(f"🚀 RAG 引擎初始化完成")
    
    def retrieve(self, query: str) -> List[NodeWithScore]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            
        Returns:
            List[NodeWithScore]: 检索到的文档节点
        """
        retriever = self.index.as_retriever(similarity_top_k=self.similarity_top_k)
        return retriever.retrieve(query)
    
    async def aretrieve(self, query: str) -> List[NodeWithScore]:
        """
        异步检索相关文档
        """
        retriever = self.index.as_retriever(similarity_top_k=self.similarity_top_k)
        return await retriever.aretrieve(query)
    
    def chat(self, message: str) -> str:
        """同步对话"""
        response = self.chat_engine.chat(message)
        return str(response)
    
    async def achat(self, message: str) -> str:
        """异步对话"""
        response = await self.chat_engine.achat(message)
        return str(response)
    
    def stream_chat(self, message: str):
        """流式对话（同步）"""
        response = self.chat_engine.stream_chat(message)
        for token in response.response_gen:
            yield token
    
    async def astream_chat(self, message: str):
        """流式对话（异步）"""
        response = await self.chat_engine.astream_chat(message)
        async for token in response.async_response_gen():
            yield token
