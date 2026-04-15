/**
 * 检索测试调试：全文词项与过滤轨迹解析（与后端 pipeline_trace / query_analysis 对齐）
 */

export interface LexicalTermsView {
  priorityTerms: string[]
  priorityPhrases: string[]
  ignoredTerms: string[]
}

export function getLexicalTermsFromQueryAnalysis(
  queryAnalysis: Record<string, any> | null | undefined
): LexicalTermsView {
  const qa = queryAnalysis || {}
  const asStrings = (v: unknown) =>
    Array.isArray(v) ? v.map((x) => String(x).trim()).filter(Boolean) : []
  return {
    priorityTerms: asStrings(qa.priority_lexical_terms),
    priorityPhrases: asStrings(qa.priority_lexical_phrases),
    ignoredTerms: asStrings(qa.ignored_lexical_terms),
  }
}

export interface FilterTraceParts {
  /** 用户/API 显式传入的过滤（pipeline.filters.explicit_filters） */
  explicit: Record<string, any>
  /** 查询分析阶段合并后的过滤结果（query_analysis.resolved_filters） */
  resolvedMerged: Record<string, any>
  /** 检索阶段最终生效的过滤结果（pipeline.filters.resolved_filters） */
  resolvedPipeline: Record<string, any>
  /** 人类可读的过滤摘要（pipeline.filters.debug_summary） */
  filterDebug: Record<string, any>
}

export function getFilterTraceParts(
  debug: Record<string, any> | null | undefined,
  queryAnalysis: Record<string, any> | null | undefined
): FilterTraceParts {
  const pipelineTrace = (debug?.pipeline_trace || {}) as Record<string, any>
  const pipelineFilters = (pipelineTrace.filters || {}) as Record<string, any>
  const fromPipeline = (pipelineFilters.debug_summary || {}) as Record<string, any>
  const fromRoot = (debug?.filter_debug_summary || {}) as Record<string, any>
  // 无结果提前返回时可能没有 pipeline_trace，但顶层仍有 filter_debug_summary
  const filterDebug = Object.keys(fromPipeline).length > 0 ? fromPipeline : fromRoot
  return {
    explicit: (pipelineFilters.explicit_filters || {}) as Record<string, any>,
    resolvedMerged: (queryAnalysis?.resolved_filters || {}) as Record<string, any>,
    resolvedPipeline: (pipelineFilters.resolved_filters || {}) as Record<string, any>,
    filterDebug,
  }
}

/** 将 ID 列表格式化为可读短文本（过长时截断） */
export function formatIdListLine(ids: unknown, maxShow = 14): string {
  const list = Array.isArray(ids) ? ids.map((x) => String(x).trim()).filter(Boolean) : []
  if (list.length === 0) {
    return '无'
  }
  const head = list.slice(0, maxShow)
  const extra = list.length > maxShow ? ` …共 ${list.length} 项` : ''
  return `${head.join('、')}${extra}`
}

/** 元数据对象单行展示 */
export function formatMetadataRecord(meta: unknown): string {
  if (meta == null || typeof meta !== 'object' || Array.isArray(meta)) {
    return '无'
  }
  const o = meta as Record<string, unknown>
  if (Object.keys(o).length === 0) {
    return '无'
  }
  try {
    return JSON.stringify(o)
  }
  catch {
    return String(meta)
  }
}

export function formatRequestedCounts(
  counts: Record<string, unknown> | undefined
): string {
  if (!counts || typeof counts !== 'object') {
    return '无'
  }
  const parts: string[] = []
  const map: Record<string, string> = {
    kb_doc_ids: '限定文档',
    folder_ids: '文件夹',
    folder_tag_ids: '文件夹标签',
    tag_ids: '文档标签',
    document_metadata_keys: '文档元数据键',
    search_unit_metadata_keys: '单元元数据键',
  }
  for (const [k, label] of Object.entries(map)) {
    const n = Number((counts as any)[k] ?? 0)
    if (Number.isFinite(n) && n > 0) {
      parts.push(`${label} ${n}`)
    }
  }
  return parts.length > 0 ? parts.join(' · ') : '无显式计数'
}

/**
 * 后端 debug.lexical_query_debug：PG FTS 查询构建时的词项拆分（见 rag/lexical/text_utils.build_pg_fts_query_payload）
 * 与 query_analysis.priority_lexical_* 不同，这里是实际用于 strict/loose 检索串的拆分结果。
 */
export interface LexicalFtsDebugView {
  normalizedQuery: string
  asciiTerms: string[]
  cjkTerms: string[]
  strictTerms: string[]
  looseTerms: string[]
  stopwordHits: string[]
  ignoredTerms: string[]
  stopwordCount: number
  hasPhrasePattern: boolean
  empty: boolean
}

export function getLexicalFtsDebugFromDebug(
  debug: Record<string, any> | null | undefined
): LexicalFtsDebugView {
  const raw = (debug?.lexical_query_debug || {}) as Record<string, any>
  const asStrings = (v: unknown) =>
    Array.isArray(v) ? v.map((x) => String(x).trim()).filter(Boolean) : []
  const normalizedQuery = String(raw.normalized_query || '').trim()
  const asciiTerms = asStrings(raw.ascii_terms)
  const cjkTerms = asStrings(raw.cjk_terms)
  const strictTerms = asStrings(raw.strict_terms)
  const looseTerms = asStrings(raw.loose_terms)
  const stopwordHits = asStrings(raw.stopword_hits)
  const ignoredTerms = asStrings(raw.ignored_terms)
  const stopwordCount = Number(raw.stopword_count || 0)
  const empty = !normalizedQuery && asciiTerms.length === 0 && cjkTerms.length === 0 && strictTerms.length === 0
  return {
    normalizedQuery,
    asciiTerms,
    cjkTerms,
    strictTerms,
    looseTerms,
    stopwordHits,
    ignoredTerms,
    stopwordCount: Number.isFinite(stopwordCount) ? stopwordCount : 0,
    hasPhrasePattern: Boolean(raw.has_phrase_pattern),
    empty,
  }
}

export function formatAppliedCounts(
  counts: Record<string, unknown> | undefined
): string {
  if (!counts || typeof counts !== 'object') {
    return '无'
  }
  const parts: string[] = []
  const map: Record<string, string> = {
    kb_doc_ids: 'kb 文档',
    document_ids: '业务文档',
    content_group_ids: '内容组',
  }
  for (const [k, label] of Object.entries(map)) {
    const n = Number((counts as any)[k] ?? 0)
    if (Number.isFinite(n) && n > 0) {
      parts.push(`${label} ${n}`)
    }
  }
  return parts.length > 0 ? parts.join(' · ') : '无落地计数'
}
