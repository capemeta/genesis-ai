import { useRef, useState } from 'react'
import { ArrowDownToLine, ArrowUpToLine, ChevronDown, ChevronUp, Copy, Download, Loader2, Search } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  RetrievalDebugCandidateSummaryList,
  RetrievalDebugJsonBlock,
  RetrievalDebugMetricCard,
  RetrievalDebugRow,
  RetrievalDebugSection,
  RetrievalDebugSheet,
  RetrievalDebugStat,
  formatRetrievalDebugNumber,
} from '@/features/shared/retrieval-debug'
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
import { AUTO_FILTER_MODE_OPTIONS } from './constants'

interface RetrievalTestResultsProps {
  result: RetrievalTestRunState | null
  isRunning?: boolean
  compareResult?: RetrievalTestRunState | null
  historyResults?: RetrievalTestRunState[]
  onExportHistory?: () => void
  finalScoreThreshold: number
}

function InfoTooltipLabel({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button type='button' className='inline-flex cursor-help items-center gap-1 text-left'>
            <span>{label}</span>
            <span className='inline-flex h-4 w-4 items-center justify-center rounded-full border border-current/30 text-[10px] leading-none opacity-75'>?</span>
          </button>
        </TooltipTrigger>
        <TooltipContent className='max-w-[320px] text-xs leading-5'>
          <p>{tooltip}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function getResultBadgeMeta(score: number, finalScoreThreshold: number) {
  const strongThreshold = Math.min(finalScoreThreshold + 0.2, 1)

  if (score >= strongThreshold) {
    return {
      label: '高相关',
      className: 'border-none bg-green-100 text-green-700 hover:bg-green-100',
    }
  }

  if (score >= finalScoreThreshold) {
    return {
      label: '已命中',
      className: 'border-none bg-blue-100 text-blue-700 hover:bg-blue-100',
    }
  }

  return {
    label: '低于阈值',
    className: 'border-none bg-slate-100 text-slate-600 hover:bg-slate-100',
  }
}

function resolveEffectiveKeywordScore(item?: RetrievalTestRunState['items'][number] | null) {
  const directScore = item?.keyword_score
  if (typeof directScore === 'number' && Number.isFinite(directScore)) {
    return directScore
  }
  const traceScore = (item?.metadata?.score_trace || {}) as Record<string, any>
  if (typeof traceScore.keyword_score === 'number' && Number.isFinite(traceScore.keyword_score)) {
    return Number(traceScore.keyword_score)
  }
  return undefined
}

function resolveHitDetailLexicalScore(detail?: Record<string, any> | null) {
  if (typeof detail?.lexical_raw_score === 'number' && Number.isFinite(detail.lexical_raw_score)) {
    return Number(detail.lexical_raw_score)
  }
  if (String(detail?.backend_type || '').trim() === 'pg_fts' || String(detail?.backend_type || '').trim() === 'lexical') {
    const score = detail?.score
    if (typeof score === 'number' && Number.isFinite(score)) {
      return Number(score)
    }
  }
  return undefined
}

function formatDelta(value: number, digits = 0) {
  const normalizedValue = Object.is(value, -0) ? 0 : value
  if (!Number.isFinite(normalizedValue) || Math.abs(normalizedValue) < 10 ** -(digits + 1)) {
    return `0${digits > 0 ? normalizedValue.toFixed(digits).slice(1) : ''}`
  }
  return `${normalizedValue > 0 ? '+' : ''}${normalizedValue.toFixed(digits)}`
}

function buildItemMap(items: RetrievalTestRunState['items']) {
  return new Map(items.map((item) => [String(item.id), item]))
}

function getGroupingStrategyLabel(strategy?: string) {
  const normalized = String(strategy || '').trim()
  if (normalized === 'business_content_group') {
    return '业务聚合'
  }
  if (normalized === 'result_unit_only') {
    return '结果单元'
  }
  return '未标注'
}

function getHierarchicalModeLabel(mode?: string) {
  const normalized = String(mode || '').trim()
  if (normalized === 'leaf_only') {
    return '仅叶子块'
  }
  if (normalized === 'recursive') {
    return '递归父上下文'
  }
  if (normalized === 'auto_merge') {
    return '自动父块合并'
  }
  return '未标注'
}

function getResultUnitKindLabel(kind?: string) {
  const normalized = String(kind || '').trim()
  if (normalized === 'complete_unit') {
    return '完整单元回收'
  }
  if (normalized === 'promoted_parent') {
    return '父块提升'
  }
  if (normalized === 'leaf') {
    return '叶子直返'
  }
  if (normalized === 'doc_summary') {
    return '文档摘要'
  }
  return '未标注'
}

function getResultUnitBadgeMeta(kind?: string) {
  const normalized = String(kind || '').trim()
  if (normalized === 'promoted_parent') {
    return {
      label: '父块展示',
      className: 'border-none bg-amber-100 text-amber-700 hover:bg-amber-100',
    }
  }
  if (normalized === 'complete_unit') {
    return {
      label: '完整单元',
      className: 'border-none bg-emerald-100 text-emerald-700 hover:bg-emerald-100',
    }
  }
  if (normalized === 'leaf') {
    return {
      label: '叶子块展示',
      className: 'border-none bg-sky-100 text-sky-700 hover:bg-sky-100',
    }
  }
  if (normalized === 'doc_summary') {
    return {
      label: '文档摘要',
      className: 'border-none bg-violet-100 text-violet-700 hover:bg-violet-100',
    }
  }
  return {
    label: '结果单元未标注',
    className: 'border-none bg-slate-100 text-slate-600 hover:bg-slate-100',
  }
}

function getChunkTopologyTypeLabel(kind?: string) {
  const normalized = String(kind || '').trim()
  if (normalized === 'root') {
    return '根块'
  }
  if (normalized === 'intermediate') {
    return '中间块'
  }
  if (normalized === 'leaf') {
    return '叶子块'
  }
  if (normalized === 'root_leaf') {
    return '根叶一体块'
  }
  return '未标注'
}

function buildResultStrategySummary(metadata?: Record<string, any>) {
  const parts: string[] = []
  const groupingStrategy = getGroupingStrategyLabel(metadata?.grouping_strategy)
  const hierarchicalMode = getHierarchicalModeLabel(metadata?.hierarchical_retrieval_mode)
  const resultUnitKind = getResultUnitKindLabel(metadata?.result_unit_kind)

  if (groupingStrategy !== '未标注') {
    parts.push(`分组 ${groupingStrategy}`)
  }
  if (hierarchicalMode !== '未标注') {
    parts.push(`层级 ${hierarchicalMode}`)
  }
  if (resultUnitKind !== '未标注') {
    parts.push(`结果 ${resultUnitKind}`)
  }
  return parts.join(' · ')
}


function getScoreDeltaMeta(currentScore: number, previousScore?: number) {
  if (typeof previousScore !== 'number') {
    return {
      label: '本轮新增',
      className: 'border-none bg-violet-100 text-violet-700 hover:bg-violet-100',
    }
  }

  const delta = currentScore - previousScore
  if (Math.abs(delta) < 0.005) {
    return {
      label: '分数持平',
      className: 'border-none bg-slate-100 text-slate-600 hover:bg-slate-100',
    }
  }
  if (delta > 0) {
    return {
      label: `分数提升 ${formatDelta(delta, 2)}`,
      className: 'border-none bg-emerald-100 text-emerald-700 hover:bg-emerald-100',
    }
  }
  return {
    label: `分数下降 ${formatDelta(delta, 2)}`,
    className: 'border-none bg-amber-100 text-amber-700 hover:bg-amber-100',
  }
}

function getResultPreviewText(item?: RetrievalTestRunState['items'][number] | null) {
  return String(item?.content || '暂无内容')
}

function getDebugContentViews(item?: RetrievalTestRunState['items'][number] | null) {
  const metadata = (item?.metadata || {}) as Record<string, any>
  const debug = (metadata.debug || {}) as Record<string, any>
  return {
    rawHitChunk: (debug.raw_hit_chunk || {}) as Record<string, any>,
    contextUnit: (debug.context_unit || {}) as Record<string, any>,
    llmContext: (debug.llm_context || {}) as Record<string, any>,
  }
}

function getSelectedResultTone(score?: number) {
  if (typeof score !== 'number' || !Number.isFinite(score)) {
    return {
      cardClassName: 'rounded-3xl border border-slate-200/90 bg-white p-5 shadow-sm',
      labelClassName: 'text-slate-600',
    }
  }
  if (score >= 0.85) {
    return {
      cardClassName: 'rounded-3xl border border-emerald-200/90 bg-gradient-to-br from-white via-emerald-50/55 to-slate-50 p-5 shadow-sm shadow-emerald-100/60',
      labelClassName: 'text-emerald-700',
    }
  }
  if (score >= 0.7) {
    return {
      cardClassName: 'rounded-3xl border border-cyan-200/90 bg-gradient-to-br from-white via-cyan-50/55 to-slate-50 p-5 shadow-sm shadow-cyan-100/60',
      labelClassName: 'text-cyan-700',
    }
  }
  return {
    cardClassName: 'rounded-3xl border border-amber-200/90 bg-gradient-to-br from-white via-amber-50/60 to-slate-50 p-5 shadow-sm shadow-amber-100/60',
    labelClassName: 'text-amber-700',
  }
}

function CopyJsonActionButton({ value }: { value: unknown }) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(value, null, 2))
      toast.success('JSON 已复制')
    }
    catch {
      toast.error('复制失败，请检查浏览器权限')
    }
  }

  return (
    <Button
      type='button'
      variant='outline'
      size='sm'
      className='h-7 gap-1.5 border-slate-300 bg-white text-xs text-slate-700 hover:bg-slate-50'
      onClick={handleCopy}
    >
      <Copy className='h-3.5 w-3.5' />
      复制 JSON
    </Button>
  )
}

function formatAutoFilterModeLabel(mode?: string) {
  const normalized = String(mode || '').trim()
  const matched = AUTO_FILTER_MODE_OPTIONS.find(item => item.value === normalized)
  return matched?.label || normalized || '未标注'
}

function formatAutoSignalTypeLabel(type?: string) {
  const normalized = String(type || '').trim()
  if (normalized === 'doc_tag') {
    return '文档标签加权'
  }
  if (normalized === 'folder_tag') {
    return '文件夹标签加权'
  }
  if (normalized === 'document_metadata') {
    return '文档元数据过滤'
  }
  if (normalized === 'search_unit_metadata') {
    return '分块元数据过滤'
  }
  return normalized || '未标注'
}

function formatMatchModeLabel(mode?: string) {
  const normalized = String(mode || '').trim()
  if (normalized === 'boost') {
    return '只加权'
  }
  if (normalized === 'match_or_missing') {
    return '匹配或缺失'
  }
  if (normalized === 'match_only') {
    return '必须匹配'
  }
  return normalized || '未标注'
}

