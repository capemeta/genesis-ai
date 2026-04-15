import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { CircleHelp, FileSearch, Search, Sparkles } from 'lucide-react'
import type { QueryAnalysisMetadataOption } from '@/lib/api/knowledge-base'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'

type MetadataTarget = 'document_metadata' | 'search_unit_metadata'
type MetadataMatchMode = 'match_or_missing' | 'match_only'

function HelpTip({ content }: { content: string }) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type='button'
            className='inline-flex shrink-0 items-center text-muted-foreground transition-colors hover:text-foreground'
            aria-label='说明'
          >
            <CircleHelp className='h-3.5 w-3.5' />
          </button>
        </TooltipTrigger>
        <TooltipContent side='top' className='max-w-xs text-xs leading-5'>
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function normalizeMetadataOptions(rawValue: string): Array<string | QueryAnalysisMetadataOption> {
  return rawValue
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split('|').map((item) => item.trim())
      if (parts.length <= 1) {
        return line
      }
      const [label, value, aliasText] = parts
      const aliases = (aliasText || '')
        .split(/[，,\/]/)
        .map((item) => item.trim())
        .filter(Boolean)
      return {
        label: label || value,
        value: value || label,
        aliases,
      }
    })
}

function formatMetadataOptions(value: Array<string | QueryAnalysisMetadataOption> | undefined): string {
  if (!Array.isArray(value)) {
    return ''
  }
  return value
    .map((item) => {
      if (typeof item === 'string') {
        return item
      }
      const label = String(item.label || item.name || item.value || '').trim()
      const normalizedValue = String(item.value || item.name || item.label || '').trim()
      const aliases = Array.isArray(item.aliases) ? item.aliases.filter(Boolean).join('/') : ''
      return [label, normalizedValue, aliases].filter(Boolean).join('|')
    })
    .filter(Boolean)
    .join('\n')
}

function parseMetadataPath(value: string): string[] {
  return value
    .split('.')
    .map((item) => item.trim())
    .filter(Boolean)
}

function formatMetadataPath(value: unknown): string {
  if (!Array.isArray(value)) {
    return ''
  }
  return value.map((item) => String(item || '').trim()).filter(Boolean).join('.')
}

interface RetrievalAnswerSectionProps {
  config: ConfigState
  onConfigChange: (config: ConfigState) => void
}

function sanitizeQueryAnalysisConfig(rawQueryAnalysis: Record<string, any>) {
  const nextQueryAnalysis = { ...rawQueryAnalysis }
  const autoFilterMode = String(nextQueryAnalysis.auto_filter_mode || 'disabled')
  const enableLlmAutoFilter = autoFilterMode === 'llm_candidate' || autoFilterMode === 'hybrid'
  const enableHybridUpgrade = autoFilterMode === 'hybrid'

  if (!enableLlmAutoFilter) {
    delete nextQueryAnalysis.enable_llm_filter_expression
    delete nextQueryAnalysis.llm_candidate_min_confidence
    delete nextQueryAnalysis.llm_upgrade_confidence_threshold
    delete nextQueryAnalysis.llm_max_upgrade_count
  }
  else if (!enableHybridUpgrade) {
    delete nextQueryAnalysis.llm_upgrade_confidence_threshold
    delete nextQueryAnalysis.llm_max_upgrade_count
  }

  return nextQueryAnalysis
}

