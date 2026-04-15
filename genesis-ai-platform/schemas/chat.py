"""
聊天模块 Schema 定义
"""
from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatCapabilityBindingBase(BaseModel):
    """聊天空间能力挂载基础定义"""

    capability_type: Literal[
        "knowledge_base",
        "tool",
        "search_provider",
        "mcp_server",
        "workflow",
        "skill",
    ] = Field(..., description="能力类型")
    capability_id: UUID = Field(..., description="能力对象ID")
    binding_role: Literal["default", "primary", "secondary", "optional"] = Field(
        default="default",
        description="绑定角色",
    )
    is_enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=100, description="优先级，越小越靠前")
    config: dict[str, Any] = Field(default_factory=dict, description="局部覆盖配置")


class ChatCapabilityBindingCreate(ChatCapabilityBindingBase):
    """创建能力挂载请求"""


class ChatCapabilityBindingUpdate(BaseModel):
    """更新能力挂载请求"""

    is_enabled: Optional[bool] = Field(default=None, description="是否启用")
    priority: Optional[int] = Field(default=None, description="优先级")
    config: Optional[dict[str, Any]] = Field(default=None, description="局部覆盖配置")


class ChatSpaceBase(BaseModel):
    """聊天空间基础字段"""

    name: str = Field(..., min_length=1, max_length=255, description="空间名称")
    description: Optional[str] = Field(default=None, description="空间描述")
    entrypoint_type: Literal["assistant", "workflow", "agent"] = Field(
        default="assistant",
        description="入口类型",
    )
    entrypoint_id: Optional[UUID] = Field(default=None, description="入口对象ID")
    default_config: dict[str, Any] = Field(default_factory=dict, description="空间默认配置")
    is_pinned: bool = Field(default=False, description="是否置顶")
    display_order: int = Field(default=100, description="展示排序")


class ChatSpaceCreate(ChatSpaceBase):
    """创建聊天空间请求"""


