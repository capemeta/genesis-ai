"""
检索后端抽象基类
"""
from abc import ABC, abstractmethod
from typing import List

from rag.retrieval.types import LexicalSearchRequest, SearchHit, VectorSearchRequest


class VectorSearchBackend(ABC):
    """向量检索后端抽象接口。"""

    backend_type: str

    @abstractmethod
    async def search(self, request: VectorSearchRequest) -> List[SearchHit]:
        """执行向量检索。"""
        raise NotImplementedError


class LexicalSearchBackend(ABC):
    """全文检索后端抽象接口。"""

    backend_type: str

    @abstractmethod
    async def search(self, request: LexicalSearchRequest) -> List[SearchHit]:
        """执行全文检索。"""
        raise NotImplementedError
