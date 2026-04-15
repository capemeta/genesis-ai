import { useQuery } from '@tanstack/react-query'
import {
  ArrowUpRight,
  ChevronRight,
  Loader2,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { fetchChunkByNodeId } from '@/lib/api/chunks'
import { FullHierarchyTreeNode } from './full-hierarchy-tree-node'

// ============================================================
// ParentChainNode - 父节点链递归组件
// ============================================================

interface ParentChainNodeProps {
  nodeId: string
  selectedNodeId: string | null
  expandedNodes: Set<string>
  onSelect: (nodeId: string) => void
  onToggle: (nodeId: string) => void
  initialChunkId?: string | null
  depth?: number
}

export function ParentChainNode({
  nodeId,
  selectedNodeId,
  expandedNodes,
  onSelect,
  onToggle,
  initialChunkId,
  depth = 0,
}: ParentChainNodeProps) {
  const { data: chunk, isLoading } = useQuery({
    queryKey: ['chunk', 'node', nodeId],
    queryFn: () => fetchChunkByNodeId(nodeId),
    staleTime: 1000 * 60 * 10,
  })

  const pId = chunk?.metadata_info?.parent_id
  const cIds = chunk?.metadata_info?.child_ids || []
  const isExpanded = expandedNodes.has(nodeId)
  const isSelected = selectedNodeId === nodeId
  const isInitialNode = nodeId === initialChunkId
  const hasChildren = cIds.length > 0
  const hasParent = !!pId

  if (isLoading) {
    return (
      <div className='flex items-center gap-2 py-2 text-xs text-muted-foreground'>
        <Loader2 className='h-3 w-3 animate-spin' />
        加载父节点...
      </div>
    )
  }

  return (
    <div className='relative'>
      {/* 递归展示父节点的父节点 */}
      {hasParent && (
        <div className='mb-3'>
          <ParentChainNode
            nodeId={pId}
            selectedNodeId={selectedNodeId}
            expandedNodes={expandedNodes}
            onSelect={onSelect}
            onToggle={onToggle}
            initialChunkId={initialChunkId}
            depth={depth + 1}
          />
          {/* 连接线 - 移除负值定位 */}
          <div className='my-1 flex justify-center'>
            <div className='h-3 w-0.5 bg-gradient-to-b from-amber-300 to-amber-200 dark:from-amber-700 dark:to-amber-800' />
          </div>
        </div>
      )}

      {/* 当前父节点 */}
      <div
        className={cn(
          'group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 transition-all',
          isSelected
            ? 'border-2 border-blue-400 bg-blue-100 dark:border-blue-600 dark:bg-blue-900/30'
            : isInitialNode
              ? 'border-2 border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-900/20'
              : 'border-2 border-transparent hover:bg-slate-100 dark:hover:bg-slate-800'
        )}
        style={{ marginLeft: `${depth * 20}px` }}
      >
        {/* 展开/折叠按钮 */}
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggle(nodeId)
            }}
            className='flex h-5 w-5 shrink-0 items-center justify-center rounded transition-colors hover:bg-slate-200 dark:hover:bg-slate-700'
          >
            <ChevronRight
              className={cn(
                'h-4 w-4 transition-transform',
                isExpanded && 'rotate-90'
              )}
            />
          </button>
        ) : (
          <div className='h-5 w-5 shrink-0' />
        )}

        {/* 节点内容 */}
        <div
          className='flex min-w-0 flex-1 items-center gap-2'
          onClick={() => onSelect(nodeId)}
        >
          {/* 层级图标 */}
          <div className='flex h-6 w-6 shrink-0 items-center justify-center rounded bg-amber-100 text-amber-600'>
            <ArrowUpRight className='h-3 w-3' />
          </div>

          {/* 节点信息 */}
          <div className='min-w-0 flex-1'>
            <div className='flex items-center gap-2'>
              <span className='truncate font-mono text-xs font-bold text-slate-600 dark:text-slate-400'>
                #{chunk?.position || String(nodeId).slice(0, 8)}
              </span>
              <Badge variant='secondary' className='h-4 px-1.5 text-[9px]'>
                {chunk?.token_count || 0}t
              </Badge>
            </div>
            <div className='mt-0.5 truncate text-[10px] text-muted-foreground'>
              {chunk?.content?.slice(0, 50) || '...'}
            </div>
          </div>

          {/* 子节点数量 */}
          {hasChildren && (
            <Badge variant='outline' className='h-5 shrink-0 px-1.5 text-[9px]'>
              {cIds.length}
            </Badge>
          )}

          {/* 节点状态标识统一放在最右侧，避免干扰左侧层级缩进视觉 */}
          {isInitialNode && !isSelected && (
            <div className='flex shrink-0 items-center gap-1 rounded-full bg-amber-500 px-2 py-0.5 text-[9px] font-bold text-white shadow-md'>
              <div className='h-1.5 w-1.5 animate-pulse rounded-full bg-white' />
              起点
            </div>
          )}

          {!isInitialNode && !isSelected && (
            <div className='shrink-0 rounded-full bg-amber-600 px-2 py-0.5 text-[9px] font-bold text-white shadow-sm'>
              父节点
            </div>
          )}
        </div>
      </div>

      {/* 递归渲染子节点（如果展开） */}
      {hasChildren && isExpanded && (
        <div className='mt-1 ml-6 border-l-2 border-dashed border-slate-200 pl-4 dark:border-slate-700'>
          {cIds.map((cid: unknown) => {
            const childNodeId = String(cid)
            return (
            <FullHierarchyTreeNode
              key={childNodeId}
              nodeId={childNodeId}
              selectedNodeId={selectedNodeId}
              expandedNodes={expandedNodes}
              onSelect={onSelect}
              onToggle={onToggle}
              depth={0}
              initialChunkId={initialChunkId}
            />
            )
          })}
        </div>
      )}
    </div>
  )
}
