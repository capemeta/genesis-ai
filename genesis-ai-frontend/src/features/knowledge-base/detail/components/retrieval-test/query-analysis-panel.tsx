import { useState } from 'react'
import { ChevronRight, Copy } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { RetrievalTestRunState } from './types'
import {
  formatAppliedCounts,
  formatIdListLine,
  formatMetadataRecord,
  formatRequestedCounts,
  getFilterTraceParts,
  getLexicalFtsDebugFromDebug,
  getLexicalTermsFromQueryAnalysis,
} from './retrieval-query-debug-utils'

interface QueryAnalysisPanelProps {
  result: RetrievalTestRunState
  currentResult?: RetrievalTestRunState | null
  compareResult?: RetrievalTestRunState | null
  historyResults?: RetrievalTestRunState[]
  selectedViewRunId?: string | null
  onSelectViewRun?: (runId: string | null) => void
  mode?: 'full' | 'summary'
  onOpenGlobalDebug?: () => void
}

type QueryAnalysisTab = 'overview' | 'compare' | 'diagnosis'

function formatDelta(value: number, digits = 0) {
  const normalizedValue = Object.is(value, -0) ? 0 : value
  if (!Number.isFinite(normalizedValue) || Math.abs(normalizedValue) < 10 ** -(digits + 1)) {
    return `0${digits > 0 ? normalizedValue.toFixed(digits).slice(1) : ''}`
  }
  return `${normalizedValue > 0 ? '+' : ''}${normalizedValue.toFixed(digits)}`
}

function formatOptionalDelta(value: number, digits = 0) {
  const normalizedValue = Object.is(value, -0) ? 0 : value
  if (!Number.isFinite(normalizedValue) || Math.abs(normalizedValue) < 10 ** -(digits + 1)) {
    return null
  }
  return `${normalizedValue > 0 ? '+' : ''}${normalizedValue.toFixed(digits)}`
}

function buildScopeDistribution(items: RetrievalTestRunState['items']) {
  const distribution: Record<string, number> = {}
  items.forEach((item) => {
    const scopes = Array.isArray(item.metadata?.matched_scopes) ? item.metadata.matched_scopes : []
    scopes.forEach((scope) => {
      const key = String(scope || '').trim()
      if (!key) {
        return
      }
      distribution[key] = (distribution[key] || 0) + 1
    })
  })
  return distribution
}

function buildDocumentSet(items: RetrievalTestRunState['items']) {
  return new Set(items.map((item) => String(item.source?.document_name || '').trim()).filter(Boolean))
}