function buildAutoSignalEffectDescription(item: Record<string, any>) {
  const signalType = String(item.signal_type || '').trim()
  const filterValue = String(item.filter_value || '').trim() || '当前值'
  const debug = (item.debug || {}) as Record<string, any>
  const fieldName = String(debug.field_name || debug.field_key || item.target_id || '').trim() || '字段'
  const matchMode = String(item.match_mode || item.usage || '').trim()

  if (signalType === 'doc_tag' || signalType === 'folder_tag') {
    return '效果：仅参与标签加权，不直接缩窄检索范围'
  }
  if (signalType === 'document_metadata') {
    if (matchMode === 'match_only') {
      return `生效条件：仅保留文档元数据“${fieldName}=${filterValue}”的结果`
    }
    return `生效条件：文档元数据“${fieldName}=${filterValue}”或字段缺失时保留，否则过滤`
  }
  if (signalType === 'search_unit_metadata') {
    if (matchMode === 'match_only') {
      return `生效条件：仅保留搜索单元元数据“${fieldName}=${filterValue}”的结果`
    }
    return `生效条件：搜索单元元数据“${fieldName}=${filterValue}”或字段缺失时保留，否则过滤`
  }
  return ''
}

function renderAutoFilterSignals(signals: unknown) {
  const list = Array.isArray(signals) ? signals : []
  if (list.length === 0) {
    return <div className='text-xs text-slate-500'>未生成自动过滤 / 加权信号。</div>
  }
  return (
    <div className='space-y-2'>
      {list.map((raw, index) => {
        const item = (raw || {}) as Record<string, any>
        const targetPath = Array.isArray(item.target_path) ? item.target_path.map((part) => String(part || '').trim()).filter(Boolean).join('.') : ''
        const debug = (item.debug || {}) as Record<string, any>
        const effectDescription = buildAutoSignalEffectDescription(item)
        const signalType = String(item.signal_type || '').trim()
        const isMetadataSignal = signalType === 'document_metadata' || signalType === 'search_unit_metadata'
        const metadataFieldLabel = String(debug.field_name || debug.field_key || item.target_id || '').trim() || '字段'
        const metadataValueLabel = String(item.filter_value || '').trim() || '无'
        return (
          <div key={`${String(item.signal_type || 'signal')}-${String(item.target_id || index)}`} className='rounded-xl border border-slate-200/90 bg-white/85 p-3 text-xs text-slate-700'>
            <div className='flex flex-wrap items-center justify-between gap-2'>
              <div className='flex min-w-0 flex-wrap items-center gap-1.5'>
                <Badge variant='outline' className='border-blue-200 bg-blue-50 text-blue-700'>
                  {formatAutoSignalTypeLabel(item.signal_type)}
                </Badge>
                {isMetadataSignal ? (
                  <div className='flex flex-wrap items-center gap-2'>
                    <span className='rounded-md bg-white/90 px-2 py-1 text-[11px] font-semibold text-sky-700 shadow-sm'>
                      {metadataFieldLabel}
                    </span>
                    <span className='rounded-md bg-sky-100/90 px-2 py-1 text-[11px] font-medium text-sky-900'>
                      {metadataValueLabel}
                    </span>
                  </div>
                ) : (
                  <span className='font-medium'>{String(item.filter_value || '未标注')}</span>
                )}
                <span className='text-slate-400'>·</span>
                <span>{formatMatchModeLabel(item.match_mode || item.usage)}</span>
              </div>
              <span className='font-mono text-[11px] text-slate-500'>conf {formatRetrievalDebugNumber(item.confidence)}</span>
            </div>
            <div className='mt-2 grid gap-1 text-[11px] text-slate-500 sm:grid-cols-2'>
              {!isMetadataSignal ? <span className='break-all'>target_id: {String(item.target_id || '无')}</span> : null}
              {!isMetadataSignal && targetPath ? <span className='break-all'>target_path: {targetPath}</span> : null}
              <span>来源: {String(item.layer || 'unknown')} / {String(item.source || 'unknown')}</span>
              <span>应用: {item.applied ? '是' : '候选信号'}</span>
              {isMetadataSignal && targetPath && targetPath !== metadataFieldLabel ? (
                <span className='break-all'>字段路径: {targetPath}</span>
              ) : null}
            </div>
            {effectDescription ? (
              <div className='mt-2 rounded-lg border border-dashed border-sky-200 bg-sky-50/60 px-2.5 py-2 text-[11px] leading-relaxed text-sky-900'>
                {effectDescription}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function renderAutoMetadataDebug(value: unknown) {
  const record = (value && typeof value === 'object' ? value : {}) as Record<string, any>
  const entries = Object.entries(record)
  if (entries.length === 0) {
    return <div className='text-xs text-slate-500'>本轮没有应用自动元数据过滤。</div>
  }
  return (
    <div className='space-y-2'>
      {entries.map(([key, raw]) => {
        const item = (raw || {}) as Record<string, any>
        const values = Array.isArray(item.values) ? item.values.map((current) => String(current || '').trim()).filter(Boolean) : []
        return (
          <div key={key} className='rounded-xl border border-emerald-200/80 bg-emerald-50/40 px-3 py-2 text-xs text-emerald-900'>
            <div className='flex flex-wrap items-center justify-between gap-2'>
              <div className='flex flex-wrap items-center gap-2'>
                <span className='rounded-md bg-white/80 px-2 py-1 text-[11px] font-semibold text-emerald-700 shadow-sm'>
                  {key}
                </span>
                <span className='rounded-md bg-emerald-100/90 px-2 py-1 text-[11px] font-medium text-emerald-900'>
                  {values.length > 0 ? values.join(' / ') : '无'}
                </span>
              </div>
              <span className='text-[11px]'>{formatMatchModeLabel(item.match_mode)}</span>
            </div>
            <div className='mt-2 text-[11px] leading-relaxed text-emerald-800/80'>
              <span>关系: {String(item.relation || '同字段 OR，不同字段 AND')}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function buildAutoTagBoostLines(debug: Record<string, any>) {
  const matches = Array.isArray(debug.matches) ? debug.matches : []
  const lines = [
    `有效标签加权: ${formatRetrievalDebugNumber(debug.boost)}`,
    `文档标签: ${formatRetrievalDebugNumber(debug.doc_tag_boost)}`,
    `文件夹标签: ${formatRetrievalDebugNumber(debug.folder_tag_boost)}`,
  ]
  matches.slice(0, 6).forEach((match: Record<string, any>) => {
    const type = formatAutoSignalTypeLabel(match.type)
    const distance = typeof match.distance === 'number' ? ` · 距离 ${match.distance}` : ''
    lines.push(`${type}: ${String(match.filter_value || match.tag_id || '未标注')}${distance} · ${formatRetrievalDebugNumber(match.score)}`)
  })
  if (matches.length > 6) {
    lines.push(`其余匹配: ${matches.length - 6} 项`)
  }
  return lines
}

function buildCandidateLabelMap(
  queryAnalysis: Record<string, any>,
  filterType: 'tag_id' | 'folder_tag_id' | 'folder_id'
) {
  const source = Array.isArray(queryAnalysis.filter_candidates) ? queryAnalysis.filter_candidates : []
  const result = new Map<string, string[]>()
  source.forEach((item: Record<string, any>) => {
    if (String(item?.filter_type || '').trim() !== filterType) {
      return
    }
    const targetId = String(item?.target_id || '').trim()
    const label = String(item?.filter_value || '').trim()
    if (!targetId || !label) {
      return
    }
    const prev = result.get(targetId) || []
    if (!prev.includes(label)) {
      prev.push(label)
      result.set(targetId, prev)
    }
  })
  return result
}

function buildMatchedDocumentNameMap(filterDebug: Record<string, any>) {
  const matchedDocs = Array.isArray(filterDebug?.matched_documents) ? filterDebug.matched_documents : []
  const result = new Map<string, string>()
  matchedDocs.forEach((item: Record<string, any>) => {
    const id = String(item?.kb_doc_id || '').trim()
    const name = String(item?.name || '').trim()
    if (id && name && !result.has(id)) {
      result.set(id, name)
    }
  })
  return result
}

function buildMatchedDocumentDetailMap(filterDebug: Record<string, any>) {
  const matchedDocs = Array.isArray(filterDebug?.matched_documents) ? filterDebug.matched_documents : []
  const result = new Map<string, Record<string, any>>()
  matchedDocs.forEach((item: Record<string, any>) => {
    const id = String(item?.kb_doc_id || '').trim()
    if (!id) {
      return
    }
    result.set(id, {
      id,
      name: String(item?.name || '').trim(),
      document_id: String(item?.document_id || '').trim(),
    })
  })
  return result
}

function buildResolvedFilterLabelMap(items: unknown) {
  const list = Array.isArray(items) ? items : []
  const result = new Map<string, Record<string, any>>()
  list.forEach((item) => {
    const id = String((item as Record<string, any>)?.id || '').trim()
    if (id) {
      result.set(id, (item as Record<string, any>) || {})
    }
  })
  return result
}

function mergeDetailMaps(
  primary: Map<string, Record<string, any>>,
  fallback: Map<string, Record<string, any>>
) {
  const result = new Map<string, Record<string, any>>()
  const ids = new Set([...primary.keys(), ...fallback.keys()])
  ids.forEach((id) => {
    result.set(id, {
      ...(fallback.get(id) || {}),
      ...(primary.get(id) || {}),
    })
  })
  return result
}

function renderIdWithNameList(
  ids: unknown,
  options?: {
    nameMap?: Map<string, string>
    aliasMap?: Map<string, string[]>
    detailMap?: Map<string, Record<string, any>>
    emptyText?: string
  }
) {
  const list = Array.isArray(ids) ? ids.map(item => String(item).trim()).filter(Boolean) : []
  if (list.length === 0) {
    return options?.emptyText || '无'
  }
  return (
    <TooltipProvider>
      <div className='flex flex-wrap gap-1.5'>
        {list.map((id) => {
          const detail = options?.detailMap?.get(id) || {}
          const detailMatchedTerms = Array.isArray(detail.matched_terms) ? detail.matched_terms.map((item) => String(item).trim()).filter(Boolean) : []
          const aliases = detailMatchedTerms.length > 0 ? detailMatchedTerms : (options?.aliasMap?.get(id) || [])
          const detailName = String(detail.name || '').trim()
          const detailPath = String(detail.path || '').trim()
          const detailDocumentId = String(detail.document_id || '').trim()
          const fallbackName = detailName || options?.nameMap?.get(id)
          const displayLabel = aliases[0] || fallbackName || id
          const extraAliasCount = aliases.length > 1 ? aliases.length - 1 : 0
          const handleCopy = async (value: string, successMessage: string) => {
            try {
              await navigator.clipboard.writeText(value)
              toast.success(successMessage)
            }
            catch {
              toast.error('复制失败，请检查浏览器权限')
            }
          }
          return (
            <Tooltip key={id}>
              <TooltipTrigger asChild>
                <Badge variant='secondary' className='max-w-[280px] cursor-help truncate'>
                  {displayLabel}
                  {extraAliasCount > 0 ? ` +${extraAliasCount}` : ''}
                </Badge>
              </TooltipTrigger>
              <TooltipContent align='start' className='max-w-[440px] rounded-xl border border-sky-100 bg-white/95 p-3 text-xs text-slate-700 shadow-lg shadow-sky-100/50'>
                {detailName ? <div>名称: {detailName}</div> : null}
                {detailPath ? <div className='mt-1'>路径: {detailPath}</div> : null}
                <div className='mt-2 rounded-lg border border-sky-100 bg-sky-50/80 px-2.5 py-2'>
                  <div className='flex items-center justify-between gap-2'>
                    <span className='font-medium text-sky-700'>kb 文档 ID</span>
                    <Button
                      type='button'
                      variant='outline'
                      size='sm'
                      className='h-6 border-sky-200 bg-white px-2 text-[10px] text-sky-700 hover:bg-sky-50'
                      onClick={() => handleCopy(id, 'kb 文档 ID 已复制')}
                    >
                      复制
                    </Button>
                  </div>
                  <div className='mt-1 break-all font-mono text-[11px] text-sky-900'>{id}</div>
                </div>
                {detailDocumentId ? (
                  <div className='mt-2 rounded-lg border border-pink-100 bg-pink-50/80 px-2.5 py-2'>
                    <div className='flex items-center justify-between gap-2'>
                      <span className='font-medium text-pink-700'>业务文档 ID</span>
                      <Button
                        type='button'
                        variant='outline'
                        size='sm'
                        className='h-6 border-pink-200 bg-white px-2 text-[10px] text-pink-700 hover:bg-pink-50'
                        onClick={() => handleCopy(detailDocumentId, '业务文档 ID 已复制')}
                      >
                        复制
                      </Button>
                    </div>
                    <div className='mt-1 break-all font-mono text-[11px] text-pink-900'>{detailDocumentId}</div>
                  </div>
                ) : null}
                {aliases.length > 1 ? (
                  <div className='mt-2'>
                    <div className='text-slate-500'>匹配词</div>
                    <div className='mt-1 break-all text-slate-700'>{aliases.join('、')}</div>
                  </div>
                ) : null}
              </TooltipContent>
            </Tooltip>
          )
        })}
      </div>
    </TooltipProvider>
  )
}

function renderMatchedDocumentPreview(filterDebug: Record<string, any>) {
  const detailMap = buildMatchedDocumentDetailMap(filterDebug)
  const ids = Array.from(detailMap.keys())
  if (ids.length === 0) {
    return '无'
  }
  return renderIdWithNameList(ids, { detailMap })
}

function CopyJsonIconButton({ value, title = '复制 JSON' }: { value: unknown; title?: string }) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(value, null, 2))
      toast.success('JSON 已复制')
    }
    catch {
      toast.error('复制失败，请检查浏览器权限')
    }
  }

  return (
    <Button
      type='button'
      variant='ghost'
      size='icon'
      className='h-7 w-7 rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-800'
      onClick={handleCopy}
      title={title}
      aria-label={title}
    >
      <Copy className='h-3.5 w-3.5' />
    </Button>
  )
}

function filterCandidatesByType(candidates: unknown, filterType: string) {
  const source = Array.isArray(candidates) ? candidates : []
  return source.filter((item) => String((item as Record<string, any>)?.filter_type || '').trim() === filterType) as Array<Record<string, any>>
}

/**
 * 统一的检索词项深度全景展示（对齐 QueryAnalysis 和 PG FTS 分词）
 */
function CategorizedSearchTerms({
  queryAnalysis,
  debug,
}: {
  queryAnalysis: Record<string, any>
  debug: Record<string, any>
}) {
  const fts = getLexicalFtsDebugFromDebug(debug)
  const lexiconMatches = (queryAnalysis.retrieval_lexicon_matches || []) as any[]
  const glossaryEntries = (queryAnalysis.glossary_entries || []) as any[]
  const { priorityPhrases } = getLexicalTermsFromQueryAnalysis(queryAnalysis)

  const allTerms = Array.from(new Set(fts.strictTerms)).filter(Boolean)

  if (allTerms.length === 0 && fts.empty) {
    return (
      <RetrievalDebugSection title='检索词项全景分析'>
        <div className='text-xs text-slate-500'>暂无检索词项分解数据。</div>
      </RetrievalDebugSection>
    )
  }

  return (
    <RetrievalDebugSection title='检索词项分解 · 深度全景'>
      <div className='space-y-4'>
        <p className='text-[11px] leading-relaxed text-slate-500'>
          此处展示了实际参与全文检索查询构造的词项，全文检索查询使用这些词项进行查询。
        </p>

        <div className='flex flex-wrap gap-2'>
          {allTerms.map((term, index) => {
            const lexiconMatch = lexiconMatches.find((m) => m.term === term || m.matched_text === term)
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
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold shadow-sm active:scale-95 transition-all ${bgColor}`}
              >
                <span>{term}</span>
                {weightInfo && (
                  <span className='ml-0.5 rounded bg-black/10 px-1.5 py-0.5 font-mono text-[9px] font-bold text-current/85'>
                    {weightInfo}
                  </span>
                )}
                {isPhrase && (
                  <span className='ml-0.5 inline-block h-2.5 w-2.5 rounded-sm border border-violet-300 bg-violet-200 shadow-[0_0_0_2px_rgba(196,181,253,0.35)]' title='短语/精准匹配' />
                )}
              </div>
            )
          })}
        </div>

        <div className='rounded-xl border border-dashed border-slate-200 bg-slate-50/30 p-3'>
          <div className='mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400'>底层 FTS 详情</div>
          <div className='space-y-2'>
            <RetrievalDebugRow label='规范化查询' value={fts.normalizedQuery || '无'} textSizeClassName='text-[11px]' />
            <RetrievalDebugRow label='短语 ILIKE' value={fts.hasPhrasePattern ? '已启用（整句归一化）' : '未启用'} textSizeClassName='text-[11px]' />
            <RetrievalDebugRow
              label='命中停用词'
              value={fts.stopwordHits.length > 0 ? `${fts.stopwordHits.join('、')}（词表 ${fts.stopwordCount} 项）` : `无（词表 ${fts.stopwordCount} 项）`}
              textSizeClassName='text-[11px]'
            />
            <div className='flex flex-wrap gap-x-6 gap-y-2'>
               {fts.asciiTerms.length > 0 && (
                 <div className='min-w-[80px]'>
                    <div className='mb-1 text-[10px] text-slate-400'>ASCII 项</div>
                    <div className='flex flex-wrap gap-1'>
                      {fts.asciiTerms.map(t => (
                        <span key={t} className='rounded bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700'>{t}</span>
                      ))}
                    </div>
                 </div>
               )}
               {fts.cjkTerms.length > 0 && (
                 <div className='min-w-[80px]'>
                    <div className='mb-1 text-[10px] text-slate-400'>CJK 片段</div>
                    <div className='flex flex-wrap gap-1'>
                      {fts.cjkTerms.map(t => (
                        <span key={t} className='rounded bg-rose-50 px-1.5 py-0.5 text-[10px] text-rose-700'>{t}</span>
                      ))}
                    </div>
                 </div>
               )}
            </div>
          </div>
        </div>

        <div className='flex items-center gap-4 text-[10px] text-muted-foreground/70'>
          <div className='flex items-center gap-1.5'>
            <div className='h-3.5 w-3.5 rounded-sm border border-sky-200 bg-sky-100' />
            <span>通用分词</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <div className='h-3.5 w-3.5 rounded-sm border border-pink-200 bg-pink-100' />
            <span>检索词条 (核心加分)</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <div className='h-3.5 w-3.5 rounded-sm border border-emerald-200 bg-emerald-100' />
            <span>专业术语</span>
          </div>
          <div className='flex items-center gap-1.5 ml-2'>
            <div className='h-3.5 w-3.5 rounded-sm border border-violet-300 bg-violet-200' />
            <span>短语匹配模式</span>
          </div>
        </div>
      </div>
    </RetrievalDebugSection>
  )
}

/** 显式请求过滤 vs 查询分析合并 vs 候选解析落地 */
function FilterTraceDebugSection({
  debug,
  queryAnalysis,
}: {
  debug: Record<string, any>
  queryAnalysis: Record<string, any>
}) {
  const pipelineTrace = (debug.pipeline_trace || {}) as Record<string, any>
  const normalized = (pipelineTrace.config?.normalized_config || {}) as Record<string, any>
  const { explicit, resolvedMerged, resolvedPipeline, filterDebug } = getFilterTraceParts(debug, queryAnalysis)
  const resolvedFilterLabels = (queryAnalysis.resolved_filter_labels || {}) as Record<string, any>
  const resolvedFolderMap = buildResolvedFilterLabelMap(resolvedFilterLabels.folders)
  const resolvedDocTagMap = buildResolvedFilterLabelMap(resolvedFilterLabels.doc_tags)
  const resolvedFolderTagMap = buildResolvedFilterLabelMap(resolvedFilterLabels.folder_tags)
  const resolvedKbDocMap = buildResolvedFilterLabelMap(resolvedFilterLabels.kb_docs)
  const tagAliasMap = buildCandidateLabelMap(queryAnalysis, 'tag_id')
  const folderTagAliasMap = buildCandidateLabelMap(queryAnalysis, 'folder_tag_id')
  const folderAliasMap = buildCandidateLabelMap(queryAnalysis, 'folder_id')
  const matchedDocNameMap = buildMatchedDocumentNameMap(filterDebug)
  const matchedDocDetailMap = buildMatchedDocumentDetailMap(filterDebug)
  const kbDocDetailMap = mergeDetailMaps(resolvedKbDocMap, matchedDocDetailMap)
  const autoSignals = Array.isArray(queryAnalysis.auto_filter_signals) ? queryAnalysis.auto_filter_signals : []
  const candidateBreakdown = (queryAnalysis.candidate_breakdown || {}) as Record<string, any>
  const ruleCandidates = Array.isArray(candidateBreakdown.rule_candidates) ? candidateBreakdown.rule_candidates : []
  const llmCandidates = Array.isArray(candidateBreakdown.llm_candidates) ? candidateBreakdown.llm_candidates : []
  const correctedRuleCandidates = Array.isArray(candidateBreakdown.corrected_rule_candidates) ? candidateBreakdown.corrected_rule_candidates : []
  const folderRuleCandidates = filterCandidatesByType(ruleCandidates, 'folder_id')
  const folderLlmCandidates = filterCandidatesByType(llmCandidates, 'folder_id')
  const correctedFolderCandidates = filterCandidatesByType(correctedRuleCandidates, 'folder_id')

  return (
    <RetrievalDebugSection title='过滤链路总览'>
      <div className='space-y-4'>
        <RetrievalDebugRow
          label='自动过滤模式'
          value={formatAutoFilterModeLabel(String(queryAnalysis.auto_filter_mode || normalized.auto_filter_mode || ''))}
        />
        <div className='rounded-2xl border border-slate-200/80 bg-slate-50/50 p-3'>
          <div className='mb-2 text-xs font-semibold text-slate-700'>请求侧 · 显式过滤（界面 / API 传入）</div>
          <RetrievalDebugRow label='文件夹' value={renderIdWithNameList(explicit.folder_ids, { aliasMap: folderAliasMap, detailMap: resolvedFolderMap })} />
          <RetrievalDebugRow label='文档标签' value={renderIdWithNameList(explicit.tag_ids, { aliasMap: tagAliasMap, detailMap: resolvedDocTagMap })} />
          <RetrievalDebugRow label='文件夹标签' value={renderIdWithNameList(explicit.folder_tag_ids, { aliasMap: folderTagAliasMap, detailMap: resolvedFolderTagMap })} />
          <RetrievalDebugRow label='限定 kb 文档' value={renderIdWithNameList(explicit.kb_doc_ids, { nameMap: matchedDocNameMap, detailMap: resolvedKbDocMap })} />
          <RetrievalDebugRow label='限定业务文档 ID' value={formatIdListLine(explicit.document_ids)} />
          <RetrievalDebugRow label='内容组 ID' value={formatIdListLine(explicit.content_group_ids)} />
          <RetrievalDebugRow label='文档元数据过滤' value={formatMetadataRecord(explicit.document_metadata)} textSizeClassName='text-xs break-all' />
          <RetrievalDebugRow label='搜索单元元数据过滤' value={formatMetadataRecord(explicit.search_unit_metadata)} textSizeClassName='text-xs break-all' />
          <RetrievalDebugRow
            label={<InfoTooltipLabel label='统一过滤表达式（标签 / 元数据）' tooltip='这里是前端/API 显式传入的高级过滤表达式。它属于硬过滤，优先级最高；如果同时有 LLM 表达式，后端会在其基础上继续 AND 收紧，不会被覆盖。' /> as any}
            value={formatMetadataRecord(explicit.filter_expression)}
            textSizeClassName='text-xs break-all'
          />
          <RetrievalDebugRow
            label='目录/标签选项'
            value={[
              `含子文件夹: ${explicit.include_descendant_folders === true ? '是' : explicit.include_descendant_folders === false ? '否' : '—'}`,
              `仅已打标文档: ${explicit.only_tagged === true ? '是' : explicit.only_tagged === false ? '否' : '—'}`,
              typeof explicit.latest_days === 'number' ? `最近 ${explicit.latest_days} 天` : '',
            ].filter(Boolean).join(' · ') || '—'}
          />
        </div>

        <div className='rounded-2xl border border-fuchsia-200/80 bg-fuchsia-50/35 p-3'>
          <div className='mb-2 text-xs font-semibold text-fuchsia-900'>
            <InfoTooltipLabel label='查询分析候选分层' tooltip='这一组是查询分析阶段的候选，不等于最终硬过滤。规则候选来自规则/词表命中；LLM 候选除了模型输出外，还会经过系统证据校验，只有能在原问题、改写问题或规则候选里找到证据的候选，才可能继续升级。' />
          </div>
          <RetrievalDebugRow
            label='规则候选 / LLM 候选 / 被纠偏规则'
            value={`${ruleCandidates.length} / ${llmCandidates.length} / ${correctedRuleCandidates.length}`}
          />
          {ruleCandidates.length > 0 ? (
            <div className='pt-2'>
              <div className='mb-2 text-[11px] font-medium text-fuchsia-900'>
                <InfoTooltipLabel label='规则候选' tooltip='规则候选由规则层直接从当前问题识别出来，通常基于标签名、别名、词表、元数据枚举等高确定性匹配。标签类规则候选只会从“当前知识库实际仍在文档/文件夹上使用中的标签”里匹配，不再扫描整个标签池。在 hybrid 模式下，这批候选会作为参考一起传给 LLM。' />
              </div>
              <RetrievalDebugJsonBlock
                value={ruleCandidates}
                maxHeightClassName='max-h-48'
                showCopyButton={false}
              />
            </div>
          ) : null}
          {correctedRuleCandidates.length > 0 ? (
            <div className='pt-2'>
              <div className='mb-2 text-[11px] font-medium text-fuchsia-900'>
                <InfoTooltipLabel label='被 LLM 纠偏的规则候选' tooltip='这部分原本来自规则层，但在 hybrid 模式下被高置信 LLM 候选判定为需要修正，所以不会再按原值继续生效。' />
              </div>
              <RetrievalDebugJsonBlock
                value={correctedRuleCandidates}
                maxHeightClassName='max-h-40'
                showCopyButton={false}
              />
            </div>
          ) : null}
          {llmCandidates.length > 0 ? (
            <div className='pt-2'>
              <div className='mb-2 text-[11px] font-medium text-fuchsia-900'>
                <InfoTooltipLabel label='LLM 候选' tooltip='这部分是 LLM 基于当前问题、规则候选、目录/标签/元数据候选池抽取出来的结构化候选。前端展示里会同时看到系统回填的 evidence_type / evidence_text / evidence_query_source，它们才是后端真正采用的证据结论；model_reason 仅作调试参考。' />
              </div>
              <RetrievalDebugJsonBlock
                value={llmCandidates}
                maxHeightClassName='max-h-48'
                showCopyButton={false}
              />
            </div>
          ) : null}
        </div>

        <div className='rounded-2xl border border-sky-200/80 bg-sky-50/35 p-3'>
          <div className='mb-2 text-xs font-semibold text-sky-900'>
            <InfoTooltipLabel label='目录候选命中（文件夹名称 / 路径）' tooltip='这里专门展示文件夹候选，方便判断是不是因为“文件夹名称、路径或目录别名”触发了范围识别。它不是最终硬过滤本身，而是查询分析阶段识别出的目录范围信号。' />
          </div>
          <RetrievalDebugRow
            label='规则 / LLM / 被纠偏'
            value={`${folderRuleCandidates.length} / ${folderLlmCandidates.length} / ${correctedFolderCandidates.length}`}
          />
          {folderRuleCandidates.length > 0 ? (
            <div className='pt-2'>
              <div className='mb-2 text-[11px] font-medium text-sky-900'>规则目录候选</div>
              <RetrievalDebugCandidateSummaryList candidates={folderRuleCandidates} emptyText='无规则目录候选' />
            </div>
          ) : null}
          {correctedFolderCandidates.length > 0 ? (
            <div className='pt-2'>
              <div className='mb-2 text-[11px] font-medium text-sky-900'>被 LLM 纠偏的目录候选</div>
              <RetrievalDebugCandidateSummaryList candidates={correctedFolderCandidates} emptyText='无被纠偏目录候选' />
            </div>
          ) : null}
          {folderLlmCandidates.length > 0 ? (
            <div className='pt-2'>
              <div className='mb-2 text-[11px] font-medium text-sky-900'>LLM 目录候选</div>
              <RetrievalDebugCandidateSummaryList candidates={folderLlmCandidates} emptyText='无 LLM 目录候选' />
            </div>
          ) : null}
          {folderRuleCandidates.length === 0 && correctedFolderCandidates.length === 0 && folderLlmCandidates.length === 0 ? (
            <div className='pt-1 text-xs text-slate-500'>当前问题未识别到文件夹名称 / 路径相关的目录候选。</div>
          ) : null}
        </div>

        <div className='rounded-2xl border border-violet-200/80 bg-violet-50/35 p-3'>
          <div className='mb-2 text-xs font-semibold text-violet-900'>
            <InfoTooltipLabel label='LLM 候选抽取' tooltip='这一块展示的是“给 LLM 做候选抽取”的链路状态。它描述 LLM 是否参与、输出了多少候选、是否生成了统一过滤表达式，以及这些输出是否通过后端的证据校验并落地。' />
          </div>
          <RetrievalDebugRow
            label='是否参与'
            value={queryAnalysis.llm_debug && Object.keys(queryAnalysis.llm_debug).length > 0 ? '是' : '否'}
          />
          {queryAnalysis.llm_debug && Object.keys(queryAnalysis.llm_debug).length > 0 ? (
            <>
              <RetrievalDebugRow label='模型' value={String(queryAnalysis.llm_debug.model || queryAnalysis.llm_debug.provider || '未标注')} />
              <RetrievalDebugRow label='最小置信度' value={String(queryAnalysis.llm_debug.min_confidence ?? '无')} />
              <RetrievalDebugRow label='候选总数' value={String(queryAnalysis.llm_debug.total_candidate_count ?? '0')} />
              <RetrievalDebugRow label='通过/拒绝/冲突' value={`${queryAnalysis.llm_debug.validated_candidate_count ?? 0}/${queryAnalysis.llm_debug.rejected_candidate_count ?? 0}/${queryAnalysis.llm_debug.conflict_candidate_count ?? 0}`} />
              <RetrievalDebugRow
                label='证据类型分布'
                value={(() => {
                  const distribution = (queryAnalysis.llm_debug.evidence_type_distribution || {}) as Record<string, any>
                  const parts = Object.entries(distribution)
                    .map(([key, value]) => `${key} ${value}`)
                  return parts.length > 0 ? parts.join(' · ') : '无'
                })()}
              />
              <RetrievalDebugRow label='升级为硬过滤' value={String(queryAnalysis.llm_debug.upgraded_candidate_count ?? 0)} />
              <RetrievalDebugRow label='纠偏规则候选' value={String(queryAnalysis.llm_debug.rule_corrected_by_llm_count ?? 0)} />
              <RetrievalDebugRow
                label={<InfoTooltipLabel label='LLM 统一过滤表达式' tooltip='这是 LLM 输出的复杂结构化过滤表达式，适合表示括号、跨字段 OR、NOT 等。它不是前端传入的高级表达式，而是 LLM 的输出；若通过校验，会在显式表达式基础上继续 AND 收紧。' /> as any}
                value={[
                  queryAnalysis.llm_debug.filter_expression_status ? `状态 ${queryAnalysis.llm_debug.filter_expression_status}` : '',
                  queryAnalysis.llm_debug.filter_expression_applied ? '已落地' : queryAnalysis.llm_debug.filter_expression ? '未落地' : '',
                  !queryAnalysis.llm_debug.filter_expression && (queryAnalysis.llm_debug.upgraded_candidate_count ?? 0) > 0 ? '表达式为空，但候选已升级为硬过滤' : '',
                  queryAnalysis.llm_debug.filter_expression_merge_mode ? `合并 ${queryAnalysis.llm_debug.filter_expression_merge_mode}` : '',
                ].filter(Boolean).join(' · ') || '无'}
              />
              {queryAnalysis.llm_debug.filter_expression ? (
                <div className='pt-2'>
                  <div className='mb-2 flex items-center justify-between gap-2 text-[11px] font-medium text-violet-900'>
                    <InfoTooltipLabel label='LLM 统一过滤表达式（标签 / 元数据）' tooltip='这里展示的是 LLM 产出的表达式原文，已经过字段/标签/目录白名单校验和归一化。若上方显示“已落地”，说明它已经参与最终检索。注意：即使这里为空，LLM 候选本身仍可能通过证据校验后直接升级为硬过滤。' />
                    <CopyJsonIconButton value={queryAnalysis.llm_debug.filter_expression} title='复制 LLM 统一过滤表达式' />
                  </div>
                  <RetrievalDebugJsonBlock
                    value={queryAnalysis.llm_debug.filter_expression}
                    maxHeightClassName='max-h-56'
                    showCopyButton={false}
                  />
                </div>
              ) : null}
              {queryAnalysis.llm_debug.parsed_output ? (
                <div className='pt-2'>
                  <div className='mb-2 flex items-center justify-between gap-2 text-[11px] font-medium text-violet-900'>
                    <InfoTooltipLabel label='LLM 原始结构化输出' tooltip='这是 LLM 返回的原始 JSON 结构化结果，包含 candidates 和可能的 filter_expression。它还不是最终结果，后端会继续做校验、冲突检查、纠偏和落地判定。' />
                    <CopyJsonIconButton value={queryAnalysis.llm_debug.parsed_output} title='复制 LLM 原始结构化输出' />
                  </div>
                  <RetrievalDebugJsonBlock
                    value={queryAnalysis.llm_debug.parsed_output}
                    maxHeightClassName='max-h-56'
                    showCopyButton={false}
                  />
                </div>
              ) : null}
            </>
          ) : null}
        </div>

        <div className='rounded-2xl border border-cyan-200/80 bg-cyan-50/35 p-3'>
          <div className='mb-2 text-xs font-semibold text-cyan-900'>
            <InfoTooltipLabel
              label='自动信号（候选层）· 标签加权 / 元数据待应用信号'
              tooltip='这里展示的是查询分析阶段生成的自动信号，还不是最终执行结果。标签信号主要用于加权；元数据信号会在后续检索阶段尝试转成实际过滤。真正已经落地的元数据过滤条件，请看下方“自动元数据过滤 · 实际落地条件”。'
            />
          </div>
          <RetrievalDebugRow
            label='信号计数'
            value={[
              `文档标签 ${filterDebug.auto_filter_signal_counts?.doc_tag ?? 0}`,
              `文件夹标签 ${filterDebug.auto_filter_signal_counts?.folder_tag ?? 0}`,
              `文档元数据 ${filterDebug.auto_filter_signal_counts?.document_metadata ?? 0}`,
              `分块元数据 ${filterDebug.auto_filter_signal_counts?.search_unit_metadata ?? 0}`,
            ].join(' · ')}
          />
          <div className='mt-3'>{renderAutoFilterSignals(autoSignals)}</div>
        </div>

        <div className='rounded-2xl border border-emerald-200/80 bg-emerald-50/35 p-3'>
          <div className='mb-2 text-xs font-semibold text-emerald-900'>自动元数据过滤（执行层）· 实际落地条件</div>
          {renderAutoMetadataDebug(filterDebug.auto_metadata_debug)}
        </div>

        <div className='rounded-2xl border border-indigo-200/70 bg-indigo-50/40 p-3'>
          <div className='mb-2 text-xs font-semibold text-indigo-800'>查询分析阶段 · 合并后的过滤结果（query_analysis.resolved_filters）</div>
          <RetrievalDebugRow label='文件夹' value={renderIdWithNameList(resolvedMerged.folder_ids, { aliasMap: folderAliasMap, detailMap: resolvedFolderMap })} />
          <RetrievalDebugRow label='文档标签' value={renderIdWithNameList(resolvedMerged.tag_ids, { aliasMap: tagAliasMap, detailMap: resolvedDocTagMap })} />
          <RetrievalDebugRow label='文件夹标签' value={renderIdWithNameList(resolvedMerged.folder_tag_ids, { aliasMap: folderTagAliasMap, detailMap: resolvedFolderTagMap })} />
          <RetrievalDebugRow label='限定 kb 文档' value={renderIdWithNameList(resolvedMerged.kb_doc_ids, { nameMap: matchedDocNameMap, detailMap: resolvedKbDocMap })} />
          <RetrievalDebugRow label='限定业务文档 ID' value={formatIdListLine(resolvedMerged.document_ids)} />
          <RetrievalDebugRow label='内容组 ID' value={formatIdListLine(resolvedMerged.content_group_ids)} />
          <RetrievalDebugRow label='文档元数据过滤' value={formatMetadataRecord(resolvedMerged.document_metadata)} textSizeClassName='text-xs break-all' />
          <RetrievalDebugRow label='搜索单元元数据过滤' value={formatMetadataRecord(resolvedMerged.search_unit_metadata)} textSizeClassName='text-xs break-all' />
          <RetrievalDebugRow
            label={<InfoTooltipLabel label='统一过滤表达式（标签 / 元数据）' tooltip='这是查询分析阶段合并出的过滤表达式。它可能来自前端/API 显式表达式，也可能叠加了 LLM 统一过滤表达式。这里表示“准备传给检索阶段”的结果，不等于数据库层最终解析后的执行形态。' /> as any}
            value={formatMetadataRecord(resolvedMerged.filter_expression)}
            textSizeClassName='text-xs break-all'
          />
          <RetrievalDebugRow
            label='目录/标签选项'
            value={[
              `含子文件夹: ${resolvedMerged.include_descendant_folders === true ? '是' : resolvedMerged.include_descendant_folders === false ? '否' : '—'}`,
              `仅已打标: ${resolvedMerged.only_tagged === true ? '是' : resolvedMerged.only_tagged === false ? '否' : '—'}`,
              typeof resolvedMerged.latest_days === 'number' ? `最近 ${resolvedMerged.latest_days} 天` : '',
            ].filter(Boolean).join(' · ') || '—'}
          />
        </div>

        <div className='rounded-2xl border border-amber-200/80 bg-amber-50/35 p-3'>
          <div className='mb-2 text-xs font-semibold text-amber-900'>检索阶段 · 最终生效的过滤条件（pipeline.resolved_filters）</div>
          <RetrievalDebugRow
            label='已应用过滤'
            value={resolvedPipeline.filter_applied === true ? '是' : resolvedPipeline.filter_applied === false ? '否' : '—'}
          />
          <RetrievalDebugRow
            label='表达式执行范围'
            value={[
              resolvedPipeline.expression_debug?.requested ? '请求包含表达式' : '未请求表达式',
              resolvedPipeline.expression_debug?.resolved ? '已归一化' : '未归一化',
              resolvedPipeline.expression_debug?.document_scope_applied ? '文档层生效' : '',
              resolvedPipeline.expression_debug?.search_unit_scope_applied ? '搜索单元层生效' : '',
            ].filter(Boolean).join(' · ') || '—'}
            textSizeClassName='text-xs break-all'
          />
          <RetrievalDebugRow
            label='最终执行表达式'
            value={formatMetadataRecord(resolvedPipeline.filter_expression)}
            textSizeClassName='text-xs break-all'
          />
          <RetrievalDebugRow label='最终命中的 kb 文档' value={renderIdWithNameList(resolvedPipeline.kb_doc_ids, { nameMap: matchedDocNameMap, detailMap: kbDocDetailMap })} />
          <RetrievalDebugRow label='最终命中的内容组' value={formatIdListLine(resolvedPipeline.content_group_ids)} />
        </div>

        <div className='rounded-2xl border border-slate-200/80 bg-white p-3'>
          <div className='mb-2 text-xs font-semibold text-slate-700'>摘要（debug_summary）</div>
          <RetrievalDebugRow label='请求计数' value={formatRequestedCounts(filterDebug.requested_filter_counts as Record<string, unknown>)} />
          <RetrievalDebugRow label='落地计数' value={formatAppliedCounts(filterDebug.applied_filter_counts as Record<string, unknown>)} />
          <RetrievalDebugRow
            label='表达式状态'
            value={[
              filterDebug.expression_debug?.requested ? '请求中有表达式' : '请求中无表达式',
              filterDebug.expression_debug?.resolved ? '已归一化' : '',
              filterDebug.expression_debug?.document_scope_applied ? '文档层已参与' : '',
              filterDebug.expression_debug?.search_unit_scope_applied ? '搜索单元层已参与' : '',
            ].filter(Boolean).join(' · ') || '—'}
          />
          <RetrievalDebugRow
            label='命中文档预览'
            value={renderMatchedDocumentPreview(filterDebug)}
            textSizeClassName='text-xs'
          />
        </div>
      </div>
    </RetrievalDebugSection>
  )
}

export function RetrievalTestResults({
  result,
  isRunning = false,
  compareResult,
  historyResults = [],
  onExportHistory,
  finalScoreThreshold,
}: RetrievalTestResultsProps) {
  const [detailItem, setDetailItem] = useState<RetrievalTestRunState['items'][number] | null>(null)
  const [globalDebugOpen, setGlobalDebugOpen] = useState(false)
  const [expandedItemIds, setExpandedItemIds] = useState<Set<string>>(new Set())
  const messageScrollRef = useRef<HTMLDivElement | null>(null)
  const hitCount = result?.items.length ?? 0
  const avgScore = hitCount > 0
    ? result!.items.reduce((sum, item) => sum + item.score, 0) / hitCount
    : 0
  const sourceCount = hitCount > 0
    ? new Set(result!.items.map((item) => item.source.document_name)).size
    : 0
  const compareItemMap = buildItemMap(compareResult?.items || [])

  const toggleExpanded = (itemId: string) => {
    setExpandedItemIds((prev) => {
      const next = new Set(prev)
      if (next.has(itemId)) {
        next.delete(itemId)
      }
      else {
        next.add(itemId)
      }
      return next
    })
  }

  const scrollToTop = () => {
    messageScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const scrollToBottom = () => {
    const container = messageScrollRef.current
    if (!container) {
      return
    }
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
  }

  return (
    <div className='flex flex-1 flex-col overflow-hidden'>
      <div className='flex items-center justify-between border-b bg-blue-50/20 p-4'>
        <div className='flex flex-col gap-2'>
          <div className='flex flex-wrap items-center gap-2'>
          <Badge variant='outline' className='py-0 text-[10px] uppercase tracking-widest'>
            {isRunning ? '检索进行中' : result ? `Top ${hitCount} 条结果` : '待检索'}
          </Badge>
          <span className='mr-1 text-xs text-muted-foreground'>
            {isRunning ? '正在执行召回、融合与重排，请稍候...' : result ? `耗时: ${result.elapsedMs}ms` : '输入问题后开始检索'}
          </span>
          {result && hitCount > 0 && (
            <>
              <div className='inline-flex items-center gap-1 rounded-full border bg-background/80 px-2 py-0.5 text-[10px] text-muted-foreground'>
                <span>结果条数</span>
                <span className='font-mono text-foreground'>{hitCount}</span>
              </div>
              <div className='inline-flex items-center gap-1 rounded-full border bg-background/80 px-2 py-0.5 text-[10px] text-muted-foreground'>
                <span>命中文档</span>
                <span className='font-mono text-foreground'>{sourceCount}</span>
              </div>
              <div className='inline-flex items-center gap-1 rounded-full border bg-background/80 px-2 py-0.5 text-[10px] text-muted-foreground'>
                <span>平均最终分</span>
                <span className='font-mono text-foreground'>{avgScore.toFixed(2)}</span>
              </div>
            </>
          )}
          </div>
        </div>
        <div className='flex items-center gap-2'>
          <Button
            type='button'
            variant='default'
            size='sm'
            className='h-8 gap-1.5 border border-blue-600 bg-blue-600 text-xs text-white shadow-sm hover:bg-blue-700'
            onClick={() => setGlobalDebugOpen(true)}
            disabled={!result}
            title='查看查询级诊断（改写、过滤、召回、全局结果）'
          >
            全局诊断（查询级）
          </Button>
          <Button
            type='button'
            variant='outline'
            size='sm'
            className='h-8 gap-1.5 text-xs'
            onClick={onExportHistory}
            disabled={!result && historyResults.length === 0}
          >
            <Download className='h-3.5 w-3.5' />
            导出记录
          </Button>
        </div>
      </div>

      <div ref={messageScrollRef} className='relative flex-1 overflow-y-auto p-6'>
        <div className='mx-auto w-full max-w-6xl space-y-4'>

          {isRunning ? (
            <div className='space-y-4'>
              <div className='rounded-3xl border border-cyan-200/70 bg-gradient-to-br from-cyan-50 via-white to-blue-50/70 p-5 shadow-sm'>
                <div className='flex items-center gap-3'>
                  <div className='flex h-10 w-10 items-center justify-center rounded-2xl bg-cyan-100 text-cyan-700'>
                    <Loader2 className='h-5 w-5 animate-spin' />
                  </div>
                  <div className='space-y-1'>
                    <div className='text-sm font-semibold text-cyan-800'>正在检索与重排结果</div>
                    <div className='text-xs text-muted-foreground'>内容区会在结果返回后自动更新，请耐心等待。</div>
                  </div>
                </div>
              </div>
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={`retrieval-loading-${index}`}
                  className='animate-pulse space-y-4 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm'
                >
                  <div className='flex items-start justify-between gap-4'>
                    <div className='flex-1 space-y-3'>
                      <div className='h-4 w-48 rounded-full bg-slate-200/80' />
                      <div className='flex gap-2'>
                        <div className='h-6 w-24 rounded-full bg-slate-200/80' />
                        <div className='h-6 w-20 rounded-full bg-slate-200/70' />
                        <div className='h-6 w-20 rounded-full bg-slate-200/70' />
                      </div>
                    </div>
                    <div className='h-8 w-24 rounded-full bg-slate-200/80' />
                  </div>
                  <div className='space-y-2'>
                    <div className='h-3 w-full rounded-full bg-slate-200/70' />
                    <div className='h-3 w-11/12 rounded-full bg-slate-200/70' />
                    <div className='h-3 w-8/12 rounded-full bg-slate-200/70' />
                  </div>
                  <div className='flex gap-2'>
                    <div className='h-5 w-16 rounded-full bg-slate-200/70' />
                    <div className='h-5 w-20 rounded-full bg-slate-200/70' />
                    <div className='h-5 w-24 rounded-full bg-slate-200/70' />
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {!isRunning && result && result.items.length > 0 ? (
            result.items.map((item) => {
              const itemId = String(item.id)
              const isExpanded = expandedItemIds.has(itemId)
              const badgeMeta = getResultBadgeMeta(item.score, finalScoreThreshold)
              const previousItem = compareItemMap.get(String(item.id))
              const itemDiffBadge = getScoreDeltaMeta(item.score, previousItem?.score)
              const strategySummary = buildResultStrategySummary((item.metadata || {}) as Record<string, any>)
              const resultUnitBadge = getResultUnitBadgeMeta(item.metadata?.result_unit_kind)
              const effectiveKeywordScore = resolveEffectiveKeywordScore(item)
              const scoreTrace = (item.metadata?.score_trace || {}) as Record<string, any>
              const hitScoreDetails = Array.isArray(item.metadata?.hit_score_details) ? item.metadata.hit_score_details : []
              const cardClassName = previousItem
                ? 'space-y-4 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-lg'
                : 'space-y-4 rounded-3xl border border-cyan-200/80 bg-gradient-to-br from-cyan-50 via-white to-amber-50/60 p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-cyan-300 hover:shadow-lg'

              return (
                <div key={item.id} className={cardClassName}>
                  <div className='flex items-start justify-between gap-4'>
                    <div className='space-y-1'>
                      <div className='flex items-center gap-2 text-xs'>
                        <span className='rounded bg-primary/10 px-2 py-0.5 font-bold text-primary'>
                          #{String(item.rank).padStart(2, '0')}
                        </span>
                        <span className='font-semibold'>{item.title}</span>
                        <Badge variant='outline' className={resultUnitBadge.className}>
                          {resultUnitBadge.label}
                        </Badge>
                      </div>
                      {strategySummary ? (
                        <div className='text-[11px] text-muted-foreground'>
                          {strategySummary}
                        </div>
                      ) : null}
                      <div className='flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]'>
                        <span className='inline-flex items-center rounded-full bg-blue-50 px-2.5 py-1 text-blue-700'>
                          <span className='text-muted-foreground/80'>综合得分</span>
                          <span className='ml-1.5 font-mono text-[12px] font-semibold text-blue-700'>{item.score.toFixed(2)}</span>
                        </span>
                        <span className='text-muted-foreground'>
                          向量相似度
                          <span className='ml-1 font-mono text-foreground'>
                            {typeof item.vector_score === 'number' ? item.vector_score.toFixed(2) : '--'}
                          </span>
                        </span>
                        <span className='text-muted-foreground'>
                          全文相关性
                          <span className='ml-1 font-mono text-foreground'>
                            {formatRetrievalDebugNumber(effectiveKeywordScore)}
                          </span>
                        </span>
                        <span className='text-muted-foreground'>
                          块 ID
                          <span className='ml-1 font-mono text-foreground'>
                            {String(item.metadata?.context_unit_id || item.source.chunk_id || '--')}
                          </span>
                        </span>
                        <span className='text-muted-foreground'>
                          Token
                          <span className='ml-1 font-mono text-foreground'>
                            {String(item.metadata?.context_unit_token_count ?? '--')}
                          </span>
                        </span>
                      </div>
                      {(typeof item.metadata?.lexical_raw_score === 'number'
                        || typeof item.metadata?.lexical_structured_score === 'number'
                        || typeof scoreTrace.fusion_score === 'number'
                        || typeof scoreTrace.rerank_score === 'number') ? (
                        <div className='flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground'>
                          {typeof item.metadata?.lexical_raw_score === 'number' ? (
                            <span>全文原始分 <span className='font-mono text-foreground'>{item.metadata.lexical_raw_score.toFixed(2)}</span></span>
                          ) : null}
                          {typeof item.metadata?.lexical_structured_score === 'number' ? (
                            <span>QA 词面分 <span className='font-mono text-foreground'>{item.metadata.lexical_structured_score.toFixed(2)}</span></span>
                          ) : null}
                          {typeof scoreTrace.fusion_score === 'number' ? (
                            <span>融合分 <span className='font-mono text-foreground'>{scoreTrace.fusion_score.toFixed(2)}</span></span>
                          ) : null}
                          {typeof scoreTrace.rerank_overlap === 'number' ? (
                            <span>重排重合度 <span className='font-mono text-foreground'>{scoreTrace.rerank_overlap.toFixed(2)}</span></span>
                          ) : null}
                          {typeof scoreTrace.rerank_score === 'number' ? (
                            <span>重排后 <span className='font-mono text-foreground'>{scoreTrace.rerank_score.toFixed(2)}</span></span>
                          ) : null}
                          {typeof scoreTrace.auto_tag_boost === 'number' && scoreTrace.auto_tag_boost > 0 ? (
                            <span>标签加权 <span className='font-mono text-foreground'>{scoreTrace.auto_tag_boost.toFixed(2)}</span></span>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    <div className='flex flex-col items-end gap-2'>
                      <Button
                        type='button'
                        variant='ghost'
                        size='sm'
                        className='h-7 rounded-full px-2 text-[11px] text-muted-foreground hover:text-foreground'
                        onClick={() => toggleExpanded(itemId)}
                      >
                        {isExpanded ? <ChevronUp className='mr-1.5 h-3.5 w-3.5' /> : <ChevronDown className='mr-1.5 h-3.5 w-3.5' />}
                        {isExpanded ? '收起全文' : '展开全文'}
                      </Button>
                      <Button
                        type='button'
                        variant='outline'
                        size='sm'
                        className='h-7 rounded-full border-blue-200 bg-white/80 px-3 text-[11px] text-blue-700 shadow-sm transition-colors hover:bg-blue-50'
                        onClick={() => setDetailItem(item)}
                        title='查看当前命中项的评分拆解与上下文细节'
                      >
                        分块诊断（本条）
                      </Button>
                      <div className='flex items-center gap-2'>
                      <Badge className={badgeMeta.className}>{badgeMeta.label}</Badge>
                      <Badge className={itemDiffBadge.className}>{itemDiffBadge.label}</Badge>
                      </div>
                    </div>
                  </div>

                  <p className={`${isExpanded ? '' : 'line-clamp-3'} text-sm leading-relaxed text-muted-foreground transition-all`}>
                    {getResultPreviewText(item)}
                  </p>

                  <div className='flex flex-wrap items-center gap-2 pt-2'>
                    {item.tags.map((tag) => (
                      <Badge key={tag} variant='secondary' className='py-0 text-[9px]'>
                        #{tag}
                      </Badge>
                    ))}
                    {Array.isArray(item.metadata?.matched_scopes) ? (
                      <span className='text-[10px] text-muted-foreground'>
                        命中投影: {item.metadata.matched_scopes.join(' / ')}
                      </span>
                    ) : null}
                    {item.metadata?.doc_summary_hit ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        摘要辅路
                      </Badge>
                    ) : null}
                    {item.metadata?.chunk_topology_type ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        块类型: {getChunkTopologyTypeLabel(item.metadata.chunk_topology_type)}
                      </Badge>
                    ) : null}
                    {item.metadata?.kb_type === 'table' && Array.isArray(item.metadata?.dimension_field_names) && item.metadata.dimension_field_names.length > 0 ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        维度: {item.metadata.dimension_field_names.slice(0, 3).join(' / ')}
                      </Badge>
                    ) : null}
                    {item.metadata?.kb_type === 'table' && Array.isArray(item.metadata?.metric_field_names) && item.metadata.metric_field_names.length > 0 ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        指标: {item.metadata.metric_field_names.slice(0, 3).join(' / ')}
                      </Badge>
                    ) : null}
                    {Number(item.metadata?.strategy_contributions?.query_intent_bonus || 0) > 0 ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        意图加权
                      </Badge>
                    ) : null}
                    {Number(item.metadata?.strategy_contributions?.metadata_bonus || 0) > 0 ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        字段加权
                      </Badge>
                    ) : null}
                    {Number(item.metadata?.strategy_contributions?.auto_tag_boost || 0) > 0 ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        标签加权
                      </Badge>
                    ) : null}
                    {Number(item.metadata?.strategy_contributions?.repeated_hit_bonus || 0) > 0 ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        重复命中加权
                      </Badge>
                    ) : null}
                    {!previousItem && compareResult ? (
                      <Badge variant='outline' className='py-0 text-[9px]'>
                        对比轮次未命中
                      </Badge>
                    ) : null}
                    <span className='text-[10px] text-muted-foreground'>
                      来源: {item.source.document_name}
                      {item.source.page_numbers && item.source.page_numbers.length > 0
                        ? ` · 第 ${item.source.page_numbers.join(', ')} 页`
                        : ''}
                    </span>
                  </div>
                  {hitScoreDetails.length > 0 ? (
                    <div className='rounded-xl border border-dashed bg-background/60 px-3 py-2 text-[10px] text-muted-foreground'>
                      {hitScoreDetails.slice(0, 4).map((detail, index) => {
                        const backendType = String(detail?.backend_type || '').trim()
                        const searchScope = String(detail?.search_scope || '').trim()
                        const score = typeof detail?.score === 'number' ? detail.score.toFixed(2) : '--'
                        const lexicalRaw = typeof detail?.lexical_raw_score === 'number' ? detail.lexical_raw_score.toFixed(2) : ''
                        const lexicalStructured = typeof detail?.lexical_structured_score === 'number' ? detail.lexical_structured_score.toFixed(2) : ''
                        return (
                          <div key={`${item.id}-${backendType}-${searchScope}-${index}`}>
                            {`${backendType || 'unknown'} / ${searchScope || 'unknown'}: ${score}`}
                            {lexicalRaw ? ` · 原始全文 ${lexicalRaw}` : ''}
                            {lexicalStructured ? ` · 结构化全文 ${lexicalStructured}` : ''}
                          </div>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              )
            })
          ) : (
            <div className='flex flex-col items-center justify-center py-24 text-muted-foreground'>
              <Search className='mb-4 h-14 w-14 stroke-1 opacity-40' />
              <p className='text-sm'>还没有检索结果</p>
              <p className='mt-2 text-xs opacity-70'>先输入测试问题，再点击右下角开始检索。</p>
            </div>
          )}
        </div>
        <div className='pointer-events-none sticky bottom-4 z-20 mt-4 flex justify-end gap-2'>
          <Button
            type='button'
            variant='outline'
            size='icon'
            className='pointer-events-auto h-9 w-9 rounded-full border-blue-200 bg-white/95 text-blue-700 shadow-md hover:bg-blue-50'
            onClick={scrollToTop}
            aria-label='快速回到顶部'
            title='回到顶部'
          >
            <ArrowUpToLine className='h-4 w-4' />
          </Button>
          <Button
            type='button'
            variant='outline'
            size='icon'
            className='pointer-events-auto h-9 w-9 rounded-full border-blue-200 bg-white/95 text-blue-700 shadow-md hover:bg-blue-50'
            onClick={scrollToBottom}
            aria-label='快速跳到底部'
            title='到底部'
          >
            <ArrowDownToLine className='h-4 w-4' />
          </Button>
        </div>
      </div>
      <RetrievalDebugDrawer
        item={detailItem}
        result={result}
        open={Boolean(detailItem)}
        onOpenChange={(open) => {
          if (!open) {
            setDetailItem(null)
          }
        }}
      />
      <RetrievalGlobalDebugDrawer
        result={result}
        open={globalDebugOpen}
        onOpenChange={setGlobalDebugOpen}
      />
    </div>
  )
}

function RetrievalDebugDrawer({
  item,
  result,
  open,
  onOpenChange,
}: {
  item: RetrievalTestRunState['items'][number] | null
  result: RetrievalTestRunState | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const debug = (result?.debug || {}) as Record<string, any>
  const pipelineTrace = (debug.pipeline_trace || {}) as Record<string, any>
  const traceRetrieval = (pipelineTrace.retrieval || {}) as Record<string, any>
  const traceResults = (pipelineTrace.results || {}) as Record<string, any>
  const traceItem = Array.isArray(traceResults.items)
    ? traceResults.items.find((current: Record<string, any>) => String(current?.id) === String(item?.id))
    : null
  const metadata = (item?.metadata || {}) as Record<string, any>
  const effectiveKeywordScore = resolveEffectiveKeywordScore(item)
  const scoreTrace = (metadata.score_trace || {}) as Record<string, any>
  const autoTagBoostDebug = (metadata.auto_tag_boost_debug || scoreTrace.auto_tag_boost_debug || {}) as Record<string, any>
  const hitDetails = Array.isArray(metadata.hit_score_details) ? metadata.hit_score_details : []
  const lexicalCandidates = Array.isArray(metadata.lexical_structured_candidates)
    ? metadata.lexical_structured_candidates
    : []
  const { rawHitChunk, contextUnit, llmContext } = getDebugContentViews(item)
  const contextUnitContent = String(contextUnit.content || item?.content || metadata.context_unit_content || metadata.display_chunk_content || metadata.full_result_content || '')
  const rawHitContent = String(rawHitChunk.content || metadata.raw_hit_chunk_content || '')
  const llmContextContent = String(llmContext.content || metadata.llm_context_content || item?.content || '')
  const contextUnitTokenCount = contextUnit.token_count ?? metadata.context_unit_token_count
  const rawHitTokenCount = rawHitChunk.token_count ?? metadata.raw_hit_chunk_token_count
  const llmContextTokenCount = llmContext.token_count ?? metadata.llm_context_token_count
  const selectedTone = getSelectedResultTone(item?.score)

  return (
    <RetrievalDebugSheet
      open={open}
      onOpenChange={onOpenChange}
      title='分块诊断详情'
      description='仅针对当前选中结果分块的评分、命中与上下文拼装信息。'
      widthClassName='sm:max-w-[760px]'
    >
        <div className='space-y-4 p-5'>
          <div className={selectedTone.cardClassName}>
            <div className={`text-xs uppercase tracking-[0.2em] ${selectedTone.labelClassName}`}>Selected Result</div>
            <div className='mt-2 text-lg font-semibold text-slate-900'>{item?.title || '未选择结果'}</div>
            <p className='mt-3 text-sm leading-6 text-slate-600'>{getResultPreviewText(item)}</p>
            <div className='mt-4 grid grid-cols-3 gap-3'>
              <RetrievalDebugStat label='综合得分' value={item?.score} tone='cyan' />
              <RetrievalDebugStat label='向量相似度' value={item?.vector_score} tone='emerald' />
              <RetrievalDebugStat label='全文相关性' value={effectiveKeywordScore} tone='amber' />
            </div>
          </div>

          <RetrievalDebugSection title='评分拆解'>
            <div className='grid gap-3 sm:grid-cols-2'>
              <RetrievalDebugMetricCard title='融合阶段' lines={[
                `融合分: ${formatRetrievalDebugNumber(scoreTrace.fusion_score ?? scoreTrace.final_score)}`,
                `全文相关性: ${formatRetrievalDebugNumber(effectiveKeywordScore)}`,
                `scope 权重: ${formatRetrievalDebugNumber(scoreTrace.scope_weight)}`,
                `重复命中奖励: ${formatRetrievalDebugNumber(scoreTrace.repeated_hit_bonus)}`,
                `意图奖励: ${formatRetrievalDebugNumber(scoreTrace.query_intent_bonus)}`,
                `元数据奖励: ${formatRetrievalDebugNumber(scoreTrace.metadata_bonus)}`,
                `标签加权: ${formatRetrievalDebugNumber(scoreTrace.auto_tag_boost)}`,
              ]} />
              <RetrievalDebugMetricCard title='重排阶段' lines={[
                `模型: ${String(scoreTrace.rerank_model || metadata.rerank_model || '未启用')}`,
                `重排重合度: ${formatRetrievalDebugNumber(scoreTrace.rerank_overlap ?? metadata.rerank_overlap)}`,
                `重排后分: ${formatRetrievalDebugNumber(scoreTrace.rerank_score)}`,
                `对比文本: ${String(metadata.rerank_text_preview || '无')}`,
              ]} />
            </div>
          </RetrievalDebugSection>

          <RetrievalDebugSection title='标签与元数据命中'>
            <div className='grid gap-3 sm:grid-cols-2'>
              <RetrievalDebugMetricCard
                title='自动标签加权'
                lines={Object.keys(autoTagBoostDebug).length > 0 ? buildAutoTagBoostLines(autoTagBoostDebug) : ['本条结果没有自动标签加权']}
              />
              <RetrievalDebugMetricCard title='过滤型元数据说明' lines={[
                '自动元数据只用于过滤，不参与加分',
                `非过滤字段加权: ${formatRetrievalDebugNumber(scoreTrace.metadata_bonus)}`,
                `匹配投影: ${Array.isArray(metadata.matched_scopes) ? metadata.matched_scopes.join(' / ') : '无'}`,
              ]} />
            </div>
          </RetrievalDebugSection>

          <RetrievalDebugSection title='结果归并'>
            <div className='grid gap-3 sm:grid-cols-2'>
              <RetrievalDebugMetricCard title='分组策略' lines={[
                `当前策略: ${getGroupingStrategyLabel(metadata.grouping_strategy)}`,
                `业务聚合开关: ${metadata.group_by_content_group ? '开启' : '关闭'}`,
                `content_group_id: ${String(metadata.content_group_id || '无')}`,
              ]} />
              <RetrievalDebugMetricCard title='层级策略' lines={[
                `层级召回: ${getHierarchicalModeLabel(metadata.hierarchical_retrieval_mode)}`,
                `结果来源: ${getResultUnitKindLabel(metadata.result_unit_kind)}`,
                `块类型: ${getChunkTopologyTypeLabel(metadata.chunk_topology_type)}`,
                `邻近块补充: ${String(metadata.neighbor_window_size ?? '0')}`,
                `父块 ID: ${String(metadata.parent_chunk_id || '无')}`,
              ]} />
            </div>
          </RetrievalDebugSection>

          <RetrievalDebugSection title='最终上下文块'>
            <div className='rounded-2xl border border-slate-200/90 bg-gradient-to-b from-white to-slate-50/70 p-4 text-sm leading-6 text-slate-700 whitespace-pre-wrap break-words'>
              {contextUnitContent || '暂无最终上下文块内容'}
            </div>
            <div className='mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2'>
              <span>context_unit_id: {String(contextUnit.chunk_id || metadata.context_unit_id || metadata.display_chunk_id || '无')}</span>
              <span>结果单元类型: {getResultUnitKindLabel(metadata.result_unit_kind)}</span>
              <span>token 数: {String(contextUnitTokenCount ?? '无')}</span>
              <span>字符数: {String(contextUnit.text_length ?? '无')}</span>
            </div>
          </RetrievalDebugSection>

          <RetrievalDebugSection title='原始命中分块'>
            <div className='rounded-2xl border border-slate-200/90 bg-gradient-to-b from-white to-slate-50/70 p-4 text-sm leading-6 text-slate-700 whitespace-pre-wrap break-words'>
              {rawHitContent || '当前结果没有记录原始命中分块内容'}
            </div>
            <div className='mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2'>
              <span>raw_hit_chunk_id: {String(rawHitChunk.chunk_id || metadata.raw_hit_chunk_id || '无')}</span>
              <span>块类型: {getChunkTopologyTypeLabel(rawHitChunk.topology_type)}</span>
              <span>parent_chunk_id: {String(rawHitChunk.parent_chunk_id || metadata.parent_chunk_id || '无')}</span>
              <span>token 数: {String(rawHitTokenCount ?? '无')}</span>
            </div>
          </RetrievalDebugSection>

          <RetrievalDebugSection title='传给 LLM 的最终上下文'>
            <div className='rounded-2xl border border-slate-200/90 bg-gradient-to-b from-white to-slate-50/70 p-4 text-sm leading-6 text-slate-700 whitespace-pre-wrap break-words'>
              {llmContextContent || '暂无 LLM 上下文内容'}
            </div>
            <div className='mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2'>
              <span>来源块: {String(llmContext.source_chunk_id || contextUnit.chunk_id || metadata.context_unit_id || '无')}</span>
              <span>组装策略: {String(llmContext.assembly_strategy || metadata.result_unit_kind || 'direct_chunk')}</span>
              <span>包含父块: {llmContext.includes_parent ? '是' : '否'}</span>
              <span>包含邻近块: {llmContext.includes_neighbors ? '是' : '否'}</span>
              <span>token 数: {String(llmContextTokenCount ?? '无')}</span>
              <span>字符数: {String(llmContext.text_length ?? '无')}</span>
            </div>
          </RetrievalDebugSection>

          <RetrievalDebugSection title='命中明细'>
            {hitDetails.length > 0 ? (
              <div className='space-y-2'>
                {hitDetails.map((detail, index) => (
                  <div key={`${String(detail?.backend_type || 'hit')}-${index}`} className='rounded-2xl border border-slate-200/90 bg-gradient-to-b from-white to-slate-50/80 p-3'>
                    <div className='flex items-center justify-between gap-3'>
                      <div className='text-sm font-medium text-slate-800'>
                        {String(detail?.backend_type || 'unknown')} / {String(detail?.search_scope || 'unknown')}
                      </div>
                      <div className='font-mono text-sm text-cyan-700'>{formatRetrievalDebugNumber(detail?.score)}</div>
                    </div>
                    <div className='mt-2 grid gap-2 text-xs text-slate-500 sm:grid-cols-2'>
                      <span>原始全文: {formatRetrievalDebugNumber(resolveHitDetailLexicalScore(detail))}</span>
                      <span>结构化全文: {formatRetrievalDebugNumber(detail?.lexical_structured_score)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className='text-sm text-slate-500'>当前结果没有命中明细。</div>
            )}
          </RetrievalDebugSection>

          <RetrievalDebugSection title='QA 结构化全文候选'>
            {lexicalCandidates.length > 0 ? (
              <div className='space-y-2'>
                {lexicalCandidates.map((candidate, index) => (
                  <div key={`${String(candidate?.query_source || 'candidate')}-${index}`} className='rounded-2xl border border-slate-200/90 bg-gradient-to-b from-white to-slate-50/80 p-3 text-xs text-slate-700'>
                    <div className='flex items-center justify-between gap-3'>
                      <span>{String(candidate?.query_source || 'unknown')}</span>
                      <span className='font-mono text-amber-700'>{formatRetrievalDebugNumber(candidate?.score)}</span>
                    </div>
                    <div className='mt-2 break-all text-slate-500'>{String(candidate?.normalized_query || '')}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className='text-sm text-slate-500'>当前没有 QA 结构化全文候选。</div>
            )}
          </RetrievalDebugSection>

          <RetrievalDebugSection title='召回概览'>
            <div className='grid gap-3 sm:grid-cols-3'>
              <RetrievalDebugStat label='向量召回' value={traceRetrieval.vector_hit_count} tone='emerald' />
              <RetrievalDebugStat label='全文召回' value={traceRetrieval.lexical_hit_count} tone='amber' />
              <RetrievalDebugStat label='结果数' value={traceResults.item_count} tone='cyan' />
            </div>
          </RetrievalDebugSection>

          <RetrievalDebugSection
            title='分块原始调试 JSON'
            headerAction={
              <CopyJsonActionButton
                value={{
                  item,
                  trace_item: traceItem,
                  score_trace: scoreTrace,
                  auto_tag_boost_debug: autoTagBoostDebug,
                  hit_score_details: hitDetails,
                  raw_hit_chunk: rawHitChunk,
                  context_unit: contextUnit,
                  llm_context: llmContext,
                }}
              />
            }
          >
            <RetrievalDebugJsonBlock
              value={{
                item,
                trace_item: traceItem,
                score_trace: scoreTrace,
                auto_tag_boost_debug: autoTagBoostDebug,
                hit_score_details: hitDetails,
                raw_hit_chunk: rawHitChunk,
                context_unit: contextUnit,
                llm_context: llmContext,
              }}
              maxHeightClassName='max-h-72'
              showCopyButton={false}
            />
          </RetrievalDebugSection>
        </div>
    </RetrievalDebugSheet>
  )
}

function RetrievalGlobalDebugDrawer({
  result,
  open,
  onOpenChange,
}: {
  result: RetrievalTestRunState | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryAnalysis = (result?.queryAnalysis || {}) as Record<string, any>
  const debug = (result?.debug || {}) as Record<string, any>
  const pipelineTrace = (debug.pipeline_trace || {}) as Record<string, any>
  const traceInput = (pipelineTrace.input || {}) as Record<string, any>
  const traceRetrieval = (pipelineTrace.retrieval || {}) as Record<string, any>
  const traceResults = (pipelineTrace.results || {}) as Record<string, any>
  const queryRewriteDebug = (queryAnalysis.query_rewrite_debug || {}) as Record<string, any>
  const standaloneQuestion = String(traceInput.standalone_query || queryAnalysis.standalone_query || queryAnalysis.raw_query || '与原始问题相同')
  const normalizedRetrievalQuestion = String(
    traceInput.rewritten_query || queryAnalysis.rewritten_query || queryAnalysis.standalone_query || '与原始问题相同'
  )
  const lexicalQueryText = String(traceInput.lexical_query || queryAnalysis.lexical_query || '无')
  const synonymSummary = Array.isArray(queryAnalysis.synonym_matches)
    ? queryAnalysis.synonym_matches
        .slice(0, 5)
        .map((item: Record<string, any>) => {
          const userTerm = String(item?.user_term || '').trim()
          const professionalTerm = String(item?.professional_term || '').trim()
          return userTerm && professionalTerm ? `${userTerm} -> ${professionalTerm}` : ''
        })
        .filter(Boolean)
        .join('；')
    : ''

  return (
    <RetrievalDebugSheet
      open={open}
      onOpenChange={onOpenChange}
      title='全局查询诊断'
      description='聚焦本轮查询级链路：改写、过滤、召回与结果汇总，不包含单条分块细节。'
      widthClassName='sm:max-w-[720px]'
    >
      <div className='space-y-4 p-5'>
        {result ? (
          <>
            <RetrievalDebugSection title='查询级输入链路'>
              <RetrievalDebugRow label='原始输入' value={String(traceInput.raw_query || queryAnalysis.raw_query || result.executedQuery || '无')} />
            </RetrievalDebugSection>

            <RetrievalDebugSection title='查询理解与改写'>
              <RetrievalDebugRow label='是否改写' value={traceInput.query_rewritten ? '是' : '否'} />
              <RetrievalDebugRow label='改写状态' value={String(queryRewriteDebug.status || (queryAnalysis.standalone_query && queryAnalysis.standalone_query !== queryAnalysis.raw_query ? 'success' : 'disabled'))} />
              <RetrievalDebugRow label='改写后的独立问题' value={standaloneQuestion} />
              <RetrievalDebugRow label='归一化后的检索问题' value={normalizedRetrievalQuestion} />
              <RetrievalDebugRow label='最终全文检索查询串' value={lexicalQueryText} />
              <RetrievalDebugRow label='同义词改写' value={synonymSummary || '未命中'} />
              <RetrievalDebugRow label='改写原因' value={String(queryRewriteDebug.rewrite_reason || '—')} />
              <RetrievalDebugRow label='历史上下文数' value={String(queryRewriteDebug.history_count ?? 0)} />
              <RetrievalDebugRow label='目录建议' value={queryRewriteDebug.folder_routing_enabled ? '启用' : queryRewriteDebug.enabled ? '未启用' : '未启用'} />
              <RetrievalDebugRow
                label='主 / 次目录候选'
                value={`${Array.isArray(queryRewriteDebug.folder_routing_hints?.primary_folder_candidates) ? queryRewriteDebug.folder_routing_hints.primary_folder_candidates.length : 0} / ${Array.isArray(queryRewriteDebug.folder_routing_hints?.secondary_folder_candidates) ? queryRewriteDebug.folder_routing_hints.secondary_folder_candidates.length : 0}`}
              />
            </RetrievalDebugSection>

            <CategorizedSearchTerms queryAnalysis={queryAnalysis} debug={debug} />

            <FilterTraceDebugSection debug={debug} queryAnalysis={queryAnalysis} />

            <RetrievalDebugSection title='全局召回与结果'>
              <div className='grid gap-3 sm:grid-cols-3'>
                <RetrievalDebugStat label='向量召回' value={traceRetrieval.vector_hit_count} tone='emerald' />
                <RetrievalDebugStat label='全文召回' value={traceRetrieval.lexical_hit_count} tone='amber' />
                <RetrievalDebugStat label='最终结果数' value={traceResults.item_count ?? result.items.length} tone='cyan' />
              </div>
            </RetrievalDebugSection>

            <RetrievalDebugSection
              title='全局原始调试 JSON'
              headerAction={<CopyJsonActionButton value={{ query_analysis: queryAnalysis, pipeline_trace: pipelineTrace }} />}
            >
              <RetrievalDebugJsonBlock value={{ query_analysis: queryAnalysis, pipeline_trace: pipelineTrace }} maxHeightClassName='max-h-96' showCopyButton={false} />
            </RetrievalDebugSection>
          </>
        ) : (
          <RetrievalDebugSection title='全局查询诊断'>
            <div className='text-sm text-slate-500'>暂无可展示的查询结果，请先执行一次检索或切换到历史轮次。</div>
          </RetrievalDebugSection>
        )}
      </div>
    </RetrievalDebugSheet>
  )
}
