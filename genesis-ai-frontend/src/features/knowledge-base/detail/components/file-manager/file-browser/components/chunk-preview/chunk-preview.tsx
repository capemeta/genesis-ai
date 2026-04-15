/**
 * 切片预览组件 - 主组件（精简版）
 *
 * 注意：这是精简后的主组件，只包含布局和数据流逻辑
 * 其他组件已提取到独立文件中
 */
import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Columns2,
  Maximize2,
  GitMerge,
  GitCommit,
  CornerDownRight,
  Search,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fetchChunkById } from '@/lib/api/chunks'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { DocumentPreview } from '../document-preview'

// 本地组件
import type { ChunkPreviewProps } from './types'
import { useChunkPreviewData } from './hooks/use-chunk-preview-data'
import { ScrollAssistButtons } from './components/scroll-assist-buttons'
import { SourceFilePreview } from './components/source-file-preview'
import { ChunkCard } from './components/chunk-card'
import { getChunkHierarchyRole } from './lib/hierarchy'

/**
 * 切片预览主组件
 * 双栏布局：左侧源文件预览，右侧切片列表
 */
export function ChunkPreview({
  fileName,
  kbDocId,
  kbType,
  kbDoc,
  onBack,
  onReparse,
}: ChunkPreviewProps) {
  const chunkListScrollRef = useRef<HTMLDivElement>(null)
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [showSourcePreview, setShowSourcePreview] = useState(true)
  const [selectedChunkId, setSelectedChunkId] = useState<number | null>(null)
  const [chunkIdKeyword, setChunkIdKeyword] = useState('')
  const [isSearchingChunkId, setIsSearchingChunkId] = useState(false)

  // 获取切片数据
  const [viewMode, setViewMode] = useState<
    'all' | 'leaf' | 'intermediate' | 'root'
  >('all')

  const switchViewMode = (nextViewMode: typeof viewMode) => {
    setPage(1)
    setViewMode(nextViewMode)
  }

  const handleSearchChunkById = async () => {
    const normalizedKeyword = chunkIdKeyword.trim()
    if (!normalizedKeyword) {
      toast.error('请输入分块 ID')
      return
    }

    if (!/^\d+$/.test(normalizedKeyword)) {
      toast.error('分块 ID 需为数字')
      return
    }

    setIsSearchingChunkId(true)
    try {
      const chunkId = Number(normalizedKeyword)
      const targetChunk = await fetchChunkById(chunkId)

      if (String(targetChunk.kb_doc_id) !== String(kbDocId)) {
        toast.error('该分块不属于当前文档')
        return
      }

      if (viewMode !== 'all') {
        const role = getChunkHierarchyRole(targetChunk)
        if (role !== viewMode) {
          toast.error('该分块不在当前筛选视图中，请先切换到“全部”')
          return
        }
      }

      const targetPage = Math.max(
        1,
        Math.ceil((Number(targetChunk.position) || 1) / pageSize)
      )
      setPage(targetPage)
      setSelectedChunkId(targetChunk.id)
      toast.success(`已定位到分块 ID: ${targetChunk.id}`)
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '分块查询失败，请稍后重试'
      toast.error(message)
    } finally {
      setIsSearchingChunkId(false)
    }
  }

  const {
    allChunks,
    chunkDepthMap,
    error,
    extension,
    fullDocumentChunkCount,
    hierarchyStats,
    isError,
    isLoading,
    isSourceLoading,
    pdfHighlights,
    sourceContent,
    sourceError,
    totalCount,
    totalPages,
  } = useChunkPreviewData({
    fileName,
    kbDocId,
    page,
    pageSize,
    selectedChunkId,
    showSourcePreview,
    viewMode,
  })

  useEffect(() => {
    if (!selectedChunkId) {
      return
    }
    const selectedElement = document.getElementById(`chunk-${selectedChunkId}`)
    selectedElement?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
  }, [allChunks, selectedChunkId, page])

  return (
    <div className='flex h-full flex-1 flex-col overflow-hidden'>
      {/* ============ 紧凑单行 Header ============ */}
      <div className='flex h-12 shrink-0 items-center gap-1.5 border-b bg-card px-3'>
        {/* 1. 返回按钮 */}
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant='ghost'
                size='icon'
                onClick={onBack}
                className='h-8 w-8 text-muted-foreground hover:text-foreground'
              >
                <ArrowLeft className='h-4 w-4' />
              </Button>
            </TooltipTrigger>
            <TooltipContent side='bottom' className='text-xs'>
              返回文件列表
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <div className='mx-0.5 h-5 w-px bg-slate-200' />

        {/* 2. 标题区域 */}
        <div className='flex min-w-0 flex-1 items-center gap-2'>
          <h2 className='text-sm font-bold whitespace-nowrap'>切片预览</h2>
          <span className='text-xs text-muted-foreground'>·</span>
          <span
            className='max-w-[300px] truncate text-sm text-muted-foreground'
            title={fileName}
          >
            {fileName}
          </span>
          <Badge
            variant='secondary'
            className='h-5 shrink-0 px-2 py-0 font-mono text-[11px]'
          >
            {viewMode === 'all' ? fullDocumentChunkCount : totalCount}
          </Badge>
        </div>

        {/* 3. 右侧操作区 */}
        <div className='flex shrink-0 items-center gap-1.5'>
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant='outline'
                  size='sm'
                  className={cn(
                    'h-8 gap-1.5 text-xs',
                    showSourcePreview
                      ? 'border-blue-200 bg-blue-50/80 text-blue-600'
                      : ''
                  )}
                  onClick={() => setShowSourcePreview(!showSourcePreview)}
                >
                  {showSourcePreview ? (
                    <Columns2 className='h-3.5 w-3.5' />
                  ) : (
                    <Maximize2 className='h-3.5 w-3.5' />
                  )}
                  {showSourcePreview ? '双栏' : '单栏'}
                </Button>
              </TooltipTrigger>
              <TooltipContent side='bottom' className='text-xs'>
                {showSourcePreview
                  ? '隐藏源文件预览，切片全屏'
                  : '显示源文件预览（双栏模式）'}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {onReparse && (
            <Button
              variant='outline'
              size='sm'
              className='h-8 gap-1.5 text-xs'
              onClick={onReparse}
            >
              <RefreshCw className='h-3.5 w-3.5' />
              重新解析
            </Button>
          )}
        </div>
      </div>

      {/* ============ 双栏内容区 ============ */}
      <div className='flex flex-1 overflow-hidden'>
        {/* 左侧：源文件预览区域 */}
        <div
          className={cn(
            'shrink-0 overflow-hidden border-r bg-muted/10 transition-all duration-300 ease-in-out',
            showSourcePreview
              ? 'w-[45%] opacity-100'
              : 'w-0 border-r-0 opacity-0'
          )}
        >
          <div className='flex h-full w-full flex-col'>
            {kbDoc ? (
              <DocumentPreview
                kbDocId={kbDocId}
                fileName={fileName}
                kbDoc={kbDoc}
                pdfHighlights={pdfHighlights}
              />
            ) : (
              <SourceFilePreview
                fileName={fileName}
                content={sourceContent}
                isLoading={isSourceLoading}
                error={sourceError}
              />
            )}
          </div>
        </div>

        {/* 右侧：切片列表 */}
        <div className='relative min-w-0 flex-1'>
          <div ref={chunkListScrollRef} className='h-full overflow-y-auto'>
            <div className='px-5 py-4'>
              {/* 状态统计条与过滤器 */}
              <div className='mb-4 flex flex-col gap-3'>
                <div className='flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-[11px] dark:border-slate-800 dark:bg-slate-900/50'>
                  {hierarchyStats.hasHierarchical && (
                    <div className='flex items-center gap-3 text-muted-foreground opacity-70'>
                      <span className='font-medium'>全文件结构</span>
                      <span className='opacity-40'>·</span>
                      <span>根块 {hierarchyStats.root}</span>
                      <span className='opacity-40'>·</span>
                      <span>中间块 {hierarchyStats.intermediate}</span>
                      <span className='opacity-40'>·</span>
                      <span>叶子块 {hierarchyStats.leaf}</span>
                    </div>
                  )}
                  <div className='ml-auto flex items-center gap-2 text-muted-foreground opacity-60'>
                    <span>当前视图共 {totalCount} 个切片</span>
                    <div className='h-3 w-px bg-slate-200 dark:bg-slate-700' />
                    <span>
                      第 {page}/{totalPages || 1} 页
                    </span>
                  </div>
                  <div className='ml-6 flex items-center gap-2'>
                    <span className='text-xs text-muted-foreground'>ID 搜索</span>
                  <Input
                    value={chunkIdKeyword}
                    onChange={e => setChunkIdKeyword(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        void handleSearchChunkById()
                      }
                    }}
                    placeholder='输入 ID，例如 1024'
                    className='h-7 w-[80px] bg-white text-xs dark:bg-slate-950'
                  />
                  <Button
                    type='button'
                    size='sm'
                    variant='outline'
                    className='h-7 gap-1.5 text-xs'
                    onClick={() => {
                      void handleSearchChunkById()
                    }}
                    disabled={isSearchingChunkId}
                  >
                    {isSearchingChunkId ? (
                      <Loader2 className='h-3.5 w-3.5 animate-spin' />
                    ) : (
                      <Search className='h-3.5 w-3.5' />
                    )}
                    定位
                  </Button>
                  </div>
                </div>

                {hierarchyStats.hasHierarchical && (
                  <div className='flex items-center gap-2'>
                    <Button
                      variant={viewMode === 'all' ? 'default' : 'outline'}
                      size='sm'
                      onClick={() => switchViewMode('all')}
                      className='h-7 px-3 text-[11px]'
                    >
                      全部
                    </Button>
                    <Button
                      variant={viewMode === 'leaf' ? 'default' : 'outline'}
                      size='sm'
                      onClick={() => switchViewMode('leaf')}
                      className={cn(
                        'h-7 border-emerald-200 px-3 text-[11px] hover:bg-emerald-50 dark:border-emerald-900',
                        viewMode === 'leaf' &&
                          'border-transparent bg-emerald-600 text-white hover:bg-emerald-700'
                      )}
                    >
                      <GitCommit className='mr-1 h-3 w-3' />
                      叶子块（检索单元）
                    </Button>
                    <Button
                      variant={viewMode === 'root' ? 'default' : 'outline'}
                      size='sm'
                      onClick={() => switchViewMode('root')}
                      className={cn(
                        'h-7 border-blue-200 px-3 text-[11px] hover:bg-blue-50 dark:border-blue-900',
                        viewMode === 'root' &&
                          'border-transparent bg-blue-600 text-white hover:bg-blue-700'
                      )}
                    >
                      <GitMerge className='mr-1 h-3 w-3' />
                      根块（章节大纲）
                    </Button>
                    <Button
                      variant={
                        viewMode === 'intermediate' ? 'default' : 'outline'
                      }
                      size='sm'
                      onClick={() => switchViewMode('intermediate')}
                      className={cn(
                        'h-7 border-amber-200 px-3 text-[11px] hover:bg-amber-50 dark:border-amber-900',
                        viewMode === 'intermediate' &&
                          'border-transparent bg-amber-600 text-white hover:bg-amber-700'
                      )}
                    >
                      <CornerDownRight className='mr-1 h-3 w-3' />
                      中间块（上下文层）
                    </Button>
                  </div>
                )}
              </div>

              {isLoading ? (
                <div className='flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/50 py-16 dark:border-slate-800 dark:bg-slate-900/50'>
                  <div className='flex flex-col items-center gap-3'>
                    <Loader2 className='h-8 w-8 animate-spin text-muted-foreground' />
                    <p className='text-sm text-muted-foreground'>
                      正在加载当前分块列表...
                    </p>
                  </div>
                </div>
              ) : isError ? (
                <div className='flex flex-col items-center justify-center gap-3 py-16'>
                  <AlertCircle className='h-12 w-12 text-destructive' />
                  <p className='text-sm text-muted-foreground'>加载切片失败</p>
                  <p className='text-xs text-muted-foreground'>
                    {error instanceof Error ? error.message : '未知错误'}
                  </p>
                </div>
              ) : !Array.isArray(allChunks) ? (
                <div className='flex flex-col items-center justify-center gap-3 py-16'>
                  <AlertCircle className='h-12 w-12 text-destructive' />
                  <p className='text-sm text-muted-foreground'>数据格式错误</p>
                </div>
              ) : (
                <>
                  {allChunks.length === 0 ? (
                    <div className='flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/50 py-16 dark:border-slate-800 dark:bg-slate-900/50'>
                      <AlertCircle className='h-8 w-8 text-slate-300' />
                      <p className='text-sm text-muted-foreground'>
                        该视图模式下暂无切片数据
                      </p>
                      {viewMode !== 'all' && (
                        <Button
                          variant='link'
                          size='sm'
                          onClick={() => switchViewMode('all')}
                          className='text-blue-500'
                        >
                          返回全部
                        </Button>
                      )}
                    </div>
                  ) : (
                    <div className='relative grid grid-cols-1 gap-4'>
                      {(() => {
                        return allChunks.map((chunk, index) => (
                          <ChunkCard
                            key={chunk.id}
                            chunk={chunk}
                            index={(page - 1) * pageSize + index}
                            depth={chunkDepthMap.get(chunk.id) ?? 0}
                            extension={extension}
                            kbType={kbType}
                            isSelected={
                              Number(chunk.id) === Number(selectedChunkId)
                            }
                            onSelect={setSelectedChunkId}
                          />
                        ))
                      })()}
                    </div>
                  )}

                  {/* 底部分页控制 */}
                  <div className='mt-6 flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900'>
                    <div className='flex items-center gap-2'>
                      <Button
                        variant='outline'
                        size='icon'
                        className='h-8 w-8'
                        onClick={() => setPage(1)}
                        disabled={page === 1}
                      >
                        <span className='text-[10px] font-bold'>&laquo;</span>
                      </Button>
                      <Button
                        variant='ghost'
                        size='icon'
                        className='h-8 w-8'
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                      >
                        <ChevronLeft className='h-4 w-4' />
                      </Button>
                    </div>

                    <div className='flex items-center gap-2'>
                      <div className='flex items-center gap-1.5 rounded-md border px-3 py-1'>
                        <span className='text-xs font-semibold text-blue-600'>
                          {page}
                        </span>
                        <span className='text-xs text-muted-foreground'>/</span>
                        <span className='text-xs text-muted-foreground'>
                          {totalPages || 1}
                        </span>
                      </div>
                    </div>

                    <div className='flex items-center gap-2'>
                      <Button
                        variant='ghost'
                        size='icon'
                        className='h-8 w-8'
                        onClick={() =>
                          setPage((p) => Math.min(totalPages, p + 1))
                        }
                        disabled={page >= totalPages}
                      >
                        <ChevronRight className='h-4 w-4' />
                      </Button>
                      <Button
                        variant='outline'
                        size='icon'
                        className='h-8 w-8'
                        onClick={() => setPage(totalPages)}
                        disabled={page >= totalPages}
                      >
                        <span className='text-[10px] font-bold'>&raquo;</span>
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
          <ScrollAssistButtons
            containerRef={chunkListScrollRef}
            watchDeps={[
              page,
              totalCount,
              allChunks.length,
              viewMode,
              isLoading,
            ]}
          />
        </div>
      </div>
    </div>
  )
}
