import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowDown,
  ArrowUp,
  Download,
  Eye,
  FileSpreadsheet,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from 'lucide-react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { Pagination } from '../../../pagination'
import { FolderMountField } from '../../shared/folder-mount-field'
import {
  batchDeleteQAItems,
  batchToggleQAItemsEnabled,
  createQAItem,
  createQAVirtualDataset,
  deleteQAItem,
  downloadQATemplate,
  fetchQADatasetDetail,
  fetchQADatasets,
  fetchQAItems,
  importQADatasetFile,
  previewQAImport,
  reorderQAItems,
  toggleQAItemEnabled,
  updateQAItem,
  exportQADatasetCsv,
  type QAImportPreview,
  type QAItem,
  type QAItemStructured,
} from '@/lib/api/qa-items'
import type { KnowledgeBaseDocument } from '@/lib/api/knowledge-base'

interface QADataManagerProps {
  kbId: string
  selectedFolderId?: string | null
}

interface QAItemFormState {
  question: string
  answer: string
  questionAliases: string[]
  tags: string
  category: string
}

const EMPTY_FORM: QAItemFormState = {
  question: '',
  answer: '',
  questionAliases: [''],
  tags: '',
  category: '',
}

function getDatasetStatusMeta(parseStatus?: string, runtimeStage?: string | null, progress?: number) {
  if (runtimeStage === 'edited_waiting_reparse') {
    return {
      label: '待重解析',
      className: 'bg-orange-100 text-orange-700 hover:bg-orange-100',
    }
  }

  switch (String(parseStatus || '').toLowerCase()) {
    case 'completed':
      return {
        label: '已解析',
        className: 'bg-green-100 text-green-700 hover:bg-green-100',
      }
    case 'processing':
      return {
        label: `正在解析${typeof progress === 'number' ? ` ${progress}%` : ''}`,
        className: 'bg-blue-50 text-blue-700 hover:bg-blue-50',
      }
    case 'queued':
      return {
        label: '排队中',
        className: 'bg-yellow-100 text-yellow-700 hover:bg-yellow-100',
      }
    case 'failed':
      return {
        label: '解析失败',
        className: 'bg-red-100 text-red-700 hover:bg-red-100',
      }
    default:
      return {
        label: '等待启动',
        className: 'bg-slate-100 text-slate-700 hover:bg-slate-100',
      }
  }
}

function buildStructuredItem(form: QAItemFormState): QAItemStructured {
  return {
    question: form.question.trim(),
    answer: form.answer.trim(),
    similar_questions: form.questionAliases
      .map((item) => item.trim())
      .filter(Boolean),
    tags: form.tags
      .split(/[,，;；\n]/)
      .map((item) => item.trim())
      .filter(Boolean),
    category: form.category.trim() || null,
  }
}

function buildFormState(item?: QAItem): QAItemFormState {
  if (!item) {
    return EMPTY_FORM
  }
  return {
    question: item.content_structured.question || '',
    answer: item.content_structured.answer || '',
    questionAliases: (item.content_structured.similar_questions || []).length
      ? [...(item.content_structured.similar_questions || [])]
      : [''],
    tags: (item.content_structured.tags || []).join('，'),
    category: item.content_structured.category || '',
  }
}

