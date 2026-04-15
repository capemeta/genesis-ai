import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Edit3, Plus, Search, Trash2, Loader2, Info } from 'lucide-react'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
// Removed unused Card imports
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { listGlossariesByScope, createGlossary, updateGlossary, deleteGlossary, type GlossaryItem } from './api'
import { GlossaryEditorDialog, type GlossaryEditorValue } from './glossary-editor-dialog'
import { Pagination } from '../file-manager/file-browser/components/pagination'

interface GlossaryManagementProps {
  kbId: string
}

type GlossaryScopeFilter = 'all' | 'kb' | 'tenant'

const DEFAULT_EDITOR_VALUE: GlossaryEditorValue = {
  term: '',
  definition: '',
  examples: '',
  is_active: true,
  is_global_scope: false,
}

const toEditorValue = (item: GlossaryItem): GlossaryEditorValue => ({
  term: item.term,
  definition: item.definition,
  examples: item.examples || '',
  is_active: item.is_active,
  is_global_scope: !item.kb_id,
})

export function GlossaryPage({ kbId }: GlossaryManagementProps) {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [scopeFilter, setScopeFilter] = useState<GlossaryScopeFilter>('all')
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorValue, setEditorValue] = useState<GlossaryEditorValue>(DEFAULT_EDITOR_VALUE)
  const [editingItem, setEditingItem] = useState<GlossaryItem | null>(null)
  const [pendingDelete, setPendingDelete] = useState<GlossaryItem | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [editLoadingId, setEditLoadingId] = useState<string | null>(null)

  const glossaryQuery = useQuery({
    queryKey: ['kb-glossaries', kbId, search],
    queryFn: () => listGlossariesByScope(kbId, search.trim() || undefined),
    enabled: Boolean(kbId),
  })

  const sourceData = useMemo(() => glossaryQuery.data ?? [], [glossaryQuery.data])
  const filteredData = useMemo(() => {
    return sourceData.filter((item) => {
      if (scopeFilter === 'kb') {
        return item.kb_id === kbId
      }
      if (scopeFilter === 'tenant') {
        return !item.kb_id
      }
      return true
    })
  }, [kbId, scopeFilter, sourceData])

  const totalItems = filteredData.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const safeCurrentPage = Math.min(currentPage, totalPages)
  const startIndex = totalItems ? (safeCurrentPage - 1) * pageSize : 0
  const pagedData = filteredData.slice(startIndex, startIndex + pageSize)
  const endIndex = Math.min(startIndex + pagedData.length, totalItems)

  const stats = useMemo(() => {
    const total = sourceData.length
    const active = sourceData.filter((item) => item.is_active).length
    const kbCount = sourceData.filter((item) => item.kb_id === kbId).length
    const tenantCount = sourceData.filter((item) => !item.kb_id).length
    return { total, active, kbCount, tenantCount }
  }, [kbId, sourceData])

  const refreshList = async () => {
    await queryClient.invalidateQueries({ queryKey: ['kb-glossaries', kbId] })
  }

  const createMutation = useMutation({
    mutationFn: createGlossary,
    onSuccess: async () => {
      toast.success('术语创建成功')
      setEditorOpen(false)
      setEditingItem(null)
      setEditorValue(DEFAULT_EDITOR_VALUE)
      await refreshList()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updateGlossary>[1] }) =>
      updateGlossary(id, payload),
    onSuccess: async () => {
      toast.success('术语更新成功')
      setEditorOpen(false)
      setEditingItem(null)
      setEditorValue(DEFAULT_EDITOR_VALUE)
      await refreshList()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteGlossary,
    onSuccess: async () => {
      toast.success('术语删除成功')
      setPendingDelete(null)
      await refreshList()
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateGlossary(id, { is_active: enabled }),
    onSuccess: async (_data, vars) => {
      toast.success(vars.enabled ? '术语已启用' : '术语已停用')
      await refreshList()
    },
  })

  const isSaving = createMutation.isPending || updateMutation.isPending

  const openCreate = () => {
    setEditingItem(null)
    setEditorValue(DEFAULT_EDITOR_VALUE)
    setEditorOpen(true)
  }

  const openEdit = (item: GlossaryItem) => {
    setEditLoadingId(item.id)
    try {
      setEditingItem(item)
      setEditorValue(toEditorValue(item))
      setEditorOpen(true)
    } finally {
      setEditLoadingId(null)
    }
  }

  const handleSubmit = () => {
    const term = editorValue.term.trim()
    const definition = editorValue.definition.trim()
    if (!term) {
      toast.error('术语名称不能为空')
      return
    }
    if (!definition) {
      toast.error('术语定义不能为空')
      return
    }

    const payload = {
      kb_id: editorValue.is_global_scope ? null : kbId,
      term,
      definition,
      examples: editorValue.examples.trim() || undefined,
      is_active: editorValue.is_active,
    }

    const duplicate = sourceData.find((item) => {
      if (editingItem && item.id === editingItem.id) {
        return false
      }
      const sameScope = editorValue.is_global_scope ? !item.kb_id : item.kb_id === kbId
      return sameScope && item.term.trim().toLowerCase() === term.toLowerCase()
    })
    if (duplicate) {
      toast.error('同作用域下术语名称重复，请更换后再保存')
      return
    }

    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, payload })
      return
    }
    createMutation.mutate(payload)
  }

  return (
    <div className='flex h-full min-h-0 flex-col'>
      <div className='flex items-center justify-between border-b bg-blue-50/30 px-6 py-3 transition-colors duration-300'>
        <div className='flex items-center gap-4'>
          <div className='flex items-center gap-2'>
            <div className='flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100/50 text-blue-600'>
              <BookOpen className='h-4 w-4' />
            </div>
            <div>
              <h2 className='text-base font-semibold text-blue-700'>术语管理</h2>
              <p className='hidden text-xs text-blue-600/70 lg:block'>启用的术语会进入检索分词词典，并用于生成阶段的术语解释。</p>
            </div>
          </div>
          <div className='hidden h-4 w-px bg-blue-200 md:block' />
          <div className='hidden items-center gap-3 text-xs md:flex'>
            <span className='flex items-center gap-1.5 text-blue-600/80'>
              <span className='h-1.5 w-1.5 rounded-full bg-blue-500' />
              总数: <span className='font-bold text-blue-700'>{stats.total}</span>
            </span>
            <span className='flex items-center gap-1.5 text-cyan-600/80'>
              <span className='h-1.5 w-1.5 rounded-full bg-cyan-500' />
              已启用: <span className='font-bold text-cyan-700'>{stats.active}</span>
            </span>
            <span className='flex items-center gap-1.5 text-indigo-600/80'>
              <span className='h-1.5 w-1.5 rounded-full bg-indigo-500' />
              本库: <span className='font-bold text-indigo-700'>{stats.kbCount}</span>
            </span>
          </div>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className='hidden cursor-help items-center gap-1 text-xs text-blue-600/70 xl:flex'>
                  <Info className='h-3.5 w-3.5' />
                  检索词典
                </span>
              </TooltipTrigger>
              <TooltipContent side='bottom' className='max-w-sm text-xs'>
                术语名称会作为检索分词词典项；同义词仍用于查询改写，不会默认写入正文索引。
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <Button size='sm' onClick={openCreate} className='bg-blue-600 hover:bg-blue-700 text-white'>
          <Plus className='mr-1.5 h-3.5 w-3.5' />
          新建术语
        </Button>
      </div>

      <div className='flex-1 overflow-hidden p-4'>
        <div className='flex h-full flex-col overflow-hidden rounded-xl border border-blue-100/60 bg-white/50 shadow-sm backdrop-blur-sm'>
          <div className='flex flex-wrap items-center justify-between gap-3 border-b bg-blue-50/20 px-4 py-2.5'>
            <div className='relative flex-1 min-w-[240px] max-w-sm'>
              <Search className='absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-blue-400' />
              <Input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
                  setCurrentPage(1)
                }}
                className='h-8 border-blue-100 bg-white/80 pl-8 text-xs focus-visible:ring-blue-400'
                placeholder='搜索术语内容...'
              />
            </div>
            <div className='flex items-center gap-1 rounded-lg border border-blue-100 bg-white/80 p-0.5 shadow-sm'>
              {[
                { id: 'all', label: '全部' },
                { id: 'kb', label: '本库' },
                { id: 'tenant', label: '租户' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setScopeFilter(tab.id as GlossaryScopeFilter)
                    setCurrentPage(1)
                  }}
                  className={`px-3 py-1 text-xs font-medium transition-all rounded-md ${scopeFilter === tab.id
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-blue-600/70 hover:bg-blue-50'
                    }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className='flex-1 overflow-auto bg-gradient-to-b from-blue-50/10 to-transparent p-4'>
            {glossaryQuery.isLoading ? (
              <div className='flex h-32 flex-col items-center justify-center gap-2 text-blue-400'>
                <div className='h-5 w-5 animate-spin rounded-full border-2 border-blue-400 border-t-transparent' />
                <span className='text-xs'>加载中...</span>
              </div>
            ) : filteredData.length === 0 ? (
              <div className='flex h-32 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-blue-200 bg-blue-50/20'>
                <BookOpen className='h-6 w-6 text-blue-200' />
                <span className='text-xs text-blue-400'>暂无术语数据</span>
              </div>
            ) : (
              <TooltipProvider>
                <div className='grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3'>
                  {pagedData.map((item) => (
                    <div
                      key={item.id}
                      className='group relative flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-300 hover:border-blue-400 hover:shadow-lg'
                    >
                      <div className='space-y-2.5'>
                        <div className='flex items-start justify-between gap-2.5'>
                          <div className='min-w-0 flex-1 flex items-center gap-2'>
                            <span className='truncate text-base font-extrabold text-indigo-700 group-hover:text-blue-600 transition-colors' title={item.term}>
                              {item.term}
                            </span>
                            <Badge
                              className={`h-4 border-none px-1.5 text-[9px] font-bold shadow-none shrink-0 ${item.kb_id ? 'bg-blue-100/50 text-blue-600' : 'bg-indigo-100/50 text-indigo-600'
                                }`}
                            >
                              {item.kb_id ? '本库' : '租户'}
                            </Badge>
                          </div>
                          <div className='flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100'>
                            <Button
                              size='icon'
                              variant='ghost'
                              className='h-7 w-7 text-slate-400 hover:bg-blue-50 hover:text-blue-600 disabled:opacity-50'
                              onClick={() => openEdit(item)}
                              disabled={editLoadingId === item.id}
                            >
                              {editLoadingId === item.id ? (
                                <Loader2 className='h-3.5 w-3.5 animate-spin' />
                              ) : (
                                <Edit3 className='h-3.5 w-3.5' />
                              )}
                            </Button>
                            <Button
                              size='icon'
                              variant='ghost'
                              className='h-7 w-7 text-slate-400 hover:bg-red-50 hover:text-red-500'
                              onClick={() => setPendingDelete(item)}
                            >
                              <Trash2 className='h-3.5 w-3.5' />
                            </Button>
                          </div>
                        </div>

                        <div className='space-y-1.5 pl-2.5 border-l-2 border-slate-100 group-hover:border-blue-200 transition-colors'>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <p className='text-[13px] leading-relaxed text-slate-500 line-clamp-2 cursor-help'>
                                <span className='font-bold text-slate-300 mr-1.5'>[含义]</span>
                                {item.definition || '未填写'}
                              </p>
                            </TooltipTrigger>
                            <TooltipContent side='bottom' className='max-w-md p-2 text-xs bg-slate-800 text-slate-100'>
                              {item.definition || '未填写'}
                            </TooltipContent>
                          </Tooltip>

                          {item.examples && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <p className='text-[13px] italic text-blue-400/80 line-clamp-1 cursor-help'>
                                  <span className='font-bold opacity-60 mr-1.5 not-italic text-slate-300'>[例句]</span>
                                  {item.examples}
                                </p>
                              </TooltipTrigger>
                              <TooltipContent side='bottom' className='max-w-md p-2 text-xs bg-blue-900 text-blue-50'>
                                {item.examples}
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </div>

                      <div className='mt-4 flex items-center justify-between pt-2 border-t border-slate-50'>
                        <div className='flex items-center gap-1.5'>
                          <Switch
                            checked={item.is_active}
                            onCheckedChange={(checked) => toggleMutation.mutate({ id: item.id, enabled: checked })}
                            disabled={toggleMutation.isPending}
                            className='scale-[0.65]'
                          />
                          <span className={`text-[10px] font-bold ${item.is_active ? 'text-blue-500' : 'text-slate-300'}`}>
                            {item.is_active ? '已启用' : '已停用'}
                          </span>
                        </div>
                        <span className='text-[9px] text-slate-200 font-mono italic'>{new Date(item.updated_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </TooltipProvider>
            )}
          </div>

          <div className='border-t bg-blue-50/10 px-4 py-1.5'>
            <Pagination
              currentPage={safeCurrentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={totalItems}
              startIndex={startIndex}
              endIndex={endIndex}
              onPageChange={setCurrentPage}
              onPageSizeChange={(nextPageSize) => {
                setPageSize(nextPageSize)
                setCurrentPage(1)
              }}
            />
          </div>
        </div>
      </div>

      <GlossaryEditorDialog
        open={editorOpen}
        onOpenChange={setEditorOpen}
        value={editorValue}
        onChange={setEditorValue}
        onSubmit={handleSubmit}
        loading={isSaving}
        editingItem={editingItem}
      />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(open) => {
          if (!open) {
            setPendingDelete(null)
          }
        }}
        title='确认删除术语？'
        description={pendingDelete ? `术语“${pendingDelete.term}”删除后不可恢复。` : ''}
        onConfirm={() => {
          if (pendingDelete) {
            deleteMutation.mutate(pendingDelete.id)
          }
        }}
        loading={deleteMutation.isPending}
        confirmText='确认删除'
      />
    </div>
  )
}
