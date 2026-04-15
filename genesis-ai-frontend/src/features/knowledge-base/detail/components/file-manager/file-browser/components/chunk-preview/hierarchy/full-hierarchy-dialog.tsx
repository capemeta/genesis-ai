import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, GitMerge, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { fetchChunkByNodeId } from '@/lib/api/chunks'
import type { Chunk } from '../types'
import { getChunkNodeId } from '../lib/hierarchy'
import { ScrollAssistButtons } from '../components/scroll-assist-buttons'
import { FullHierarchyTreeNode } from './full-hierarchy-tree-node'
import { FullHierarchyDetailView } from './full-hierarchy-detail-view'

// ============================================================
// FullHierarchyDialog - 全屏层级树视图
// ============================================================

interface FullHierarchyDialogProps {
  chunk: Chunk
  open: boolean
  kbType?: string
  onOpenChange: (open: boolean) => void
}

export function FullHierarchyDialog({
  chunk,
  open,
  kbType,
  onOpenChange,
}: FullHierarchyDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <FullHierarchyDialogContent
          key={chunk.id}
          chunk={chunk}
          kbType={kbType}
          onOpenChange={onOpenChange}
        />
      )}
    </Dialog>
  )
}

function FullHierarchyDialogContent({
  chunk,
  kbType,
  onOpenChange,
}: {
  chunk: Chunk
  kbType?: string
  onOpenChange: (open: boolean) => void
}) {
  const treeScrollRef = useRef<HTMLDivElement>(null)
  const detailScrollRef = useRef<HTMLDivElement>(null)
  const initialNodeId = getChunkNodeId(chunk)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(
    initialNodeId
  )
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(
    new Set(initialNodeId ? [initialNodeId] : [])
  )
  const initialChunkId = initialNodeId

  const { data: selectedChunk } = useQuery({
    queryKey: ['chunk', 'node', selectedNodeId],
    queryFn: () => fetchChunkByNodeId(selectedNodeId!),
    enabled: Boolean(selectedNodeId) && selectedNodeId !== initialNodeId,
    staleTime: 1000 * 60 * 10,
  })

  const currentChunk = selectedNodeId === initialNodeId ? chunk : selectedChunk

  const toggleNode = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const nextExpandedNodes = new Set(prev)
      if (nextExpandedNodes.has(nodeId)) {
        nextExpandedNodes.delete(nodeId)
      } else {
        nextExpandedNodes.add(nodeId)
      }
      return nextExpandedNodes
    })
  }

  return (
    <DialogContent className='flex h-[92vh] w-[98vw] !max-w-none flex-col p-0'>
      {/* Header */}
      <div className='shrink-0 border-b bg-gradient-to-r from-slate-50 to-blue-50/30 px-6 py-4 dark:from-slate-900 dark:to-blue-950/30'>
        <DialogTitle className='flex items-center gap-3 text-lg font-bold'>
          <div className='rounded-lg bg-blue-100 p-2 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'>
            <GitMerge className='h-5 w-5' />
          </div>
          完整层级树视图
          <Badge variant='secondary' className='text-xs'>
            无限深度递归
          </Badge>
        </DialogTitle>
        <DialogDescription className='mt-2 text-sm'>
          探索完整的切片层级关系，支持无限深度展开。左侧树形结构，右侧详细内容。
        </DialogDescription>
      </div>

      {/* Content: 左右分栏 */}
      <div className='flex flex-1 overflow-hidden'>
        {/* 左侧：树形结构 */}
        <div className='relative w-[40%] border-r bg-slate-50/50 dark:bg-slate-900/50'>
          <div ref={treeScrollRef} className='h-full overflow-y-auto'>
            <div className='p-4'>
              <div className='mb-3 flex min-h-[24px] items-center gap-2 text-xs text-muted-foreground'>
                <BookOpen className='h-4 w-4 shrink-0' />
                <span className='leading-none'>
                  点击节点查看详情，点击箭头展开/折叠
                </span>
              </div>
              <div className='relative'>
                {initialNodeId ? (
                  <FullHierarchyTreeNode
                    nodeId={initialNodeId}
                    initialData={chunk}
                    selectedNodeId={selectedNodeId}
                    expandedNodes={expandedNodes}
                    onSelect={setSelectedNodeId}
                    onToggle={toggleNode}
                    isRoot={true}
                    initialChunkId={initialChunkId}
                  />
                ) : (
                  <div className='rounded-lg border border-dashed p-4 text-sm text-muted-foreground'>
                    当前切片没有 node_id，暂不支持层级树查询。
                  </div>
                )}
              </div>
            </div>
          </div>
          <ScrollAssistButtons
            containerRef={treeScrollRef}
            watchDeps={[selectedNodeId, expandedNodes.size]}
            className='right-3'
          />
        </div>

        {/* 右侧：详细内容 */}
        <div className='relative flex-1 bg-white dark:bg-slate-950'>
          <div ref={detailScrollRef} className='h-full overflow-y-auto'>
            <div className='p-6'>
              {currentChunk ? (
                <FullHierarchyDetailView chunk={currentChunk} kbType={kbType} />
              ) : (
                <div className='flex h-full items-center justify-center'>
                  <Loader2 className='h-8 w-8 animate-spin text-muted-foreground' />
                </div>
              )}
            </div>
          </div>
          <ScrollAssistButtons
            containerRef={detailScrollRef}
            watchDeps={[selectedNodeId, currentChunk?.id]}
            className='right-3'
          />
        </div>
      </div>

      {/* Footer */}
      <div className='flex shrink-0 items-center justify-between border-t bg-slate-50 px-6 py-3 dark:bg-slate-900/50'>
        <div className='text-xs text-muted-foreground'>
          当前选中:{' '}
          <span className='font-mono font-bold text-blue-600 dark:text-blue-400'>
            {String(selectedNodeId).slice(0, 12)}
          </span>
        </div>
        <Button
          variant='outline'
          size='sm'
          onClick={() => onOpenChange(false)}
        >
          关闭
        </Button>
      </div>
    </DialogContent>
  )
}