function formatRunTimeLabel(run?: RetrievalTestRunState | null) {
  if (!run) {
    return '未执行'
  }
  if (!run.executedAt) {
    return run.mode === 'mock' ? '模拟数据' : '刚刚执行'
  }
  const date = new Date(run.executedAt)
  if (Number.isNaN(date.getTime())) {
    return run.executedAt
  }
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function formatCandidateFilterType(type?: string): string {
  const normalized = String(type || '').trim()
  if (normalized === 'folder_id') {
    return '文件夹'
  }
  if (normalized === 'tag_id') {
    return '文档标签'
  }
  if (normalized === 'folder_tag_id') {
    return '文件夹标签'
  }
  if (normalized === 'kb_doc_id') {
    return 'kb 文档'
  }
  if (normalized === 'document_metadata') {
    return '文档元数据'
  }
  if (normalized === 'search_unit_metadata') {
    return '分块元数据'
  }
  return normalized || '未标注'
}

function formatCandidateEvidenceType(type?: string): string {
  const normalized = String(type || '').trim()
  if (normalized === 'explicit_query_match') {
    return '原问题直命中'
  }
  if (normalized === 'alias_match') {
    return '别名命中'
  }
  if (normalized === 'rewrite_query_match') {
    return '改写命中'
  }
  if (normalized === 'rule_supported') {
    return '规则候选支撑'
  }
  if (normalized === 'candidate_inference') {
    return '候选池推断'
  }
  return normalized || '无证据'
}

function formatCandidatePreview(item: Record<string, any>) {
  const label = formatCandidateFilterType(item?.filter_type)
  const value = String(item?.display_name || item?.filter_value || item?.target_id || '').trim()
  const evidence = formatCandidateEvidenceType(item?.evidence_type)
  const evidenceText = String(item?.evidence_text || '').trim()
  const validation = String(item?.validation_status || '').trim()
  const parts = [`${label}${value ? `: ${value}` : ''}`]
  if (evidence) {
    parts.push(`证据 ${evidence}`)
  }
  if (evidenceText) {
    parts.push(`命中 ${evidenceText}`)
  }
  if (validation) {
    parts.push(`校验 ${validation}`)
  }
  return parts.join(' · ')
}

function filterCandidatesByType(candidates: unknown, filterType: string) {
  const source = Array.isArray(candidates) ? candidates : []
  return source.filter((item) => String((item as Record<string, any>)?.filter_type || '').trim() === filterType) as Array<Record<string, any>>
}

function formatFolderCandidatePreview(candidate: Record<string, any>) {
  const name = String(candidate?.display_name || candidate?.filter_value || candidate?.target_id || '').trim() || '未标注目录'
  const path = String(candidate?.display_path || '').trim()
  const source = String(candidate?.source || '').trim()
  const matchedTerms = Array.isArray(candidate?.matched_terms)
    ? candidate.matched_terms.map((item: unknown) => String(item).trim()).filter(Boolean)
    : []
  const sourceLabel = source === 'folder_path'
    ? '路径命中'
    : source === 'folder_name'
      ? '名称命中'
      : source === 'llm'
        ? 'LLM 判断'
        : ''
  const suffix = matchedTerms.length > 0 ? ` · 命中词 ${matchedTerms.join('、')}` : ''
  return `${name}${path ? ` · ${path}` : ''}${sourceLabel ? ` · ${sourceLabel}` : ''}${suffix}`
}

export function QueryAnalysisPanel({
  result,
  currentResult,
  compareResult,
  historyResults = [],
  selectedViewRunId,
  onSelectViewRun,
  mode = 'full',
  onOpenGlobalDebug,
}: QueryAnalysisPanelProps) {
  const [activeTab, setActiveTab] = useState<QueryAnalysisTab>('overview')
  const queryAnalysis = (result.queryAnalysis || {}) as Record<string, any>
  const debug = (result.debug || {}) as Record<string, any>
  const rawQuestion = String(queryAnalysis.raw_query || result.executedQuery || '').trim() || '无'
  const standaloneQuestion = String(queryAnalysis.standalone_query || queryAnalysis.raw_query || '').trim() || rawQuestion
  const normalizedRetrievalQuestion = String(
    queryAnalysis.rewritten_query || queryAnalysis.standalone_query || queryAnalysis.raw_query || ''
  ).trim() || standaloneQuestion
  const lexicalQueryText = String(queryAnalysis.lexical_query || queryAnalysis.rewritten_query || '').trim() || '无'
  const glossaryEntries = Array.isArray(queryAnalysis.glossary_entries) ? queryAnalysis.glossary_entries : []
  const retrievalLexiconMatches = Array.isArray(queryAnalysis.retrieval_lexicon_matches) ? queryAnalysis.retrieval_lexicon_matches : []
  const synonymMatches = Array.isArray(queryAnalysis.synonym_matches) ? queryAnalysis.synonym_matches : []
  const queryRewriteDebug = (queryAnalysis.query_rewrite_debug || {}) as Record<string, any>
  const candidateFilters = Array.isArray(queryAnalysis.filter_candidates) ? queryAnalysis.filter_candidates : []
  const candidateBreakdown = (queryAnalysis.candidate_breakdown || {}) as Record<string, any>
  const ruleCandidates = Array.isArray(candidateBreakdown.rule_candidates) ? candidateBreakdown.rule_candidates : []
  const llmCandidates = Array.isArray(candidateBreakdown.llm_candidates) ? candidateBreakdown.llm_candidates : []
  const correctedRuleCandidates = Array.isArray(candidateBreakdown.corrected_rule_candidates) ? candidateBreakdown.corrected_rule_candidates : []
  const folderRuleCandidates = filterCandidatesByType(ruleCandidates, 'folder_id')
  const folderLlmCandidates = filterCandidatesByType(llmCandidates, 'folder_id')
  const correctedFolderCandidates = filterCandidatesByType(correctedRuleCandidates, 'folder_id')
  const autoFilterSignals = Array.isArray(queryAnalysis.auto_filter_signals) ? queryAnalysis.auto_filter_signals : []
  const retrievalFilters = (queryAnalysis.resolved_filters || {}) as Record<string, any>
  const filterDebugSummary = (debug.filter_debug_summary || {}) as Record<string, any>
  const resultDebugSummary = (debug.result_debug_summary || {}) as Record<string, any>
  const pipelineTrace = (debug.pipeline_trace || {}) as Record<string, any>
  const traceInput = (pipelineTrace.input || {}) as Record<string, any>
  const traceRetrieval = (pipelineTrace.retrieval || {}) as Record<string, any>
  const lexicalTerms = getLexicalTermsFromQueryAnalysis(queryAnalysis)
  const lexicalFts = getLexicalFtsDebugFromDebug(debug)
  const filterParts = getFilterTraceParts(debug, queryAnalysis)
  const explicitFilters = filterParts.explicit
  const filterPipelineDebug = filterParts.filterDebug
  const traceResults = (pipelineTrace.results || {}) as Record<string, any>
  const currentDocSet = buildDocumentSet(result.items)
  const previousDocSet = buildDocumentSet(compareResult?.items || [])
  const addedDocuments = Array.from(currentDocSet).filter((name) => !previousDocSet.has(name))
  const removedDocuments = Array.from(previousDocSet).filter((name) => !currentDocSet.has(name))
  const currentHitCount = result.items.length
  const previousHitCount = compareResult?.items.length ?? 0
  const currentAvgScore = currentHitCount > 0
    ? result.items.reduce((sum, item) => sum + item.score, 0) / currentHitCount
    : 0
  const previousAvgScore = previousHitCount > 0
    ? (compareResult?.items || []).reduce((sum, item) => sum + item.score, 0) / previousHitCount
    : 0
  const hitDelta = currentHitCount - previousHitCount
  const scoreDelta = currentAvgScore - previousAvgScore
  const elapsedDelta = compareResult ? result.elapsedMs - compareResult.elapsedMs : 0

  const matchedScopeDistribution = resultDebugSummary.matched_scope_distribution && typeof resultDebugSummary.matched_scope_distribution === 'object'
    ? resultDebugSummary.matched_scope_distribution as Record<string, number>
    : buildScopeDistribution(result.items)
  const previousScopeDistribution = compareResult ? buildScopeDistribution(compareResult.items) : {}
  const scopeDeltaItems = Array.from(new Set([...Object.keys(matchedScopeDistribution), ...Object.keys(previousScopeDistribution)]))
    .sort()
    .map((scope) => {
      const currentCount = matchedScopeDistribution[scope] || 0
      const previousCount = previousScopeDistribution[scope] || 0
      return `${scope}: ${currentCount} (${formatDelta(currentCount - previousCount)})`
    })

  const hasLexicalSummary
    = lexicalTerms.priorityTerms.length > 0
      || lexicalTerms.priorityPhrases.length > 0
      || lexicalTerms.ignoredTerms.length > 0
      || !lexicalFts.empty
  const hasFilterSummary
    = formatIdListLine(explicitFilters.folder_ids) !== '无'
      || formatIdListLine(explicitFilters.tag_ids) !== '无'
      || formatIdListLine(explicitFilters.folder_tag_ids) !== '无'
      || formatIdListLine(explicitFilters.kb_doc_ids) !== '无'
      || formatIdListLine(explicitFilters.document_ids) !== '无'
      || formatMetadataRecord(explicitFilters.document_metadata) !== '无'
      || formatMetadataRecord(explicitFilters.search_unit_metadata) !== '无'
      || formatMetadataRecord(explicitFilters.filter_expression) !== '无'
      || formatIdListLine(retrievalFilters.folder_ids) !== '无'
      || formatIdListLine(retrievalFilters.tag_ids) !== '无'
      || formatMetadataRecord(retrievalFilters.filter_expression) !== '无'
  const hasContent
    = Boolean(queryAnalysis.raw_query)
      || Boolean(queryAnalysis.rewritten_query)
      || synonymMatches.length > 0
      || glossaryEntries.length > 0
      || candidateFilters.length > 0
      || autoFilterSignals.length > 0
      || Object.keys(debug).length > 0
      || hasLexicalSummary
      || hasFilterSummary

  if (!hasContent) {
    return null
  }

  const selectedHistoryIndex = selectedViewRunId ? historyResults.findIndex((item) => item.runId === selectedViewRunId) : -1
  const viewingLabel = selectedHistoryIndex >= 0 ? `历史第 ${selectedHistoryIndex + 1} 轮` : '当前轮次（最新）'
  const viewLabel = selectedViewRunId ? '历史轮次' : '当前轮次'
  const trendLabel = !compareResult
    ? '无基线'
    : (hitDelta > 0 || scoreDelta > 0) ? '表现提升' : (hitDelta < 0 || scoreDelta < 0) ? '表现下降' : '基本持平'
  const trendClassName = !compareResult
    ? 'border-slate-200 bg-slate-100 text-slate-700'
    : (hitDelta > 0 || scoreDelta > 0)
        ? 'border-emerald-200 bg-emerald-100 text-emerald-700'
        : (hitDelta < 0 || scoreDelta < 0)
            ? 'border-amber-200 bg-amber-100 text-amber-700'
            : 'border-slate-200 bg-slate-100 text-slate-700'

  if (mode === 'summary') {
    return (
      <details className='group rounded-2xl border border-blue-200/70 bg-blue-50/40 p-4 shadow-sm open:shadow-md'>
        <summary className='cursor-pointer list-none'>
          <div className='flex items-center justify-between gap-2'>
            <div className='inline-flex items-center gap-1.5 text-sm font-semibold text-blue-800'>
              <ChevronRight className='h-4 w-4 transition-transform duration-200 group-open:rotate-90' />
              <span>查询分析摘要（全局）</span>
            </div>
            <Button
              type='button'
              variant='default'
              size='sm'
              className='h-7 border border-blue-600 bg-blue-600 px-2 text-[11px] text-white shadow-sm hover:bg-blue-700'
              onClick={(event) => {
                // 避免点击按钮时触发 details 折叠切换。
                event.preventDefault()
                event.stopPropagation()
                onOpenGlobalDebug?.()
              }}
              title='查看查询级诊断（改写、过滤、召回、全局结果）'
            >
              全局诊断（查询级）
            </Button>
          </div>
        </summary>
        <div className='mt-3 space-y-3 text-sm'>
          <div className='rounded-xl border border-blue-200/70 bg-white/90 p-3'>
            <div className='flex flex-wrap items-center justify-between gap-2'>
              <div className='flex min-w-0 items-center gap-2'>
                <Badge variant='outline' className='border-blue-200 bg-blue-50 text-blue-700'>{viewLabel}</Badge>
                <span className='truncate text-sm text-foreground/80'>{result.executedQuery || '未记录问题'}</span>
              </div>
              <Badge variant='outline' className={trendClassName}>{trendLabel}</Badge>
            </div>
            <div className='mt-3 grid gap-2 sm:grid-cols-3'>
              <MetricPill title='结果条数' value={`${currentHitCount}`} delta={compareResult ? formatOptionalDelta(hitDelta) : null} />
              <MetricPill title='平均分' value={currentAvgScore.toFixed(2)} delta={compareResult ? formatOptionalDelta(scoreDelta, 2) : null} />
              <MetricPill title='耗时' value={`${result.elapsedMs}ms`} delta={compareResult ? (() => {
                const delta = formatOptionalDelta(elapsedDelta)
                return delta ? `${delta}ms` : null
              })() : null} />
            </div>
          </div>

          <div className='rounded-xl border border-indigo-200 bg-indigo-50/70 px-4 py-3'>
            <div className='text-xs font-semibold uppercase tracking-wider text-indigo-700'>当前查看轮次</div>
            <div className='mt-1 text-sm text-indigo-900'>{viewingLabel} · {formatRunTimeLabel(result)}</div>
          </div>

          <HistoryCard
            title='历史对比轮次'
            currentResult={result}
            latestResult={currentResult}
            historyResults={historyResults}
            selectedViewRunId={selectedViewRunId}
            onSelectViewRun={onSelectViewRun}
          />

          <div className='rounded-xl border border-dashed border-blue-200 bg-white/80 px-3 py-2 text-xs text-muted-foreground'>
            完整链路、对比与 JSON 详情已收敛到全局诊断侧边栏。
          </div>
        </div>
      </details>
    )
  }

  return (
    <details className='rounded-2xl border border-blue-200/70 bg-blue-50/40 p-5 shadow-sm open:shadow-md' open>
      <summary className='cursor-pointer list-none text-sm font-semibold text-blue-800'>查询分析结果</summary>
      <div className='mt-4 space-y-4 text-sm'>
        <div className='rounded-xl border border-blue-200/70 bg-white/85 p-4'>
          <div className='flex flex-wrap items-center justify-between gap-2'>
            <div className='flex min-w-0 items-center gap-2'>
              <Badge variant='outline' className='border-blue-200 bg-blue-50 text-blue-700'>{viewLabel}</Badge>
              <span className='truncate text-sm text-foreground/80'>{result.executedQuery || '未记录问题'}</span>
            </div>
            <Badge variant='outline' className={trendClassName}>{trendLabel}</Badge>
          </div>
          <div className='mt-3 grid gap-2 sm:grid-cols-3'>
            <MetricPill title='结果条数' value={`${currentHitCount}`} delta={compareResult ? formatOptionalDelta(hitDelta) : null} />
            <MetricPill title='平均分' value={currentAvgScore.toFixed(2)} delta={compareResult ? formatOptionalDelta(scoreDelta, 2) : null} />
            <MetricPill title='耗时' value={`${result.elapsedMs}ms`} delta={compareResult ? (() => {
              const delta = formatOptionalDelta(elapsedDelta)
              return delta ? `${delta}ms` : null
            })() : null} />
          </div>
        </div>

        <div className='rounded-xl border border-indigo-200 bg-indigo-50/70 px-4 py-3'>
          <div className='text-xs font-semibold uppercase tracking-wider text-indigo-700'>当前查看轮次</div>
          <div className='mt-1 text-sm text-indigo-900'>{viewingLabel} · {formatRunTimeLabel(result)}</div>
        </div>

        <QueryAnalysisTabs activeTab={activeTab} onChange={setActiveTab} />

        {activeTab === 'overview' ? (
          <div className='grid gap-3 md:grid-cols-2'>
            <HistoryCard
              title='历史对比轮次'
              currentResult={result}
              latestResult={currentResult}
              historyResults={historyResults}
              selectedViewRunId={selectedViewRunId}
              onSelectViewRun={onSelectViewRun}
            />
            <InfoCard title='原始问题' value={rawQuestion} />
            <ListCard
              title='查询改写状态'
              items={[
                `是否改写: ${queryAnalysis.standalone_query && queryAnalysis.standalone_query !== queryAnalysis.raw_query ? '是' : '否'}`,
                `状态: ${String(queryRewriteDebug.status || (queryAnalysis.standalone_query && queryAnalysis.standalone_query !== queryAnalysis.raw_query ? 'success' : 'disabled'))}`,
                queryRewriteDebug.rewrite_reason ? `原因: ${String(queryRewriteDebug.rewrite_reason)}` : '',
                typeof queryRewriteDebug.history_count === 'number' ? `历史上下文: ${queryRewriteDebug.history_count}` : '',
                queryRewriteDebug.folder_routing_enabled ? '目录建议: 已启用' : queryRewriteDebug.enabled ? '目录建议: 未启用' : '',
              ].filter(Boolean)}
              emptyText='未启用查询改写'
            />
            <InfoCard
              title='改写后的独立问题'
              value={standaloneQuestion}
            />
            <InfoCard
              title='归一化后的检索问题'
              value={normalizedRetrievalQuestion}
            />
            <InfoCard
              title='最终全文检索查询串'
              value={lexicalQueryText}
            />
            <ListCard
              title='同义词改写链路'
              items={synonymMatches.slice(0, 5).map((item) => {
                const userTerm = String(item?.user_term || '').trim()
                const professionalTerm = String(item?.professional_term || '').trim()
                const expansions = Array.isArray(item?.expansion_terms)
                  ? item.expansion_terms.map((value: unknown) => String(value).trim()).filter(Boolean)
                  : []
                return [
                  userTerm && professionalTerm ? `${userTerm} -> ${professionalTerm}` : '',
                  expansions.length > 0 ? `扩展词 ${expansions.join('、')}` : '',
                ].filter(Boolean).join(' · ')
              }).filter(Boolean)}
              emptyText='未命中同义词改写；归一化后的检索问题与原问题保持一致。'
            />
            <ListCard
              title='自动过滤候选'
              items={candidateFilters.slice(0, 5).map((item) => {
                const preview = formatCandidatePreview(item)
                return item?.applied ? `${preview} · 已应用` : preview
              }).filter(Boolean)}
              emptyText='未识别到过滤候选'
            />
            <ListCard
              title='候选分层'
              items={[
                `规则候选: ${ruleCandidates.length}`,
                `LLM 候选: ${llmCandidates.length}`,
                `被 LLM 纠偏的规则: ${correctedRuleCandidates.length}`,
              ]}
              emptyText='无候选分层数据'
            />
            <ListCard
              title='目录候选命中'
              items={[
                `规则目录候选: ${folderRuleCandidates.length}`,
                `LLM 目录候选: ${folderLlmCandidates.length}`,
                `被纠偏目录候选: ${correctedFolderCandidates.length}`,
                ...folderRuleCandidates.slice(0, 2).map((item) => `规则 · ${formatFolderCandidatePreview(item)}`),
                ...folderLlmCandidates.slice(0, 2).map((item) => `LLM · ${formatFolderCandidatePreview(item)}`),
              ]}
              emptyText='当前未识别到文件夹名称 / 路径相关的目录候选'
            />
            <ListCard
              title='自动信号'
              items={autoFilterSignals.slice(0, 5).map((item) => {
                const type = String(item?.signal_type || '').trim()
                const value = String(item?.filter_value || '').trim()
                const mode = String(item?.match_mode || item?.usage || '').trim()
                const confidence = typeof item?.confidence === 'number' ? item.confidence.toFixed(2) : ''
                return [type, value, mode, confidence ? `conf ${confidence}` : ''].filter(Boolean).join(' · ')
              }).filter(Boolean)}
              emptyText='未生成自动过滤 / 加权信号'
            />
            <ListCard
              title='术语上下文'
              items={glossaryEntries.slice(0, 5).map((item) => {
                const term = String(item?.term || '').trim()
                const definition = String(item?.definition || '').trim()
                return definition ? `${term}: ${definition}` : term
              }).filter(Boolean)}
              emptyText='未识别到术语上下文'
            />
            <CategorizedTermsCard
              title='最终全文检索词项拆解'
              strictTerms={lexicalFts.strictTerms}
              lexiconMatches={retrievalLexiconMatches}
              glossaryEntries={glossaryEntries}
              priorityPhrases={lexicalTerms.priorityPhrases}
            />
            <ListCard
              title='过滤·请求（标签 / 目录）'
              items={[
                `文件夹: ${formatIdListLine(explicitFilters.folder_ids)}`,
                `文档标签: ${formatIdListLine(explicitFilters.tag_ids)}`,
                `文件夹标签: ${formatIdListLine(explicitFilters.folder_tag_ids)}`,
                `kb 文档: ${formatIdListLine(explicitFilters.kb_doc_ids)}`,
                `业务文档: ${formatIdListLine(explicitFilters.document_ids)}`,
              ]}
              emptyText='无显式标签 / 目录约束'
            />
            <ListCard
              title='过滤·请求（元数据 / 表达式）'
              items={[
                `文档元数据: ${formatMetadataRecord(explicitFilters.document_metadata)}`,
                `单元元数据: ${formatMetadataRecord(explicitFilters.search_unit_metadata)}`,
                `表达式: ${formatMetadataRecord(explicitFilters.filter_expression)}`,
              ]}
              emptyText='无显式元数据 / 表达式约束'
            />
            <ListCard
              title='过滤·落地（标签 / 目录）'
              items={[
                `文件夹: ${formatIdListLine(retrievalFilters.folder_ids)}`,
                `文档标签: ${formatIdListLine(retrievalFilters.tag_ids)}`,
                `文件夹标签: ${formatIdListLine(retrievalFilters.folder_tag_ids)}`,
                `kb 文档: ${formatIdListLine(retrievalFilters.kb_doc_ids)}`,
                `业务文档: ${formatIdListLine(retrievalFilters.document_ids)}`,
              ]}
              emptyText='无落地标签 / 目录约束'
            />
            <ListCard
              title='过滤·落地（元数据 / 表达式）'
              items={[
                `文档元数据: ${formatMetadataRecord(retrievalFilters.document_metadata)}`,
                `单元元数据: ${formatMetadataRecord(retrievalFilters.search_unit_metadata)}`,
                `表达式: ${formatMetadataRecord(retrievalFilters.filter_expression)}`,
                `摘要: 请求 ${formatRequestedCounts(filterPipelineDebug.requested_filter_counts as Record<string, unknown>)} → 落地 ${formatAppliedCounts(filterPipelineDebug.applied_filter_counts as Record<string, unknown>)}`,
              ]}
              emptyText='无落地元数据 / 表达式约束'
            />
          </div>
        ) : null}

        {activeTab === 'compare' ? (
          <div className='grid gap-3 md:grid-cols-2'>
            <ListCard
              title='核心变化'
              items={compareResult
                ? [
                    result.executedQuery === compareResult.executedQuery ? '与基线使用相同问题' : `问题已变化: 基线为“${compareResult.executedQuery}”`,
                    `结果条数: ${currentHitCount}${formatOptionalDelta(hitDelta) ? ` (${formatOptionalDelta(hitDelta)})` : '（持平）'}`,
                    `平均最终分: ${currentAvgScore.toFixed(2)}${formatOptionalDelta(scoreDelta, 2) ? ` (${formatOptionalDelta(scoreDelta, 2)})` : '（持平）'}`,
                    `耗时: ${result.elapsedMs}ms${formatOptionalDelta(elapsedDelta) ? ` (${formatOptionalDelta(elapsedDelta)}ms)` : '（持平）'}`,
                  ]
                : []}
              emptyText='当前没有可用基线，执行下一轮后可查看对比。'
            />
            <ListCard
              title='文档变化'
              items={compareResult
                ? [
                    addedDocuments.length > 0 ? `新增文档: ${addedDocuments.join('、')}` : '新增文档: 无',
                    removedDocuments.length > 0 ? `移除文档: ${removedDocuments.join('、')}` : '移除文档: 无',
                  ]
                : []}
              emptyText='当前没有文档级变化。'
            />
            <ListCard title='Scope 变化' items={compareResult ? scopeDeltaItems : []} emptyText='当前没有 Scope 变化数据。' />
            <InfoCard
              title='一行结论'
              value={compareResult
                ? `${trendLabel}：结果条数${formatOptionalDelta(hitDelta) || '持平'}，平均分${formatOptionalDelta(scoreDelta, 2) || '持平'}，耗时${(formatOptionalDelta(elapsedDelta) ? `${formatOptionalDelta(elapsedDelta)}ms` : '持平')}。`
                : '暂无基线，建议继续执行一轮后再观察变化趋势。'}
            />
          </div>
        ) : null}

        {activeTab === 'diagnosis' ? (
          <div className='grid gap-3 md:grid-cols-2'>
            <ListCard
              title='执行链路摘要'
              items={[
                `原始问题: ${String(traceInput.raw_query || queryAnalysis.raw_query || result.executedQuery || '无')}`,
                `是否改写: ${traceInput.query_rewritten ? '是' : '否'}`,
                `改写后的独立问题: ${String(traceInput.standalone_query || queryAnalysis.standalone_query || queryAnalysis.raw_query || '与原始问题相同')}`,
                `归一化后的检索问题: ${String(traceInput.rewritten_query || queryAnalysis.rewritten_query || queryAnalysis.standalone_query || '与原始问题相同')}`,
                `最终全文检索查询串: ${String(traceInput.lexical_query || queryAnalysis.lexical_query || '无')}`,
                `过滤状态: ${formatRequestedCounts(filterPipelineDebug.requested_filter_counts as Record<string, unknown>)} → ${formatAppliedCounts(filterPipelineDebug.applied_filter_counts as Record<string, unknown>)}`,
                `向量召回: ${Number(traceRetrieval.vector_hit_count || 0)}`,
                `全文召回: ${Number(traceRetrieval.lexical_hit_count || 0)}`,
                `总结果数: ${Number(traceResults.item_count || result.items.length || 0)}`,
              ]}
              emptyText='当前没有执行链路摘要'
            />
            <CategorizedTermsCard
              title='最终全文检索词项拆解'
              strictTerms={lexicalFts.strictTerms}
              lexiconMatches={retrievalLexiconMatches}
              glossaryEntries={glossaryEntries}
              priorityPhrases={lexicalTerms.priorityPhrases}
            />
            <DiagnosisJsonGroup
              groups={[
                { id: 'pipeline-trace', title: 'Pipeline Trace', description: '完整链路事件（输入、过滤、召回、融合、结果）。', value: pipelineTrace, emptyText: '当前没有 Pipeline Trace', defaultOpen: true },
                { id: 'filter-summary', title: '过滤摘要', description: '硬过滤匹配命中与过滤执行摘要。', value: filterDebugSummary, emptyText: '无过滤摘要' },
                { id: 'retrieval-filters', title: '实际过滤条件', description: '当前轮次最终落地到检索的过滤条件。', value: retrievalFilters, emptyText: '当前未生成硬过滤条件' },
              ]}
            />
          </div>
        ) : null}
      </div>
    </details>
  )
}

function QueryAnalysisTabs({ activeTab, onChange }: { activeTab: QueryAnalysisTab; onChange: (tab: QueryAnalysisTab) => void }) {
  const tabs: Array<{ id: QueryAnalysisTab; label: string }> = [
    { id: 'overview', label: '总览' },
    { id: 'compare', label: '对比' },
    { id: 'diagnosis', label: '诊断' },
  ]
  return (
    <div className='flex flex-wrap gap-2'>
      {tabs.map((tab) => (
        <Button key={tab.id} type='button' variant={activeTab === tab.id ? 'default' : 'outline'} size='sm' className='h-8 text-xs' onClick={() => onChange(tab.id)}>
          {tab.label}
        </Button>
      ))}
    </div>
  )
}

function MetricPill({ title, value, delta }: { title: string; value: string; delta?: string | null }) {
  return (
    <div className='rounded-lg border border-border/60 bg-muted/30 px-3 py-2'>
      <div className='text-[11px] text-muted-foreground'>{title}</div>
      <div className='mt-1 flex items-end justify-between gap-2'>
        <span className='font-mono text-sm font-semibold text-foreground'>{value}</span>
        {delta ? <span className='text-[11px] text-muted-foreground'>{delta}</span> : null}
      </div>
    </div>
  )
}

function DiagnosisJsonGroup({
  groups,
}: {
  groups: Array<{ id: string; title: string; description: string; value: Record<string, any>; emptyText: string; defaultOpen?: boolean }>
}) {
  const handleCopyJson = async (value: Record<string, any>) => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(value, null, 2))
      toast.success('JSON 已复制')
    }
    catch {
      toast.error('复制失败，请检查浏览器权限')
    }
  }

  return (
    <div className='space-y-2 md:col-span-2'>
      {groups.map((group) => {
        const hasValue = group.value && Object.keys(group.value).length > 0
        return (
          <details key={group.id} className='rounded-xl border border-border/60 bg-background/80 p-3' open={group.defaultOpen}>
            <summary className='cursor-pointer list-none text-sm font-semibold text-foreground/80'>{group.title}</summary>
            <div className='mt-2 text-xs text-muted-foreground'>{group.description}</div>
            <div className='mt-2'>
              {hasValue ? (
                <div className='space-y-2'>
                  <div className='flex justify-end'>
                    <Button
                      type='button'
                      variant='outline'
                      size='sm'
                      className='h-7 gap-1.5 text-xs'
                      onClick={() => handleCopyJson(group.value)}
                    >
                      <Copy className='h-3.5 w-3.5' />
                      复制 JSON
                    </Button>
                  </div>
                  <pre className='max-h-80 overflow-x-auto overflow-y-auto rounded-lg bg-slate-950 px-3 py-3 text-xs leading-6 text-slate-100'>
                    {JSON.stringify(group.value, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className='text-sm text-muted-foreground'>{group.emptyText}</div>
              )}
            </div>
          </details>
        )
      })}
    </div>
  )
}

function HistoryCard({
  title,
  currentResult,
  latestResult,
  historyResults,
  selectedViewRunId,
  onSelectViewRun,
}: {
  title: string
  currentResult: RetrievalTestRunState
  latestResult?: RetrievalTestRunState | null
  historyResults: RetrievalTestRunState[]
  selectedViewRunId?: string | null
  onSelectViewRun?: (runId: string | null) => void
}) {
  const showLatestRow = Boolean(latestResult)
  return (
    <div className='rounded-xl border border-border/60 bg-background/80 p-4'>
      <div className='mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground/70'>{title}</div>
      <div className='mb-3 rounded-lg border border-dashed border-blue-200 bg-blue-50/60 px-3 py-2 text-xs text-blue-700'>
        正在查看：{formatRunTimeLabel(currentResult)} · {currentResult.executedQuery || '未记录问题'}
      </div>
      {showLatestRow || historyResults.length > 0 ? (
        <div className='space-y-2'>
          {showLatestRow ? (
            <button
              type='button'
              onClick={() => onSelectViewRun?.(null)}
              className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                !selectedViewRunId
                  ? 'border-blue-300 bg-blue-50 text-blue-800'
                  : 'border-border/60 bg-muted/30 text-foreground/80 hover:border-blue-200 hover:bg-blue-50/40'
              }`}
            >
              <div className='flex items-center justify-between gap-3'>
                <span className='font-medium'>当前轮次（最新）</span>
                <span className='text-[11px] text-muted-foreground'>{latestResult?.items.length || 0} 条 · {latestResult?.elapsedMs || 0}ms</span>
              </div>
              <div className='mt-1 line-clamp-2 text-xs text-muted-foreground'>{latestResult?.executedQuery || '未记录问题'}</div>
            </button>
          ) : null}
          {historyResults.map((run, index) => {
            const isSelected = selectedViewRunId === (run.runId || null)
            return (
              <button
                key={run.runId || `history-run-${index}`}
                type='button'
                onClick={() => onSelectViewRun?.(run.runId || null)}
                className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                  isSelected
                    ? 'border-blue-300 bg-blue-50 text-blue-800'
                    : 'border-border/60 bg-muted/30 text-foreground/80 hover:border-blue-200 hover:bg-blue-50/40'
                }`}
              >
                <div className='flex items-center justify-between gap-3'>
                  <span className='font-medium'>历史第 {index + 1} 轮</span>
                  <span className='text-[11px] text-muted-foreground'>{run.items.length} 条 · {run.elapsedMs}ms</span>
                </div>
                <div className='mt-1 line-clamp-2 text-xs text-muted-foreground'>{run.executedQuery || '未记录问题'}</div>
              </button>
            )
          })}
          <div className='text-[11px] text-muted-foreground'>历史仅保留最近 3 轮，可点击切换结果视图。</div>
        </div>
      ) : (
        <div className='text-sm text-muted-foreground'>再执行一次检索后，这里会保留最近 3 轮结果，方便切换查看。</div>
      )}
    </div>
  )
}

