/**
 * 同步记录筛选栏
 */

import { Globe, Check, ChevronsUpDown, RefreshCw, Webhook, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import type { WebPageItem } from '@/lib/api/web-sync'
import type { RunStatusFilter } from '../../types'

export interface RunsFilterBarProps {
  pageOptions: WebPageItem[]
  selectedPageId: string
  onPageSelect: (pageId: string) => void
  runStatusFilter: RunStatusFilter
  onStatusFilterChange: (status: RunStatusFilter) => void
  isManualRefresh: boolean
  onRefresh: () => void
  onLatestCheck: () => void
  latestCheckPending: boolean
  pagePickerOpen: boolean
  onPagePickerOpenChange: (open: boolean) => void
}

export function RunsFilterBar({
  pageOptions,
  selectedPageId,
  onPageSelect,
  runStatusFilter,
  onStatusFilterChange,
  isManualRefresh,
  onRefresh,
  onLatestCheck,
  latestCheckPending,
  pagePickerOpen,
  onPagePickerOpenChange,
}: RunsFilterBarProps) {
  return (
    <div className="relative z-[1] mt-2.5 flex flex-wrap items-end gap-2 border-t border-white/50 pt-2.5">
      <div className="min-w-0 w-full flex-1 basis-0 sm:min-w-[220px]">
        <p className="mb-1 text-[11px] font-medium text-slate-500">按网页地址筛选</p>
        <Popover open={pagePickerOpen} onOpenChange={onPagePickerOpenChange}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              role="combobox"
              aria-expanded={pagePickerOpen}
              title={
                selectedPageId
                  ? pageOptions.find(p => p.kb_web_page_id === selectedPageId)?.url
                  : '查看所有页面的同步记录'
              }
              className="h-9 w-full justify-between gap-2 border-sky-200/70 bg-white/90 px-3 font-normal shadow-sm shadow-sky-100/40 hover:bg-white"
            >
              <span className="flex min-w-0 flex-1 items-center gap-2">
                <Globe className="h-3.5 w-3.5 shrink-0 text-sky-600" aria-hidden />
                <span className="truncate text-left text-sm">
                  {selectedPageId
                    ? pageOptions.find(p => p.kb_web_page_id === selectedPageId)?.name ||
                      pageOptions.find(p => p.kb_web_page_id === selectedPageId)?.url ||
                      '选择页面'
                    : '全部页面'}
                </span>
              </span>
              <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" aria-hidden />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            className="w-[min(calc(100vw-2rem),440px)] p-0"
            align="start"
            sideOffset={4}
          >
            <Command>
              <CommandInput placeholder="搜索名称、URL、域名…" />
              <CommandList>
                <CommandEmpty>没有匹配的页面</CommandEmpty>
                <CommandGroup heading="范围">
                  <CommandItem
                    value="全部页面 所有 不限定 任意 url"
                    onSelect={() => {
                      onPageSelect('')
                      onPagePickerOpenChange(false)
                    }}
                  >
                    <Check className={cn('h-4 w-4 shrink-0', selectedPageId ? 'opacity-0' : 'opacity-100')} />
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="font-medium">全部页面</span>
                      <span className="text-xs text-muted-foreground">不限定 URL，显示所有同步记录</span>
                    </div>
                  </CommandItem>
                </CommandGroup>
                {pageOptions.length > 0 ? (
                  <>
                    <CommandSeparator />
                    <CommandGroup heading="网页地址">
                      {pageOptions.map(item => {
                        const searchBlob = `${item.name} ${item.url} ${item.domain}`.trim()
                        return (
                          <CommandItem
                            key={item.kb_web_page_id}
                            value={searchBlob}
                            onSelect={() => {
                              onPageSelect(item.kb_web_page_id)
                              onPagePickerOpenChange(false)
                            }}
                          >
                            <Check
                              className={cn(
                                'h-4 w-4 shrink-0',
                                selectedPageId !== item.kb_web_page_id && 'opacity-0'
                              )}
                            />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium leading-tight">{item.name || item.url}</p>
                              <p className="mt-0.5 truncate text-xs text-muted-foreground" title={item.url}>
                                {item.url}
                              </p>
                              {item.domain ? (
                                <p className="mt-0.5 text-[11px] text-muted-foreground/80">域名 · {item.domain}</p>
                              ) : null}
                            </div>
                          </CommandItem>
                        )
                      })}
                    </CommandGroup>
                  </>
                ) : (
                  <p className="px-3 py-2.5 text-center text-xs text-muted-foreground">
                    暂无已登记页面，请到「网页页面」添加 URL
                  </p>
                )}
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>
      <div className="flex w-full shrink-0 flex-wrap items-center gap-1.5 sm:w-auto sm:pb-0">
        <Select value={runStatusFilter} onValueChange={value => onStatusFilterChange(value as RunStatusFilter)}>
          <SelectTrigger className="h-9 w-full min-w-[124px] border-sky-200/70 bg-white/90 text-sm shadow-sm shadow-sky-100/40 backdrop-blur-[2px] hover:bg-white sm:w-[128px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            <SelectItem value="queued">排队中</SelectItem>
            <SelectItem value="running">执行中</SelectItem>
            <SelectItem value="success">成功</SelectItem>
            <SelectItem value="failed">失败</SelectItem>
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          className="h-9 border-sky-200/80 bg-white/95 px-3 text-sm shadow-sm shadow-sky-100/30 hover:bg-white"
          disabled={isManualRefresh}
          onClick={onRefresh}
        >
          <RefreshCw className={cn('mr-1.5 h-3.5 w-3.5', isManualRefresh && 'animate-spin')} />
          {isManualRefresh ? '查询中…' : '查询'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          className="h-9 border border-sky-200/50 bg-white/90 px-3 text-sm shadow-sm shadow-sky-100/25 hover:bg-white"
          disabled={!selectedPageId || latestCheckPending}
          onClick={onLatestCheck}
        >
          {latestCheckPending ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Webhook className="mr-1.5 h-3.5 w-3.5" />
          )}
          校验最新
        </Button>
      </div>
    </div>
  )
}
