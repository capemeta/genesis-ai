import type { ReactNode } from 'react'
import { Copy } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'

type RetrievalDebugTone = 'cyan' | 'emerald' | 'amber'

export function RetrievalDebugSheet({
  open,
  onOpenChange,
  title,
  description,
  widthClassName = 'sm:max-w-[760px]',
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  widthClassName?: string
  children: ReactNode
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side='right' className={`w-[min(96vw,820px)] overflow-y-auto bg-gradient-to-b from-slate-100 via-slate-50 to-slate-100 p-0 text-slate-900 ${widthClassName}`}>
        <div className='sticky top-0 z-10 border-b border-slate-200/80 bg-white/95 px-5 py-2.5 shadow-sm backdrop-blur'>
          <SheetHeader className='space-y-1 text-left'>
            <SheetTitle className='text-base font-semibold tracking-tight text-slate-900'>{title}</SheetTitle>
            <SheetDescription className='text-xs text-slate-500'>{description}</SheetDescription>
          </SheetHeader>
        </div>
        {children}
      </SheetContent>
    </Sheet>
  )
}

export function RetrievalDebugSection({
  title,
  headerAction,
  children,
  className = '',
}: {
  title: ReactNode
  headerAction?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-3xl border border-slate-200/90 bg-white p-4 shadow-sm shadow-slate-200/50 ${className}`}>
      <div className='mb-3 flex items-center justify-between gap-3'>
        <div className='text-sm font-semibold tracking-tight text-slate-900'>{title}</div>
        {headerAction}
      </div>
      {children}
    </section>
  )
}

export function RetrievalDebugRow({
  label,
  value,
  labelWidthClassName = 'sm:grid-cols-[120px_1fr]',
  textSizeClassName = 'text-sm',
}: {
  label: string
  value: ReactNode
  labelWidthClassName?: string
  textSizeClassName?: string
}) {
  return (
    <div className={`grid gap-1 border-b border-slate-200/70 py-2 last:border-0 ${labelWidthClassName} ${textSizeClassName}`}>
      <span className='text-slate-500'>{label}</span>
      <span className='break-all text-slate-800'>{value}</span>
    </div>
  )
}

export function RetrievalDebugMetricCard({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className='rounded-2xl border border-slate-200/90 bg-gradient-to-b from-white to-slate-50/70 p-4'>
      <div className='mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500'>{title}</div>
      <div className='space-y-1 text-xs leading-5 text-slate-700'>
        {lines.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>
    </div>
  )
}

export function RetrievalDebugStat({
  label,
  value,
  tone,
  compact = false,
}: {
  label: string
  value: unknown
  tone: RetrievalDebugTone
  compact?: boolean
}) {
  const toneClass = {
    cyan: 'from-cyan-50 via-cyan-50 to-white text-cyan-800 border-cyan-200/80',
    emerald: 'from-emerald-50 via-emerald-50 to-white text-emerald-800 border-emerald-200/80',
    amber: 'from-amber-50 via-amber-50 to-white text-amber-800 border-amber-200/80',
  }[tone]

  return (
    <div className={`rounded-2xl border bg-gradient-to-br ${toneClass} ${compact ? 'px-3 py-2' : 'p-3'}`}>
      <div className='text-[10px] uppercase tracking-[0.18em] opacity-70'>{label}</div>
      <div className={`${compact ? 'text-sm' : 'text-lg'} mt-1 font-mono font-semibold`}>{formatRetrievalDebugNumber(value)}</div>
    </div>
  )
}

export function RetrievalHitList({
  title,
  hits,
  maxItems,
}: {
  title: string
  hits: Array<Record<string, any>>
  maxItems?: number
}) {
  const visibleHits = typeof maxItems === 'number' ? hits.slice(0, maxItems) : hits

  return (
    <div className='space-y-2'>
      <div className='text-xs font-semibold uppercase tracking-[0.18em] text-slate-500'>{title}</div>
      {visibleHits.map((hit, index) => (
        <div key={`${title}-${String(hit.search_unit_id || hit.id || index)}`} className='rounded-2xl border border-slate-200 bg-slate-50/80 p-3 text-xs text-slate-700'>
          <div className='flex items-center justify-between gap-3'>
            <span>{String(hit.search_scope || hit.vector_scope || 'unknown')}</span>
            <span className='font-mono text-cyan-700'>{formatRetrievalDebugNumber(hit.score)}</span>
          </div>
          {hit.question_text ? <div className='mt-2 break-all text-slate-500'>问题: {String(hit.question_text)}</div> : null}
          {typeof hit.lexical_raw_score === 'number' || typeof hit.lexical_structured_score === 'number' ? (
            <div className='mt-2 text-slate-500'>
              原始全文 {formatRetrievalDebugNumber(hit.lexical_raw_score)} · 结构化 {formatRetrievalDebugNumber(hit.lexical_structured_score)}
            </div>
          ) : null}
        </div>
      ))}
      {visibleHits.length === 0 ? <div className='text-xs text-slate-500'>没有命中。</div> : null}
    </div>
  )
}

export function RetrievalDebugJsonBlock({
  value,
  maxHeightClassName = 'max-h-80',
  showCopyButton = true,
}: {
  value: unknown
  maxHeightClassName?: string
  showCopyButton?: boolean
}) {
  const handleCopyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(value, null, 2))
      toast.success('JSON 已复制')
    }
    catch {
      toast.error('复制失败，请检查浏览器权限')
    }
  }

  return (
    <div className='space-y-2'>
      {showCopyButton ? (
        <div className='flex justify-end'>
          <Button type='button' variant='outline' size='sm' className='h-7 gap-1.5 border-slate-300 bg-white text-xs text-slate-700 hover:bg-slate-50' onClick={handleCopyJson}>
            <Copy className='h-3.5 w-3.5' />
            复制 JSON
          </Button>
        </div>
      ) : null}
      <pre className={`${maxHeightClassName} overflow-auto rounded-2xl border border-slate-200/90 bg-gradient-to-b from-white to-slate-50/70 p-4 text-[11px] leading-5 text-slate-700`}>
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

function formatCandidateTypeLabel(type?: unknown) {
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

function formatCandidateSourceLabel(source?: unknown, filterType?: unknown) {
  const normalized = String(source || '').trim()
  if (!normalized) {
    return ''
  }
  if (normalized === 'folder_path') {
    return '文件夹路径命中'
  }
  if (normalized === 'folder_name') {
    return '文件夹名称命中'
  }
  if (normalized === 'tag_name') {
    return '标签名称命中'
  }
  if (normalized === 'tag_alias') {
    return '标签别名命中'
  }
  if (normalized === 'metadata_option') {
    return '元数据枚举命中'
  }
  if (normalized === 'metadata_field') {
    return '元数据字段命中'
  }
  if (normalized === 'llm') {
    if (String(filterType || '').trim() === 'folder_id') {
      return 'LLM 目录判断'
    }
    return 'LLM 语义判断'
  }
  return normalized
}

/**
 * 统一展示规则/LLM 候选，优先把名称、路径、命中词翻译成人能直接看懂的内容。
 */
export function RetrievalDebugCandidateSummaryList({
  candidates,
  emptyText = '无候选',
  maxItems = 6,
}: {
  candidates: Array<Record<string, any>>
  emptyText?: string
  maxItems?: number
}) {
  const visibleCandidates = Array.isArray(candidates) ? candidates.slice(0, maxItems) : []
  if (visibleCandidates.length === 0) {
    return <div className='text-xs text-slate-500'>{emptyText}</div>
  }

  return (
    <div className='space-y-2'>
      {visibleCandidates.map((candidate, index) => {
        const filterType = formatCandidateTypeLabel(candidate?.filter_type)
        const sourceLabel = formatCandidateSourceLabel(candidate?.source, candidate?.filter_type)
        const displayName = String(candidate?.display_name || candidate?.filter_value || candidate?.target_id || '').trim() || '未标注'
        const displayPath = String(candidate?.display_path || '').trim()
        const matchedTerms = Array.isArray(candidate?.matched_terms)
          ? candidate.matched_terms.map((item: unknown) => String(item).trim()).filter(Boolean)
          : []
        const confidence = typeof candidate?.confidence === 'number' ? Number(candidate.confidence) : null
        const reason = String(candidate?.reason || '').trim()
        const targetId = String(candidate?.target_id || '').trim()

        return (
          <div key={`${String(candidate?.filter_type || 'candidate')}-${targetId || displayName}-${index}`} className='rounded-xl border border-slate-200 bg-slate-50/80 p-3'>
            <div className='flex flex-wrap items-start justify-between gap-2'>
              <div className='min-w-0 flex-1'>
                <div className='truncate text-sm font-medium text-slate-800'>{displayName}</div>
                {displayPath ? <div className='mt-1 break-all text-[11px] text-slate-500'>路径: {displayPath}</div> : null}
              </div>
              <div className='flex flex-wrap items-center gap-1.5'>
                <Badge variant='secondary' className='border-none bg-white text-slate-700 shadow-sm'>
                  {filterType}
                </Badge>
                {sourceLabel ? (
                  <Badge variant='secondary' className='border-none bg-indigo-100 text-indigo-700'>
                    {sourceLabel}
                  </Badge>
                ) : null}
                {confidence !== null ? (
                  <Badge variant='secondary' className='border-none bg-cyan-100 text-cyan-700'>
                    置信度 {confidence.toFixed(2)}
                  </Badge>
                ) : null}
              </div>
            </div>
            <div className='mt-2 space-y-1 text-xs text-slate-600'>
              {matchedTerms.length > 0 ? <div>命中词: {matchedTerms.join('、')}</div> : null}
              {reason ? <div>原因: {reason}</div> : null}
              {targetId ? <div className='break-all text-[11px] text-slate-500'>ID: {targetId}</div> : null}
            </div>
          </div>
        )
      })}
      {Array.isArray(candidates) && candidates.length > maxItems ? (
        <div className='text-[11px] text-slate-500'>其余 {candidates.length - maxItems} 项可在下方原始 JSON 中继续查看。</div>
      ) : null}
    </div>
  )
}

export function formatRetrievalDebugNumber(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(2)
  }
  return '--'
}
