/**
 * 同步记录表格
 */

import { Globe, CheckCircle2, AlertCircle, Clock3, ChevronsUpDown, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type { WebSyncRunItem, WebPageItem } from '@/lib/api/web-sync'
import { formatTime, formatRunStatus } from '../../utils'

export interface RunsTableProps {
  runs: WebSyncRunItem[]
  pageOptions: WebPageItem[]
  isManualRefresh: boolean
}

export function RunsTable({ runs, pageOptions, isManualRefresh }: RunsTableProps) {
  return (
    <>
      <ul className="mx-auto max-w-4xl space-y-3">
        {runs.map(run => {
          const relatedPage = pageOptions.find(p => p.kb_web_page_id === run.kb_web_page_id)
          return (
            <li
              key={run.run_id}
              className={cn(
                'rounded-xl border p-4 shadow-sm transition-all hover:shadow-md',
                run.status === 'success' && 'border-emerald-200/50 bg-gradient-to-br from-white to-emerald-50/30 hover:border-emerald-300/60',
                run.status === 'failed' && 'border-rose-200/50 bg-gradient-to-br from-white to-rose-50/30 hover:border-rose-300/60',
                (run.status === 'queued' || run.status === 'running') && 'border-amber-200/50 bg-gradient-to-br from-white to-amber-50/30 hover:border-amber-300/60',
                (!run.status || (run.status !== 'success' && run.status !== 'failed' && run.status !== 'queued' && run.status !== 'running')) && 'border-slate-200/80 bg-white hover:border-slate-300/90'
              )}
            >
              {/* 页面标题和地址 */}
              {relatedPage && (
                <div className="mb-2.5 flex items-start gap-2 rounded-lg bg-slate-50/80 p-2.5">
                  <Globe className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-700" title={relatedPage.name || relatedPage.url}>
                      {relatedPage.name || relatedPage.url}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-slate-400" title={relatedPage.url}>
                      {relatedPage.url}
                    </p>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <Badge
                    variant="secondary"
                    className={cn(
                      'font-normal',
                      run.trigger_type === 'manual' && 'bg-blue-50 text-blue-600 border-blue-200',
                      run.trigger_type === 'scheduled' && 'bg-purple-50 text-purple-600 border-purple-200',
                      (!run.trigger_type || (run.trigger_type !== 'manual' && run.trigger_type !== 'scheduled')) && 'bg-slate-50 text-slate-600'
                    )}
                  >
                    {run.trigger_type}
                  </Badge>
                  <span className="text-xs tabular-nums text-slate-400">HTTP {run.http_status ?? '—'}</span>
                </div>
                <div
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
                    run.status === 'success' && 'bg-emerald-100/70 text-emerald-700',
                    run.status === 'failed' && 'bg-rose-100/70 text-rose-700',
                    (run.status === 'queued' || run.status === 'running') && 'bg-amber-100/70 text-amber-700',
                    (!run.status || (run.status !== 'success' && run.status !== 'failed' && run.status !== 'queued' && run.status !== 'running')) && 'bg-slate-100/70 text-slate-600'
                  )}
                >
                  {run.status === 'success' && <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />}
                  {run.status === 'failed' && <AlertCircle className="h-3.5 w-3.5 shrink-0" />}
                  {(run.status === 'queued' || run.status === 'running') && <Clock3 className="h-3.5 w-3.5 shrink-0" />}
                  {formatRunStatus(run.status)}
                </div>
              </div>
              <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2 sm:gap-x-6">
                <div className="flex gap-2 text-slate-500">
                  <dt className="shrink-0 text-slate-400">开始</dt>
                  <dd className="tabular-nums text-slate-600">{formatTime(run.started_at || run.created_at)}</dd>
                </div>
                <div className="flex gap-2 text-slate-500">
                  <dt className="shrink-0 text-slate-400">结束</dt>
                  <dd className="tabular-nums text-slate-600">{formatTime(run.ended_at)}</dd>
                </div>
                <div className="flex gap-2 text-slate-500 sm:col-span-2">
                  <dt className="shrink-0 text-slate-400">变化</dt>
                  <dd className={cn(
                    run.content_changed === true && 'text-amber-600',
                    run.content_changed === false && 'text-emerald-600',
                    run.content_changed === null && 'text-slate-400'
                  )}>
                    {run.content_changed === null ? '—' : run.content_changed ? '有变化' : '无变化'}
                  </dd>
                </div>
              </dl>
              {run.error_message ? (
                <p
                  className="mt-3 line-clamp-2 rounded-lg border border-rose-200/60 bg-rose-50/70 px-2.5 py-2 text-xs text-rose-600"
                  title={run.error_message}
                >
                  {run.error_message}
                </p>
              ) : null}
            </li>
          )
        })}
      </ul>

      {isManualRefresh && (
        <div
          className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-white/55 backdrop-blur-[1px]"
          aria-busy
          aria-label="正在按当前条件查询同步记录"
        >
          <div className="flex flex-col items-center gap-2 rounded-lg border border-slate-200 bg-white/95 px-4 py-3 shadow-sm">
            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
            <span className="text-xs text-slate-600">正在查询…</span>
          </div>
        </div>
      )}
    </>
  )
}

export interface RunsPaginationProps {
  total: number
  page: number
  onPageChange: (page: number) => void
}

export function RunsPagination({ total, page, onPageChange }: RunsPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / 20))

  return (
    <div className="mx-auto mt-6 max-w-4xl">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200/60 bg-white/90 px-4 py-3 shadow-sm">
        <span className="text-xs text-slate-500">
          共 <span className="font-medium text-slate-700">{total}</span> 条记录
          {total > 20 && (
            <span className="ml-2 text-slate-400">· 每页 20 条</span>
          )}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-8 w-20"
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            <ChevronsUpDown className="mr-1 h-3.5 w-3.5 rotate-90" />
            上一页
          </Button>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500">第</span>
            <Input
              type="number"
              min={1}
              max={totalPages}
              value={page}
              onChange={e => {
                const val = parseInt(e.target.value, 10)
                if (!isNaN(val) && val >= 1 && val <= totalPages) {
                  onPageChange(val)
                }
              }}
              className="h-8 w-14 text-center text-xs"
            />
            <span className="text-xs text-slate-500">页</span>
            <span className="text-xs text-slate-400">
              / 共 {totalPages} 页
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-8 w-20"
            disabled={page >= totalPages}
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          >
            下一页
            <ChevronsUpDown className="ml-1 h-3.5 w-3.5 -rotate-90" />
          </Button>
        </div>
      </div>
    </div>
  )
}
