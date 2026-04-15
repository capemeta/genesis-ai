import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import {
  Database,
  FileSpreadsheet,
  Eye,
  Loader2,
  Pencil,
  Plus,
  Search,
  Settings2,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'

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
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { Pagination } from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/pagination'
import {
  fetchKnowledgeBase,
  fetchKnowledgeBaseDocuments,
  type KnowledgeBaseDocument,
  type TableSchemaColumn,
  type TableColumnType,
} from '@/lib/api/knowledge-base'
import {
  createTableRow,
  deleteTableRow,
  fetchTableRows,
  updateTableRow,
  type TableRowItem,
} from '@/lib/api/table-rows'

interface TableManagerProps {
  kbId: string
  selectedFolderId?: string | null
}

type EditorMode = 'create' | 'edit'

interface EditorState {
  mode: EditorMode
  row: TableRowItem | null
  sheetName: string
  values: Record<string, string>
  columns: string[]
}

interface RowDetailState {
  row: TableRowItem
  columns: string[]
}

const EMPTY_TABLE_ROWS: TableRowItem[] = []
const EMPTY_VISIBLE_COLUMNS: string[] = []
const DEFAULT_VISIBLE_COLUMN_LIMIT = 12

function getRequestErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return fallback
}

function getInputTypeByColumnType(columnType?: TableColumnType): 'text' | 'number' | 'datetime-local' {
  if (columnType === 'int' || columnType === 'float') {
    return 'number'
  }
  if (columnType === 'datetime') {
    return 'datetime-local'
  }
  return 'text'
}

function parseBooleanLike(value: unknown): boolean | null {
  const normalizedValue = String(value ?? '').trim().toLowerCase()
  if (!normalizedValue) {
    return null
  }
  if (['true', '1', 'yes', 'y', '是'].includes(normalizedValue)) {
    return true
  }
  if (['false', '0', 'no', 'n', '否'].includes(normalizedValue)) {
    return false
  }
  return null
}

function getBooleanSelectValue(value: unknown): string {
  const parsed = parseBooleanLike(value)
  if (parsed === true) {
    return 'true'
  }
  if (parsed === false) {
    return 'false'
  }
  return '__empty__'
}

function formatCellValue(value: unknown, columnType?: TableColumnType): string {
  if (columnType === 'bool') {
    const parsed = parseBooleanLike(value)
    if (parsed === true) {
      return '是'
    }
    if (parsed === false) {
      return '否'
    }
    return ''
  }
  return String(value ?? '')
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
    case 'cancelled':
      return {
        label: '已取消',
        className: 'bg-gray-100 text-gray-700 hover:bg-gray-100',
      }
    case 'cancelling':
      return {
        label: '取消中',
        className: 'bg-orange-100 text-orange-700 hover:bg-orange-100',
      }
    default:
      return {
        label: '等待启动',
        className: 'bg-slate-100 text-slate-700 hover:bg-slate-100',
      }
  }
}

function getVisibleColumns(
  row?: TableRowItem | null,
  sheetHeaders?: Record<string, string[]>
): string[] {
  if (!row) {
    return []
  }
  const sheetHeader = sheetHeaders?.[row.sheet_name]
  if (Array.isArray(sheetHeader) && sheetHeader.length) {
    return sheetHeader.map((item) => String(item))
  }
  const sourceHeader = row.source_meta?.header
  if (Array.isArray(sourceHeader) && sourceHeader.length) {
    return sourceHeader.map((item) => String(item))
  }
  return Object.keys(row.row_data || {})
}

function shouldUseTextarea(columnType?: TableColumnType): boolean {
  return !columnType || columnType === 'text'
}

function getTextareaRows(value: string): number {
  const lineCount = value.split(/\r?\n/).length
  return Math.min(Math.max(lineCount, 1), 8)
}

function normalizeVisibleColumns(
  selectedColumns: string[],
  availableColumns: string[],
  fallbackLimit = 12,
  allowEmpty = false
): string[] {
  if (!availableColumns.length) {
    return []
  }

  if (!selectedColumns.length) {
    return allowEmpty ? [] : availableColumns.slice(0, fallbackLimit)
  }

  const selectedSet = new Set(
    selectedColumns.filter((column) => availableColumns.includes(column))
  )
  const orderedColumns = availableColumns.filter((column) => selectedSet.has(column))
  if (orderedColumns.length) {
    return orderedColumns
  }
  return allowEmpty ? [] : availableColumns.slice(0, fallbackLimit)
}

