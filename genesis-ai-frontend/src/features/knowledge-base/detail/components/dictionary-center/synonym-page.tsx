import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Shuffle, Edit3, Plus, Search, Sparkles, Trash2, MoveRight, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  batchUpsertSynonymVariants,
  createSynonym,
  deleteSynonym,
  listSynonymsByScope,
  listSynonymVariants,
  rewriteSynonymPreview,
  updateSynonym,
  type SynonymItem,
  type SynonymVariantItem,
} from './api'
import { SynonymEditorDialog, type SynonymEditorValue } from './synonym-editor-dialog'
import { Pagination } from '../file-manager/file-browser/components/pagination'

interface SynonymManagementProps {
  kbId: string
}

type SynonymScopeFilter = 'all' | 'kb' | 'tenant'

const DEFAULT_EDITOR_VALUE: SynonymEditorValue = {
  professional_term: '',
  variant_terms: '',
  priority: 100,
  is_active: true,
  is_global_scope: false,
}

/**
 * 变体数据加载器组件
 */
function VariantLoader({ synonymId, children }: { synonymId: string, children: (variants: SynonymVariantItem[]) => React.ReactNode }) {
  const { data } = useQuery({
    queryKey: ['kb-synonym-variants', synonymId],
    queryFn: () => listSynonymVariants(synonymId),
    enabled: !!synonymId
  })
  return <>{children(data ?? [])}</>
}

