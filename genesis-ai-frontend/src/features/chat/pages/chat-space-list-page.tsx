import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Grid3x3, List, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  chatQueryKeys,
  createChatSpace,
  deleteChatSpace,
  fetchChatBootstrap,
  fetchChatSpaces,
  updateChatSpace,
} from '@/features/chat/api/chat'
import { ChatSpaceCard } from '@/features/chat/components/list/chat-space-card'
import { CreateChatSpaceDialog } from '@/features/chat/components/shared/create-chat-space-dialog'
import type { ChatCreateSpaceFormValues, ChatSpace } from '@/features/chat/types/chat'

type ViewMode = 'grid' | 'list'
type StatusFilter = 'active' | 'archived'

export function ChatSpaceListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('active')
  const [page, setPage] = useState(1)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const pageSize = 12

  const bootstrapQuery = useQuery({
    queryKey: chatQueryKeys.bootstrap(),
    queryFn: fetchChatBootstrap,
  })

  const spacesQuery = useQuery({
    queryKey: chatQueryKeys.spaces({ page, pageSize, search, status: statusFilter }),
    queryFn: () =>
      fetchChatSpaces({
        page,
        pageSize,
        search,
        status: statusFilter,
      }),
  })

  const createSpaceMutation = useMutation({
    mutationFn: async (values: ChatCreateSpaceFormValues) => {
      return createChatSpace({
        name: values.name,
        description: values.description || undefined,
        entrypoint_type: values.entrypointType,
        entrypoint_id:
          values.entrypointType === 'workflow' && values.workflowId ? values.workflowId : null,
        default_config: {},
      })
    },
    onSuccess: async (space) => {
      toast.success('聊天空间创建成功')
      await queryClient.invalidateQueries({ queryKey: chatQueryKeys.all })
      setIsCreateDialogOpen(false)
      navigate({
        to: '/chat/$chatId',
        params: { chatId: space.id },
        search: { sessionId: undefined },
      })
    },
  })

  const updateSpaceMutation = useMutation({
    mutationFn: async ({ space, nextStatus }: { space: ChatSpace; nextStatus: ChatSpace['status'] }) =>
      updateChatSpace(space.id, { status: nextStatus }),
    onSuccess: async () => {
      toast.success('聊天空间状态已更新')
      await queryClient.invalidateQueries({ queryKey: chatQueryKeys.all })
    },
  })

  const deleteSpaceMutation = useMutation({
    mutationFn: deleteChatSpace,
    onSuccess: async () => {
      toast.success('聊天空间已删除')
      await queryClient.invalidateQueries({ queryKey: chatQueryKeys.all })
    },
  })

  const spaces = spacesQuery.data?.data || []
  const total = spacesQuery.data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const listContent = useMemo(() => {
    if (spaces.length === 0) {
      return (
        <div className='flex flex-col items-center justify-center min-h-[400px] border-2 border-dashed rounded-3xl bg-muted/5'>
          <div className='text-xl font-semibold'>暂无聊天空间</div>
          <div className='mt-2 text-sm text-muted-foreground'>
            创建一个即可开始：先按主题建空间，进入后再配置模型、知识库和具体聊天参数。
          </div>
          <Button className='mt-6 bg-blue-600 hover:bg-blue-700 text-white' onClick={() => setIsCreateDialogOpen(true)}>
            <Plus className='mr-2 h-4 w-4' />
            新建空间
          </Button>
        </div>
      )
    }

    const cards = spaces.map((space) => (
      <ChatSpaceCard
        key={space.id}
        space={space}
        viewMode={viewMode}
        onArchive={(item) =>
          updateSpaceMutation.mutate({
            space: item,
            nextStatus: item.status === 'archived' ? 'active' : 'archived',
          })
        }
        onDelete={(item) => deleteSpaceMutation.mutate(item.id)}
      />
    ))

    if (viewMode === 'list') {
      return <div className='space-y-2'>{cards}</div>
    }

    return <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'>{cards}</div>
  }, [spaces, viewMode, updateSpaceMutation, deleteSpaceMutation])

  return (
    <div className='w-full px-6 md:px-8 lg:px-12 xl:px-16 py-8 max-w-[1920px] mx-auto'>
      <div className='flex flex-col gap-6'>
        <div className='mb-2 flex flex-col gap-4 md:flex-row md:items-end md:justify-between'>
          <div className='space-y-1.5'>
            <div className='space-y-1.5'>
              <h1 className='text-3xl font-bold tracking-tight'>
                聊天空间
              </h1>
              <p className='text-muted-foreground max-w-2xl text-balance'>
                聚合您的 AI 伴侣。每个空间独立配置知识库与模型参数，让对话更专业、更智能。
              </p>
            </div>
          </div>
          <Button className='shrink-0 shadow-sm bg-blue-600 hover:bg-blue-700 text-white' onClick={() => setIsCreateDialogOpen(true)}>
            <Plus className='mr-2 h-4 w-4' />
            新建空间
          </Button>
        </div>

        <div className='flex flex-col sm:flex-row items-center justify-between gap-4 mb-2 bg-muted/30 p-4 rounded-xl border'>
          <div className='flex items-center gap-4 w-full sm:w-auto flex-1'>
            <div className='relative w-full max-w-md'>
              <Search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
                <Input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value)
                    setPage(1)
                  }}
                  placeholder='搜索空间名称...'
                  className='pl-9 bg-background'
                />
            </div>
            <Select
              value={statusFilter}
              onValueChange={(value: StatusFilter) => {
                setStatusFilter(value)
                setPage(1)
              }}
            >
              <SelectTrigger className='w-[160px] bg-background'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='active'>活跃中</SelectItem>
                <SelectItem value='archived'>已归档</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className='flex items-center gap-4 shrink-0'>
            <div className='text-xs text-muted-foreground'>
              共 <span className='font-semibold text-foreground'>{total}</span> 个空间
            </div>
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

      {spacesQuery.isLoading ? (
        <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'>
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className='h-56 animate-pulse rounded-2xl border bg-muted/30' />
          ))}
        </div>
      ) : (
        listContent
      )}

      {totalPages > 1 ? (
        <div className='flex items-center justify-center gap-3 mt-8 mb-2'>
          <Button variant='outline' disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>
            上一页
          </Button>
          <div className='text-sm text-muted-foreground'>
            第 {page} / {totalPages} 页
          </div>
          <Button
            variant='outline'
            disabled={page >= totalPages}
            onClick={() => setPage((current) => current + 1)}
          >
            下一页
          </Button>
        </div>
      ) : null}

      <CreateChatSpaceDialog
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
        bootstrap={bootstrapQuery.data}
        onSubmit={(values) => createSpaceMutation.mutate(values)}
        isSubmitting={createSpaceMutation.isPending}
      />
    </div>
    </div>
  )
}