function validateEditorValues(
  columns: string[],
  values: Record<string, string>,
  schemaColumnMap: Record<string, TableSchemaColumn>
): string | null {
  for (const column of columns) {
    const schema = schemaColumnMap[column]
    const rawValue = values[column] ?? ''
    const normalizedValue = rawValue.trim()

    if (schema && !schema.nullable && !normalizedValue) {
      return `字段“${column}”不能为空`
    }

    if (!normalizedValue) {
      continue
    }

    if (schema?.type === 'int' && !/^-?\d+$/.test(normalizedValue)) {
      return `字段“${column}”必须是整数`
    }

    if (schema?.type === 'float' && Number.isNaN(Number(normalizedValue))) {
      return `字段“${column}”必须是数字`
    }

    if (schema?.type === 'datetime' && Number.isNaN(Date.parse(normalizedValue))) {
      return `字段“${column}”必须是有效时间`
    }

    if (schema?.type === 'bool' && parseBooleanLike(normalizedValue) === null) {
      return `字段“${column}”必须是布尔值`
    }
  }

  return null
}

export function TableManager({ kbId, selectedFolderId }: TableManagerProps) {
  const queryClient = useQueryClient()
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [datasetSearch, setDatasetSearch] = useState('')
  const [rowSearch, setRowSearch] = useState('')
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({})
  const [visibleColumns, setVisibleColumns] = useState<string[]>([])
  const [hasCustomizedVisibleColumns, setHasCustomizedVisibleColumns] = useState(false)
  const [showAllFilterFields, setShowAllFilterFields] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editorState, setEditorState] = useState<EditorState | null>(null)
  const [rowDetailState, setRowDetailState] = useState<RowDetailState | null>(null)

  const { data: documentsResponse, isLoading: isLoadingDatasets } = useQuery({
    queryKey: ['table-datasets', kbId, selectedFolderId],
    queryFn: () =>
      fetchKnowledgeBaseDocuments(kbId, {
        folder_id: selectedFolderId || null,
        include_subfolders: true,
        page: 1,
        page_size: 100,
      }),
    enabled: !!kbId,
  })

  const { data: knowledgeBase } = useQuery({
    queryKey: ['knowledge-base', kbId],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: !!kbId,
  })

  const rawSchemaColumns = knowledgeBase?.retrieval_config?.table?.schema?.columns
  const schemaColumns = useMemo<TableSchemaColumn[]>(
    () => (Array.isArray(rawSchemaColumns) ? rawSchemaColumns : []),
    [rawSchemaColumns]
  )

  const schemaColumnMap = useMemo(
    () =>
      schemaColumns.reduce<Record<string, TableSchemaColumn>>((acc, column) => {
        if (column.name) {
          acc[column.name] = column
        }
        return acc
      }, {}),
    [schemaColumns]
  )

  const datasets = useMemo(() => {
    const docs = documentsResponse?.data || []
    const keyword = datasetSearch.trim().toLowerCase()
    return docs.filter((dataset: KnowledgeBaseDocument) => {
      const contentKind = String(dataset.document?.metadata?.content_kind || '').trim()
      if (contentKind && contentKind !== 'table_dataset') {
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
  }, [datasetSearch, documentsResponse])

  const activeDatasetId = useMemo(() => {
    if (!datasets.length) {
      return null
    }
    if (selectedDatasetId && datasets.some((item) => item.id === selectedDatasetId)) {
      return selectedDatasetId
    }
    return datasets[0].id
  }, [datasets, selectedDatasetId])

  const filterableColumns = useMemo(() => {
    return schemaColumns.filter((column) => column.filterable).map((column) => column.name).filter(Boolean)
  }, [schemaColumns])

  const sanitizedColumnFilters: Record<string, string> = {}
  for (const column of filterableColumns) {
    if (columnFilters[column]) {
      sanitizedColumnFilters[column] = columnFilters[column]
    }
  }

  const { data: rowsResponse, isLoading: isLoadingRows } = useQuery({
    queryKey: ['table-rows', activeDatasetId, currentPage, pageSize, rowSearch, sanitizedColumnFilters],
    queryFn: () =>
      fetchTableRows(activeDatasetId!, {
        page: currentPage,
        page_size: pageSize,
        search: rowSearch.trim(),
        column_filters: sanitizedColumnFilters,
      }),
    enabled: !!activeDatasetId,
  })

  const rows = rowsResponse?.rows ?? EMPTY_TABLE_ROWS
  const datasetDetail = rowsResponse?.dataset
  const datasetSheetHeaders = useMemo(() => {
    const rawMap = datasetDetail?.metadata?.table_sheet_headers
    if (!rawMap || typeof rawMap !== 'object') {
      return {}
    }
    return Object.entries(rawMap as Record<string, unknown>).reduce<Record<string, string[]>>(
      (acc, [sheetName, header]) => {
        if (Array.isArray(header) && header.length) {
          acc[sheetName] = header.map((item) => String(item))
        }
        return acc
      },
      {}
    )
  }, [datasetDetail?.metadata?.table_sheet_headers])

  const totalRows = rowsResponse?.total || 0
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize))
  const safeCurrentPage = Math.min(currentPage, totalPages)
  const startIndex = totalRows ? (safeCurrentPage - 1) * pageSize : 0
  const endIndex = Math.min(startIndex + rows.length, totalRows)

  const availableColumns = useMemo(() => {
    const columnNames = schemaColumns.map((column) => column.name).filter(Boolean)
    if (columnNames.length) {
      return columnNames
    }
    return getVisibleColumns(rows[0] || null, datasetSheetHeaders)
  }, [schemaColumns, rows, datasetSheetHeaders])

  const normalizedVisibleColumns = hasCustomizedVisibleColumns
    ? normalizeVisibleColumns(
        visibleColumns,
        availableColumns,
        DEFAULT_VISIBLE_COLUMN_LIMIT,
        true
      )
    : normalizeVisibleColumns(EMPTY_VISIBLE_COLUMNS, availableColumns, DEFAULT_VISIBLE_COLUMN_LIMIT)

  const hiddenColumnCount = Math.max(0, availableColumns.length - normalizedVisibleColumns.length)
  const visibleFilterColumns = showAllFilterFields && filterableColumns.length > 6
    ? filterableColumns
    : filterableColumns.slice(0, 6)
  const isAllColumnsVisible =
    availableColumns.length > 0 && normalizedVisibleColumns.length === availableColumns.length
  const hasVisibleColumns = normalizedVisibleColumns.length > 0

  const updateVisibleColumns = (nextColumns: string[]) => {
    setHasCustomizedVisibleColumns(true)
    setVisibleColumns(
      normalizeVisibleColumns(nextColumns, availableColumns, DEFAULT_VISIBLE_COLUMN_LIMIT, true)
    )
  }

  const resetVisibleColumns = () => {
    setHasCustomizedVisibleColumns(false)
    setVisibleColumns(EMPTY_VISIBLE_COLUMNS)
  }

  const defaultSheetName = useMemo(() => {
    if (rows.length) {
      return rows[0].sheet_name
    }
    return 'Sheet1'
  }, [rows])

  const refreshSelectedDataset = async (kbDocId?: string | null) => {
    await queryClient.invalidateQueries({ queryKey: ['table-datasets', kbId] })
    await queryClient.invalidateQueries({ queryKey: ['table-datasets', kbId, selectedFolderId] })
    if (kbDocId) {
      await queryClient.invalidateQueries({ queryKey: ['table-rows', kbDocId] })
    }
  }

  const updateRowMutation = useMutation({
    mutationFn: updateTableRow,
    onSuccess: async () => {
      toast.success('表格行已更新，当前数据集已置为待重新解析')
      setEditorState(null)
      await refreshSelectedDataset(activeDatasetId)
    },
    onError: (error: unknown) => {
      toast.error(getRequestErrorMessage(error, '更新表格行失败'))
    },
  })

  const createRowMutation = useMutation({
    mutationFn: createTableRow,
    onSuccess: async () => {
      toast.success('表格行已新增，当前数据集已置为待重新解析')
      setEditorState(null)
      await refreshSelectedDataset(activeDatasetId)
    },
    onError: (error: unknown) => {
      toast.error(getRequestErrorMessage(error, '新增表格行失败'))
    },
  })

  const deleteRowMutation = useMutation({
    mutationFn: deleteTableRow,
    onSuccess: async () => {
      toast.success('表格行已删除，当前数据集已置为待重新解析')
      await refreshSelectedDataset(activeDatasetId)
    },
    onError: (error: unknown) => {
      toast.error(getRequestErrorMessage(error, '删除表格行失败'))
    },
  })

  const openEditDialog = (row: TableRowItem) => {
    const nextValues: Record<string, string> = {}
    Object.entries(row.row_data || {}).forEach(([key, value]) => {
      nextValues[key] = value == null ? '' : String(value)
    })
    const columnNames = schemaColumns.map((column) => column.name).filter(Boolean)
    setEditorState({
      mode: 'edit',
      row,
      sheetName: row.sheet_name,
      values: nextValues,
      columns: columnNames.length ? columnNames : getVisibleColumns(row, datasetSheetHeaders),
    })
  }

  const openRowDetailDialog = (row: TableRowItem) => {
    const columnNames = schemaColumns.map((column) => column.name).filter(Boolean)

    setRowDetailState({
      row,
      columns: columnNames.length ? columnNames : getVisibleColumns(row, datasetSheetHeaders),
    })
  }

  const openCreateDialog = () => {
    const baseRow = rows[0] || null
    const schemaColumnNames = schemaColumns.map((column) => column.name).filter(Boolean)
    const columns = schemaColumnNames.length
      ? schemaColumnNames
      : getVisibleColumns(baseRow, datasetSheetHeaders)
    const initialValues = columns.reduce<Record<string, string>>((acc, column) => {
      acc[column] = ''
      return acc
    }, {})
    setEditorState({
      mode: 'create',
      row: null,
      sheetName: defaultSheetName,
      values: initialValues,
      columns,
    })
  }

  const handleSaveRow = async () => {
    if (!activeDatasetId || !editorState) {
      return
    }
    const validationMessage = validateEditorValues(
      editorState.columns,
      editorState.values,
      schemaColumnMap
    )
    if (validationMessage) {
      toast.error(validationMessage)
      return
    }

    const normalizedRowData = Object.entries(editorState.values).reduce<Record<string, string>>(
      (acc, [key, value]) => {
        acc[key] = value
        return acc
      },
      {}
    )

    if (editorState.mode === 'edit' && editorState.row) {
      await updateRowMutation.mutateAsync({
        row_id: editorState.row.id,
        item: {
          row_data: normalizedRowData,
        },
      })
      return
    }

    await createRowMutation.mutateAsync({
      kb_doc_id: activeDatasetId,
      item: {
        sheet_name: editorState.sheetName.trim() || defaultSheetName,
        row_data: normalizedRowData,
      },
    })
  }

  const handleDeleteRow = async (row: TableRowItem) => {
    await deleteRowMutation.mutateAsync({ row_id: row.id })
  }

  const isSaving = updateRowMutation.isPending || createRowMutation.isPending

  return (
    <div className='flex h-full min-h-0 bg-gradient-to-br from-slate-50 to-blue-50/30'>
      <aside className='flex w-80 flex-col border-r border-slate-200 bg-white/80 backdrop-blur-sm'>
        <div className='border-b border-slate-200 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 p-3'>
          <div className='mb-2 flex items-center gap-2'>
            <div className='rounded-lg bg-blue-500/10 p-1.5'>
              <FileSpreadsheet className='h-4 w-4 text-blue-600' />
            </div>
            <h2 className='text-sm font-semibold text-slate-800'>表格文件</h2>
          </div>
          <div className='relative'>
            <Search className='absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400' />
            <Input
              value={datasetSearch}
              onChange={(e) => setDatasetSearch(e.target.value)}
              placeholder='搜索表格文件...'
              className='h-8 border-slate-200 bg-white pl-8 text-sm placeholder:text-slate-400 focus-visible:ring-blue-500'
            />
          </div>
        </div>
        <div className='min-h-0 flex-1 overflow-y-auto'>
          <div className='space-y-3 p-3'>
            {isLoadingDatasets ? (
              <div className='flex items-center justify-center py-12 text-sm text-slate-500'>
                <Loader2 className='mr-2 h-4 w-4 animate-spin text-blue-500' />
                正在加载数据集...
              </div>
            ) : datasets.length ? (
              datasets.map((dataset) => {
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
                    onClick={() => {
                      setSelectedDatasetId(dataset.id)
                      setCurrentPage(1)
                      setVisibleColumns(EMPTY_VISIBLE_COLUMNS)
                      setHasCustomizedVisibleColumns(false)
                    }}
                    title={dataset.display_name || dataset.document.name}
                    className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                      isActive
                        ? 'border-blue-300 bg-gradient-to-r from-blue-50 to-cyan-50 shadow-sm'
                        : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-blue-50/30'
                    }`}
                  >
                    <div className='flex items-start justify-between gap-3'>
                      <div className='min-w-0'>
                        <p className='truncate text-sm font-medium text-slate-800'>
                          {dataset.display_name || dataset.document.name}
                        </p>
                        <p className='mt-1 text-xs text-slate-500'>
                          {dataset.document.file_type} · 结构化表格文件
                        </p>
                      </div>
                      <Badge variant='secondary' className={statusMeta.className}>
                        {statusMeta.label}
                      </Badge>
                    </div>
                  </button>
                )
              })
            ) : (
              <div className='rounded-xl border border-dashed p-6 text-sm text-slate-500'>
                当前还没有表格数据集。先在“内容管理”中上传并解析 Excel/CSV 文件。
              </div>
            )}
          </div>
        </div>
      </aside>

      <main className='flex min-w-0 flex-1 flex-col'>
        {!activeDatasetId ? (
          <div className='flex h-full flex-col items-center justify-center gap-3 text-slate-500'>
            <Database className='h-10 w-10 text-blue-400' />
            <p className='text-sm'>请选择左侧一个表格数据集</p>
          </div>
        ) : (
          <>
            <div className='min-h-0 flex-1 p-4'>
              <Card className='flex h-full flex-col border-slate-200 bg-white shadow-sm'>
                <CardHeader className='border-b border-slate-200 bg-gradient-to-r from-blue-50/30 to-cyan-50/30 px-4 py-2.5'>
                    <div className='space-y-3'>
                      <div className='flex items-start justify-between gap-3 border-b pb-3'>
                        <div className='min-w-0'>
                          <CardTitle className='truncate text-sm font-semibold text-slate-800' title={datasetDetail?.display_name || '表格记录'}>
                            {datasetDetail?.display_name || '表格记录'}
                          </CardTitle>
                          <div className='mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500'>
                            <span>共 {datasetDetail?.row_count ?? 0} 条记录</span>
                            {datasetDetail?.pending_reparse_row_count ? (
                              <Badge
                                variant='secondary'
                                className='border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-50'
                              >
                                {datasetDetail.pending_reparse_row_count} 次变更待重解析
                              </Badge>
                            ) : null}
                            {datasetDetail?.parse_error ? (
                              <span className='text-amber-600'>{datasetDetail.parse_error}</span>
                            ) : null}
                          </div>
                        </div>
                        <div className='flex items-center gap-2'>
                          <Button variant='outline' size='sm' className='border-blue-200 text-blue-700 hover:bg-blue-50' onClick={openCreateDialog} disabled={!activeDatasetId}>
                            <Plus className='mr-2 h-4 w-4' />
                            新增记录
                          </Button>
                        </div>
                      </div>

                      <div className='flex items-center justify-between gap-3'>
                        <div className='space-y-1'>
                          <CardTitle className='text-sm'>表格记录</CardTitle>
                          <p className='text-xs text-slate-500'>
                            左侧字段输入用于按指定列筛选，右侧搜索用于按可检索字段做关键词匹配。
                          </p>
                        </div>
                        <div className='flex items-center gap-2'>
                          <div className='relative w-64 max-w-full'>
                            <Search className='absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground' />
                            <Input
                              value={rowSearch}
                              onChange={(e) => {
                                setRowSearch(e.target.value)
                                setCurrentPage(1)
                              }}
                              placeholder='搜索记录（按可检索字段）...'
                              className='h-8 pl-8 border-slate-200 focus-visible:ring-blue-500'
                            />
                          </div>
                          <Popover>
                            <PopoverTrigger asChild>
                              <Button variant='outline' size='icon' className='h-8 w-8' title='列显示设置'>
                                <Settings2 className='h-3.5 w-3.5' />
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent align='end' className='w-64'>
                              <div className='space-y-3'>
                                <div>
                                  <div className='text-sm font-semibold text-slate-800'>显示列</div>
                                  <p className='mt-1 text-xs text-slate-500'>
                                    当前共 {availableColumns.length} 列，已显示 {normalizedVisibleColumns.length} 列；列较多时可横向滚动查看。
                                  </p>
                                </div>
                                <div className='flex items-center justify-between gap-3 rounded-lg border bg-muted/20 px-3 py-2'>
                                  <label className='flex items-center gap-2 text-sm font-medium text-slate-700'>
                                    <Checkbox
                                      checked={isAllColumnsVisible}
                                      onCheckedChange={(nextChecked) => {
                                        updateVisibleColumns(nextChecked ? availableColumns : [])
                                      }}
                                    />
                                    <span>全选显示列</span>
                                  </label>
                                  <Button
                                    type='button'
                                    variant='ghost'
                                    size='sm'
                                    className='h-7 px-2 text-xs'
                                    disabled={!hasCustomizedVisibleColumns && hasVisibleColumns}
                                    onClick={resetVisibleColumns}
                                  >
                                    恢复默认
                                  </Button>
                                </div>
                                <div className='space-y-1.5'>
                                  {availableColumns.map((column) => {
                                    const checked = normalizedVisibleColumns.includes(column)
                                    return (
                                      <label key={column} className='flex items-center gap-2 text-sm text-slate-700'>
                                        <Checkbox
                                          checked={checked}
                                          onCheckedChange={(nextChecked) => {
                                            updateVisibleColumns(
                                              nextChecked
                                                ? [...normalizedVisibleColumns, column]
                                                : normalizedVisibleColumns.filter((item) => item !== column)
                                            )
                                          }}
                                        />
                                        <span>{column}</span>
                                      </label>
                                    )
                                  })}
                                </div>
                              </div>
                            </PopoverContent>
                          </Popover>
                        </div>
                      </div>

                      <div className='flex flex-wrap items-center gap-2 text-xs text-slate-500'>
                        {hiddenColumnCount > 0 ? (
                          <>
                            <span>当前有 {hiddenColumnCount} 列未展示。</span>
                            <button
                              type='button'
                              className='font-medium text-blue-600 underline-offset-4 hover:underline'
                              onClick={() => updateVisibleColumns(availableColumns)}
                            >
                              一键显示全部列
                            </button>
                          </>
                        ) : null}
                      </div>

                    {filterableColumns.length ? (
                      <div className='space-y-1.5'>
                        <div className='grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3'>
                        {visibleFilterColumns.map((column) => (
                          <div key={column} className='min-w-0'>
                            <Input
                              value={sanitizedColumnFilters[column] || ''}
                              onChange={(e) => {
                                setColumnFilters((prev) => ({
                                  ...prev,
                                  [column]: e.target.value,
                                }))
                                setCurrentPage(1)
                              }}
                              placeholder={`筛选 ${column}`}
                              className='h-8 border-slate-200 focus-visible:ring-blue-500'
                            />
                          </div>
                        ))}
                        </div>
                        {filterableColumns.length > visibleFilterColumns.length ? (
                          <button
                            type='button'
                            className='text-xs font-medium text-blue-600 underline-offset-4 hover:underline'
                            onClick={() => setShowAllFilterFields(true)}
                          >
                            展开剩余 {filterableColumns.length - visibleFilterColumns.length} 个过滤字段
                          </button>
                        ) : null}
                        {showAllFilterFields && filterableColumns.length > 6 ? (
                          <button
                            type='button'
                            className='text-xs text-slate-500 underline-offset-4 hover:underline'
                            onClick={() => setShowAllFilterFields(false)}
                          >
                            收起过滤字段
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </CardHeader>
                <CardContent className='min-h-0 flex-1 p-0'>
                  <div className='flex h-full min-h-0 flex-col'>
                    <div className='min-h-0 flex-1 overflow-x-auto px-4 py-3'>
                      {isLoadingRows ? (
                        <div className='flex items-center justify-center py-16 text-sm text-slate-500'>
                          <Loader2 className='mr-2 h-4 w-4 animate-spin text-blue-500' />
                          正在加载表格数据...
                        </div>
                      ) : rows.length ? (
                        <div className='min-w-max'>
                          <div className='max-h-full overflow-y-auto rounded-md border'>
                            <table className='w-full caption-bottom text-sm'>
                              <TableHeader>
                                <TableRow>
                                  <TableHead className='sticky top-0 z-10 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 font-medium text-slate-700 w-[120px]'>Sheet</TableHead>
                                  <TableHead className='sticky top-0 z-10 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 font-medium text-slate-700 w-[90px]'>行号</TableHead>
                                  {normalizedVisibleColumns.map((column) => (
                                    <TableHead key={column} className='sticky top-0 z-10 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 font-medium text-slate-700'>
                                      {column}
                                    </TableHead>
                                  ))}
                                  <TableHead className='sticky top-0 z-10 bg-gradient-to-r from-blue-50/50 to-cyan-50/50 font-medium text-slate-700 w-[120px]'>来源</TableHead>
                                  <TableHead className='sticky right-0 top-0 z-20 w-[160px] bg-background/95 text-right backdrop-blur supports-[backdrop-filter]:bg-background/80 shadow-[-1px_0_0_0_theme(colors.border)]'>
                                    操作
                                  </TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {rows.map((row) => (
                                  <TableRow key={row.id}>
                                    <TableCell title={row.sheet_name}>
                                      <div className='font-medium'>{row.sheet_name}</div>
                                    </TableCell>
                                    <TableCell>
                                      <div className='font-medium'>{row.row_index}</div>
                                    </TableCell>
                                    {normalizedVisibleColumns.map((column) => (
                                      <TableCell key={column} className='max-w-[260px] align-top'>
                                        <div
                                          className='line-clamp-3 whitespace-pre-wrap break-all'
                                          title={formatCellValue(row.row_data?.[column], schemaColumnMap[column]?.type)}
                                        >
                                          {formatCellValue(row.row_data?.[column], schemaColumnMap[column]?.type)}
                                        </div>
                                      </TableCell>
                                    ))}
                                    <TableCell>
                                      <Badge variant={row.source_type === 'manual' ? 'secondary' : 'outline'} className={row.source_type === 'manual' ? 'bg-blue-100 text-blue-700' : ''}>
                                        {row.source_type === 'manual' ? '手工维护' : 'Excel导入'}
                                      </Badge>
                                    </TableCell>
                                    <TableCell className='sticky right-0 z-10 bg-white/95 text-right backdrop-blur supports-[backdrop-filter]:bg-background/80 shadow-[-1px_0_0_0_theme(colors.border)]'>
                                      <div className='flex items-center justify-end gap-1'>
                                        <Button variant='ghost' size='icon' onClick={() => openRowDetailDialog(row)}>
                                          <Eye className='h-4 w-4' />
                                        </Button>
                                        <Button variant='ghost' size='icon' onClick={() => openEditDialog(row)}>
                                          <Pencil className='h-4 w-4' />
                                        </Button>
                                        <Button
                                          variant='ghost'
                                          size='icon'
                                          onClick={() => handleDeleteRow(row)}
                                          disabled={deleteRowMutation.isPending}
                                        >
                                          <Trash2 className='h-4 w-4 text-destructive' />
                                        </Button>
                                      </div>
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </table>
                          </div>
                        </div>
                      ) : (
                        <div className='flex flex-col items-center justify-center gap-3 py-16 text-sm text-slate-500'>
                          <div>当前数据集中还没有可显示的行。</div>
                          {datasetDetail?.parse_status === 'pending' ? (
                            <div className='text-xs text-amber-600 font-medium'>
                              当前文件还未开始解析，请回到“文件列表”触发解析后再查看数据视图。
                            </div>
                          ) : null}
                          {datasetDetail?.parse_status === 'queued' || datasetDetail?.parse_status === 'processing' ? (
                            <div className='text-xs text-slate-500'>
                              当前文件正在解析中，解析完成后这里会自动出现表格记录。
                            </div>
                          ) : null}
                          {datasetDetail?.parse_status === 'completed' && (datasetDetail?.row_count || 0) === 0 ? (
                            <div className='text-xs text-slate-500'>
                              当前文件已完成解析，但还没有生成可用记录，请检查表头识别与结构定义是否匹配。
                            </div>
                          ) : null}
                        </div>
                      )}
                    </div>
                    <div className='border-t'>
                      <Pagination
                        currentPage={safeCurrentPage}
                        totalPages={totalPages}
                        pageSize={pageSize}
                        totalItems={totalRows}
                        startIndex={startIndex}
                        endIndex={endIndex}
                        onPageChange={(page) => setCurrentPage(page)}
                        onPageSizeChange={(nextPageSize) => {
                          setPageSize(nextPageSize)
                          setCurrentPage(1)
                        }}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </main>

      <Dialog open={!!editorState} onOpenChange={(open) => !open && setEditorState(null)}>
        <DialogContent className='max-w-3xl'>
          <DialogHeader>
            <DialogTitle>{editorState?.mode === 'create' ? '新增表格行' : '编辑表格行'}</DialogTitle>
            <DialogDescription>支持直接编辑单元格内容，文本字段可录入多行。</DialogDescription>
          </DialogHeader>
          <ScrollArea className='max-h-[60vh] pr-4'>
            <div className='space-y-3'>
              <div className='space-y-1.5'>
                <Label>工作表名称</Label>
                <Input
                  value={editorState?.sheetName ?? ''}
                  onChange={(e) =>
                    setEditorState((prev) =>
                      prev
                        ? {
                            ...prev,
                            sheetName: e.target.value,
                          }
                        : prev
                    )
                  }
                  disabled={editorState?.mode === 'edit'}
                />
              </div>
              {(editorState?.columns || []).map((column) => {
                const value = editorState?.values?.[column] ?? ''
                const columnType = schemaColumnMap[column]?.type
                const useTextarea = shouldUseTextarea(columnType)
                return (
                  <div key={column} className='space-y-1.5'>
                    <Label>{column}</Label>
                    {columnType === 'bool' ? (
                      <Select
                        value={getBooleanSelectValue(value)}
                        onValueChange={(nextValue) =>
                          setEditorState((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  values: {
                                    ...prev.values,
                                    [column]: nextValue === '__empty__' ? '' : (nextValue === 'true' ? '是' : '否'),
                                  },
                                }
                              : prev
                          )
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder='请选择' />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value='__empty__'>空</SelectItem>
                          <SelectItem value='true'>是</SelectItem>
                          <SelectItem value='false'>否</SelectItem>
                        </SelectContent>
                      </Select>
                    ) : useTextarea ? (
                      <Textarea
                        value={value}
                        onChange={(e) =>
                          setEditorState((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  values: { ...prev.values, [column]: e.target.value },
                                }
                              : prev
                          )
                        }
                        rows={getTextareaRows(value)}
                        className='resize-y'
                      />
                    ) : (
                      <Input
                        type={getInputTypeByColumnType(columnType)}
                        value={value}
                        onChange={(e) =>
                          setEditorState((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  values: { ...prev.values, [column]: e.target.value },
                                }
                              : prev
                          )
                        }
                      />
                    )}
                  </div>
                )
              })}
              {editorState?.mode === 'create' && !(editorState.columns || []).length ? (
                <div className='rounded-lg border border-dashed p-4 text-sm text-slate-500'>
                  当前数据集还没有可复用的表头，后端会按你提交的字段创建新记录。这里先从已有数据集生成字段。
                </div>
              ) : null}
            </div>
          </ScrollArea>
          <DialogFooter>
            <div className='mr-auto text-xs text-amber-600'>
              保存后会标记为待重解析，重新解析后检索结果才会更新。
            </div>
            <Button variant='outline' onClick={() => setEditorState(null)}>
              取消
            </Button>
            <Button onClick={handleSaveRow} disabled={isSaving}>
              {isSaving ? <Loader2 className='mr-2 h-4 w-4 animate-spin text-blue-500' /> : null}
              保存并标记待重解析
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!rowDetailState} onOpenChange={(open) => !open && setRowDetailState(null)}>
        <DialogContent className='max-w-4xl'>
          <DialogHeader>
            <DialogTitle>记录详情</DialogTitle>
            <DialogDescription>
              查看当前 `kb_table_rows` 记录的完整字段值与来源信息。
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className='max-h-[65vh] pr-4'>
            <div className='space-y-3'>
              <div className='grid grid-cols-3 gap-3 rounded-lg border border-slate-200 bg-gradient-to-r from-blue-50/30 to-cyan-50/30 p-4 text-sm'>
                <div>
                  <div className='text-xs text-slate-500'>工作表</div>
                  <div className='mt-0.5 font-medium text-slate-800'>{rowDetailState?.row.sheet_name || '-'}</div>
                </div>
                <div>
                  <div className='text-xs text-slate-500'>行号</div>
                  <div className='mt-0.5 font-medium text-slate-800'>第 {rowDetailState?.row.row_index || '-'} 行</div>
                </div>
                <div>
                  <div className='text-xs text-slate-500'>来源</div>
                  <div className='mt-0.5 font-medium text-slate-800'>
                    {rowDetailState?.row.source_type === 'manual' ? '手工维护' : 'Excel导入'}
                  </div>
                </div>
              </div>

              {(rowDetailState?.columns || []).map((column) => (
                <div key={column} className='space-y-1.5 rounded-lg border border-slate-200 bg-white p-3'>
                  <Label>{column}</Label>
                  <div className='rounded-md bg-slate-50 border border-slate-200 px-3 py-2 text-sm whitespace-pre-wrap break-all'>
                    {formatCellValue(rowDetailState?.row.row_data?.[column], schemaColumnMap[column]?.type) || '-'}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button variant='outline' onClick={() => setRowDetailState(null)}>
              关闭
            </Button>
            {rowDetailState ? (
              <Button
                onClick={() => {
                  const targetRow = rowDetailState.row
                  setRowDetailState(null)
                  openEditDialog(targetRow)
                }}
              >
                <Pencil className='mr-2 h-4 w-4' />
                编辑这条记录
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
