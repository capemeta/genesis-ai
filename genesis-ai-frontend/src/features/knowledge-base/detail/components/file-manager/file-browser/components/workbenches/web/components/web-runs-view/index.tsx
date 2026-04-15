/**
 * 同步记录视图主组件
 */

import { useState, useEffect } from 'react'
import { Globe, Clock3, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { RunStatusFilter } from '../../types'
import { useWebPages, useWebPagesStats, useWebSyncRuns } from '../../hooks'
import { useLatestCheckMutation } from '../../hooks'
import { RunsTable, RunsPagination } from './runs-table'
import { RunsFilterBar } from './runs-filter-bar'

export interface WebRunsViewProps {
  kbId: string
}

export function WebRunsView({ kbId }: WebRunsViewProps) {
  // 筛选状态
  const [selectedPageId, setSelectedPageId] = useState('')
  const [runStatusFilter, setRunStatusFilter] = useState<RunStatusFilter>('all')
  const [runsPage, setRunsPage] = useState(1)
  const [isManualRefresh, setIsManualRefresh] = useState(false)
  const [runsPagePickerOpen, setRunsPagePickerOpen] = useState(false)

  // 数据查询
  const { allPagesData: pageOptions } = useWebPages({
    kbId,
    view: 'web-runs',
    selectedFolderId: null,
    includeSubfolders: true,
    pageSearchKeyword: '',
    pageListPage: 1,
  })

  const stats = useWebPagesStats(pageOptions)

  const { runsData, isLoadingRuns, refetchRuns } = useWebSyncRuns({
    kbId,
    view: 'web-runs',
    selectedPageId,
    runStatusFilter,
    runsPage,
  })

  // Mutations
  const latestCheckMutation = useLatestCheckMutation(kbId)

  // 重置页码
  useEffect(() => {
    setRunsPage(1)
  }, [selectedPageId, runStatusFilter])

  // 刷新
  const handleRefresh = () => {
    setIsManualRefresh(true)
    void refetchRuns().finally(() => setIsManualRefresh(false))
  }

  // 最新校验
  const handleLatestCheck = () => {
    if (selectedPageId) {
      latestCheckMutation.mutate({ kb_web_page_id: selectedPageId })
    }
  }

  return (
    <div className="flex h-full min-h-0 bg-gradient-to-br from-slate-50 via-white to-slate-50/80">
      <main className="min-w-0 flex-1 px-6 pb-4 pt-0 md:pb-5">
        <Card className="flex h-full min-h-0 flex-col overflow-hidden border-slate-200/70 bg-white shadow-sm ring-1 ring-slate-950/5">
          <CardHeader className="relative space-y-0 overflow-hidden border-b border-sky-100/80 bg-gradient-to-br from-sky-50 via-cyan-50/85 to-violet-50/55 px-4 py-2.5 sm:px-5">
            {/* 右上角柔和高光 */}
            <div
              className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_85%_55%_at_95%_0%,rgba(255,255,255,0.42),transparent_50%)]"
              aria-hidden
            />
            {/* 第一行：标题 + 统计 */}
            <div className="relative z-[1] flex flex-wrap items-center gap-x-4 gap-y-2">
              <div className="flex min-w-0 flex-1 items-center gap-2 sm:min-w-[200px] sm:flex-none">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/85 text-sky-600 shadow-sm ring-1 ring-sky-100/90">
                  <Clock3 className="h-4 w-4" strokeWidth={2} />
                </div>
                <div className="min-w-0">
                  <CardTitle className="text-base font-semibold leading-tight text-slate-800">同步记录</CardTitle>
                  <p className="mt-0.5 text-[11px] leading-snug text-slate-500">日志 · 筛选 · 校验</p>
                </div>
              </div>
              <div className="flex w-full flex-wrap items-center gap-x-2.5 gap-y-1 sm:ml-auto sm:w-auto sm:justify-end sm:gap-x-0">
                {(
                  [
                    { label: '总页面', value: stats.total },
                    { label: '同步中', value: stats.running, dot: 'bg-sky-400/70' },
                    { label: '失败', value: stats.failed, dot: 'bg-rose-400/60' },
                    { label: '待更新', value: stats.outdated, dot: 'bg-amber-400/60' },
                  ] as const
                ).map((item, i) => (
                  <span key={item.label} className="inline-flex items-center">
                    {i > 0 ? <span className="mx-2.5 hidden h-3 w-px bg-sky-200/70 sm:inline" aria-hidden /> : null}
                    <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                      {'dot' in item && item.dot ? (
                        <span className={('inline-block size-1.5 shrink-0 rounded-full ' + item.dot) as string} aria-hidden />
                      ) : null}
                      <span>{item.label}</span>
                      <span className="tabular-nums text-xs font-medium text-slate-600">{item.value}</span>
                    </span>
                  </span>
                ))}
              </div>
            </div>

            <RunsFilterBar
              pageOptions={pageOptions}
              selectedPageId={selectedPageId}
              onPageSelect={setSelectedPageId}
              runStatusFilter={runStatusFilter}
              onStatusFilterChange={setRunStatusFilter}
              isManualRefresh={isManualRefresh}
              onRefresh={handleRefresh}
              onLatestCheck={handleLatestCheck}
              latestCheckPending={latestCheckMutation.isPending}
              pagePickerOpen={runsPagePickerOpen}
              onPagePickerOpenChange={setRunsPagePickerOpen}
            />
          </CardHeader>

          <CardContent className="relative min-h-0 flex-1 overflow-auto bg-slate-50/40 p-4 md:p-5">
            {isLoadingRuns ? (
              <div className="flex flex-col items-center justify-center gap-3 py-16 text-sm text-slate-500">
                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                <span>加载同步记录中…</span>
              </div>
            ) : (runsData?.items || []).length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200/80 bg-white/60 py-14 text-center">
                <Globe className="mb-2 h-9 w-9 text-slate-300" />
                <p className="text-sm text-slate-500">暂无同步记录</p>
                <p className="mt-1 max-w-xs text-xs text-slate-400">调整筛选条件或等待同步任务完成后将在此展示</p>
              </div>
            ) : (
              <div className="relative">
                <RunsTable
                  runs={runsData?.items || []}
                  pageOptions={pageOptions}
                  isManualRefresh={isManualRefresh}
                />
                {runsData && runsData.total > 0 && (
                  <RunsPagination
                    total={runsData.total}
                    page={runsPage}
                    onPageChange={setRunsPage}
                  />
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
