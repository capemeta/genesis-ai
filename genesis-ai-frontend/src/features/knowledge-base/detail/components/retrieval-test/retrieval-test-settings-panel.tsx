import { Info, Loader2, Plus, RotateCcw, Save, SlidersHorizontal, Trash2 } from 'lucide-react'
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { AUTO_FILTER_MODE_OPTIONS, DEFAULT_RETRIEVAL_TEST_FORM, HIERARCHICAL_RETRIEVAL_MODE_OPTIONS } from './constants'
import { fetchModelSettingsOverview } from '@/lib/api/model-platform'
import type { RetrievalTestFormState } from './types'
import { FilterExpressionEditor } from '@/features/shared/filter-expression-editor'
import { fetchFolderTree } from '@/lib/api/folder'
import { fetchKnowledgeBaseDocuments, type KnowledgeBase, type QueryAnalysisMetadataField, type TableSchemaColumn } from '@/lib/api/knowledge-base'
import { getFolderAvailableTags, listScopedTags } from '@/lib/api/tag'
import { fetchQAKBFacets } from '@/lib/api/qa-items'
import type { FolderTreeNode } from '@/lib/api/folder.types'

interface RetrievalTestSettingsPanelProps {
  kb: KnowledgeBase
  kbType: string
  form: RetrievalTestFormState
  onFormChange: (updater: (prev: RetrievalTestFormState) => RetrievalTestFormState) => void
  onReset: () => void
  onSave: () => void
  saveDisabled: boolean
  actionDisabled: boolean
  isSaving: boolean
}

function SectionTitle({
  title,
  hint,
  tone,
}: {
  title: string
  hint: string
  tone: 'blue' | 'violet' | 'emerald'
}) {
  const toneClasses: Record<'blue' | 'violet' | 'emerald', { wrap: string; bar: string; title: string; hint: string }> = {
    blue: {
      wrap: 'bg-blue-50/60 border-blue-100/80',
      bar: 'bg-blue-500',
      title: 'text-blue-700',
      hint: 'text-blue-600/80',
    },
    violet: {
      wrap: 'bg-violet-50/60 border-violet-100/80',
      bar: 'bg-violet-500',
      title: 'text-violet-700',
      hint: 'text-violet-600/80',
    },
    emerald: {
      wrap: 'bg-emerald-50/60 border-emerald-100/80',
      bar: 'bg-emerald-500',
      title: 'text-emerald-700',
      hint: 'text-emerald-600/80',
    },
  }
  const style = toneClasses[tone]

  return (
    <div className={`flex items-end justify-between rounded-lg border px-2.5 py-2 ${style.wrap}`}>
      <span className={`inline-flex items-center gap-2 text-sm font-semibold ${style.title}`}>
        <span className={`h-4 w-1 rounded-full ${style.bar}`} />
        {title}
      </span>
      <span className={`text-[11px] ${style.hint}`}>{hint}</span>
    </div>
  )
}

