"""
聊天执行轮次相关模型
"""
from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ChatTurn(Base):
    """
    聊天执行轮次

    一轮问答的一次真实执行快照。
    """

    __tablename__ = "chat_turns"

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )
    request_id: Mapped[UUID] = mapped_column(nullable=False, comment="请求链路ID")
    execution_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="执行模式"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, comment="执行状态")
    user_message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="用户消息ID",
    )
    assistant_message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="助手消息ID",
    )
    effective_model_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="实际执行模型ID")
    effective_retrieval_profile_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("retrieval_profiles.id", ondelete="SET NULL"),
        nullable=True,
        comment="实际检索模板ID",
    )
    effective_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="本轮真实生效配置快照"
    )
    rewrite_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="改写后的查询")
    final_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="最终执行查询")
    prompt_tokens: Mapped[Optional[int]] = mapped_column(nullable=True, comment="输入Token数")
    completion_tokens: Mapped[Optional[int]] = mapped_column(nullable=True, comment="输出Token数")
    total_tokens: Mapped[Optional[int]] = mapped_column(nullable=True, comment="总Token数")
    latency_ms: Mapped[Optional[int]] = mapped_column(nullable=True, comment="耗时（毫秒）")
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="错误码")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误信息")
    debug_summary: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="执行摘要"
    )

    __table_args__ = (
        CheckConstraint(
            "execution_mode IN ('retrieval_chat', 'workflow', 'agent')",
            name="ck_chat_turns_execution_mode",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_chat_turns_status",
        ),
        UniqueConstraint("tenant_id", "request_id", name="uq_chat_turns_tenant_request"),
    )


class ChatTurnRetrieval(Base):
    """
    检索明细
    """

    __tablename__ = "chat_turn_retrievals"

    # 检索明细表是追加型记录，数据库表结构只有 created_at，没有 updated_at。
    updated_at = None  # type: ignore[assignment]

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )
    turn_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属轮次ID",
    )
    retrieval_source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="检索来源类型"
    )
    retrieval_source_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="检索来源对象ID")
    kb_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="知识库ID")
    kb_doc_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="知识库文档挂载ID")
    chunk_id: Mapped[Optional[int]] = mapped_column(nullable=True, comment="分块ID")
    retrieval_stage: Mapped[str] = mapped_column(String(32), nullable=False, comment="检索阶段")
    raw_score: Mapped[Optional[float]] = mapped_column(nullable=True, comment="原始分值")
    rerank_score: Mapped[Optional[float]] = mapped_column(nullable=True, comment="重排分值")
    final_score: Mapped[Optional[float]] = mapped_column(nullable=True, comment="最终分值")
    rank_index: Mapped[Optional[int]] = mapped_column(nullable=True, comment="排名序号")
    selected_for_context: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否入选最终上下文"
    )
    selected_for_citation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否入选最终引用"
    )
    metadata_info: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, comment="扩展元数据"
    )

    __table_args__ = (
        CheckConstraint(
            "retrieval_source_type IN ('knowledge_base', 'web_search', 'graph', 'workflow_memory')",
            name="ck_chat_turn_retrievals_source_type",
        ),
        CheckConstraint(
            "retrieval_stage IN ('rewrite', 'recall', 'rerank', 'final_context')",
            name="ck_chat_turn_retrievals_stage",
        ),
    )


class ChatTurnToolCall(Base):
    """
    工具调用明细
    """

    __tablename__ = "chat_turn_tool_calls"

    # 工具调用明细表是追加型记录，数据库表结构只有 created_at，没有 updated_at。
    updated_at = None  # type: ignore[assignment]

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )
    turn_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属轮次ID",
    )
    message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联消息ID",
    )
    tool_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="工具类型")
    tool_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="工具对象ID")
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="工具名称")
    provider_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="提供方类型")
    provider_ref_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, comment="提供方对象ID")
    call_index: Mapped[int] = mapped_column(nullable=False, default=1, comment="调用序号")
    status: Mapped[str] = mapped_column(String(32), nullable=False, comment="调用状态")
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="输入参数")
    output_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="输出结果")
    error_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="错误码")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误信息")
    latency_ms: Mapped[Optional[int]] = mapped_column(nullable=True, comment="耗时（毫秒）")
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )

    __table_args__ = (
        CheckConstraint(
            "tool_type IN ('builtin', 'external_api', 'mcp_tool', 'workflow_tool', 'skill_tool')",
            name="ck_chat_turn_tool_calls_tool_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_chat_turn_tool_calls_status",
        ),
    )


class ChatTurnWorkflowRun(Base):
    """
    工作流运行明细
    """

    __tablename__ = "chat_turn_workflow_runs"

    # 工作流运行明细表是追加型记录，数据库表结构只有 created_at，没有 updated_at。
    updated_at = None  # type: ignore[assignment]

    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True, comment="所属租户ID")
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )
    turn_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属轮次ID",
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        comment="工作流ID",
    )
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False, comment="触发来源")
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="运行状态")
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="输入参数")
    output_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="输出结果")
    run_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="运行摘要")
    error_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="错误码")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误信息")
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )

    __table_args__ = (
        CheckConstraint(
            "trigger_source IN ('session_entrypoint', 'tool_call', 'agent_decision')",
            name="ck_chat_turn_workflow_runs_trigger_source",
        ),
        CheckConstraint(
            "run_status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_chat_turn_workflow_runs_status",
        ),
    )
