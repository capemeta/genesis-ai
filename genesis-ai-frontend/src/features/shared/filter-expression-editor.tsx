import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, CirclePlus, Filter, GitBranchPlus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { QueryAnalysisMetadataField } from '@/lib/api/knowledge-base'

type GroupOperator = 'and' | 'or' | 'not'
type RuleOperator = 'eq' | 'ne' | 'in' | 'not_in' | 'exists' | 'not_exists'
type BuilderField = 'folder' | 'folder_tag' | 'tag' | 'kb_doc' | 'metadata' | 'search_unit_metadata'

interface BuilderGroupNode {
  id: string
  kind: 'group'
  op: GroupOperator
  items: BuilderNode[]
}

interface BuilderRuleNode {
  id: string
  kind: 'rule'
  field: BuilderField
  path: string[]
  op: RuleOperator
  values: string[]
}

type BuilderNode = BuilderGroupNode | BuilderRuleNode

interface NamedOption {
  id: string
  name: string
}

interface LabeledOption {
  id: string
  label: string
}

interface MetadataPathOption {
  label: string
  value: string
  path: string[]
  options: string[]
  targetLabel: string
  description: string
}

interface ValueOption {
  value: string
  label: string
  description?: string
}

interface FilterExpressionEditorProps {
  value: string
  onChange: (value: string) => void
  metadataFields?: QueryAnalysisMetadataField[]
  folders?: LabeledOption[]
  tags?: NamedOption[]
  folderTags?: NamedOption[]
  kbDocs?: NamedOption[]
  className?: string
  placeholder?: string
  /** inline：嵌入页面；dialog：仅展示摘要，在弹窗内编辑（适合侧栏等窄区域） */
  variant?: 'inline' | 'dialog'
  /** variant=dialog 时弹窗标题 */
  dialogTitle?: string
}

function getFilterExpressionSummary(value: string): { status: 'empty' | 'ok' | 'error'; message: string } {
  const text = value.trim()
  if (!text) {
    return { status: 'empty', message: '未配置硬过滤（留空表示不额外限制）' }
  }
  const parsed = parseExpressionText(value)
  if (parsed.error) {
    return { status: 'error', message: `JSON 无效：${parsed.error}` }
  }
  const compact = text.replace(/\s+/g, ' ')
  const preview = compact.length > 96 ? `${compact.slice(0, 96)}…` : compact
  return { status: 'ok', message: preview }
}

function parseExpressionText(value: string): { json: Record<string, any> | null; error: string | null } {
  const text = value.trim()
  if (!text) {
    return { json: null, error: null }
  }
  try {
    const parsed = JSON.parse(text)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { json: null, error: '表达式必须是 JSON 对象' }
    }
    return { json: parsed as Record<string, any>, error: null }
  }
  catch (error) {
    return { json: null, error: error instanceof Error ? error.message : 'JSON 解析失败' }
  }
}

/**
 * 把 JSON 表达式和构造器节点互转，方便在“可视化编辑”和“JSON 直编”之间同步。
 */
function createNodeFactory() {
  let index = 0
  return () => `expr-node-${index++}`
}

function normalizeNodeValueList(node: Record<string, any>): string[] {
  const rawValues = Array.isArray(node.values)
    ? node.values
    : node.value !== undefined && node.value !== null
      ? [node.value]
      : []
  return rawValues
    .map((item) => String(item ?? '').trim())
    .filter(Boolean)
}

function parseExpressionNode(node: Record<string, any>, nextId: () => string): BuilderNode {
  const op = String(node.op || '').trim().toLowerCase()
  if (op === 'and' || op === 'or' || op === 'not') {
    const items = Array.isArray(node.items) ? node.items : []
    return {
      id: nextId(),
      kind: 'group',
      op,
      items: items
        .filter((item) => item && typeof item === 'object' && !Array.isArray(item))
        .map((item) => parseExpressionNode(item as Record<string, any>, nextId)),
    }
  }

  const field = String(node.field || 'metadata').trim().toLowerCase()
  const normalizedField: BuilderField =
    field === 'folder' || field === 'folder_id'
      ? 'folder'
      : field === 'folder_tag' || field === 'folder_tag_id'
        ? 'folder_tag'
        : field === 'tag' || field === 'tag_id' || field === 'doc_tag'
          ? 'tag'
          : field === 'kb_doc' || field === 'kb_doc_id'
            ? 'kb_doc'
            : field === 'search_unit_metadata'
              ? 'search_unit_metadata'
              : 'metadata'
  const path = Array.isArray(node.path)
    ? node.path.map((item) => String(item || '').trim()).filter(Boolean)
    : []
  const normalizedOp = ['eq', 'ne', 'in', 'not_in', 'exists', 'not_exists'].includes(op) ? op as RuleOperator : 'eq'
  return {
    id: nextId(),
    kind: 'rule',
    field: normalizedField,
    path,
    op: normalizedOp,
    values: normalizeNodeValueList(node),
  }
}

