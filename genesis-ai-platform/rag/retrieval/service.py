"""
检索执行服务骨架
"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from rag.retrieval.router import get_lexical_search_backend, get_vector_search_backend
from rag.retrieval.types import LexicalSearchRequest, SearchHit, VectorSearchRequest


class RetrievalExecutionService:
    """统一检索执行入口。

    当前阶段作用：
    - 固定上层只依赖一个统一 service
    - 内部按配置路由到具体后端
    - 真实 PG / Qdrant / ES 实现后续补齐
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def vector_search(self, request: VectorSearchRequest) -> List[SearchHit]:
        """执行向量检索。"""
        backend = get_vector_search_backend(self.session)
        return await backend.search(request)

    async def lexical_search(self, request: LexicalSearchRequest) -> List[SearchHit]:
        """执行全文检索。"""
        backend = get_lexical_search_backend(self.session)
        return await backend.search(request)
