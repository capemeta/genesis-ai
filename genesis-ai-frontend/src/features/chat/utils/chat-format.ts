import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import type {
  ChatConfigDraft,
  ChatCapabilityBinding,
  ChatMessage,
  ChatSession,
  ChatSpace,
} from '@/features/chat/types/chat'

export function formatRelativeTime(date?: string | null): string {
  if (!date) {
    return '刚刚'
  }

  try {
    return formatDistanceToNow(new Date(date), {
      addSuffix: true,
      locale: zhCN,
    })
  } catch {
    return '刚刚'
  }
}

export function getSpaceSubtitle(space: ChatSpace): string {
  const entrypointLabelMap = {
    assistant: '自由对话',
    workflow: '按流程办理',
    agent: '智能助手',
  } as const

  return `${entrypointLabelMap[space.entrypoint_type]} · ${space.status === 'archived' ? '已归档' : '可继续聊'}`
}

export function getSessionDisplayTitle(session: ChatSession, index?: number): string {
  return session.title?.trim() || `会话 ${typeof index === 'number' ? index + 1 : ''}`.trim()
}

export function getMessageText(message: ChatMessage): string {
  return message.display_content || message.content || ''
}

export function buildAutoSessionTitle(content: string): string {
  const normalized = content
    .replace(/\s+/g, ' ')
    .replace(/[。！？!?,，；;：:]+$/g, '')
    .trim()

  if (!normalized) {
    return '未命名会话'
  }

  return normalized.length > 24 ? `${normalized.slice(0, 24).trim()}...` : normalized
}

export function isFallbackSessionTitle(title?: string | null): boolean {
  const normalized = title?.trim()

  if (!normalized) {
    return true
  }

  return /^新会话\s*\d+$/.test(normalized) || /-\s*会话\s*\d+$/.test(normalized)
}

export function buildConfigDraft(
  _space?: ChatSpace | null,
  session?: ChatSession | null,
  selectedKnowledgeBaseIds: string[] = []
): ChatConfigDraft {
  const sessionConfig = session?.config_override || {}
  const queryRewriteMode =
    typeof sessionConfig.enable_query_rewrite === 'boolean'
      ? sessionConfig.enable_query_rewrite
        ? 'enabled'
        : 'disabled'
      : 'inherit'
  const capabilityBindings = Array.isArray(session?.capabilities) ? session.capabilities : []
  const knowledgeBaseScopes = capabilityBindings
    .filter((binding) => binding.capability_type === 'knowledge_base')
    .reduce<ChatConfigDraft['knowledgeBaseScopes']>((acc, binding) => {
      acc[binding.capability_id] = normalizeKnowledgeBaseScopeDraft(binding)
      return acc
    }, {})

  return {
    defaultModelId:
      typeof sessionConfig.default_model_id === 'string' ? sessionConfig.default_model_id : '',
    temperature:
      typeof sessionConfig.temperature === 'number' ? Number(sessionConfig.temperature) : 0.7,
    topP:
      typeof sessionConfig.top_p === 'number' ? Number(sessionConfig.top_p) : 1,
    presencePenalty:
      typeof sessionConfig.presence_penalty === 'number' ? Number(sessionConfig.presence_penalty) : 0,
    frequencyPenalty:
      typeof sessionConfig.frequency_penalty === 'number' ? Number(sessionConfig.frequency_penalty) : 0,
    maxTokens:
      typeof sessionConfig.max_tokens === 'number' ? Number(sessionConfig.max_tokens) : 2048,
    reasoningEffort:
      sessionConfig.reasoning_effort === 'low' || sessionConfig.reasoning_effort === 'high'
        ? sessionConfig.reasoning_effort
        : 'medium',
    searchDepthK:
      typeof sessionConfig.search_depth_k === 'number' ? Number(sessionConfig.search_depth_k) : 5,
    rerankTopN:
      typeof sessionConfig.rerank_top_n === 'number' ? Number(sessionConfig.rerank_top_n) : 3,
    minScore:
      typeof sessionConfig.min_score === 'number' ? Number(sessionConfig.min_score) : 0.3,
    vectorWeight:
      typeof sessionConfig.vector_weight === 'number' ? Number(sessionConfig.vector_weight) : 0.55,
    vectorSimilarityThreshold:
      typeof sessionConfig.vector_similarity_threshold === 'number'
        ? Number(sessionConfig.vector_similarity_threshold)
        : 0.25,
    keywordRelevanceThreshold:
      typeof sessionConfig.keyword_relevance_threshold === 'number'
        ? Number(sessionConfig.keyword_relevance_threshold)
        : 0.2,
    vectorTopK:
      typeof sessionConfig.vector_top_k === 'number'
        ? Number(sessionConfig.vector_top_k)
        : 60,
    keywordTopK:
      typeof sessionConfig.keyword_top_k === 'number'
        ? Number(sessionConfig.keyword_top_k)
        : 40,
    enableRerank: Boolean(sessionConfig.enable_rerank),
    rerankModelId:
      typeof sessionConfig.rerank_model === 'string' ? sessionConfig.rerank_model : '',
    reasoningMode: Boolean(sessionConfig.reasoning_mode),
    persistentContextEnabled: sessionConfig.enable_persistent_context !== false,
    queryRewriteMode,
    synonymRewriteEnabled: sessionConfig.enable_synonym_rewrite !== false,
    autoFilterMode:
      sessionConfig.auto_filter_mode === 'rule' ||
      sessionConfig.auto_filter_mode === 'llm_candidate' ||
      sessionConfig.auto_filter_mode === 'hybrid'
        ? sessionConfig.auto_filter_mode
        : 'disabled',
    enableLlmFilterExpression: sessionConfig.enable_llm_filter_expression !== false,
    llmCandidateMinConfidence:
      typeof sessionConfig.llm_candidate_min_confidence === 'number'
        ? Number(sessionConfig.llm_candidate_min_confidence)
        : 0.55,
    llmUpgradeConfidenceThreshold:
      typeof sessionConfig.llm_upgrade_confidence_threshold === 'number'
        ? Number(sessionConfig.llm_upgrade_confidence_threshold)
        : 0.82,
    llmMaxUpgradeCount:
      typeof sessionConfig.llm_max_upgrade_count === 'number'
        ? Number(sessionConfig.llm_max_upgrade_count)
        : 2,
    hierarchicalRetrievalMode:
      sessionConfig.hierarchical_retrieval_mode === 'leaf_only' ||
      sessionConfig.hierarchical_retrieval_mode === 'auto_merge'
        ? sessionConfig.hierarchical_retrieval_mode
        : 'recursive',
    neighborWindowSize:
      typeof sessionConfig.neighbor_window_size === 'number'
        ? Number(sessionConfig.neighbor_window_size)
        : 0,
    enableParentContext: sessionConfig.enable_parent_context !== false,
    groupByContentGroup: sessionConfig.group_by_content_group !== false,
    filterInheritanceEnabled: sessionConfig.enable_filter_inheritance !== false,
    filterInheritanceEvaluationEnabled: Boolean(sessionConfig.enable_filter_inheritance_evaluation),
    queryRewriteContext: Array.isArray(sessionConfig.query_rewrite_context)
      ? sessionConfig.query_rewrite_context
        .map((item) => ({
          role: (item?.role === 'assistant' ? 'assistant' : 'user') as 'user' | 'assistant',
          content: String(item?.content || '').trim(),
        }))
        .filter((item) => item.content.length > 0)
      : [],
    selectedKnowledgeBaseIds,
    knowledgeBaseScopes,
  }
}

