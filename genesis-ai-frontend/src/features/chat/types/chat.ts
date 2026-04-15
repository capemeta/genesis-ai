import type { PaginatedResponse } from '@/lib/api/types'

export type ChatSpaceStatus = 'active' | 'archived' | 'deleted'
export type ChatSessionStatus = 'active' | 'archived' | 'deleted'
export type ChatEntrypointType = 'assistant' | 'workflow' | 'agent'
export type ChatChannel = 'ui' | 'api' | 'system'
export type ChatVisibility = 'user_visible' | 'backend_only'
export type ChatPersistenceMode = 'persistent' | 'ephemeral'
export type ChatMessageRole = 'system' | 'user' | 'assistant' | 'tool'
export type ChatMessageStatus =
  | 'pending'
  | 'running'
  | 'streaming'
  | 'completed'
  | 'failed'
  | 'cancelled'
export type ChatCapabilityType =
  | 'knowledge_base'
  | 'tool'
  | 'search_provider'
  | 'mcp_server'
  | 'workflow'
  | 'skill'

export interface ChatSelectorOption {
  id: string
  name: string
  description?: string | null
  extra?: Record<string, any>
}

export interface ChatWorkflowOption {
  id: string
  name: string
  description?: string | null
  workflow_type: string
  status: string
}

export interface ChatRetrievalProfileOption {
  id: string
  name: string
  description?: string | null
  status: string
}

export interface ChatBootstrapData {
  retrieval_profiles: ChatRetrievalProfileOption[]
  workflows: ChatWorkflowOption[]
  knowledge_bases: ChatSelectorOption[]
  models: ChatSelectorOption[]
  rerank_models: ChatSelectorOption[]
}

export interface ChatSpace {
  id: string
  tenant_id: string
  owner_id: string
  name: string
  description?: string | null
  status: ChatSpaceStatus
  entrypoint_type: ChatEntrypointType
  entrypoint_id?: string | null
  default_config: Record<string, any>
  is_pinned: boolean
  display_order: number
  last_session_at?: string | null
  created_at: string
  updated_at: string
}