function parseExpressionTree(value: Record<string, any> | null): BuilderGroupNode {
  const nextId = createNodeFactory()
  if (!value) {
    return { id: nextId(), kind: 'group', op: 'and', items: [] }
  }
  const parsed = parseExpressionNode(value, nextId)
  if (parsed.kind === 'group') {
    return parsed
  }
  return {
    id: nextId(),
    kind: 'group',
    op: 'and',
    items: [parsed],
  }
}

function serializeRuleNode(node: BuilderRuleNode): Record<string, any> {
  const payload: Record<string, any> = {
    field: node.field,
    op: node.op,
  }
  if ((node.field === 'metadata' || node.field === 'search_unit_metadata') && node.path.length > 0) {
    payload.path = node.path
  }
  if (!['exists', 'not_exists'].includes(node.op) && node.values.length > 0) {
    payload.values = node.values
  }
  return payload
}

function serializeExpressionNode(node: BuilderNode): Record<string, any> {
  if (node.kind === 'rule') {
    return serializeRuleNode(node)
  }
  return {
    op: node.op,
    items: node.items.map(serializeExpressionNode),
  }
}

function stringifyExpressionTree(root: BuilderGroupNode): string {
  if (root.items.length === 0) {
    return ''
  }
  const payload = root.items.length === 1
    ? serializeExpressionNode(root.items[0])
    : serializeExpressionNode(root)
  return JSON.stringify(payload, null, 2)
}

function updateNodeById(node: BuilderNode, targetId: string, updater: (node: BuilderNode) => BuilderNode): BuilderNode {
  if (node.id === targetId) {
    return updater(node)
  }
  if (node.kind === 'group') {
    return {
      ...node,
      items: node.items.map((item) => updateNodeById(item, targetId, updater)),
    }
  }
  return node
}

function removeNodeById(node: BuilderGroupNode, targetId: string): BuilderGroupNode {
  return {
    ...node,
    items: node.items
      .filter((item) => item.id !== targetId)
      .map((item) => item.kind === 'group' ? removeNodeById(item, targetId) : item),
  }
}

function createDefaultRule(field: BuilderField = 'metadata'): BuilderRuleNode {
  return {
    id: `draft-${Math.random().toString(36).slice(2, 10)}`,
    kind: 'rule',
    field,
    path: field === 'metadata' ? ['region'] : [],
    op: field === 'metadata' || field === 'search_unit_metadata' ? 'eq' : 'in',
    values: [],
  }
}

function createDefaultGroup(): BuilderGroupNode {
  return {
    id: `draft-${Math.random().toString(36).slice(2, 10)}`,
    kind: 'group',
    op: 'and',
    items: [],
  }
}

function parseValueText(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function formatValueText(values: string[]): string {
  return values.join(', ')
}

function dedupeValues(values: string[]): string[] {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)))
}

function getFieldLabel(field: BuilderField): string {
  if (field === 'folder') return '文件夹'
  if (field === 'folder_tag') return '文件夹标签'
  if (field === 'tag') return '文档标签'
  if (field === 'kb_doc') return 'kb 文档'
  if (field === 'metadata') return '文档元数据'
  return '分块元数据'
}

