import { memo, useCallback, useMemo } from 'react'
import { CircleHelp, Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import type {
  KnowledgeBase,
  TableColumnRole,
  TableRetrievalSettings,
  TableSchemaColumn,
  TableSchemaStatus,
} from '@/lib/api/knowledge-base'
import {
  DEFAULT_TABLE_RETRIEVAL_CONFIG,
  DEFAULT_TABLE_SCHEMA_COLUMN,
} from '@/features/knowledge-base/detail/components/shared-config/constants'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'

interface TableStructureSectionProps {
  config: ConfigState
  onConfigChange: (config: ConfigState) => void
  schemaStatus: TableSchemaStatus
  lockedColumnCount?: number
}

const ROLE_OPTIONS: Array<{ value: TableColumnRole; label: string }> = [
  { value: 'entity', label: '基础字段' },
  { value: 'content', label: '详情内容' },
  { value: 'identifier', label: '唯一标识' },
]

function normalizeTableRetrievalConfig(config: ConfigState): TableRetrievalSettings {
  const current = ((config.retrieval_config || {}) as KnowledgeBase['retrieval_config'])?.table || {}
  const normalizedColumns = (current.schema?.columns || []).map((column) => {
    const normalizedRole = column.role === 'dimension' ? 'entity' : column.role
    return {
      ...column,
      role: normalizedRole,
    }
  })

  return {
    ...DEFAULT_TABLE_RETRIEVAL_CONFIG,
    ...current,
    schema: {
      columns: normalizedColumns,
    },
  }
}

function deriveColumnCapabilities(column: TableSchemaColumn): Partial<TableSchemaColumn> {
  if (column.role === 'identifier') {
    return {
      filterable: true,
      aggregatable: false,
      searchable: true,
    }
  }
  if (column.role === 'entity') {
    return {
      filterable: true,
      aggregatable: true,
      searchable: true,
    }
  }
  return {
    filterable: false,
    aggregatable: false,
    searchable: true,
  }
}

function HelpTip({ content }: { content: string }) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type='button'
            className='inline-flex items-center text-muted-foreground transition-colors hover:text-foreground'
          >
            <CircleHelp className='h-3.5 w-3.5' />
          </button>
        </TooltipTrigger>
        <TooltipContent className='max-w-xs text-xs leading-5'>{content}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

interface TableStructureRowProps {
  column: TableSchemaColumn
  index: number
  isLockedColumn: boolean
  onUpdateName: (index: number, nextName: string) => void
  onUpdateTextList: (index: number, field: 'aliases' | 'enum_values', rawValue: string) => void
  onUpdateColumn: (index: number, patch: Partial<TableSchemaColumn>, syncRole?: boolean) => void
  onRemoveColumn: (index: number) => void
}

const TableStructureRow = memo(function TableStructureRow({
  column,
  index,
  isLockedColumn,
  onUpdateName,
  onUpdateTextList,
  onUpdateColumn,
  onRemoveColumn,
}: TableStructureRowProps) {
  return (
    <tr className='border-b last:border-b-0'>
      <td className='px-3 py-2 align-top'>
        <div className='space-y-2'>
          <Input
            value={column.name}
            onChange={(e) => onUpdateName(index, e.target.value)}
            placeholder='例如：事项名称'
            disabled={isLockedColumn}
          />
          <Input
            value={Array.isArray(column.aliases) ? column.aliases.join('，') : ''}
            onChange={(e) => onUpdateTextList(index, 'aliases', e.target.value)}
            placeholder='识别别名，如：区域，大区'
            disabled={isLockedColumn}
          />
          <Input
            value={Array.isArray(column.enum_values) ? column.enum_values.map((item) => typeof item === 'string' ? item : String(item?.value || item?.label || item?.name || '')).filter(Boolean).join('，') : ''}
            onChange={(e) => onUpdateTextList(index, 'enum_values', e.target.value)}
            placeholder='可选值，如：华东，华南，华北'
          />
        </div>
      </td>
      <td className='px-3 py-2 align-top'>
        <Select
          value={column.role}
          onValueChange={(value) =>
            onUpdateColumn(index, { role: value as TableColumnRole }, true)
          }
        >
          <SelectTrigger>
            <SelectValue placeholder='选择用途' />
          </SelectTrigger>
          <SelectContent>
            {ROLE_OPTIONS.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </td>
      <td className='px-3 py-2 text-center'>
        <Switch
          checked={column.filterable}
          onCheckedChange={(checked) => onUpdateColumn(index, { filterable: checked })}
        />
      </td>
      <td className='px-3 py-2 text-center'>
        <Switch
          checked={column.searchable}
          onCheckedChange={(checked) => onUpdateColumn(index, { searchable: checked })}
        />
      </td>
      <td className='px-3 py-2 text-center'>
        <Switch
          checked={column.nullable}
          onCheckedChange={(checked) => onUpdateColumn(index, { nullable: checked })}
          disabled={isLockedColumn ? column.nullable : false}
        />
      </td>
      <td className='px-3 py-2 text-center'>
        <Switch
          checked={column.aggregatable}
          onCheckedChange={(checked) => onUpdateColumn(index, { aggregatable: checked })}
        />
      </td>
      <td className='px-3 py-2 text-right'>
        <Button
          type='button'
          variant='ghost'
          size='sm'
          onClick={() => onRemoveColumn(index)}
          disabled={isLockedColumn}
        >
          <Trash2 className='mr-1 h-4 w-4 text-destructive' />
          删除
        </Button>
      </td>
    </tr>
  )
})

export function TableStructureSection({
  config,
  onConfigChange,
  schemaStatus,
  lockedColumnCount = 0,
}: TableStructureSectionProps) {
  const tableConfig = useMemo(() => normalizeTableRetrievalConfig(config), [config])
  const columns = useMemo(() => tableConfig.schema?.columns || [], [tableConfig.schema?.columns])
  const isConfirmed = schemaStatus === 'confirmed'
  const isStructureLocked = isConfirmed && lockedColumnCount > 0

  const updateTableConfig = useCallback((patch: Partial<TableRetrievalSettings>) => {
    onConfigChange({
      ...config,
      retrieval_config: {
        ...(config.retrieval_config || {}),
        table: {
          ...tableConfig,
          ...patch,
        },
      } as KnowledgeBase['retrieval_config'],
    })
  }, [config, onConfigChange, tableConfig])

  const updateColumns = useCallback((nextColumns: TableSchemaColumn[]) => {
    updateTableConfig({
      schema: { columns: nextColumns },
    })
  }, [updateTableConfig])

  const updateColumn = useCallback((index: number, patch: Partial<TableSchemaColumn>, syncRole = false) => {
    const nextColumns = columns.map((column, currentIndex) => {
      if (currentIndex !== index) {
        return column
      }
      const nextColumn = { ...column, ...patch }
      if (syncRole) {
        return {
          ...nextColumn,
          ...deriveColumnCapabilities(nextColumn),
        }
      }
      return nextColumn
    })
    updateColumns(nextColumns)
  }, [columns, updateColumns])

  const addColumn = useCallback(() => {
    updateColumns([...columns, { ...DEFAULT_TABLE_SCHEMA_COLUMN }])
  }, [columns, updateColumns])

  const removeColumn = useCallback((index: number) => {
    const isLockedColumn = isStructureLocked && index < lockedColumnCount
    if (isLockedColumn) {
      return
    }
    updateColumns(columns.filter((_, currentIndex) => currentIndex !== index))
  }, [columns, isStructureLocked, lockedColumnCount, updateColumns])

  const updateColumnName = useCallback((index: number, nextName: string) => {
    const isLockedColumn = isStructureLocked && index < lockedColumnCount
    if (isLockedColumn) {
      return
    }
    const nextColumns = columns.map((column, currentIndex) => {
      if (currentIndex !== index) {
        return column
      }
      return {
        ...column,
        name: nextName,
      }
    })
    updateColumns(nextColumns)
  }, [columns, isStructureLocked, lockedColumnCount, updateColumns])

  const updateColumnTextList = useCallback((
    index: number,
    field: 'aliases' | 'enum_values',
    rawValue: string
  ) => {
    const nextValues = rawValue
      .split(/[，,\n]/)
      .map((item) => item.trim())
      .filter(Boolean)

    updateColumn(index, { [field]: nextValues } as Partial<TableSchemaColumn>)
  }, [updateColumn])

  return (
    <section>
      <div className='rounded-xl border bg-card p-4 shadow-sm'>
        <div className='space-y-3'>
          <div className='flex items-center justify-between gap-3'>
            <div>
              <h3 className='text-sm font-semibold text-foreground'>字段结构</h3>
              <p className='mt-1 text-xs text-muted-foreground'>
                定稿前可调整字段名称、必填规则与字段数量；定稿后允许新增可空字段，也允许放宽既有字段的非空约束。
              </p>
            </div>
            <div className='flex items-center gap-2'>
              <Button type='button' size='sm' variant='outline' onClick={addColumn}>
                <Plus className='mr-2 h-4 w-4' />
                新增字段
              </Button>
            </div>
          </div>

          {columns.length ? (
            <div className='overflow-x-auto rounded-lg border'>
              <table className='min-w-[1180px] w-full text-sm'>
                <thead className='bg-muted/30'>
                  <tr className='border-b text-left'>
                    <th className='w-[260px] px-3 py-2 font-medium'>
                      <div className='inline-flex items-center gap-1'>
                        字段名称与识别提示
                        <HelpTip content='除了标准字段名，还可以补充别名和常见可选值，方便自动识别过滤条件。' />
                      </div>
                    </th>
                    <th className='w-[180px] px-3 py-2 font-medium'>
                      <div className='inline-flex items-center gap-1'>
                        字段用途
                        <HelpTip content='决定这一列更偏向基础检索、详情内容，还是唯一标识。' />
                      </div>
                    </th>
                    <th className='px-3 py-2 text-center font-medium'>
                      <div className='inline-flex items-center gap-1'>
                        可过滤
                        <HelpTip content='用于数据视图顶部筛选，也可作为结构化检索的过滤候选字段。' />
                      </div>
                    </th>
                    <th className='px-3 py-2 text-center font-medium'>
                      <div className='inline-flex items-center gap-1'>
                        可检索
                        <HelpTip content='用于记录搜索与问答检索时的文本匹配范围。' />
                      </div>
                    </th>
                    <th className='px-3 py-2 text-center font-medium'>
                      <div className='inline-flex items-center gap-1'>
                        允许为空
                        <HelpTip content='字段缺失时是否允许导入；关闭后，该字段会作为必填字段参与预检。' />
                      </div>
                    </th>
                    <th className='px-3 py-2 text-center font-medium'>
                      <div className='inline-flex items-center gap-1'>
                        可聚合
                        <HelpTip content='用于统计分析或后续聚合能力的预留开关，日常问答可以保持默认。' />
                      </div>
                    </th>
                    <th className='w-[92px] px-3 py-2 text-right font-medium'>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {columns.map((column, index) => {
                    const isLockedColumn = isStructureLocked && index < lockedColumnCount
                    return (
                      <TableStructureRow
                        key={index}
                        column={column}
                        index={index}
                        isLockedColumn={isLockedColumn}
                        onUpdateName={updateColumnName}
                        onUpdateTextList={updateColumnTextList}
                        onUpdateColumn={updateColumn}
                        onRemoveColumn={removeColumn}
                      />
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className='rounded-xl border border-dashed p-6'>
              <div className='flex flex-col gap-4 md:flex-row md:items-center md:justify-between'>
                <div>
                  <div className='text-sm font-medium text-foreground'>还没有设置字段</div>
                  <p className='mt-1 text-sm text-muted-foreground'>
                    建议先上传一份标准 Excel 生成结构草稿；如果暂时没有标准文件，也可以先手动定义结构。
                  </p>
                </div>
                <div className='flex items-center gap-2'>
                  <Button type='button' onClick={addColumn}>
                    <Plus className='mr-2 h-4 w-4' />
                    手动新增字段
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
