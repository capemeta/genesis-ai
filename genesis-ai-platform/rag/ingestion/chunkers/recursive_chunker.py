"""
递归分块器
"""

from typing import List, Dict, Any, Optional
from .base import BaseChunker


class RecursiveChunker(BaseChunker):
    """
    递归分块器
    
    特点：
    - 递归切分
    - 保持段落完整性
    - 灵活适应不同文档
    
    适用场景：
    - 通用文档
    - 混合格式文档
    
    TODO: 集成 LangChain RecursiveCharacterTextSplitter
    """
    
    def chunk_sync(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        同步递归分块
        
        直接在 Celery Worker 进程中执行
        """
        print(f"[RecursiveChunker] 开始递归分块，文本长度: {len(text)}")
        
        # TODO: 集成 LangChain RecursiveCharacterTextSplitter
        # from langchain.text_splitter import RecursiveCharacterTextSplitter
        # 
        # text_splitter = RecursiveCharacterTextSplitter(
        #     chunk_size=self.chunk_size,
        #     chunk_overlap=self.chunk_overlap,
        #     separators=["\n\n", "\n", "。", "！", "？", " ", ""],
        # )
        # 
        # texts = text_splitter.split_text(text)
        # 
        # chunks = []
        # for i, chunk_text in enumerate(texts):
        #     chunks.append({
        #         "text": chunk_text,
        #         "metadata": {
        #             **(metadata or {}),
        #             "chunk_index": i,
        #             "chunk_strategy": "recursive",
        #         }
        #     })
        
        # 占位实现：简单递归分块
        chunks = self._simple_recursive_chunk(text, metadata or {})
        
        print(f"[RecursiveChunker] 递归分块完成，分块数: {len(chunks)}")
        
        return chunks
    
    def _simple_recursive_chunk(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        简单的递归分块实现（占位）
        
        按分隔符优先级递归切分
        """
        separators = ["\n\n", "\n", "。", "！", "？", " "]
        
        def split_text(text: str, separators: List[str]) -> List[str]:
            """递归切分文本"""
            if not separators or len(text) <= self.chunk_size:
                return [text]
            
            separator = separators[0]
            remaining_separators = separators[1:]
            
            # 按当前分隔符切分
            parts = text.split(separator)
            
            chunks: List[str] = []
            current_chunk = ""
            
            for part in parts:
                if len(current_chunk) + len(part) + len(separator) <= self.chunk_size:
                    if current_chunk:
                        current_chunk += separator + part
                    else:
                        current_chunk = part
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    # 如果单个 part 太长，继续递归切分
                    if len(part) > self.chunk_size:
                        sub_chunks = split_text(part, remaining_separators)
                        chunks.extend(sub_chunks)
                        current_chunk = ""
                    else:
                        current_chunk = part
            
            if current_chunk:
                chunks.append(current_chunk)
            
            return chunks
        
        texts = split_text(text, separators)
        
        chunks: List[Dict[str, Any]] = []
        for i, chunk_text in enumerate(texts):
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "chunk_index": i,
                        "chunk_strategy": "recursive",
                    }
                })
        
        # 如果没有分块，整个文本作为一个分块
        if not chunks:
            chunks.append({
                "text": text,
                "metadata": {
                    **metadata,
                    "chunk_index": 0,
                    "chunk_strategy": "recursive"
                }
            })
        
        return chunks
