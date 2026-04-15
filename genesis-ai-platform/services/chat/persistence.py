"""聊天服务拆分模块：persistence。"""
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



class ChatPersistenceMixin:
    """按职责拆分的聊天服务能力。"""

    async def _load_citation_map(
        self: Any,
        message_ids: list[UUID],
    ) -> dict[UUID, list[ChatMessageCitation]]:
        """批量加载消息引用，避免逐条查询。"""
        if not message_ids:
            return {}
        stmt = (
            select(ChatMessageCitation)
            .where(ChatMessageCitation.message_id.in_(message_ids))
            .order_by(ChatMessageCitation.citation_index.asc(), ChatMessageCitation.created_at.asc())
        )
        citations = (await self.db.execute(stmt)).scalars().all()
        result: dict[UUID, list[ChatMessageCitation]] = {}
        for citation in citations:
            result.setdefault(citation.message_id, []).append(citation)
        return result

    async def _upsert_session_stats_for_send(
        self: Any,
        *,
        session_id: UUID,
        tenant_id: UUID,
        effective_model_id: Optional[UUID],
        turn_status: str,
        updated_at: datetime,
    ) -> None:
        """发送消息后更新会话统计缓存。"""
        stats = await self.db.get(ChatSessionStats, session_id)
        if not stats:
            stats = ChatSessionStats(
                session_id=session_id,
                tenant_id=tenant_id,
                updated_at=updated_at,
            )
            self.db.add(stats)

        stats.message_count += 2
        stats.turn_count += 1
        stats.user_message_count += 1
        stats.assistant_message_count += 1
        stats.last_model_id = effective_model_id
        stats.last_turn_status = turn_status
        stats.updated_at = updated_at

    async def _replace_turn_retrievals(
        self: Any,
        *,
        turn_id: UUID,
        rows: list[ChatTurnRetrieval],
    ) -> None:
        """重建本轮检索明细。"""

        await self.db.execute(delete(ChatTurnRetrieval).where(ChatTurnRetrieval.turn_id == turn_id))
        for row in rows:
            self.db.add(row)
        await self.db.flush()

    def _build_turn_retrieval_rows(
        self: Any,
        *,
        tenant_id: UUID,
        session_id: UUID,
        turn_id: UUID,
        items: list[dict[str, Any]],
    ) -> list[ChatTurnRetrieval]:
        """将最终检索结果写成 turn retrieval 明细。"""

        rows: list[ChatTurnRetrieval] = []
        for index, item in enumerate(items, start=1):
            source = dict(item.get("source") or {})
            metadata = dict(item.get("metadata") or {})
            chunk_id_raw = source.get("chunk_id")
            chunk_id = int(str(chunk_id_raw)) if str(chunk_id_raw or "").isdigit() else None
            rows.append(
                ChatTurnRetrieval(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    turn_id=turn_id,
                    retrieval_source_type="knowledge_base",
                    retrieval_source_id=UUID(str(item["kb_id"])) if item.get("kb_id") else None,
                    kb_id=UUID(str(item["kb_id"])) if item.get("kb_id") else None,
                    kb_doc_id=UUID(str(metadata["kb_doc_id"])) if metadata.get("kb_doc_id") else None,
                    chunk_id=chunk_id,
                    retrieval_stage="final_context",
                    raw_score=float(item.get("vector_score") or item.get("keyword_score") or item.get("score") or 0.0),
                    rerank_score=float(item.get("score") or 0.0),
                    final_score=float(item.get("score") or 0.0),
                    rank_index=index,
                    selected_for_context=True,
                    selected_for_citation=True,
                    metadata_info=metadata,
                )
            )
        return rows

    async def _replace_assistant_citations(
        self: Any,
        *,
        assistant_message: ChatMessage,
        turn: ChatTurn,
        retrieval_package: dict[str, Any],
    ) -> None:
        """根据最终上下文结果重建 assistant citations。"""

        await self.db.execute(delete(ChatMessageCitation).where(ChatMessageCitation.message_id == assistant_message.id))
        for index, item in enumerate(retrieval_package.get("items") or [], start=1):
            source = dict(item.get("source") or {})
            metadata = dict(item.get("metadata") or {})
            page_numbers = list(source.get("page_numbers") or [])
            chunk_id_raw = source.get("chunk_id")
            chunk_id = int(str(chunk_id_raw)) if str(chunk_id_raw or "").isdigit() else None
            citation = ChatMessageCitation(
                tenant_id=assistant_message.tenant_id,
                session_id=assistant_message.session_id,
                turn_id=turn.id,
                message_id=assistant_message.id,
                citation_index=index,
                kb_id=UUID(str(item["kb_id"])) if item.get("kb_id") else None,
                kb_doc_id=UUID(str(metadata["kb_doc_id"])) if metadata.get("kb_doc_id") else None,
                chunk_id=chunk_id,
                source_anchor=str(source.get("document_name") or ""),
                page_number=int(page_numbers[0]) if page_numbers else None,
                snippet=str(item.get("snippet") or ""),
                score=float(item.get("score") or 0.0),
                metadata_info=metadata,
            )
            self.db.add(citation)
        await self.db.flush()
