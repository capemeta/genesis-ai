import { memo, useState, useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import { toast } from 'sonner'
import { withAppAssetPath } from '@/lib/app-base'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  BookOpen,
  Braces,
  Check,
  Code2,
  Copy,
  CornerDownRight,
  GitCommit,
  GitMerge,
  Heading,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { getChunkEnhancement, updateChunk } from '@/lib/api/chunks'
import type { Chunk } from '../types'
import {
  isHierarchyChunk,
  getChunkHierarchyRole,
} from '../lib/hierarchy'
import { isExcelRowParentChunk } from '../lib/excel'
import { ExcelSheetRootBadge, ExcelRowParentBadge } from './badges'
import { ChunkContentRenderer } from './chunk-content-renderer'
import { ChunkEditDialog } from './chunk-edit-dialog'
import { HierarchyMindMapButton } from '../hierarchy/hierarchy-mind-map-button'

// ============================================================
// ChunkCard - 单个切片卡片
// ============================================================

interface ChunkCardProps {
  chunk: Chunk
  index: number
  depth?: number
  extension?: string
  kbType?: string
  isSelected?: boolean
  onSelect?: (chunkId: number) => void
}

export const ChunkCard = memo(function ChunkCard({
  chunk,
  index,
  depth = 0,
  extension,
  kbType,
  isSelected = false,
  onSelect,
}: ChunkCardProps) {
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [showRaw, setShowRaw] = useState(false)
  const [showJsonDialog, setShowJsonDialog] = useState(false)
  const [isCopied, setIsCopied] = useState(false)
  const queryClient = useQueryClient()
  const isEdited = Boolean(chunk.is_content_edited)
  const isExcelRowParent = isExcelRowParentChunk(chunk)
  const isTableKnowledgeBase = kbType === 'table'

  // 限制最大缩进，防止深度太深导致内容过窄
  const safeDepth = Math.min(depth, 3)
  const indentSize = safeDepth * 24 // 基础缩进

  // 从 metadata_info 中提取页码信息
  const pageNumber =
    chunk.metadata_info?.page_number || chunk.metadata_info?.page || null
  const enhancement = getChunkEnhancement(chunk.metadata_info)
  const retrievalQuestions = enhancement.questions || []
  const keywords = enhancement.keywords || []
  // 完整标题：仅用层级路径（header_path / budget_header_text / prompt_header_text），不用当前节标题 heading
  const promptPaths = chunk.metadata_info?.prompt_header_paths
  const joinedPromptPaths =
    Array.isArray(promptPaths) && promptPaths.length > 0
      ? promptPaths.filter(Boolean).join(' / ')
      : ''
  const fullTitle =
    chunk.metadata_info?.header_path ||
    chunk.metadata_info?.budget_header_text ||
    chunk.metadata_info?.prompt_header_text ||
    joinedPromptPaths ||
    chunk.summary ||
    chunk.content?.split('\n')[0]?.trim().slice(0, 300) ||
    '（无完整标题）'

  // 切换激活状态
  const { mutate: toggleActive, isPending: isToggling } = useMutation({
    mutationFn: () =>
      updateChunk(chunk.id, {
        is_active: !chunk.is_active,
      }),
    onSuccess: () => {
      toast.success(chunk.is_active ? '已禁用切片' : '已启用切片')
      queryClient.invalidateQueries({ queryKey: ['chunks', chunk.kb_doc_id] })
    },
    onError: (error: unknown) => {
      const message =
        error instanceof AxiosError
          ? ((error.response?.data as { detail?: string } | undefined)?.detail ??
            error.message)
          : error instanceof Error
            ? error.message
            : '操作失败'
      toast.error(message)
    },
  })

  // 缓存渲染后的内容，避免切换原文/渲染视图时快速重排
  const renderedContent = useMemo(() => {
    return (
      <ChunkContentRenderer
        chunk={chunk}
        extension={extension}
        kbType={kbType}
      />
    )
  }, [chunk, extension, kbType])

  const formattedChunkJson = useMemo(
    () => JSON.stringify(chunk, null, 2),
    [chunk]
  )

  // 复制原始内容到剪贴板
  const handleCopyContent = async () => {
    try {
      await navigator.clipboard.writeText(chunk.content)
      setIsCopied(true)
      toast.success('已复制到剪贴板')
      setTimeout(() => setIsCopied(false), 2000)
    } catch (_error) {
      toast.error('复制失败')
    }
  }

  return (
    <>
      <div
        id={`chunk-${chunk.id}`} // Added ID for scrolling
        className='group relative cursor-pointer transition-all duration-300'
        style={{ marginLeft: safeDepth > 0 ? `${indentSize}px` : '0px' }}
        onClick={() => onSelect?.(Number(chunk.id))}
      >
        {/* 树状连接线 */}
        {safeDepth > 0 && (
          <div
            className='pointer-events-none absolute top-0 bottom-0 -left-4 w-px bg-slate-200 dark:bg-slate-700'
            style={{ left: '-16px' }}
          >
            <div className='absolute top-5 left-0 h-px w-4 bg-slate-200 dark:bg-slate-700' />
          </div>
        )}

        <div
          className={cn(
            'overflow-hidden rounded-lg border border-slate-200 bg-white/80 shadow-sm transition-all duration-300 dark:border-slate-700 dark:bg-slate-900/80',
            isExcelRowParent
              ? 'border-dashed border-slate-300 bg-slate-50/75 opacity-80 group-hover:border-slate-400 hover:bg-slate-100/80 hover:shadow-md dark:border-slate-700 dark:bg-slate-900/60 dark:group-hover:border-slate-600 dark:hover:bg-slate-800/80'
              : 'group-hover:border-blue-400 hover:scale-[1.005] hover:bg-gradient-to-br hover:shadow-xl dark:group-hover:border-blue-600',
            safeDepth === 0
              ? 'hover:from-blue-50/50 hover:to-indigo-50/30'
              : 'hover:from-slate-50 hover:to-blue-50/20',
            isSelected &&
              'border-blue-400 ring-2 ring-blue-400 dark:border-blue-500 dark:ring-blue-500'
          )}
        >
          {/* Header: 元数据与层级标识 */}
          <div
            className={cn(
              'flex items-center justify-between border-b px-4 py-2',
              isExcelRowParent &&
                'border-slate-200 bg-slate-100/80 dark:border-slate-700 dark:bg-slate-800/70',
              safeDepth === 0
                ? 'bg-slate-50/80 dark:bg-slate-800/80'
                : 'bg-white/40 dark:bg-slate-800/40'
            )}
          >
            <div className='flex items-center gap-2.5 overflow-hidden'>
              {/* 层级 Badge */}
              {(() => {
                const childIds = chunk.metadata_info?.child_ids || []
                const hasChildren = childIds.length > 0
                const hasParent =
                  (chunk.parent_id || chunk.metadata_info?.parent_id) !== null
                const isHierarchical = isHierarchyChunk(chunk)

                if (!isHierarchical) return null

                const hierarchyRole = getChunkHierarchyRole(chunk, safeDepth)

                if (hierarchyRole === 'root') {
                  // 纯根块（有子块的章节）
                  return (
                    <div className='flex items-center gap-2'>
                      <Badge
                        variant='outline'
                        className='h-5 shrink-0 border-blue-200 bg-blue-50 px-1.5 text-[10px] text-blue-600'
                      >
                        <GitMerge className='mr-1 h-3 w-3' /> 根块（章节大纲）
                      </Badge>
                      {hasChildren && (
                        <div className='ml-1 flex items-center'>
                          <HierarchyMindMapButton
                            chunk={chunk}
                            direction='down'
                            kbType={kbType}
                          />
                        </div>
                      )}
                    </div>
                  )
                } else if (hierarchyRole === 'intermediate') {
                  // 中间块（有父有子）
                  return (
                    <div className='flex items-center gap-2'>
                      <Badge
                        variant='outline'
                        className='h-5 shrink-0 border-amber-200 bg-amber-50 px-1.5 text-[10px] font-medium text-amber-600'
                      >
                        <CornerDownRight className='mr-1 h-3 w-3' />{' '}
                        中间块（上下文层）
                      </Badge>
                      <div className='flex items-center gap-1'>
                        <HierarchyMindMapButton
                          chunk={chunk}
                          direction='up'
                          kbType={kbType}
                        />
                        {hasChildren && (
                          <HierarchyMindMapButton
                            chunk={chunk}
                            direction='down'
                            kbType={kbType}
                          />
                        )}
                      </div>
                    </div>
                  )
                } else {
                  // 叶子块（含独立块的无子节点情况）
                  return (
                    <div className='flex items-center gap-2'>
                      <Badge
                        variant='outline'
                        className='h-5 shrink-0 border-emerald-200 bg-emerald-50 px-1.5 text-[10px] text-emerald-600'
                      >
                        <GitCommit className='mr-1 h-3 w-3' />{' '}
                        叶子块（检索单元）
                      </Badge>
                      {hasParent && (
                        <div className='ml-1 flex items-center'>
                          <HierarchyMindMapButton
                            chunk={chunk}
                            direction='up'
                            kbType={kbType}
                          />
                        </div>
                      )}
                    </div>
                  )
                }
              })()}

              <span className='font-mono text-xs font-bold text-slate-400'>
                #{chunk.position || index + 1}
              </span>
              <Badge
                variant='outline'
                className='h-5 shrink-0 border-slate-200 bg-slate-50 px-1.5 font-mono text-[10px] text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
              >
                ID: {String(chunk.id)}
              </Badge>

              <ExcelSheetRootBadge chunk={chunk} />
              <ExcelRowParentBadge chunk={chunk} />

              <div className='hidden items-center gap-2 text-muted-foreground sm:flex'>
                <span className='text-[10px] text-muted-foreground'>·</span>
                <span className='text-xs whitespace-nowrap'>
                  {chunk.token_count || 0} tokens
                </span>
                <span className='text-[10px] text-muted-foreground'>·</span>
                <span className='text-xs whitespace-nowrap'>
                  {chunk.text_length || chunk.content.length} chars
                </span>
                {pageNumber && (
                  <>
                    <span className='text-[10px] text-muted-foreground'>·</span>
                    <span className='text-xs'>P{pageNumber}</span>
                  </>
                )}
              </div>

              {isEdited && (
                <Badge
                  variant='outline'
                  className='h-5 shrink-0 border-orange-300 bg-orange-100 px-1.5 text-[10px] font-semibold text-orange-700 dark:border-orange-800 dark:bg-orange-950/40 dark:text-orange-300'
                >
                  已编辑
                </Badge>
              )}

              {/* 父节点上下文提示 (如果父节点不在当前页) */}
              {/* Replaced by HierarchyMindMapButton */}
            </div>

            <div className='flex shrink-0 items-center gap-2'>
              <div className='flex items-center gap-1.5'>
                <Switch
                  checked={chunk.is_active}
                  onCheckedChange={() => toggleActive()}
                  disabled={isToggling}
                  className='scale-75'
                />
              </div>
              <TooltipProvider delayDuration={0}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant='ghost'
                      size='icon'
                      className='pointer-events-auto h-7 w-7 cursor-default'
                      tabIndex={-1}
                    >
                      <Heading className='h-3.5 w-3.5 text-muted-foreground' />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent
                    side='bottom'
                    className='max-w-md text-xs break-words whitespace-pre-wrap'
                  >
                    {fullTitle}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider delayDuration={0}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant='ghost'
                      size='icon'
                      className={cn(
                        'h-7 w-7 transition-colors',
                        isCopied &&
                          'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400'
                      )}
                      onClick={handleCopyContent}
                      title='复制原始内容'
                    >
                      {isCopied ? (
                        <Check className='h-3.5 w-3.5' />
                      ) : (
                        <Copy className='h-3.5 w-3.5' />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side='bottom' className='text-xs'>
                    {isCopied ? '已复制' : '复制原始内容'}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider delayDuration={0}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant='ghost'
                      size='icon'
                      className={cn(
                        'h-7 w-7',
                        showJsonDialog && 'bg-slate-100 dark:bg-slate-700'
                      )}
                      onClick={() => setShowJsonDialog(true)}
                      title='查看分块 JSON 数据'
                    >
                      <Braces className='h-3.5 w-3.5' />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side='bottom' className='text-xs'>
                    查看分块 JSON 数据
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button
                variant='ghost'
                size='icon'
                className={cn(
                  'h-7 w-7',
                  showRaw && 'bg-amber-50 text-amber-600'
                )}
                onClick={() => setShowRaw(!showRaw)}
                title={showRaw ? '渲染视图' : '查看原文'}
              >
                {showRaw ? (
                  <BookOpen className='h-3.5 w-3.5' />
                ) : (
                  <Code2 className='h-3.5 w-3.5' />
                )}
              </Button>
              <Button
                variant='ghost'
                size='icon'
                className='h-7 w-7'
                onClick={() => setIsEditDialogOpen(true)}
                title={
                  isTableKnowledgeBase
                    ? '查看切片详情（内容只读）'
                    : '编辑切片'
                }
              >
                <img
                  src={withAppAssetPath('icons/icon_edit_chunk.svg')}
                  alt='edit'
                  className='h-4 w-4'
                />
              </Button>
            </div>
          </div>

          <div className='px-4 py-3'>
            {chunk.summary && (
              <div className='mb-2.5 rounded-md border border-blue-100 bg-blue-50/50 p-2.5 dark:border-blue-900/50 dark:bg-blue-950/20'>
                <div className='mb-1 flex items-center gap-1.5'>
                  <div className='h-3 w-1 rounded-full bg-blue-400' />
                  <span className='text-[11px] font-bold tracking-wider text-blue-600 uppercase'>
                    摘要
                  </span>
                </div>
                <p className='text-xs leading-relaxed text-slate-600 italic dark:text-slate-300'>
                  {chunk.summary}
                </p>
              </div>
            )}

            {/* 内容渲染区域 */}
            <div
              className={cn(
                'min-h-[40px]',
                safeDepth > 0 && 'text-slate-700 dark:text-slate-300'
              )}
            >
              {showRaw ? (
                <div className='relative'>
                  <pre className='overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap text-slate-300 shadow-inner'>
                    {chunk.content}
                  </pre>
                  <Badge
                    variant='outline'
                    className='absolute top-2 right-2 border-slate-700 bg-slate-800 text-[9px] text-slate-400'
                  >
                    RAW
                  </Badge>
                </div>
              ) : (
                renderedContent
              )}
            </div>

            {(retrievalQuestions.length > 0 || keywords.length > 0) && (
              <div className='mt-3 space-y-3 border-t border-slate-100 pt-3 dark:border-slate-800'>
                {retrievalQuestions.length > 0 && (
                  <div className='space-y-1.5'>
                    <div className='flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-emerald-700 dark:text-emerald-400'>
                      <span className='h-3 w-1 rounded-full bg-emerald-500' />
                      <span>检索问题</span>
                    </div>
                    <div className='flex flex-wrap gap-2'>
                      {retrievalQuestions.map((q: string, idx: number) => (
                        <div
                          key={idx}
                          className='inline-flex items-center gap-1.5 rounded-md border border-emerald-100 bg-emerald-50/50 px-2 py-1 text-xs text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-400'
                        >
                          <span className='font-bold opacity-70'>#{idx + 1}</span>
                          <span className='max-w-[220px] truncate'>{q}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {keywords.length > 0 && (
                  <div className='space-y-1.5'>
                    <div className='flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-blue-700 dark:text-blue-400'>
                      <span className='h-3 w-1 rounded-full bg-blue-500' />
                      <span>关键词</span>
                    </div>
                    <div className='flex flex-wrap gap-2'>
                      {keywords.map((keyword: string) => (
                        <div
                          key={keyword}
                          className='inline-flex items-center rounded-md border border-blue-100 bg-blue-50/50 px-2 py-1 text-xs text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-400'
                        >
                          <span className='max-w-[220px] truncate'>{keyword}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 分块 JSON 数据弹窗 */}
      <Dialog open={showJsonDialog} onOpenChange={setShowJsonDialog}>
        <DialogContent className='flex max-h-[85vh] max-w-3xl flex-col'>
          <DialogHeader>
            <DialogTitle className='flex items-center gap-2'>
              <Braces className='h-5 w-5' />
              分块 #{chunk.position ?? index + 1} JSON 数据
            </DialogTitle>
            <DialogDescription>
              当前分块的完整 JSON 结构，便于调试与对接。
            </DialogDescription>
          </DialogHeader>
          <div className='flex min-h-0 flex-1 flex-col gap-2 overflow-hidden'>
            <pre className='flex-1 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap text-slate-300'>
              {formattedChunkJson}
            </pre>
            <DialogFooter className='shrink-0'>
              <Button
                variant='outline'
                size='sm'
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      formattedChunkJson
                    )
                    toast.success('JSON 已复制到剪贴板')
                  } catch {
                    toast.error('复制失败')
                  }
                }}
              >
                <Copy className='mr-1.5 h-3.5 w-3.5' />
                复制 JSON
              </Button>
              <Button
                variant='secondary'
                size='sm'
                onClick={() => setShowJsonDialog(false)}
              >
                关闭
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      <ChunkEditDialog
        chunk={chunk}
        open={isEditDialogOpen}
        kbType={kbType}
        onOpenChange={setIsEditDialogOpen}
      />
    </>
  )
})