function getOperatorOptions(field: BuilderField): Array<{ value: RuleOperator; label: string }> {
  if (field === 'metadata' || field === 'search_unit_metadata') {
    return [
      { value: 'eq', label: '等于' },
      { value: 'ne', label: '不等于' },
      { value: 'in', label: '包含任一值' },
      { value: 'not_in', label: '排除这些值' },
      { value: 'exists', label: '字段存在' },
      { value: 'not_exists', label: '字段不存在' },
    ]
  }
  return [
    { value: 'eq', label: '等于' },
    { value: 'in', label: '包含任一值' },
    { value: 'not_in', label: '排除这些值' },
  ]
}

function normalizeMetadataPath(field?: QueryAnalysisMetadataField | null): string[] {
  if (Array.isArray(field?.metadata_path) && field.metadata_path.length > 0) {
    return field.metadata_path.map((item) => String(item || '').trim()).filter(Boolean)
  }
  const key = String(field?.key || '').trim()
  return key ? [key] : []
}

function normalizeMetadataOptionValues(field?: QueryAnalysisMetadataField | null): string[] {
  const rawOptions = Array.isArray(field?.options) && field.options.length > 0
    ? field.options
    : Array.isArray(field?.enum_values)
      ? field.enum_values
      : []
  return rawOptions
    .map((item) => {
      if (typeof item === 'string') {
        return item.trim()
      }
      if (!item || typeof item !== 'object') {
        return ''
      }
      return String(item.value || item.name || item.label || '').trim()
    })
    .filter(Boolean)
}

function buildMetadataPathOptions(fields: QueryAnalysisMetadataField[], target: BuilderField): MetadataPathOption[] {
  return fields
    .filter((field) => {
      const normalizedTarget = String(field.target || 'document_metadata').trim()
      return target === 'search_unit_metadata'
        ? normalizedTarget === 'search_unit_metadata'
        : normalizedTarget !== 'search_unit_metadata'
    })
    .map((field) => {
      const path = normalizeMetadataPath(field)
      const baseLabel = String(field.name || field.key || path.join('.') || '未命名字段').trim()
      const pathText = path.join('.')
      const targetLabel = target === 'search_unit_metadata' ? '分块元数据' : '文档元数据'
      const optionCount = normalizeMetadataOptionValues(field).length
      return {
        label: `${baseLabel} · ${pathText}`,
        value: path.join('.'),
        path,
        options: normalizeMetadataOptionValues(field),
        targetLabel,
        description: `${targetLabel}${optionCount > 0 ? ` · ${optionCount} 个候选值` : ''}`,
      }
    })
    .filter((item) => item.value)
}

function getSelectableValueOptions(
  node: BuilderRuleNode,
  metadataFields: QueryAnalysisMetadataField[],
  folders: LabeledOption[],
  tags: NamedOption[],
  folderTags: NamedOption[],
  kbDocs: NamedOption[],
): ValueOption[] {
  if (node.field === 'folder') {
    return folders.map((item) => ({ value: item.id, label: item.label, description: item.id }))
  }
  if (node.field === 'tag') {
    return tags.map((item) => ({ value: item.id, label: item.name, description: item.id }))
  }
  if (node.field === 'folder_tag') {
    return folderTags.map((item) => ({ value: item.id, label: item.name, description: item.id }))
  }
  if (node.field === 'kb_doc') {
    return kbDocs.map((item) => ({ value: item.id, label: item.name, description: item.id }))
  }
  const pathOptions = buildMetadataPathOptions(metadataFields, node.field)
  const matched = pathOptions.find((item) => item.value === node.path.join('.'))
  return (matched?.options || []).map((item) => ({ value: item, label: item }))
}

function buildValueAliasMap(options: ValueOption[]): Map<string, string> {
  const map = new Map<string, string>()
  options.forEach((option) => {
    map.set(option.value, option.value)
    map.set(option.label, option.value)
    if (option.description) {
      map.set(option.description, option.value)
    }
  })
  return map
}

function getValueDisplayMap(options: ValueOption[]): Map<string, string> {
  const map = new Map<string, string>()
  options.forEach((option) => {
    map.set(option.value, option.label)
  })
  return map
}

