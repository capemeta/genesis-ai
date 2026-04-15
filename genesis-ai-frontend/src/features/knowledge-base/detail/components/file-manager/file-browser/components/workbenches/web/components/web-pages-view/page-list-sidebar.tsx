/**
 * 页面列表侧边栏
 */

import { Globe, Search, RefreshCw, Plus, Copy, ExternalLink, MoreVertical, RefreshCw as SyncIcon, Webhook, Edit2, Trash2, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import type { WebPageItem } from '@/lib/api/web-sync'
import { formatTime, formatWebPageSyncStatus, getWebPageSyncStatusClass } from '../../utils'

export interface PageListSidebarProps {
  pageSearchKeyword: string
  onPageSearchKeywordChange: (keyword: string) => void
  pageListPage: number
  totalPages: number
  totalItems: number
  includeSubfolders: boolean
  onIncludeSubfoldersChange: (value: boolean) => void
  isFetchingPagedPages: boolean
  isLoadingPagedPages: boolean
  isRefetchingPagedPages: boolean
  pagedPageOptions: WebPageItem[]
  selectedPageId: string
  onPageSelect: (pageId: string) => void
  onAddPage: () => void
  onRefreshList: () => void
  onSyncNow: (pageId: string) => void
  onLatestCheck: (pageId: string) => void
  onEditPage: (page: WebPageItem) => void
  onDeletePage: (page: WebPageItem) => void
  onCopyUrl: (url?: string | null) => void
  onOpenUrl: (url?: string | null) => void
  onPageChange: (page: number) => void
}

export function PageListSidebar({
  pageSearchKeyword,
  onPageSearchKeywordChange,
  pageListPage,
  totalPages,
  totalItems,
  includeSubfolders,
  onIncludeSubfoldersChange,
  isFetchingPagedPages,
  isLoadingPagedPages,
  isRefetchingPagedPages,
  pagedPageOptions,
  selectedPageId,
  onPageSelect,
  onAddPage,
  onRefreshList,
  onSyncNow,
  onLatestCheck,
  onEditPage,
  onDeletePage,
  onCopyUrl,
  onOpenUrl,
  onPageChange,
}: PageListSidebarProps) {
  return (
    <aside className="flex w-80 flex-col border-r border-slate-200 bg-white/80 backdrop-blur-sm">
      <div className="border-b border-slate-200 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 p-3">
        <div className="mb-2 flex items-center gap-2">
          <div className="rounded-lg bg-blue-500/10 p-1.5">
            <Globe className="h-4 w-4 text-blue-600" />
          </div>
          <h2 className="text-sm font-semibold text-slate-800">网页页面</h2>
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="搜索名称、URL、域名"
            value={pageSearchKeyword}
            onChange={e => {
              onPageSearchKeywordChange(e.target.value)
            }}
            className="h-8 border-slate-200 bg-white pl-8 text-sm placeholder:text-slate-400 focus-visible:ring-blue-500"
          />
        </div>
      </div>
      <div className="border-b border-slate-200 p-3">
        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            disabled={isFetchingPagedPages}
            onClick={onRefreshList}
          >
            <RefreshCw className={isFetchingPagedPages ? 'mr-2 h-3.5 w-3.5 animate-spin' : 'mr-2 h-3.5 w-3.5'} />
            {isFetchingPagedPages ? '刷新中…' : '刷新列表'}
          </Button>
          <Button size="sm" className="bg-blue-600 hover:bg-blue-700 shadow-sm shadow-blue-200" onClick={onAddPage}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            新增页面
          </Button>
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2">
          <Switch checked={includeSubfolders} onCheckedChange={onIncludeSubfoldersChange} />
          <span className="text-xs text-slate-600">包含子文件夹</span>
        </div>
      </div>
      <div className="relative min-h-0 flex-1 overflow-y-auto p-3">
        <div className="space-y-3">
          {isLoadingPagedPages ? (
            <div className="flex items-center justify-center py-12 text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin text-blue-500" />
              正在加载页面...
            </div>
          ) : pagedPageOptions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white/80 p-4 text-sm text-slate-500">暂无页面，请先新增 URL。</div>
          ) : (
            pagedPageOptions.map(item => {
              const isActive = item.kb_web_page_id === selectedPageId
              return (
                <div
                  key={item.kb_web_page_id}
                  onClick={() => onPageSelect(item.kb_web_page_id)}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      onPageSelect(item.kb_web_page_id)
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    isActive
                      ? 'border-blue-300 bg-blue-50/70 shadow-sm ring-1 ring-blue-200'
                      : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-blue-50/30'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-800">{item.name}</p>
                      <div className="mt-1 flex items-center gap-1">
                        <p className="min-w-0 flex-1 truncate text-xs text-slate-500">{item.url}</p>
                        <button
                          type="button"
                          className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                          title="复制 URL"
                          aria-label="复制 URL"
                          onClick={event => {
                            event.stopPropagation()
                            onCopyUrl(item.url)
                          }}
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">最近同步：{formatTime(item.last_synced_at)}</p>
                    </div>
                    <div className="flex items-start gap-1">
                      <Badge className={getWebPageSyncStatusClass(item.sync_status)}>{formatWebPageSyncStatus(item.sync_status)}</Badge>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <span
                            className="inline-flex h-6 w-6 cursor-pointer items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                            onClick={event => event.stopPropagation()}
                          >
                            <MoreVertical className="h-3.5 w-3.5" />
                          </span>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="start" sideOffset={4} avoidCollisions className="min-w-[160px]" onClick={event => event.stopPropagation()}>
                          <DropdownMenuItem
                            onClick={event => {
                              event.stopPropagation()
                              onSyncNow(item.kb_web_page_id)
                            }}
                          >
                            <SyncIcon className="mr-2 h-4 w-4" />
                            立即同步
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={event => {
                              event.stopPropagation()
                              onLatestCheck(item.kb_web_page_id)
                            }}
                          >
                            <Webhook className="mr-2 h-4 w-4" />
                            校验最新
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={event => {
                              event.stopPropagation()
                              onOpenUrl(item.url)
                            }}
                          >
                            <ExternalLink className="mr-2 h-4 w-4" />
                            打开网页
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={event => {
                              event.stopPropagation()
                              onEditPage(item)
                            }}
                          >
                            <Edit2 className="mr-2 h-4 w-4" />
                            编辑页面
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            variant="destructive"
                            onClick={event => {
                              event.stopPropagation()
                              onDeletePage(item)
                            }}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            删除页面
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
        {isRefetchingPagedPages ? (
          <div
            className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-white/55 backdrop-blur-[1px]"
            aria-busy
            aria-label="正在刷新列表"
          >
            <div className="flex flex-col items-center gap-2 rounded-lg border border-slate-200 bg-white/95 px-4 py-3 shadow-sm">
              <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              <span className="text-xs text-slate-600">正在刷新列表…</span>
            </div>
          </div>
        ) : null}
      </div>
      <div className="border-t border-slate-200 p-3">
        <div className="mb-2 text-xs text-slate-500">
          共 {totalItems} 条，第 {pageListPage} / {totalPages} 页
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" size="sm" disabled={pageListPage <= 1} onClick={() => onPageChange(Math.max(1, pageListPage - 1))}>
            上一页
          </Button>
          <Button variant="outline" size="sm" disabled={pageListPage >= totalPages} onClick={() => onPageChange(Math.min(totalPages, pageListPage + 1))}>
            下一页
          </Button>
        </div>
      </div>
    </aside>
  )
}