class ChatSpaceUpdate(BaseModel):
    """更新聊天空间请求"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="空间名称")
    description: Optional[str] = Field(default=None, description="空间描述")
    status: Optional[Literal["active", "archived", "deleted"]] = Field(
        default=None,
        description="空间状态",
    )
    entrypoint_type: Optional[Literal["assistant", "workflow", "agent"]] = Field(
        default=None,
        description="入口类型",
    )
    entrypoint_id: Optional[UUID] = Field(default=None, description="入口对象ID")
    default_config: Optional[dict[str, Any]] = Field(default=None, description="空间默认配置")
    is_pinned: Optional[bool] = Field(default=None, description="是否置顶")
    display_order: Optional[int] = Field(default=None, description="展示排序")


class ChatSpaceRead(ChatSpaceBase):
    """聊天空间读取模型"""

    id: UUID
    tenant_id: UUID
    owner_id: UUID
    status: str
    last_session_at: Optional[datetime] = None
    created_by_id: Optional[UUID] = None
    updated_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionStatsRead(BaseModel):
    """会话统计读取模型"""

    session_id: UUID
    tenant_id: UUID
    message_count: int
    turn_count: int
    user_message_count: int
    assistant_message_count: int
    tool_call_count: int
    workflow_run_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    last_model_id: Optional[UUID] = None
    last_turn_status: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionBase(BaseModel):
    """聊天会话基础字段"""

    title: Optional[str] = Field(default=None, max_length=255, description="会话标题")
    summary: Optional[str] = Field(default=None, description="会话摘要")
    title_source: Literal["manual", "auto", "fallback"] = Field(
        default="manual",
        description="标题来源",
    )
    channel: Literal["ui", "api", "system"] = Field(default="ui", description="来源渠道")
    visibility: Literal["user_visible", "backend_only"] = Field(
        default="user_visible",
        description="可见性",
    )
    persistence_mode: Literal["persistent", "ephemeral"] = Field(
        default="persistent",
        description="持久化模式",
    )
    config_override: dict[str, Any] = Field(default_factory=dict, description="会话级配置覆盖")
    is_pinned: bool = Field(default=False, description="是否置顶")
    display_order: int = Field(default=100, description="展示排序")


class ChatSessionCreate(ChatSessionBase):
    """创建会话请求"""


class ChatSessionUpdate(BaseModel):
    """更新会话请求"""

    title: Optional[str] = Field(default=None, max_length=255, description="会话标题")
    title_source: Optional[Literal["manual", "auto", "fallback"]] = Field(
        default=None,
        description="标题来源",
    )
    summary: Optional[str] = Field(default=None, description="会话摘要")
    status: Optional[Literal["active", "archived", "deleted"]] = Field(
        default=None,
        description="会话状态",
    )
    config_override: Optional[dict[str, Any]] = Field(default=None, description="会话级配置覆盖")
    is_pinned: Optional[bool] = Field(default=None, description="是否置顶")
    display_order: Optional[int] = Field(default=None, description="展示排序")


class ChatSessionRead(ChatSessionBase):
    """聊天会话读取模型"""

    id: UUID
    tenant_id: UUID
    chat_space_id: UUID
    owner_id: UUID
    status: str
    last_message_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_by_id: Optional[UUID] = None
    updated_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    stats: Optional[ChatSessionStatsRead] = None
    capabilities: list[dict[str, Any]] = Field(default_factory=list, description="会话能力挂载")

    model_config = ConfigDict(from_attributes=True)


class ChatMessageCitationRead(BaseModel):
    """消息引用读取模型"""

    id: UUID
    tenant_id: UUID
    session_id: UUID
    turn_id: Optional[UUID] = None
    message_id: UUID
    citation_index: int
    kb_id: Optional[UUID] = None
    kb_doc_id: Optional[UUID] = None
    chunk_id: Optional[int] = None
    source_anchor: Optional[str] = None
    page_number: Optional[int] = None
    snippet: Optional[str] = None
    score: Optional[float] = None
    metadata_info: dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChatMessageRead(BaseModel):
    """聊天消息读取模型"""

    id: UUID
    tenant_id: UUID
    session_id: UUID
    turn_id: Optional[UUID] = None
    parent_message_id: Optional[UUID] = None
    replaces_message_id: Optional[UUID] = None
    role: str
    message_type: str
    status: str
    source_channel: str
    content: Optional[str] = None
    content_blocks: list[dict[str, Any]] = Field(default_factory=list)
    display_content: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    is_visible: bool = True
    metadata_info: dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    citations: list[ChatMessageCitationRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChatMessageSendRequest(BaseModel):
    """发送消息请求"""

    content: str = Field(..., min_length=1, description="用户输入内容")
    source_channel: Literal["ui", "api", "system"] = Field(default="ui", description="来源渠道")
    content_blocks: list[dict[str, Any]] = Field(default_factory=list, description="富内容块")
    config_override: dict[str, Any] = Field(default_factory=dict, description="本轮临时配置覆盖")
    metadata_info: dict[str, Any] = Field(default_factory=dict, description="消息扩展元数据")


class ChatTurnRead(BaseModel):
    """聊天轮次读取模型"""

    id: UUID
    tenant_id: UUID
    session_id: UUID
    request_id: UUID
    execution_mode: str
    status: str
    user_message_id: Optional[UUID] = None
    assistant_message_id: Optional[UUID] = None
    effective_model_id: Optional[UUID] = None
    effective_retrieval_profile_id: Optional[UUID] = None
    effective_config: dict[str, Any] = Field(default_factory=dict)
    rewrite_query: Optional[str] = None
    final_query: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    debug_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSendResponse(BaseModel):
    """发送消息响应"""

    session: ChatSessionRead
    turn: ChatTurnRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead


class RetrievalProfileOption(BaseModel):
    """检索模板下拉选项"""

    id: UUID
    name: str
    description: Optional[str] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class WorkflowOption(BaseModel):
    """工作流下拉选项"""

    id: UUID
    name: str
    description: Optional[str] = None
    workflow_type: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class ChatSelectorOption(BaseModel):
    """通用下拉选项"""

    id: UUID
    name: str
    description: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatBootstrapResponse(BaseModel):
    """聊天页面初始化响应"""

    retrieval_profiles: list[RetrievalProfileOption] = Field(default_factory=list)
    workflows: list[WorkflowOption] = Field(default_factory=list)
    knowledge_bases: list[ChatSelectorOption] = Field(default_factory=list)
    models: list[ChatSelectorOption] = Field(default_factory=list)
    rerank_models: list[ChatSelectorOption] = Field(default_factory=list)


class ChatKnowledgeBasePickerRequest(BaseModel):
    """聊天挂载知识库选择器专用列表（排除已挂载项；与知识库列表页 /knowledge-bases/list 分离）"""

    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")
    search: Optional[str] = Field(default=None, description="名称或描述模糊搜索")
    exclude_ids: list[UUID] = Field(
        default_factory=list,
        description="已挂载到当前空间的知识库 ID，结果中排除",
    )
