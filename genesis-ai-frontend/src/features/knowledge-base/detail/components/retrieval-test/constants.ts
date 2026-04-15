import type { RetrievalTestConfig, RetrievalTestFormState, RetrievalTestItem } from './types'

export const DEFAULT_RETRIEVAL_TEST_CONFIG: Required<RetrievalTestConfig> = {
  vector_similarity_threshold: 0.25,
  keyword_relevance_threshold: 0.2,
  final_score_threshold: 0.3,
  vector_weight: 0.55,
  top_k: 8,
  vector_top_k: 60,
  keyword_top_k: 40,
  rerank_top_n: 30,
  enable_rerank: true,
  rerank_model: '',
  metadata_filter: 'all',
  use_knowledge_graph: false,
  enable_query_rewrite: false,
  enable_synonym_rewrite: true,
  auto_filter_mode: 'disabled',
  enable_llm_filter_expression: true,
  llm_candidate_min_confidence: 0.55,
  llm_upgrade_confidence_threshold: 0.82,
  llm_max_upgrade_count: 2,
  hierarchical_retrieval_mode: 'recursive',
  neighbor_window_size: 0,
  debug_trace_level: 'detailed',
  metadata_fields: [],
  extra_metadata_fields: [],
  override_metadata_fields: [],
  search_scopes: [],
  enable_parent_context: true,
  group_by_content_group: true,
}

export const DEFAULT_RETRIEVAL_TEST_FORM: RetrievalTestFormState = {
  vectorSimilarityThreshold: DEFAULT_RETRIEVAL_TEST_CONFIG.vector_similarity_threshold,
  keywordRelevanceThreshold: DEFAULT_RETRIEVAL_TEST_CONFIG.keyword_relevance_threshold,
  finalScoreThreshold: DEFAULT_RETRIEVAL_TEST_CONFIG.final_score_threshold,
  vectorWeight: DEFAULT_RETRIEVAL_TEST_CONFIG.vector_weight,
  topK: DEFAULT_RETRIEVAL_TEST_CONFIG.top_k,
  vectorTopK: DEFAULT_RETRIEVAL_TEST_CONFIG.vector_top_k,
  keywordTopK: DEFAULT_RETRIEVAL_TEST_CONFIG.keyword_top_k,
  rerankTopN: DEFAULT_RETRIEVAL_TEST_CONFIG.rerank_top_n,
  enableRerank: DEFAULT_RETRIEVAL_TEST_CONFIG.enable_rerank,
  rerankModel: DEFAULT_RETRIEVAL_TEST_CONFIG.rerank_model,
  useKnowledgeGraph: DEFAULT_RETRIEVAL_TEST_CONFIG.use_knowledge_graph,
  enableQueryRewrite: DEFAULT_RETRIEVAL_TEST_CONFIG.enable_query_rewrite,
  enableSynonymRewrite: DEFAULT_RETRIEVAL_TEST_CONFIG.enable_synonym_rewrite,
  autoFilterMode: DEFAULT_RETRIEVAL_TEST_CONFIG.auto_filter_mode,
  enableLlmFilterExpression: DEFAULT_RETRIEVAL_TEST_CONFIG.enable_llm_filter_expression,
  llmCandidateMinConfidence: DEFAULT_RETRIEVAL_TEST_CONFIG.llm_candidate_min_confidence,
  llmUpgradeConfidenceThreshold: DEFAULT_RETRIEVAL_TEST_CONFIG.llm_upgrade_confidence_threshold,
  llmMaxUpgradeCount: DEFAULT_RETRIEVAL_TEST_CONFIG.llm_max_upgrade_count,
  hierarchicalRetrievalMode: DEFAULT_RETRIEVAL_TEST_CONFIG.hierarchical_retrieval_mode,
  neighborWindowSize: DEFAULT_RETRIEVAL_TEST_CONFIG.neighbor_window_size,
  groupByContentGroup: DEFAULT_RETRIEVAL_TEST_CONFIG.group_by_content_group,
  filterExpressionText: '',
  queryRewriteContext: [],
  query: '',
}

export const AUTO_FILTER_MODE_OPTIONS = [
  { value: 'disabled', label: '关闭自动过滤' },
  { value: 'rule', label: '规则型高置信抽取' },
  { value: 'llm_candidate', label: 'LLM 候选抽取' },
  { value: 'hybrid', label: '规则 + LLM 候选' },
]

export const HIERARCHICAL_RETRIEVAL_MODE_OPTIONS = [
  { value: 'leaf_only', label: '仅叶子块' },
  { value: 'recursive', label: '递归父上下文' },
  { value: 'auto_merge', label: '自动父块合并' },
]

export const MOCK_RETRIEVAL_TEST_RESULTS: RetrievalTestItem[] = [
  {
    id: 'mock-1',
    rank: 1,
    title: '赣州市政务OA平台操作指引.pdf',
    content:
      '赣州市“跨省通办”视频提示特色应用（政府端）操作指引 V1.2，本文档提供从启动到完成的完整操作步骤，用图解方式帮助新用户快速上手。',
    score: 0.92,
    keyword_score: 0.88,
    vector_score: 0.94,
    tags: ['政务', '手册'],
    source: {
      document_name: '赣州市政务OA平台操作指引.pdf',
      chunk_id: 'chunk-001',
      page_numbers: [2, 3],
    },
  },
  {
    id: 'mock-2',
    rank: 2,
    title: '系统集成管理规范_v3.docx',
    content:
      '接口对接与管理平台规范说明：所有对接赣州12345系统的第三方应用，必须遵循平台安全规范，核心交易数据需保留可追溯记录。',
    score: 0.81,
    keyword_score: 0.79,
    vector_score: 0.84,
    tags: ['规范'],
    source: {
      document_name: '系统集成管理规范_v3.docx',
      chunk_id: 'chunk-014',
      page_numbers: [6],
    },
  },
  {
    id: 'mock-3',
    rank: 3,
    title: '政务服务流程说明.md',
    content:
      '在政务服务事项流转中，需先完成受理登记，再进入材料校验和审批流转，最后同步归档到统一知识中心。',
    score: 0.77,
    keyword_score: 0.72,
    vector_score: 0.8,
    tags: ['流程', '知识中心'],
    source: {
      document_name: '政务服务流程说明.md',
      chunk_id: 'chunk-029',
      page_numbers: [],
    },
  },
]