export interface ChatCapabilityBinding {
  id: string
  session_id: string
  capability_type: ChatCapabilityType
  capability_id: string
  binding_role: 'default' | 'primary' | 'secondary' | 'optional'
  is_enabled: boolean
  priority: number
  config: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface ChatSessionStats {
  session_id: string
  tenant_id: string
  message_count: number
  turn_count: number
  user_message_count: number
  assistant_message_count: number
  tool_call_count: number
  workflow_run_count: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  last_model_id?: string | null
  last_turn_status?: string | null
  updated_at: string
}

export interface ChatSession {
  id: string
  tenant_id: string
  chat_space_id: string
  owner_id: string
  title?: string | null
  summary?: string | null
  title_source: 'manual' | 'auto' | 'fallback'
  channel: ChatChannel
  visibility: ChatVisibility
  persistence_mode: ChatPersistenceMode
  config_override: Record<string, any>
  is_pinned: boolean
  display_order: number
  status: ChatSessionStatus
  last_message_at?: string | null
  closed_at?: string | null
  archived_at?: string | null
  deleted_at?: string | null
  created_at: string
  updated_at: string
  stats?: ChatSessionStats | null
  capabilities?: ChatCapabilityBinding[]
}

export interface ChatMessageCitation {
  id: string
  tenant_id: string
  session_id: string
  turn_id?: string | null
  message_id: string
  citation_index: number
  kb_id?: string | null
  kb_doc_id?: string | null
  chunk_id?: number | null
  source_anchor?: string | null
  page_number?: number | null
  snippet?: string | null
  score?: number | null
  metadata?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  tenant_id: string
  session_id: string
  turn_id?: string | null
  parent_message_id?: string | null
  replaces_message_id?: string | null
  role: ChatMessageRole
  message_type: string
  status: ChatMessageStatus
  source_channel: ChatChannel
  content?: string | null
  content_blocks: Array<Record<string, any>>
  display_content?: string | null
  error_code?: string | null
  error_message?: string | null
  is_visible: boolean
  metadata?: Record<string, any>
  user_id?: string | null
  created_at: string
  updated_at: string
  citations: ChatMessageCitation[]
}

export interface ChatTurn {
  id: string
  tenant_id: string
  session_id: string
  request_id: string
  execution_mode: string
  status: ChatMessageStatus
  user_message_id?: string | null
  assistant_message_id?: string | null
  effective_model_id?: string | null
  effective_retrieval_profile_id?: string | null
  effective_config: Record<string, any>
  rewrite_query?: string | null
  final_query?: string | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  total_tokens?: number | null
  latency_ms?: number | null
  started_at?: string | null
  completed_at?: string | null
  error_code?: string | null
  error_message?: string | null
  debug_summary: Record<string, any>
  created_at: string
  updated_at: string
}

export interface ChatSendMessageRequest {
  content: string
  source_channel?: ChatChannel
  content_blocks?: Array<Record<string, any>>
  config_override?: Record<string, any>
  metadata_info?: Record<string, any>
}

export interface ChatSendMessageResponse {
  session: ChatSession
  turn: ChatTurn
  user_message: ChatMessage
  assistant_message: ChatMessage
}

export interface ChatSpacePayload {
  name: string
  description?: string
  entrypoint_type?: ChatEntrypointType
  entrypoint_id?: string | null
  default_config?: Record<string, any>
  is_pinned?: boolean
  display_order?: number
}

export interface ChatSessionPayload {
  title?: string | null
  summary?: string | null
  title_source?: 'manual' | 'auto' | 'fallback'
  channel?: ChatChannel
  visibility?: ChatVisibility
  persistence_mode?: ChatPersistenceMode
  config_override?: Record<string, any>
  is_pinned?: boolean
  display_order?: number
}

export interface ChatConfigDraft {
  defaultModelId: string
  temperature: number
  topP: number
  presencePenalty: number
  frequencyPenalty: number
  maxTokens: number
  reasoningEffort: 'low' | 'medium' | 'high'
  searchDepthK: number
  rerankTopN: number
  minScore: number
  vectorWeight: number
  vectorSimilarityThreshold: number
  keywordRelevanceThreshold: number
  vectorTopK: number
  keywordTopK: number
  enableRerank: boolean
  rerankModelId: string
  reasoningMode: boolean
  persistentContextEnabled: boolean
  queryRewriteMode: 'inherit' | 'enabled' | 'disabled'
  synonymRewriteEnabled: boolean
  autoFilterMode: 'disabled' | 'rule' | 'llm_candidate' | 'hybrid'
  enableLlmFilterExpression: boolean
  llmCandidateMinConfidence: number
  llmUpgradeConfidenceThreshold: number
  llmMaxUpgradeCount: number
  hierarchicalRetrievalMode: 'leaf_only' | 'recursive' | 'auto_merge'
  neighborWindowSize: number
  enableParentContext: boolean
  groupByContentGroup: boolean
  filterInheritanceEnabled: boolean
  filterInheritanceEvaluationEnabled: boolean
  queryRewriteContext: Array<{
    role: 'user' | 'assistant'
    content: string
  }>
  selectedKnowledgeBaseIds: string[]
  knowledgeBaseScopes: Record<
    string,
    {
      kbDocIds: string[]
      folderIds: string[]
      folderTagIds: string[]
      includeDescendantFolders: boolean
      tagIds: string[]
      metadata: Record<string, string>
      filterExpressionText: string
    }
  >
}

export interface ChatCreateSpaceFormValues {
  name: string
  description: string
  entrypointType: ChatEntrypointType
  workflowId: string
}

export interface ChatSpacesQuery {
  page: number
  pageSize: number
  search?: string
  status?: Extract<ChatSpaceStatus, 'active' | 'archived'>
}

export interface ChatSessionsQuery {
  page?: number
  pageSize?: number
  status?: Extract<ChatSessionStatus, 'active' | 'archived'>
}

export type ChatSpaceListResponse = PaginatedResponse<ChatSpace>
export type ChatSessionListResponse = PaginatedResponse<ChatSession>

export interface ChatStreamTurnCreatedEvent {
  session: ChatSession
  turn: ChatTurn
  user_message: ChatMessage
  assistant_message: ChatMessage
}

export interface ChatStreamStatusEvent {
  message_id: string
  turn_id: string
  status: ChatMessageStatus
}

export interface ChatStreamDeltaEvent {
  message_id: string
  turn_id: string
  index: number
  delta: string
}

export interface ChatStreamCompletedEvent {
  session: ChatSession
  turn: ChatTurn
  assistant_message: ChatMessage
  usage?: Record<string, any>
}

export interface ChatStreamFailedEvent {
  turn_id: string
  message_id: string
  error: string
}

export type ChatStreamEventMap = {
  'turn.created': ChatStreamTurnCreatedEvent
  'assistant.status': ChatStreamStatusEvent
  'assistant.delta': ChatStreamDeltaEvent
  'assistant.completed': ChatStreamCompletedEvent
  'assistant.failed': ChatStreamFailedEvent
}

export type ChatStreamEventName = keyof ChatStreamEventMap

export interface ChatStreamEvent<T extends ChatStreamEventName = ChatStreamEventName> {
  event: T
  data: ChatStreamEventMap[T]
}