export function SynonymPage({ kbId }: SynonymManagementProps) {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [scopeFilter, setScopeFilter] = useState<SynonymScopeFilter>('all')
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorValue, setEditorValue] = useState<SynonymEditorValue>(DEFAULT_EDITOR_VALUE)
  const [editingItem, setEditingItem] = useState<SynonymItem | null>(null)
  const [pendingDelete, setPendingDelete] = useState<SynonymItem | null>(null)
  const [previewInput, setPreviewInput] = useState('')
  const [previewResult, setPreviewResult] = useState<{
    rewritten_query: string
    matches: Array<{ user_term: string; professional_term: string; scope: 'kb' | 'tenant' }>
  } | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // 1. 获取主列表
  const { data: sourceData = [], isLoading } = useQuery({
    queryKey: ['kb-synonyms', kbId, search],
    queryFn: () => listSynonymsByScope(kbId, search.trim() || undefined),
    enabled: Boolean(kbId),
  })

  // 2. 过滤与分页
  const filteredData = useMemo(() => {
    return sourceData.filter((item) => {
      if (scopeFilter === 'kb') return item.kb_id === kbId
      if (scopeFilter === 'tenant') return !item.kb_id
      return true
    })
  }, [kbId, scopeFilter, sourceData])

  const totalItems = filteredData.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const safeCurrentPage = Math.min(currentPage, totalPages)
  const pagedData = filteredData.slice((safeCurrentPage - 1) * pageSize, safeCurrentPage * pageSize)

  // 3. 统计项（参考 GLossaryPage）
  const stats = useMemo(() => {
    const total = sourceData.length
    const active = sourceData.filter((item) => item.is_active).length
    const kbCount = sourceData.filter((item) => item.kb_id === kbId).length
    const tenantCount = sourceData.filter((item) => !item.kb_id).length
    return { total, active, kbCount, tenantCount }
  }, [kbId, sourceData])

  const refreshList = async () => {
    await queryClient.invalidateQueries({ queryKey: ['kb-synonyms', kbId] })
  }

  // 4. Mutations
  const createMutation = useMutation({
    mutationFn: createSynonym,
    onSuccess: async (newItem) => {
      // 级联同步变体
      const variants = editorValue.variant_terms.split(/[,，\n]/).map(t => t.trim()).filter(Boolean)
      if (variants.length > 0) {
        await batchUpsertSynonymVariants({
          synonym_id: newItem.id,
          variants: variants.map(v => ({ user_term: v, is_active: true })),
          replace: true
        })
      }
      toast.success('同义词规则创建成功')
      setEditorOpen(false)
      await refreshList()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) => updateSynonym(id, payload),
    onSuccess: async (_, { id }) => {
      const variants = editorValue.variant_terms.split(/[,，\n]/).map(t => t.trim()).filter(Boolean)
      await batchUpsertSynonymVariants({
        synonym_id: id,
        variants: variants.map(v => ({ user_term: v, is_active: true })),
        replace: true
      })
      toast.success('规则更新成功')
      setEditorOpen(false)
      await refreshList()
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => updateSynonym(id, { is_active: enabled }),
    onSuccess: async () => {
      await refreshList()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSynonym,
    onSuccess: async () => {
      toast.success('规则已删除')
      setPendingDelete(null)
      await refreshList()
    },
  })

  const rewriteMutation = useMutation({
    mutationFn: (query: string) => rewriteSynonymPreview(kbId, query),
    onSuccess: (result) => {
      setPreviewResult({
        rewritten_query: result.rewritten_query,
        matches: result.matches.map((item) => ({
          user_term: item.user_term,
          professional_term: item.professional_term,
          scope: item.scope,
        })),
      })
    },
  })

  const [editLoadingId, setEditLoadingId] = useState<string | null>(null)

  // 5. Handlers
  const openAdd = () => {
    setEditingItem(null)
    setEditorValue(DEFAULT_EDITOR_VALUE)
    setEditorOpen(true)
  }

  const openEdit = async (item: SynonymItem) => {
    setEditLoadingId(item.id)
    try {
      // 需要额外拉取变体词充填编辑器
      const variants = await listSynonymVariants(item.id)
      setEditingItem(item)
      setEditorValue({
        professional_term: item.professional_term,
        variant_terms: variants.map(v => v.user_term).join('\n'), // 保持换行显示
        priority: item.priority,
        is_active: item.is_active,
        is_global_scope: !item.kb_id
      })
      setEditorOpen(true)
    } catch (e) {
      toast.error('获取变体信息失败')
    } finally {
      setEditLoadingId(null)
    }
  }

  const onSave = async (value: SynonymEditorValue) => {
    const payload = {
      professional_term: value.professional_term,
      priority: value.priority,
      is_active: value.is_active,
      kb_id: value.is_global_scope ? null : kbId,
    }
    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  return (
    <div className='flex h-full min-h-0 flex-col'>
      {/* 沉浸式页头 - 完美复刻 GlossaryPage */}
      <div className='flex items-center justify-between border-b bg-blue-50/30 px-6 py-3 transition-colors duration-300'>
        <div className='flex items-center gap-4'>
          <div className='flex items-center gap-2'>
            <div className='flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100/50 text-blue-600'>
              <Shuffle className='h-4 w-4' />
            </div>
            <h2 className='text-base font-semibold text-blue-700'>同义词管理</h2>
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
              本库规则: <span className='font-bold text-indigo-700'>{stats.kbCount}</span>
            </span>
          </div>
        </div>
        <Button size='sm' onClick={openAdd} className='bg-blue-600 hover:bg-blue-700 text-white'>
          <Plus className='mr-1.5 h-3.5 w-3.5' />
          添加记录
        </Button>
      </div>

      <div className='flex-1 overflow-hidden p-4 space-y-4 flex flex-col'>
        <div className='flex-1 overflow-hidden rounded-xl border border-blue-100/60 bg-white/50 shadow-sm backdrop-blur-sm flex flex-col'>
          {/* 搜索与过滤 - 对齐 Glossary */}
          <div className='flex flex-wrap items-center justify-between gap-3 border-b bg-blue-50/20 px-4 py-2.5'>
            <div className='relative flex-1 min-w-[240px] max-w-sm'>
              <Search className='absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-blue-400' />
              <Input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setCurrentPage(1)
                }}
                className='h-8 border-blue-100 bg-white/80 pl-8 text-xs focus-visible:ring-blue-400'
                placeholder='搜索标准词语...'
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
                    setScopeFilter(tab.id as SynonymScopeFilter)
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
            {/* 词典网格 */}
            <div className='grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5'>
              {isLoading ? (
                <div className='col-span-full flex h-32 flex-col items-center justify-center gap-2'>
                  <div className='h-5 w-5 animate-spin rounded-full border-2 border-blue-400 border-t-transparent' />
                  <span className='text-xs text-blue-400'>正在整理映射数据...</span>
                </div>
              ) : pagedData.length === 0 ? (
                <div className='col-span-full py-16 bg-blue-50/20 rounded-xl border border-dashed border-blue-100 flex flex-col items-center gap-3'>
                  <Shuffle className='h-8 w-8 text-blue-200' />
                  <span className='text-xs text-blue-400'>暂无映射规则</span>
                </div>
              ) : (
                <TooltipProvider>
                  {pagedData.map((item) => (
                    <div
                      key={item.id}
                      className='group relative flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-300 hover:border-blue-400 hover:shadow-lg'
                    >
                      <div className='space-y-2.5'>
                        <div className='flex items-start justify-between gap-2.5'>
                          <div className='min-w-0 flex-1 flex items-center gap-2'>
                            <span className='truncate text-base font-extrabold text-indigo-700 group-hover:text-blue-600 transition-colors' title={item.professional_term}>
                              {item.professional_term}
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
                          <VariantLoader synonymId={item.id}>
                            {(variants) => (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <div className='space-y-1 cursor-help'>
                                    <p className='text-[10px] font-bold text-slate-300 uppercase tracking-tighter'>[口语映射]</p>
                                    <div className='flex flex-wrap gap-1'>
                                      {variants.length > 0 ? (
                                        variants.slice(0, 3).map(v => (
                                          <span key={v.id} className='text-[11px] font-medium text-slate-500 break-all'>
                                            {v.user_term}
                                          </span>
                                        ))
                                      ) : (
                                        <span className='text-[11px] italic text-slate-300'>未维护</span>
                                      )}
                                      {variants.length > 3 && (
                                        <span className='text-[10px] font-bold text-blue-400'>+{variants.length - 3}</span>
                                      )}
                                    </div>
                                  </div>
                                </TooltipTrigger>
                                <TooltipContent side='bottom' className='max-w-md p-2 text-xs bg-slate-800 text-slate-100'>
                                  <div className='space-y-1'>
                                    {variants.map(v => (
                                      <div key={v.id} className='flex items-center gap-2'>
                                        <MoveRight className='h-2.5 w-2.5 opacity-40' />
                                        <span>{v.user_term}</span>
                                      </div>
                                    ))}
                                  </div>
                                </TooltipContent>
                              </Tooltip>
                            )}
                          </VariantLoader>
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
                            {item.is_active ? '启用' : '停用'}
                          </span>
                        </div>
                        <span className='text-[9px] text-slate-200 font-mono italic'>P:{item.priority}</span>
                      </div>
                    </div>
                  ))}
                </TooltipProvider>
              )}
            </div>
          </div>

          {/* 分页 */}
          <div className='border-t bg-blue-50/5 p-3 flex justify-center shrink-0'>
            <Pagination
              currentPage={safeCurrentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={totalItems}
              startIndex={(safeCurrentPage - 1) * pageSize}
              endIndex={Math.min(safeCurrentPage * pageSize, totalItems)}
              onPageChange={setCurrentPage}
              onPageSizeChange={(nextPageSize) => {
                setPageSize(nextPageSize)
                setCurrentPage(1)
              }}
            />
          </div>
        </div>

        {/* 改写预览 - 采用一致的卡片风格 */}
        <div className='rounded-xl border border-orange-100 bg-white p-4 shadow-sm'>
          <div className='flex items-center gap-2 mb-4'>
            <div className='h-8 w-8 rounded-lg bg-orange-50 text-orange-600 flex items-center justify-center'>
              <Sparkles className='h-4 w-4' />
            </div>
            <div>
              <h3 className='text-sm font-bold text-slate-800'>规则生效预览</h3>
              <p className='text-[10px] text-slate-400'>输入查询词，测试改写逻辑</p>
            </div>
          </div>

          <div className='grid gap-4 md:grid-cols-2'>
            <div className='space-y-1.5'>
              <div className='flex gap-2'>
                <Input
                  value={previewInput}
                  onChange={(e) => setPreviewInput(e.target.value)}
                  className='h-8 border-slate-100 bg-slate-50 text-xs'
                  placeholder='例：我想看LLM的应用'
                />
                <Button size='sm' className='h-8 bg-slate-800 text-white text-[10px] px-4' onClick={() => rewriteMutation.mutate(previewInput.trim())} disabled={rewriteMutation.isPending}>
                  测试
                </Button>
              </div>
            </div>
            <div className='bg-blue-50/50 rounded-lg border border-blue-100/30 flex items-center px-4 h-8'>
              {previewResult ? (
                <p className='text-xs font-bold text-blue-700'>{previewResult.rewritten_query}</p>
              ) : (
                <p className='text-slate-300 italic text-[10px]'>查看改写结果</p>
              )}
            </div>
          </div>
        </div>
      </div>

      <SynonymEditorDialog
        open={editorOpen}
        onOpenChange={setEditorOpen}
        value={editorValue}
        onChange={setEditorValue}
        onSave={onSave}
        loading={createMutation.isPending || updateMutation.isPending}
        isEdit={!!editingItem}
      />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title='删除映射规则'
        description={pendingDelete ? `此操作将永久移除 “${pendingDelete.professional_term}” 的所有同义词映射关系。` : ''}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete.id)}
        loading={deleteMutation.isPending}
      />
    </div>
  )
}
