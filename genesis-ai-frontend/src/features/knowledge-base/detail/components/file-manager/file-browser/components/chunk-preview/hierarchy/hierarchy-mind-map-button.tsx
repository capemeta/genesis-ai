import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowUpRight,
  GitCommit,
  GitMerge,
  Loader2,
  Maximize2,
} from 'lucide-react'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { fetchChunkByNodeId } from '@/lib/api/chunks'
import type { Chunk } from '../types'
import { getChunkNodeId } from '../lib/hierarchy'
import { ExcelSheetRootBadge } from '../components/badges'
import { FullHierarchyDialog } from './full-hierarchy-dialog'

// ============================================================
// HierarchyMindMapButton - 递归思维导图组件（改进版）
// ============================================================

export function HierarchyMindMapButton({
  chunk,
  direction = 'up',
  kbType,
}: {
  chunk: Chunk
  direction?: 'up' | 'down'
  kbType?: string
}) {
  const [isPopoverOpen, setIsPopoverOpen] = useState(false)
  const [isFullViewOpen, setIsFullViewOpen] = useState(false)
  const currentNodeId = getChunkNodeId(chunk)
  const pId = chunk.metadata_info?.parent_id
  const cIds = chunk.metadata_info?.child_ids || []

  // 层级树明确依赖 node_id，没有 node_id 时不展示该能力。
  if (!currentNodeId) return null

  // 如果是向上溯源且没有父类，则不显示
  if (direction === 'up' && !pId) return null

  // 如果是向下探测且没有子类，则不显示
  if (direction === 'down' && cIds.length === 0) return null

  const handleOpenFullView = () => {
    setIsPopoverOpen(false)
    setIsFullViewOpen(true)
  }

  return (
    <>
      <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
        <PopoverTrigger asChild>
          <button
            className={cn(
              'flex cursor-pointer items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] transition-all',
              direction === 'up'
                ? 'border-slate-100 bg-slate-50 text-slate-500 hover:border-amber-200 hover:bg-amber-50 hover:text-amber-600'
                : 'border-blue-100 bg-blue-50/50 text-blue-500 hover:border-blue-200 hover:bg-blue-100/50'
            )}
          >
            {direction === 'up' ? (
              <ArrowUpRight className='h-3 w-3' />
            ) : (
              <GitCommit className='h-3 w-3' />
            )}
            {direction === 'up' ? '查看溯源路径' : `${cIds.length} 个子节点`}
          </button>
        </PopoverTrigger>
        <PopoverContent
          className='shadow-3xl w-[600px] border-2 border-slate-300 bg-white p-0 dark:border-slate-700 dark:bg-slate-950'
          side='top'
          align='start'
        >
          <div className='flex items-center justify-between border-b-2 border-slate-200 bg-gradient-to-r from-slate-100 to-slate-50 p-3 dark:border-slate-700 dark:from-slate-800 dark:to-slate-900'>
            <div className='flex items-center gap-2'>
              <div
                className={cn(
                  'rounded-md p-1',
                  direction === 'up'
                    ? 'bg-amber-100 text-amber-600'
                    : 'bg-blue-100 text-blue-600'
                )}
              >
                <GitMerge className='h-4 w-4' />
              </div>
              <span className='text-xs font-bold'>
                {direction === 'up' ? '溯源 Lineage' : '子树结构 Descendants'}
              </span>
            </div>
            <div className='flex items-center gap-2'>
              <Badge variant='outline' className='text-[9px] opacity-60'>
                快速预览（最多 3 层）
              </Badge>
              <Button
                size='sm'
                className='h-6 gap-1 bg-blue-600 px-2 text-[10px] text-white hover:bg-blue-700'
                onClick={handleOpenFullView}
              >
                <Maximize2 className='h-3 w-3' />
                完整树
              </Button>
            </div>
          </div>
          <div className='max-h-[60vh] overflow-y-auto bg-slate-50/30 p-4 dark:bg-slate-900/30'>
            <div className='relative border-l-2 border-dashed border-slate-200 pl-4 dark:border-slate-700'>
              <HierarchyTreeNode
                nodeId={currentNodeId}
                initialData={chunk}
                mode={direction}
                isSelf={true}
                maxDepth={3}
              />
            </div>
          </div>
          <div className='flex items-center justify-between border-t-2 border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900/50'>
            <span className='text-[10px] text-muted-foreground'>
              点击 ID 可以快速定位当前页面的切片
            </span>
            <Button
              size='sm'
              className='h-7 gap-1.5 bg-blue-600 text-[11px] text-white hover:bg-blue-700'
              onClick={handleOpenFullView}
            >
              <Maximize2 className='h-3 w-3' />
              查看完整层级树
            </Button>
          </div>
        </PopoverContent>
      </Popover>

      {/* 全屏层级树视图 */}
      <FullHierarchyDialog
        chunk={chunk}
        kbType={kbType}
        open={isFullViewOpen}
        onOpenChange={setIsFullViewOpen}
      />
    </>
  )
}

