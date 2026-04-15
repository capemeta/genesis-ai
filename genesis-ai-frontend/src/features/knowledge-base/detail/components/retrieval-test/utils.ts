import { DEFAULT_RETRIEVAL_TEST_CONFIG, MOCK_RETRIEVAL_TEST_RESULTS } from './constants'
import type {
  RetrievalTestApiRequest,
  RetrievalTestConfig,
  RetrievalTestFormState,
  RetrievalTestRewriteContextItem,
  RetrievalTestRunState,
} from './types'

function isUuidLike(value?: string | null): boolean {
  const text = String(value || '').trim()
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(text)
}

function parseFilterExpressionText(value: string): Record<string, any> | null {
  const text = value.trim()
  if (!text) {
    return null
  }
  const parsed = JSON.parse(text)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('过滤表达式必须是 JSON 对象')
  }
  return parsed as Record<string, any>
}

function sanitizeRetrievalTestConfig(config: Required<RetrievalTestConfig>): Required<RetrievalTestConfig> {
  const nextConfig = { ...config }
  const autoFilterMode = String(nextConfig.auto_filter_mode || 'disabled')
  const enableLlmAutoFilter = autoFilterMode === 'llm_candidate' || autoFilterMode === 'hybrid'
  const enableHybridUpgrade = autoFilterMode === 'hybrid'

  if (!enableLlmAutoFilter) {
    delete (nextConfig as Record<string, any>).enable_llm_filter_expression
    delete (nextConfig as Record<string, any>).llm_candidate_min_confidence
    delete (nextConfig as Record<string, any>).llm_upgrade_confidence_threshold
    delete (nextConfig as Record<string, any>).llm_max_upgrade_count
  }
  else if (!enableHybridUpgrade) {
    delete (nextConfig as Record<string, any>).llm_upgrade_confidence_threshold
    delete (nextConfig as Record<string, any>).llm_max_upgrade_count
  }

  return nextConfig
}

export function buildFormStateFromConfig(config?: RetrievalTestConfig): RetrievalTestFormState {
  const savedRerankModel = String(config?.rerank_model || '').trim()
  const normalizedRerankModel = isUuidLike(savedRerankModel) ? savedRerankModel : ''
  return {
    vectorSimilarityThreshold:
      config?.vector_similarity_threshold ?? DEFAULT_RETRIEVAL_TEST_CONFIG.vector_similarity_threshold,
    keywordRelevanceThreshold:
      config?.keyword_relevance_threshold ?? DEFAULT_RETRIEVAL_TEST_CONFIG.keyword_relevance_threshold,
    finalScoreThreshold:
      config?.final_score_threshold ?? DEFAULT_RETRIEVAL_TEST_CONFIG.final_score_threshold,
    vectorWeight: config?.vector_weight ?? DEFAULT_RETRIEVAL_TEST_CONFIG.vector_weight,
    topK: config?.top_k ?? DEFAULT_RETRIEVAL_TEST_CONFIG.top_k,
    vectorTopK: config?.vector_top_k ?? DEFAULT_RETRIEVAL_TEST_CONFIG.vector_top_k,
    keywordTopK: config?.keyword_top_k ?? DEFAULT_RETRIEVAL_TEST_CONFIG.keyword_top_k,
    rerankTopN: config?.rerank_top_n ?? DEFAULT_RETRIEVAL_TEST_CONFIG.rerank_top_n,
    enableRerank: config?.enable_rerank ?? DEFAULT_RETRIEVAL_TEST_CONFIG.enable_rerank,
    rerankModel: normalizedRerankModel || DEFAULT_RETRIEVAL_TEST_CONFIG.rerank_model,
    useKnowledgeGraph: config?.use_knowledge_graph ?? DEFAULT_RETRIEVAL_TEST_CONFIG.use_knowledge_graph,
    enableQueryRewrite:
      config?.enable_query_rewrite ?? DEFAULT_RETRIEVAL_TEST_CONFIG.enable_query_rewrite,
    enableSynonymRewrite:
      config?.enable_synonym_rewrite ?? DEFAULT_RETRIEVAL_TEST_CONFIG.enable_synonym_rewrite,
    autoFilterMode: config?.auto_filter_mode ?? DEFAULT_RETRIEVAL_TEST_CONFIG.auto_filter_mode,
    enableLlmFilterExpression:
      config?.enable_llm_filter_expression ?? DEFAULT_RETRIEVAL_TEST_CONFIG.enable_llm_filter_expression,
    llmCandidateMinConfidence:
      config?.llm_candidate_min_confidence ?? DEFAULT_RETRIEVAL_TEST_CONFIG.llm_candidate_min_confidence,
    llmUpgradeConfidenceThreshold:
      config?.llm_upgrade_confidence_threshold ?? DEFAULT_RETRIEVAL_TEST_CONFIG.llm_upgrade_confidence_threshold,
    llmMaxUpgradeCount:
      config?.llm_max_upgrade_count ?? DEFAULT_RETRIEVAL_TEST_CONFIG.llm_max_upgrade_count,
    hierarchicalRetrievalMode:
      config?.hierarchical_retrieval_mode ?? DEFAULT_RETRIEVAL_TEST_CONFIG.hierarchical_retrieval_mode,
    neighborWindowSize: config?.neighbor_window_size ?? DEFAULT_RETRIEVAL_TEST_CONFIG.neighbor_window_size,
    groupByContentGroup:
      config?.group_by_content_group ?? DEFAULT_RETRIEVAL_TEST_CONFIG.group_by_content_group,
    filterExpressionText: '',
    queryRewriteContext: [],
    query: '',
  }
}

