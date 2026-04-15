import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronUp, FileText, Filter, FolderTree, RotateCcw, Tags } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { InlineHelpTip } from '@/features/chat/components/shared/inline-help-tip'
import { FilterExpressionEditor } from '@/features/shared/filter-expression-editor'
import { fetchKnowledgeBase } from '@/lib/api/knowledge-base'
import { fetchKnowledgeBaseDocuments } from '@/lib/api/knowledge-base'
import { fetchFolderTree } from '@/lib/api/folder'
import { fetchQAKBFacets } from '@/lib/api/qa-items'
import { getFolderAvailableTags, listScopedTags } from '@/lib/api/tag'
import type { FolderTreeNode, Tag } from '@/lib/api/folder.types'
import type {
  ChatConfigDraft,
  ChatSelectorOption,
} from '@/features/chat/types/chat'
import type { QueryAnalysisMetadataField, TableSchemaColumn } from '@/lib/api/knowledge-base'

interface KnowledgeBaseScopeCardProps {
  kbId: string
  kbOption?: ChatSelectorOption
  scopeDraft: ChatConfigDraft['knowledgeBaseScopes'][string]
  expanded: boolean
  onExpandedChange: (expanded: boolean) => void
  onChange: (nextScope: ChatConfigDraft['knowledgeBaseScopes'][string]) => void
}

function normalizeMetadataValue(value: string): string {
  return value.trim()
}

function flattenFolderTree(nodes: FolderTreeNode[], prefix = ''): Array<{ id: string; label: string }> {
  const result: Array<{ id: string; label: string }> = []
  for (const node of nodes) {
    const label = prefix ? `${prefix} / ${node.name}` : node.name
    result.push({ id: node.id, label })
    if (Array.isArray(node.children) && node.children.length > 0) {
      result.push(...flattenFolderTree(node.children, label))
    }
  }
  return result
}

/**
 * 知识库会话范围设置卡片。
 * 只暴露当前后端稳定支持的目录、标签、分类与结构化字段过滤，避免 UI 过重。
 */
