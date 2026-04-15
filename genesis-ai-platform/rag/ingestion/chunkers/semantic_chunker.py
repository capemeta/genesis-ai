"""
语义分块器
"""

from typing import List, Dict, Any, Optional
from .base import BaseChunker


class SemanticChunker(BaseChunker):
    """
    语义分块器
    
    特点：
    - 基于语义相似度
    - 保持语义完整性
    - CPU 密集
    
    适用场景：
    - 需要高质量分块
    - 长文档
    
    TODO: 集成 LlamaIndex SemanticSplitter
    """
    
    def chunk_sync(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        同步语义分块
        
        直接在 Celery Worker 进程中执行
        """
        print(f"[SemanticChunker] 开始语义分块，文本长度: {len(text)}")
        
        # TODO: 集成 LlamaIndex SemanticSplitter
        # from llama_index.core.node_parser import SemanticSplitterNodeParser
        # from llama_index.embeddings.openai import OpenAIEmbedding
        # 
        # embed_model = OpenAIEmbedding()
        # splitter = SemanticSplitterNodeParser(
        #     buffer_size=1,
        #     breakpoint_percentile_threshold=95,
        #     embed_model=embed_model,
        # )
        # 
        # nodes = splitter.get_nodes_from_documents([Document(text=text)])
        # 
        # chunks = []
        # for i, node in enumerate(nodes):
        #     chunks.append({
        #         "text": node.text,
        #         "metadata": {
        #             **(metadata or {}),
        #             "chunk_index": i,
        #             "chunk_strategy": "semantic",
        #         }
        #     })
        
        # 占位实现：简单按句子分块
        chunks = self._simple_semantic_chunk(text, metadata or {})
        
        print(f"[SemanticChunker] 语义分块完成，分块数: {len(chunks)}")
        
        return chunks
    
    def _simple_semantic_chunk(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        简单的语义分块实现（占位）
        
        按句子分块，每个分块包含多个句子
        """
        import re
        
        # 简单的句子分割
        sentences = re.split(r'[。！？\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks: List[Dict[str, Any]] = []
        current_chunk: List[str] = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.chunk_size and current_chunk:
                # 保存当前分块
                chunk_text = '。'.join(current_chunk) + '。'
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "chunk_index": len(chunks),
                        "chunk_strategy": "semantic",
                        "sentence_count": len(current_chunk),
                    }
                })
                
                # 开始新分块（保留重叠）
                overlap_sentences = current_chunk[-1:] if self.chunk_overlap > 0 else []
                current_chunk = overlap_sentences + [sentence]
                current_length = sum(len(s) for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
        
        # 保存最后一个分块
        if current_chunk:
            chunk_text = '。'.join(current_chunk) + '。'
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "chunk_index": len(chunks),
                    "chunk_strategy": "semantic",
                    "sentence_count": len(current_chunk),
                }
            })
        
        # 如果没有分块，整个文本作为一个分块
        if not chunks:
            chunks.append({
                "text": text,
                "metadata": {
                    **metadata,
                    "chunk_index": 0,
                    "chunk_strategy": "semantic"
                }
            })
        
        return chunks
