"""
Qdrant 检索后端骨架。
"""

from typing import List

from rag.lexical.analysis import get_default_lexical_analyzer
from rag.lexical.analysis.types import LexicalAnalyzerInput
from rag.retrieval.backends.base import LexicalSearchBackend, VectorSearchBackend
from rag.retrieval.types import LexicalSearchRequest, SearchHit, VectorSearchRequest


class QdrantVectorSearchBackend(VectorSearchBackend):
    """Qdrant 向量检索后端骨架。"""

    backend_type = "qdrant"

    async def search(self, request: VectorSearchRequest) -> List[SearchHit]:
        """执行 Qdrant 向量检索。

        TODO:
        1. 建立 Qdrant client
        2. 按 `chunk_search_units` 投影规则组织 payload
        3. 将结果转换成统一 `SearchHit`
        """
        raise NotImplementedError("Qdrant 向量检索后端尚未实现")


class QdrantLexicalSearchBackend(LexicalSearchBackend):
    """Qdrant 全文 / 稀疏检索后端骨架。"""

    backend_type = "qdrant_lexical"

    async def search(self, request: LexicalSearchRequest) -> List[SearchHit]:
        """执行 Qdrant 全文检索。

        TODO:
        1. 按 Qdrant text index / sparse BM25 方案确定 collection schema
        2. 使用统一 `LexicalAnalyzer` 输出构造 sparse/BM25 查询或 text filter
        3. 将 Qdrant payload 映射回统一 `SearchHit`
        """
        _analysis = get_default_lexical_analyzer().analyze(
            LexicalAnalyzerInput(
                text=request.query,
                mode="query",
                priority_terms=list(request.priority_terms or []),
                priority_phrases=list(request.priority_phrases or []),
                synonym_terms=list(request.synonym_terms or []),
                glossary_terms=list(request.glossary_terms or []),
                retrieval_stopwords=list(request.retrieval_stopwords or []),
            )
        )
        raise NotImplementedError("Qdrant 全文检索后端尚未实现")


# 兼容旧导入名。
QdrantSearchBackend = QdrantVectorSearchBackend
