"""
PostgreSQL pgvector 检索后端
"""
from typing import List

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from rag.pgvector_utils import (
    build_vector_cast_type,
    ensure_pgvector_dimension_compatible,
    get_pgvector_embedding_dimension,
)
from rag.retrieval.backends.base import VectorSearchBackend
from rag.retrieval.filter_expression import build_search_unit_expression_sql, collect_expanding_param_names
from rag.retrieval.types import SearchHit, VectorSearchRequest


class PGVectorSearchBackend(VectorSearchBackend):
    """当前 PostgreSQL pgvector 后端。"""

    backend_type = "pg_vector"

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(self, request: VectorSearchRequest) -> List[SearchHit]:
        """执行 pgvector 向量检索。"""
        if not request.query_embedding:
            return []

        query_dimension = int(request.query_embedding_dimension or len(request.query_embedding))
        index_dimension = await get_pgvector_embedding_dimension(self.session)
        ensure_pgvector_dimension_compatible(
            actual_dimension=query_dimension,
            index_dimension=index_dimension,
            scene="向量检索",
        )
        vector_cast_type = build_vector_cast_type(
            index_dimension=index_dimension,
            fallback_dimension=query_dimension,
        )
        query_embedding = self._format_vector_literal(request.query_embedding)
        sql = """
            SELECT
                su.id AS search_unit_id,
                su.chunk_id AS chunk_id,
                su.kb_id AS kb_id,
                su.kb_doc_id AS kb_doc_id,
                su.document_id AS document_id,
                su.content_group_id AS content_group_id,
                su.search_scope AS search_scope,
                1 - (CAST(vec.embedding AS __VECTOR_CAST_TYPE__) <=> CAST(:query_embedding AS __VECTOR_CAST_TYPE__)) AS score,
                su.metadata AS metadata
            FROM pg_chunk_search_unit_vectors vec
            JOIN chunk_search_units su ON su.id = vec.search_unit_id
            JOIN chunks c ON c.id = su.chunk_id
            JOIN knowledge_base_documents kbd ON kbd.id = su.kb_doc_id
            WHERE
                vec.tenant_id = CAST(:tenant_id AS uuid)
                AND vec.kb_id = CAST(:kb_id AS uuid)
                AND vec.is_active = true
                AND vec.embedding_dimension = :query_embedding_dimension
                AND kbd.tenant_id = CAST(:tenant_id AS uuid)
                AND kbd.kb_id = CAST(:kb_id AS uuid)
                AND kbd.parse_status = 'completed'
                AND kbd.is_enabled = true
                AND su.is_active = true
                AND c.is_active = true
        """
        params = {
            "tenant_id": str(request.tenant_id),
            "kb_id": str(request.kb_id),
            "query_embedding": query_embedding,
            "query_embedding_dimension": query_dimension,
            "top_k": max(1, int(request.top_k or 10)),
        }

        if request.search_scopes:
            sql += " AND su.search_scope IN :search_scopes"
            params["search_scopes"] = list(request.search_scopes)

        if request.metadata_filters:
            sql += " AND su.metadata @> CAST(:metadata_filters AS jsonb)"
            params["metadata_filters"] = request.metadata_filters

        metadata_expression_sql = ""
        if request.metadata_filter_expression:
            metadata_expression_sql = build_search_unit_expression_sql(
                expression=request.metadata_filter_expression,
                params=params,
                prefix="su_expr",
            )
            if metadata_expression_sql:
                sql += f" AND {metadata_expression_sql}"

        if request.kb_doc_ids:
            sql += " AND su.kb_doc_id IN :kb_doc_ids"
            params["kb_doc_ids"] = list(request.kb_doc_ids)

        if request.document_ids:
            sql += " AND su.document_id IN :document_ids"
            params["document_ids"] = list(request.document_ids)

        if request.content_group_ids:
            sql += " AND su.content_group_id IN :content_group_ids"
            params["content_group_ids"] = list(request.content_group_ids)

        if request.display_only:
            sql += " AND c.display_enabled = true"

        if request.leaf_only:
            # 默认按叶子块召回，父块主要在召回后补上下文。
            sql += " AND COALESCE((c.metadata->>'is_leaf')::boolean, true) = true"

        sql += " ORDER BY CAST(vec.embedding AS __VECTOR_CAST_TYPE__) <=> CAST(:query_embedding AS __VECTOR_CAST_TYPE__) ASC LIMIT :top_k"
        sql = sql.replace("__VECTOR_CAST_TYPE__", vector_cast_type)
        bind_params = []
        if request.search_scopes:
            bind_params.append(bindparam("search_scopes", expanding=True))
        if request.kb_doc_ids:
            bind_params.append(bindparam("kb_doc_ids", expanding=True))
        if request.document_ids:
            bind_params.append(bindparam("document_ids", expanding=True))
        if request.content_group_ids:
            bind_params.append(bindparam("content_group_ids", expanding=True))
        for name in collect_expanding_param_names(metadata_expression_sql, "su_expr"):
            bind_params.append(bindparam(name, expanding=True))
        stmt = text(sql).bindparams(*bind_params) if bind_params else text(sql)

        result = await self.session.execute(stmt, params)
        rows = result.mappings().all()
        return [
            SearchHit(
                search_unit_id=int(row["search_unit_id"]),
                chunk_id=int(row["chunk_id"]),
                kb_id=row["kb_id"],
                kb_doc_id=row["kb_doc_id"],
                document_id=row["document_id"],
                content_group_id=row["content_group_id"],
                search_scope=str(row["search_scope"]),
                score=float(row["score"] or 0.0),
                backend_type=self.backend_type,
                metadata=dict(row["metadata"] or {}),
            )
            for row in rows
        ]

    def _format_vector_literal(self, embedding: List[float]) -> str:
        """将查询向量转成 pgvector 字面量。"""
        if not embedding:
            raise ValueError("query_embedding 不能为空")
        return "[" + ",".join(format(float(item), ".12g") for item in embedding) + "]"
