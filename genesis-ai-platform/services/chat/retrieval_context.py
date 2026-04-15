"""聊天服务拆分模块：retrieval_context。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestException, NotFoundException
from models.chat_message import ChatMessage, ChatMessageCitation
from models.chat_session import ChatSession, ChatSessionCapabilityBinding, ChatSessionStats
from models.chat_space import ChatSpace
from models.chat_turn import ChatTurn, ChatTurnRetrieval
from models.folder import Folder
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.resource_tag import TARGET_TYPE_FOLDER, ResourceTag
from models.tag import Tag
from models.retrieval_profile import RetrievalProfile
from models.tenant_model import TenantModel
from models.tenant_model_provider import TenantModelProvider
from models.platform_model import PlatformModel
from models.user import User
from models.workflow import Workflow
from rag.retrieval.hybrid import HybridRetrievalService
from services.model_platform_service import ModelInvocationService
from schemas.chat import (
    ChatBootstrapResponse,
    ChatCapabilityBindingCreate,
    ChatCapabilityBindingUpdate,
    ChatMessageCitationRead,
    ChatMessageRead,
    ChatMessageSendRequest,
    ChatSelectorOption,
    ChatSendResponse,
    ChatSessionCreate,
    ChatSessionRead,
    ChatSessionStatsRead,
    ChatSessionUpdate,
    ChatSpaceCreate,
    ChatSpaceRead,
    ChatSpaceUpdate,
    ChatTurnRead,
    RetrievalProfileOption,
    WorkflowOption,
)



class ChatRetrievalContextMixin:
    """按职责拆分的聊天服务能力。"""

    _CHAT_PROMPT_METADATA_WHITELIST = ("地区", "部门", "适用主体", "生效时间")

    async def _retrieve_session_context(
        self: Any,
        *,
        session_id: UUID,
        turn_id: UUID,
        current_user: User,
        query: str,
        effective_config: dict[str, Any],
        tenant_model_id: Optional[UUID],
    ) -> dict[str, Any]:
        """执行会话级真实检索，并写入检索明细。"""

        bindings = await self._load_bound_knowledge_bases(
            session_id=session_id,
            tenant_id=current_user.tenant_id,
            effective_config=effective_config,
        )
        if not bindings:
            await self._replace_turn_retrievals(turn_id=turn_id, rows=[])
            return {
                "items": [],
                "summary": {
                    "knowledge_bases": [],
                    "result_count": 0,
                    "selected_count": 0,
                },
            }

        all_items: list[dict[str, Any]] = []
        analysis_debug: list[dict[str, Any]] = []
        retrieval_debug_traces: list[dict[str, Any]] = []
        glossary_context: list[dict[str, Any]] = []
        filter_inheritance_evaluations: dict[str, dict[str, Any]] = {}
        retrieval_service = HybridRetrievalService(self.db)
        query_rewrite_context = await self._load_query_rewrite_context(
            session_id=session_id,
            turn_id=turn_id,
            tenant_id=current_user.tenant_id,
            effective_config=effective_config,
        )
        filter_inheritance_package = await self._resolve_filter_inheritance_package(
            session_id=session_id,
            current_user=current_user,
            current_query=query,
            bindings=bindings,
            effective_config=effective_config,
            tenant_model_id=tenant_model_id,
        )
        for kb, binding in bindings:
            merged_config = self._merge_chat_retrieval_config(
                kb=kb,
                effective_config=effective_config,
                binding_config=binding.config,
            )
            merged_config.setdefault("debug_trace_level", "detailed")
            raw_filters = self._extract_chat_retrieval_filters(binding.config)
            inherited_filters = dict(
                (filter_inheritance_package.get("merged_filters_by_kb") or {}).get(str(kb.id)) or raw_filters
            )
            result = await retrieval_service.search(
                current_user=current_user,
                kb=kb,
                query=query,
                raw_config=merged_config,
                raw_filters=inherited_filters,
                query_rewrite_context=query_rewrite_context,
            )
            retrieval_debug_traces.append(
                {
                    "kb_id": str(kb.id),
                    "kb_name": kb.name,
                    "binding_role": binding.binding_role,
                    "pipeline_trace": dict((result.get("debug") or {}).get("pipeline_trace") or {}),
                }
            )
            if (
                effective_config.get("enable_filter_inheritance_evaluation", False)
                and inherited_filters != raw_filters
            ):
                baseline_result = await retrieval_service.search(
                    current_user=current_user,
                    kb=kb,
                    query=query,
                    raw_config=merged_config,
                    raw_filters=raw_filters,
                    query_rewrite_context=query_rewrite_context,
                )
                filter_inheritance_evaluations[str(kb.id)] = self._build_filter_inheritance_effect_evaluation(
                    kb=kb,
                    inherited_result=result,
                    baseline_result=baseline_result,
                )
            query_analysis = dict(result.get("query_analysis") or {})
            if query_analysis:
                query_analysis["kb_id"] = str(kb.id)
                query_analysis["kb_name"] = kb.name
                query_analysis["filter_inheritance"] = dict(
                    ((filter_inheritance_package.get("debug") or {}).get("kb_decisions") or {}).get(str(kb.id)) or {}
                )
                if str(kb.id) in filter_inheritance_evaluations:
                    query_analysis["filter_inheritance_effect_evaluation"] = dict(
                        filter_inheritance_evaluations.get(str(kb.id)) or {}
                    )
                analysis_debug.append(query_analysis)
                for glossary in list(query_analysis.get("glossary_entries") or []):
                    glossary_context.append(
                        {
                            "kb_id": str(kb.id),
                            "kb_name": kb.name,
                            "term": glossary.get("term"),
                            "definition": glossary.get("definition"),
                            "examples": glossary.get("examples"),
                            "scope": glossary.get("scope"),
                        }
                    )
            for item in result.get("items") or []:
                item["kb_id"] = str(kb.id)
                item["kb_name"] = kb.name
                item["binding_role"] = binding.binding_role
                all_items.append(item)

        selected_items = self._merge_cross_kb_results(
            query=query,
            effective_config=effective_config,
            items=all_items,
        )
        selected_items = await self._attach_prompt_context_headers(
            items=selected_items,
            query=query,
        )
        persistent_context_payload = await self._build_persistent_context_payload(
            effective_config=effective_config,
            bindings=bindings,
            selected_items=selected_items,
        )
        llm_prompt_context = self._build_llm_prompt_context_summary(
            selected_items=selected_items,
            glossary_context=self._deduplicate_glossary_context(glossary_context),
            persistent_context=persistent_context_payload,
        )
        await self._replace_turn_retrievals(
            turn_id=turn_id,
            rows=self._build_turn_retrieval_rows(
                tenant_id=current_user.tenant_id,
                session_id=session_id,
                turn_id=turn_id,
                items=selected_items,
            ),
        )
        filter_inheritance_package = self._attach_filter_inheritance_effect_evaluation(
            package=filter_inheritance_package,
            evaluations=filter_inheritance_evaluations,
        )
        return {
            "items": selected_items,
            "summary": {
                "knowledge_bases": [kb.name for kb, _binding in bindings],
                "result_count": len(all_items),
                "selected_count": len(selected_items),
                "query_analysis": analysis_debug,
                "pipeline_traces": retrieval_debug_traces,
                "filter_inheritance": dict(filter_inheritance_package.get("summary") or {}),
                "llm_prompt_context": llm_prompt_context,
            },
            "glossary_context": self._deduplicate_glossary_context(glossary_context),
            "persistent_context": persistent_context_payload,
            "filter_inheritance": filter_inheritance_package,
        }

    async def _load_query_rewrite_context(
        self: Any,
        *,
        session_id: UUID,
        turn_id: UUID,
        tenant_id: UUID,
        effective_config: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """加载查询改写所需的最近几轮对话上下文。"""

        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.session_id == session_id,
                ChatMessage.is_visible.is_(True),
                or_(ChatMessage.turn_id.is_(None), ChatMessage.turn_id != turn_id),
                ChatMessage.role.in_(("user", "assistant")),
                ChatMessage.status.in_(("completed", "streaming")),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        rows.reverse()
        result: list[dict[str, str]] = []
        manual_context = list((effective_config or {}).get("query_rewrite_context") or [])
        for item in manual_context:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            result.append({"role": role, "content": content})
        for item in rows:
            role = str(item.role or "").strip().lower()
            content = str(item.content or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            result.append({"role": role, "content": content})
        return result[-12:]

    async def _load_bound_knowledge_bases(
        self: Any,
        *,
        session_id: UUID,
        tenant_id: UUID,
        effective_config: Optional[dict[str, Any]] = None,
    ) -> list[tuple[KnowledgeBase, Any]]:
        """加载当前会话启用的知识库绑定。"""

        # 发送消息时允许携带“未保存草稿”的临时知识库绑定，优先级高于会话已保存绑定。
        runtime_override_enabled = bool((effective_config or {}).get("runtime_knowledge_base_bindings_enabled"))
        runtime_bindings = list((effective_config or {}).get("runtime_knowledge_base_bindings") or [])
        if runtime_override_enabled:
            ordered_bindings: list[dict[str, Any]] = []
            kb_ids: list[UUID] = []
            for index, item in enumerate(runtime_bindings):
                if not isinstance(item, dict):
                    continue
                kb_id_raw = item.get("kb_id")
                if not kb_id_raw:
                    continue
                try:
                    kb_id = UUID(str(kb_id_raw))
                except (TypeError, ValueError):
                    continue
                if kb_id in kb_ids:
                    continue
                kb_ids.append(kb_id)
                ordered_bindings.append(
                    {
                        "kb_id": kb_id,
                        "binding_role": str(item.get("binding_role") or ("primary" if index == 0 else "secondary")),
                        "is_enabled": item.get("is_enabled", True) is not False,
                        "priority": int(item.get("priority") or (100 + index)),
                        "config": dict(item.get("config") or {}),
                    }
                )

            if not kb_ids:
                return []

            kb_stmt = select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.id.in_(kb_ids),
            )
            kb_rows = (await self.db.execute(kb_stmt)).scalars().all()
            kb_map = {item.id: item for item in kb_rows}
            result: list[tuple[KnowledgeBase, Any]] = []
            for item in sorted(ordered_bindings, key=lambda row: (row["priority"], str(row["kb_id"]))):
                kb = kb_map.get(item["kb_id"])
                if not kb or item["is_enabled"] is False:
                    continue
                result.append(
                    (
                        kb,
                        type(
                            "RuntimeKnowledgeBaseBinding",
                            (),
                            {
                                "binding_role": item["binding_role"],
                                "priority": item["priority"],
                                "config": item["config"],
                                "is_enabled": True,
                            },
                        )(),
                    )
                )
            return result

        stmt = (
            select(KnowledgeBase, ChatSessionCapabilityBinding)
            .join(
                ChatSessionCapabilityBinding,
                ChatSessionCapabilityBinding.capability_id == KnowledgeBase.id,
            )
            .where(
                ChatSessionCapabilityBinding.tenant_id == tenant_id,
                ChatSessionCapabilityBinding.session_id == session_id,
                ChatSessionCapabilityBinding.capability_type == "knowledge_base",
                ChatSessionCapabilityBinding.is_enabled.is_(True),
                KnowledgeBase.tenant_id == tenant_id,
            )
            .order_by(ChatSessionCapabilityBinding.priority.asc(), KnowledgeBase.name.asc())
        )
        return list((await self.db.execute(stmt)).all())

    def _merge_chat_retrieval_config(
        self: Any,
        *,
        kb: KnowledgeBase,
        effective_config: dict[str, Any],
        binding_config: dict[str, Any],
    ) -> dict[str, Any]:
        """合并聊天检索配置。

        优先级：
        - 知识库 retrieval_test 默认
        - 会话级 effective_config
        - 绑定级 config.retrieval
        """

        kb_defaults = dict((kb.retrieval_config or {}).get("retrieval_test") or {})
        binding_retrieval = dict((binding_config or {}).get("retrieval") or {})
        return self._merge_dicts(kb_defaults, effective_config, binding_retrieval)

    def _extract_chat_retrieval_filters(self: Any, binding_config: dict[str, Any]) -> dict[str, Any]:
        """从绑定配置中提取过滤条件。"""

        return dict((binding_config or {}).get("filters") or {})

    def _merge_cross_kb_results(
        self: Any,
        *,
        query: str,
        effective_config: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """跨知识库合并检索结果。"""

        if not items:
            return []

        rerank_top_n = int(effective_config.get("rerank_top_n") or 3)
        final_top_k = int(effective_config.get("search_depth_k") or rerank_top_n or 5)
        min_score = float(effective_config.get("min_score") or 0.0)

        scored_items = list(items)
        scored_items.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
        if rerank_top_n > 0:
            scored_items = scored_items[: max(rerank_top_n, final_top_k)]

        query_terms = self._tokenize_query_terms(query)
        rescored_items: list[dict[str, Any]] = []
        for item in scored_items:
            snippet = str(item.get("content") or "")
            title = str(item.get("title") or "")
            lexical_bonus = self._compute_term_overlap_bonus(query_terms, f"{title}\n{snippet}")
            merged_score = min(1.0, float(item.get("score") or 0.0) * 0.9 + lexical_bonus * 0.1)
            item["score"] = round(merged_score, 4)
            rescored_items.append(item)

        rescored_items.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
        filtered_items = [item for item in rescored_items if float(item.get("score") or 0.0) >= min_score]
        selected = filtered_items[: max(1, final_top_k)]
        for index, item in enumerate(selected, start=1):
            item["rank"] = index
        return selected

    def _build_retrieval_context_prompt(self: Any, retrieval_package: dict[str, Any]) -> Optional[str]:
        """将检索结果转换为系统上下文。"""

        items = list(retrieval_package.get("items") or [])
        glossary_context = list(retrieval_package.get("glossary_context") or [])
        persistent_context = dict(retrieval_package.get("persistent_context") or {})
        kb_contexts = list(persistent_context.get("kb_contexts") or [])
        doc_contexts = list(persistent_context.get("doc_contexts") or [])
        if not items and not glossary_context and not kb_contexts and not doc_contexts:
            return None

        lines = [
            "以下是检索到的参考资料，请优先基于这些内容回答。",
            "要求：",
            "1. 如果资料不足以支持结论，要明确说明。",
            "2. 不要虚构未检索到的细节。",
            "3. 优先使用高排名结果，并在回答中保持信息一致。",
        ]
        if kb_contexts:
            lines.extend(
                [
                    "",
                    "回答补充说明：",
                ]
            )
            for item in kb_contexts:
                kb_name = str(item.get("kb_name") or "").strip()
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                title = f"{kb_name}" if kb_name else "当前知识库"
                lines.append(f"- {title}: {content}")

        if doc_contexts:
            lines.extend(
                [
                    "",
                    "命中文档补充说明：",
                ]
            )
            for item in doc_contexts:
                document_name = str(item.get("document_name") or "").strip() or "未命名文档"
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                lines.append(f"- {document_name}: {content}")

        if glossary_context:
            lines.extend(
                [
                    "",
                    "专业术语说明：",
                ]
            )
            for item in glossary_context:
                term = str(item.get("term") or "").strip()
                definition = str(item.get("definition") or "").strip()
                if not term or not definition:
                    continue
                kb_name = str(item.get("kb_name") or "").strip()
                examples = str(item.get("examples") or "").strip()
                title = f"{term}（来源知识库：{kb_name}）" if kb_name else term
                lines.append(f"- {title}: {definition}")
                if examples:
                    lines.append(f"  示例: {examples}")

        if items:
            lines.extend(
                [
                    "",
                    "检索上下文：",
                ]
            )
        for item in items:
            source = dict(item.get("source") or {})
            metadata = dict(item.get("metadata") or {})
            prompt_header = dict(item.get("prompt_header") or {})
            scope_text = "、".join(metadata.get("matched_scopes") or [])
            page_numbers = list(source.get("page_numbers") or [])
            page_text = f" | 页码: {','.join(str(page) for page in page_numbers)}" if page_numbers else ""
            lines.extend(
                [
                    f"[{item.get('rank')}] {source.get('document_name')}{page_text}",
                    f"得分: {item.get('score')}",
                    f"命中域: {scope_text or 'default'}",
                ]
            )
            header_lines = self._build_prompt_header_lines(prompt_header)
            lines.extend(header_lines)
            lines.extend(
                [
                    f"内容: {item.get('content')}",
                    "",
                ]
            )
        return "\n".join(lines).strip()

    async def _attach_prompt_context_headers(
        self: Any,
        *,
        items: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        """为聊天回答阶段补充结构化头信息。"""

        if not items:
            return items

        kb_doc_ids: list[UUID] = []
        for item in items:
            metadata = dict(item.get("metadata") or {})
            kb_doc_id_raw = str(metadata.get("kb_doc_id") or "").strip()
            if not kb_doc_id_raw:
                continue
            try:
                kb_doc_ids.append(UUID(kb_doc_id_raw))
            except ValueError:
                continue
        normalized_ids = list(dict.fromkeys(kb_doc_ids))
        if not normalized_ids:
            return items

        kb_doc_rows = (
            await self.db.execute(
                select(KnowledgeBaseDocument.id, KnowledgeBaseDocument.folder_id, KnowledgeBaseDocument.custom_metadata)
                .where(KnowledgeBaseDocument.id.in_(normalized_ids))
            )
        ).all()
        kb_doc_map: dict[UUID, dict[str, Any]] = {
            kb_doc_id: {
                "folder_id": folder_id,
                "custom_metadata": dict(custom_metadata or {}),
            }
            for kb_doc_id, folder_id, custom_metadata in kb_doc_rows
        }

        folder_ids = [payload.get("folder_id") for payload in kb_doc_map.values() if payload.get("folder_id") is not None]
        folder_map: dict[UUID, Folder] = {}
        if folder_ids:
            folders = (
                await self.db.execute(
                    select(Folder).where(Folder.id.in_(list(dict.fromkeys(folder_ids))))
                )
            ).scalars().all()
            folder_map = {folder.id: folder for folder in folders}

        path_folder_ids: set[UUID] = set()
        kb_doc_folder_paths: dict[UUID, list[UUID]] = {}
        for kb_doc_id, payload in kb_doc_map.items():
            folder_id = payload.get("folder_id")
            folder = folder_map.get(folder_id) if folder_id is not None else None
            path_ids = self._parse_folder_path_ids(str(folder.path or "").strip()) if folder is not None else []
            if folder_id is not None and folder_id not in path_ids:
                path_ids.append(folder_id)
            kb_doc_folder_paths[kb_doc_id] = path_ids
            path_folder_ids.update(path_ids)

        folder_tag_map: dict[UUID, list[str]] = {}
        if path_folder_ids:
            folder_tag_rows = (
                await self.db.execute(
                    select(ResourceTag.target_id, Tag.name)
                    .join(Tag, Tag.id == ResourceTag.tag_id)
                    .where(
                        ResourceTag.target_type == TARGET_TYPE_FOLDER,
                        ResourceTag.action == "add",
                        ResourceTag.target_id.in_(list(path_folder_ids)),
                    )
                )
            ).all()
            for folder_id, tag_name in folder_tag_rows:
                normalized_name = str(tag_name or "").strip()
                if not normalized_name:
                    continue
                folder_tag_map.setdefault(folder_id, [])
                if normalized_name not in folder_tag_map[folder_id]:
                    folder_tag_map[folder_id].append(normalized_name)

        normalized_query = str(query or "").strip().lower()
        for item in items:
            metadata = dict(item.get("metadata") or {})
            kb_doc_id_raw = str(metadata.get("kb_doc_id") or "").strip()
            if not kb_doc_id_raw:
                continue
            try:
                kb_doc_id = UUID(kb_doc_id_raw)
            except ValueError:
                continue
            kb_doc_payload = kb_doc_map.get(kb_doc_id) or {}
            doc_tags = self._select_prompt_doc_tags(
                tags=list(item.get("tags") or []),
                normalized_query=normalized_query,
            )
            folder_tags = self._select_prompt_folder_tags(
                path_ids=kb_doc_folder_paths.get(kb_doc_id) or [],
                folder_tag_map=folder_tag_map,
            )
            metadata_summary = self._select_prompt_metadata_summary(
                custom_metadata=dict(kb_doc_payload.get("custom_metadata") or {}),
            )
            item["prompt_header"] = {
                "doc_tags": doc_tags,
                "folder_tags": folder_tags,
                "metadata": metadata_summary,
            }
        return items

    def _build_prompt_header_lines(self: Any, prompt_header: dict[str, Any]) -> list[str]:
        """把结构化头信息转换成适合写入回答提示词的短行。"""

        lines: list[str] = []
        doc_tags = [str(item).strip() for item in list(prompt_header.get("doc_tags") or []) if str(item).strip()]
        folder_tags = [str(item).strip() for item in list(prompt_header.get("folder_tags") or []) if str(item).strip()]
        metadata = dict(prompt_header.get("metadata") or {})
        if doc_tags:
            lines.append(f"文档标签: {', '.join(doc_tags)}")
        if folder_tags:
            lines.append(f"文件夹业务标签: {', '.join(folder_tags)}")
        if metadata:
            metadata_text = "；".join(f"{key}={value}" for key, value in metadata.items() if str(value).strip())
            if metadata_text:
                lines.append(f"文档元数据: {metadata_text}")
        return lines

    def _build_llm_prompt_context_summary(
        self: Any,
        *,
        selected_items: list[dict[str, Any]],
        glossary_context: list[dict[str, Any]],
        persistent_context: dict[str, Any],
    ) -> dict[str, Any]:
        """构建回答阶段上下文摘要，方便前端诊断展示。"""

        kb_contexts = list(persistent_context.get("kb_contexts") or [])
        doc_contexts = list(persistent_context.get("doc_contexts") or [])
        result_headers: list[dict[str, Any]] = []
        for item in selected_items[:8]:
            source = dict(item.get("source") or {})
            metadata = dict(item.get("metadata") or {})
            result_headers.append(
                {
                    "rank": item.get("rank"),
                    "title": str(item.get("title") or source.get("document_name") or "未命名文档"),
                    "document_name": str(source.get("document_name") or item.get("title") or "未命名文档"),
                    "score": item.get("score"),
                    "matched_scopes": list(metadata.get("matched_scopes") or []),
                    "prompt_header": dict(item.get("prompt_header") or {}),
                }
            )

        return {
            "kb_contexts": [
                {
                    "kb_id": str(item.get("kb_id") or ""),
                    "kb_name": str(item.get("kb_name") or ""),
                    "content_preview": self._truncate_text(str(item.get("content") or ""), 220),
                }
                for item in kb_contexts[:6]
            ],
            "doc_contexts": [
                {
                    "kb_id": str(item.get("kb_id") or ""),
                    "kb_doc_id": str(item.get("kb_doc_id") or ""),
                    "kb_name": str(item.get("kb_name") or ""),
                    "document_name": str(item.get("document_name") or ""),
                    "source": str(item.get("source") or ""),
                    "content_preview": self._truncate_text(str(item.get("content") or ""), 220),
                }
                for item in doc_contexts[:8]
            ],
            "glossary_entries": [
                {
                    "kb_id": str(item.get("kb_id") or ""),
                    "kb_name": str(item.get("kb_name") or ""),
                    "term": str(item.get("term") or ""),
                    "definition": self._truncate_text(str(item.get("definition") or ""), 180),
                    "examples": self._truncate_text(str(item.get("examples") or ""), 160),
                }
                for item in glossary_context[:8]
            ],
            "result_headers": result_headers,
        }

    def _select_prompt_doc_tags(self: Any, *, tags: list[Any], normalized_query: str) -> list[str]:
        """挑选更适合传给回答模型的文档标签。"""

        normalized_tags = []
        for item in tags:
            tag_name = str(item or "").strip()
            if tag_name and tag_name not in normalized_tags:
                normalized_tags.append(tag_name)
        if not normalized_tags:
            return []
        if not normalized_query:
            return normalized_tags[:3]
        matched = [tag for tag in normalized_tags if tag.lower() in normalized_query or normalized_query in tag.lower()]
        ordered = matched + [tag for tag in normalized_tags if tag not in matched]
        return ordered[:3]

    def _select_prompt_folder_tags(
        self: Any,
        *,
        path_ids: list[UUID],
        folder_tag_map: dict[UUID, list[str]],
    ) -> list[str]:
        """从目录路径上挑选更偏业务域的高层标签。"""

        result: list[str] = []
        for folder_id in path_ids[:3]:
            for tag_name in folder_tag_map.get(folder_id, []):
                normalized_name = str(tag_name or "").strip()
                if normalized_name and normalized_name not in result:
                    result.append(normalized_name)
                if len(result) >= 3:
                    return result
        return result

    def _select_prompt_metadata_summary(self: Any, *, custom_metadata: dict[str, Any]) -> dict[str, str]:
        """从文档元数据中挑选白名单字段，避免把整包 JSON 直接传给大模型。"""

        result: dict[str, str] = {}
        for key in self._CHAT_PROMPT_METADATA_WHITELIST:
            value = custom_metadata.get(key)
            serialized = self._serialize_prompt_metadata_value(value)
            if serialized:
                result[key] = serialized
        return result

    def _serialize_prompt_metadata_value(self: Any, value: Any) -> str:
        """序列化白名单元数据字段。"""

        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return str(value).strip()
        if isinstance(value, list):
            normalized_items = [str(item).strip() for item in value if str(item).strip()]
            return "、".join(normalized_items[:5])
        if isinstance(value, dict):
            normalized_items = [
                f"{str(key).strip()}={str(item).strip()}"
                for key, item in value.items()
                if str(key).strip() and str(item).strip()
            ]
            return "；".join(normalized_items[:5])
        return str(value).strip()

    def _parse_folder_path_ids(self: Any, value: str) -> list[UUID]:
        """把目录路径字符串解析成 UUID 列表。"""

        if not value:
            return []
        result: list[UUID] = []
        for item in [segment.strip() for segment in value.split("/") if segment.strip()]:
            try:
                folder_id = UUID(item)
            except ValueError:
                continue
            if folder_id not in result:
                result.append(folder_id)
        return result

    async def _build_persistent_context_payload(
        self: Any,
        *,
        effective_config: dict[str, Any],
        bindings: list[tuple[KnowledgeBase, ChatSessionCapabilityBinding]],
        selected_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """组装知识库级与文档级补充上下文。"""

        session_enabled = bool(effective_config.get("enable_persistent_context", True))
        if not session_enabled:
            return {
                "kb_contexts": [],
                "doc_contexts": [],
                "debug": {
                    "session_enabled": False,
                    "kb_contexts": [],
                    "doc_contexts": [],
                },
            }

        kb_contexts: list[dict[str, Any]] = []
        kb_context_debug: list[dict[str, Any]] = []
        doc_contexts: list[dict[str, Any]] = []
        doc_context_debug: list[dict[str, Any]] = []

        selected_kb_doc_ids: list[UUID] = []
        for item in selected_items:
            metadata = dict(item.get("metadata") or {})
            kb_doc_id_raw = str(metadata.get("kb_doc_id") or "").strip()
            if not kb_doc_id_raw:
                continue
            try:
                selected_kb_doc_ids.append(UUID(kb_doc_id_raw))
            except ValueError:
                continue

        kb_doc_ids = list(dict.fromkeys(selected_kb_doc_ids))
        kb_doc_map: dict[UUID, KnowledgeBaseDocument] = {}
        if kb_doc_ids:
            stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.id.in_(kb_doc_ids))
            kb_docs = (await self.db.execute(stmt)).scalars().all()
            kb_doc_map = {item.id: item for item in kb_docs}

        for kb, _binding in bindings:
            persistent_context_cfg = dict((kb.retrieval_config or {}).get("persistent_context") or {})
            kb_context_enabled = bool(persistent_context_cfg.get("enabled"))
            kb_context_content = str(persistent_context_cfg.get("content") or "").strip()
            if kb_context_enabled and kb_context_content:
                kb_contexts.append(
                    {
                        "kb_id": str(kb.id),
                        "kb_name": kb.name,
                        "content": kb_context_content,
                    }
                )
            kb_context_debug.append(
                {
                    "kb_id": str(kb.id),
                    "kb_name": kb.name,
                    "enabled": kb_context_enabled,
                    "injected": bool(kb_context_enabled and kb_context_content),
                }
            )

            seen_doc_ids: set[str] = set()
            for item in selected_items:
                item_kb_id = str(item.get("kb_id") or "").strip()
                if item_kb_id != str(kb.id):
                    continue
                metadata = dict(item.get("metadata") or {})
                kb_doc_id_raw = str(metadata.get("kb_doc_id") or "").strip()
                if not kb_doc_id_raw or kb_doc_id_raw in seen_doc_ids:
                    continue
                seen_doc_ids.add(kb_doc_id_raw)
                try:
                    kb_doc_id = UUID(kb_doc_id_raw)
                except ValueError:
                    continue
                kb_doc = kb_doc_map.get(kb_doc_id)
                doc_context_cfg = dict(((kb_doc.intelligence_config if kb_doc else {}) or {}).get("persistent_context") or {})
                doc_context_enabled = bool(doc_context_cfg.get("enabled"))
                doc_context_content = str(doc_context_cfg.get("content") or "").strip()
                summary_fallback_enabled = bool(persistent_context_cfg.get("enable_doc_summary_as_context"))
                summary_text = str(kb_doc.summary or "").strip() if kb_doc else ""

                injected = False
                source_type = ""
                content = ""
                if doc_context_enabled and doc_context_content:
                    injected = True
                    source_type = "doc_persistent_context"
                    content = doc_context_content
                elif summary_fallback_enabled and summary_text:
                    injected = True
                    source_type = "kb_doc.summary"
                    content = summary_text

                doc_context_debug.append(
                    {
                        "kb_id": str(kb.id),
                        "kb_doc_id": kb_doc_id_raw,
                        "document_name": str(item.get("title") or "").strip(),
                        "doc_context_enabled": doc_context_enabled,
                        "summary_fallback_enabled": summary_fallback_enabled,
                        "source": source_type or None,
                        "injected": injected,
                    }
                )
                if not injected:
                    continue
                doc_contexts.append(
                    {
                        "kb_id": str(kb.id),
                        "kb_name": kb.name,
                        "kb_doc_id": kb_doc_id_raw,
                        "document_name": str(item.get("title") or "").strip(),
                        "content": content,
                        "source": source_type,
                    }
                )

        return {
            "kb_contexts": kb_contexts,
            "doc_contexts": doc_contexts,
            "debug": {
                "session_enabled": True,
                "kb_contexts": kb_context_debug,
                "doc_contexts": doc_context_debug,
            },
        }

    def _deduplicate_glossary_context(self: Any, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按知识库与术语去重术语上下文。"""

        result: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        for item in entries:
            kb_id = str(item.get("kb_id") or "")
            term = str(item.get("term") or "").strip().lower()
            if not term:
                continue
            key = (kb_id, term)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            result.append(item)
        return result

    def _tokenize_query_terms(self: Any, query: str) -> list[str]:
        """提取简单检索词。"""

        normalized = str(query or "").strip().lower()
        if not normalized:
            return []
        parts = [item for item in normalized.replace("\n", " ").split(" ") if item]
        return list(dict.fromkeys(parts))

    def _compute_term_overlap_bonus(self: Any, query_terms: list[str], text: str) -> float:
        """计算轻量词面重排加分。"""

        if not query_terms:
            return 0.0
        haystack = str(text or "").lower()
        hit_count = sum(1 for term in query_terms if term and term in haystack)
        return hit_count / max(1, len(query_terms))
