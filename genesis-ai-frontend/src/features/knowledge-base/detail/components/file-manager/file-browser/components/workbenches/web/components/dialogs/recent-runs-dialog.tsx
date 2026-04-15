/**
 * 最近同步记录弹窗
 */

import { History, Loader2, CheckCircle2, AlertCircle, Clock3 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { WebSyncRunItem } from '@/lib/api/web-sync'
import { formatTime, formatRunStatus } from '../../utils'

export interface RecentRunsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  pageName?: string
  isLoading: boolean
  runs: WebSyncRunItem[]
  total: number
  page: number
  onPageChange: (page: number) => void
}

export function RecentRunsDialog({
  open,
  onOpenChange,
  pageName,
  isLoading,
  runs,
  total,
  page,
  onPageChange,
}: RecentRunsDialogProps) {
  const totalPages = Math.ceil(total / 10)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="h-5 w-5 text-sky-600" />
            同步记录
            {pageName && (
              <span className="ml-1 text-sm font-normal text-slate-400">
                · {pageName}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-2 -mx-2 px-2">
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin text-blue-500" />
              加载同步记录中...
            </div>
          ) : runs.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/50 p-8 text-center">
              <History className="mx-auto mb-2 h-8 w-8 text-slate-300" />
              <p className="text-sm text-slate-500">暂无同步记录</p>
              <p className="mt-1 text-xs text-slate-400">对该页面进行同步后将显示记录</p>
            </div>
          ) : (
            <ul className="space-y-2.5">
              {runs.map(run => (
                <li
                  key={run.run_id}
                  className={cn(
                    'rounded-xl border p-3.5 transition-all',
                    run.status === 'success' && 'border-emerald-200/60 bg-gradient-to-br from-emerald-50/50 to-white',
                    run.status === 'failed' && 'border-rose-200/60 bg-gradient-to-br from-rose-50/50 to-white',
                    (run.status === 'queued' || run.status === 'running') && 'border-amber-200/60 bg-gradient-to-br from-amber-50/50 to-white',
                    !run.status || (run.status !== 'success' && run.status !== 'failed' && run.status !== 'queued' && run.status !== 'running') && 'border-slate-200/60 bg-white'
                  )}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <Badge
                        variant="outline"
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
                  <dl className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    <div className="flex gap-2">
                      <dt className="shrink-0 text-slate-400">开始</dt>
                      <dd className="tabular-nums text-slate-600">{formatTime(run.started_at || run.created_at)}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="shrink-0 text-slate-400">结束</dt>
                      <dd className="tabular-nums text-slate-600">{formatTime(run.ended_at)}</dd>
                    </div>
                    <div className="col-span-2 flex gap-2">
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
                      className="mt-2.5 line-clamp-2 rounded-lg border border-rose-200/60 bg-rose-50/70 px-2.5 py-2 text-xs text-rose-600"
                      title={run.error_message}
                    >
                      {run.error_message}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 弹窗分页控件 */}
        {total > 10 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
            <span className="text-xs text-slate-500">
              共 {total} 条
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-16"
                disabled={page <= 1}
                onClick={() => onPageChange(Math.max(1, page - 1))}
              >
                上一页
              </Button>
              <span className="text-xs text-slate-500">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-16"
                disabled={page >= totalPages}
                onClick={() => onPageChange(Math.min(totalPages, page + 1))}
              >
                下一页
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