export function KnowledgeBaseScopeCard({
  kbId,
  kbOption,
  scopeDraft,
  expanded,
  onExpandedChange,
  onChange,
}: KnowledgeBaseScopeCardProps) {
  const kbQuery = useQuery({
    queryKey: ['chat', 'kb-scope', 'kb-detail', kbId],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: expanded,
    staleTime: 60_000,
  })

  const tagsQuery = useQuery({
    queryKey: ['chat', 'kb-scope', 'kb-tags', kbId],
    queryFn: async () =>
      (
        await listScopedTags({
          kb_id: kbId,
          scope: 'all',
          target_types: ['kb_doc'],
          page: 1,
          page_size: 100,
        })
      ).data.tags,
    enabled: expanded,
    staleTime: 60_000,
  })

  const folderTreeQuery = useQuery({
    queryKey: ['chat', 'kb-scope', 'folder-tree', kbId],
    queryFn: () => fetchFolderTree(kbId),
    enabled: expanded,
    staleTime: 60_000,
  })

  const folderTagsQuery = useQuery({
    queryKey: ['chat', 'kb-scope', 'folder-tags', kbId],
    queryFn: () => getFolderAvailableTags(kbId, undefined, 100),
    enabled: expanded,
    staleTime: 60_000,
  })

  const kbDocsQuery = useQuery({
    queryKey: ['chat', 'kb-scope', 'kb-docs', kbId],
    queryFn: async () => {
      const response = await fetchKnowledgeBaseDocuments(kbId, {
        page: 1,
        page_size: 100,
        is_enabled: true,
      })
      return response.data
    },
    enabled: expanded,
    staleTime: 60_000,
  })

  const qaFacetsQuery = useQuery({
    queryKey: ['chat', 'kb-scope', 'qa-facets', kbId],
    queryFn: () => fetchQAKBFacets(kbId),
    enabled: expanded && kbQuery.data?.type === 'qa',
    staleTime: 60_000,
  })

  const metadataFields = useMemo(() => {
    if (kbQuery.data?.type === 'table') {
      const tableColumns = Array.isArray(kbQuery.data?.retrieval_config?.table?.schema?.columns)
        ? kbQuery.data.retrieval_config.table.schema.columns
        : []
      const explicitMetadataFields = Array.isArray(kbQuery.data?.retrieval_config?.query_analysis?.metadata_fields)
        ? kbQuery.data.retrieval_config.query_analysis.metadata_fields
        : []
      const explicitFieldMap = new Map(
        explicitMetadataFields.map((field) => [String(field.key || '').trim(), field])
      )

      return tableColumns
        .filter((column: TableSchemaColumn) => Boolean(column?.filterable && column?.name))
        .map((column: TableSchemaColumn): QueryAnalysisMetadataField => {
          const key = String(column.name || '').trim()
          const explicit = explicitFieldMap.get(key)
          return {
            key,
            name: explicit?.name || key,
            aliases: explicit?.aliases || column.aliases,
            enum_values: explicit?.enum_values || column.enum_values,
            options: explicit?.options,
          }
        })
    }
    if (kbQuery.data?.type === 'qa') {
      const facets = qaFacetsQuery.data
      const fields: QueryAnalysisMetadataField[] = []
      if (Array.isArray(facets?.categories) && facets.categories.length > 0) {
        fields.push({
          key: 'category',
          name: '问答分类',
          enum_values: facets.categories,
        })
      }
      if (Array.isArray(facets?.tags) && facets.tags.length > 0) {
        fields.push({
          key: 'tag',
          name: '问答标签',
          enum_values: facets.tags,
        })
      }
      return fields
    }
    const queryAnalysis = kbQuery.data?.retrieval_config?.query_analysis
    return Array.isArray(queryAnalysis?.metadata_fields) ? queryAnalysis.metadata_fields : []
  }, [kbQuery.data, qaFacetsQuery.data])

  const availableTags = useMemo(() => {
    const allTags = Array.isArray(tagsQuery.data) ? tagsQuery.data : []
    return allTags.filter((tag) => tag.allowed_target_types?.includes('kb_doc'))
  }, [tagsQuery.data])

  const availableFolders = useMemo(
    () => flattenFolderTree(Array.isArray(folderTreeQuery.data) ? folderTreeQuery.data : []),
    [folderTreeQuery.data]
  )

  const availableFolderTags = useMemo(
    () => (Array.isArray(folderTagsQuery.data) ? folderTagsQuery.data : []),
    [folderTagsQuery.data]
  )
  const activeFilterCount = useMemo(() => {
    const kbDocCount = scopeDraft.kbDocIds.length
    const folderCount = scopeDraft.folderIds.length
    const folderTagCount = scopeDraft.folderTagIds.length
    const tagCount = scopeDraft.tagIds.length
    const metadataCount = Object.values(scopeDraft.metadata).filter((value) => value.trim().length > 0).length
    const expressionCount = String(scopeDraft.filterExpressionText || '').trim().length > 0 ? 1 : 0
    return kbDocCount + folderCount + folderTagCount + tagCount + metadataCount + expressionCount
  }, [scopeDraft.filterExpressionText, scopeDraft.kbDocIds, scopeDraft.folderIds, scopeDraft.folderTagIds, scopeDraft.metadata, scopeDraft.tagIds])

  const toggleKbDoc = (kbDocId: string) => {
    const currentKbDocIds = Array.isArray(scopeDraft.kbDocIds) ? scopeDraft.kbDocIds : []
    const nextKbDocIds = currentKbDocIds.includes(kbDocId)
      ? currentKbDocIds.filter((item) => item !== kbDocId)
      : [...currentKbDocIds, kbDocId]
    onChange({
      ...scopeDraft,
      kbDocIds: nextKbDocIds,
    })
  }

  const toggleFolder = (folderId: string) => {
    const currentFolderIds = Array.isArray(scopeDraft.folderIds) ? scopeDraft.folderIds : []
    const nextFolderIds = currentFolderIds.includes(folderId)
      ? currentFolderIds.filter((item) => item !== folderId)
      : [...currentFolderIds, folderId]
    onChange({
      ...scopeDraft,
      folderIds: nextFolderIds,
    })
  }

  const toggleFolderTag = (tagId: string) => {
    const currentTagIds = Array.isArray(scopeDraft.folderTagIds) ? scopeDraft.folderTagIds : []
    const nextTagIds = currentTagIds.includes(tagId)
      ? currentTagIds.filter((item) => item !== tagId)
      : [...currentTagIds, tagId]
    onChange({
      ...scopeDraft,
      folderTagIds: nextTagIds,
    })
  }

  const toggleTag = (tagId: string) => {
    const currentTagIds = Array.isArray(scopeDraft.tagIds) ? scopeDraft.tagIds : []
    const nextTagIds = currentTagIds.includes(tagId)
      ? currentTagIds.filter((item) => item !== tagId)
      : [...currentTagIds, tagId]
    onChange({
      ...scopeDraft,
      tagIds: nextTagIds,
    })
  }

  const updateMetadata = (key: string, value: string) => {
    const nextMetadata = { ...(scopeDraft.metadata || {}) }
    const normalizedValue = normalizeMetadataValue(value)
    if (normalizedValue) {
      nextMetadata[key] = normalizedValue
    } else {
      delete nextMetadata[key]
    }
    onChange({
      ...scopeDraft,
      metadata: nextMetadata,
    })
  }

  const resetScope = () => {
    onChange({
      kbDocIds: [],
      folderIds: [],
      folderTagIds: [],
      includeDescendantFolders: true,
      tagIds: [],
      metadata: {},
      filterExpressionText: '',
    })
  }

  const renderMetadataField = (field: NonNullable<typeof metadataFields>[number]) => {
    const key = String(field.key || '').trim()
    if (!key) {
      return null
    }

    const label = String(field.name || key).trim() || key
    const rawOptions = Array.isArray(field.options) && field.options.length > 0
      ? field.options
      : Array.isArray(field.enum_values)
        ? field.enum_values
        : []
    const options = rawOptions
      .map((option) => {
        if (typeof option === 'string') {
          const normalized = option.trim()
          return normalized ? { value: normalized, label: normalized } : null
        }
        if (!option || typeof option !== 'object') {
          return null
        }
        const value = String(option.value || option.name || option.label || '').trim()
        if (!value) {
          return null
        }
        return {
          value,
          label: String(option.label || option.name || value).trim() || value,
        }
      })
      .filter((item): item is { value: string; label: string } => Boolean(item))
    const currentValue = scopeDraft.metadata?.[key] || ''

    return (
      <div key={key} className='space-y-2 rounded-xl border border-border/40 bg-background/60 p-3'>
        <Label className='text-[11px] font-semibold text-foreground/70'>{label}</Label>
        {options.length > 0 ? (
          <Select value={currentValue || '__all__'} onValueChange={(value) => updateMetadata(key, value === '__all__' ? '' : value)}>
            <SelectTrigger className='h-9 w-full rounded-lg border-border/50 bg-muted/20 text-xs'>
              <SelectValue placeholder={`不限${label}`} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='__all__'>不限</SelectItem>
              {options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            value={currentValue}
            placeholder={`只看${label}`}
            className='h-9 rounded-lg border-border/50 bg-muted/20 text-xs'
            onChange={(event) => updateMetadata(key, event.target.value)}
          />
        )}
      </div>
    )
  }

  return (
    <div className='rounded-2xl border border-border/50 bg-background/40 p-4 shadow-sm'>
      <div className='flex items-start justify-between gap-3'>
        <div className='min-w-0 space-y-1'>
          <div className='flex items-center gap-2'>
            <span className='truncate text-sm font-semibold text-foreground/80' title={kbOption?.name || kbId}>
              {kbOption?.name || kbId}
            </span>
            {activeFilterCount > 0 ? (
              <Badge variant='secondary' className='rounded-full text-[10px] font-medium'>
                已设 {activeFilterCount} 项
              </Badge>
            ) : null}
          </div>
          <div className='flex items-center gap-1.5 text-[10px] text-muted-foreground/55'>
            <Filter className='h-3.5 w-3.5' />
            只影响当前会话里这个知识库的检索范围
          </div>
        </div>
        <div className='flex items-center gap-2'>
          {activeFilterCount > 0 ? (
            <Button
              type='button'
              variant='ghost'
              size='sm'
              className='h-8 rounded-lg px-2 text-[10px] text-muted-foreground'
              onClick={resetScope}
            >
              <RotateCcw className='mr-1 h-3.5 w-3.5' />
              清空
            </Button>
          ) : null}
          <Button
            type='button'
            variant='outline'
            size='sm'
            className='h-8 rounded-lg border-border/50 bg-muted/15 text-[10px] font-semibold'
            onClick={() => onExpandedChange(!expanded)}
          >
            范围设置
            {expanded ? <ChevronUp className='ml-1 h-3.5 w-3.5' /> : <ChevronDown className='ml-1 h-3.5 w-3.5' />}
          </Button>
        </div>
      </div>

      {expanded ? (
        <div className='mt-4 space-y-4 border-t border-dashed pt-4'>
          <div className='space-y-3'>
            <div className='flex items-center gap-1.5'>
              <FileText className='h-3.5 w-3.5 text-emerald-500/80' />
              <Label className='mb-0 text-[11px] font-bold text-foreground/65'>指定文档</Label>
              <InlineHelpTip content='只在这些文档里检索。适合这次对话只围绕几篇资料展开。' />
            </div>
            {kbDocsQuery.isLoading ? (
              <div className='text-[11px] text-muted-foreground/50'>正在加载文档列表…</div>
            ) : Array.isArray(kbDocsQuery.data) && kbDocsQuery.data.length > 0 ? (
              <div className='flex flex-wrap gap-2'>
                {kbDocsQuery.data.map((kbDoc) => {
                  const docId = String(kbDoc.id || '').trim()
                  if (!docId) {
                    return null
                  }
                  const active = scopeDraft.kbDocIds.includes(docId)
                  const title = String(kbDoc.display_name || kbDoc.document?.name || '未命名文档').trim() || '未命名文档'
                  return (
                    <button
                      key={docId}
                      type='button'
                      className={`max-w-full rounded-full border px-3 py-1 text-[11px] transition-colors ${
                        active
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700'
                          : 'border-border/50 bg-muted/15 text-muted-foreground hover:border-border hover:bg-muted/30'
                      }`}
                      onClick={() => toggleKbDoc(docId)}
                      title={title}
                    >
                      <span className='block max-w-[280px] truncate'>{title}</span>
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className='text-[11px] text-muted-foreground/50'>这个知识库暂时还没有可选文档。</div>
            )}
          </div>

          <div className='space-y-3'>
            <div className='flex items-center gap-1.5'>
              <FolderTree className='h-3.5 w-3.5 text-amber-500/80' />
              <Label className='mb-0 text-[11px] font-bold text-foreground/65'>目录范围</Label>
              <InlineHelpTip content='只在这些目录下检索。适合把会话限定到某个项目、部门或资料区。' />
            </div>
            {folderTreeQuery.isLoading ? (
              <div className='text-[11px] text-muted-foreground/50'>正在加载目录…</div>
            ) : availableFolders.length > 0 ? (
              <>
                <div className='flex flex-wrap gap-2'>
                  {availableFolders.map((folder) => {
                    const active = scopeDraft.folderIds.includes(folder.id)
                    return (
                      <button
                        key={folder.id}
                        type='button'
                        className={`rounded-full border px-3 py-1 text-[11px] transition-colors ${
                          active
                            ? 'border-amber-500/40 bg-amber-500/10 text-amber-700'
                            : 'border-border/50 bg-muted/15 text-muted-foreground hover:border-border hover:bg-muted/30'
                        }`}
                        onClick={() => toggleFolder(folder.id)}
                        title={folder.label}
                      >
                        {folder.label}
                      </button>
                    )
                  })}
                </div>
                {(scopeDraft.folderIds.length > 0 || scopeDraft.folderTagIds.length > 0) ? (
                  <div className='flex items-center justify-between rounded-xl border border-border/40 bg-muted/10 px-3 py-2'>
                    <div className='space-y-0.5'>
                      <div className='text-[11px] font-semibold text-foreground/70'>包含子目录</div>
                      <div className='text-[10px] text-muted-foreground/45'>
                        打开后，会把下级目录里的文档也一起纳入检索范围
                      </div>
                    </div>
                    <Switch
                      checked={scopeDraft.includeDescendantFolders !== false}
                      onCheckedChange={(checked) =>
                        onChange({
                          ...scopeDraft,
                          includeDescendantFolders: checked,
                        })
                      }
                    />
                  </div>
                ) : null}
              </>
            ) : (
              <div className='text-[11px] text-muted-foreground/50'>这个知识库还没有目录结构。</div>
            )}
          </div>

          <div className='space-y-3'>
            <div className='flex items-center gap-1.5'>
              <Tags className='h-3.5 w-3.5 text-orange-500/75' />
              <Label className='mb-0 text-[11px] font-bold text-foreground/65'>文件夹标签</Label>
              <InlineHelpTip content='按目录标签缩小检索范围，适合先圈定资料区，再在其中检索文档内容。' />
            </div>
            {folderTagsQuery.isLoading ? (
              <div className='text-[11px] text-muted-foreground/50'>正在加载目录标签…</div>
            ) : availableFolderTags.length > 0 ? (
              <div className='flex flex-wrap gap-2'>
                {availableFolderTags.map((tag: Tag) => {
                  const active = scopeDraft.folderTagIds.includes(tag.id)
                  return (
                    <button
                      key={tag.id}
                      type='button'
                      className={`rounded-full border px-3 py-1 text-[11px] transition-colors ${
                        active
                          ? 'border-orange-500/40 bg-orange-500/10 text-orange-700'
                          : 'border-border/50 bg-muted/15 text-muted-foreground hover:border-border hover:bg-muted/30'
                      }`}
                      onClick={() => toggleFolderTag(tag.id)}
                    >
                      {tag.name}
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className='text-[11px] text-muted-foreground/50'>这个知识库暂时没有可选目录标签。</div>
            )}
          </div>

          <div className='space-y-3'>
            <div className='flex items-center gap-1.5'>
              <Tags className='h-3.5 w-3.5 text-blue-500/70' />
              <Label className='mb-0 text-[11px] font-bold text-foreground/65'>文档标签</Label>
              <InlineHelpTip content='只在命中这些标签的文档里检索。可多选；不选表示不限。' />
            </div>
            {tagsQuery.isLoading ? (
              <div className='text-[11px] text-muted-foreground/50'>正在加载可选标签…</div>
            ) : availableTags.length > 0 ? (
              <div className='flex flex-wrap gap-2'>
                {availableTags.map((tag: Tag) => {
                  const active = scopeDraft.tagIds.includes(tag.id)
                  return (
                    <button
                      key={tag.id}
                      type='button'
                      className={`rounded-full border px-3 py-1 text-[11px] transition-colors ${
                        active
                          ? 'border-blue-500/40 bg-blue-500/10 text-blue-700'
                          : 'border-border/50 bg-muted/15 text-muted-foreground hover:border-border hover:bg-muted/30'
                      }`}
                      onClick={() => toggleTag(tag.id)}
                    >
                      {tag.name}
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className='text-[11px] text-muted-foreground/50'>这个知识库暂时没有可选文档标签。</div>
            )}
          </div>

          <div className='space-y-3'>
            <div className='flex items-center gap-1.5'>
              <Label className='mb-0 text-[11px] font-bold text-foreground/65'>文档属性</Label>
              <InlineHelpTip
                content={
                  kbQuery.data?.type === 'table'
                    ? '按表格里的过滤字段缩小范围，例如地区、年份、产品。留空就是不限。'
                    : kbQuery.data?.type === 'qa'
                      ? '按问答分类或标签缩小范围，适合常见 FAQ、产品问答或流程问答场景。'
                    : '按文档属性缩小范围，例如区域、产品线、版本。留空就是不限。'
                }
              />
            </div>
            {kbQuery.isLoading || qaFacetsQuery.isLoading ? (
              <div className='text-[11px] text-muted-foreground/50'>
                {kbQuery.data?.type === 'table'
                  ? '正在加载可选过滤字段…'
                  : kbQuery.data?.type === 'qa'
                    ? '正在加载问答分类与标签…'
                    : '正在加载可选文档属性…'}
              </div>
            ) : metadataFields.length > 0 ? (
              <div className='grid gap-3'>
                {metadataFields.map(renderMetadataField)}
              </div>
            ) : (
              <div className='text-[11px] text-muted-foreground/50'>
                {kbQuery.data?.type === 'table'
                  ? '这个表格知识库还没有可过滤字段，请先在表结构里勾选 filterable 列。'
                  : kbQuery.data?.type === 'qa'
                    ? '这个 QA 知识库暂时还没有可选的分类或标签。'
                  : '这个知识库还没有配置可识别的文档属性。'}
              </div>
            )}
          </div>

          <div className='space-y-3'>
            <div className='flex items-center gap-1.5'>
              <Label className='mb-0 text-[11px] font-bold text-foreground/65'>高级过滤表达式（标签 / 元数据）</Label>
              <InlineHelpTip content='统一表达标签、目录、文档元数据、分块元数据等组合条件。支持括号、跨字段 OR、not_in，并会和上方简单过滤一起生效。' />
            </div>
            <FilterExpressionEditor
              value={scopeDraft.filterExpressionText || ''}
              onChange={(nextValue) =>
                onChange({
                  ...scopeDraft,
                  filterExpressionText: nextValue,
                })
              }
              metadataFields={metadataFields}
              folders={availableFolders}
              tags={availableTags.map((item) => ({ id: item.id, name: item.name }))}
              folderTags={availableFolderTags.map((item: any) => ({ id: item.id, name: String(item.name || item.label || item.id) }))}
              kbDocs={(Array.isArray(kbDocsQuery.data) ? kbDocsQuery.data : []).map((item: any) => ({
                id: item.id,
                name: String(item.name || item.filename || item.id),
              }))}
              placeholder={'{"op":"and","items":[{"field":"metadata","path":["region"],"op":"in","values":["南康"]},{"field":"tag","op":"not_in","values":["标签ID"]}]}'}
            />
            <div className='text-[10px] leading-5 text-muted-foreground/55'>
              留空表示不限；这里是统一过滤入口，标签和元数据都可以写，保存后会随聊天知识库过滤一起生效。
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