function InfoCard({ title, value }: { title: string; value: string }) {
  return (
    <div className='rounded-xl border border-border/60 bg-background/80 p-4'>
      <div className='mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground/70'>{title}</div>
      <div className='whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/80'>{value}</div>
    </div>
  )
}

function ListCard({ title, items, emptyText }: { title: string; items: string[]; emptyText: string }) {
  return (
    <div className='rounded-xl border border-border/60 bg-background/80 p-4'>
      <div className='mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground/70'>{title}</div>
      {items.length > 0 ? (
        <div className='space-y-2'>
          {items.map((item, index) => (
            <div key={`${title}-${index}`} className='rounded-lg bg-muted/40 px-3 py-2 text-sm leading-relaxed text-foreground/80'>
              {item}
            </div>
          ))}
        </div>
      ) : (
        <div className='text-sm text-muted-foreground'>{emptyText}</div>
      )}
    </div>
  )
}

function CategorizedTermsCard({
  title,
  strictTerms,
  lexiconMatches,
  glossaryEntries,
  priorityPhrases,
}: {
  title: string
  strictTerms: string[]
  lexiconMatches: any[]
  glossaryEntries: any[]
  priorityPhrases: string[]
}) {
  const allTerms = Array.from(new Set(strictTerms)).filter(Boolean)

  return (
    <div className='rounded-xl border border-border/60 bg-background/80 p-4'>
      <div className='mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground/70'>{title}</div>
      <p className='mb-3 text-[11px] leading-5 text-muted-foreground'>
        下列词项会参与最终全文检索查询构造，是实际用于全文检索召回的输入；它们不直接参与向量 embedding，而是服务于全文检索这一支路。
      </p>
      <div className='flex flex-wrap gap-2'>
        {allTerms.length > 0 ? (
          allTerms.map((term, index) => {
            const lexiconMatch = lexiconMatches.find((m) => m.term === term || (m.matched_text === term))
            const glossaryEntry = glossaryEntries.find((g) => g.term === term)
            const isPhrase = priorityPhrases.includes(term)

            let bgColor = 'bg-sky-100 text-sky-700 border-sky-200'
            let weightInfo = ''

            if (lexiconMatch) {
              bgColor = 'bg-pink-100 text-pink-700 border-pink-200'
              weightInfo = `x${lexiconMatch.weight || 1}`
            }
            else if (glossaryEntry) {
              bgColor = 'bg-emerald-100 text-emerald-700 border-emerald-200'
              weightInfo = 'x1.0'
            }

            return (
              <div
                key={`term-${index}`}
                className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold shadow-sm transition-all hover:shadow-md ${bgColor}`}
              >
                <span>{term}</span>
                {weightInfo && (
                  <span className='ml-0.5 rounded bg-black/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-current/85'>
                    {weightInfo}
                  </span>
                )}
                {isPhrase && (
                  <span className='ml-0.5 inline-block h-2.5 w-2.5 rounded-sm border border-violet-300 bg-violet-200 shadow-[0_0_0_2px_rgba(196,181,253,0.35)]' title='短语匹配' />
                )}
              </div>
            )
          })
        ) : (
          <div className='text-sm text-muted-foreground'>暂无分词数据</div>
        )}
      </div>
      <p className='mt-3 text-[10px] text-muted-foreground/60'>
        浅天蓝色为通用分词；浅珊瑚粉色为检索词条（核心加分）；浅薄荷绿色为专业术语；浅薰衣草紫方块表示短语匹配。上述词项会被用于全文检索查询构造，后续的向量检索、融合与重排走的是另一条链路。
      </p>
    </div>
  )
}