/**
 * 规范化知识库绑定上的过滤草稿，避免前端直接处理原始 JSON。
 */
export function normalizeKnowledgeBaseScopeDraft(
  binding?: Pick<ChatCapabilityBinding, 'config'>
): ChatConfigDraft['knowledgeBaseScopes'][string] {
  const filters = ((binding?.config || {}).filters || {}) as Record<string, any>
  const metadata = filters.metadata as Record<string, any>
  const filterExpression = filters.filter_expression && typeof filters.filter_expression === 'object'
    ? JSON.stringify(filters.filter_expression, null, 2)
    : ''

  return {
    folderIds: Array.isArray(filters.folder_ids)
      ? filters.folder_ids.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    kbDocIds: Array.isArray(filters.kb_doc_ids)
      ? filters.kb_doc_ids.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    folderTagIds: Array.isArray(filters.folder_tag_ids)
      ? filters.folder_tag_ids.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    includeDescendantFolders: filters.include_descendant_folders !== false,
    tagIds: Array.isArray(filters.tag_ids)
      ? filters.tag_ids.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    metadata:
      metadata && typeof metadata === 'object'
        ? Object.fromEntries(
            Object.entries(metadata)
              .filter(([key]) => typeof key === 'string' && key.trim().length > 0)
              .map(([key, value]) => [key, value == null ? '' : String(value)])
          )
        : {},
    filterExpressionText: filterExpression,
  }
}

export function mergeMessages(
  persistedMessages: ChatMessage[],
  incomingMessages: ChatMessage[]
): ChatMessage[] {
  const messageMap = new Map<string, ChatMessage>()

  for (const message of persistedMessages) {
    messageMap.set(message.id, message)
  }

  for (const message of incomingMessages) {
    messageMap.set(message.id, message)
  }

  return sortChatMessages(Array.from(messageMap.values()))
}

/**
 * 统一聊天消息排序规则：
 * 1. 优先按创建时间正序
 * 2. 时间相同再按更新时间兜底
 * 3. 同一轮固定 user 在 assistant 前
 * 4. 最后使用角色顺序与 ID 保证稳定排序
 */
export function sortChatMessages(messages: ChatMessage[]): ChatMessage[] {
  const roleOrder: Record<string, number> = {
    system: 0,
    user: 1,
    assistant: 2,
    tool: 3,
  }

  return [...messages].sort((left, right) => {
    const leftTime = new Date(left.created_at).getTime()
    const rightTime = new Date(right.created_at).getTime()
    const timeDelta = leftTime - rightTime
    if (timeDelta !== 0) {
      return timeDelta
    }

    // 同一轮消息必须固定 user 在 assistant 前，避免数据库时间精度或前端缓存合并导致展示顺序抖动。
    if (left.turn_id && left.turn_id === right.turn_id && left.role !== right.role) {
      return (roleOrder[left.role] ?? 99) - (roleOrder[right.role] ?? 99)
    }

    const leftGroupKey = left.turn_id || left.id
    const rightGroupKey = right.turn_id || right.id
    const groupDelta = leftGroupKey.localeCompare(rightGroupKey)
    if (groupDelta !== 0) {
      return groupDelta
    }

    const leftUpdatedTime = new Date(left.updated_at).getTime()
    const rightUpdatedTime = new Date(right.updated_at).getTime()
    const updatedTimeDelta = leftUpdatedTime - rightUpdatedTime
    if (updatedTimeDelta !== 0) {
      return updatedTimeDelta
    }

    const roleDelta = (roleOrder[left.role] ?? 99) - (roleOrder[right.role] ?? 99)
    if (roleDelta !== 0) {
      return roleDelta
    }

    return left.id.localeCompare(right.id)
  })
}