function HierarchyTreeNode({
  nodeId,
  initialData,
  mode,
  isSelf = false,
  depth = 0,
  maxDepth = 3,
}: {
  nodeId: string
  initialData?: Chunk
  mode: 'up' | 'down'
  isSelf?: boolean
  depth?: number
  maxDepth?: number
}) {
  const { data: chunk, isLoading } = useQuery({
    queryKey: ['chunk', 'node', nodeId],
    queryFn: () => fetchChunkByNodeId(nodeId),
    initialData: initialData,
    staleTime: 1000 * 60 * 10,
  })

  const pId = chunk?.metadata_info?.parent_id
  const cIds = chunk?.metadata_info?.child_ids || []

  const scrollToChunk = () => {
    const targetChunkId = chunk?.id ?? initialData?.id
    const element = targetChunkId
      ? document.getElementById(`chunk-${targetChunkId}`)
      : null
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      element.classList.add('ring-2', 'ring-blue-400', 'ring-offset-2')
      setTimeout(() => {
        element.classList.remove('ring-2', 'ring-blue-400', 'ring-offset-2')
      }, 2000)
    }
  }

  if (isLoading)
    return (
      <div className='flex items-center justify-center gap-2 py-4 text-[10px] opacity-50'>
        <Loader2 className='h-3 w-3 animate-spin' /> 加载节点详情...
      </div>
    )

  return (
    <div className={cn('relative py-3', !isSelf && 'mt-1')}>
      {/* 溯源路径：自动递归父级 */}
      {mode === 'up' && pId && depth < maxDepth && (
        <div className='relative mb-3'>
          <HierarchyTreeNode
            nodeId={pId}
            mode='up'
            depth={depth + 1}
            maxDepth={maxDepth}
          />
          {/* 视觉连接线 */}
          <div className='absolute -bottom-3 left-1/2 h-3 w-0.5 -translate-x-1/2 bg-gradient-to-b from-slate-200 to-blue-200 dark:from-slate-800 dark:to-blue-900' />
        </div>
      )}

      <div
        onClick={scrollToChunk}
        className={cn(
          'group relative cursor-pointer rounded-xl border-2 bg-white p-4 shadow-md transition-all dark:bg-slate-900',
          isSelf
            ? 'z-10 border-blue-400 bg-blue-50/30 ring-2 ring-blue-500/10 dark:bg-blue-950/20'
            : depth === 0
              ? 'border-blue-200 hover:border-blue-400 dark:border-blue-900 dark:hover:border-blue-700'
              : depth === 1
                ? 'border-amber-200 hover:border-amber-400 dark:border-amber-900 dark:hover:border-amber-700'
                : 'border-emerald-200 hover:border-emerald-400 dark:border-emerald-900 dark:hover:border-emerald-700'
        )}
      >
        {/* 装饰物：如果是父节点显示一个小标签 */}
        {!isSelf && mode === 'up' && (
          <div className='absolute -top-2 left-4 rounded-full bg-amber-600 px-2 py-0.5 text-[9px] font-bold tracking-tighter text-white uppercase shadow-md dark:bg-amber-700'>
            父节点
          </div>
        )}

        {/* 当前节点标识 */}
        {isSelf && (
          <div className='absolute -top-2 left-4 flex items-center gap-1 rounded-full bg-blue-600 px-2 py-0.5 text-[9px] font-bold tracking-tighter text-white uppercase shadow-md dark:bg-blue-700'>
            <div className='h-1.5 w-1.5 animate-pulse rounded-full bg-white' />
            当前节点
          </div>
        )}

        <div className='mb-2 flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <span className='rounded bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] font-bold text-slate-400 dark:bg-slate-800'>
              {String(nodeId).slice(0, 8)}
              {isSelf && <span className='ml-1 text-blue-500'>(当前节点)</span>}
            </span>
            <ExcelSheetRootBadge chunk={chunk} />
            <div className='flex items-center gap-1.5'>
              <Badge
                variant='secondary'
                className='h-4 border-none bg-slate-100 px-1.5 text-[9px] text-slate-600 dark:bg-slate-800 dark:text-slate-400'
              >
                {chunk?.token_count || 0} tokens
              </Badge>
            </div>
          </div>
          {!isSelf && (
            <ArrowUpRight className='h-3 w-3 text-slate-300 transition-colors group-hover:text-blue-500' />
          )}
        </div>

        {/* 完整内容展示区域 */}
        <div className='custom-scrollbar max-h-[200px] overflow-y-auto rounded-lg border border-slate-100 bg-slate-50/50 p-2.5 text-xs leading-relaxed text-slate-700 italic dark:border-slate-800 dark:bg-slate-950/30 dark:text-slate-300'>
          {chunk?.content || '（内容为空或加载失败）'}
        </div>
      </div>

      {/* 子孙路径：自动递归子级 */}
      {mode === 'down' && cIds.length > 0 && depth < maxDepth && (
        <div className='mt-3 space-y-4 border-l-2 border-dashed border-blue-100 pl-6 dark:border-blue-900/30'>
          {cIds.map((cid: unknown) => {
            const childNodeId = String(cid)
            return (
            <HierarchyTreeNode
              key={childNodeId}
              nodeId={childNodeId}
              mode='down'
              depth={depth + 1}
              maxDepth={maxDepth}
            />
            )
          })}
        </div>
      )}
    </div>
  )
}