export function buildConfigFromFormState(state: RetrievalTestFormState): Required<RetrievalTestConfig> {
  return sanitizeRetrievalTestConfig({
    vector_similarity_threshold: Number(state.vectorSimilarityThreshold.toFixed(2)),
    keyword_relevance_threshold: Number(state.keywordRelevanceThreshold.toFixed(2)),
    final_score_threshold: Number(state.finalScoreThreshold.toFixed(2)),
    vector_weight: Number(state.vectorWeight.toFixed(2)),
    top_k: state.topK,
    vector_top_k: state.vectorTopK,
    keyword_top_k: state.keywordTopK,
    rerank_top_n: state.rerankTopN,
    enable_rerank: state.enableRerank,
    rerank_model: state.enableRerank ? state.rerankModel : '',
    metadata_filter: DEFAULT_RETRIEVAL_TEST_CONFIG.metadata_filter,
    use_knowledge_graph: state.useKnowledgeGraph,
    enable_query_rewrite: state.enableQueryRewrite,
    enable_synonym_rewrite: state.enableSynonymRewrite,
    auto_filter_mode: state.autoFilterMode,
    enable_llm_filter_expression: state.enableLlmFilterExpression,
    llm_candidate_min_confidence: Number(state.llmCandidateMinConfidence.toFixed(2)),
    llm_upgrade_confidence_threshold: Number(state.llmUpgradeConfidenceThreshold.toFixed(2)),
    llm_max_upgrade_count: Math.max(1, Math.round(state.llmMaxUpgradeCount)),
    hierarchical_retrieval_mode: state.hierarchicalRetrievalMode,
    neighbor_window_size: state.neighborWindowSize,
    group_by_content_group: state.groupByContentGroup,
    debug_trace_level: DEFAULT_RETRIEVAL_TEST_CONFIG.debug_trace_level,
    metadata_fields: [],
    extra_metadata_fields: [],
    override_metadata_fields: [],
    search_scopes: [],
    enable_parent_context: true,
  })
}

export function validateRetrievalTestFormState(state: RetrievalTestFormState): void {
  if (state.enableRerank && !state.rerankModel.trim()) {
    throw new Error('已开启重排序，请先选择一个 rerank 模型')
  }
  if (state.neighborWindowSize < 0 || state.neighborWindowSize > 5) {
    throw new Error('邻近块补充数量必须在 0 到 5 之间')
  }
  if (state.llmCandidateMinConfidence < 0 || state.llmCandidateMinConfidence > 1) {
    throw new Error('LLM 最小置信度必须在 0 到 1 之间')
  }
  if (state.llmUpgradeConfidenceThreshold < 0 || state.llmUpgradeConfidenceThreshold > 1) {
    throw new Error('硬过滤升级阈值必须在 0 到 1 之间')
  }
  if (state.llmMaxUpgradeCount < 1 || state.llmMaxUpgradeCount > 8) {
    throw new Error('最大升级数量必须在 1 到 8 之间')
  }
  try {
    parseFilterExpressionText(state.filterExpressionText)
  } catch (error) {
    const message = error instanceof Error ? error.message : '过滤表达式不是合法 JSON'
    throw new Error(`过滤表达式配置错误：${message}`)
  }
  const invalidContext = (state.queryRewriteContext || []).find(
    (item) => String(item.content || '').trim().length === 0
  )
  if (invalidContext) {
    throw new Error('多轮测试上下文中存在空内容，请补全或删除该条消息')
  }
}

export function buildRetrievalTestRequest(kbId: string, state: RetrievalTestFormState): RetrievalTestApiRequest {
  const filterExpression = parseFilterExpressionText(state.filterExpressionText)
  const filters = filterExpression ? { filter_expression: filterExpression } : undefined
  const queryRewriteContext = (state.queryRewriteContext || [])
    .map((item: RetrievalTestRewriteContextItem) => ({
      role: item.role,
      content: String(item.content || '').trim(),
    }))
    .filter((item) => item.content.length > 0)
  return {
    kb_id: kbId,
    query: state.query.trim(),
    config: buildConfigFromFormState(state),
    ...(queryRewriteContext.length > 0 ? { query_rewrite_context: queryRewriteContext } : {}),
    ...(filters ? { filters } : {}),
  }
}

export function buildMockRunState(state: RetrievalTestFormState): RetrievalTestRunState {
  const items = MOCK_RETRIEVAL_TEST_RESULTS.slice(0, state.topK).map((item, index) => ({
    ...item,
    rank: index + 1,
  }))

  return {
    items,
    elapsedMs: 124,
    executedQuery: state.query.trim(),
    mode: 'mock',
    queryAnalysis: null,
    debug: null,
  }
}

export function isSameConfig(
  left?: RetrievalTestConfig,
  right?: RetrievalTestConfig
): boolean {
  return JSON.stringify(left ?? DEFAULT_RETRIEVAL_TEST_CONFIG) === JSON.stringify(right ?? DEFAULT_RETRIEVAL_TEST_CONFIG)
}
