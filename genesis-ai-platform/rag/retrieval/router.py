"""
检索后端路由工厂
"""
from sqlalchemy.ext.asyncio import AsyncSession

from rag.retrieval.backends import (
    LexicalSearchBackend,
    MilvusLexicalSearchBackend,
    MilvusVectorSearchBackend,
    PGFTSSearchBackend,
    PGVectorSearchBackend,
    QdrantLexicalSearchBackend,
    QdrantSearchBackend,
    VectorSearchBackend,
)
from rag.retrieval.config import get_active_search_backends


def get_vector_search_backend(session: AsyncSession) -> VectorSearchBackend:
    """根据当前配置返回向量检索后端实例。"""
    active = get_active_search_backends()
    if active.vector_backend == "pg_vector":
        return PGVectorSearchBackend(session)
    if active.vector_backend == "qdrant":
        return QdrantSearchBackend()
    if active.vector_backend == "milvus":
        return MilvusVectorSearchBackend()
    raise ValueError(f"不支持的向量检索后端: {active.vector_backend}")


def get_lexical_search_backend(session: AsyncSession) -> LexicalSearchBackend:
    """根据当前配置返回全文检索后端实例。"""
    active = get_active_search_backends()
    if active.lexical_backend == "pg_fts":
        return PGFTSSearchBackend(session)
    if active.lexical_backend == "qdrant":
        return QdrantLexicalSearchBackend()
    if active.lexical_backend == "milvus":
        return MilvusLexicalSearchBackend()
    raise ValueError(f"不支持的全文检索后端: {active.lexical_backend}")