export function QADataManager({ kbId, selectedFolderId = null }: QADataManagerProps) {
  const queryClient = useQueryClient()
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [datasetSearch, setDatasetSearch] = useState('')
  const [itemSearch, setItemSearch] = useState('')
  const [includeDisabled, setIncludeDisabled] = useState(true)
  const [includeSubfolders, setIncludeSubfolders] = useState(true)
  const [datasetDialogOpen, setDatasetDialogOpen] = useState(false)
  const [datasetName, setDatasetName] = useState('')
  const [datasetFolderId, setDatasetFolderId] = useState<string | null>(selectedFolderId)
  const [itemDialogOpen, setItemDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<QAItem | null>(null)
  const [detailItem, setDetailItem] = useState<QAItem | null>(null)
  const [itemForm, setItemForm] = useState<QAItemFormState>(EMPTY_FORM)
  const [selectedItemIds, setSelectedItemIds] = useState<string[]>([])
  const [pendingDeleteItem, setPendingDeleteItem] = useState<QAItem | null>(null)
  const [pendingBatchDelete, setPendingBatchDelete] = useState(false)
  const [importDialogOpen, setImportDialogOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importPreview, setImportPreview] = useState<QAImportPreview | null>(null)
  const [importFolderId, setImportFolderId] = useState<string | null>(selectedFolderId)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // 左侧数据集列表：与表格型工作台保持一致，统一从文档域筛选 QA 载体
  const {
    data: datasets = [],
    isLoading: isLoadingDatasets,
    isFetching: isFetchingDatasets,
    refetch: refetchDatasets,
  } = useQuery({
    queryKey: ['qa-datasets', kbId, selectedFolderId, includeSubfolders],
    queryFn: () => fetchQADatasets(kbId, { folderId: selectedFolderId, includeSubfolders }),
    enabled: !!kbId,
  })

  useEffect(() => {
    if (datasetDialogOpen) {
      setDatasetFolderId(selectedFolderId)
    }
  }, [datasetDialogOpen, selectedFolderId])

  useEffect(() => {
    if (importDialogOpen) {
      setImportFolderId(selectedFolderId)
    }
  }, [importDialogOpen, selectedFolderId])

  const qaDatasets = useMemo(() => {
    const keyword = datasetSearch.trim().toLowerCase()
    return datasets.filter((dataset: KnowledgeBaseDocument) => {
      const metadata = dataset.metadata || {}
      const isQADataset = (
        metadata.content_kind === 'qa_dataset' ||
        dataset.document.file_type === 'CSV' ||
        dataset.document.file_type === 'XLSX' ||
        metadata.virtual_file
      )
      if (!isQADataset) {
        return false
      }
      if (!keyword) {
        return true
      }
      return [dataset.display_name, dataset.document.name, dataset.summary || '']
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    })
  }, [datasetSearch, datasets])

  const activeDatasetId = useMemo(() => {
    if (!qaDatasets.length) {
      return null
    }
    if (selectedDatasetId && qaDatasets.some((item) => item.id === selectedDatasetId)) {
      return selectedDatasetId
    }
    return qaDatasets[0].id
  }, [qaDatasets, selectedDatasetId])

  const selectedDataset = useMemo(
    () => qaDatasets.find((dataset) => dataset.id === activeDatasetId) || null,
    [qaDatasets, activeDatasetId]
  )

  useEffect(() => {
    if (activeDatasetId !== selectedDatasetId) {
      setSelectedDatasetId(activeDatasetId)
    }
  }, [activeDatasetId, selectedDatasetId])

  const {
    data: datasetDetail,
    isLoading: isLoadingDetail,
    isFetching: isFetchingDetail,
    refetch: refetchDatasetDetail,
  } = useQuery({
    queryKey: ['qa-dataset-detail', activeDatasetId],
    queryFn: () => fetchQADatasetDetail(activeDatasetId!),
    enabled: !!activeDatasetId,
  })

  const {
    data: itemsResponse,
    isLoading: isLoadingItems,
    isFetching: isFetchingItems,
    refetch: refetchItems,
  } = useQuery({
    queryKey: ['qa-items', activeDatasetId, includeDisabled],
    queryFn: () => fetchQAItems(activeDatasetId!, includeDisabled),
    enabled: !!activeDatasetId,
  })

  const items = itemsResponse?.items || []
  const filteredItems = useMemo(() => {
    const keyword = itemSearch.trim().toLowerCase()
    if (!keyword) {
      return items
    }
    return items.filter((item) => {
      const structured = item.content_structured
      const aliases = (structured.similar_questions || []).join(' ')
      const tags = (structured.tags || []).join(' ')
      return [structured.question, structured.answer, aliases, tags, structured.category || '']
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    })
  }, [itemSearch, items])

  const totalItems = filteredItems.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const safeCurrentPage = Math.min(currentPage, totalPages)
  const startIndex = totalItems ? (safeCurrentPage - 1) * pageSize : 0
  const pagedItems = filteredItems.slice(startIndex, startIndex + pageSize)
  const endIndex = Math.min(startIndex + pagedItems.length, totalItems)

  useEffect(() => {
    setCurrentPage(1)
    setSelectedItemIds([])
  }, [activeDatasetId, itemSearch, includeDisabled, pageSize])

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages)
    }
  }, [currentPage, totalPages])

  const refreshDatasetQueries = async (kbDocId?: string) => {
    await queryClient.invalidateQueries({ queryKey: ['qa-datasets', kbId] })
    if (kbDocId) {
      await queryClient.invalidateQueries({ queryKey: ['qa-dataset-detail', kbDocId] })
      await queryClient.invalidateQueries({ queryKey: ['qa-items', kbDocId] })
    }
  }

  const createDatasetMutation = useMutation({
    mutationFn: createQAVirtualDataset,
    onSuccess: async (data) => {
      toast.success('手工问答集已创建')
      setDatasetDialogOpen(false)
      setDatasetName('')
      setSelectedDatasetId(data.kb_doc_id)
      await refreshDatasetQueries(data.kb_doc_id)
    },
  })

  const previewImportMutation = useMutation({
    mutationFn: previewQAImport,
    onSuccess: (data) => {
      setImportPreview(data)
      toast.success(`预检成功，共解析 ${data.item_count} 条问答`)
    },
  })

  const importDatasetMutation = useMutation({
    mutationFn: importQADatasetFile,
    onSuccess: async (data) => {
      toast.success('问答文件导入成功')
      setImportDialogOpen(false)
      setImportFile(null)
      setImportPreview(null)
      setSelectedDatasetId(data.kb_doc_id)
      await refreshDatasetQueries(data.kb_doc_id)
    },
  })

  const createItemMutation = useMutation({
    mutationFn: createQAItem,
    onSuccess: async (data) => {
      toast.success('问答已创建')
      setItemDialogOpen(false)
      setEditingItem(null)
      setItemForm(EMPTY_FORM)
      await refreshDatasetQueries(data.dataset.kb_doc_id)
    },
  })

  const updateItemMutation = useMutation({
    mutationFn: updateQAItem,
    onSuccess: async (data) => {
      toast.success('问答已更新')
      setItemDialogOpen(false)
      setEditingItem(null)
      setItemForm(EMPTY_FORM)
      await refreshDatasetQueries(data.dataset.kb_doc_id)
    },
  })

  const deleteItemMutation = useMutation({
    mutationFn: deleteQAItem,
    onSuccess: async (data) => {
      toast.success('问答已删除')
      setPendingDeleteItem(null)
      await refreshDatasetQueries(data.dataset.kb_doc_id)
    },
  })

  const batchDeleteItemsMutation = useMutation({
    mutationFn: batchDeleteQAItems,
    onSuccess: async (data) => {
      toast.success(`已删除 ${data.deleted_count} 条问答`)
      setPendingBatchDelete(false)
      setSelectedItemIds([])
      await refreshDatasetQueries(data.dataset.kb_doc_id)
    },
  })

  const toggleItemMutation = useMutation({
    mutationFn: toggleQAItemEnabled,
    onSuccess: async (data) => {
      toast.success(data.enabled ? '问答已启用' : '问答已禁用')
      await refreshDatasetQueries(data.dataset.kb_doc_id)
    },
  })

  const batchToggleItemsMutation = useMutation({
    mutationFn: batchToggleQAItemsEnabled,
    onSuccess: async (data) => {
      toast.success(data.enabled ? '已批量启用问答' : '已批量禁用问答')
      setSelectedItemIds([])
      await refreshDatasetQueries(data.dataset.kb_doc_id)
    },
  })

  const reorderMutation = useMutation({
    mutationFn: reorderQAItems,
    onSuccess: async (data) => {
      await refreshDatasetQueries(data.dataset.kb_doc_id)
    },
  })

  const handleOpenCreateItem = () => {
    setEditingItem(null)
    setItemForm(EMPTY_FORM)
    setItemDialogOpen(true)
  }

  const handleOpenEditItem = (item: QAItem) => {
    setEditingItem(item)
    setItemForm(buildFormState(item))
    setItemDialogOpen(true)
  }

  const updateAliasAt = (index: number, value: string) => {
    setItemForm((prev) => ({
      ...prev,
      questionAliases: prev.questionAliases.map((alias, aliasIndex) => (
        aliasIndex === index ? value : alias
      )),
    }))
  }

  const addAliasRow = () => {
    setItemForm((prev) => ({
      ...prev,
      questionAliases: [...prev.questionAliases, ''],
    }))
  }

  const removeAliasRow = (index: number) => {
    setItemForm((prev) => {
      const nextAliases = prev.questionAliases.filter((_, aliasIndex) => aliasIndex !== index)
      return {
        ...prev,
        questionAliases: nextAliases.length ? nextAliases : [''],
      }
    })
  }

  const handleSaveItem = () => {
    if (!activeDatasetId) {
      toast.error('请先选择问答集')
      return
    }
    const structured = buildStructuredItem(itemForm)
    if (!structured.question || !structured.answer) {
      toast.error('问题和答案不能为空')
      return
    }

    if (editingItem) {
      updateItemMutation.mutate({
        item_id: editingItem.id,
        item: structured,
      })
      return
    }

    createItemMutation.mutate({
      kb_doc_id: activeDatasetId,
      item: structured,
    })
  }

  const handleMoveItem = (itemId: string, direction: 'up' | 'down') => {
    if (!activeDatasetId || items.length <= 1) {
      return
    }
    const currentIndex = items.findIndex((item) => item.id === itemId)
    if (currentIndex < 0) {
      return
    }
    const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1
    if (targetIndex < 0 || targetIndex >= items.length) {
      return
    }

    const reordered = [...items]
    const [currentItem] = reordered.splice(currentIndex, 1)
    reordered.splice(targetIndex, 0, currentItem)

    reorderMutation.mutate({
      kb_doc_id: activeDatasetId,
      items: reordered.map((item, index) => ({
        item_id: item.id,
        position: index,
      })),
    })
  }

  const handlePreviewImport = () => {
    if (!importFile) {
      toast.error('请先选择文件')
      return
    }
    previewImportMutation.mutate(importFile)
  }

  const handleImportDataset = () => {
    if (!importFile) {
      toast.error('请先选择文件')
      return
    }
    importDatasetMutation.mutate({
      kbId,
      folderId: importFolderId,
      file: importFile,
    })
  }

  const handleDownloadDataset = async () => {
    if (!selectedDatasetId || !selectedDataset) {
      return
    }
    const rawName = selectedDataset.display_name || selectedDataset.document.name || 'qa_dataset'
    const fallbackName = rawName.toLowerCase().endsWith('.csv') ? rawName : `${rawName}.csv`
    await exportQADatasetCsv(selectedDatasetId, fallbackName)
  }

  const currentPageSelectedIds = pagedItems.map((item) => item.id)
  const allCurrentPageSelected =
    currentPageSelectedIds.length > 0 && currentPageSelectedIds.every((id) => selectedItemIds.includes(id))

  const toggleSelectItem = (itemId: string, checked: boolean) => {
    setSelectedItemIds((prev) =>
      checked ? Array.from(new Set([...prev, itemId])) : prev.filter((id) => id !== itemId)
    )
  }

  const toggleSelectCurrentPage = (checked: boolean) => {
    setSelectedItemIds((prev) => {
      if (checked) {
        return Array.from(new Set([...prev, ...currentPageSelectedIds]))
      }
      return prev.filter((id) => !currentPageSelectedIds.includes(id))
    })
  }

  const isRefreshingDataList = isFetchingDatasets || isFetchingDetail || isFetchingItems

  const handleRefreshDataList = async () => {
    try {
      if (activeDatasetId) {
        await Promise.all([
          refetchDatasets(),
          refetchDatasetDetail(),
          refetchItems(),
        ])
      } else {
        await refetchDatasets()
      }
      toast.success('列表已刷新')
    } catch {
      toast.error('刷新列表失败，请稍后重试')
    }
  }

  return (
    <div className='flex h-full min-h-0 bg-gradient-to-br from-slate-50 to-blue-50/30'>
      <aside className='flex w-80 flex-col border-r border-slate-200 bg-white/80 backdrop-blur-sm'>
        <div className='border-b border-slate-200 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 p-3'>
          <div className='mb-2 flex items-center gap-2'>
            <div className='rounded-lg bg-blue-500/10 p-1.5'>
              <FileSpreadsheet className='h-4 w-4 text-blue-600' />
            </div>
            <h2 className='text-sm font-semibold text-slate-800'>问答数据集</h2>
          </div>
          <div className='relative'>
            <Search className='absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400' />
            <Input
              value={datasetSearch}
              onChange={(e) => setDatasetSearch(e.target.value)}
              placeholder='搜索问答文件...'
              className='h-8 border-slate-200 bg-white pl-8 text-sm placeholder:text-slate-400 focus-visible:ring-blue-500'
            />
          </div>
        </div>

        <div className='border-b border-slate-200 p-3'>
          <div className='grid grid-cols-2 gap-2'>
            <Button size='sm' variant='outline' onClick={() => downloadQATemplate()}>
              <Download className='mr-1.5 h-3.5 w-3.5' />
              模板
            </Button>
            <Button size='sm' variant='outline' onClick={() => setImportDialogOpen(true)}>
              <Upload className='mr-1.5 h-3.5 w-3.5' />
              导入
            </Button>
            <Button size='sm' variant='outline' className='col-span-2' onClick={() => setDatasetDialogOpen(true)}>
              <Plus className='mr-1.5 h-3.5 w-3.5' />
              新建手工问答集
            </Button>
          </div>
          <div className='mt-3 flex items-center justify-between gap-2 rounded-md border border-slate-200 bg-white px-3 py-2'>
            <div className='flex items-center gap-2'>
              <Switch checked={includeSubfolders} onCheckedChange={setIncludeSubfolders} />
              <span className='text-xs text-slate-600'>包含子文件夹</span>
            </div>
            <Button
              variant='outline'
              size='sm'
              onClick={handleRefreshDataList}
              disabled={isRefreshingDataList}
              className='h-7 px-2 text-xs'
            >
              {isRefreshingDataList ? (
                <Loader2 className='mr-1 h-3.5 w-3.5 animate-spin' />
              ) : (
                <RefreshCw className='mr-1 h-3.5 w-3.5' />
              )}
              刷新列表
            </Button>
          </div>
        </div>

        <div className='min-h-0 flex-1 overflow-y-auto'>
          <div className='space-y-3 p-3'>
            {isLoadingDatasets ? (
              <div className='flex items-center justify-center py-12 text-sm text-slate-500'>
                <Loader2 className='mr-2 h-4 w-4 animate-spin text-blue-500' />
                正在加载数据集...
              </div>
            ) : qaDatasets.length ? (
              qaDatasets.map((dataset) => {
                const isActive = dataset.id === activeDatasetId
                const statusMeta = getDatasetStatusMeta(
                  dataset.parse_status,
                  dataset.runtime_stage,
                  dataset.parse_progress
                )
                return (
                  <button
                    key={dataset.id}
                    type='button'
                    onClick={() => setSelectedDatasetId(dataset.id)}
                    className={`w-full rounded-xl border p-3 text-left transition ${
                      isActive
                        ? 'border-blue-300 bg-blue-50/70 shadow-sm ring-1 ring-blue-200'
                        : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-blue-50/30'
                    }`}
                  >
                    <div className='flex items-start justify-between gap-2'>
                      <div className='min-w-0'>
                        <div className='truncate text-sm font-medium text-slate-800'>
                          {dataset.display_name || dataset.document.name}
                        </div>
                        <div className='mt-1 text-xs text-slate-500'>
                          {dataset.document.file_type || 'FILE'} · {dataset.chunk_count || 0} 切片
                        </div>
                      </div>
                      <Badge className={statusMeta.className}>{statusMeta.label}</Badge>
                    </div>
                  </button>
                )
              })
            ) : (
              <div className='rounded-xl border border-dashed border-slate-300 bg-white/80 p-4 text-sm text-slate-500'>
                当前目录暂无 QA 数据集，先在文件列表上传，或在这里新建手工问答集。
              </div>
            )}
          </div>
        </div>
      </aside>

      <main className='min-w-0 flex-1 p-4'>
        {!activeDatasetId ? (
          <div className='flex h-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-slate-300 bg-white/90 text-sm text-slate-500'>
            <FileSpreadsheet className='h-8 w-8 text-slate-400' />
            <div>请先选择一个问答数据集</div>
          </div>
        ) : (
          <Card className='flex h-full min-h-0 flex-col overflow-hidden border-slate-200 bg-white/95 shadow-sm'>
            <CardHeader className='border-b border-slate-200 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 p-4'>
              <div className='flex flex-wrap items-center justify-between gap-3'>
                <div>
                  <CardTitle className='text-base text-slate-800'>
                    {selectedDataset?.display_name || selectedDataset?.document.name || '问答数据'}
                  </CardTitle>
                  <div className='mt-1 flex items-center gap-2 text-xs text-slate-500'>
                    <span>总条目 {datasetDetail?.item_count ?? items.length}</span>
                    <span>·</span>
                    <span>启用 {datasetDetail?.enabled_item_count ?? 0}</span>
                    <span>·</span>
                    <span>禁用 {datasetDetail?.disabled_item_count ?? 0}</span>
                  </div>
                </div>
                <div className='flex items-center gap-2'>
                  <Button variant='outline' size='sm' onClick={handleDownloadDataset}>
                    <Download className='mr-1.5 h-3.5 w-3.5' />
                    导出 CSV
                  </Button>
                </div>
              </div>

              <div className='mt-3 flex flex-wrap items-center gap-2'>
                <div className='relative min-w-[260px] flex-1'>
                  <Search className='pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400' />
                  <Input
                    value={itemSearch}
                    onChange={(event) => setItemSearch(event.target.value)}
                    placeholder='搜索问题、答案、别名、标签'
                    className='border-slate-200 bg-white pl-9'
                  />
                </div>
                <div className='flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2'>
                  <Switch checked={includeDisabled} onCheckedChange={setIncludeDisabled} />
                  <span className='text-xs text-slate-600'>包含禁用</span>
                </div>
                <Button size='sm' onClick={handleOpenCreateItem}>
                  <Plus className='mr-1.5 h-3.5 w-3.5' />
                  新增问答
                </Button>
              </div>

              {selectedItemIds.length > 0 && (
                // 批量操作仅保留 QA 领域能力，文档重命名/标签维护统一交给文件列表处理
                <div className='mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700'>
                  <span>已选 {selectedItemIds.length} 条</span>
                  <Button
                    size='sm'
                    variant='outline'
                    className='h-7 border-blue-200 bg-white text-blue-700 hover:bg-blue-100'
                    onClick={() => batchToggleItemsMutation.mutate({ item_ids: selectedItemIds, enabled: true })}
                    disabled={batchToggleItemsMutation.isPending}
                  >
                    批量启用
                  </Button>
                  <Button
                    size='sm'
                    variant='outline'
                    className='h-7 border-blue-200 bg-white text-blue-700 hover:bg-blue-100'
                    onClick={() => batchToggleItemsMutation.mutate({ item_ids: selectedItemIds, enabled: false })}
                    disabled={batchToggleItemsMutation.isPending}
                  >
                    批量禁用
                  </Button>
                  <Button
                    size='sm'
                    variant='outline'
                    className='h-7 border-red-200 bg-white text-red-700 hover:bg-red-50'
                    onClick={() => setPendingBatchDelete(true)}
                    disabled={batchDeleteItemsMutation.isPending}
                  >
                    批量删除
                  </Button>
                </div>
              )}
            </CardHeader>

            <CardContent className='min-h-0 flex-1 p-0'>
              <div className='flex h-full min-h-0 flex-col'>
                <div className='min-h-0 flex-1 overflow-x-auto px-4 py-3'>
                  {isLoadingItems || isLoadingDetail ? (
                    <div className='flex items-center justify-center py-16 text-sm text-slate-500'>
                      <Loader2 className='mr-2 h-4 w-4 animate-spin text-blue-500' />
                      正在加载问答数据...
                    </div>
                  ) : pagedItems.length ? (
                    <div className='max-h-full overflow-y-auto rounded-md border'>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className='sticky top-0 z-10 w-[44px] bg-gradient-to-r from-blue-50/50 to-cyan-50/50'>
                              <Checkbox
                                checked={allCurrentPageSelected}
                                onCheckedChange={(checked) => toggleSelectCurrentPage(!!checked)}
                              />
                            </TableHead>
                            <TableHead className='sticky top-0 z-10 min-w-[220px] bg-gradient-to-r from-blue-50/50 to-cyan-50/50'>问题</TableHead>
                            <TableHead className='sticky top-0 z-10 min-w-[280px] bg-gradient-to-r from-blue-50/50 to-cyan-50/50'>答案</TableHead>
                            <TableHead className='sticky top-0 z-10 min-w-[180px] bg-gradient-to-r from-blue-50/50 to-cyan-50/50'>标签/分类</TableHead>
                            <TableHead className='sticky top-0 z-10 w-[80px] bg-gradient-to-r from-blue-50/50 to-cyan-50/50'>状态</TableHead>
                            <TableHead className='sticky right-0 top-0 z-20 w-[210px] bg-white/95 text-right shadow-[-1px_0_0_0_theme(colors.border)] backdrop-blur supports-[backdrop-filter]:bg-background/80'>操作</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {pagedItems.map((item) => (
                            <TableRow key={item.id}>
                              <TableCell>
                                <Checkbox
                                  checked={selectedItemIds.includes(item.id)}
                                  onCheckedChange={(checked) => toggleSelectItem(item.id, !!checked)}
                                />
                              </TableCell>
                              <TableCell>
                                <div className='space-y-1'>
                                  <div className='font-medium text-slate-800'>{item.content_structured.question}</div>
                                  <div className='line-clamp-2 text-xs text-slate-500'>
                                    {(item.content_structured.similar_questions || []).join(' / ') || '无相似问题'
                                    }
                                  </div>
                                </div>
                              </TableCell>
                              <TableCell>
                                <div className='line-clamp-3 whitespace-pre-wrap text-slate-700'>
                                  {item.content_structured.answer}
                                </div>
                              </TableCell>
                              <TableCell>
                                <div className='space-y-1'>
                                  <div className='flex flex-wrap gap-1'>
                                    {(item.content_structured.tags || []).slice(0, 3).map((tag) => (
                                      <Badge key={tag} variant='secondary' className='bg-slate-100 text-slate-700'>
                                        {tag}
                                      </Badge>
                                    ))}
                                  </div>
                                  <div className='text-xs text-slate-500'>
                                    分类：{item.content_structured.category || '-'}
                                  </div>
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge className={item.is_enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'}>
                                  {item.is_enabled ? '启用' : '禁用'}
                                </Badge>
                              </TableCell>
                              <TableCell className='sticky right-0 bg-white/95 text-right shadow-[-1px_0_0_0_theme(colors.border)] backdrop-blur supports-[backdrop-filter]:bg-background/80'>
                                <div className='flex items-center justify-end gap-1'>
                                  <Button variant='ghost' size='icon' onClick={() => setDetailItem(item)}>
                                    <Eye className='h-4 w-4' />
                                  </Button>
                                  <Button variant='ghost' size='icon' onClick={() => handleOpenEditItem(item)}>
                                    <Pencil className='h-4 w-4' />
                                  </Button>
                                  <Button
                                    variant='ghost'
                                    size='icon'
                                    onClick={() => handleMoveItem(item.id, 'up')}
                                    disabled={reorderMutation.isPending}
                                  >
                                    <ArrowUp className='h-4 w-4' />
                                  </Button>
                                  <Button
                                    variant='ghost'
                                    size='icon'
                                    onClick={() => handleMoveItem(item.id, 'down')}
                                    disabled={reorderMutation.isPending}
                                  >
                                    <ArrowDown className='h-4 w-4' />
                                  </Button>
                                  <Button
                                    variant='ghost'
                                    size='icon'
                                    onClick={() => toggleItemMutation.mutate({ item_id: item.id, enabled: !item.is_enabled })}
                                  >
                                    {item.is_enabled ? (
                                      <span className='text-xs text-amber-600'>禁用</span>
                                    ) : (
                                      <span className='text-xs text-emerald-600'>启用</span>
                                    )}
                                  </Button>
                                  <Button variant='ghost' size='icon' onClick={() => setPendingDeleteItem(item)}>
                                    <Trash2 className='h-4 w-4 text-destructive' />
                                  </Button>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className='flex flex-col items-center justify-center gap-3 py-16 text-sm text-slate-500'>
                      <div>当前数据集中还没有可显示的问答条目。</div>
                      <Button size='sm' onClick={handleOpenCreateItem}>
                        <Plus className='mr-1.5 h-3.5 w-3.5' />
                        新增第一条问答
                      </Button>
                    </div>
                  )}
                </div>
                <div className='border-t'>
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
            </CardContent>
          </Card>
        )}
      </main>

      <Dialog open={datasetDialogOpen} onOpenChange={setDatasetDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建手工问答集</DialogTitle>
            <DialogDescription>创建一个可在线维护的 QA 虚拟文件。</DialogDescription>
          </DialogHeader>
          <div className='space-y-4 py-2'>
            <div className='space-y-2'>
              <Label htmlFor='qa-dataset-name'>问答集名称</Label>
              <Input
                id='qa-dataset-name'
                value={datasetName}
                onChange={(event) => setDatasetName(event.target.value)}
                placeholder='例如：售后服务问答集'
              />
            </div>
            <FolderMountField
              kbId={kbId}
              value={datasetFolderId}
              onChange={setDatasetFolderId}
              description='默认使用当前选中的目录，也可以在这里改挂到其他目录。'
            />
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setDatasetDialogOpen(false)}>
              取消
            </Button>
            <Button
              onClick={() =>
                createDatasetMutation.mutate({
                  kb_id: kbId,
                  dataset_name: datasetName.trim(),
                  folder_id: datasetFolderId,
                  items: [],
                })
              }
              disabled={!datasetName.trim() || createDatasetMutation.isPending}
            >
              {createDatasetMutation.isPending && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={itemDialogOpen} onOpenChange={setItemDialogOpen}>
        <DialogContent className='sm:max-w-2xl'>
          <DialogHeader>
            <DialogTitle>{editingItem ? '编辑问答' : '新增问答'}</DialogTitle>
            <DialogDescription>相似问题支持逐条维护，点击新增可继续添加；标签可使用中文或英文逗号/分号分隔。</DialogDescription>
          </DialogHeader>
          <div className='grid gap-4 py-2'>
            <div className='space-y-2'>
              <Label>问题</Label>
              <Input value={itemForm.question} onChange={(e) => setItemForm((prev) => ({ ...prev, question: e.target.value }))} />
            </div>
            <div className='space-y-2'>
              <Label>答案</Label>
              <Textarea
                rows={6}
                value={itemForm.answer}
                onChange={(e) => setItemForm((prev) => ({ ...prev, answer: e.target.value }))}
              />
            </div>
            <div className='space-y-2'>
              <div className='flex items-center justify-between'>
                <Label>相似问题</Label>
                <Button type='button' size='sm' variant='outline' onClick={addAliasRow}>
                  <Plus className='mr-1.5 h-3.5 w-3.5' />
                  新增记录
                </Button>
              </div>
              <div className='space-y-2'>
                {itemForm.questionAliases.map((alias, index) => (
                  <div key={`alias-${index}`} className='flex items-center gap-2'>
                    <Input
                      value={alias}
                      onChange={(e) => updateAliasAt(index, e.target.value)}
                      placeholder={`别名 ${index + 1}，例如：密码重置入口在哪`}
                      className='flex-1'
                    />
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      onClick={() => removeAliasRow(index)}
                    >
                      删除记录
                    </Button>
                  </div>
                ))}
              </div>
            </div>
            <div className='grid gap-4 md:grid-cols-2'>
              <div className='space-y-2'>
                <Label>分类</Label>
                <Input
                  value={itemForm.category}
                  onChange={(e) => setItemForm((prev) => ({ ...prev, category: e.target.value }))}
                  placeholder='账号管理'
                />
              </div>
              <div className='space-y-2'>
                <Label>标签</Label>
                <Input
                  value={itemForm.tags}
                  onChange={(e) => setItemForm((prev) => ({ ...prev, tags: e.target.value }))}
                  placeholder='账号，登录'
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setItemDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSaveItem} disabled={createItemMutation.isPending || updateItemMutation.isPending}>
              {(createItemMutation.isPending || updateItemMutation.isPending) && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={importDialogOpen}
        onOpenChange={(open) => {
          setImportDialogOpen(open)
          if (!open) {
            setImportFile(null)
            setImportPreview(null)
            setImportFolderId(selectedFolderId)
          }
        }}
      >
        <DialogContent className='sm:max-w-2xl'>
          <DialogHeader>
            <DialogTitle>导入问答文件</DialogTitle>
            <DialogDescription>支持导入 `.csv` / `.xlsx` 模板文件，并挂载到当前目录或指定目录。</DialogDescription>
          </DialogHeader>
          <div className='space-y-4 py-2'>
            <FolderMountField
              kbId={kbId}
              value={importFolderId}
              onChange={setImportFolderId}
              description='如果不修改，导入后的问答集会落在当前选中的目录。'
            />
            <div className='space-y-2'>
              <Label htmlFor='qa-import-file'>问答文件</Label>
              <Input
                id='qa-import-file'
                type='file'
                accept='.csv,.xlsx'
                onChange={(event) => {
                  const nextFile = event.target.files?.[0] || null
                  setImportFile(nextFile)
                  setImportPreview(null)
                }}
              />
            </div>
            {importFile ? (
              <div className='rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600'>
                已选择文件：{importFile.name}
              </div>
            ) : null}
            {importPreview ? (
              <div className='space-y-2 rounded-lg border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-600'>
                <div className='flex flex-wrap items-center gap-2'>
                  <Badge variant='secondary'>共 {importPreview.item_count} 条</Badge>
                  <Badge variant='secondary'>启用 {importPreview.enabled_item_count} 条</Badge>
                  <Badge variant='secondary'>禁用 {importPreview.disabled_item_count} 条</Badge>
                </div>
                <div className='rounded-md border border-dashed border-slate-300 bg-white px-3 py-2 text-xs text-slate-500'>
                  必填列：{importPreview.required_headers.join('、')}
                </div>
              </div>
            ) : null}
          </div>
          <DialogFooter className='gap-2 sm:justify-between'>
            <Button variant='outline' onClick={() => downloadQATemplate()}>
              <Download className='mr-1.5 h-3.5 w-3.5' />
              下载模板
            </Button>
            <div className='flex items-center gap-2'>
              <Button variant='outline' onClick={() => setImportDialogOpen(false)}>
                取消
              </Button>
              <Button
                variant='outline'
                disabled={!importFile || previewImportMutation.isPending}
                onClick={handlePreviewImport}
              >
                {previewImportMutation.isPending ? <Loader2 className='mr-1.5 h-3.5 w-3.5 animate-spin' /> : null}
                预检
              </Button>
              <Button
                disabled={!importFile || importDatasetMutation.isPending}
                onClick={handleImportDataset}
              >
                {importDatasetMutation.isPending ? <Loader2 className='mr-1.5 h-3.5 w-3.5 animate-spin' /> : null}
                开始导入
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!detailItem} onOpenChange={(open) => !open && setDetailItem(null)}>
        <DialogContent className='sm:max-w-3xl'>
          <DialogHeader>
            <DialogTitle>问答详情</DialogTitle>
            <DialogDescription>查看当前问答的完整内容、别名、标签和来源信息。</DialogDescription>
          </DialogHeader>
          {detailItem ? (
            <div className='space-y-5 py-2'>
              <div className='space-y-2'>
                <Label>问题</Label>
                <div className='rounded-xl border bg-muted/20 px-4 py-3 text-sm leading-6'>
                  {detailItem.content_structured.question}
                </div>
              </div>
              <div className='space-y-2'>
                <Label>答案</Label>
                <div className='max-h-72 overflow-auto rounded-xl border bg-muted/20 px-4 py-3 text-sm leading-6 whitespace-pre-wrap'>
                  {detailItem.content_structured.answer}
                </div>
              </div>
              {(detailItem.content_structured.similar_questions || []).length > 0 ? (
                <div className='space-y-2'>
                  <Label>相似问题</Label>
                  <div className='flex flex-wrap gap-2'>
                    {detailItem.content_structured.similar_questions.map((alias) => (
                      <Badge key={alias} variant='outline'>
                        {alias}
                      </Badge>
                    ))}
                  </div>
                </div>
              ) : null}
              <div className='grid gap-4 md:grid-cols-2'>
                <div className='space-y-2'>
                  <Label>分类</Label>
                  <div className='rounded-xl border bg-muted/20 px-4 py-3 text-sm'>
                    {detailItem.content_structured.category || '未设置'}
                  </div>
                </div>
                <div className='space-y-2'>
                  <Label>状态</Label>
                  <div className='rounded-xl border bg-muted/20 px-4 py-3 text-sm'>
                    {detailItem.is_enabled ? '启用' : '禁用'}
                  </div>
                </div>
              </div>
              <div className='space-y-2'>
                <Label>标签</Label>
                <div className='flex min-h-12 flex-wrap gap-2 rounded-xl border bg-muted/20 px-4 py-3'>
                  {(detailItem.content_structured.tags || []).length > 0 ? (
                    detailItem.content_structured.tags.map((tag) => (
                      <Badge key={tag} variant='secondary'>
                        {tag}
                      </Badge>
                    ))
                  ) : (
                    <span className='text-sm text-muted-foreground'>未设置标签</span>
                  )}
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant='outline' onClick={() => setDetailItem(null)}>
              关闭
            </Button>
            {detailItem ? (
              <Button
                onClick={() => {
                  setDetailItem(null)
                  handleOpenEditItem(detailItem)
                }}
              >
                编辑问答
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!pendingDeleteItem}
        onOpenChange={(open) => {
          if (!open) {
            setPendingDeleteItem(null)
          }
        }}
        title='确认删除问答？'
        description={
          pendingDeleteItem ? `删除后将同步移除该问答对应的检索切片：${pendingDeleteItem.content_structured.question}` : ''
        }
        onConfirm={() => {
          if (pendingDeleteItem) {
            deleteItemMutation.mutate(pendingDeleteItem.id)
          }
        }}
        loading={deleteItemMutation.isPending}
        confirmText='确认删除'
      />

      <ConfirmDialog
        open={pendingBatchDelete}
        onOpenChange={setPendingBatchDelete}
        title='确认批量删除问答？'
        description={`删除后将同步移除这 ${selectedItemIds.length} 条问答及其检索切片，该操作不可撤销。`}
        onConfirm={() => {
          if (selectedItemIds.length > 0) {
            batchDeleteItemsMutation.mutate(selectedItemIds)
          }
        }}
        loading={batchDeleteItemsMutation.isPending}
        confirmText='确认批量删除'
      />
    </div>
  )
}
