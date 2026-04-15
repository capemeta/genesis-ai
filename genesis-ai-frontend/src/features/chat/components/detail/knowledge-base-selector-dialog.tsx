import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, ChevronLeft, ChevronRight, Database, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { fetchChatKnowledgeBasePickerList } from '@/features/chat/api/chat'
import type { ChatSelectorOption } from '@/features/chat/types/chat'

const PAGE_SIZE = 20

/** 知识库类型展示（与 extra.type 对应） */
const KB_TYPE_LABEL: Record<string, string> = {
  general: '通用',
  qa: '问答',
  table: '表格',
  web: '网页',
  media: '媒体',
  connector: '连接器',
}

interface KnowledgeBaseSelectorDialogProps {
  open: boolean
  /** 侧栏已挂载的知识库 ID，列表中排除（服务端过滤） */
  excludeIds: string[]
  onOpenChange: (open: boolean) => void
  /** 本弹窗勾选的若干 ID，由侧栏合并进已选列表 */
  onConfirm: (addedIds: string[]) => void
}

function typeLabel(kb: ChatSelectorOption): string {
  const t = kb.extra?.type
  return typeof t === 'string' ? KB_TYPE_LABEL[t] ?? t : '通用'
}

function isPrivate(kb: ChatSelectorOption): boolean {
  return kb.extra?.visibility === 'private'
}

