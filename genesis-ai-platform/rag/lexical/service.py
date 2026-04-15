"""
检索投影全文索引服务。

职责：
- 基于 chunk_search_units 构建 PostgreSQL 本地全文索引
- 将结果写入 pg_chunk_search_unit_lexical_indexes
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.chunk_search_unit import ChunkSearchUnit
from models.kb_glossary import KBGlossary
from models.knowledge_base import KnowledgeBase
from rag.lexical.text_utils import build_lexical_index_text, normalize_lexical_text


class SearchUnitLexicalIndexService:
    """检索投影全文索引构建服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_indexes_for_chunk_ids(self, *, chunk_ids: list[int]) -> dict[str, Any]:
        """为指定 chunk 的检索投影构建全文索引。"""
        if not chunk_ids:
            return {"indexed_count": 0}

        search_units = await self._load_search_units(chunk_ids)
        if not search_units:
            return {"indexed_count": 0}

        rows: list[dict[str, Any]] = []
        kb_hints_cache: dict[UUID, dict[str, list[str]]] = {}
        for search_unit in search_units:
            metadata = dict(search_unit.metadata_info or {})
            lexical_source_text = str(metadata.get("lexical_text") or search_unit.search_text or "")
            kb_hints = kb_hints_cache.get(search_unit.kb_id)
            if kb_hints is None:
                kb_hints = await self._load_kb_lexical_hints(
                    tenant_id=search_unit.tenant_id,
                    kb_id=search_unit.kb_id,
                )
                kb_hints_cache[search_unit.kb_id] = kb_hints
            matched_hints = self._match_hints_for_text(text=lexical_source_text, hints=kb_hints)
            normalized_text = build_lexical_index_text(
                lexical_source_text,
                priority_terms=matched_hints.get("priority_terms"),
                priority_phrases=matched_hints.get("priority_phrases"),
                glossary_terms=matched_hints.get("glossary_terms"),
                retrieval_stopwords=kb_hints.get("retrieval_stopwords"),
            )
            if not normalized_text:
                continue
            lexical_content_hash = (
                str(search_unit.search_text_hash)
                if str(search_unit.search_text or "").strip() == str(lexical_source_text or "").strip()
                else hashlib.sha256(str(lexical_source_text).strip().encode("utf-8")).hexdigest()
            )
            rows.append(
                {
                    "tenant_id": str(search_unit.tenant_id),
                    "kb_id": str(search_unit.kb_id),
                    "search_unit_id": int(search_unit.id),
                    "lexical_scope": str(search_unit.search_scope),
                    "language_config": "simple",
                    "search_text": normalized_text,
                    "content_hash": lexical_content_hash,
                    "metadata": json.dumps(
                        {
                            "search_scope": search_unit.search_scope,
                            "is_primary": bool(search_unit.is_primary),
                            "priority": int(search_unit.priority or 100),
                        },
                        ensure_ascii=False,
                    ),
                }
            )

        if rows:
            await self._upsert_indexes(rows)

        return {"indexed_count": len(rows)}

    async def _load_search_units(self, chunk_ids: list[int]) -> list[ChunkSearchUnit]:
        """加载需要构建全文索引的检索投影。"""
        stmt = (
            select(ChunkSearchUnit)
            .where(
                ChunkSearchUnit.chunk_id.in_(chunk_ids),
                ChunkSearchUnit.is_active == True,  # noqa: E712
            )
            .order_by(ChunkSearchUnit.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _load_kb_lexical_hints(self, *, tenant_id: UUID, kb_id: UUID) -> dict[str, list[str]]:
        """加载知识库级索引词典候选。"""

        kb = await self.session.get(KnowledgeBase, kb_id)
        kb_query_analysis = dict((kb.retrieval_config or {}).get("query_analysis") or {}) if kb else {}
        retrieval_lexicon = [
            dict(item or {})
            for item in list(kb_query_analysis.get("retrieval_lexicon") or [])
            if isinstance(item, dict)
        ]
        retrieval_stopwords = [
            str(item).strip()
            for item in list(kb_query_analysis.get("retrieval_stopwords") or [])
            if str(item or "").strip()
        ]

        glossary_stmt = (
            select(KBGlossary)
            .where(
                KBGlossary.tenant_id == tenant_id,
                KBGlossary.is_active.is_(True),
                or_(KBGlossary.kb_id == kb_id, KBGlossary.kb_id.is_(None)),
            )
            .order_by(KBGlossary.updated_at.desc())
            .limit(300)
        )
        glossary_rows = list((await self.session.execute(glossary_stmt)).scalars().all())
        glossary_terms = [str(item.term or "").strip() for item in glossary_rows if str(item.term or "").strip()]

        priority_terms: list[str] = []
        priority_phrases: list[str] = []
        for item in retrieval_lexicon[:300]:
            if item.get("enabled", True) is False:
                continue
            term = str(item.get("term") or "").strip()
            aliases = [str(alias).strip() for alias in list(item.get("aliases") or []) if str(alias or "").strip()]
            for value in [term, *aliases]:
                if value and value not in priority_terms:
                    priority_terms.append(value)
            if term and term not in priority_phrases:
                priority_phrases.append(term)

        return {
            "priority_terms": priority_terms,
            "priority_phrases": priority_phrases,
            "glossary_terms": glossary_terms,
            "retrieval_stopwords": retrieval_stopwords,
        }

    def _match_hints_for_text(self, *, text: str, hints: dict[str, list[str]]) -> dict[str, list[str]]:
        """只返回在当前文本中实际出现过的词典项，避免全量词典污染单条索引。"""

        normalized_text = normalize_lexical_text(text)
        result: dict[str, list[str]] = {}
        for key in ("priority_terms", "priority_phrases", "glossary_terms"):
            matched: list[str] = []
            for item in list(hints.get(key) or []):
                normalized_item = normalize_lexical_text(item)
                if normalized_item and normalized_item in normalized_text and item not in matched:
                    matched.append(item)
            result[key] = matched
        return result

    async def _upsert_indexes(self, rows: list[dict[str, Any]]) -> None:
        """批量 upsert 本地全文索引。"""
        stmt = text(
            """
            INSERT INTO pg_chunk_search_unit_lexical_indexes (
                tenant_id,
                kb_id,
                search_unit_id,
                lexical_scope,
                language_config,
                search_text,
                search_vector,
                content_hash,
                is_active,
                metadata
            )
            VALUES (
                CAST(:tenant_id AS uuid),
                CAST(:kb_id AS uuid),
                :search_unit_id,
                :lexical_scope,
                :language_config,
                :search_text,
                to_tsvector('simple', :search_text),
                :content_hash,
                true,
                CAST(:metadata AS jsonb)
            )
            ON CONFLICT (search_unit_id, lexical_scope)
            DO UPDATE SET
                language_config = EXCLUDED.language_config,
                search_text = EXCLUDED.search_text,
                search_vector = EXCLUDED.search_vector,
                content_hash = EXCLUDED.content_hash,
                is_active = true,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            """
        )
        await self.session.execute(stmt, rows)
        await self.session.flush()