export function RetrievalAnswerSection({ config, onConfigChange }: RetrievalAnswerSectionProps) {
  const persistentContext = {
    enabled: false,
    content: '',
    enable_doc_summary_as_context: false,
    enable_doc_summary_retrieval: false,
    doc_summary_min_chars: 24,
    doc_summary_min_tokens: 8,
    doc_summary_max_chars: 1200,
    doc_summary_min_unique_terms: 3,
    doc_summary_excluded_phrases: [],
    ...((config.retrieval_config as Record<string, any> | undefined)?.persistent_context || {}),
  }
  const queryAnalysis = {
    enable_query_rewrite: false,
    enable_synonym_rewrite: true,
    auto_filter_mode: 'disabled',
    enable_llm_filter_expression: true,
    metadata_fields: [],
    retrieval_lexicon: [],
    retrieval_stopwords: [],
    llm_candidate_min_confidence: 0.55,
    llm_upgrade_confidence_threshold: 0.82,
    llm_max_upgrade_count: 2,
    ...((config.retrieval_config as Record<string, any> | undefined)?.query_analysis || {}),
  }

  const updatePersistentContext = (patch: Record<string, any>) => {
    onConfigChange({
      ...config,
      retrieval_config: {
        ...(config.retrieval_config || {}),
        persistent_context: {
          ...persistentContext,
          ...patch,
        },
      },
    })
  }

  const updateQueryAnalysis = (patch: Record<string, any>) => {
    const nextQueryAnalysis = sanitizeQueryAnalysisConfig({
      ...queryAnalysis,
      ...patch,
    })
    onConfigChange({
      ...config,
      retrieval_config: {
        ...(config.retrieval_config || {}),
        query_analysis: nextQueryAnalysis,
      },
    })
  }

  const metadataFields = Array.isArray(queryAnalysis.metadata_fields) ? queryAnalysis.metadata_fields : []
  const retrievalLexicon = Array.isArray(queryAnalysis.retrieval_lexicon) ? queryAnalysis.retrieval_lexicon : []
  const retrievalStopwords = Array.isArray(queryAnalysis.retrieval_stopwords) ? queryAnalysis.retrieval_stopwords : []
  const autoFilterMode = String(queryAnalysis.auto_filter_mode || 'disabled')
  const enableLlmAutoFilter = autoFilterMode === 'llm_candidate' || autoFilterMode === 'hybrid'
  const enableHybridUpgrade = autoFilterMode === 'hybrid'

  const updateMetadataField = (index: number, patch: Record<string, any>) => {
    const nextFields = metadataFields.map((field: any, currentIndex: number) =>
      currentIndex === index ? { ...field, ...patch } : field
    )
    updateQueryAnalysis({ metadata_fields: nextFields })
  }

  const removeMetadataField = (index: number) => {
    updateQueryAnalysis({ metadata_fields: metadataFields.filter((_: any, currentIndex: number) => currentIndex !== index) })
  }

  const addMetadataField = () => {
    updateQueryAnalysis({
      metadata_fields: [
        ...metadataFields,
        {
          key: '',
          name: '',
          aliases: [],
          enum_values: [],
          target: 'document_metadata',
          metadata_path: [],
          match_mode: 'match_or_missing',
        },
      ],
    })
  }

  const updateRetrievalLexiconItem = (index: number, patch: Record<string, any>) => {
    const nextItems = retrievalLexicon.map((item: any, currentIndex: number) =>
      currentIndex === index ? { ...item, ...patch } : item
    )
    updateQueryAnalysis({ retrieval_lexicon: nextItems })
  }

  const removeRetrievalLexiconItem = (index: number) => {
    updateQueryAnalysis({
      retrieval_lexicon: retrievalLexicon.filter((_: any, currentIndex: number) => currentIndex !== index),
    })
  }

  const addRetrievalLexiconItem = () => {
    updateQueryAnalysis({
      retrieval_lexicon: [
        ...retrievalLexicon,
        {
          term: '',
          aliases: [],
          is_phrase: true,
          weight: 1,
          enabled: true,
        },
      ],
    })
  }

  return (
    <div className='space-y-6'>
      <div className='space-y-2'>
        <div className='flex items-center justify-between'>
          <Label className='inline-flex items-center gap-2 text-sm font-semibold text-foreground'>
            <Sparkles className='h-4 w-4 text-muted-foreground/60' />
            回答补充说明
            <HelpTip content='给这个知识库补一段稳定说明。聊天时会优先参考它，适合写适用范围、口径约束或默认前提。' />
          </Label>
          <Switch
            checked={Boolean(persistentContext.enabled)}
            onCheckedChange={(checked) => updatePersistentContext({ enabled: checked })}
            aria-label='启用回答补充说明'
          />
        </div>
        <div className='space-y-3 rounded-lg border border-border bg-muted/10 p-4'>
          <p className='text-xs leading-relaxed text-muted-foreground'>
            让回答默认带上这份背景说明，适合写适用范围、统一口径或提醒事项。
          </p>

          <Textarea
            value={persistentContext.content || ''}
            onChange={(e) => updatePersistentContext({ content: e.target.value })}
            placeholder='例如：默认按中国区制度回答，金额统一按人民币理解。'
            rows={4}
            className='min-h-[112px] text-sm leading-relaxed'
            disabled={!persistentContext.enabled}
          />

          <div className='flex items-start justify-between gap-3 rounded-md border border-border/70 bg-background/70 px-3 py-3'>
            <div className='space-y-1'>
              <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                命中文档摘要补充
                <HelpTip content='当最终参考资料里命中文档时，可把该文档摘要一起带给模型，帮助回答更稳。默认关闭，避免旧摘要带来噪声。' />
              </div>
              <p className='text-xs leading-relaxed text-muted-foreground'>
                命中文档时，补一小段文档背景。
              </p>
            </div>
            <Switch
              checked={Boolean(persistentContext.enable_doc_summary_as_context)}
              onCheckedChange={(checked) => updatePersistentContext({ enable_doc_summary_as_context: checked })}
              aria-label='启用命中文档摘要补充'
              disabled={!persistentContext.enabled}
            />
          </div>

          <div className='flex items-start justify-between gap-3 rounded-md border border-border/70 bg-background/70 px-3 py-3'>
            <div className='space-y-1'>
              <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                文档摘要参与检索
                <HelpTip content='让文档摘要参与辅助检索，适合做粗粒度召回扩展。默认关闭，不会替代正文检索。' />
              </div>
              <p className='text-xs leading-relaxed text-muted-foreground'>
                让摘要补充召回，但正文仍然优先。
              </p>
            </div>
            <Switch
              checked={Boolean(persistentContext.enable_doc_summary_retrieval)}
              onCheckedChange={(checked) => updatePersistentContext({ enable_doc_summary_retrieval: checked })}
              aria-label='启用文档摘要参与检索'
            />
          </div>

          <div className='space-y-3 rounded-md border border-border/70 bg-background/70 px-3 py-3'>
            <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
              摘要质量门槛
              <HelpTip content='过滤太短、太空泛或明显占位的摘要，减少摘要辅路带来的噪声。' />
            </div>
            <div className='grid gap-3 md:grid-cols-2'>
              <div className='space-y-1.5'>
                <Label className='text-xs font-medium text-muted-foreground'>最少字符数</Label>
                <Input
                  type='number'
                  min={1}
                  value={String(persistentContext.doc_summary_min_chars ?? 24)}
                  onChange={(e) => updatePersistentContext({ doc_summary_min_chars: Number(e.target.value || 24) })}
                  className='h-9 text-sm'
                />
              </div>
              <div className='space-y-1.5'>
                <Label className='text-xs font-medium text-muted-foreground'>最少 Token</Label>
                <Input
                  type='number'
                  min={1}
                  value={String(persistentContext.doc_summary_min_tokens ?? 8)}
                  onChange={(e) => updatePersistentContext({ doc_summary_min_tokens: Number(e.target.value || 8) })}
                  className='h-9 text-sm'
                />
              </div>
              <div className='space-y-1.5'>
                <Label className='text-xs font-medium text-muted-foreground'>最大字符数</Label>
                <Input
                  type='number'
                  min={32}
                  value={String(persistentContext.doc_summary_max_chars ?? 1200)}
                  onChange={(e) => updatePersistentContext({ doc_summary_max_chars: Number(e.target.value || 1200) })}
                  className='h-9 text-sm'
                />
              </div>
              <div className='space-y-1.5'>
                <Label className='text-xs font-medium text-muted-foreground'>最少唯一词项</Label>
                <Input
                  type='number'
                  min={1}
                  value={String(persistentContext.doc_summary_min_unique_terms ?? 3)}
                  onChange={(e) => updatePersistentContext({ doc_summary_min_unique_terms: Number(e.target.value || 3) })}
                  className='h-9 text-sm'
                />
              </div>
            </div>
            <div className='space-y-1.5'>
              <Label className='text-xs font-medium text-muted-foreground'>忽略这些占位摘要</Label>
              <Textarea
                value={Array.isArray(persistentContext.doc_summary_excluded_phrases) ? persistentContext.doc_summary_excluded_phrases.join('\n') : ''}
                onChange={(e) =>
                  updatePersistentContext({
                    doc_summary_excluded_phrases: e.target.value
                      .split('\n')
                      .map((item) => item.trim())
                      .filter(Boolean),
                  })
                }
                placeholder={'每行一个，例如：\n暂无摘要\n待补充'}
                rows={4}
                className='text-sm leading-relaxed'
              />
            </div>
          </div>
        </div>
      </div>

      <div className='space-y-2'>
        <div className='flex items-center justify-between'>
          <Label className='inline-flex items-center gap-2 text-sm font-semibold text-foreground'>
            <Search className='h-4 w-4 text-muted-foreground/60' />
            检索理解
            <HelpTip content='控制检索前的查询理解过程，包括同义词归一化、规则型自动过滤，以及可识别的元数据字段。' />
          </Label>
        </div>
        <div className='space-y-3 rounded-lg border border-border bg-muted/10 p-4'>
          <div className='grid gap-3 md:grid-cols-2'>
            <div className='flex items-start justify-between gap-3 rounded-md border border-border/70 bg-background/70 px-3 py-3'>
              <div className='space-y-1'>
                <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                  查询改写
                  <HelpTip content='用独立的 LLM 查询改写器把问题补成更适合检索的 standalone query。聊天中可结合最近几轮对话；若知识库存在多级目录，还可顺带给出目录路径建议。' />
                </div>
                <p className='text-xs leading-relaxed text-muted-foreground'>
                  建议按需开启。没有多轮上下文且只有根目录时，系统会自动跳过改写。
                </p>
              </div>
              <Switch
                checked={Boolean(queryAnalysis.enable_query_rewrite)}
                onCheckedChange={(checked) => updateQueryAnalysis({ enable_query_rewrite: checked })}
                aria-label='启用查询改写'
              />
            </div>

            <div className='flex items-start justify-between gap-3 rounded-md border border-border/70 bg-background/70 px-3 py-3'>
              <div className='space-y-1'>
                <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                  同义词改写
                  <HelpTip content='位于查询改写之后，对 standalone query 再做术语归一化，提升口语词、简称和专业词的召回对齐。' />
                </div>
                <p className='text-xs leading-relaxed text-muted-foreground'>
                  推荐开启，作为查询改写后的第二步标准化。
                </p>
              </div>
              <Switch
                checked={Boolean(queryAnalysis.enable_synonym_rewrite)}
                onCheckedChange={(checked) => updateQueryAnalysis({ enable_synonym_rewrite: checked })}
                aria-label='启用同义词改写'
              />
            </div>

            <div className='space-y-2 rounded-md border border-border/70 bg-background/70 px-3 py-3'>
              <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                自动过滤抽取
                <HelpTip content='从问题中识别目录、标签、文档元数据或分块元数据候选。LLM 模式下，同一次模型调用除了返回 candidates，也可以顺带返回统一过滤表达式。' />
              </div>
              <Select
                value={String(queryAnalysis.auto_filter_mode || 'disabled')}
                onValueChange={(value) => updateQueryAnalysis({ auto_filter_mode: value })}
              >
                <SelectTrigger className='h-9 text-sm'>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='disabled'>关闭</SelectItem>
                  <SelectItem value='rule'>规则抽取</SelectItem>
                  <SelectItem value='llm_candidate'>LLM 候选</SelectItem>
                  <SelectItem value='hybrid'>规则 + LLM 候选</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {enableLlmAutoFilter ? (
              <div className='flex items-start justify-between gap-3 rounded-md border border-dashed border-border/70 bg-background/70 px-3 py-3'>
                <div className='space-y-1'>
                  <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                    LLM 统一过滤表达式
                    <HelpTip content='这是自动过滤抽取那一次 LLM 调用的附带输出，不会额外多调用一次模型。适合表达 OR、NOT、not_in、跨字段组合等复杂条件。' />
                  </div>
                  <p className='text-xs leading-relaxed text-muted-foreground'>
                    高级选项。关闭后，LLM 仍可输出候选，但不会把同次返回里的复杂表达式并入最终过滤。
                  </p>
                </div>
                <Switch
                  checked={queryAnalysis.enable_llm_filter_expression !== false}
                  onCheckedChange={(checked) => updateQueryAnalysis({ enable_llm_filter_expression: checked })}
                  aria-label='启用 LLM 统一过滤表达式'
                />
              </div>
            ) : null}
          </div>

          {enableLlmAutoFilter ? (
            <div className='space-y-3 rounded-md border border-border/70 bg-background/70 px-3 py-3'>
              <div className='space-y-1'>
                <div className='text-sm font-medium text-foreground'>自动过滤抽取 · LLM 候选校验</div>
                <p className='text-xs leading-relaxed text-muted-foreground'>
                  当前后端设计里，`llm_candidate` 主要负责产出并校验 LLM 候选；只有 `hybrid` 才允许高置信候选继续纠偏规则并升级为硬过滤。
                </p>
              </div>
              <div className='rounded-md border border-border/60 bg-background/80 px-3 py-3'>
                <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                  LLM 最小置信度
                  <HelpTip content='作用于自动过滤抽取这一次 LLM 返回的 candidates。低于该值的候选会在校验阶段直接被拒绝。' />
                </div>
                <div className='mt-2 max-w-[220px]'>
                  <Input
                    type='number'
                    min={0}
                    max={1}
                    step='0.01'
                    value={String(queryAnalysis.llm_candidate_min_confidence ?? 0.55)}
                    onChange={(e) => updateQueryAnalysis({ llm_candidate_min_confidence: Number(e.target.value || 0.55) })}
                    className='h-9 text-sm'
                  />
                </div>
              </div>
              {enableHybridUpgrade ? (
                <div className='space-y-3 rounded-md border border-dashed border-border/60 bg-background/80 px-3 py-3'>
                  <div className='space-y-1'>
                    <div className='text-sm font-medium text-foreground'>自动过滤抽取 · Hybrid 硬过滤升级</div>
                    <p className='text-xs leading-relaxed text-muted-foreground'>
                      仅 `hybrid` 模式生效。高置信 LLM 候选在这一层才允许纠偏规则候选，并进一步升级为最终硬过滤。
                    </p>
                  </div>
                  <div className='space-y-3'>
                    <div className='space-y-1.5'>
                      <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                        硬过滤升级阈值
                        <HelpTip content='只在 hybrid 模式下生效。达到该阈值的高置信 LLM 候选，才允许纠偏规则候选或升级成硬过滤。' />
                      </div>
                      <div className='max-w-[220px]'>
                        <Input
                          type='number'
                          min={0}
                          max={1}
                          step='0.01'
                          value={String(queryAnalysis.llm_upgrade_confidence_threshold ?? 0.82)}
                          onChange={(e) => updateQueryAnalysis({ llm_upgrade_confidence_threshold: Number(e.target.value || 0.82) })}
                          className='h-9 text-sm'
                        />
                      </div>
                    </div>
                    <div className='space-y-1.5'>
                      <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                        最大升级数量
                        <HelpTip content='只在 hybrid 模式下生效。限制本轮最多有多少个 LLM 候选可以升级成硬过滤，避免一次查询过度收窄。' />
                      </div>
                      <div className='max-w-[220px]'>
                        <Input
                          type='number'
                          min={0}
                          max={8}
                          value={String(queryAnalysis.llm_max_upgrade_count ?? 2)}
                          onChange={(e) => updateQueryAnalysis({ llm_max_upgrade_count: Number(e.target.value || 2) })}
                          className='h-9 text-sm'
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className='space-y-3 rounded-md border border-border/70 bg-background/70 p-3'>
            <div className='flex items-center justify-between gap-3'>
              <div className='space-y-1'>
                <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                  检索词条
                  <HelpTip content='配置高价值业务词和短语。词条会进入检索分词词典；别名和缩写用于命中用户问法后扩展到标准词。' />
                </div>
                <p className='text-xs leading-relaxed text-muted-foreground'>
                  适合写产品名、业务短语、英文缩写和容易被分错的固定表达。
                </p>
              </div>
              <Button type='button' variant='outline' size='sm' className='h-8 px-3 text-sm' onClick={addRetrievalLexiconItem}>
                新增词条
              </Button>
            </div>

            {retrievalLexicon.length > 0 ? (
              <div className='space-y-3'>
                {retrievalLexicon.map((item: any, index: number) => (
                  <div key={`retrieval-lexicon-${index}`} className='space-y-3 rounded-md border border-border/60 bg-muted/10 p-3'>
                    <div className='space-y-1.5'>
                      <Label className='text-xs font-medium text-muted-foreground'>标准词</Label>
                      <Input
                        value={String(item?.term || '')}
                        onChange={(e) => updateRetrievalLexiconItem(index, { term: e.target.value })}
                        placeholder='例如：净收入留存率'
                        className='h-9 text-sm'
                      />
                    </div>

                    <div className='grid gap-3 md:grid-cols-2'>
                      <div className='space-y-1.5'>
                        <Label className='text-xs font-medium text-muted-foreground'>别名 / 缩写</Label>
                        <Textarea
                          value={Array.isArray(item?.aliases) ? item.aliases.join('\n') : ''}
                          onChange={(e) =>
                            updateRetrievalLexiconItem(index, {
                              aliases: e.target.value
                                .split('\n')
                                .map((alias) => alias.trim())
                                .filter(Boolean),
                            })
                          }
                          placeholder={'可选，每行一个，例如：\nNRR\n净留存'}
                          rows={3}
                          className='text-sm leading-relaxed'
                        />
                        <p className='text-xs text-muted-foreground'>用户命中别名时会扩展到标准词；没有别名时直接新建另一个词条也可以。</p>
                      </div>
                      <div className='space-y-3'>
                        <div className='space-y-1.5'>
                          <div className='flex items-center justify-between'>
                            <Label className='text-xs font-medium text-muted-foreground'>检索权重</Label>
                            <span className='text-[10px] text-muted-foreground/80'>范围 0-2</span>
                          </div>
                          <Input
                            type='number'
                            min={0}
                            max={2}
                            step='0.1'
                            value={String(item?.weight ?? 1)}
                            onChange={(e) => {
                              const val = Number(e.target.value)
                              updateRetrievalLexiconItem(index, { weight: isNaN(val) ? 1 : val })
                            }}
                            className='h-9 text-sm'
                          />
                          <p className='text-[11px] text-muted-foreground/70'>
                            默认 1.0；0 为不加分，2 为最强加成。影响全文初筛排序。
                          </p>
                        </div>
                        <div className='flex items-center justify-between rounded-md border border-border/70 bg-background/70 px-3 py-2'>
                          <div className='space-y-0.5'>
                            <div className='text-sm font-medium text-foreground'>启用词条</div>
                            <div className='text-xs text-muted-foreground'>关闭后保留配置，但不参与检索增强。</div>
                          </div>
                          <Switch
                            checked={Boolean(item?.enabled ?? true)}
                            onCheckedChange={(checked) => updateRetrievalLexiconItem(index, { enabled: checked })}
                          />
                        </div>
                      </div>
                    </div>

                    <div className='flex justify-end'>
                      <Button type='button' variant='ghost' size='sm' className='h-8 px-3 text-sm text-destructive' onClick={() => removeRetrievalLexiconItem(index)}>
                        删除词条
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className='rounded-md border border-dashed border-border/70 bg-muted/10 px-3 py-4 text-xs leading-relaxed text-muted-foreground'>
                还没有检索词条。建议先补最重要的专业术语、英文缩写和业务短语。
              </div>
            )}
          </div>

          <div className='space-y-3 rounded-md border border-border/70 bg-background/70 p-3'>
            <div className='space-y-1'>
              <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                忽略词 / 低价值词
                <HelpTip content='把“介绍、说明、相关内容”这类高频但低信息的词先过滤掉，减少中文全文检索噪声。' />
              </div>
              <p className='text-xs leading-relaxed text-muted-foreground'>
                适合放泛词、套话和经常带来噪声的搜索词。每行一个。
              </p>
            </div>
            <Textarea
              value={retrievalStopwords.join('\n')}
              onChange={(e) =>
                updateQueryAnalysis({
                  retrieval_stopwords: e.target.value
                    .split('\n')
                    .map((item) => item.trim())
                    .filter(Boolean),
                })
              }
              rows={4}
              placeholder={'每行一个，例如：\n介绍\n说明\n相关内容'}
              className='text-sm leading-relaxed'
            />
          </div>

          <div className='space-y-3 rounded-md border border-border/70 bg-background/70 p-3'>
            <div className='flex items-center justify-between gap-3'>
              <div className='space-y-1'>
                <div className='inline-flex items-center gap-2 text-sm font-medium text-foreground'>
                  自动元数据识别字段
                  <HelpTip content='告诉系统哪些元数据字段允许从问题中识别。标签不在这里配置；这里仅负责文档元数据 / 分块元数据字段。建议只填有固定选项的字段。' />
                </div>
                <p className='text-xs leading-relaxed text-muted-foreground'>
                  适合枚举型字段，例如部门、年份、地区。
                </p>
              </div>
              <Button type='button' variant='outline' size='sm' className='h-8 px-3 text-sm' onClick={addMetadataField}>
                新增字段
              </Button>
            </div>

            {metadataFields.length > 0 ? (
              <div className='space-y-3'>
                {metadataFields.map((field: any, index: number) => (
                  <div key={`metadata-field-${index}`} className='space-y-3 rounded-md border border-border/60 bg-muted/10 p-3'>
                    <div className='grid gap-3 md:grid-cols-2'>
                      <div className='space-y-1.5'>
                        <Label className='text-xs font-medium text-muted-foreground'>字段 Key</Label>
                        <Input
                          value={String(field?.key || '')}
                          onChange={(e) => updateMetadataField(index, { key: e.target.value })}
                          placeholder='例如：department'
                          className='h-9 text-sm'
                        />
                      </div>
                      <div className='space-y-1.5'>
                        <Label className='text-xs font-medium text-muted-foreground'>显示名称</Label>
                        <Input
                          value={String(field?.name || '')}
                          onChange={(e) => updateMetadataField(index, { name: e.target.value })}
                          placeholder='例如：部门'
                          className='h-9 text-sm'
                        />
                      </div>
                    </div>

                    <div className='space-y-1.5'>
                      <Label className='text-xs font-medium text-muted-foreground'>字段别名</Label>
                      <Input
                        value={Array.isArray(field?.aliases) ? field.aliases.join(', ') : ''}
                        onChange={(e) =>
                          updateMetadataField(index, {
                            aliases: e.target.value
                              .split(',')
                              .map((item) => item.trim())
                              .filter(Boolean),
                          })
                        }
                        placeholder='例如：部门, 事业部'
                        className='h-9 text-sm'
                      />
                    </div>

                    <div className='grid gap-3 md:grid-cols-3'>
                      <div className='space-y-1.5'>
                        <Label className='text-xs font-medium text-muted-foreground'>过滤目标</Label>
                        <Select
                          value={String(field?.target || 'document_metadata')}
                          onValueChange={(value: MetadataTarget) => updateMetadataField(index, { target: value })}
                        >
                          <SelectTrigger className='h-9 text-sm'>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value='document_metadata'>文档元数据</SelectItem>
                            <SelectItem value='search_unit_metadata'>分块 / 行元数据</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className='space-y-1.5'>
                        <Label className='text-xs font-medium text-muted-foreground'>元数据路径</Label>
                        <Input
                          value={formatMetadataPath(field?.metadata_path)}
                          onChange={(e) => updateMetadataField(index, { metadata_path: parseMetadataPath(e.target.value) })}
                          placeholder='例如：filter_fields.region'
                          className='h-9 text-sm'
                        />
                      </div>
                      <div className='space-y-1.5'>
                        <Label className='text-xs font-medium text-muted-foreground'>自动过滤关系</Label>
                        <Select
                          value={String(field?.match_mode || 'match_or_missing')}
                          onValueChange={(value: MetadataMatchMode) => updateMetadataField(index, { match_mode: value })}
                        >
                          <SelectTrigger className='h-9 text-sm'>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value='match_or_missing'>匹配或缺失</SelectItem>
                            <SelectItem value='match_only'>必须匹配</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className='rounded-md border border-border/70 bg-background/70 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground'>
                      多个字段按 AND 组合；同一字段多值按 OR 组合。选择“匹配或缺失”时，已有该字段但值不匹配的文档会被排除，缺少该字段的通用文档仍可进入召回。
                    </div>

                    <div className='space-y-1.5'>
                      <Label className='text-xs font-medium text-muted-foreground'>可选值配置</Label>
                      <Textarea
                        value={formatMetadataOptions(
                          Array.isArray(field?.options) && field.options.length > 0
                            ? field.options
                            : Array.isArray(field?.enum_values)
                              ? field.enum_values
                              : []
                        )}
                        onChange={(e) =>
                          updateMetadataField(index, {
                            enum_values: normalizeMetadataOptions(e.target.value),
                            options: normalizeMetadataOptions(e.target.value),
                          })
                        }
                        rows={4}
                        placeholder='例如：研发, 销售, 财务'
                        className='min-h-[96px] text-sm'
                      />
                      <p className='text-[11px] leading-relaxed text-muted-foreground'>
                        一行一个值。高级写法：`显示名|实际值|别名1/别名2`
                      </p>
                    </div>

                    <div className='flex justify-end'>
                      <Button
                        type='button'
                        variant='ghost'
                        size='sm'
                        className='h-8 px-2 text-xs text-muted-foreground hover:text-destructive'
                        onClick={() => removeMetadataField(index)}
                      >
                        删除字段
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className='rounded-md border border-dashed border-border bg-muted/5 px-3 py-4 text-center text-sm text-muted-foreground'>
                当前未配置元数据识别字段
              </div>
            )}
          </div>

          <div className='rounded-lg border border-border bg-muted/10 p-4'>
            <div className='flex items-center gap-2 text-sm font-semibold text-foreground'>
              <FileSearch className='h-4 w-4 text-muted-foreground/60' />
              配置边界说明
            </div>
            <p className='mt-2 text-xs leading-relaxed text-muted-foreground'>
              这里配置的是知识库级的检索理解与回答补充逻辑，不改变文档存储结构，也不改变内容管理工作区中的解析、增强和高级索引设置。
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
