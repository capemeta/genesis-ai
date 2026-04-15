/**
 * 页面详情面板
 */

import { Globe, Copy, ExternalLink, History, AlertCircle, Search, RefreshCw, Webhook, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { WebPageItem, WebScheduleItem } from '@/lib/api/web-sync'
import type { ScheduleFormState } from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/shared/schedule-rule-builder'
import ScheduleRuleBuilder from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/shared/schedule-rule-builder'
import type { WebChunkingDraft } from '../../types'
import { formatTime, formatWebPageSyncStatus, getWebPageSyncStatusClass, formatFetchMode } from '../../utils'
import { buildSchedulePayload } from '../../utils'

export interface PageDetailPanelProps {
  selectedPage: WebPageItem | undefined
  selectedPageId: string
  selectedPageFolderName: string
  selectedPageConfigDraft: {
    timeoutSeconds: number
    contentSelector: string
    chunking: WebChunkingDraft
  }
  kbDefaultSchedule: WebScheduleItem | undefined
  selectedPageSchedule: WebScheduleItem | undefined
  pageScheduleForm: ScheduleFormState
  onPageScheduleFormChange: (form: ScheduleFormState) => void
  scheduleFormRestoredToDefault: boolean
  onSaveSchedule: (payload: Parameters<typeof buildSchedulePayload>[1]) => void
  onDeleteSchedule: () => void
  onCopyUrl: (url?: string | null) => void
  onOpenUrl: (url?: string | null) => void
  onOpenRecentRuns: () => void
  onPreviewExtract: () => void
  onLatestCheck: () => void
  onSyncNow: () => void
  previewPending: boolean
  latestCheckPending: boolean
  syncNowPending: boolean
  saveSchedulePending: boolean
  deleteSchedulePending: boolean
  recentRunsCount: number
}

export function PageDetailPanel({
  selectedPage,
  selectedPageId,
  selectedPageFolderName,
  selectedPageConfigDraft,
  kbDefaultSchedule,
  selectedPageSchedule,
  pageScheduleForm,
  onPageScheduleFormChange,
  scheduleFormRestoredToDefault,
  onSaveSchedule,
  onDeleteSchedule,
  onCopyUrl,
  onOpenUrl,
  onOpenRecentRuns,
  onPreviewExtract,
  onLatestCheck,
  onSyncNow,
  previewPending,
  latestCheckPending,
  syncNowPending,
  saveSchedulePending,
  deleteSchedulePending,
  recentRunsCount,
}: PageDetailPanelProps) {
  return (
    <main className="min-w-0 flex-1 p-4">
      <Card className="flex h-full min-h-0 flex-col overflow-hidden border-slate-200 bg-white/95 shadow-sm">
        <CardHeader className="border-b border-slate-200 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              <CardTitle className="text-base text-slate-800">{selectedPage ? selectedPage.name : '页面详情与调度'}</CardTitle>
              <div className="mt-1 flex items-center gap-1.5">
                <div className="flex min-w-0 items-center gap-1.5">
                  <p className="min-w-0 truncate text-xs text-slate-500">
                    {selectedPage ? selectedPage.url : '请选择左侧页面后进行调度配置与手动操作'}
                  </p>
                  {selectedPage ? (
                    <>
                      <button
                        type="button"
                        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                        title="复制 URL"
                        aria-label="复制 URL"
                        onClick={() => onCopyUrl(selectedPage.url)}
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                        title="新标签页打开"
                        aria-label="新标签页打开"
                        onClick={() => onOpenUrl(selectedPage.url)}
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </button>
                    </>
                  ) : null}
                </div>
              </div>
              {/* 状态字段区域 */}
              {selectedPage && (
                <div className="mt-2 space-y-1.5 text-xs">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
                    <span className="flex items-center gap-1">
                      状态：<Badge className={getWebPageSyncStatusClass(selectedPage.sync_status)}>{formatWebPageSyncStatus(selectedPage.sync_status)}</Badge>
                      {/* 同步记录弹窗触发按钮 */}
                      <button
                        type="button"
                        className="inline-flex items-center justify-center rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
                        onClick={onOpenRecentRuns}
                        title="查看最近同步记录"
                      >
                        <History className="h-3.5 w-3.5" />
                        {recentRunsCount > 0 && (
                          <span className="absolute -mt-1 ml-0.5 inline-flex h-2 w-2">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
                            <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500 opacity-90"></span>
                          </span>
                        )}
                      </button>
                    </span>
                    <span className="text-slate-600">最近同步：{formatTime(selectedPage.last_synced_at)}</span>
                    <span className="text-slate-600">挂载目录：{selectedPageFolderName}</span>
                    <span className="text-slate-600">新增时间：{formatTime(selectedPage.created_at)}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">抓取：{formatFetchMode(selectedPage.fetch_mode)}</span>
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">超时：{selectedPageConfigDraft.timeoutSeconds}s</span>
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">分块上限：{selectedPageConfigDraft.chunking.max_embed_tokens}</span>
                    {selectedPageConfigDraft.contentSelector ? (
                      <span
                        className="max-w-full truncate rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-sky-700"
                        title={selectedPageConfigDraft.contentSelector}
                      >
                        Selector：{selectedPageConfigDraft.contentSelector}
                      </span>
                    ) : (
                      <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">Selector：未指定</span>
                    )}
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                className="border-sky-200 bg-white text-sky-700 hover:bg-sky-50"
                disabled={!selectedPageId || previewPending}
                onClick={onPreviewExtract}
              >
                {previewPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Search className="mr-1.5 h-3.5 w-3.5" />
                )}
                抽取预览
              </Button>
              <Button
                size="sm"
                className="bg-orange-500 hover:bg-orange-600 shadow-sm shadow-orange-200 text-white"
                disabled={!selectedPageId || latestCheckPending}
                onClick={onLatestCheck}
              >
                {latestCheckPending ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Webhook className="mr-1.5 h-3.5 w-3.5" />}
                校验最新
              </Button>
              <Button
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 shadow-sm shadow-blue-200"
                disabled={!selectedPageId || syncNowPending}
                onClick={onSyncNow}
              >
                {syncNowPending ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="mr-1.5 h-3.5 w-3.5" />}
                立即同步
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="min-h-0 flex-1 overflow-auto p-4">
          {!selectedPage ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-slate-300 bg-white/90 text-sm text-slate-500">
              <Globe className="h-8 w-8 text-slate-400" />
              <div>请先在左侧选择一个页面</div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* 同步失败时展示错误详情块 */}
              {selectedPage.sync_status === 'failed' && selectedPage.last_error && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3">
                  <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-red-700">
                    <AlertCircle className="h-3.5 w-3.5" />
                    同步错误
                  </div>
                  <p className="whitespace-pre-wrap break-all text-xs text-red-600">{selectedPage.last_error}</p>
                </div>
              )}

              <ScheduleRuleBuilder
                title="页面级定时覆盖"
                description={
                  scheduleFormRestoredToDefault
                    ? '当前页面正在继承知识库默认规则；如需单独控制，可在这里保存页面级规则。'
                    : selectedPageSchedule
                      ? '当前页面已启用独立规则，保存后继续覆盖知识库默认规则。'
                      : '当前页面正在继承知识库默认规则；如需单独控制，可在这里保存页面级规则。'
                }
                form={pageScheduleForm}
                onChange={onPageScheduleFormChange}
                nextTriggerAt={scheduleFormRestoredToDefault ? kbDefaultSchedule?.next_trigger_at : selectedPageSchedule?.next_trigger_at}
                savedScheduleType={scheduleFormRestoredToDefault ? kbDefaultSchedule?.schedule_type as any : (selectedPageSchedule?.schedule_type as any || undefined)}
                saveLabel="保存页面规则"
                saveDisabled={!selectedPageId || saveSchedulePending}
                isSaving={saveSchedulePending}
                secondaryActionLabel={selectedPageSchedule ? '恢复继承默认规则' : undefined}
                secondaryActionDisabled={!selectedPageSchedule || deleteSchedulePending}
                onSecondaryAction={() => {
                  onDeleteSchedule()
                }}
                onSave={() => {
                  onSaveSchedule(pageScheduleForm)
                }}
              />
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