function MultiValuePickerDialog({
  open,
  onOpenChange,
  title,
  options,
  selectedValues,
  onApply,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  options: ValueOption[]
  selectedValues: string[]
  onApply: (values: string[]) => void
}) {
  const [keyword, setKeyword] = useState('')
  const [draftValues, setDraftValues] = useState<string[]>(selectedValues)

  useEffect(() => {
    if (open) {
      setDraftValues(selectedValues)
      setKeyword('')
    }
  }, [open, selectedValues])

  const filteredOptions = useMemo(() => {
    const needle = keyword.trim().toLowerCase()
    if (!needle) {
      return options
    }
    return options.filter((option) =>
      [option.label, option.value, option.description || ''].some((text) => text.toLowerCase().includes(needle))
    )
  }, [keyword, options])

  const toggleValue = (value: string, checked: boolean | 'indeterminate') => {
    setDraftValues((prev) => {
      const active = checked === true
      if (active) {
        return dedupeValues([...prev, value])
      }
      return prev.filter((item) => item !== value)
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton className='max-w-2xl'>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className='text-xs'>多选结果会写入表达式值，标签 / 文件夹 / 文档类条件实际保存为 ID。</DialogDescription>
        </DialogHeader>
        <div className='space-y-3'>
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder='搜索名称、路径或 ID'
            className='h-9 text-sm'
          />
          <div className='max-h-[360px] space-y-2 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50/50 p-2'>
            {filteredOptions.length === 0 ? (
              <div className='px-2 py-6 text-center text-xs text-slate-500'>没有匹配项</div>
            ) : (
              filteredOptions.map((option) => {
                const checked = draftValues.includes(option.value)
                return (
                  <label
                    key={option.value}
                    className={cn(
                      'flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2 transition-colors',
                      checked ? 'border-blue-300 bg-blue-50/70' : 'border-transparent bg-white hover:border-slate-200'
                    )}
                  >
                    <Checkbox checked={checked} onCheckedChange={(next) => toggleValue(option.value, next)} />
                    <div className='min-w-0 space-y-1'>
                      <div className='break-all text-sm text-slate-800'>{option.label}</div>
                      {option.description ? (
                        <div className='break-all text-[11px] text-slate-500'>{option.description}</div>
                      ) : null}
                      {option.description !== option.value ? (
                        <div className='break-all font-mono text-[10px] text-slate-400'>{option.value}</div>
                      ) : null}
                    </div>
                  </label>
                )
              })
            )}
          </div>
        </div>
        <DialogFooter className='gap-2'>
          <Button type='button' variant='outline' size='sm' onClick={() => onOpenChange(false)}>取消</Button>
          <Button type='button' size='sm' onClick={() => { onApply(draftValues); onOpenChange(false) }}>应用所选值</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function RuleEditor({
  node,
  metadataFields,
  folders,
  tags,
  folderTags,
  kbDocs,
  onChange,
  onRemove,
}: {
  node: BuilderRuleNode
  metadataFields: QueryAnalysisMetadataField[]
  folders: LabeledOption[]
  tags: NamedOption[]
  folderTags: NamedOption[]
  kbDocs: NamedOption[]
  onChange: (next: BuilderRuleNode) => void
  onRemove: () => void
}) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const metadataPathOptions = useMemo(
    () => buildMetadataPathOptions(metadataFields, node.field),
    [metadataFields, node.field]
  )
  const selectableValueOptions = useMemo(
    () => getSelectableValueOptions(node, metadataFields, folders, tags, folderTags, kbDocs),
    [folderTags, folders, kbDocs, metadataFields, node, tags]
  )
  const quickValueOptions = useMemo(
    () => selectableValueOptions.slice(0, 10),
    [selectableValueOptions]
  )
  const valueAliasMap = useMemo(() => buildValueAliasMap(selectableValueOptions), [selectableValueOptions])
  const valueDisplayMap = useMemo(() => getValueDisplayMap(selectableValueOptions), [selectableValueOptions])
  const operatorOptions = useMemo(() => getOperatorOptions(node.field), [node.field])
  const selectedMetadataPathOption = useMemo(
    () => metadataPathOptions.find((item) => item.value === node.path.join('.')) || null,
    [metadataPathOptions, node.path]
  )
  const selectedValueSummary = useMemo(
    () => node.values.map((item) => valueDisplayMap.get(item) || item),
    [node.values, valueDisplayMap]
  )

  useEffect(() => {
    if (!['folder', 'folder_tag', 'tag', 'kb_doc'].includes(node.field)) {
      return
    }
    const normalized = dedupeValues(node.values.map((item) => valueAliasMap.get(item) || item))
    if (JSON.stringify(normalized) !== JSON.stringify(node.values)) {
      onChange({ ...node, values: normalized })
    }
  }, [node, onChange, valueAliasMap])

  return (
    <div className='space-y-3 rounded-lg border border-slate-200/80 bg-white p-3'>
      <div className='grid gap-3 md:grid-cols-[160px_140px_1fr_auto]'>
        <div className='space-y-1.5'>
          <Label className='text-[11px] text-muted-foreground'>过滤字段</Label>
          <Select
            value={node.field}
            onValueChange={(value: BuilderField) => {
              const nextPath = value === 'metadata' || value === 'search_unit_metadata'
                ? buildMetadataPathOptions(metadataFields, value)[0]?.path || node.path
                : []
              onChange({
                ...node,
                field: value,
                path: nextPath,
                op: getOperatorOptions(value)[0]?.value || 'eq',
                values: [],
              })
            }}
          >
            <SelectTrigger className='h-8 text-xs'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='folder'>文件夹</SelectItem>
              <SelectItem value='folder_tag'>文件夹标签</SelectItem>
              <SelectItem value='tag'>文档标签</SelectItem>
              <SelectItem value='kb_doc'>kb 文档</SelectItem>
              <SelectItem value='metadata'>文档元数据</SelectItem>
              <SelectItem value='search_unit_metadata'>分块元数据</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className='space-y-1.5'>
          <Label className='text-[11px] text-muted-foreground'>操作符</Label>
          <Select
            value={node.op}
            onValueChange={(value: RuleOperator) => {
              onChange({
                ...node,
                op: value,
                values: value === 'exists' || value === 'not_exists' ? [] : node.values,
              })
            }}
          >
            <SelectTrigger className='h-8 text-xs'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {operatorOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className='space-y-1.5'>
          <Label className='text-[11px] text-muted-foreground'>
            {node.field === 'metadata' || node.field === 'search_unit_metadata' ? '字段路径 / 值' : '值'}
          </Label>
          <div className='space-y-2'>
            {(node.field === 'metadata' || node.field === 'search_unit_metadata') ? (
              <>
                <Select
                  value={node.path.join('.')}
                  onValueChange={(value) => {
                    const matched = metadataPathOptions.find((item) => item.value === value)
                    onChange({
                      ...node,
                        path: matched?.path || parseValueText(value.split('.').join(',')),
                      values: [],
                    })
                  }}
                >
                  <SelectTrigger className='h-8 text-xs'>
                    <SelectValue placeholder='选择已配置字段' />
                  </SelectTrigger>
                  <SelectContent>
                    {metadataPathOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  value={node.path.join('.')}
                  onChange={(event) => onChange({ ...node, path: parseValueText(event.target.value.split('.').join(',')) })}
                  placeholder='支持手动输入路径，如 region 或 qa_fields.category'
                  className='h-8 text-xs'
                />
                {selectedMetadataPathOption ? (
                  <div className='rounded-md border border-slate-200 bg-slate-50/70 px-2 py-2 text-[11px] text-slate-600'>
                    <div>{selectedMetadataPathOption.targetLabel}</div>
                    <div className='font-mono text-[10px] text-slate-500'>{selectedMetadataPathOption.value}</div>
                    <div className='text-[10px] text-slate-500'>{selectedMetadataPathOption.description}</div>
                  </div>
                ) : null}
              </>
            ) : null}
            {node.op !== 'exists' && node.op !== 'not_exists' ? (
              <>
                <Input
                  value={formatValueText(node.values)}
                  onChange={(event) => onChange({ ...node, values: dedupeValues(parseValueText(event.target.value)) })}
                  placeholder={node.field === 'metadata' || node.field === 'search_unit_metadata' ? '多个值可用逗号分隔' : '可手动输入 ID，多个值用逗号分隔'}
                  className='h-8 text-xs'
                />
                {selectableValueOptions.length > 0 ? (
                  <Button
                    type='button'
                    variant='outline'
                    size='sm'
                    className='h-8 w-full justify-center text-xs'
                    onClick={() => setPickerOpen(true)}
                  >
                    选择多个值
                  </Button>
                ) : null}
              </>
            ) : (
              <div className='rounded-md border border-dashed border-slate-200 bg-slate-50 px-2 py-2 text-[11px] text-slate-500'>
                当前操作符不需要填写值。
              </div>
            )}
            {quickValueOptions.length > 0 && node.op !== 'exists' && node.op !== 'not_exists' ? (
              <div className='flex flex-wrap gap-1.5'>
                {quickValueOptions.map((option) => {
                  const active = node.values.includes(option.value)
                  return (
                    <button
                      key={`${node.id}-${option.value}`}
                      type='button'
                      className={cn(
                        'rounded-md border px-2 py-1 text-[10px] transition-colors',
                        active
                          ? 'border-blue-300 bg-blue-50 text-blue-700'
                          : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300 hover:bg-slate-100'
                      )}
                      onClick={() => {
                        onChange({
                          ...node,
                          values: active
                            ? node.values.filter((item) => item !== option.value)
                            : dedupeValues([...node.values, option.value]),
                        })
                      }}
                    >
                      {option.label}
                    </button>
                  )
                })}
              </div>
            ) : null}
            {node.values.length > 0 ? (
              <div className='rounded-md border border-slate-200 bg-slate-50/70 px-2 py-2 text-[11px] text-slate-600'>
                已选值：{selectedValueSummary.join('，')}
              </div>
            ) : null}
          </div>
        </div>

        <div className='flex items-start justify-end pt-6'>
          <Button type='button' variant='ghost' size='icon-sm' onClick={onRemove} title='删除条件'>
            <Trash2 className='h-4 w-4 text-slate-500' />
          </Button>
        </div>
      </div>

      <div className='text-[11px] text-slate-500'>
        当前条件：{getFieldLabel(node.field)} {operatorOptions.find((item) => item.value === node.op)?.label || node.op}
      </div>
      <MultiValuePickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        title={`选择${getFieldLabel(node.field)}值`}
        options={selectableValueOptions}
        selectedValues={node.values}
        onApply={(values) => onChange({ ...node, values: dedupeValues(values) })}
      />
    </div>
  )
}

function GroupEditor({
  node,
  root,
  depth,
  metadataFields,
  folders,
  tags,
  folderTags,
  kbDocs,
  onRootChange,
}: {
  node: BuilderGroupNode
  root: BuilderGroupNode
  depth: number
  metadataFields: QueryAnalysisMetadataField[]
  folders: LabeledOption[]
  tags: NamedOption[]
  folderTags: NamedOption[]
  kbDocs: NamedOption[]
  onRootChange: (next: BuilderGroupNode) => void
}) {
  const handleNodeChange = (targetId: string, next: BuilderNode) => {
    onRootChange(updateNodeById(root, targetId, () => next) as BuilderGroupNode)
  }

  const handleAddRule = () => {
    const nextRule = createDefaultRule()
    onRootChange(
      updateNodeById(root, node.id, (current) => ({
        ...(current as BuilderGroupNode),
        items: [...(current as BuilderGroupNode).items, nextRule],
      })) as BuilderGroupNode
    )
  }

  const handleAddGroup = () => {
    const nextGroup = createDefaultGroup()
    onRootChange(
      updateNodeById(root, node.id, (current) => ({
        ...(current as BuilderGroupNode),
        items: [...(current as BuilderGroupNode).items, nextGroup],
      })) as BuilderGroupNode
    )
  }

  return (
    <div className={cn('space-y-3 rounded-lg border bg-slate-50/60 p-3', depth === 0 ? 'border-slate-200/80' : 'border-slate-200')}>
      <div className='flex flex-wrap items-center justify-between gap-2'>
        <div className='flex items-center gap-2'>
          <span className='rounded bg-slate-900 px-2 py-0.5 text-[10px] font-medium text-white'>
            {depth === 0 ? '根分组' : `子分组 ${depth}`}
          </span>
          <Select
            value={node.op}
            onValueChange={(value: GroupOperator) => handleNodeChange(node.id, { ...node, op: value })}
          >
            <SelectTrigger className='h-8 w-[120px] text-xs'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='and'>AND</SelectItem>
              <SelectItem value='or'>OR</SelectItem>
              <SelectItem value='not'>NOT</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className='flex flex-wrap gap-2'>
          <Button type='button' variant='outline' size='sm' className='h-8 text-xs' onClick={handleAddRule}>
            <CirclePlus className='h-3.5 w-3.5' />
            添加条件
          </Button>
          <Button type='button' variant='outline' size='sm' className='h-8 text-xs' onClick={handleAddGroup}>
            <GitBranchPlus className='h-3.5 w-3.5' />
            添加子分组
          </Button>
          {depth > 0 ? (
            <Button
              type='button'
              variant='ghost'
              size='sm'
              className='h-8 text-xs text-slate-500'
              onClick={() => onRootChange(removeNodeById(root, node.id))}
            >
              删除分组
            </Button>
          ) : null}
        </div>
      </div>

      <div className='space-y-3'>
        {node.items.length === 0 ? (
          <div className='rounded-md border border-dashed border-slate-200 bg-white px-3 py-4 text-xs text-slate-500'>
            这个分组还没有条件。可以添加“条件”或“子分组”。
          </div>
        ) : null}
        {node.items.map((item) => (
          <div key={item.id} className={cn(depth > 0 ? 'border-l border-slate-200 pl-3' : '')}>
            {item.kind === 'group' ? (
              <GroupEditor
                node={item}
                root={root}
                depth={depth + 1}
                metadataFields={metadataFields}
                folders={folders}
                tags={tags}
                folderTags={folderTags}
                kbDocs={kbDocs}
                onRootChange={onRootChange}
              />
            ) : (
              <RuleEditor
                node={item}
                metadataFields={metadataFields}
                folders={folders}
                tags={tags}
                folderTags={folderTags}
                kbDocs={kbDocs}
                onChange={(next) => handleNodeChange(item.id, next)}
                onRemove={() => onRootChange(removeNodeById(root, item.id))}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

interface FilterExpressionEditorInnerProps {
  value: string
  onChange: (value: string) => void
  metadataFields: QueryAnalysisMetadataField[]
  folders: LabeledOption[]
  tags: NamedOption[]
  folderTags: NamedOption[]
  kbDocs: NamedOption[]
  className?: string
  placeholder?: string
  /** 弹窗内使用更高最小高度 */
  contentSize?: 'default' | 'dialog'
}

function FilterExpressionEditorInner({
  value,
  onChange,
  metadataFields,
  folders,
  tags,
  folderTags,
  kbDocs,
  className,
  placeholder,
  contentSize = 'default',
}: FilterExpressionEditorInnerProps) {
  const [tab, setTab] = useState<'builder' | 'json'>('builder')
  const parsed = useMemo(() => parseExpressionText(value), [value])
  const root = useMemo(() => parseExpressionTree(parsed.json), [parsed.json])

  const applyRootChange = (next: BuilderGroupNode) => {
    onChange(stringifyExpressionTree(next))
  }

  return (
    <Tabs value={tab} onValueChange={(next) => setTab(next as 'builder' | 'json')} className={className}>
      <TabsList className='grid w-full grid-cols-2'>
        <TabsTrigger value='builder'>构造器</TabsTrigger>
        <TabsTrigger value='json'>JSON</TabsTrigger>
      </TabsList>

      <TabsContent value='builder' className='space-y-3'>
        {parsed.error ? (
          <div className='rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-800'>
            当前 JSON 还不合法，构造器暂时无法同步。你可以先切到 JSON 修正，或者直接点下面按钮用构造器覆盖当前内容。
            <div className='mt-2'>
              <Button type='button' size='sm' variant='outline' className='h-8 text-xs' onClick={() => onChange('')}>
                清空并用构造器重建
              </Button>
            </div>
          </div>
        ) : (
          <GroupEditor
            node={root}
            root={root}
            depth={0}
            metadataFields={metadataFields}
            folders={folders}
            tags={tags}
            folderTags={folderTags}
            kbDocs={kbDocs}
            onRootChange={applyRootChange}
          />
        )}
        <div className='text-[11px] leading-5 text-slate-500'>
          构造器适合搭常见的 AND / OR / NOT 组合；底层仍然会保存成统一过滤表达式 JSON。
        </div>
      </TabsContent>

      <TabsContent value='json' className='space-y-2'>
        <Textarea
          value={value}
          placeholder={placeholder}
          className={cn(
            'resize-y rounded-lg font-mono text-[11px]',
            contentSize === 'dialog' ? 'min-h-[min(360px,50vh)]' : 'min-h-28',
            parsed.error ? 'border-red-300 bg-red-50/60 focus-visible:ring-red-200' : 'border-border/50 bg-white'
          )}
          spellCheck={false}
          onChange={(event) => onChange(event.target.value)}
        />
        <div className={cn('text-[11px] leading-5', parsed.error ? 'text-red-600' : 'text-slate-500')}>
          {parsed.error ? `JSON 校验失败：${parsed.error}` : 'JSON 合法。构造器和 JSON 会双向同步。'}
        </div>
      </TabsContent>
    </Tabs>
  )
}

export function FilterExpressionEditor({
  value,
  onChange,
  metadataFields = [],
  folders = [],
  tags = [],
  folderTags = [],
  kbDocs = [],
  className,
  placeholder,
  variant = 'inline',
  dialogTitle = '高级过滤表达式',
}: FilterExpressionEditorProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [draft, setDraft] = useState(value)

  const summary = useMemo(() => getFilterExpressionSummary(value), [value])

  const openDialog = () => {
    setDraft(value)
    setDialogOpen(true)
  }

  const handleApply = () => {
    onChange(draft)
    setDialogOpen(false)
  }

  const handleDialogOpenChange = (next: boolean) => {
    setDialogOpen(next)
    if (next) {
      setDraft(value)
    }
  }

  if (variant === 'dialog') {
    return (
      <div className={cn('space-y-2', className)}>
        <div className='flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between'>
          <div
            className={cn(
              'min-w-0 flex-1 rounded-md border px-2.5 py-2 text-[11px] leading-snug',
              summary.status === 'error'
                ? 'border-red-200 bg-red-50/50 text-red-800'
                : summary.status === 'ok'
                  ? 'border-emerald-200/80 bg-white text-slate-700'
                  : 'border-dashed border-slate-200 bg-white/80 text-muted-foreground'
            )}
          >
            <div className='flex items-start gap-1.5'>
              {summary.status === 'error' ? (
                <AlertCircle className='mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600' aria-hidden />
              ) : null}
              <span className='break-all font-mono'>{summary.message}</span>
            </div>
          </div>
          <Button type='button' variant='outline' size='sm' className='h-8 shrink-0 gap-1.5 text-xs' onClick={openDialog}>
            <Filter className='h-3.5 w-3.5' />
            编辑表达式
          </Button>
        </div>

        <Dialog open={dialogOpen} onOpenChange={handleDialogOpenChange}>
          <DialogContent
            showCloseButton
            className='flex max-h-[min(92vh,900px)] w-full max-w-[calc(100%-1.5rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl'
          >
            <DialogHeader className='shrink-0 border-b px-5 py-4 text-start'>
              <DialogTitle className='text-base'>{dialogTitle}</DialogTitle>
              <DialogDescription className='text-xs'>
                在「构造器」中可视化组合条件，或在「JSON」中直接编辑；确定后才会应用到检索。
              </DialogDescription>
            </DialogHeader>
            <div className='min-h-0 flex-1 overflow-y-auto px-5 py-4'>
              <FilterExpressionEditorInner
                value={draft}
                onChange={setDraft}
                metadataFields={metadataFields}
                folders={folders}
                tags={tags}
                folderTags={folderTags}
                kbDocs={kbDocs}
                placeholder={placeholder}
                contentSize='dialog'
              />
            </div>
            <DialogFooter className='shrink-0 gap-2 border-t bg-muted/20 px-5 py-3 sm:justify-end'>
              <Button type='button' variant='outline' size='sm' className='h-9' onClick={() => setDialogOpen(false)}>
                取消
              </Button>
              <Button type='button' size='sm' className='h-9' onClick={handleApply}>
                确定
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    )
  }

  return (
    <FilterExpressionEditorInner
      value={value}
      onChange={onChange}
      metadataFields={metadataFields}
      folders={folders}
      tags={tags}
      folderTags={folderTags}
      kbDocs={kbDocs}
      className={className}
      placeholder={placeholder}
      contentSize='default'
    />
  )
}