function FieldLabel({
  label,
  tooltip,
}: {
  label: string
  tooltip?: string
}) {
  return (
    <label className='flex items-center gap-1.5 text-[11px] font-medium text-foreground/90'>
      {label}
      {tooltip && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className='h-3.5 w-3.5 cursor-help text-muted-foreground/80' />
            </TooltipTrigger>
            <TooltipContent>
              <p className='text-[11px]'>{tooltip}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </label>
  )
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

export function RetrievalTestSettingsPanel({
  kb,
  kbType,
  form,
  onFormChange,
  onReset,
  onSave,
  saveDisabled,
  actionDisabled,
  isSaving,
}: RetrievalTestSettingsPanelProps) {
  const enableLlmAutoFilter = form.autoFilterMode === 'llm_candidate' || form.autoFilterMode === 'hybrid'
  const enableHybridUpgrade = form.autoFilterMode === 'hybrid'
  const { data: modelOverview } = useQuery({
    queryKey: ['model-platform-settings-overview'],
    queryFn: fetchModelSettingsOverview,
  })
  const rerankModelOptions = useMemo(
    () =>
      (modelOverview?.providers ?? [])
        .filter((provider) => provider.is_configured && provider.is_enabled)
        .flatMap((provider) =>
          provider.models
            .filter((model) => model.is_enabled && model.capabilities.includes('rerank'))
            .map((model) => ({
              value: model.tenant_model_id,
              label: `${provider.display_name} / ${model.display_name}`,
            }))
        ),
    [modelOverview?.providers],
  )
  const hierarchicalModeOptions = useMemo(() => {
    const normalizedKbType = kbType.trim().toLowerCase()
    if (normalizedKbType === 'qa' || normalizedKbType === 'table') {
      return HIERARCHICAL_RETRIEVAL_MODE_OPTIONS.filter((item) => item.value !== 'leaf_only')
    }
    return HIERARCHICAL_RETRIEVAL_MODE_OPTIONS
  }, [kbType])
  const folderTreeQuery = useQuery({
    queryKey: ['retrieval-test', 'folder-tree', kb.id],
    queryFn: () => fetchFolderTree(kb.id),
    staleTime: 60_000,
  })
  const tagsQuery = useQuery({
    queryKey: ['retrieval-test', 'doc-tags', kb.id],
    queryFn: async () =>
      (
        await listScopedTags({
          kb_id: kb.id,
          scope: 'all',
          target_types: ['kb_doc'],
          page: 1,
          page_size: 100,
        })
      ).data.tags,
    staleTime: 60_000,
  })
  const folderTagsQuery = useQuery({
    queryKey: ['retrieval-test', 'folder-tags', kb.id],
    queryFn: () => getFolderAvailableTags(kb.id, undefined, 100),
    staleTime: 60_000,
  })
  const kbDocsQuery = useQuery({
    queryKey: ['retrieval-test', 'kb-docs', kb.id],
    queryFn: async () => {
      const response = await fetchKnowledgeBaseDocuments(kb.id, {
        page: 1,
        page_size: 100,
        is_enabled: true,
      })
      return response.data
    },
    staleTime: 60_000,
  })
  const qaFacetsQuery = useQuery({
    queryKey: ['retrieval-test', 'qa-facets', kb.id],
    queryFn: () => fetchQAKBFacets(kb.id),
    enabled: kb.type === 'qa',
    staleTime: 60_000,
  })
  const metadataFields = useMemo(() => {
    if (kb.type === 'table') {
      const tableColumns = Array.isArray(kb.retrieval_config?.table?.schema?.columns)
        ? kb.retrieval_config.table.schema.columns
        : []
      const explicitMetadataFields = Array.isArray(kb.retrieval_config?.query_analysis?.metadata_fields)
        ? kb.retrieval_config.query_analysis.metadata_fields
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
            target: explicit?.target,
            metadata_path: explicit?.metadata_path,
          }
        })
    }
    if (kb.type === 'qa') {
      const facets = qaFacetsQuery.data
      const fields: QueryAnalysisMetadataField[] = []
      if (Array.isArray(facets?.categories) && facets.categories.length > 0) {
        fields.push({
          key: 'category',
          name: '问答分类',
          enum_values: facets.categories,
          target: 'search_unit_metadata',
          metadata_path: ['qa_fields', 'category'],
        })
      }
      if (Array.isArray(facets?.tags) && facets.tags.length > 0) {
        fields.push({
          key: 'tag',
          name: '问答标签',
          enum_values: facets.tags,
          target: 'search_unit_metadata',
          metadata_path: ['qa_fields', 'tag'],
        })
      }
      return fields
    }
    return Array.isArray(kb.retrieval_config?.query_analysis?.metadata_fields)
      ? kb.retrieval_config.query_analysis.metadata_fields
      : []
  }, [kb, qaFacetsQuery.data])
  const availableFolders = useMemo(
    () => flattenFolderTree(Array.isArray(folderTreeQuery.data) ? folderTreeQuery.data : []),
    [folderTreeQuery.data]
  )
  const availableTags = useMemo(
    () => (Array.isArray(tagsQuery.data) ? tagsQuery.data : []).filter((tag) => tag.allowed_target_types?.includes('kb_doc')),
    [tagsQuery.data]
  )
  const availableFolderTags = useMemo(
    () => (Array.isArray(folderTagsQuery.data) ? folderTagsQuery.data : []),
    [folderTagsQuery.data]
  )
  const availableKbDocs = useMemo(
    () => (Array.isArray(kbDocsQuery.data) ? kbDocsQuery.data : []).map((item: any) => ({
      id: item.id,
      name: String(item.name || item.filename || item.id),
    })),
    [kbDocsQuery.data]
  )
  const softSliderClassName =
    'py-1.5 [&_[data-slot=slider-track]]:bg-blue-100/80 [&_[data-slot=slider-range]]:bg-blue-400/80 [&_[data-slot=slider-thumb]]:border-blue-300 [&_[data-slot=slider-thumb]]:bg-blue-50 [&_[data-slot=slider-thumb]]:hover:ring-blue-200/70 [&_[data-slot=slider-thumb]]:focus-visible:ring-blue-200/80'

  const updateNumberField = (
    key: 'topK' | 'vectorTopK' | 'keywordTopK' | 'rerankTopN',
    min: number,
    max: number,
    fallback: number
  ) => (value: string) => {
    const parsed = Number(value)
    const nextValue = Number.isFinite(parsed) ? Math.min(Math.max(Math.round(parsed), min), max) : fallback
    onFormChange((prev) => ({ ...prev, [key]: nextValue }))
  }

  const updateThresholdField = (
    key: 'vectorSimilarityThreshold' | 'keywordRelevanceThreshold' | 'finalScoreThreshold',
    fallback: number
  ) => ([value]: number[]) => {
      onFormChange((prev) => ({ ...prev, [key]: value ?? fallback }))
  }

  const updateQueryRewriteContextItem = (
    index: number,
    patch: Partial<RetrievalTestFormState['queryRewriteContext'][number]>
  ) => {
    onFormChange((prev) => ({
      ...prev,
      queryRewriteContext: prev.queryRewriteContext.map((item, currentIndex) =>
        currentIndex === index ? { ...item, ...patch } : item
      ),
    }))
  }

  const addQueryRewriteContextItem = () => {
    onFormChange((prev) => ({
      ...prev,
      queryRewriteContext: [
        ...prev.queryRewriteContext,
        {
          role: prev.queryRewriteContext.length % 2 === 0 ? 'user' : 'assistant',
          content: '',
        },
      ],
    }))
  }

  const removeQueryRewriteContextItem = (index: number) => {
    onFormChange((prev) => ({
      ...prev,
      queryRewriteContext: prev.queryRewriteContext.filter((_, currentIndex) => currentIndex !== index),
    }))
  }

  const handleRestoreRecommended = () => {
    onFormChange((prev) => ({
      ...DEFAULT_RETRIEVAL_TEST_FORM,
      queryRewriteContext: prev.queryRewriteContext,
      query: prev.query,
    }))
  }

  return (
    <aside className='flex w-[340px] flex-none flex-col border-r bg-transparent'>
      <div className='flex items-center justify-between gap-2 border-b bg-blue-50/20 p-3'>
        <div className='flex items-center gap-2'>
          <SlidersHorizontal className='h-4 w-4 text-blue-600' />
          <span className='text-sm font-semibold text-blue-700'>测试参数设置</span>
        </div>
        <Button
          variant='ghost'
          size='sm'
          className='h-7 px-2 text-[11px] text-blue-700 hover:bg-blue-100/70 hover:text-blue-800'
          onClick={handleRestoreRecommended}
          disabled={actionDisabled}
        >
          恢复推荐
        </Button>
      </div>

      <div className='flex-1 overflow-y-auto p-4'>
        <div className='space-y-5'>
          <div className='space-y-3'>
            <SectionTitle title='召回' hint='控制候选结果进入范围' tone='blue' />
            <div className='grid grid-cols-2 gap-2'>
              <div className='space-y-1.5'>
                <FieldLabel label='向量召回条数' tooltip='控制语义检索阶段进入候选集的结果数量。' />
                <Input
                  type='number'
                  min={1}
                  max={200}
                  value={form.vectorTopK}
                  onChange={(event) =>
                    updateNumberField('vectorTopK', 1, 200, form.vectorTopK)(event.target.value)
                  }
                />
              </div>
              <div className='space-y-1.5'>
                <FieldLabel label='全文召回条数' tooltip='控制关键词检索阶段进入候选集的结果数量。' />
                <Input
                  type='number'
                  min={1}
                  max={200}
                  value={form.keywordTopK}
                  onChange={(event) =>
                    updateNumberField('keywordTopK', 1, 200, form.keywordTopK)(event.target.value)
                  }
                />
              </div>
            </div>

            <div className='space-y-2'>
              <div className='flex items-center justify-between'>
                <FieldLabel label='向量相似度阈值' tooltip='过滤语义检索阶段分数过低的结果。' />
                <span className='rounded bg-primary/5 px-2 py-0.5 font-mono text-[11px] font-medium text-primary'>
                  {form.vectorSimilarityThreshold.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[form.vectorSimilarityThreshold]}
                onValueChange={updateThresholdField('vectorSimilarityThreshold', form.vectorSimilarityThreshold)}
                max={1}
                step={0.01}
                className={softSliderClassName}
              />
            </div>

            <div className='space-y-2'>
              <div className='flex items-center justify-between'>
                <FieldLabel label='全文相关性阈值' tooltip='过滤关键词检索阶段相关性过低的结果。' />
                <span className='rounded bg-primary/5 px-2 py-0.5 font-mono text-[11px] font-medium text-primary'>
                  {form.keywordRelevanceThreshold.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[form.keywordRelevanceThreshold]}
                onValueChange={updateThresholdField('keywordRelevanceThreshold', form.keywordRelevanceThreshold)}
                max={1}
                step={0.01}
                className={softSliderClassName}
              />
            </div>
          </div>

          <div className='space-y-3'>
            <SectionTitle title='融合' hint='控制多路结果合并方式' tone='violet' />
            <div className='space-y-2'>
              <div className='flex items-center justify-between'>
                <FieldLabel label='向量权重' tooltip='控制融合计算时语义检索结果的权重占比。' />
                <div className='flex items-center gap-2 text-[11px]'>
                  <span className='text-muted-foreground'>全文 {(1 - form.vectorWeight).toFixed(2)}</span>
                  <span className='rounded bg-primary/5 px-2 py-0.5 font-mono font-medium text-primary'>
                    向量 {form.vectorWeight.toFixed(2)}
                  </span>
                </div>
              </div>
              <Slider
                value={[form.vectorWeight]}
                onValueChange={([value]) =>
                  onFormChange((prev) => ({ ...prev, vectorWeight: value ?? prev.vectorWeight }))
                }
                max={1}
                step={0.01}
                className={softSliderClassName}
              />
            </div>

            <div className='space-y-2'>
              <div className='flex items-center justify-between'>
                <FieldLabel label='最终结果阈值' tooltip='过滤融合或重排后仍然偏弱的最终结果。' />
                <span className='rounded bg-primary/5 px-2 py-0.5 font-mono text-[11px] font-medium text-primary'>
                  {form.finalScoreThreshold.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[form.finalScoreThreshold]}
                onValueChange={updateThresholdField('finalScoreThreshold', form.finalScoreThreshold)}
                max={1}
                step={0.01}
                className={softSliderClassName}
              />
            </div>
          </div>

          <div className='space-y-3'>
            <SectionTitle title='排序与输出' hint='控制最终展示结果' tone='emerald' />
            <div className='grid grid-cols-2 gap-2'>
              <div className='space-y-1.5'>
                <FieldLabel label='重排输入条数' tooltip='控制进入重排模型参与精排的候选结果数量。' />
                <Input
                  type='number'
                  min={1}
                  max={200}
                  value={form.rerankTopN}
                  onChange={(event) =>
                    updateNumberField('rerankTopN', 1, 200, form.rerankTopN)(event.target.value)
                  }
                />
              </div>
              <div className='space-y-1.5'>
                <FieldLabel label='最终返回条数' tooltip='控制最终展示给用户的检索结果数量。' />
                <Input
                  type='number'
                  min={1}
                  max={200}
                  value={form.topK}
                  onChange={(event) =>
                    updateNumberField('topK', 1, 200, form.topK)(event.target.value)
                  }
                />
              </div>
              </div>

              <div className='space-y-1.5'>
                <div className='flex items-start justify-between gap-3 rounded-lg border border-emerald-200/70 bg-emerald-50/60 p-3'>
                  <div className='space-y-1'>
                    <FieldLabel label='启用重排序' tooltip='开启后使用真实 rerank 模型对候选结果精排。开启后必须选择模型。' />
                    <p className='text-[11px] text-muted-foreground'>默认开启。若未配置 rerank 模型，保存或执行检索时会直接报错。</p>
                  </div>
                  <Switch
                    checked={form.enableRerank}
                    onCheckedChange={(checked) => onFormChange((prev) => ({ ...prev, enableRerank: checked }))}
                    disabled={actionDisabled}
                  />
                </div>
              </div>

              <div className='space-y-1.5'>
                <FieldLabel label='Rerank 模型' tooltip='从模型中心中选择具备 rerank 能力的租户模型。' />
                <Select
                  value={form.rerankModel}
                  onValueChange={(value) => onFormChange((prev) => ({ ...prev, rerankModel: value }))}
                  disabled={!form.enableRerank || rerankModelOptions.length === 0}
                >
                  <SelectTrigger className='h-9 w-full text-sm'>
                    <SelectValue placeholder={rerankModelOptions.length > 0 ? '请选择 rerank 模型' : '暂无可用 rerank 模型'} />
                  </SelectTrigger>
                  <SelectContent>
                    {rerankModelOptions.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {form.enableRerank && rerankModelOptions.length === 0 ? (
                  <p className='text-[11px] text-red-500'>当前租户还没有启用任何 rerank 模型，请先到模型中心配置。</p>
                ) : null}
                {form.enableRerank && rerankModelOptions.length > 0 && !form.rerankModel.trim() ? (
                  <p className='text-[11px] text-amber-600'>已开启重排序，请选择一个 rerank 模型后再保存或执行测试。</p>
                ) : null}
              </div>

              <div className='space-y-1.5'>
                <FieldLabel label='层级召回策略' tooltip='控制父子分块如何返回。表格、QA 等独立元素拆分场景会优先回收到完整父块或完整行。' />
                <Select
                  value={form.hierarchicalRetrievalMode}
                  onValueChange={(value: 'leaf_only' | 'recursive' | 'auto_merge') =>
                    onFormChange((prev) => ({ ...prev, hierarchicalRetrievalMode: value }))
                  }
                >
                  <SelectTrigger className='h-9 w-full text-sm'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {hierarchicalModeOptions.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className='text-[11px] text-muted-foreground'>
                  `recursive` 保留命中叶子块并补父上下文；`auto_merge` 会把同一父块下的多个命中收敛成完整父块。
                </p>
              </div>

              <div className='space-y-2'>
                <div className='flex items-center justify-between'>
                  <FieldLabel label='邻近块补充' tooltip='以命中的叶子块为中心，补充前后相邻叶子块。对普通分块和父子分块都可生效，但自动父块合并模式下作用会较弱。' />
                  <span className='rounded bg-primary/5 px-2 py-0.5 font-mono text-[11px] font-medium text-primary'>
                    {form.neighborWindowSize}
                  </span>
                </div>
                <Slider
                  value={[form.neighborWindowSize]}
                  onValueChange={([value]) =>
                    onFormChange((prev) => ({
                      ...prev,
                      neighborWindowSize: Math.min(Math.max(Math.round(value ?? prev.neighborWindowSize), 0), 5),
                    }))
                  }
                  max={5}
                  step={1}
                  className={softSliderClassName}
                />
              </div>

              <div className='space-y-1.5'>
                <div className='flex items-start justify-between gap-3 rounded-lg border border-emerald-200/70 bg-emerald-50/60 p-3'>
                  <div className='space-y-1'>
                    <FieldLabel label='按业务单元聚合' tooltip='控制是否按 content_group_id 折叠结果。它只影响 QA、表格、Excel 行等业务对象聚合，不负责父子召回。' />
                    <p className='text-[11px] text-muted-foreground'>开启后，同一 QA、同一表格行、同一 Excel 行下的多个命中会更容易收敛成一条结果；关闭后只按当前层级召回结果单元排序。</p>
                  </div>
                  <Switch
                    checked={form.groupByContentGroup}
                    onCheckedChange={(checked) => onFormChange((prev) => ({ ...prev, groupByContentGroup: checked }))}
                    disabled={actionDisabled}
                  />
                </div>
              </div>
              <div className='space-y-3 pt-1'>
                <div className='space-y-2 rounded-lg border border-slate-200/70 bg-slate-50/70 p-3'>
                  <div className='flex items-start justify-between gap-3'>
                    <div className='space-y-1'>
                      <FieldLabel label='查询改写' tooltip='用 LLM 将当前问题改写成更适合检索的独立问题。聊天中可结合最近几轮上下文；检索测试中没有历史时，仅在存在有效多级目录时尝试目录建议。' />
                      <p className='text-[11px] text-muted-foreground'>推荐按需开启。没有多轮上下文且只有根目录时，后端会自动跳过，不做无意义改写。</p>
                    </div>
                    <Switch
                      checked={form.enableQueryRewrite}
                      onCheckedChange={(checked) => onFormChange((prev) => ({ ...prev, enableQueryRewrite: checked }))}
                      disabled={actionDisabled}
                    />
                  </div>
                  {form.enableQueryRewrite ? (
                    <div className='rounded-lg border border-sky-200/70 bg-white/80 p-3'>
                      <div className='flex items-start justify-between gap-3'>
                        <div className='space-y-1'>
                          <FieldLabel label='多轮测试上下文（可选）' tooltip='这里填写当前问题之前的历史消息，按时间从早到晚排列。当前问题仍然在顶部主输入框填写。未填写时，只验证单轮改写与目录建议。' />
                          {/* <p className='text-[11px] text-muted-foreground'>
                            适合复现“那赣州的呢”“还是刚才那个材料”这类省略承接问题。
                          </p> */}
                        </div>
                        <Button
                          type='button'
                          variant='outline'
                          size='sm'
                          className='h-8 px-2 text-[11px]'
                          onClick={addQueryRewriteContextItem}
                          disabled={actionDisabled}
                        >
                          <Plus className='mr-1 h-3.5 w-3.5' />
                          添加一条
                        </Button>
                      </div>
                      <div className='mt-3 space-y-3'>
                        {form.queryRewriteContext.length > 0 ? form.queryRewriteContext.map((item, index) => (
                          <div key={`rewrite-context-${index}`} className='rounded-lg border border-slate-200/80 bg-slate-50/70 p-3'>
                            <div className='flex items-center justify-between gap-3'>
                              <div className='flex items-center gap-2'>
                                <span className='rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700'>
                                  历史 {index + 1}
                                </span>
                                <Select
                                  value={item.role}
                                  onValueChange={(value: 'user' | 'assistant') => updateQueryRewriteContextItem(index, { role: value })}
                                  disabled={actionDisabled}
                                >
                                  <SelectTrigger className='h-8 w-[104px] text-xs'>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value='user'>用户</SelectItem>
                                    <SelectItem value='assistant'>助手</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                              <Button
                                type='button'
                                variant='ghost'
                                size='sm'
                                className='h-8 px-2 text-[11px] text-muted-foreground'
                                onClick={() => removeQueryRewriteContextItem(index)}
                                disabled={actionDisabled}
                              >
                                <Trash2 className='mr-1 h-3.5 w-3.5' />
                                删除
                              </Button>
                            </div>
                            <Textarea
                              value={item.content}
                              onChange={(event) => updateQueryRewriteContextItem(index, { content: event.target.value })}
                              placeholder={item.role === 'user' ? '例如：南康地区企业开办联系电话' : '例如：上一轮助手回答的关键摘要，可选填'}
                              rows={3}
                              className='mt-3 min-h-[84px] resize-y text-sm leading-relaxed'
                              disabled={actionDisabled}
                            />
                          </div>
                        )) : (
                          <div className='rounded-lg border border-dashed border-slate-200 bg-slate-50/40 px-3 py-4 text-[11px] leading-relaxed text-muted-foreground'>
                            当前未设置历史消息。此时查询改写只会按当前单轮问题处理；如果知识库存在多个目录，也会尝试目录建议。
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className='space-y-2 rounded-lg border border-slate-200/70 bg-slate-50/70 p-3'>
                  <div className='flex items-start justify-between gap-3'>
                    <div className='space-y-1'>
                      <FieldLabel label='同义词改写' tooltip='在检索前先做标准术语归一化，提升口语词与专业词的召回对齐。' />
                      <p className='text-[11px] text-muted-foreground'>位于查询改写之后，对改写后的独立问题再做术语归一化。</p>
                    </div>
                    <Switch
                      checked={form.enableSynonymRewrite}
                      onCheckedChange={(checked) => onFormChange((prev) => ({ ...prev, enableSynonymRewrite: checked }))}
                      disabled={actionDisabled}
                    />
                  </div>
                </div>

                <div className='space-y-1.5'>
                  <FieldLabel label='自动过滤抽取' tooltip='从问题中识别目录、标签、文档元数据、分块元数据候选。LLM 模式下，同一次模型调用除了返回候选，也可以顺带返回统一过滤表达式。' />
                  <Select
                    value={form.autoFilterMode}
                    onValueChange={(value: 'disabled' | 'rule' | 'llm_candidate' | 'hybrid') =>
                      onFormChange((prev) => ({
                        ...prev,
                        autoFilterMode: value,
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {AUTO_FILTER_MODE_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {enableLlmAutoFilter ? (
                  <div className='space-y-2 rounded-lg border border-dashed border-slate-200/70 bg-slate-50/70 p-3'>
                    <div className='flex items-start justify-between gap-3'>
                      <div className='space-y-1'>
                        <FieldLabel label='LLM 统一过滤表达式' tooltip='这是自动过滤抽取这一次 LLM 调用的附带输出，不会额外多调用一次模型。适合表达 OR、NOT、not_in、跨字段组合。' />
                        <p className='text-[11px] text-muted-foreground'>关闭后，LLM 仍可输出候选，但不会把同次返回里的复杂表达式并入最终过滤。</p>
                      </div>
                      <Switch
                        checked={form.enableLlmFilterExpression}
                        onCheckedChange={(checked) => onFormChange((prev) => ({ ...prev, enableLlmFilterExpression: checked }))}
                        disabled={actionDisabled}
                      />
                    </div>
                  </div>
                ) : null}
                {enableLlmAutoFilter ? (
                  <div className='space-y-3 rounded-lg border border-slate-200/70 bg-slate-50/70 p-3'>
                    <div className='space-y-1'>
                      <div className='text-sm font-medium text-foreground'>自动过滤抽取 · LLM 候选校验</div>
                      <p className='text-[11px] leading-relaxed text-muted-foreground'>
                        当前后端设计里，`llm_candidate` 主要负责产出并校验 LLM 候选；只有 `hybrid` 才允许高置信候选继续纠偏规则并升级为硬过滤。
                      </p>
                    </div>
                    <div className='space-y-1.5 rounded-lg border border-slate-200/70 bg-white/80 p-3'>
                      <FieldLabel label='LLM 最小置信度' tooltip='作用于自动过滤抽取这一次 LLM 返回的 candidates。低于该值的候选会在校验阶段直接被拒绝。' />
                      <div className='max-w-[220px]'>
                        <Input
                          type='number'
                          min={0}
                          max={1}
                          step='0.01'
                          value={form.llmCandidateMinConfidence}
                          onChange={(event) =>
                            onFormChange((prev) => ({
                              ...prev,
                              llmCandidateMinConfidence: Math.min(Math.max(Number(event.target.value || prev.llmCandidateMinConfidence), 0), 1),
                            }))}
                          disabled={actionDisabled}
                        />
                      </div>
                    </div>
                    {enableHybridUpgrade ? (
                      <div className='space-y-3 rounded-lg border border-dashed border-slate-200/70 bg-white/80 p-3'>
                        <div className='space-y-1'>
                          <div className='text-sm font-medium text-foreground'>自动过滤抽取 · Hybrid 硬过滤升级</div>
                          <p className='text-[11px] leading-relaxed text-muted-foreground'>
                            仅 `hybrid` 模式生效。高置信 LLM 候选在这一层才允许纠偏规则候选，并进一步升级为最终硬过滤。
                          </p>
                        </div>
                        <div className='space-y-3'>
                          <div className='space-y-1.5'>
                            <FieldLabel label='硬过滤升级阈值' tooltip='只在 hybrid 模式下生效。达到该阈值的高置信 LLM 候选，才允许纠偏规则候选或升级成硬过滤。' />
                            <div className='max-w-[220px]'>
                              <Input
                                type='number'
                                min={0}
                                max={1}
                                step='0.01'
                                value={form.llmUpgradeConfidenceThreshold}
                                onChange={(event) =>
                                  onFormChange((prev) => ({
                                    ...prev,
                                    llmUpgradeConfidenceThreshold: Math.min(Math.max(Number(event.target.value || prev.llmUpgradeConfidenceThreshold), 0), 1),
                                  }))}
                                disabled={actionDisabled}
                              />
                            </div>
                          </div>
                          <div className='space-y-1.5'>
                            <FieldLabel label='最大升级数量' tooltip='只在 hybrid 模式下生效。限制本轮最多有多少个 LLM 候选可以升级成硬过滤，避免一次查询过度收窄。' />
                            <div className='max-w-[220px]'>
                              <Input
                                type='number'
                                min={1}
                                max={8}
                                value={form.llmMaxUpgradeCount}
                                onChange={(event) =>
                                  onFormChange((prev) => ({
                                    ...prev,
                                    llmMaxUpgradeCount: Math.min(Math.max(Math.round(Number(event.target.value || prev.llmMaxUpgradeCount)), 1), 8),
                                  }))}
                                disabled={actionDisabled}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className='space-y-1.5 rounded-lg border border-slate-200/70 bg-slate-50/70 p-3'>
                <FieldLabel
                  label='高级过滤表达式'
                  tooltip='输入 JSON 表达式，可直接描述目录、标签、文档元数据、分块元数据等组合过滤，并验证括号、跨字段 OR、not_in 等硬过滤能力。'
                />
                <FilterExpressionEditor
                  variant='dialog'
                  dialogTitle='高级过滤表达式'
                  value={form.filterExpressionText}
                  onChange={(nextValue) => onFormChange((prev) => ({ ...prev, filterExpressionText: nextValue }))}
                  metadataFields={metadataFields}
                  folders={availableFolders}
                  tags={availableTags.map((item) => ({ id: item.id, name: item.name }))}
                  folderTags={availableFolderTags.map((item: any) => ({ id: item.id, name: String(item.name || item.label || item.id) }))}
                  kbDocs={availableKbDocs}
                  placeholder={'{"op":"or","items":[{"field":"metadata","path":["region"],"op":"in","values":["南康"]},{"field":"tag","op":"not_in","values":["标签ID"]}]}'}
                />
                <div className='text-[11px] leading-5 text-muted-foreground'>
                  这里是统一过滤表达式入口，标签和元数据都能写；留空表示不额外增加硬过滤。
                </div>
              </div>
          </div>
        </div>
      </div>

      <div className='border-t bg-blue-50/20 p-3'>
        <div className='flex items-center gap-2'>
          <Button
            variant='ghost'
            size='sm'
            className='flex-1 gap-1.5 text-xs text-muted-foreground'
            onClick={onReset}
            disabled={actionDisabled}
          >
            <RotateCcw className='h-3.5 w-3.5' />
            恢复已保存
          </Button>
          <Button
            size='sm'
            className='flex-1 gap-1.5 bg-blue-600 text-xs text-white hover:bg-blue-700'
            onClick={onSave}
            disabled={saveDisabled || actionDisabled}
          >
            {isSaving ? <Loader2 className='h-3.5 w-3.5 animate-spin' /> : <Save className='h-3.5 w-3.5' />}
            保存配置
          </Button>
        </div>
      </div>
    </aside>
  )
}
