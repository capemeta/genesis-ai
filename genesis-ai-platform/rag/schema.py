from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

class Rect(BaseModel):
    """坐标区域 [x, y, w, h] 分数坐标 (0-1)"""
    x: float
    y: float
    w: float
    h: float

class BaseChunk(BaseModel):
    """解析出的基础切片结构"""
    content: str
    chunk_type: str = "text"  # text, table, image, header, footer
    page_numbers: List[int] = Field(default_factory=list)
    bbox: List[List[float]] = Field(default_factory=list)  # 对应坐标
    metadata: Dict[str, Any] = Field(default_factory=dict)
    position: int = 0  # 在文档中的顺序

class ParsedDocument(BaseModel):
    """解析后的文档全量信息"""
    doc_id: UUID
    kb_doc_id: UUID
    chunks: List[BaseChunk]
    token_count: int = 0
    summary: Optional[str] = None
    parsing_logs: List[Dict[str, Any]] = Field(default_factory=list)
