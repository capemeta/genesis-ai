"""聊天服务拆分模块：filter_inheritance。"""
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
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
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



class ChatFilterInheritanceMixin:
    """按职责拆分的聊天服务能力。"""

    async def _resolve_filter_inheritance_package(
        self: Any,
        *,
        session_id: UUID,
        current_user: User,
        current_query: str,
        bindings: list[tuple[KnowledgeBase, ChatSessionCapabilityBinding]],
        effective_config: dict[str, Any],
        tenant_model_id: Optional[UUID],
    ) -> dict[str, Any]:
        """解析多轮对话中的过滤继承策略。"""

        if effective_config.get("enable_filter_inheritance", True) is False:
            return {
                "merged_filters_by_kb": {},
                "summary": {
                    "enabled": False,
                    "status": "disabled",
                },
                "debug": {
                    "enabled": False,
                    "status": "disabled",
                    "kb_decisions": {},
                },
            }

        previous_turn_context = await self._load_latest_completed_turn_filter_context(
            session_id=session_id,
            current_user=current_user,
        )
        if not previous_turn_context:
            return {
                "merged_filters_by_kb": {},
                "summary": {
                    "enabled": True,
                    "status": "no_previous_turn",
                },
                "debug": {
                    "enabled": True,
                    "status": "no_previous_turn",
                    "kb_decisions": {},
                },
            }

        previous_query = str(previous_turn_context.get("previous_query") or "").strip()
        previous_analysis_map = dict(previous_turn_context.get("previous_analysis_map") or {})
        candidate_kbs = []
        for kb, binding in bindings:
            kb_id_text = str(kb.id)
            previous_analysis = dict(previous_analysis_map.get(kb_id_text) or {})
            if not previous_analysis:
                continue
            previous_filter_summary = self._build_previous_filter_summary(previous_analysis)
            if not previous_filter_summary:
                continue
            candidate_kbs.append(
                {
                    "kb_id": kb_id_text,
                    "kb_name": kb.name,
                    "binding_filters": self._summarize_filter_payload(
                        self._extract_chat_retrieval_filters(binding.config)
                    ),
                    "previous_active_filters": previous_filter_summary,
                }
            )

        if not candidate_kbs:
            return {
                "merged_filters_by_kb": {},
                "summary": {
                    "enabled": True,
                    "status": "no_previous_filters",
                    "previous_query": previous_query,
                },
                "debug": {
                    "enabled": True,
                    "status": "no_previous_filters",
                    "previous_query": previous_query,
                    "kb_decisions": {},
                },
            }

        llm_result = await self._run_filter_inheritance_llm(
            current_user=current_user,
            tenant_model_id=tenant_model_id,
            previous_query=previous_query,
            current_query=current_query,
            candidate_kbs=candidate_kbs,
        )

        kb_decisions = dict(llm_result.get("decisions") or {})
        merged_filters_by_kb: dict[str, dict[str, Any]] = {}
        kb_debug: dict[str, dict[str, Any]] = {}
        applied_kb_count = 0

        for kb, binding in bindings:
            kb_id_text = str(kb.id)
            explicit_filters = self._extract_chat_retrieval_filters(binding.config)
            previous_analysis = dict(previous_analysis_map.get(kb_id_text) or {})
            previous_filters = dict(previous_analysis.get("resolved_filters") or {})
            decision = dict(kb_decisions.get(kb_id_text) or {})
            merged_filters = self._merge_filter_inheritance(
                explicit_filters=explicit_filters,
                previous_filters=previous_filters,
                decision=decision,
            )
            if merged_filters != explicit_filters:
                merged_filters_by_kb[kb_id_text] = merged_filters
                applied_kb_count += 1

            kb_debug[kb_id_text] = {
                "kb_id": kb_id_text,
                "kb_name": kb.name,
                "previous_query": previous_query,
                "action": str(decision.get("action") or "none"),
                "inherit_previous_filters": bool(decision.get("inherit_previous_filters", False)),
                "clear_targets": list(decision.get("clear_targets") or []),
                "reason": str(decision.get("reason") or "").strip() or None,
                "confidence": decision.get("confidence"),
                "applied": merged_filters != explicit_filters,
                "explicit_filters": self._summarize_filter_payload(explicit_filters),
                "previous_filters": self._summarize_filter_payload(previous_filters),
                "merged_filters": self._summarize_filter_payload(merged_filters),
            }

        return {
            "merged_filters_by_kb": merged_filters_by_kb,
            "summary": {
                "enabled": True,
                "status": str(llm_result.get("status") or "success"),
                "previous_query": previous_query,
                "applied_kb_count": applied_kb_count,
                "decision_count": len(kb_debug),
            },
            "debug": {
                "enabled": True,
                "status": str(llm_result.get("status") or "success"),
                "model": llm_result.get("model"),
                "previous_query": previous_query,
                "error": llm_result.get("error"),
                "kb_decisions": kb_debug,
            },
        }

    async def _load_latest_completed_turn_filter_context(
        self: Any,
        *,
        session_id: UUID,
        current_user: User,
    ) -> Optional[dict[str, Any]]:
        """加载最近一轮已完成对话中的过滤快照。"""

        stmt = (
            select(ChatTurn)
            .where(
                ChatTurn.tenant_id == current_user.tenant_id,
                ChatTurn.session_id == session_id,
                ChatTurn.status == "completed",
            )
            .order_by(ChatTurn.completed_at.desc(), ChatTurn.created_at.desc())
            .limit(1)
        )
        previous_turn = (await self.db.execute(stmt)).scalar_one_or_none()
        if previous_turn is None:
            return None

        previous_user_message = await self.db.get(ChatMessage, previous_turn.user_message_id) if previous_turn.user_message_id else None
        retrieval_context = dict((previous_turn.debug_summary or {}).get("retrieval_context") or {})
        query_analysis_items = list(retrieval_context.get("query_analysis") or [])
        analysis_map: dict[str, dict[str, Any]] = {}
        for item in query_analysis_items:
            if not isinstance(item, dict):
                continue
            kb_id_text = str(item.get("kb_id") or "").strip()
            if not kb_id_text:
                continue
            analysis_map[kb_id_text] = item

        return {
            "previous_query": str((previous_user_message.content if previous_user_message else None) or "").strip(),
            "previous_turn_id": str(previous_turn.id),
            "previous_analysis_map": analysis_map,
        }

    async def _run_filter_inheritance_llm(
        self: Any,
        *,
        current_user: User,
        tenant_model_id: Optional[UUID],
        previous_query: str,
        current_query: str,
        candidate_kbs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """调用 LLM 判断多轮过滤继承关系。"""

        messages = [
            {
                "role": "system",
                "content": (
                    "你是多轮检索范围继承决策器。"
                    "你的任务是判断当前问题是否要延续上一轮检索过滤范围。"
                    "只输出 JSON，禁止输出解释性文本。"
                    "输出格式为 "
                    "{\"decisions\": [{\"kb_id\": \"知识库ID\", \"action\": \"inherit|refine|relax|replace|clear|none\", "
                    "\"inherit_previous_filters\": true, "
                    "\"clear_targets\": [\"folder_ids\", \"tag_ids\", \"folder_tag_ids\", \"kb_doc_ids\", \"metadata\", \"metadata.region\", \"search_unit_metadata\", \"search_unit_metadata.filter_fields.region\", \"filter_expression\"], "
                    "\"confidence\": 0到1, \"reason\": \"简短原因\"}]}"
                    "。"
                    "规则："
                    "1. 只有在用户明显表达“还是、继续、沿用、刚才那批、同范围”等语义时，才倾向 inherit/refine。"
                    "2. 如果用户表达“换成、改成、不要限定、别按、取消限制”，应通过 replace/clear/relax 清理旧范围。"
                    "3. 当用户明显切换新主题且没有延续语义时，优先输出 none。"
                    "4. 不要编造新的过滤值，本阶段只判断上一轮范围是否继承以及清理哪些范围。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "previous_query": previous_query,
                        "current_query": current_query,
                        "knowledge_bases": candidate_kbs,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        invocation_service = ModelInvocationService(self.db)
        try:
            result = await invocation_service.chat(
                current_user=current_user,
                tenant_model_id=tenant_model_id,
                capability_type="chat",
                messages=messages,
                temperature=0,
                max_tokens=600,
                stream=False,
                extra_body=None,
                request_source="chat_filter_inheritance",
            )
            content = self._extract_assistant_content(result)
            parsed = self._parse_filter_inheritance_response(content)
            return {
                "status": "success",
                "model": result.get("model"),
                "decisions": self._normalize_filter_inheritance_decisions(parsed.get("decisions")),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "decisions": {},
            }

    def _parse_filter_inheritance_response(self: Any, content: str) -> dict[str, Any]:
        """解析过滤继承 LLM 输出。"""

        normalized = str(content or "").strip()
        if not normalized:
            raise ValueError("过滤继承分析未返回内容")
        if normalized.startswith("```"):
            normalized = re.sub(r"^```(?:json)?\s*|\s*```$", "", normalized, flags=re.IGNORECASE | re.DOTALL).strip()
        parsed = json.loads(normalized)
        if not isinstance(parsed, dict):
            raise ValueError("过滤继承分析输出不是 JSON 对象")
        return parsed

    def _normalize_filter_inheritance_decisions(
        self: Any,
        raw_items: Any,
    ) -> dict[str, dict[str, Any]]:
        """规范化过滤继承决策输出。"""

        allowed_actions = {"inherit", "refine", "relax", "replace", "clear", "none"}
        result: dict[str, dict[str, Any]] = {}
        if not isinstance(raw_items, list):
            return result

        for item in raw_items[:20]:
            if not isinstance(item, dict):
                continue
            kb_id = str(item.get("kb_id") or "").strip()
            action = str(item.get("action") or "none").strip().lower()
            if not kb_id or action not in allowed_actions:
                continue
            clear_targets = [
                str(target).strip()
                for target in list(item.get("clear_targets") or [])
                if str(target).strip()
            ]
            try:
                confidence = round(float(item.get("confidence") or 0), 4)
            except (TypeError, ValueError):
                confidence = 0.0
            result[kb_id] = {
                "action": action,
                "inherit_previous_filters": bool(item.get("inherit_previous_filters", action in {"inherit", "refine", "relax"})),
                "clear_targets": clear_targets,
                "reason": str(item.get("reason") or "").strip() or None,
                "confidence": max(0.0, min(1.0, confidence)),
            }
        return result

    def _build_previous_filter_summary(
        self: Any,
        previous_analysis: dict[str, Any],
    ) -> list[str]:
        """把上一轮已生效过滤整理成更适合 LLM 判断的摘要。"""

        result: list[str] = []
        filter_candidates = list(previous_analysis.get("filter_candidates") or [])
        for item in filter_candidates:
            if not isinstance(item, dict):
                continue
            if not bool(item.get("applied") or item.get("upgraded_to_hard_filter")):
                continue
            filter_type = str(item.get("filter_type") or "").strip()
            filter_value = str(item.get("filter_value") or "").strip()
            target_id = str(item.get("target_id") or "").strip()
            if filter_type and filter_value:
                result.append(f"{filter_type}: {filter_value}")
            elif filter_type and target_id:
                result.append(f"{filter_type}: {target_id}")

        if result:
            return list(dict.fromkeys(result))

        return self._summarize_filter_payload(dict(previous_analysis.get("resolved_filters") or {}))

    def _build_filter_inheritance_effect_evaluation(
        self: Any,
        *,
        kb: KnowledgeBase,
        inherited_result: dict[str, Any],
        baseline_result: dict[str, Any],
    ) -> dict[str, Any]:
        """构建多轮过滤继承的影子基线评估结果。"""

        inherited_summary = self._summarize_retrieval_result(inherited_result)
        baseline_summary = self._summarize_retrieval_result(baseline_result)
        inherited_documents = set(inherited_summary["matched_document_names"])
        baseline_documents = set(baseline_summary["matched_document_names"])
        inherited_hit = int(inherited_summary["hit_count"])
        baseline_hit = int(baseline_summary["hit_count"])
        inherited_score = float(inherited_summary["avg_score"])
        baseline_score = float(baseline_summary["avg_score"])
        inherited_doc_count = len(inherited_documents)
        baseline_doc_count = len(baseline_documents)

        if inherited_hit > baseline_hit or inherited_score > baseline_score or inherited_doc_count > baseline_doc_count:
            verdict = "positive"
        elif inherited_hit < baseline_hit or inherited_score < baseline_score or inherited_doc_count < baseline_doc_count:
            verdict = "negative"
        else:
            verdict = "neutral"

        scope_delta: dict[str, int] = {}
        inherited_scopes = dict(inherited_summary.get("matched_scope_distribution") or {})
        baseline_scopes = dict(baseline_summary.get("matched_scope_distribution") or {})
        for scope in sorted(set(inherited_scopes) | set(baseline_scopes)):
            scope_delta[scope] = int(inherited_scopes.get(scope, 0)) - int(baseline_scopes.get(scope, 0))

        return {
            "kb_id": str(kb.id),
            "kb_name": kb.name,
            "enabled": True,
            "verdict": verdict,
            "baseline_label": "不延续上一轮范围",
            "experiment_label": "延续上一轮范围",
            "baseline": baseline_summary,
            "experiment": inherited_summary,
            "delta": {
                "hit_count": inherited_hit - baseline_hit,
                "avg_score": round(inherited_score - baseline_score, 4),
                "document_count": inherited_doc_count - baseline_doc_count,
                "elapsed_ms": int(inherited_summary["elapsed_ms"]) - int(baseline_summary["elapsed_ms"]),
                "added_documents": sorted(inherited_documents - baseline_documents),
                "removed_documents": sorted(baseline_documents - inherited_documents),
                "scope_distribution": scope_delta,
            },
        }

    def _summarize_retrieval_result(self: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """压缩检索结果为便于调试对比的摘要。"""

        items = list(payload.get("items") or [])
        matched_document_names = sorted(
            {
                str((item.get("source") or {}).get("document_name") or "").strip()
                for item in items
                if str((item.get("source") or {}).get("document_name") or "").strip()
            }
        )
        matched_scope_distribution: dict[str, int] = {}
        for item in items:
            metadata = dict(item.get("metadata") or {})
            for scope in list(metadata.get("matched_scopes") or []):
                scope_key = str(scope or "").strip()
                if not scope_key:
                    continue
                matched_scope_distribution[scope_key] = matched_scope_distribution.get(scope_key, 0) + 1

        avg_score = 0.0
        if items:
            avg_score = sum(float(item.get("score") or 0.0) for item in items) / len(items)
        return {
            "hit_count": len(items),
            "avg_score": round(avg_score, 4),
            "elapsed_ms": int(payload.get("elapsed_ms") or 0),
            "matched_document_names": matched_document_names,
            "matched_scope_distribution": matched_scope_distribution,
        }

    def _attach_filter_inheritance_effect_evaluation(
        self: Any,
        *,
        package: dict[str, Any],
        evaluations: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """把影子基线评估结果附着到过滤继承调试包。"""

        next_package = dict(package or {})
        summary = dict(next_package.get("summary") or {})
        debug = dict(next_package.get("debug") or {})

        if not evaluations:
            summary["effect_evaluation"] = {"enabled": False}
            debug["effect_evaluation"] = {"enabled": False}
            next_package["summary"] = summary
            next_package["debug"] = debug
            return next_package

        positive_count = 0
        neutral_count = 0
        negative_count = 0
        total_hit_delta = 0.0
        total_score_delta = 0.0

        for evaluation in evaluations.values():
            verdict = str(evaluation.get("verdict") or "neutral")
            delta = dict(evaluation.get("delta") or {})
            total_hit_delta += float(delta.get("hit_count") or 0.0)
            total_score_delta += float(delta.get("avg_score") or 0.0)
            if verdict == "positive":
                positive_count += 1
            elif verdict == "negative":
                negative_count += 1
            else:
                neutral_count += 1

        evaluated_kb_count = len(evaluations)
        aggregate_summary = {
            "enabled": True,
            "evaluated_kb_count": evaluated_kb_count,
            "positive_kb_count": positive_count,
            "neutral_kb_count": neutral_count,
            "negative_kb_count": negative_count,
            "avg_hit_delta": round(total_hit_delta / evaluated_kb_count, 4) if evaluated_kb_count else 0.0,
            "avg_score_delta": round(total_score_delta / evaluated_kb_count, 4) if evaluated_kb_count else 0.0,
        }
        summary["effect_evaluation"] = aggregate_summary
        debug["effect_evaluation"] = {
            **aggregate_summary,
            "kb_results": evaluations,
        }
        next_package["summary"] = summary
        next_package["debug"] = debug
        return next_package

    def _summarize_filter_payload(
        self: Any,
        raw_filters: dict[str, Any],
    ) -> list[str]:
        """将过滤字典摘要为可读条目。"""

        filters = dict(raw_filters or {})
        items: list[str] = []
        for key in ("kb_doc_ids", "folder_ids", "folder_tag_ids", "tag_ids"):
            values = list(filters.get(key) or [])
            if values:
                items.append(f"{key}: {len(values)} 项")

        metadata = dict(filters.get("document_metadata") or filters.get("metadata") or {})
        for key, value in metadata.items():
            items.append(f"metadata.{key}: {value}")

        search_unit_metadata = dict(filters.get("search_unit_metadata") or {})
        items.extend(self._flatten_search_unit_metadata_summary(search_unit_metadata))
        if isinstance(filters.get("filter_expression"), dict) and filters.get("filter_expression"):
            items.append("filter_expression: 已设置")
        return items

    def _flatten_search_unit_metadata_summary(
        self: Any,
        search_unit_metadata: dict[str, Any],
        *,
        path_prefix: str = "search_unit_metadata",
    ) -> list[str]:
        """展开结构化过滤摘要。"""

        items: list[str] = []
        for key, value in search_unit_metadata.items():
            current_path = f"{path_prefix}.{key}"
            if isinstance(value, dict):
                items.extend(self._flatten_search_unit_metadata_summary(value, path_prefix=current_path))
            else:
                items.append(f"{current_path}: {value}")
        return items

    def _merge_filter_inheritance(
        self: Any,
        *,
        explicit_filters: dict[str, Any],
        previous_filters: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """按“显式优先、继承可控”的规则合并上一轮过滤。"""

        base_filters = self._clone_filter_payload(explicit_filters)
        if not bool(decision.get("inherit_previous_filters")):
            return base_filters

        inherited_filters = self._clone_filter_payload(previous_filters)
        for target in list(decision.get("clear_targets") or []):
            self._remove_filter_target(inherited_filters, str(target))
        return self._merge_filter_payloads(base_filters=base_filters, inherited_filters=inherited_filters)

    def _clone_filter_payload(self: Any, raw_filters: dict[str, Any]) -> dict[str, Any]:
        """深拷贝过滤字典，避免修改原对象。"""

        return json.loads(json.dumps(dict(raw_filters or {}), ensure_ascii=False, default=str))

    def _merge_filter_payloads(
        self: Any,
        *,
        base_filters: dict[str, Any],
        inherited_filters: dict[str, Any],
    ) -> dict[str, Any]:
        """将继承过滤并入显式过滤，显式过滤优先。"""

        merged = self._clone_filter_payload(base_filters)
        for key in ("kb_doc_ids", "folder_ids", "folder_tag_ids", "tag_ids"):
            explicit_values = list(merged.get(key) or [])
            inherited_values = list(inherited_filters.get(key) or [])
            if explicit_values:
                merged[key] = list(dict.fromkeys(explicit_values))
                continue
            if inherited_values:
                merged[key] = list(dict.fromkeys(inherited_values))

        if "include_descendant_folders" not in merged and "include_descendant_folders" in inherited_filters:
            merged["include_descendant_folders"] = inherited_filters.get("include_descendant_folders")

        explicit_metadata = dict(merged.get("metadata") or merged.get("document_metadata") or {})
        inherited_metadata = dict(inherited_filters.get("metadata") or inherited_filters.get("document_metadata") or {})
        if inherited_metadata:
            merged["metadata"] = {**inherited_metadata, **explicit_metadata}
        elif explicit_metadata:
            merged["metadata"] = explicit_metadata

        explicit_search_unit_metadata = dict(merged.get("search_unit_metadata") or {})
        inherited_search_unit_metadata = dict(inherited_filters.get("search_unit_metadata") or {})
        if inherited_search_unit_metadata:
            merged["search_unit_metadata"] = self._deep_merge_nested_filters(
                base_value=inherited_search_unit_metadata,
                override_value=explicit_search_unit_metadata,
            )
        elif explicit_search_unit_metadata:
            merged["search_unit_metadata"] = explicit_search_unit_metadata

        explicit_expression = dict(merged.get("filter_expression") or {})
        inherited_expression = dict(inherited_filters.get("filter_expression") or {})
        if explicit_expression:
            merged["filter_expression"] = explicit_expression
        elif inherited_expression:
            merged["filter_expression"] = inherited_expression
        return merged

    def _deep_merge_nested_filters(
        self: Any,
        *,
        base_value: dict[str, Any],
        override_value: dict[str, Any],
    ) -> dict[str, Any]:
        """递归合并结构化过滤，override 优先。"""

        result = self._clone_filter_payload(base_value)
        for key, value in dict(override_value or {}).items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge_nested_filters(
                    base_value=dict(result.get(key) or {}),
                    override_value=value,
                )
            else:
                result[key] = value
        return result

    def _remove_filter_target(self: Any, inherited_filters: dict[str, Any], target: str) -> None:
        """从继承过滤中移除指定目标。"""

        normalized = str(target or "").strip()
        if not normalized:
            return
        if normalized in {"kb_doc_ids", "folder_ids", "folder_tag_ids", "tag_ids"}:
            inherited_filters.pop(normalized, None)
            return
        if normalized == "metadata":
            inherited_filters.pop("metadata", None)
            inherited_filters.pop("document_metadata", None)
            return
        if normalized.startswith("metadata."):
            metadata_key = normalized.split(".", 1)[1].strip()
            for metadata_root in ("metadata", "document_metadata"):
                metadata = inherited_filters.get(metadata_root)
                if isinstance(metadata, dict):
                    metadata.pop(metadata_key, None)
            return
        if normalized == "search_unit_metadata":
            inherited_filters.pop("search_unit_metadata", None)
            return
        if normalized == "filter_expression":
            inherited_filters.pop("filter_expression", None)
            return
        if normalized.startswith("search_unit_metadata."):
            path = [item for item in normalized.split(".")[1:] if item]
            search_unit_metadata = inherited_filters.get("search_unit_metadata")
            if isinstance(search_unit_metadata, dict):
                self._remove_nested_path(search_unit_metadata, path)

    def _remove_nested_path(self: Any, current: dict[str, Any], path: list[str]) -> None:
        """移除嵌套字典上的指定路径。"""

        if not path or not isinstance(current, dict):
            return
        if len(path) == 1:
            current.pop(path[0], None)
            return
        child = current.get(path[0])
        if not isinstance(child, dict):
            return
        self._remove_nested_path(child, path[1:])
