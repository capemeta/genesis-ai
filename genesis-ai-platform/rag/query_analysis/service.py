"""
查询分析服务。

当前策略：
- 同义词改写默认启用，优先用于检索语义对齐
- 自动过滤提取默认关闭，仅在显式开启时使用规则型高置信命中
- 专业术语用于补充生成阶段上下文，不直接参与硬过滤

后续可扩展：
- 在本模块中接入 LLM 查询分析
- 引入多轮对话上下文感知的过滤补全
- 引入术语、标签、目录的更复杂置信度融合
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, case, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.folder import Folder
from models.kb_glossary import KBGlossary
from models.kb_synonym import KBSynonym
from models.kb_synonym_variant import KBSynonymVariant
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.resource_tag import TARGET_TYPE_FOLDER, TARGET_TYPE_KB_DOC, ResourceTag
from models.tag import Tag
from models.user import User
from rag.llm.executor import LLMExecutor, LLMRequest
from rag.lexical.analysis.stopwords import filter_exact_stopword_terms, merge_stopwords
from rag.query_analysis.types import (
    AnalyzedQuery,
    QueryAnalysisAutoFilterSignal,
    QueryAnalysisConfig,
    QueryAnalysisFilterCandidate,
    QueryAnalysisGlossaryEntry,
    QueryAnalysisLexiconMatch,
    QueryAnalysisSynonymMatch,
)
from rag.retrieval.filter_expression import normalize_filter_expression
from rag.retrieval.types import RetrievalFilterSet

logger = logging.getLogger(__name__)


def _normalize_text(value: str) -> str:
    """统一文本归一化口径。"""

    return " ".join(str(value or "").strip().split())


class QueryAnalysisService:
    """统一查询分析服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        query: str,
        filters: RetrievalFilterSet,
        config: QueryAnalysisConfig,
    ) -> AnalyzedQuery:
        """执行查询分析。"""

        raw_query = _normalize_text(query)
        locked_filters = self._clone_filters(filters)
        resolved_filters = self._clone_filters(filters)

        standalone_query = raw_query
        query_rewrite_debug: dict[str, Any] | None = None
        if bool(getattr(config, "enable_query_rewrite", False)):
            standalone_query, query_rewrite_debug = await self._rewrite_query_by_llm(
                current_user=current_user,
                kb=kb,
                query=raw_query,
                rewrite_context=list(getattr(config, "query_rewrite_context", []) or []),
            )

        synonym_matches: list[QueryAnalysisSynonymMatch] = []
        rewritten_query = standalone_query
        if bool(getattr(config, "enable_synonym_rewrite", True)):
            rewritten_query, synonym_matches = await self._rewrite_query_by_synonyms(
                tenant_id=current_user.tenant_id,
                kb_id=kb.id,
                query=standalone_query,
            )

        rewritten_query, retrieval_lexicon_matches = self._apply_retrieval_lexicon(
            query=rewritten_query,
            retrieval_lexicon=config.retrieval_lexicon,
        )
        retrieval_stopwords = self._normalize_retrieval_stopwords(config.retrieval_stopwords)

        filter_candidates: list[QueryAnalysisFilterCandidate] = []
        llm_debug: dict[str, Any] | None = None
        rule_candidates: list[QueryAnalysisFilterCandidate] = []
        if config.auto_filter_mode in {"rule", "hybrid"}:
            rule_candidates = await self._extract_rule_based_filters(
                tenant_id=current_user.tenant_id,
                kb=kb,
                query=rewritten_query,
                existing_filters=locked_filters,
                metadata_fields=config.metadata_fields,
            )
            filter_candidates.extend(rule_candidates)
            if config.auto_filter_mode == "rule":
                resolved_filters = self._apply_filter_candidates(
                    filters=resolved_filters,
                    candidates=rule_candidates,
                )
        if config.auto_filter_mode in {"llm_candidate", "hybrid"} and config.enable_llm_candidate_extraction:
            llm_candidates, llm_debug = await self._extract_llm_filter_candidates(
                current_user=current_user,
                kb=kb,
                query=rewritten_query,
                rule_candidates=rule_candidates,
                metadata_fields=config.metadata_fields,
            )
            llm_candidates = self._validate_llm_candidates(
                candidates=llm_candidates,
                existing_filters=locked_filters,
                rule_candidates=rule_candidates,
                metadata_fields=config.metadata_fields,
                raw_query=raw_query,
                standalone_query=standalone_query,
                rewritten_query=rewritten_query,
                min_confidence=config.llm_candidate_min_confidence,
                allow_rule_override=config.auto_filter_mode == "hybrid",
            )
            if llm_debug is None:
                llm_debug = {}
            llm_debug.update(
                {
                    "min_confidence": round(config.llm_candidate_min_confidence, 4),
                    "upgrade_confidence_threshold": round(config.llm_upgrade_confidence_threshold, 4),
                    "max_upgrade_count": max(1, int(config.llm_max_upgrade_count)),
                }
            )
            llm_debug.update(
                {
                    "validated_candidate_count": len(
                        [item for item in llm_candidates if item.validation_status == "validated"]
                    ),
                    "rejected_candidate_count": len(
                        [item for item in llm_candidates if item.validation_status == "rejected"]
                    ),
                    "conflict_candidate_count": len(
                        [item for item in llm_candidates if item.validation_status == "conflicted"]
                    ),
                    "evidence_type_distribution": self._build_candidate_evidence_distribution(
                        candidates=llm_candidates,
                    ),
                }
            )
            if config.auto_filter_mode == "hybrid":
                rule_candidates = self._reconcile_rule_candidates_with_llm(
                    rule_candidates=rule_candidates,
                    llm_candidates=llm_candidates,
                    correction_confidence_threshold=config.llm_upgrade_confidence_threshold,
                )
                resolved_filters = self._apply_filter_candidates(
                    filters=resolved_filters,
                    candidates=rule_candidates,
                )
                resolved_filters = self._apply_validated_llm_candidates(
                    filters=resolved_filters,
                    candidates=llm_candidates,
                    upgrade_confidence_threshold=config.llm_upgrade_confidence_threshold,
                    max_upgrade_count=config.llm_max_upgrade_count,
                )
                llm_debug["upgraded_candidate_count"] = len(
                    [item for item in llm_candidates if item.upgraded_to_hard_filter]
                )
                llm_debug["rule_corrected_by_llm_count"] = len(
                    [item for item in rule_candidates if item.validation_status == "corrected_by_llm"]
                )
            llm_expression = dict(llm_debug.get("filter_expression") or {})
            if config.enable_llm_filter_expression and llm_expression:
                resolved_filters.filter_expression = self._merge_filter_expressions(
                    locked_expression=resolved_filters.filter_expression,
                    additive_expression=llm_expression,
                )
                llm_debug["filter_expression_applied"] = bool(resolved_filters.filter_expression)
                llm_debug["filter_expression_merge_mode"] = (
                    "and_append" if filters.filter_expression else "llm_only"
                )
            elif llm_expression:
                llm_debug["filter_expression_applied"] = False
            llm_debug.update(self._build_llm_candidate_metrics(candidates=llm_candidates))
            filter_candidates.extend(llm_candidates)

        auto_filter_signals = self._build_auto_filter_signals(
            candidates=filter_candidates,
            metadata_fields=config.metadata_fields,
        )

        glossary_entries = await self._resolve_glossary_entries(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
            query=rewritten_query,
            synonym_matches=synonym_matches,
            max_terms=config.max_glossary_terms,
        )

        lexical_query = self._build_lexical_query(
            raw_query=raw_query,
            rewritten_query=rewritten_query,
            synonym_matches=synonym_matches,
            retrieval_lexicon_matches=retrieval_lexicon_matches,
            retrieval_stopwords=retrieval_stopwords,
        )
        ignored_lexical_terms = self._collect_ignored_lexical_terms(
            source_terms=[
                raw_query,
                rewritten_query,
                *[item.professional_term for item in synonym_matches],
                *[item.term for item in retrieval_lexicon_matches],
                *[
                    alias
                    for item in retrieval_lexicon_matches
                    for alias in item.aliases
                ],
            ],
            retrieval_stopwords=retrieval_stopwords,
        )
        priority_lexical_terms, priority_lexical_phrases, lexicon_weights = self._build_priority_lexical_hints(
            retrieval_lexicon_matches=retrieval_lexicon_matches,
            glossary_entries=glossary_entries,
        )
        resolved_filter_labels = await self._build_resolved_filter_labels(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
            filters=resolved_filters,
            filter_candidates=filter_candidates,
        )
        return AnalyzedQuery(
            raw_query=raw_query,
            standalone_query=standalone_query,
            rewritten_query=rewritten_query,
            lexical_query=lexical_query,
            retrieval_filters=resolved_filters,
            synonym_matches=synonym_matches,
            glossary_entries=glossary_entries,
            retrieval_lexicon_matches=retrieval_lexicon_matches,
            ignored_lexical_terms=ignored_lexical_terms,
            retrieval_stopwords=retrieval_stopwords,
            extra_retrieval_stopwords=list(getattr(config, "extra_retrieval_stopwords", []) or []),
            priority_lexical_terms=priority_lexical_terms,
            priority_lexical_phrases=priority_lexical_phrases,
            lexicon_weights=lexicon_weights,
            filter_candidates=filter_candidates,
            auto_filter_signals=auto_filter_signals,
            query_rewrite_debug=query_rewrite_debug,
            llm_debug=llm_debug,
            resolved_filter_labels=resolved_filter_labels,
        )

    async def _build_resolved_filter_labels(
        self,
        *,
        tenant_id: UUID,
        kb_id: UUID,
        filters: RetrievalFilterSet,
        filter_candidates: list[QueryAnalysisFilterCandidate],
    ) -> dict[str, Any]:
        """构建过滤条件的人类可读展示信息（名称优先，ID 作为详情）。"""

        def _build_candidate_aliases(filter_type: str) -> dict[str, list[str]]:
            alias_map: dict[str, list[str]] = {}
            for item in filter_candidates:
                if item.filter_type != filter_type:
                    continue
                target_id = str(item.target_id or "").strip()
                alias = str(item.filter_value or "").strip()
                if not target_id or not alias:
                    continue
                bucket = alias_map.setdefault(target_id, [])
                if alias not in bucket:
                    bucket.append(alias)
            return alias_map

        folder_aliases = _build_candidate_aliases("folder_id")
        tag_aliases = _build_candidate_aliases("tag_id")
        folder_tag_aliases = _build_candidate_aliases("folder_tag_id")

        folder_items: list[dict[str, Any]] = []
        if filters.folder_ids:
            stmt = select(Folder).where(
                Folder.tenant_id == tenant_id,
                Folder.kb_id == kb_id,
                Folder.id.in_(list(filters.folder_ids)),
            )
            rows = (await self.session.execute(stmt)).scalars().all()
            folder_map = {str(item.id): item for item in rows if item.id is not None}
            for folder_id in filters.folder_ids:
                key = str(folder_id)
                folder = folder_map.get(key)
                folder_items.append(
                    {
                        "id": key,
                        "name": str(folder.name or "").strip() if folder else "",
                        "path": str(folder.full_name_path or "").strip() if folder else "",
                        "matched_terms": list(folder_aliases.get(key) or []),
                    }
                )

        tag_items: list[dict[str, Any]] = []
        folder_tag_items: list[dict[str, Any]] = []
        all_tag_ids = [*list(filters.tag_ids), *list(filters.folder_tag_ids)]
        if all_tag_ids:
            stmt = select(Tag).where(
                Tag.tenant_id == tenant_id,
                or_(Tag.kb_id == kb_id, Tag.kb_id.is_(None)),
                Tag.id.in_(all_tag_ids),
            )
            rows = (await self.session.execute(stmt)).scalars().all()
            tag_map = {str(item.id): item for item in rows if item.id is not None}

            for tag_id in filters.tag_ids:
                key = str(tag_id)
                tag = tag_map.get(key)
                tag_items.append(
                    {
                        "id": key,
                        "name": str(tag.name or "").strip() if tag else "",
                        "aliases": [str(item).strip() for item in list(tag.aliases or []) if str(item or "").strip()] if tag else [],
                        "matched_terms": list(tag_aliases.get(key) or []),
                    }
                )
            for tag_id in filters.folder_tag_ids:
                key = str(tag_id)
                tag = tag_map.get(key)
                folder_tag_items.append(
                    {
                        "id": key,
                        "name": str(tag.name or "").strip() if tag else "",
                        "aliases": [str(item).strip() for item in list(tag.aliases or []) if str(item or "").strip()] if tag else [],
                        "matched_terms": list(folder_tag_aliases.get(key) or []),
                    }
                )

        kb_doc_items: list[dict[str, str]] = []
        if filters.kb_doc_ids:
            stmt = select(KnowledgeBaseDocument).where(
                KnowledgeBaseDocument.tenant_id == tenant_id,
                KnowledgeBaseDocument.kb_id == kb_id,
                KnowledgeBaseDocument.id.in_(list(filters.kb_doc_ids)),
            )
            rows = (await self.session.execute(stmt)).scalars().all()
            doc_map = {str(item.id): item for item in rows if item.id is not None}
            for kb_doc_id in filters.kb_doc_ids:
                key = str(kb_doc_id)
                kb_doc = doc_map.get(key)
                display_name = ""
                document_id = ""
                if kb_doc is not None:
                    display_name = str(kb_doc.display_name or "").strip() or str(kb_doc.document_id)
                    document_id = str(kb_doc.document_id or "").strip()
                kb_doc_items.append({"id": key, "name": display_name, "document_id": document_id})

        return {
            "folders": folder_items,
            "doc_tags": tag_items,
            "folder_tags": folder_tag_items,
            "kb_docs": kb_doc_items,
        }

    async def _rewrite_query_by_llm(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        query: str,
        rewrite_context: list[dict[str, str]],
    ) -> tuple[str, dict[str, Any]]:
        """使用 LLM 进行独立查询改写，并可附带目录路径建议。"""

        normalized_query = _normalize_text(query)
        history_items = self._normalize_query_rewrite_context(rewrite_context)
        folder_prompt_candidates = await self._load_folder_prompt_candidates(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
        )
        folder_routing_enabled = self._has_meaningful_folder_hierarchy(folder_prompt_candidates)

        # 没有多轮上下文也没有可用目录层级时，直接跳过，避免无收益改写。
        if not history_items and not folder_routing_enabled:
            return normalized_query, {
                "enabled": True,
                "status": "skipped",
                "reason": "no_context_or_folder_hierarchy",
                "history_count": 0,
                "folder_routing_enabled": False,
                "folder_candidate_count": len(folder_prompt_candidates),
                "standalone_query": normalized_query,
                "folder_routing_hints": {
                    "enabled": False,
                    "primary_folder_candidates": [],
                    "secondary_folder_candidates": [],
                },
            }

        prompt_payload: dict[str, Any] = {
            "query": normalized_query,
            "history": history_items,
            "folder_routing_enabled": folder_routing_enabled,
        }
        if folder_routing_enabled:
            prompt_payload["folders"] = folder_prompt_candidates

        folder_instruction = (
            "当前知识库存在多级目录。若用户问题明显指向某个目录范围，可输出 folder_routing_hints。"
            "只能引用输入 folders 中的目录 ID；primary_folder_candidates 用于主候选目录，secondary_folder_candidates 用于次候选目录。"
        ) if folder_routing_enabled else (
            "当前知识库没有可用的多级目录范围，不要输出目录建议，folder_routing_hints 保持为空。"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是RAG检索查询改写器。"
                    "你的任务是把当前用户问题改写成适合检索的独立问题。"
                    "优先处理多轮省略、代词指代、上文延续，不要添加原对话没有表达的新事实。"
                    "只输出 JSON，禁止输出解释性文本。"
                    f"{folder_instruction}"
                    "输出格式为 "
                    "{\"standalone_query\": \"改写后的独立问题\", "
                    "\"rewrite_reason\": \"简短原因\", "
                    "\"used_history\": true, "
                    "\"folder_routing_hints\": {\"primary_folder_candidates\": [\"目录ID\"], \"secondary_folder_candidates\": [\"目录ID\"], \"reason\": \"简短原因\"}}。"
                    "如果不需要改写，standalone_query 直接返回当前 query。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=False),
            },
        ]
        llm_request = LLMRequest(
            messages=messages,
            temperature=0,
            max_tokens=500,
            tenant_id=str(current_user.tenant_id),
            kb_id=str(kb.id),
            request_source="query_analysis_rewrite",
            workload_type="query_analysis_rewrite",
        )
        logger.info(
            "[query_analysis_rewrite] LLM 请求: %s",
            json.dumps(
                {
                    "messages": llm_request.messages,
                    "temperature": llm_request.temperature,
                    "max_tokens": llm_request.max_tokens,
                    "tenant_id": llm_request.tenant_id,
                    "kb_id": llm_request.kb_id,
                    "request_source": llm_request.request_source,
                    "workload_type": llm_request.workload_type,
                },
                ensure_ascii=False,
            ),
        )

        try:
            response = await LLMExecutor().chat(llm_request)
            logger.info(
                "[query_analysis_rewrite] LLM 响应: %s",
                json.dumps(
                    {
                        "model": response.model,
                        "content": response.content,
                        "usage": response.usage,
                    },
                    ensure_ascii=False,
                ),
            )
            parsed = self._parse_query_rewrite_response(response.content)
        except (RuntimeError, HTTPException, ValueError, json.JSONDecodeError) as exc:
            return normalized_query, {
                "enabled": True,
                "status": "failed",
                "error": str(exc),
                "history_count": len(history_items),
                "folder_routing_enabled": folder_routing_enabled,
                "folder_candidate_count": len(folder_prompt_candidates),
                "standalone_query": normalized_query,
                "folder_routing_hints": {
                    "enabled": folder_routing_enabled,
                    "primary_folder_candidates": [],
                    "secondary_folder_candidates": [],
                },
            }

        standalone_query = _normalize_text(str(parsed.get("standalone_query") or normalized_query))
        if not standalone_query:
            standalone_query = normalized_query
        folder_routing_hints = self._normalize_query_rewrite_folder_hints(
            parsed.get("folder_routing_hints"),
            folders=folder_prompt_candidates if folder_routing_enabled else [],
        )
        debug = {
            "enabled": True,
            "status": "success",
            "history_count": len(history_items),
            "folder_routing_enabled": folder_routing_enabled,
            "folder_candidate_count": len(folder_prompt_candidates),
            "rewrite_reason": str(parsed.get("rewrite_reason") or "").strip() or None,
            "used_history": bool(parsed.get("used_history", False)),
            "standalone_query": standalone_query,
            "folder_routing_hints": folder_routing_hints,
            "parsed_output": parsed,
        }
        return standalone_query, debug

    def _normalize_query_rewrite_context(self, value: list[dict[str, str]] | None) -> list[dict[str, str]]:
        """规范化查询改写上下文，限制长度，避免提示词膨胀。"""

        result: list[dict[str, str]] = []
        for item in list(value or [])[-6:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            content = _normalize_text(str(item.get("content") or ""))
            if role not in {"user", "assistant"} or not content:
                continue
            result.append({"role": role, "content": content})
        return result

    def _has_meaningful_folder_hierarchy(self, folders: list[dict[str, Any]]) -> bool:
        """判断当前知识库是否存在足以支持目录建议的目录结构。"""

        normalized_folders = [item for item in list(folders or []) if isinstance(item, dict)]
        return len(normalized_folders) > 1

    def _parse_query_rewrite_response(self, content: str) -> dict[str, Any]:
        """解析查询改写 LLM 的 JSON 响应。"""

        text = str(content or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                raise
            parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise ValueError("查询改写返回结果必须是 JSON 对象")
        return parsed

    def _normalize_query_rewrite_folder_hints(
        self,
        payload: Any,
        *,
        folders: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """校验目录建议，只允许引用当前输入中的目录 ID。"""

        folder_ids = {str(item.get("id") or "").strip() for item in list(folders or []) if str(item.get("id") or "").strip()}
        data = dict(payload or {}) if isinstance(payload, dict) else {}
        primary = [
            item
            for item in [str(folder_id).strip() for folder_id in list(data.get("primary_folder_candidates") or [])]
            if item in folder_ids
        ]
        secondary = [
            item
            for item in [str(folder_id).strip() for folder_id in list(data.get("secondary_folder_candidates") or [])]
            if item in folder_ids and item not in primary
        ]
        return {
            "enabled": bool(folder_ids),
            "primary_folder_candidates": primary[:3],
            "secondary_folder_candidates": secondary[:3],
            "reason": str(data.get("reason") or "").strip() or None,
        }

    async def _rewrite_query_by_synonyms(
        self,
        *,
        tenant_id: UUID,
        kb_id: UUID,
        query: str,
    ) -> tuple[str, list[QueryAnalysisSynonymMatch]]:
        """基于标准词映射改写查询。"""

        if not query:
            return query, []

        stmt = (
            select(KBSynonymVariant, KBSynonym)
            .join(KBSynonym, KBSynonym.id == KBSynonymVariant.synonym_id)
            .where(
                KBSynonym.tenant_id == tenant_id,
                KBSynonym.is_active.is_(True),
                KBSynonymVariant.is_active.is_(True),
                or_(KBSynonym.kb_id == kb_id, KBSynonym.kb_id.is_(None)),
            )
            .order_by(
                case((KBSynonym.kb_id == kb_id, 0), else_=1),
                KBSynonym.priority.asc(),
                KBSynonym.updated_at.desc(),
                KBSynonymVariant.updated_at.desc(),
            )
        )
        rows = (await self.session.execute(stmt)).all()

        grouped_rules: dict[UUID, dict[str, Any]] = {}
        for variant, synonym in rows:
            professional_term = _normalize_text(synonym.professional_term)
            user_term = _normalize_text(variant.user_term)
            if not user_term or not professional_term:
                continue
            rule = grouped_rules.setdefault(
                synonym.id,
                {
                    "professional_term": professional_term,
                    "synonym_id": synonym.id,
                    "scope": "kb" if synonym.kb_id is not None else "tenant",
                    "variants": [],
                },
            )
            variants = list(rule.get("variants") or [])
            if not any(item["user_term"] == user_term for item in variants):
                variants.append({"user_term": user_term, "variant_id": variant.id})
                rule["variants"] = variants

        mapping: dict[str, dict[str, Any]] = {}
        for rule in grouped_rules.values():
            variants = list(rule.get("variants") or [])
            expansion_terms = [
                str(item).strip()
                for item in [
                    rule.get("professional_term"),
                    *[variant.get("user_term") for variant in variants],
                ]
                if str(item or "").strip()
            ]
            expansion_terms = list(dict.fromkeys(expansion_terms))[:6]
            for variant in variants:
                user_term = str(variant.get("user_term") or "").strip()
                if not user_term or user_term in mapping:
                    continue
                mapping[user_term] = {
                    "professional_term": str(rule["professional_term"]),
                    "synonym_id": rule["synonym_id"],
                    "variant_id": variant["variant_id"],
                    "scope": str(rule["scope"]),
                    "expansion_terms": expansion_terms,
                }

        if not mapping:
            return query, []

        matched_rules: dict[str, QueryAnalysisSynonymMatch] = {}
        sorted_terms = sorted(mapping.keys(), key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(term) for term in sorted_terms))

        def _replace(match: re.Match[str]) -> str:
            user_term = match.group(0)
            rule = mapping.get(user_term)
            if not rule:
                return user_term
            matched_rules.setdefault(
                user_term,
                QueryAnalysisSynonymMatch(
                    user_term=user_term,
                    professional_term=str(rule["professional_term"]),
                    synonym_id=rule["synonym_id"],
                    variant_id=rule["variant_id"],
                    scope=str(rule["scope"]),
                    expansion_terms=list(rule.get("expansion_terms") or []),
                ),
            )
            return str(rule["professional_term"])

        rewritten_query = pattern.sub(_replace, query)
        return rewritten_query, list(matched_rules.values())

    async def _resolve_glossary_entries(
        self,
        *,
        tenant_id: UUID,
        kb_id: UUID,
        query: str,
        synonym_matches: list[QueryAnalysisSynonymMatch],
        max_terms: int,
    ) -> list[QueryAnalysisGlossaryEntry]:
        """提取与当前问题相关的专业术语定义。"""

        normalized_query = query.lower()
        forced_terms = {_normalize_text(item.professional_term).lower() for item in synonym_matches if item.professional_term}
        stmt = (
            select(KBGlossary)
            .where(
                KBGlossary.tenant_id == tenant_id,
                KBGlossary.is_active.is_(True),
                or_(KBGlossary.kb_id == kb_id, KBGlossary.kb_id.is_(None)),
            )
            .order_by(
                case((KBGlossary.kb_id == kb_id, 0), else_=1),
                KBGlossary.updated_at.desc(),
            )
        )
        rows = (await self.session.execute(stmt)).scalars().all()

        entries: list[QueryAnalysisGlossaryEntry] = []
        seen_terms: set[str] = set()
        for glossary in rows:
            normalized_term = _normalize_text(glossary.term)
            lowered_term = normalized_term.lower()
            if not normalized_term or lowered_term in seen_terms:
                continue
            if lowered_term not in forced_terms and lowered_term not in normalized_query:
                continue
            entries.append(
                QueryAnalysisGlossaryEntry(
                    term=normalized_term,
                    definition=str(glossary.definition or "").strip(),
                    examples=str(glossary.examples or "").strip() or None,
                    scope="kb" if glossary.kb_id is not None else "tenant",
                )
            )
            seen_terms.add(lowered_term)
            if len(entries) >= max(1, max_terms):
                break
        return entries

    async def _extract_rule_based_filters(
        self,
        *,
        tenant_id: UUID,
        kb: KnowledgeBase,
        query: str,
        existing_filters: RetrievalFilterSet,
        metadata_fields: list[dict[str, Any]],
    ) -> list[QueryAnalysisFilterCandidate]:
        """从问题中做高置信规则型过滤提取。"""

        candidates: list[QueryAnalysisFilterCandidate] = []
        if not existing_filters.folder_ids:
            candidates.extend(
                await self._match_folders(
                    tenant_id=tenant_id,
                    kb_id=kb.id,
                    query=query,
                )
            )
        if not existing_filters.tag_ids:
            candidates.extend(
                await self._match_tags(
                    tenant_id=tenant_id,
                    kb_id=kb.id,
                    query=query,
                    allowed_target_type="kb_doc",
                )
            )
        if not existing_filters.folder_tag_ids:
            candidates.extend(
                await self._match_tags(
                    tenant_id=tenant_id,
                    kb_id=kb.id,
                    query=query,
                    allowed_target_type="folder",
                )
            )
        if not existing_filters.document_metadata and not existing_filters.search_unit_metadata and metadata_fields:
            candidates.extend(
                self._match_metadata_fields(
                    query=query,
                    metadata_fields=metadata_fields,
                )
            )
        return candidates

    async def _match_folders(
        self,
        *,
        tenant_id: UUID,
        kb_id: UUID,
        query: str,
    ) -> list[QueryAnalysisFilterCandidate]:
        """匹配目录树节点。"""

        stmt = (
            select(Folder)
            .where(
                Folder.tenant_id == tenant_id,
                Folder.kb_id == kb_id,
            )
            .order_by(Folder.level.desc(), Folder.updated_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        normalized_query = query.lower()
        matched: list[QueryAnalysisFilterCandidate] = []
        for folder in rows:
            candidates = [
                str(folder.name or "").strip(),
                str(folder.full_name_path or "").strip(),
            ]
            if folder.summary:
                candidates.append(str(folder.summary).strip())
            best_source = ""
            best_value = ""
            best_confidence = 0.0
            for candidate in candidates:
                normalized_candidate = _normalize_text(candidate)
                if len(normalized_candidate) < 2:
                    continue
                lowered_candidate = normalized_candidate.lower()
                if lowered_candidate and lowered_candidate in normalized_query:
                    confidence = 0.99 if normalized_candidate == str(folder.full_name_path or "").strip() else 0.93
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_source = "folder_path" if normalized_candidate == str(folder.full_name_path or "").strip() else "folder_name"
                        best_value = normalized_candidate
            if best_confidence < 0.9:
                continue
            matched.append(
                QueryAnalysisFilterCandidate(
                    filter_type="folder_id",
                    filter_value=best_value,
                    target_id=folder.id,
                    confidence=best_confidence,
                    source=best_source,
                    layer="rule",
                    validation_status="validated",
                )
            )
        return matched[:3]

    async def _match_tags(
        self,
        *,
        tenant_id: UUID,
        kb_id: UUID,
        query: str,
        allowed_target_type: str,
    ) -> list[QueryAnalysisFilterCandidate]:
        """匹配文档标签 / 文件夹标签。"""

        usage_exists = self._build_tag_usage_exists_clause(
            tenant_id=tenant_id,
            kb_id=kb_id,
            allowed_target_type=allowed_target_type,
        )
        stmt = (
            select(Tag)
            .where(
                Tag.tenant_id == tenant_id,
                or_(Tag.kb_id == kb_id, Tag.kb_id.is_(None)),
                usage_exists,
            )
            .order_by(
                case((Tag.kb_id == kb_id, 0), else_=1),
                Tag.updated_at.desc(),
            )
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        normalized_query = query.lower()
        matched: list[QueryAnalysisFilterCandidate] = []
        for tag in rows:
            allowed_types = [str(item) for item in (tag.allowed_target_types or [])]
            if allowed_target_type not in allowed_types:
                continue

            candidate_texts = [str(tag.name or "").strip()]
            for alias in list(tag.aliases or []):
                alias_text = str(alias or "").strip()
                if alias_text:
                    candidate_texts.append(alias_text)

            best_match = ""
            best_confidence = 0.0
            best_source = ""
            for candidate in candidate_texts:
                normalized_candidate = _normalize_text(candidate)
                if len(normalized_candidate) < 2:
                    continue
                lowered_candidate = normalized_candidate.lower()
                if lowered_candidate and lowered_candidate in normalized_query:
                    confidence = 0.95 if normalized_candidate == str(tag.name or "").strip() else 0.92
                    if confidence > best_confidence:
                        best_match = normalized_candidate
                        best_confidence = confidence
                        best_source = "tag_name" if normalized_candidate == str(tag.name or "").strip() else "tag_alias"
            if best_confidence < 0.9:
                continue
            matched.append(
                QueryAnalysisFilterCandidate(
                    filter_type="tag_id" if allowed_target_type == "kb_doc" else "folder_tag_id",
                    filter_value=best_match,
                    target_id=tag.id,
                    confidence=best_confidence,
                    source=best_source,
                    layer="rule",
                    validation_status="validated",
                )
            )
        return matched[:5]

    def _apply_filter_candidates(
        self,
        *,
        filters: RetrievalFilterSet,
        candidates: list[QueryAnalysisFilterCandidate],
    ) -> RetrievalFilterSet:
        """把允许升级的自动候选写入最终硬过滤条件。

        标签和元数据自动候选会转成 auto_filter_signals，避免自然语言命中
        直接裁剪检索候选；显式过滤仍由调用方直接写入 RetrievalFilterSet。
        """

        result = self._clone_filters(filters)
        for candidate in candidates:
            if candidate.validation_status in {"conflicted", "rejected", "corrected_by_llm"}:
                continue
            if candidate.confidence < 0.9:
                continue
            if candidate.filter_type == "folder_id":
                if candidate.target_id not in result.folder_ids:
                    result.folder_ids.append(candidate.target_id)
                    candidate.applied = True
            elif candidate.filter_type == "tag_id":
                candidate.validation_reason = candidate.validation_reason or "自动文档标签仅作为加权信号"
            elif candidate.filter_type == "folder_tag_id":
                candidate.validation_reason = candidate.validation_reason or "自动文件夹标签仅作为加权信号"
            elif candidate.filter_type == "document_metadata":
                candidate.validation_reason = candidate.validation_reason or "自动文档元数据由 match_or_missing 信号处理"
            elif candidate.filter_type == "search_unit_metadata":
                candidate.validation_reason = candidate.validation_reason or "自动搜索单元元数据由独立信号处理"
        return result

    def _build_auto_filter_signals(
        self,
        *,
        candidates: list[QueryAnalysisFilterCandidate],
        metadata_fields: list[dict[str, Any]],
    ) -> list[QueryAnalysisAutoFilterSignal]:
        """把自动候选转换为可解释的过滤 / 加权信号。"""

        metadata_config = self._build_metadata_signal_config(metadata_fields=metadata_fields)
        signals: list[QueryAnalysisAutoFilterSignal] = []
        seen_keys: set[tuple[str, str, str]] = set()
        for candidate in candidates:
            if candidate.validation_status not in {"validated", "pending"}:
                continue
            if candidate.filter_type == "tag_id":
                target_id = str(candidate.target_id)
                signal_key = ("doc_tag", target_id, candidate.filter_value)
                if signal_key in seen_keys:
                    continue
                seen_keys.add(signal_key)
                signals.append(
                    QueryAnalysisAutoFilterSignal(
                        signal_type="doc_tag",
                        target_id=target_id,
                        filter_value=candidate.filter_value,
                        confidence=candidate.confidence,
                        source=candidate.source,
                        usage="tag_boost",
                        match_mode="boost",
                        layer=candidate.layer,
                        debug={"candidate_filter_type": candidate.filter_type},
                    )
                )
            elif candidate.filter_type == "folder_tag_id":
                target_id = str(candidate.target_id)
                signal_key = ("folder_tag", target_id, candidate.filter_value)
                if signal_key in seen_keys:
                    continue
                seen_keys.add(signal_key)
                signals.append(
                    QueryAnalysisAutoFilterSignal(
                        signal_type="folder_tag",
                        target_id=target_id,
                        filter_value=candidate.filter_value,
                        confidence=candidate.confidence,
                        source=candidate.source,
                        usage="tag_boost",
                        match_mode="boost",
                        layer=candidate.layer,
                        debug={"candidate_filter_type": candidate.filter_type},
                    )
                )
            elif candidate.filter_type in {"document_metadata", "search_unit_metadata"} and candidate.layer == "llm":
                target_key = ".".join(candidate.target_id) if isinstance(candidate.target_id, list) else str(candidate.target_id)
                config = metadata_config.get((candidate.filter_type, target_key))
                if config is None:
                    continue
                match_mode = str(config.get("match_mode") or "match_or_missing").strip() or "match_or_missing"
                if match_mode not in {"match_or_missing", "match_only"}:
                    match_mode = "match_or_missing"
                signal_key = (candidate.filter_type, target_key, candidate.filter_value)
                if signal_key in seen_keys:
                    continue
                seen_keys.add(signal_key)
                target_path = list(candidate.target_id) if isinstance(candidate.target_id, list) else list(config.get("target_path") or [])
                effective_target_id = ".".join(target_path) if candidate.filter_type == "document_metadata" and target_path else target_key
                signals.append(
                    QueryAnalysisAutoFilterSignal(
                        signal_type=candidate.filter_type,
                        target_id=effective_target_id,
                        target_path=target_path,
                        filter_value=candidate.filter_value,
                        confidence=candidate.confidence,
                        source=candidate.source,
                        usage=match_mode,
                        match_mode=match_mode,
                        layer=candidate.layer,
                        metadata_target=candidate.filter_type,
                        debug={
                            "field_key": str(config.get("field_key") or target_key),
                            "field_name": str(config.get("field_name") or ""),
                        },
                    )
                )
        return signals

    def _build_metadata_signal_config(
        self,
        *,
        metadata_fields: list[dict[str, Any]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """构建自动元数据信号白名单配置。"""

        result: dict[tuple[str, str], dict[str, Any]] = {}
        for field in metadata_fields:
            raw_field = dict(field or {})
            field_key = str(raw_field.get("key") or raw_field.get("name") or "").strip()
            if not field_key:
                continue
            target = str(raw_field.get("target") or "document_metadata").strip() or "document_metadata"
            filter_type = "search_unit_metadata" if target == "search_unit_metadata" else "document_metadata"
            target_path = [
                str(item).strip()
                for item in list(raw_field.get("metadata_path") or [])
                if str(item).strip()
            ]
            primary_target_id = ".".join(target_path) if target_path else field_key
            for target_id in list(dict.fromkeys([field_key, primary_target_id])):
                if not target_id:
                    continue
                result[(filter_type, target_id)] = {
                    "field_key": field_key,
                    "field_name": str(raw_field.get("name") or field_key).strip(),
                    "target_path": target_path,
                    "match_mode": str(raw_field.get("match_mode") or "match_or_missing").strip() or "match_or_missing",
                }
        return result

    def _build_lexical_query(
        self,
        *,
        raw_query: str,
        rewritten_query: str,
        synonym_matches: list[QueryAnalysisSynonymMatch],
        retrieval_lexicon_matches: list[QueryAnalysisLexiconMatch],
        retrieval_stopwords: list[str],
    ) -> str:
        """构建专门用于全文检索的查询字符串。"""

        terms: list[str] = []
        # 使用集合追踪所有已包含的 token (转为小写规范化比较)
        existing_tokens = set()

        # 优先填入 rewritten_query 和 raw_query 中的实质内容
        for source in (rewritten_query, raw_query):
            for part in source.split():
                normalized = _normalize_text(part)
                if normalized and normalized.lower() not in existing_tokens:
                    terms.append(normalized)
                    existing_tokens.add(normalized.lower())

        # 填入同义词和词项扩展
        for item in synonym_matches:
            # 标准术语
            norm = _normalize_text(item.professional_term)
            if norm and norm.lower() not in existing_tokens:
                terms.append(norm)
                existing_tokens.add(norm.lower())
            # 扩展词
            for exp in item.expansion_terms[:6]:
                norm_exp = _normalize_text(exp)
                if norm_exp and norm_exp.lower() not in existing_tokens:
                    terms.append(norm_exp)
                    existing_tokens.add(norm_exp.lower())

        # 我们不再将词项重复拼接到查询字符串中，因为它们会通过 priority_terms 专门下发并加分。
        # 保持 rewritten_query 的简洁有助于后续分词与整句匹配的准确性。
        return " ".join(self._filter_lexical_terms(terms=terms, retrieval_stopwords=retrieval_stopwords))

    def _apply_retrieval_lexicon(
        self,
        *,
        query: str,
        retrieval_lexicon: list[dict[str, Any]],
    ) -> tuple[str, list[QueryAnalysisLexiconMatch]]:
        """将知识库级检索词表接入 query rewrite 与 lexical 扩展。"""

        normalized_query = _normalize_text(query)
        if not normalized_query or not retrieval_lexicon:
            return normalized_query, []

        lowered_query = normalized_query.lower()
        matches: list[QueryAnalysisLexiconMatch] = []
        for raw_item in retrieval_lexicon[:120]:
            item = dict(raw_item or {})
            if item.get("enabled", True) is False:
                continue
            term = _normalize_text(str(item.get("term") or "").strip())
            if not term:
                continue
            aliases = [
                _normalize_text(str(alias).strip())
                for alias in list(item.get("aliases") or [])
                if _normalize_text(str(alias).strip())
            ]
            candidate_texts = [term, *aliases]
            matched_text = next((candidate for candidate in candidate_texts if candidate.lower() in lowered_query), "")
            if not matched_text:
                continue
            try:
                weight = max(0.0, min(float(item.get("weight") or 1.0), 2.0))
            except (TypeError, ValueError):
                weight = 1.0
            lexicon_match = QueryAnalysisLexiconMatch(
                term=term,
                matched_text=matched_text,
                aliases=aliases,
                is_phrase=bool(item.get("is_phrase", False)),
                weight=round(weight, 4),
                source=str(item.get("source") or "custom").strip() or "custom",
            )
            matches.append(lexicon_match)

        # 我们不再将词项重复拼接到查询字符串中，因为它们会通过 priority_terms 专门下发并加分。
        # 保持 rewritten_query 的简洁有助于后续分词与整句匹配的准确性。
        return normalized_query, matches

    def _build_priority_lexical_hints(
        self,
        *,
        retrieval_lexicon_matches: list[QueryAnalysisLexiconMatch],
        glossary_entries: list[QueryAnalysisGlossaryEntry],
    ) -> tuple[list[str], list[str], dict[str, float]]:
        """整理需要优先命中的术语和短语。"""

        priority_terms: list[str] = []
        priority_phrases: list[str] = []
        lexicon_weights: dict[str, float] = {}

        for match in retrieval_lexicon_matches:
            # 1. 处理标准词
            norm_term = _normalize_text(match.term)
            if norm_term:
                if norm_term not in priority_terms:
                    priority_terms.append(norm_term)
                if match.is_phrase and norm_term not in priority_phrases:
                    priority_phrases.append(norm_term)
                lexicon_weights[norm_term] = max(lexicon_weights.get(norm_term, 0.0), match.weight)

            # 2. 处理用户实际输入的匹配词（双向扩展）
            norm_matched = _normalize_text(match.matched_text)
            if norm_matched and norm_matched != norm_term:
                if norm_matched not in priority_terms:
                    priority_terms.append(norm_matched)
                # 如果标准词是短语，用户输入的别名通常也按短语处理优先级更高
                if match.is_phrase and norm_matched not in priority_phrases:
                    priority_phrases.append(norm_matched)
                lexicon_weights[norm_matched] = max(lexicon_weights.get(norm_matched, 0.0), match.weight)

        for entry in glossary_entries:
            normalized_term = _normalize_text(entry.term)
            if len(normalized_term) < 2:
                continue
            if normalized_term not in priority_terms:
                priority_terms.append(normalized_term)
            # 默认 glossary 长度大于等于 4 时尝试按短语优先（维持现状逻辑）
            if len(normalized_term) >= 4 and normalized_term not in priority_phrases:
                priority_phrases.append(normalized_term)
            # Glossary 给予默认基准权重 1.0
            if normalized_term not in lexicon_weights:
                lexicon_weights[normalized_term] = 1.0

        return priority_terms[:12], priority_phrases[:8], lexicon_weights

    def _normalize_retrieval_stopwords(self, raw_terms: list[str] | tuple[str, ...] | None) -> list[str]:
        """规范化检索忽略词，统一去重和空白处理。"""

        normalized_terms: list[str] = []
        for item in merge_stopwords("query", raw_terms):
            normalized = _normalize_text(str(item or "")).lower()
            if normalized and normalized not in normalized_terms:
                normalized_terms.append(normalized)
        return normalized_terms

    def _filter_lexical_terms(
        self,
        *,
        terms: list[str],
        retrieval_stopwords: list[str],
    ) -> list[str]:
        """过滤低价值词，避免它们污染全文检索 query。"""

        return filter_exact_stopword_terms(terms=terms, stopwords=retrieval_stopwords)

    def _collect_ignored_lexical_terms(
        self,
        *,
        source_terms: list[str],
        retrieval_stopwords: list[str],
    ) -> list[str]:
        """整理当前 query 中实际命中的忽略词，方便调试查看。"""

        if not source_terms or not retrieval_stopwords:
            return []

        lowered_query = " ".join(_normalize_text(item).lower() for item in source_terms if _normalize_text(item))
        matched_terms: list[str] = []
        for term in retrieval_stopwords:
            if term and term in lowered_query and term not in matched_terms:
                matched_terms.append(term)
        return matched_terms

    def _clone_filters(self, filters: RetrievalFilterSet) -> RetrievalFilterSet:
        """复制过滤集合，避免就地修改调用方对象。"""

        return RetrievalFilterSet(
            kb_doc_ids=list(filters.kb_doc_ids),
            document_ids=list(filters.document_ids),
            content_group_ids=list(filters.content_group_ids),
            folder_ids=list(filters.folder_ids),
            tag_ids=list(filters.tag_ids),
            folder_tag_ids=list(filters.folder_tag_ids),
            document_metadata=dict(filters.document_metadata),
            search_unit_metadata=dict(filters.search_unit_metadata),
            filter_expression=dict(filters.filter_expression),
            include_descendant_folders=filters.include_descendant_folders,
            only_tagged=filters.only_tagged,
            latest_days=filters.latest_days,
        )

    def _match_metadata_fields(
        self,
        *,
        query: str,
        metadata_fields: list[dict[str, Any]],
    ) -> list[QueryAnalysisFilterCandidate]:
        """基于 schema 定义抽取文档元数据过滤。

        设计原则：
        - 只处理显式枚举/候选值字段
        - 只有高置信命中才升级为硬过滤
        - 不做自由文本猜测，避免误杀召回
        """

        normalized_query = query.lower()
        matched: list[QueryAnalysisFilterCandidate] = []
        for field in metadata_fields:
            field_key = str((field or {}).get("key") or (field or {}).get("name") or "").strip()
            if not field_key:
                continue
            target = str((field or {}).get("target") or "document_metadata").strip() or "document_metadata"
            field_aliases = [
                str(item).strip()
                for item in [field.get("name"), *(list((field or {}).get("aliases") or []))]
                if str(item or "").strip()
            ]
            raw_metadata_path = list((field or {}).get("metadata_path") or [])
            metadata_path = [str(item).strip() for item in raw_metadata_path if str(item).strip()]
            values = list((field or {}).get("enum_values") or (field or {}).get("options") or [])
            if not values:
                continue
            best_value = ""
            best_confidence = 0.0
            for option in values:
                if isinstance(option, dict):
                    raw_value = str(option.get("value") or option.get("id") or "").strip()
                    labels = [
                        str(option.get("label") or "").strip(),
                        str(option.get("name") or "").strip(),
                    ]
                    aliases = [str(item).strip() for item in list(option.get("aliases") or []) if str(item).strip()]
                else:
                    raw_value = str(option).strip()
                    labels = [raw_value]
                    aliases = []
                if not raw_value:
                    continue
                candidate_texts = [item for item in labels + aliases if item]
                for candidate_text in candidate_texts:
                    lowered = _normalize_text(candidate_text).lower()
                    if len(lowered) < 2:
                        continue
                    if lowered and lowered in normalized_query:
                        # 表格/枚举字段优先按“值命中”抽取；若字段名或别名也出现，则提升为更高置信。
                        confidence = 0.96 if candidate_text == raw_value else 0.92
                        if field_aliases:
                            has_field_hint = any(
                                len(alias.lower()) >= 2 and _normalize_text(alias).lower() in normalized_query
                                for alias in field_aliases
                            )
                            if has_field_hint:
                                confidence = min(0.99, confidence + 0.02)
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_value = raw_value
            if best_confidence < 0.9 or not best_value:
                continue
            matched.append(
                QueryAnalysisFilterCandidate(
                    filter_type="search_unit_metadata" if target == "search_unit_metadata" else "document_metadata",
                    filter_value=best_value,
                    target_id=metadata_path or field_key,
                    confidence=best_confidence,
                    source=f"{target}:{field_key}",
                    layer="rule",
                    validation_status="validated",
                )
            )
        return matched[:8]

    async def _extract_llm_filter_candidates(
        self,
        *,
        current_user: User,
        kb: KnowledgeBase,
        query: str,
        rule_candidates: list[QueryAnalysisFilterCandidate],
        metadata_fields: list[dict[str, Any]],
    ) -> tuple[list[QueryAnalysisFilterCandidate], dict[str, Any]]:
        """使用 LLM 提取过滤候选，但不直接升级为硬过滤。"""

        if not query:
            return [], {"enabled": False, "reason": "empty_query"}

        folder_prompt_candidates = await self._load_folder_prompt_candidates(tenant_id=current_user.tenant_id, kb_id=kb.id)
        doc_tag_prompt_candidates = await self._load_tag_prompt_candidates(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
            allowed_target_type="kb_doc",
        )
        folder_tag_prompt_candidates = await self._load_tag_prompt_candidates(
            tenant_id=current_user.tenant_id,
            kb_id=kb.id,
            allowed_target_type="folder",
        )
        metadata_prompt_fields = self._serialize_metadata_prompt_fields(metadata_fields)
        prompt_payload: dict[str, Any] = {
            "query": query,
            "rule_candidates": self._serialize_rule_candidates_for_prompt(rule_candidates),
            "folders": folder_prompt_candidates,
            "doc_tags": doc_tag_prompt_candidates,
            "folder_tags": folder_tag_prompt_candidates,
            "metadata_fields": metadata_prompt_fields,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是RAG检索查询分析器。"
                    "请只提取用户问题里明确表达的过滤候选，不要猜测。"
                    "你只能输出JSON，且不能添加解释。"
                    "rule_candidates 是规则层已经识别到的候选，你可以补充、纠偏或改写成更准确的复杂表达式。"
                    "输出格式为 {\"candidates\": [{\"filter_type\": \"folder_id|tag_id|folder_tag_id|document_metadata|search_unit_metadata\","
                    "\"target_id\": \"目标ID或字段路径\", \"filter_value\": \"命中的值\", \"confidence\": 0到1, "
                    "\"evidence_type\": \"explicit_query_match|alias_match|rewrite_query_match|rule_supported|candidate_inference\", "
                    "\"evidence_text\": \"命中的原词或改写词\", \"evidence_query_source\": \"raw|standalone|rewritten|rule\", "
                    "\"matched_alias\": \"命中的别名，可选\", \"reason\": \"简短调试说明，可选\"}]}。"
                    "也可以额外输出 filter_expression，用于表达括号、跨字段 OR、not_in 等复杂条件；"
                    "格式为 {\"op\":\"and|or|not\",\"items\":[...]} 或叶子 {\"field\":\"metadata|search_unit_metadata|tag|folder_tag|folder\","
                    "\"path\":[\"字段路径\"],\"op\":\"eq|ne|in|not_in|exists|not_exists\",\"values\":[\"值\"]}。"
                    "如果没有明确候选，返回 {\"candidates\": []}。"
                    "对于 metadata_path 请使用以点连接的路径字符串，例如 qa_fields.tag 或 filter_fields.region。"
                    "不要把不确定或模糊的信息输出为高置信。"
                    "不要仅因为输入候选池里存在某个标签/目录/字段值，就说用户明确提到了它。"
                    "filter_expression 只能使用用户明确表达的条件，且只能引用输入候选里的字段、标签或目录ID。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=False),
            },
        ]

        llm_request = LLMRequest(
            messages=messages,
            temperature=0,
            max_tokens=600,
            tenant_id=str(current_user.tenant_id),
            kb_id=str(kb.id),
            request_source="query_analysis_llm_candidate",
            workload_type="query_analysis_llm_candidate",
        )
        logger.info(
            "[query_analysis_llm_candidate] LLM 请求: %s",
            json.dumps(
                {
                    "messages": llm_request.messages,
                    "temperature": llm_request.temperature,
                    "max_tokens": llm_request.max_tokens,
                    "tenant_id": llm_request.tenant_id,
                    "kb_id": llm_request.kb_id,
                    "request_source": llm_request.request_source,
                    "workload_type": llm_request.workload_type,
                },
                ensure_ascii=False,
            ),
        )

        try:
            response = await LLMExecutor().chat(llm_request)
            logger.info(
                "[query_analysis_llm_candidate] LLM 响应: %s",
                json.dumps(
                    {
                        "model": response.model,
                        "content": response.content,
                        "usage": response.usage,
                    },
                    ensure_ascii=False,
                ),
            )
            parsed = self._parse_llm_candidate_response(response.content)
        except (RuntimeError, HTTPException, ValueError, json.JSONDecodeError) as exc:
            return [], {
                "enabled": True,
                "status": "failed",
                "error": str(exc),
            }

        candidates = self._normalize_llm_candidates(
            parsed.get("candidates"),
            folders=folder_prompt_candidates,
            doc_tags=doc_tag_prompt_candidates,
            folder_tags=folder_tag_prompt_candidates,
            metadata_fields=metadata_prompt_fields,
        )
        filter_expression = self._normalize_llm_filter_expression(
            parsed.get("filter_expression"),
            folders=folder_prompt_candidates,
            doc_tags=doc_tag_prompt_candidates,
            folder_tags=folder_tag_prompt_candidates,
            metadata_fields=metadata_prompt_fields,
        )
        return candidates, {
            "enabled": True,
            "status": "success",
            "candidate_count": len(candidates),
            "filter_expression": filter_expression,
            "filter_expression_status": "validated" if filter_expression else "empty_or_rejected",
            "rule_candidate_count": len(prompt_payload["rule_candidates"]),
            "parsed_output": parsed,
        }

    async def _load_folder_prompt_candidates(
        self,
        *,
        tenant_id: UUID,
        kb_id: UUID,
    ) -> list[dict[str, str]]:
        """加载供 LLM 参考的目录候选。"""

        stmt = (
            select(Folder)
            .where(Folder.tenant_id == tenant_id, Folder.kb_id == kb_id)
            .order_by(Folder.level.asc(), Folder.updated_at.desc())
            .limit(60)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [
            {
                "id": str(folder.id),
                "name": str(folder.name or "").strip(),
                "path": str(folder.full_name_path or "").strip(),
            }
            for folder in rows
            if folder.id is not None and str(folder.name or "").strip()
        ]

    async def _load_tag_prompt_candidates(
        self,
        *,
        tenant_id: UUID,
        kb_id: UUID,
        allowed_target_type: str,
    ) -> list[dict[str, Any]]:
        """加载供 LLM 参考的标签候选，仅返回当前知识库实际使用中的标签。"""

        usage_exists = self._build_tag_usage_exists_clause(
            tenant_id=tenant_id,
            kb_id=kb_id,
            allowed_target_type=allowed_target_type,
        )
        stmt: Select[Any] = (
            select(Tag)
            .where(
                Tag.tenant_id == tenant_id,
                or_(Tag.kb_id == kb_id, Tag.kb_id.is_(None)),
                usage_exists,
            )
            .order_by(case((Tag.kb_id == kb_id, 0), else_=1), Tag.updated_at.desc())
            .limit(80)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        items: list[dict[str, Any]] = []
        for tag in rows:
            allowed_types = [str(item) for item in (tag.allowed_target_types or [])]
            if allowed_target_type not in allowed_types:
                continue
            items.append(
                {
                    "id": str(tag.id),
                    "name": str(tag.name or "").strip(),
                    "aliases": [str(item).strip() for item in list(tag.aliases or []) if str(item or "").strip()],
                }
            )
        return items

    def _build_tag_usage_exists_clause(
        self,
        *,
        tenant_id: UUID,
        kb_id: UUID,
        allowed_target_type: str,
    ) -> Any:
        """构建“标签当前是否仍被知识库资源使用”的 exists 条件。"""

        if allowed_target_type == TARGET_TYPE_KB_DOC:
            return exists(
                select(1)
                .select_from(ResourceTag)
                .join(
                    KnowledgeBaseDocument,
                    KnowledgeBaseDocument.id == ResourceTag.target_id,
                )
                .where(
                    ResourceTag.tenant_id == tenant_id,
                    ResourceTag.kb_id == kb_id,
                    ResourceTag.target_type == TARGET_TYPE_KB_DOC,
                    ResourceTag.action == "add",
                    ResourceTag.tag_id == Tag.id,
                    KnowledgeBaseDocument.tenant_id == tenant_id,
                    KnowledgeBaseDocument.kb_id == kb_id,
                )
            )
        if allowed_target_type == TARGET_TYPE_FOLDER:
            return exists(
                select(1)
                .select_from(ResourceTag)
                .join(Folder, Folder.id == ResourceTag.target_id)
                .where(
                    ResourceTag.tenant_id == tenant_id,
                    ResourceTag.kb_id == kb_id,
                    ResourceTag.target_type == TARGET_TYPE_FOLDER,
                    ResourceTag.action == "add",
                    ResourceTag.tag_id == Tag.id,
                    Folder.tenant_id == tenant_id,
                    Folder.kb_id == kb_id,
                )
            )
        return exists(
            select(1)
            .select_from(ResourceTag)
            .where(
                ResourceTag.tenant_id == tenant_id,
                ResourceTag.kb_id == kb_id,
                ResourceTag.target_type == allowed_target_type,
                ResourceTag.action == "add",
                ResourceTag.tag_id == Tag.id,
            )
        )

    def _serialize_metadata_prompt_fields(self, metadata_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """压缩元数据字段定义，避免提示词过长。"""

        items: list[dict[str, Any]] = []
        for field in metadata_fields[:40]:
            key = str((field or {}).get("key") or (field or {}).get("name") or "").strip()
            if not key:
                continue
            target = str((field or {}).get("target") or "document_metadata").strip() or "document_metadata"
            metadata_path = ".".join(
                str(item).strip()
                for item in list((field or {}).get("metadata_path") or [])
                if str(item).strip()
            )
            enum_values = list((field or {}).get("enum_values") or (field or {}).get("options") or [])
            serialized_options: list[dict[str, Any]] = []
            for option in enum_values[:20]:
                if isinstance(option, dict):
                    value = str(option.get("value") or option.get("id") or option.get("label") or "").strip()
                    if not value:
                        continue
                    serialized_options.append(
                        {
                            "value": value,
                            "label": str(option.get("label") or option.get("name") or value).strip(),
                            "aliases": [str(item).strip() for item in list(option.get("aliases") or []) if str(item or "").strip()],
                        }
                    )
                else:
                    normalized = str(option or "").strip()
                    if normalized:
                        serialized_options.append({"value": normalized, "label": normalized, "aliases": []})
            items.append(
                {
                    "key": key,
                    "name": str((field or {}).get("name") or key).strip(),
                    "target": target,
                    "metadata_path": metadata_path,
                    "aliases": [str(item).strip() for item in list((field or {}).get("aliases") or []) if str(item or "").strip()],
                    "options": serialized_options,
                }
            )
        return items

    def _serialize_rule_candidates_for_prompt(
        self,
        candidates: list[QueryAnalysisFilterCandidate],
    ) -> list[dict[str, Any]]:
        """压缩规则候选，供 LLM 在 hybrid 模式下做补充与纠偏。"""

        items: list[dict[str, Any]] = []
        for item in candidates[:16]:
            target_id = ".".join(item.target_id) if isinstance(item.target_id, list) else str(item.target_id)
            if not target_id:
                continue
            items.append(
                {
                    "filter_type": item.filter_type,
                    "filter_value": item.filter_value,
                    "target_id": target_id,
                    "confidence": round(float(item.confidence or 0.0), 4),
                    "source": item.source,
                }
            )
        return items

    def _parse_llm_candidate_response(self, content: str) -> dict[str, Any]:
        """解析 LLM 返回的 JSON 候选。"""

        normalized = str(content or "").strip()
        if not normalized:
            raise ValueError("LLM 未返回候选内容")
        if normalized.startswith("```"):
            normalized = re.sub(r"^```(?:json)?\s*|\s*```$", "", normalized, flags=re.IGNORECASE | re.DOTALL).strip()
        parsed = json.loads(normalized)
        if not isinstance(parsed, dict):
            raise ValueError("LLM 候选输出不是 JSON 对象")
        return parsed

    def _normalize_llm_filter_expression(
        self,
        raw_expression: Any,
        *,
        folders: list[dict[str, Any]],
        doc_tags: list[dict[str, Any]],
        folder_tags: list[dict[str, Any]],
        metadata_fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """把 LLM 表达式限制在声明过的可过滤字段内。"""

        expression = normalize_filter_expression(raw_expression)
        if not expression:
            return {}

        folder_ids = {
            str(item.get("id") or "").strip()
            for item in folders
            if str(item.get("id") or "").strip()
        }
        doc_tag_ids = {
            str(item.get("id") or "").strip()
            for item in doc_tags
            if str(item.get("id") or "").strip()
        }
        folder_tag_ids = {
            str(item.get("id") or "").strip()
            for item in folder_tags
            if str(item.get("id") or "").strip()
        }
        metadata_paths: set[tuple[str, ...]] = set()
        metadata_values_by_path: dict[tuple[str, ...], set[str]] = {}
        search_unit_paths: set[tuple[str, ...]] = set()
        search_unit_values_by_path: dict[tuple[str, ...], set[str]] = {}
        for field in metadata_fields:
            target = str((field or {}).get("target") or "document_metadata").strip() or "document_metadata"
            key = str((field or {}).get("key") or "").strip()
            metadata_path = self._normalize_metadata_prompt_path((field or {}).get("metadata_path")) or ([key] if key else [])
            if not metadata_path:
                continue
            value_set = self._collect_metadata_prompt_values(field)
            if target == "search_unit_metadata":
                search_unit_paths.add(tuple(metadata_path))
                search_unit_values_by_path[tuple(metadata_path)] = value_set
            else:
                metadata_paths.add(tuple(metadata_path))
                metadata_values_by_path[tuple(metadata_path)] = value_set

        def _filter_node(node: dict[str, Any]) -> dict[str, Any]:
            op = str(node.get("op") or "").strip().lower()
            if op in {"and", "or"}:
                items = [
                    normalized
                    for normalized in (_filter_node(dict(item)) for item in list(node.get("items") or []) if isinstance(item, dict))
                    if normalized
                ]
                if not items:
                    return {}
                return items[0] if len(items) == 1 else {"op": op, "items": items[:16]}
            if op == "not":
                items = [
                    normalized
                    for normalized in (_filter_node(dict(item)) for item in list(node.get("items") or [])[:1] if isinstance(item, dict))
                    if normalized
                ]
                return {"op": "not", "items": items} if items else {}

            field = str(node.get("field") or "").strip()
            values = [str(item).strip() for item in list(node.get("values") or []) if str(item).strip()]
            path = tuple(str(item).strip() for item in list(node.get("path") or []) if str(item).strip())
            if field in {"folder", "folder_id"}:
                allowed_values = [item for item in values if item in folder_ids]
            elif field in {"tag", "doc_tag", "tag_id"}:
                allowed_values = [item for item in values if item in doc_tag_ids]
            elif field in {"folder_tag", "folder_tag_id"}:
                allowed_values = [item for item in values if item in folder_tag_ids]
                field = "folder_tag"
            elif field in {"metadata", "document_metadata"}:
                if path not in metadata_paths:
                    return {}
                allowed_values = self._filter_expression_values(values, metadata_values_by_path.get(path) or set())
            elif field == "search_unit_metadata":
                if path not in search_unit_paths:
                    return {}
                allowed_values = self._filter_expression_values(values, search_unit_values_by_path.get(path) or set())
            else:
                return {}

            if op not in {"exists", "not_exists"} and not allowed_values:
                return {}
            return {
                "field": field,
                "op": op,
                "path": list(path),
                "values": allowed_values[:32],
            }

        return _filter_node(expression)

    def _normalize_metadata_prompt_path(self, value: Any) -> list[str]:
        """兼容提示词字段中的数组路径与点号路径。"""

        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value or "").strip()
        return [item for item in text.split(".") if item]

    def _collect_metadata_prompt_values(self, field: dict[str, Any]) -> set[str]:
        """提取字段枚举值；没有枚举时允许 LLM 输出任意文本值。"""

        values: set[str] = set()
        for option in list((field or {}).get("options") or []):
            if isinstance(option, dict):
                value = str(option.get("value") or option.get("id") or option.get("label") or "").strip()
            else:
                value = str(option or "").strip()
            if value:
                values.add(value)
        return values

    def _filter_expression_values(self, values: list[str], allowed_values: set[str]) -> list[str]:
        """字段有枚举时按枚举校验；无枚举时保留 LLM 明确抽取的文本值。"""

        if not allowed_values:
            return values
        return [item for item in values if item in allowed_values]

    def _build_candidate_evidence_distribution(
        self,
        *,
        candidates: list[QueryAnalysisFilterCandidate],
    ) -> dict[str, int]:
        """统计候选证据类型分布，便于前端诊断查看。"""

        distribution: dict[str, int] = {}
        for item in candidates:
            key = str(item.evidence_type or "missing").strip() or "missing"
            distribution[key] = distribution.get(key, 0) + 1
        return distribution

    def _resolve_candidate_query_evidence(
        self,
        *,
        candidate: QueryAnalysisFilterCandidate,
        raw_query: str,
        standalone_query: str,
        rewritten_query: str,
        rule_candidates: list[QueryAnalysisFilterCandidate],
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """为 LLM 候选生成系统侧权威证据，避免信任模型自由描述。"""

        candidate_terms = [
            _normalize_text(item).lower()
            for item in [candidate.filter_value, *list(candidate.candidate_terms or [])]
            if len(_normalize_text(item)) >= 2
        ]
        deduped_terms = list(dict.fromkeys(candidate_terms))
        query_sources = [
            ("raw", _normalize_text(raw_query).lower()),
            ("standalone", _normalize_text(standalone_query).lower()),
            ("rewritten", _normalize_text(rewritten_query).lower()),
        ]

        for source_name, source_query in query_sources:
            if not source_query:
                continue
            for term in deduped_terms:
                if term and term in source_query:
                    if term == _normalize_text(candidate.filter_value).lower():
                        evidence_type = "explicit_query_match" if source_name == "raw" else "rewrite_query_match"
                        return evidence_type, term, source_name, None
                    evidence_type = "alias_match" if source_name == "raw" else "rewrite_query_match"
                    return evidence_type, term, source_name, term

        target_key = ".".join(candidate.target_id) if isinstance(candidate.target_id, list) else str(candidate.target_id)
        for rule_candidate in rule_candidates:
            rule_target_key = ".".join(rule_candidate.target_id) if isinstance(rule_candidate.target_id, list) else str(rule_candidate.target_id)
            if (
                rule_candidate.filter_type == candidate.filter_type
                and rule_target_key == target_key
                and rule_candidate.filter_value == candidate.filter_value
            ):
                return "rule_supported", rule_candidate.filter_value, "rule", None

        return None, None, None, None

    def _normalize_llm_candidates(
        self,
        raw_candidates: Any,
        *,
        folders: list[dict[str, Any]],
        doc_tags: list[dict[str, Any]],
        folder_tags: list[dict[str, Any]],
        metadata_fields: list[dict[str, Any]],
    ) -> list[QueryAnalysisFilterCandidate]:
        """把 LLM 输出规范化为候选列表。"""

        if not isinstance(raw_candidates, list):
            return []

        folder_map = {
            str(item.get("id") or "").strip(): item
            for item in folders
            if str(item.get("id") or "").strip()
        }
        doc_tag_map = {
            str(item.get("id") or "").strip(): item
            for item in doc_tags
            if str(item.get("id") or "").strip()
        }
        folder_tag_map = {
            str(item.get("id") or "").strip(): item
            for item in folder_tags
            if str(item.get("id") or "").strip()
        }
        metadata_field_map: dict[str, dict[str, Any]] = {}
        metadata_path_map: dict[str, list[str]] = {}
        for field in metadata_fields:
            field_key = str((field or {}).get("key") or "").strip()
            if field_key:
                metadata_field_map[field_key] = dict(field or {})
            normalized_path = [
                str(item).strip()
                for item in list((field or {}).get("metadata_path") or [])
                if str(item).strip()
            ]
            if normalized_path:
                metadata_field_map[".".join(normalized_path)] = dict(field or {})
                metadata_path_map[".".join(normalized_path)] = normalized_path

        candidates: list[QueryAnalysisFilterCandidate] = []
        for item in raw_candidates[:10]:
            if not isinstance(item, dict):
                continue
            filter_type = str(item.get("filter_type") or "").strip()
            filter_value = _normalize_text(str(item.get("filter_value") or ""))
            target_id_raw = str(item.get("target_id") or "").strip()
            reason = str(item.get("reason") or "").strip() or None
            evidence_type = str(item.get("evidence_type") or "").strip() or None
            evidence_text = _normalize_text(str(item.get("evidence_text") or ""))
            evidence_query_source = str(item.get("evidence_query_source") or "").strip() or None
            matched_alias = _normalize_text(str(item.get("matched_alias") or ""))
            try:
                confidence = float(item.get("confidence") or 0)
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = max(0.0, min(0.89, confidence))
            if not filter_type or not filter_value or not target_id_raw:
                continue

            target_id: UUID | str | list[str]
            candidate_terms: list[str] = []
            if filter_type in {"folder_id", "tag_id", "folder_tag_id"}:
                allowed_items = {
                    "folder_id": folder_map,
                    "tag_id": doc_tag_map,
                    "folder_tag_id": folder_tag_map,
                }.get(filter_type, {})
                allowed_item = allowed_items.get(target_id_raw)
                if allowed_item is None:
                    continue
                try:
                    target_id = UUID(target_id_raw)
                except ValueError:
                    continue
                candidate_terms = [
                    _normalize_text(str(value))
                    for value in [
                        allowed_item.get("name"),
                        allowed_item.get("path"),
                        *(list(allowed_item.get("aliases") or [])),
                    ]
                    if _normalize_text(str(value or ""))
                ]
            elif filter_type == "document_metadata":
                metadata_field = metadata_field_map.get(target_id_raw)
                if metadata_field is None:
                    continue
                target_id = target_id_raw
                candidate_terms = [
                    _normalize_text(str(value))
                    for value in [
                        filter_value,
                        metadata_field.get("name"),
                        *(list(metadata_field.get("aliases") or [])),
                    ]
                    if _normalize_text(str(value or ""))
                ]
            elif filter_type == "search_unit_metadata":
                if target_id_raw in metadata_path_map:
                    target_id = metadata_path_map[target_id_raw]
                else:
                    target_id = [item for item in target_id_raw.split(".") if item]
                    if not target_id:
                        continue
                metadata_field = metadata_field_map.get(target_id_raw) or metadata_field_map.get(".".join(target_id))
                candidate_terms = [
                    _normalize_text(str(value))
                    for value in [
                        filter_value,
                        (metadata_field or {}).get("name"),
                        *(list((metadata_field or {}).get("aliases") or [])),
                    ]
                    if _normalize_text(str(value or ""))
                ]
            else:
                continue

            candidates.append(
                QueryAnalysisFilterCandidate(
                    filter_type=filter_type,
                    filter_value=filter_value,
                    target_id=target_id,
                    confidence=confidence,
                    source="llm_candidate",
                    layer="llm",
                    validation_status="pending",
                    applied=False,
                    model_reason=reason,
                    evidence_type=evidence_type,
                    evidence_text=evidence_text or None,
                    evidence_query_source=evidence_query_source,
                    matched_alias=matched_alias or None,
                    candidate_terms=list(dict.fromkeys(candidate_terms)),
                )
            )
        return candidates

    def _validate_llm_candidates(
        self,
        *,
        candidates: list[QueryAnalysisFilterCandidate],
        existing_filters: RetrievalFilterSet,
        rule_candidates: list[QueryAnalysisFilterCandidate],
        metadata_fields: list[dict[str, Any]],
        raw_query: str,
        standalone_query: str,
        rewritten_query: str,
        min_confidence: float,
        allow_rule_override: bool = False,
    ) -> list[QueryAnalysisFilterCandidate]:
        """校验 LLM 候选，并标记可升级与冲突状态。"""

        rule_index = {
            (
                item.filter_type,
                ".".join(item.target_id) if isinstance(item.target_id, list) else str(item.target_id),
            ): item
            for item in rule_candidates
        }

        metadata_allowed_values: dict[str, set[str]] = {}
        for field in metadata_fields:
            key = str((field or {}).get("key") or "").strip()
            path = ".".join(
                str(item).strip()
                for item in list((field or {}).get("metadata_path") or [])
                if str(item).strip()
            )
            values: set[str] = set()
            for option in list((field or {}).get("enum_values") or (field or {}).get("options") or []):
                if isinstance(option, dict):
                    normalized = str(option.get("value") or option.get("id") or option.get("label") or "").strip()
                    if normalized:
                        values.add(normalized)
                else:
                    normalized = str(option or "").strip()
                    if normalized:
                        values.add(normalized)
            if key:
                metadata_allowed_values[key] = values
            if path:
                metadata_allowed_values[path] = values

        for candidate in candidates:
            target_key = ".".join(candidate.target_id) if isinstance(candidate.target_id, list) else str(candidate.target_id)

            if candidate.confidence < max(0.0, min(1.0, float(min_confidence))):
                candidate.validation_status = "rejected"
                candidate.validation_reason = "低于最小置信度阈值"
                continue

            (
                resolved_evidence_type,
                resolved_evidence_text,
                resolved_evidence_query_source,
                resolved_matched_alias,
            ) = self._resolve_candidate_query_evidence(
                candidate=candidate,
                raw_query=raw_query,
                standalone_query=standalone_query,
                rewritten_query=rewritten_query,
                rule_candidates=rule_candidates,
            )
            candidate.evidence_type = resolved_evidence_type
            candidate.evidence_text = resolved_evidence_text
            candidate.evidence_query_source = resolved_evidence_query_source
            candidate.matched_alias = resolved_matched_alias

            if candidate.filter_type in {"folder_id", "tag_id", "folder_tag_id"} and not resolved_evidence_type:
                candidate.validation_status = "rejected"
                candidate.validation_reason = "缺少查询证据，命中仅来自候选池"
                continue

            if candidate.filter_type == "folder_id":
                if existing_filters.folder_ids and candidate.target_id not in existing_filters.folder_ids:
                    candidate.validation_status = "conflicted"
                    candidate.validation_reason = "与已有目录过滤冲突"
                    continue
            elif candidate.filter_type == "tag_id":
                if existing_filters.tag_ids and candidate.target_id not in existing_filters.tag_ids:
                    candidate.validation_status = "conflicted"
                    candidate.validation_reason = "与已有文档标签过滤冲突"
                    continue
            elif candidate.filter_type == "folder_tag_id":
                if existing_filters.folder_tag_ids and candidate.target_id not in existing_filters.folder_tag_ids:
                    candidate.validation_status = "conflicted"
                    candidate.validation_reason = "与已有文件夹标签过滤冲突"
                    continue
            elif candidate.filter_type == "document_metadata":
                existing_value = existing_filters.document_metadata.get(target_key)
                if existing_value is not None and str(existing_value) != candidate.filter_value:
                    candidate.validation_status = "conflicted"
                    candidate.validation_reason = "与已有文档属性过滤冲突"
                    continue
            elif candidate.filter_type == "search_unit_metadata":
                existing_value = self._read_nested_search_unit_metadata_value(
                    existing_filters.search_unit_metadata,
                    candidate.target_id,
                )
                if existing_value is not None and str(existing_value) != candidate.filter_value:
                    candidate.validation_status = "conflicted"
                    candidate.validation_reason = "与已有结构化过滤冲突"
                    continue

            rule_candidate = rule_index.get((candidate.filter_type, target_key))
            if rule_candidate is not None and rule_candidate.filter_value != candidate.filter_value:
                if allow_rule_override:
                    candidate.validation_reason = "与规则候选冲突，待 hybrid 阶段复核"
                else:
                    candidate.validation_status = "conflicted"
                    candidate.validation_reason = "与规则候选冲突"
                    continue

            if candidate.filter_type in {"document_metadata", "search_unit_metadata"}:
                allowed_values = metadata_allowed_values.get(target_key) or set()
                if allowed_values and candidate.filter_value not in allowed_values:
                    candidate.validation_status = "rejected"
                    candidate.validation_reason = "候选值不在 schema 可选值中"
                    continue

            candidate.validation_status = "validated"
            candidate.validation_reason = (
                f"证据通过校验：{candidate.evidence_type}"
                if candidate.evidence_type
                else "通过存在性与冲突校验"
            )

        return candidates

    def _reconcile_rule_candidates_with_llm(
        self,
        *,
        rule_candidates: list[QueryAnalysisFilterCandidate],
        llm_candidates: list[QueryAnalysisFilterCandidate],
        correction_confidence_threshold: float,
    ) -> list[QueryAnalysisFilterCandidate]:
        """在 hybrid 模式下，让高置信 LLM 候选有机会纠偏同目标规则候选。"""

        threshold = max(0.0, min(1.0, float(correction_confidence_threshold)))
        llm_override_keys: set[tuple[str, str]] = set()
        llm_override_values: dict[tuple[str, str], str] = {}
        for candidate in llm_candidates:
            target_key = ".".join(candidate.target_id) if isinstance(candidate.target_id, list) else str(candidate.target_id)
            if not target_key:
                continue
            if candidate.validation_status != "validated" or candidate.confidence < threshold:
                continue
            llm_override_keys.add((candidate.filter_type, target_key))
            llm_override_values[(candidate.filter_type, target_key)] = candidate.filter_value

        for candidate in rule_candidates:
            target_key = ".".join(candidate.target_id) if isinstance(candidate.target_id, list) else str(candidate.target_id)
            key = (candidate.filter_type, target_key)
            override_value = llm_override_values.get(key)
            if not override_value or override_value == candidate.filter_value:
                continue
            candidate.validation_status = "corrected_by_llm"
            candidate.validation_reason = f"被 LLM 候选纠偏为 {override_value}"
            candidate.applied = False
        return rule_candidates

    def _merge_filter_expressions(
        self,
        *,
        locked_expression: dict[str, Any] | None,
        additive_expression: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """把 LLM 表达式作为追加约束并入现有表达式，只允许收紧不允许放宽。"""

        base = normalize_filter_expression(locked_expression or {})
        extra = normalize_filter_expression(additive_expression or {})
        if not base:
            return extra
        if not extra:
            return base
        return {"op": "and", "items": [base, extra]}

    def _apply_validated_llm_candidates(
        self,
        *,
        filters: RetrievalFilterSet,
        candidates: list[QueryAnalysisFilterCandidate],
        upgrade_confidence_threshold: float,
        max_upgrade_count: int,
    ) -> RetrievalFilterSet:
        """把通过严格校验的 LLM 候选升级为硬过滤。"""

        result = self._clone_filters(filters)
        normalized_threshold = max(0.0, min(1.0, float(upgrade_confidence_threshold)))
        normalized_limit = max(1, int(max_upgrade_count))
        applied_count = 0
        seen_targets: set[tuple[str, str]] = set()
        for candidate in sorted(candidates, key=lambda item: item.confidence, reverse=True):
            target_key = ".".join(candidate.target_id) if isinstance(candidate.target_id, list) else str(candidate.target_id)
            if candidate.validation_status != "validated" or candidate.confidence < normalized_threshold:
                continue
            if applied_count >= normalized_limit:
                candidate.validation_status = "rejected"
                candidate.validation_reason = "超过本轮可升级候选上限"
                continue
            candidate_key = (candidate.filter_type, target_key)
            if candidate_key in seen_targets:
                candidate.validation_status = "rejected"
                candidate.validation_reason = "同目标已有更高置信候选升级"
                continue
            before_applied = candidate.applied
            result = self._apply_filter_candidates(filters=result, candidates=[candidate])
            if candidate.applied and not before_applied:
                candidate.upgraded_to_hard_filter = True
                applied_count += 1
                seen_targets.add(candidate_key)
        return result

    def _build_llm_candidate_metrics(
        self,
        *,
        candidates: list[QueryAnalysisFilterCandidate],
    ) -> dict[str, Any]:
        """构建 LLM 候选质量统计，便于调试与运营观察。"""

        total = len(candidates)
        if total <= 0:
            return {
                "validation_rate": 0.0,
                "upgrade_rate": 0.0,
                "avg_confidence": 0.0,
                "avg_validated_confidence": 0.0,
                "status_distribution": {},
                "layer_distribution": {},
                "rejection_reason_distribution": {},
            }

        validated = [item for item in candidates if item.validation_status == "validated"]
        upgraded = [item for item in candidates if item.upgraded_to_hard_filter]
        status_distribution: dict[str, int] = {}
        layer_distribution: dict[str, int] = {}
        rejection_reason_distribution: dict[str, int] = {}
        for item in candidates:
            status_distribution[item.validation_status] = status_distribution.get(item.validation_status, 0) + 1
            layer_distribution[item.layer] = layer_distribution.get(item.layer, 0) + 1
            if item.validation_status == "rejected" and item.validation_reason:
                rejection_reason_distribution[item.validation_reason] = (
                    rejection_reason_distribution.get(item.validation_reason, 0) + 1
                )

        avg_confidence = sum(item.confidence for item in candidates) / total
        avg_validated_confidence = (
            sum(item.confidence for item in validated) / len(validated)
            if validated
            else 0.0
        )
        return {
            "validation_rate": round(len(validated) / total, 4),
            "upgrade_rate": round(len(upgraded) / total, 4),
            "avg_confidence": round(avg_confidence, 4),
            "avg_validated_confidence": round(avg_validated_confidence, 4),
            "status_distribution": status_distribution,
            "layer_distribution": layer_distribution,
            "rejection_reason_distribution": rejection_reason_distribution,
        }

    def _read_nested_search_unit_metadata_value(
        self,
        search_unit_metadata: dict[str, Any],
        target_id: UUID | str | list[str],
    ) -> Any:
        """读取 search_unit_metadata 上已存在的嵌套值。"""

        if isinstance(target_id, list):
            metadata_path = [str(item).strip() for item in target_id if str(item).strip()]
        else:
            metadata_path = [item for item in str(target_id).split(".") if item]
        current: Any = search_unit_metadata
        for key in metadata_path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    def _apply_nested_search_unit_metadata_filter(
        self,
        *,
        search_unit_metadata: dict[str, Any],
        metadata_path: list[str],
        filter_value: str,
    ) -> bool:
        """将 search_unit_metadata 候选写入嵌套路径。"""

        normalized_path = [item for item in metadata_path if item]
        if not normalized_path:
            return False

        current: dict[str, Any] = search_unit_metadata
        for key in normalized_path[:-1]:
            next_value = current.get(key)
            if not isinstance(next_value, dict):
                next_value = {}
                current[key] = next_value
            current = next_value

        leaf_key = normalized_path[-1]
        if current.get(leaf_key) == filter_value:
            return False
        if leaf_key in current:
            return False
        current[leaf_key] = filter_value
        return True
