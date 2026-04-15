import type {
  RetrievalTestRequest,
  RetrievalTestResponse,
  RetrievalTestResultItem,
  RetrievalTestSettings,
} from '@/lib/api/knowledge-base'

export interface RetrievalTestRewriteContextItem {
  role: 'user' | 'assistant'
  content: string
}

export interface RetrievalTestFormState {
  vectorSimilarityThreshold: number
  keywordRelevanceThreshold: number
  finalScoreThreshold: number
  vectorWeight: number
  topK: number
  vectorTopK: number
  keywordTopK: number
  rerankTopN: number
  enableRerank: boolean
  rerankModel: string
  useKnowledgeGraph: boolean
  enableQueryRewrite: boolean
  enableSynonymRewrite: boolean
  autoFilterMode: 'disabled' | 'rule' | 'llm_candidate' | 'hybrid'
  enableLlmFilterExpression: boolean
  llmCandidateMinConfidence: number
  llmUpgradeConfidenceThreshold: number
  llmMaxUpgradeCount: number
  hierarchicalRetrievalMode: 'leaf_only' | 'recursive' | 'auto_merge'
  neighborWindowSize: number
  groupByContentGroup: boolean
  filterExpressionText: string
  queryRewriteContext: RetrievalTestRewriteContextItem[]
  query: string
}

export interface RetrievalTestRunState {
  items: RetrievalTestResultItem[]
  elapsedMs: number
  executedQuery: string
  mode: 'mock' | 'server'
  queryAnalysis?: Record<string, any> | null
  debug?: Record<string, any> | null
  executedAt?: string
  runId?: string
}

export interface RetrievalTestPageProps {
  kbId: string
}

export type RetrievalTestApiRequest = RetrievalTestRequest
export type RetrievalTestApiResponse = RetrievalTestResponse
export type RetrievalTestItem = RetrievalTestResultItem
export type RetrievalTestConfig = RetrievalTestSettings
