import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import {
  Plus,
  Search,
  Grid3x3,
  List,
  MoreHorizontal,
  FileText,
  MessageSquare,
  Table as TableIcon,
  Globe,
  Puzzle,
  Mic,
  Database,
  Clock,
  Package,
  ChevronLeft,
  ChevronRight,
  Tags,
} from 'lucide-react'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { getPageNumbers } from '@/lib/utils'
import { CreateKnowledgeBaseModal } from '@/features/knowledge-base/components/create-kb-modal'
import { toast } from 'sonner'
import { createKnowledgeBase, deleteKnowledgeBase, fetchKnowledgeBases, setKnowledgeBaseTags, type KnowledgeBase } from '@/lib/api/knowledge-base'
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { getKnowledgeBaseTags } from '@/lib/api/knowledge-base'

const KB_TYPE_CONFIG: Record<string, { icon: any; color: string; bgColor: string }> = {
  general: { icon: FileText, color: 'text-blue-500', bgColor: 'bg-blue-500/10' },
  qa: { icon: MessageSquare, color: 'text-green-500', bgColor: 'bg-green-500/10' },
  table: { icon: TableIcon, color: 'text-orange-500', bgColor: 'bg-orange-500/10' },
  web: { icon: Globe, color: 'text-cyan-500', bgColor: 'bg-cyan-500/10' },
  media: { icon: Mic, color: 'text-red-500', bgColor: 'bg-red-500/10' },
  connector: { icon: Puzzle, color: 'text-purple-500', bgColor: 'bg-purple-500/10' },
}

export const Route = createFileRoute('/_top-nav/knowledge-base/')({
  component: KnowledgeBasePage,
})

function KnowledgeBasePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [currentPage, setCurrentPage] = useState(1)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [kbToDelete, setKbToDelete] = useState<KnowledgeBase | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('created_at')
  const [selectedTagIds, setSelectedTagIds] = useState<Set<string>>(new Set())
  const [isTagPopoverOpen, setIsTagPopoverOpen] = useState(false)
  const pageSize = 8

  // Fetch data using React Query
  const { data, isLoading } = useQuery({
    queryKey: ['knowledge-bases', currentPage, search, sortBy],
    queryFn: () => fetchKnowledgeBases({
      page: currentPage,
      page_size: pageSize,
      search: search || undefined,
      sort_by: sortBy,
      sort_order: 'desc'
    }),
  })

  // Calculate pagination
  const totalPages = data ? Math.ceil(data.total / pageSize) : 0
  const pageNumbers = getPageNumbers(currentPage, totalPages)
  const tagQueries = useQueries({
    queries: (data?.data || []).map((kb) => ({
      queryKey: ['kb-tags', kb.id, 'list-card'],
      queryFn: async () => (await getKnowledgeBaseTags(kb.id)).tags,
      enabled: !!kb.id,
      staleTime: 60 * 1000,
      refetchOnWindowFocus: false,
    })),
  })
  const kbTagsMap = useMemo(
    () =>
      (data?.data || []).reduce<Record<string, Awaited<ReturnType<typeof getKnowledgeBaseTags>>['tags']>>((acc, kb, index) => {
        acc[kb.id] = tagQueries[index]?.data || []
        return acc
      }, {}),
    [data?.data, tagQueries]
  )
  const pageTagOptions = useMemo(() => {
    const tagMap = new Map<string, { id: string; name: string }>()
    Object.values(kbTagsMap).forEach((tags) => {
      tags.forEach((tag) => {
        if (!tagMap.has(tag.id)) {
          tagMap.set(tag.id, { id: tag.id, name: tag.name })
        }
      })
    })
    return Array.from(tagMap.values()).sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
  }, [kbTagsMap])
  const filteredKnowledgeBases = useMemo(() => {
    if (!data?.data) return []
    if (selectedTagIds.size === 0) return data.data
    return data.data.filter((kb) => {
      const tags = kbTagsMap[kb.id] || []
      const tagIds = new Set(tags.map((tag) => tag.id))
      return Array.from(selectedTagIds).every((tagId) => tagIds.has(tagId))
    })
  }, [data?.data, kbTagsMap, selectedTagIds])

  const handleCreateKB = async (values: any) => {
    try {
      const created = await createKnowledgeBase({
        name: values.name,
        description: values.description,
        type: values.type as any,
      })
      if (Array.isArray(values.tagIds) && values.tagIds.length > 0) {
        await setKnowledgeBaseTags(created.id, values.tagIds)
      }
      toast.success(`知识库「${values.name}」已创建`, {
        description: '现在可以开始上传文档并进行索引了',
      })
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      await navigate({
        to: '/knowledge-base/$folderId',
        params: { folderId: created.id },
        search: { initialTab: undefined, tableGuide: undefined },
      })
    } catch (error: any) {
      toast.error('创建知识库失败', {
        description: error.response?.data?.detail || '请稍后再试',
      })
      throw error
    }
  }

  const handleDeleteKB = async () => {
    if (!kbToDelete) return

    setIsDeleting(true)
    try {
      await deleteKnowledgeBase(kbToDelete.id)
      toast.success(`知识库「${kbToDelete.name}」已删除`)
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setKbToDelete(null)
    } catch (error: any) {
      toast.error('删除知识库失败', {
        description: error.response?.data?.detail || '请稍后再试',
      })
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div className='w-full px-6 md:px-8 lg:px-12 xl:px-16 py-8 max-w-[1920px] mx-auto'>
      {/* Header */}
      <div className='mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4'>
        <div>
          <h1 className='text-3xl font-bold tracking-tight mb-2'>我的知识库</h1>
          <p className='text-muted-foreground max-w-2xl text-balance'>
            管理 RAG 检索的数据源，组织文档内容，追踪分块数量，监控索引状态
          </p>
        </div>
        <Button className='shrink-0 shadow-sm bg-blue-600 hover:bg-blue-700 text-white' onClick={() => setIsCreateModalOpen(true)}>
          <Plus className='mr-2 h-4 w-4' />
          新建知识库
        </Button>
      </div>

      {/* Toolbar */}
      <div className='flex flex-col sm:flex-row items-center justify-between gap-4 mb-8 bg-muted/30 p-4 rounded-xl border'>
        <div className='flex items-center gap-4 w-full sm:w-auto flex-1'>
          {/* Search */}
          <div className='relative w-full max-w-md'>
            <Search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
            <Input
              type='search'
              placeholder='搜索知识库...'
              className='pl-9 bg-background'
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {/* Sort */}
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className='w-[160px] bg-background'>
              <SelectValue placeholder='排序方式' />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='created_at'>按时间排序</SelectItem>
              <SelectItem value='name'>按名称排序</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className='flex items-center gap-4 shrink-0'>
          <Popover open={isTagPopoverOpen} onOpenChange={setIsTagPopoverOpen}>
            <PopoverTrigger asChild>
              <Button variant='outline' className='gap-2 bg-background'>
                <Tags className='h-4 w-4' />
                本页标签筛选
                {selectedTagIds.size > 0 ? (
                  <Badge variant='secondary' className='ml-1 h-5 px-1.5 text-[10px]'>
                    {selectedTagIds.size}
                  </Badge>
                ) : null}
              </Button>
            </PopoverTrigger>
            <PopoverContent align='end' className='w-80 space-y-3'>
              <div className='space-y-1'>
                <h4 className='text-sm font-semibold'>按标签筛选当前页知识库</h4>
                <p className='text-xs leading-relaxed text-muted-foreground'>
                  这里只筛选当前已加载结果，不改变服务端分页与总数，适合快速缩小当前视图范围。
                </p>
              </div>
              <div className='max-h-56 overflow-y-auto rounded-lg border p-2'>
                {pageTagOptions.length === 0 ? (
                  <div className='py-6 text-center text-sm text-muted-foreground'>当前页暂无标签可筛选</div>
                ) : (
                  <div className='flex flex-wrap gap-2'>
                    {pageTagOptions.map((tag) => {
                      const active = selectedTagIds.has(tag.id)
                      return (
                        <button
                          key={tag.id}
                          type='button'
                          onClick={() => {
                            setSelectedTagIds((prev) => {
                              const next = new Set(prev)
                              if (next.has(tag.id)) {
                                next.delete(tag.id)
                              } else {
                                next.add(tag.id)
                              }
                              return next
                            })
                          }}
                          className={active
                            ? 'rounded-full border border-blue-500 bg-blue-50 px-3 py-1.5 text-xs text-blue-700'
                            : 'rounded-full border border-border bg-background px-3 py-1.5 text-xs hover:border-blue-300 hover:bg-blue-50/60'}
                        >
                          {tag.name}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
              {selectedTagIds.size > 0 ? (
                <div className='flex justify-end'>
                  <Button variant='ghost' size='sm' onClick={() => setSelectedTagIds(new Set())}>
                    清空筛选
                  </Button>
                </div>
              ) : null}
            </PopoverContent>
          </Popover>

          {/* View Toggle */}
          <div className='flex items-center gap-1 border rounded-lg p-1 bg-background'>
            <Button
              variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
              size='icon'
              className='h-8 w-8'
              onClick={() => setViewMode('grid')}
            >
              <Grid3x3 className='h-4 w-4' />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              size='icon'
              className='h-8 w-8'
              onClick={() => setViewMode('list')}
            >
              <List className='h-4 w-4' />
            </Button>
          </div>
        </div>
      </div>

      {/* Knowledge Base Grid/List */}
      {isLoading ? (
        <div className='flex items-center justify-center min-h-[400px]'>
          <div className='flex flex-col items-center gap-4'>
            <div className='h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent' />
            <p className='text-muted-foreground'>正在加载知识库...</p>
          </div>
        </div>
      ) : !data || data.data.length === 0 ? (
        <div className='flex flex-col items-center justify-center min-h-[400px] border-2 border-dashed rounded-3xl bg-muted/5'>
          <div className='bg-primary/10 p-6 rounded-full mb-6'>
            <Database className='h-12 w-12 text-primary' />
          </div>
          <h3 className='text-xl font-bold mb-2'>暂无知识库</h3>
          <p className='text-muted-foreground text-center max-w-sm mb-8'>
            您还没有创建过任何知识库。立即创建一个，开始构建您的专属 AI 知识库。
          </p>
          <Button className='bg-blue-600 hover:bg-blue-700 text-white' onClick={() => setIsCreateModalOpen(true)}>
            <Plus className='mr-2 h-4 w-4' />
            新建知识库
          </Button>
        </div>
      ) : filteredKnowledgeBases.length === 0 ? (
        <div className='flex flex-col items-center justify-center min-h-[280px] rounded-3xl border border-dashed bg-muted/10'>
          <Tags className='mb-4 h-10 w-10 text-muted-foreground/60' />
          <h3 className='mb-2 text-lg font-semibold'>当前页没有匹配的知识库</h3>
          <p className='mb-6 text-sm text-muted-foreground'>可以清空本页标签筛选，或切换分页查看其它结果。</p>
          <Button variant='outline' onClick={() => setSelectedTagIds(new Set())}>
            清空筛选
          </Button>
        </div>
      ) : viewMode === 'grid' ? (
        <div className='grid gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5'>
          {/* Knowledge Base Cards：覆盖 Card 默认 py-6/gap-6，去掉底部大块留白 */}
          {filteredKnowledgeBases.map((kb) => {
            const kbType = (kb.type || 'general').toLowerCase()
            const config = KB_TYPE_CONFIG[kbType] || KB_TYPE_CONFIG.general
            const Icon = config.icon
            const kbTags = kbTagsMap[kb.id] || []
            return (
              <Link
                key={kb.id}
                to='/knowledge-base/$folderId'
                params={{ folderId: kb.id }}
                search={{ initialTab: undefined, tableGuide: undefined }}
              >
                <Card className='h-full gap-0 border-muted/60 py-0 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg group'>
                  <CardHeader className='p-4'>
                    <div className='flex items-start justify-between'>
                      <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-lg ${config.bgColor} shadow-sm transition-transform group-hover:scale-105`}>
                        <Icon className={`h-5 w-5 ${config.color}`} />
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.preventDefault()}>
                          <Button variant='ghost' size='icon' className='-mr-1 -mt-1 h-7 w-7'>
                            <MoreHorizontal className='h-4 w-4 text-muted-foreground' />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align='end'>
                          <DropdownMenuItem
                            onClick={() => {
                              void navigate({
                                to: '/knowledge-base/$folderId',
                                params: { folderId: kb.id },
                                search: { initialTab: undefined, tableGuide: undefined },
                              })
                            }}
                          >
                            打开知识库
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className='text-destructive focus:bg-destructive/10 focus:text-destructive'
                            onClick={(e) => {
                              e.preventDefault()
                              setKbToDelete(kb)
                            }}
                          >
                            删除
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    <CardTitle className='text-base transition-colors group-hover:text-primary line-clamp-1'>{kb.name}</CardTitle>
                    <CardDescription className='mt-1 min-h-[32px] text-xs line-clamp-2'>
                      {kb.type} - {kb.description || '暂无描述'}
                    </CardDescription>
                    {kbTags.length > 0 ? (
                      <div className='mt-2 flex flex-wrap gap-1'>
                        {kbTags.slice(0, 3).map((tag) => (
                          <Badge key={tag.id} variant='secondary' className='text-[10px]'>
                            {tag.name}
                          </Badge>
                        ))}
                        {kbTags.length > 3 ? (
                          <Badge variant='outline' className='text-[10px]'>
                            +{kbTags.length - 3}
                          </Badge>
                        ) : null}
                      </div>
                    ) : null}
                  </CardHeader>
                  <CardContent className='border-t border-border/60 px-4 pb-2 pt-0'>
                    <div className='space-y-3 pt-3'>
                      {/* Stats */}
                      <div className='flex flex-wrap items-center gap-2 text-[11px]'>
                        <div className='flex items-center gap-1 rounded bg-muted/50 px-1.5 py-0.5 font-medium text-muted-foreground'>
                          <FileText className='h-3 w-3 text-blue-500' />
                          <span>0</span>
                        </div>
                        <div className='flex items-center gap-1 rounded bg-muted/50 px-1.5 py-0.5 font-medium text-muted-foreground'>
                          <Package className='h-3 w-3 text-indigo-500' />
                          <span>0</span>
                        </div>
                      </div>

                      <div className='flex items-center justify-between'>
                        <div className='flex items-center gap-1 text-[10px] text-muted-foreground'>
                          <Clock className='h-2.5 w-2.5' />
                          <span>{formatDistanceToNow(new Date(kb.updated_at), { addSuffix: true, locale: zhCN })}</span>
                        </div>
                        <Badge variant='secondary' className='h-4 px-1.5 text-[9px] font-bold uppercase tracking-tighter'>
                          就绪
                        </Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </div>
      ) : (
        <div className='flex flex-col gap-2'>
          {filteredKnowledgeBases.map((kb) => {
            const kbType = (kb.type || 'general').toLowerCase()
            const config = KB_TYPE_CONFIG[kbType] || KB_TYPE_CONFIG.general
            const Icon = config.icon
            const kbTags = kbTagsMap[kb.id] || []
            return (
              <Link
                key={kb.id}
                to='/knowledge-base/$folderId'
                params={{ folderId: kb.id }}
                search={{ initialTab: undefined, tableGuide: undefined }}
              >
                <div className='flex items-center justify-between p-4 bg-background border rounded-xl hover:shadow-md transition-all group'>
                  <div className='flex items-center gap-4'>
                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${config.bgColor} shadow-sm group-hover:scale-105 transition-transform`}>
                      <Icon className={`h-5 w-5 ${config.color}`} />
                    </div>
                    <div>
                      <h3 className='font-semibold text-base group-hover:text-primary transition-colors'>{kb.name}</h3>
                      <p className='text-xs text-muted-foreground line-clamp-1 max-w-md'>{kb.description || '暂无描述'}</p>
                      {kbTags.length > 0 ? (
                        <div className='mt-2 flex flex-wrap gap-1'>
                          {kbTags.slice(0, 4).map((tag) => (
                            <Badge key={tag.id} variant='secondary' className='text-[10px]'>
                              {tag.name}
                            </Badge>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div className='flex items-center gap-8'>
                    <div className='hidden md:flex items-center gap-6'>
                      <div className='flex flex-col items-center gap-0.5'>
                        <span className='text-[10px] text-muted-foreground uppercase font-bold tracking-wider'>文档</span>
                        <span className='text-sm font-semibold'>0</span>
                      </div>
                      <div className='flex flex-col items-center gap-0.5'>
                        <span className='text-[10px] text-muted-foreground uppercase font-bold tracking-wider'>分块</span>
                        <span className='text-sm font-semibold'>0</span>
                      </div>
                      <div className='flex flex-col items-center gap-0.5'>
                        <span className='text-[10px] text-muted-foreground uppercase font-bold tracking-wider'>更新</span>
                        <span className='text-sm font-medium text-muted-foreground'>{formatDistanceToNow(new Date(kb.updated_at), { addSuffix: true, locale: zhCN })}</span>
                      </div>
                    </div>

                    <div className='flex items-center gap-3'>
                      <Badge variant='outline' className='text-[10px] px-2 py-0'>
                        就绪
                      </Badge>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.preventDefault()}>
                          <Button variant='ghost' size='icon' className='h-8 w-8'>
                            <MoreHorizontal className='h-4 w-4' />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align='end'>
                          <DropdownMenuItem
                            onClick={() => {
                              void navigate({
                                to: '/knowledge-base/$folderId',
                                params: { folderId: kb.id },
                                search: { initialTab: undefined, tableGuide: undefined },
                              })
                            }}
                          >
                            打开知识库
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className='text-destructive focus:bg-destructive/10 focus:text-destructive'
                            onClick={(e) => {
                              e.preventDefault()
                              setKbToDelete(kb)
                            }}
                          >
                            删除
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      <div className='mb-8 mt-12 flex items-center justify-center gap-2'>
        <Button
          variant='outline'
          size='icon'
          className='h-9 w-9'
          onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
          disabled={currentPage === 1}
        >
          <ChevronLeft className='h-4 w-4' />
        </Button>

        <div className='flex items-center gap-1.5'>
          {pageNumbers.map((page, index) => (
            <div key={`${page}-${index}`}>
              {page === '...' ? (
                <span className='px-2 text-muted-foreground'>...</span>
              ) : (
                <Button
                  variant={currentPage === page ? 'default' : 'outline'}
                  size='icon'
                  className='h-9 w-9 font-medium'
                  onClick={() => setCurrentPage(page as number)}
                >
                  {page}
                </Button>
              )}
            </div>
          ))}
        </div>

        <Button
          variant='outline'
          size='icon'
          className='h-9 w-9'
          onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
          disabled={currentPage === totalPages}
        >
          <ChevronRight className='h-4 w-4' />
        </Button>
      </div>

      <CreateKnowledgeBaseModal
        open={isCreateModalOpen}
        onOpenChange={setIsCreateModalOpen}
        onCreate={handleCreateKB}
      />

      <AlertDialog open={!!kbToDelete} onOpenChange={(open) => !open && setKbToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除知识库？</AlertDialogTitle>
            <AlertDialogDescription>
              您正在删除知识库 <span className='font-bold text-foreground'>「{kbToDelete?.name}」</span>。
              此操作将永久删除该知识库及其下所有文档和索引数据，且不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              className={buttonVariants({ variant: 'destructive' })}
              onClick={(e) => {
                e.preventDefault()
                handleDeleteKB()
              }}
              disabled={isDeleting}
            >
              {isDeleting ? '正在删除...' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