/** 仅弹窗打开时挂载：仅累积「本次要添加」的勾选 */
function KnowledgeBaseSelectorDialogBody({
  excludeIds,
  onOpenChange,
  onConfirm,
}: Omit<KnowledgeBaseSelectorDialogProps, 'open'>) {
  const [keyword, setKeyword] = useState('')
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  const [page, setPage] = useState(1)
  /** 本次弹窗内勾选：id -> 名称（用于跨页展示） */
  const [picked, setPicked] = useState<Record<string, string>>({})

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedKeyword(keyword.trim())
      setPage(1)
    }, 320)
    return () => window.clearTimeout(timer)
  }, [keyword])

  const excludeKey = useMemo(() => [...excludeIds].sort().join(','), [excludeIds])

  // queryFn 使用 excludeIds；queryKey 用 excludeKey 稳定序列化，避免父组件传入新数组引用时误触发重复请求
  const { data, isPending, isError, error, refetch, isFetching } = useQuery({
    // eslint-disable-next-line @tanstack/query/exhaustive-deps -- 见上 excludeKey
    queryKey: ['chat', 'knowledge-base-picker', debouncedKeyword, page, excludeKey],
    queryFn: () =>
      fetchChatKnowledgeBasePickerList({
        page,
        page_size: PAGE_SIZE,
        search: debouncedKeyword || undefined,
        exclude_ids: excludeIds,
      }),
    staleTime: 30_000,
  })

  const items = useMemo(() => data?.data ?? [], [data])
  const total = data?.total ?? 0
  const totalPages = total === 0 ? 1 : Math.ceil(total / PAGE_SIZE)

  const pickedIds = Object.keys(picked)
  const pickedSummary = pickedIds.map((id) => picked[id] || id).join('、')

  const toggleKnowledgeBase = (kb: ChatSelectorOption) => {
    setPicked((prev) => {
      const next = { ...prev }
      if (next[kb.id]) {
        delete next[kb.id]
      } else {
        next[kb.id] = kb.name
      }
      return next
    })
  }

  const showEmpty = !isPending && !isError && items.length === 0
  const showList = items.length > 0

  return (
    <>
      <DialogHeader className='shrink-0 border-b bg-muted/20 px-6 py-4 text-left'>
        <DialogTitle className='pr-8 text-lg'>添加知识库</DialogTitle>
        {/* 仅读屏器可见，避免默认占视觉空间 */}
        <DialogDescription className='sr-only'>
          列表为尚未挂载到当前空间的知识库，可搜索与分页；确认后在侧栏保存配置生效。
        </DialogDescription>
      </DialogHeader>

      <div className='flex min-h-0 flex-1 flex-col gap-3 px-6 pt-4'>
        <div className='relative shrink-0'>
          <Search className='pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
          <Input
            value={keyword}
            placeholder='搜索名称或描述…'
            className='h-10 rounded-lg border-muted-foreground/20 bg-background pl-9 shadow-sm'
            onChange={(event) => setKeyword(event.target.value)}
          />
        </div>

        {!isPending && total > 0 ? (
          <div className='flex shrink-0 flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground'>
            <span>
              可添加 {total} 个 · 第 {page} / {totalPages} 页
            </span>
            {pickedIds.length > 0 ? (
              <span className='text-foreground/80'>本弹窗已选 {pickedIds.length}</span>
            ) : null}
          </div>
        ) : null}

        <div
          className={cn(
            'relative min-h-[280px] flex-1 overflow-y-auto rounded-xl border border-border/80 bg-gradient-to-b from-muted/40 to-background',
            'shadow-inner',
            isFetching && !isPending && 'opacity-70'
          )}
        >
          {isPending ? (
            <div className='space-y-2 p-3'>
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className='h-[72px] w-full rounded-lg' />
              ))}
            </div>
          ) : null}

          {isError ? (
            <div className='flex flex-col items-center justify-center gap-3 px-6 py-16 text-center'>
              <AlertCircle className='h-10 w-10 text-destructive/80' />
              <p className='text-sm text-muted-foreground'>
                {(error as Error)?.message || '加载失败，请重试'}
              </p>
              <Button size='sm' variant='outline' onClick={() => refetch()}>
                重新加载
              </Button>
            </div>
          ) : null}

          {showEmpty ? (
            <div className='flex flex-col items-center justify-center gap-2 px-6 py-20 text-center'>
              <Database className='h-10 w-10 text-muted-foreground/50' />
              <p className='text-sm font-medium text-muted-foreground'>
                {debouncedKeyword
                  ? '没有匹配的未挂载知识库'
                  : excludeIds.length > 0
                    ? '没有可添加的知识库（可能已全部挂载）'
                    : '暂无知识库'}
              </p>
              {debouncedKeyword ? (
                <p className='text-xs text-muted-foreground'>换个关键词试试</p>
              ) : null}
            </div>
          ) : null}

          {showList ? (
            <ul className='space-y-2 p-3' role='listbox' aria-multiselectable>
              {items.map((kb) => {
                const checked = Boolean(picked[kb.id])
                const tl = typeLabel(kb)

                return (
                  <li key={kb.id} role='option' aria-selected={checked}>
                    <div
                      role='button'
                      tabIndex={0}
                      className={cn(
                        'group relative flex cursor-pointer rounded-xl border p-3 text-left transition-all',
                        'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                        checked
                          ? 'border-primary/60 bg-primary/[0.07] shadow-sm ring-1 ring-primary/20'
                          : 'border-transparent bg-card/80 hover:border-border hover:bg-muted/50'
                      )}
                      onClick={() => toggleKnowledgeBase(kb)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          toggleKnowledgeBase(kb)
                        }
                      }}
                    >
                      {checked ? (
                        <div
                          className='absolute top-2 bottom-2 left-0 w-1 rounded-full bg-primary'
                          aria-hidden
                        />
                      ) : null}
                      <div className='flex w-full items-start gap-3 pl-1'>
                        <Checkbox
                          checked={checked}
                          className='mt-0.5'
                          onClick={(e) => e.stopPropagation()}
                          onCheckedChange={() => toggleKnowledgeBase(kb)}
                        />
                        <div className='min-w-0 flex-1 space-y-1.5'>
                          <div className='flex flex-wrap items-center gap-2'>
                            <span className='font-medium leading-tight'>{kb.name}</span>
                            <Badge variant='secondary' className='text-[10px] font-normal'>
                              {tl}
                            </Badge>
                            {isPrivate(kb) ? (
                              <Badge variant='outline' className='text-[10px] font-normal'>
                                私有
                              </Badge>
                            ) : null}
                          </div>
                          {kb.description ? (
                            <p className='line-clamp-2 text-xs leading-relaxed text-muted-foreground'>
                              {kb.description}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : null}
        </div>

        {!isPending && !isError && total > 0 && totalPages > 1 ? (
          <div className='flex shrink-0 items-center justify-between gap-2 border-t border-dashed pt-2'>
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='gap-1'
              disabled={page <= 1 || isFetching}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className='h-4 w-4' />
              上一页
            </Button>
            <span className='text-center text-[11px] text-muted-foreground'>
              {page} / {totalPages}
            </span>
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='gap-1'
              disabled={page >= totalPages || isFetching}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              下一页
              <ChevronRight className='h-4 w-4' />
            </Button>
          </div>
        ) : null}

        {pickedIds.length > 0 ? (
          <div className='shrink-0 rounded-lg border border-dashed border-primary/25 bg-primary/[0.04] px-3 py-2'>
            <p className='mb-1 text-[11px] font-medium text-muted-foreground'>本弹窗将添加</p>
            <p className='line-clamp-2 text-xs text-foreground/90'>{pickedSummary}</p>
          </div>
        ) : null}
      </div>

      <div className='flex shrink-0 items-center justify-end gap-2 border-t bg-muted/10 px-6 py-4'>
        <Button variant='outline' onClick={() => onOpenChange(false)}>
          取消
        </Button>
        <Button onClick={() => onConfirm(pickedIds)} disabled={pickedIds.length === 0}>
          确认添加{pickedIds.length > 0 ? `（${pickedIds.length}）` : ''}
        </Button>
      </div>
    </>
  )
}

export function KnowledgeBaseSelectorDialog({
  open,
  excludeIds,
  onOpenChange,
  onConfirm,
}: KnowledgeBaseSelectorDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='flex max-h-[min(640px,90vh)] flex-col gap-0 overflow-hidden p-0 sm:max-w-[520px]'>
        {open ? (
          <KnowledgeBaseSelectorDialogBody
            excludeIds={excludeIds}
            onOpenChange={onOpenChange}
            onConfirm={onConfirm}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
