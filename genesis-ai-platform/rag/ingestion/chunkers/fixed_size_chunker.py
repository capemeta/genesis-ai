"""
固定长度分块器
"""

import logging
from typing import List, Dict, Any, Optional
from .base import BaseChunker

logger = logging.getLogger(__name__)


class FixedSizeChunker(BaseChunker):
    """
    固定长度分块器
    
    特点：
    - 简单快速
    - 固定长度
    - 支持重叠
    
    适用场景：
    - 简单文档
    - 快速处理
    """
    
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        固定长度分块
        """
        logger.info(f"[FixedSizeChunker] 开始分块，文本长度: {len(text)}, 分块大小: {self.chunk_size}")
        
        chunks: List[Dict[str, Any]] = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    **(metadata or {}),
                    "chunk_index": len(chunks),
                    "chunk_size": len(chunk_text),
                    "chunk_strategy": "fixed_size"
                }
            })
            
            start += self.chunk_size - self.chunk_overlap
        
        logger.info(f"[FixedSizeChunker] 分块完成，分块数: {len(chunks)}")
        
        return chunks
