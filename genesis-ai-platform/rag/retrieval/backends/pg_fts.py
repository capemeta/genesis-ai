"""
PostgreSQL 全文检索后端
"""
from typing import List

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from rag.lexical.analysis.scoring import normalize_lexical_score
from rag.lexical.text_utils import build_pg_fts_query_payload
from rag.retrieval.backends.base import LexicalSearchBackend
from rag.retrieval.filter_expression import build_search_unit_expression_sql, collect_expanding_param_names
from rag.retrieval.types import LexicalSearchRequest, SearchHit


class PGFTSSearchBackend(LexicalSearchBackend):
    """当前 PostgreSQL FTS 后端。"""

    backend_type = "pg_fts"

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(self, request: LexicalSearchRequest) -> List[SearchHit]:
        """执行 PostgreSQL FTS 检索。"""
        if not str(request.query or "").strip():
            return []

        query_payload = build_pg_fts_query_payload(
            str(request.query or ""),
            priority_terms=list(request.priority_terms or []),
            priority_phrases=list(request.priority_phrases or []),
            synonym_terms=list(request.synonym_terms or []),
            glossary_terms=list(request.glossary_terms or []),
            retrieval_stopwords=list(request.retrieval_stopwords or []),
            lexicon_weights=request.lexicon_weights,
        )
        strict_query_text = str(query_payload.get("strict_query_text") or "").strip()
        loose_query_text = str(query_payload.get("loose_query_text") or "").strip()
        fallback_query_text = str(query_payload.get("fallback_query_text") or "").strip()
        phrase_pattern = query_payload.get("phrase_pattern")

        # 动态权重提取
        p_phrase_weights = list(query_payload.get("priority_phrase_weights") or [])
        p_term_weights = list(query_payload.get("priority_term_weights") or [])

        # 转换为 SQL 参数名和值的映射
        p_phrase_p1 = p_phrase_weights[0]["pattern"] if len(p_phrase_weights) > 0 else None
        p_phrase_w1 = p_phrase_weights[0]["weight"] if len(p_phrase_weights) > 0 else 0.0
        p_phrase_p2 = p_phrase_weights[1]["pattern"] if len(p_phrase_weights) > 1 else None
        p_phrase_w2 = p_phrase_weights[1]["weight"] if len(p_phrase_weights) > 1 else 0.0
        p_phrase_p3 = p_phrase_weights[2]["pattern"] if len(p_phrase_weights) > 2 else None
        p_phrase_w3 = p_phrase_weights[2]["weight"] if len(p_phrase_weights) > 2 else 0.0

        p_term_p1 = p_term_weights[0]["pattern"] if len(p_term_weights) > 0 else None
        p_term_w1 = p_term_weights[0]["weight"] if len(p_term_weights) > 0 else 0.0
        p_term_p2 = p_term_weights[1]["pattern"] if len(p_term_weights) > 1 else None
        p_term_w2 = p_term_weights[1]["weight"] if len(p_term_weights) > 1 else 0.0
        p_term_p3 = p_term_weights[2]["pattern"] if len(p_term_weights) > 2 else None
        p_term_w3 = p_term_weights[2]["weight"] if len(p_term_weights) > 2 else 0.0

        if (
            not strict_query_text
            and not loose_query_text
            and not fallback_query_text
            and not phrase_pattern
            and not p_phrase_p1
            and not p_term_p1
        ):
            return []

        sql = """
            WITH lexical_query AS (
                SELECT
                    CASE
                        WHEN :strict_query_text = '' THEN NULL
                        ELSE plainto_tsquery('simple', :strict_query_text)
                    END AS strict_query,
                    CASE
                        WHEN :loose_query_text = '' THEN NULL
                        ELSE to_tsquery('simple', :loose_query_text)
                    END AS loose_query,
                    CASE
                        WHEN :fallback_query_text = '' THEN NULL
                        ELSE to_tsquery('simple', :fallback_query_text)
                    END AS fallback_query
            )
            SELECT
                su.id AS search_unit_id,
                su.chunk_id AS chunk_id,
                su.kb_id AS kb_id,
                su.kb_doc_id AS kb_doc_id,
                su.document_id AS document_id,
                su.content_group_id AS content_group_id,
                su.search_scope AS search_scope,
                (
                    CASE
                        WHEN lexical_query.strict_query IS NOT NULL
                        THEN ts_rank_cd(lex.search_vector, lexical_query.strict_query) * 0.72
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN lexical_query.loose_query IS NOT NULL
                        THEN ts_rank_cd(lex.search_vector, lexical_query.loose_query) * 0.28
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN lexical_query.fallback_query IS NOT NULL
                        THEN ts_rank_cd(lex.search_vector, lexical_query.fallback_query) * 0.08
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN CAST(:p_phrase_p1 AS text) IS NOT NULL
                             AND lex.search_text ILIKE CAST(:p_phrase_p1 AS text)
                        THEN CAST(:p_phrase_w1 AS float) * 0.9
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN CAST(:p_phrase_p2 AS text) IS NOT NULL
                             AND lex.search_text ILIKE CAST(:p_phrase_p2 AS text)
                        THEN CAST(:p_phrase_w2 AS float) * 0.45
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN CAST(:p_phrase_p3 AS text) IS NOT NULL
                             AND lex.search_text ILIKE CAST(:p_phrase_p3 AS text)
                        THEN CAST(:p_phrase_w3 AS float) * 0.25
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN CAST(:p_term_p1 AS text) IS NOT NULL
                             AND lex.search_text ILIKE CAST(:p_term_p1 AS text)
                        THEN CAST(:p_term_w1 AS float) * 0.08
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN CAST(:p_term_p2 AS text) IS NOT NULL
                             AND lex.search_text ILIKE CAST(:p_term_p2 AS text)
                        THEN CAST(:p_term_w2 AS float) * 0.04
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN CAST(:p_term_p3 AS text) IS NOT NULL
                             AND lex.search_text ILIKE CAST(:p_term_p3 AS text)
                        THEN CAST(:p_term_w3 AS float) * 0.03
                        ELSE 0
                    END
                    +
                    CASE
                        WHEN CAST(:phrase_pattern AS text) IS NOT NULL
                             AND lex.search_text ILIKE CAST(:phrase_pattern AS text)
                        THEN CASE
                            WHEN su.search_scope = 'question' THEN 0.45
                            WHEN su.search_scope = 'row' THEN 0.4
                            WHEN su.search_scope = 'row_group' THEN 0.38
                            WHEN su.search_scope = 'row_fragment' THEN 0.36
                            WHEN su.search_scope = 'answer' THEN 0.35
                            WHEN su.search_scope = 'keyword' THEN 0.35
                            WHEN su.search_scope = 'summary' THEN 0.32
                            ELSE 0.35
                        END
                        ELSE 0
                    END
                ) AS score,
                su.metadata AS metadata
            FROM pg_chunk_search_unit_lexical_indexes lex
            JOIN chunk_search_units su ON su.id = lex.search_unit_id
            JOIN chunks c ON c.id = su.chunk_id
            JOIN knowledge_base_documents kbd ON kbd.id = su.kb_doc_id
            CROSS JOIN lexical_query
            WHERE
                lex.tenant_id = CAST(:tenant_id AS uuid)
                AND lex.kb_id = CAST(:kb_id AS uuid)
                AND lex.is_active = true
                AND kbd.tenant_id = CAST(:tenant_id AS uuid)
                AND kbd.kb_id = CAST(:kb_id AS uuid)
                AND kbd.parse_status = 'completed'
                AND kbd.is_enabled = true
                AND su.is_active = true
                AND c.is_active = true
                AND (
                    (lexical_query.strict_query IS NOT NULL AND lex.search_vector @@ lexical_query.strict_query)
                    OR (lexical_query.loose_query IS NOT NULL AND lex.search_vector @@ lexical_query.loose_query)
                    OR (lexical_query.fallback_query IS NOT NULL AND lex.search_vector @@ lexical_query.fallback_query)
                )
        """
        params = {
            "tenant_id": str(request.tenant_id),
            "kb_id": str(request.kb_id),
            "strict_query_text": strict_query_text,
            "loose_query_text": loose_query_text,
            "fallback_query_text": fallback_query_text,
            "phrase_pattern": phrase_pattern,
            "p_phrase_p1": p_phrase_p1,
            "p_phrase_w1": p_phrase_w1,
            "p_phrase_p2": p_phrase_p2,
            "p_phrase_w2": p_phrase_w2,
            "p_phrase_p3": p_phrase_p3,
            "p_phrase_w3": p_phrase_w3,
            "p_term_p1": p_term_p1,
            "p_term_w1": p_term_w1,
            "p_term_p2": p_term_p2,
            "p_term_w2": p_term_w2,
            "p_term_p3": p_term_p3,
            "p_term_w3": p_term_w3,
            "top_k": max(1, int(request.top_k or 10)),
        }

        if request.search_scopes:
            sql += " AND su.search_scope IN :search_scopes"

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

        sql += " ORDER BY score DESC, su.priority ASC LIMIT :top_k"

        bind_params = []
        if request.search_scopes:
            bind_params.append(bindparam("search_scopes", expanding=True))
            params["search_scopes"] = list(request.search_scopes)
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
        hits: list[SearchHit] = []
        for row in rows:
            raw_score = float(row["score"] or 0.0)
            metadata = dict(row["metadata"] or {})
            metadata["lexical_raw_score"] = round(raw_score, 4)
            metadata["lexical_score"] = normalize_lexical_score(raw_score)
            metadata["lexical_score_normalization"] = "raw / (raw + 0.8)"
            hits.append(
                SearchHit(
                    search_unit_id=int(row["search_unit_id"]),
                    chunk_id=int(row["chunk_id"]),
                    kb_id=row["kb_id"],
                    kb_doc_id=row["kb_doc_id"],
                    document_id=row["document_id"],
                    content_group_id=row["content_group_id"],
                    search_scope=str(row["search_scope"]),
                    score=float(metadata["lexical_score"]),
                    backend_type=self.backend_type,
                    metadata=metadata,
                )
            )
        return hits
