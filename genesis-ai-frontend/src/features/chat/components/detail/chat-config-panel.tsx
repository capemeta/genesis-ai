import type { ReactNode } from 'react'
import { useMemo, useState } from 'react'
import {
  Bot,
  Check,
  ChevronsUpDown,
  Database,
  ChevronDown,
  Plus,
  Save,
  Settings2,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { InlineHelpTip } from '@/features/chat/components/shared/inline-help-tip'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { KnowledgeBaseSelectorDialog } from '@/features/chat/components/detail/knowledge-base-selector-dialog'
import { KnowledgeBaseScopeCard } from '@/features/chat/components/detail/knowledge-base-scope-card'
import type {
  ChatBootstrapData,
  ChatConfigDraft,
  ChatSession,
} from '@/features/chat/types/chat'

interface ChatConfigPanelProps {
  bootstrap?: ChatBootstrapData
  session?: ChatSession
  draft: ChatConfigDraft
  onDraftChange: (updater: (current: ChatConfigDraft) => ChatConfigDraft) => void
  onSave: (draft: ChatConfigDraft) => Promise<void>
  hasUnsavedChanges?: boolean
  isSaving?: boolean
  className?: string
}

export function ChatConfigPanel({
  bootstrap,
  session,
  draft,
  onDraftChange,
  onSave,
  hasUnsavedChanges = false,
  isSaving = false,
  className,
}: ChatConfigPanelProps) {
  const [isKnowledgeBaseDialogOpen, setIsKnowledgeBaseDialogOpen] = useState(false)
  const [isModelPickerOpen, setIsModelPickerOpen] = useState(false)
  const [isRerankPickerOpen, setIsRerankPickerOpen] = useState(false)
  const [expandedKnowledgeBaseId, setExpandedKnowledgeBaseId] = useState<string | null>(null)
  const modelOptions = bootstrap?.models || []
  const rerankModelOptions = bootstrap?.rerank_models || []

  const selectedKnowledgeBases = useMemo(
    () =>
      draft.selectedKnowledgeBaseIds.map((id) => ({
        id,
        option: (bootstrap?.knowledge_bases || []).find((item) => item.id === id),
      })),
    [bootstrap?.knowledge_bases, draft.selectedKnowledgeBaseIds]
  )

  const groupedModelOptions = useMemo(
    () => groupOptionsByProvider(modelOptions),
    [modelOptions]
  )

  const groupedRerankOptions = useMemo(
    () => groupOptionsByProvider(rerankModelOptions),
    [rerankModelOptions]
  )

  const selectedModelLabel = useMemo(() => {
    if (!draft.defaultModelId) {
      return '使用系统默认'
    }
    return modelOptions.find((item) => item.id === draft.defaultModelId)?.name || '请选择模型'
  }, [draft.defaultModelId, modelOptions])

  const selectedRerankLabel = useMemo(() => {
    if (!draft.enableRerank) {
      return '未启用重排序'
    }
    if (!draft.rerankModelId) {
      return '请选择 rerank 模型'
    }
    return rerankModelOptions.find((item) => item.id === draft.rerankModelId)?.name || '请选择 rerank 模型'
  }, [draft.enableRerank, draft.rerankModelId, rerankModelOptions])

  const queryRewriteStatusMeta = useMemo(() => {
    switch (draft.queryRewriteMode) {
      case 'enabled':
        return { iconClassName: 'bg-sky-500/10 text-sky-600', statusLabel: '开启' }
      case 'disabled':
        return { iconClassName: 'bg-amber-500/10 text-amber-600', statusLabel: '关闭' }
      default:
        return { iconClassName: 'bg-muted text-muted-foreground/40', statusLabel: '继承知识库默认' }
    }
  }, [draft.queryRewriteMode])

  const enableLlmAutoFilter = draft.autoFilterMode === 'llm_candidate' || draft.autoFilterMode === 'hybrid'
  const enableHybridUpgrade = draft.autoFilterMode === 'hybrid'

  return (
    <aside className={cn('h-full w-full max-w-sm border-l bg-card/50 backdrop-blur-xl xl:flex xl:flex-col', className)}>
      <div className='border-b border-border/40 bg-muted/5 p-5'>
        <div className='flex items-center gap-2 text-base font-bold tracking-tight text-foreground/80'>
          <Settings2 className='h-4 w-4 text-blue-500' />
          会话配置
          <InlineHelpTip content='这里的模型、知识库和检索参数都只对当前会话生效，不会影响同一空间下的其他会话。' />
        </div>
      </div>

      <div className='flex-1 space-y-8 overflow-y-auto p-5 scrollbar-thin scrollbar-thumb-muted-foreground/10'>
        <section className='space-y-4'>
          <div className='flex items-center gap-1.5'>
            <div className='h-3 w-1 rounded-full bg-blue-500/50' />
            <Label className='mb-0 font-bold text-xs uppercase tracking-widest text-muted-foreground/60'>大模型</Label>
          </div>

          <ConfigPopoverPicker
            label='回答模型'
            tooltip='控制当前会话使用哪个聊天模型。'
            buttonLabel={selectedModelLabel}
            open={isModelPickerOpen}
            onOpenChange={setIsModelPickerOpen}
            emptyText='没有匹配的模型'
            groups={[
              {
                title: '系统默认',
                options: [{ id: '', name: '使用系统默认模型' }],
              },
              ...groupedModelOptions,
            ]}
            selectedId={draft.defaultModelId}
            onSelect={(id) => onDraftChange((current) => ({ ...current, defaultModelId: id }))}
          />

          <ConfigSlider
            label='创造性（温度）'
            tooltip='越高回答越多样，越低越稳定、可预期。'
            value={draft.temperature}
            min={0}
            max={1}
            step={0.1}
            formatValue={(value) => value.toFixed(1)}
            onChange={(value) => onDraftChange((current) => ({ ...current, temperature: value }))}
          />

          <details className='rounded-xl border border-border/40 bg-muted/10 p-4 shadow-sm'>
            <summary className='cursor-pointer list-none select-none [&::-webkit-details-marker]:hidden'>
              <div className='flex items-center justify-between gap-3 text-[11px] font-bold text-foreground/70'>
                <div className='flex items-center gap-2'>
                <Sparkles className='h-4 w-4 text-blue-500' />
                大模型高级参数
                </div>
                <ChevronDown className='h-4 w-4 text-muted-foreground/50 transition-transform duration-200 group-open:rotate-180' />
              </div>
            </summary>
            <div className='mt-4 space-y-4'>
              <ConfigSlider label='Top P' tooltip='控制采样概率质量范围。' value={draft.topP} min={0} max={1} step={0.05} formatValue={(value) => value.toFixed(2)} onChange={(value) => onDraftChange((current) => ({ ...current, topP: value }))} />
              <ConfigSlider label='Presence Penalty' tooltip='提高后会更倾向引入新话题。' value={draft.presencePenalty} min={-2} max={2} step={0.1} formatValue={(value) => value.toFixed(1)} onChange={(value) => onDraftChange((current) => ({ ...current, presencePenalty: value }))} />
              <ConfigSlider label='Frequency Penalty' tooltip='提高后会更抑制重复措辞。' value={draft.frequencyPenalty} min={-2} max={2} step={0.1} formatValue={(value) => value.toFixed(1)} onChange={(value) => onDraftChange((current) => ({ ...current, frequencyPenalty: value }))} />
              <div className='space-y-2 px-1'>
                <div className='flex items-center gap-1.5'>
                  <Label className='mb-0 text-[11px] font-bold text-foreground/60'>最大输出 Token</Label>
                  <InlineHelpTip content='限制回答最大长度。' />
                </div>
                <Input type='number' min={1} max={32768} value={draft.maxTokens} onChange={(event) => onDraftChange((current) => ({ ...current, maxTokens: Math.max(1, Math.round(Number(event.target.value || current.maxTokens))) }))} />
              </div>
              <div className='space-y-2 px-1'>
                <div className='flex items-center gap-1.5'>
                  <Label className='mb-0 text-[11px] font-bold text-foreground/60'>推理强度</Label>
                  <InlineHelpTip content='更高的推理强度通常更稳，但可能更慢。' />
                </div>
                <RadioGroup value={draft.reasoningEffort} onValueChange={(value) => onDraftChange((current) => ({ ...current, reasoningEffort: value === 'low' || value === 'high' ? value : 'medium' }))} className='grid grid-cols-3 gap-2'>
                  <RadioCard checked={draft.reasoningEffort === 'low'} value='low' title='低' />
                  <RadioCard checked={draft.reasoningEffort === 'medium'} value='medium' title='中' />
                  <RadioCard checked={draft.reasoningEffort === 'high'} value='high' title='高' />
                </RadioGroup>
              </div>
            </div>
          </details>

          <ConfigSwitch checked={draft.reasoningMode} title='深度思考模式' tooltip='需要更长推理链时可开启，但响应可能更慢。' iconClassName={draft.reasoningMode ? 'bg-blue-500/10 text-blue-500' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, reasoningMode: checked }))} icon={<Bot className='h-4 w-4' />} />
        </section>

        <section className='space-y-4'>
          <div className='flex items-center justify-between px-1'>
            <div className='flex items-center gap-1.5'>
              <div className='h-3 w-1 rounded-full bg-blue-500/50' />
              <Label className='font-bold text-xs uppercase tracking-widest text-muted-foreground/60'>资料库与范围</Label>
            </div>
            <div className='text-[10px] font-bold tabular-nums text-blue-500/40'>已选 {draft.selectedKnowledgeBaseIds.length}</div>
          </div>
          <div className='rounded-2xl border border-border/40 bg-muted/10 p-4 shadow-sm'>
            <div className='flex items-start justify-between gap-3'>
              <div className='space-y-1'>
                <div className='flex items-center gap-2 text-sm font-bold text-foreground/70'>
                  <Database className='h-4 w-4 shrink-0 text-blue-500/60' />
                  知识库挂载
                </div>
              </div>
              <Button variant='outline' size='sm' className='h-8 rounded-lg border-blue-500/20 bg-blue-500/5 text-[10px] font-bold text-blue-600 transition-all hover:border-blue-500/40 hover:bg-blue-500/10' onClick={() => setIsKnowledgeBaseDialogOpen(true)}>
                添加知识库
              </Button>
            </div>
            <div className='mt-4 flex flex-wrap gap-2'>
              {draft.selectedKnowledgeBaseIds.length > 0 ? (
                draft.selectedKnowledgeBaseIds.map((id) => {
                  const knowledgeBase = (bootstrap?.knowledge_bases || []).find((item) => item.id === id)
                  return (
                    <div key={id} className='inline-flex max-w-full items-center gap-1 rounded-lg border border-cyan-500/30 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 py-0.5 pl-2.5 pr-0.5 text-[10px] font-bold text-cyan-700 shadow-sm transition-colors hover:border-cyan-500/50 hover:from-cyan-500/15 hover:to-blue-500/15 dark:text-cyan-300'>
                      <span className='min-w-0 truncate text-cyan-700 dark:text-cyan-300' title={knowledgeBase?.name || id}>{knowledgeBase?.name || id}</span>
                      <Button type='button' variant='ghost' size='icon' className='h-6 w-6 shrink-0 text-muted-foreground/30 transition-colors hover:bg-destructive/5 hover:text-destructive' aria-label='移除该知识库' onClick={() => onDraftChange((current) => ({ ...current, selectedKnowledgeBaseIds: current.selectedKnowledgeBaseIds.filter((x) => x !== id), knowledgeBaseScopes: Object.fromEntries(Object.entries(current.knowledgeBaseScopes || {}).filter(([kbId]) => kbId !== id)) }))}>
                        <X className='h-3 w-3' />
                      </Button>
                    </div>
                  )
                })
              ) : (
                <div className='py-2 text-[10px] font-bold italic text-muted-foreground/30'>暂无挂载资料</div>
              )}
            </div>
            {selectedKnowledgeBases.length > 0 ? (
              <div className='mt-4 space-y-3 border-t border-dashed border-border/60 pt-4'>
                <div className='flex items-center gap-1.5 text-[11px] font-bold text-foreground/65'>
                  <span>检索范围</span>
                  <InlineHelpTip content='可按知识库分别限制本会话的检索范围。' />
                </div>
                {selectedKnowledgeBases.map(({ id, option }) => (
                  <KnowledgeBaseScopeCard
                    key={id}
                    kbId={id}
                    kbOption={option}
                    expanded={expandedKnowledgeBaseId === id}
                    scopeDraft={draft.knowledgeBaseScopes[id] || { kbDocIds: [], folderIds: [], folderTagIds: [], includeDescendantFolders: true, tagIds: [], metadata: {}, filterExpressionText: '' }}
                    onExpandedChange={(expanded) => {
                      setExpandedKnowledgeBaseId(expanded ? id : null)
                    }}
                    onChange={(nextScope) => onDraftChange((current) => ({ ...current, knowledgeBaseScopes: { ...(current.knowledgeBaseScopes || {}), [id]: nextScope } }))}
                  />
                ))}
              </div>
            ) : null}
          </div>
        </section>

        <section className='space-y-6'>
          <div className='flex items-center gap-1.5 px-1'>
            <div className='h-3 w-1 rounded-full bg-blue-500/50' />
            <Label className='font-bold text-xs uppercase tracking-widest text-muted-foreground/60'>检索基础</Label>
          </div>
          <ConfigSlider label='初步检索条数' tooltip='聊天主流程最终参与回答的候选规模。' value={draft.searchDepthK} min={1} max={20} step={1} formatValue={(value) => String(value)} onChange={(value) => onDraftChange((current) => ({ ...current, searchDepthK: value }))} />
          <ConfigSlider label='最终参考条数' tooltip='在候选结果中保留最相关的若干条参与生成回答。' value={draft.rerankTopN} min={1} max={50} step={1} formatValue={(value) => String(value)} onChange={(value) => onDraftChange((current) => ({ ...current, rerankTopN: value }))} />
          <ConfigSlider label='最低相关度' tooltip='低于该分数的片段会被弱化或不参与回答。' value={draft.minScore} min={0} max={1} step={0.05} formatValue={(value) => value.toFixed(2)} onChange={(value) => onDraftChange((current) => ({ ...current, minScore: value }))} />
          <ConfigSlider label='向量权重' tooltip='调高后更偏语义相似，调低后更偏关键词命中。' value={draft.vectorWeight} min={0} max={1} step={0.05} formatValue={(value) => value.toFixed(2)} onChange={(value) => onDraftChange((current) => ({ ...current, vectorWeight: value }))} />
          <ConfigSwitch checked={draft.enableRerank} title='启用重排序' tooltip='启用后会使用 rerank 模型或重排流程对候选结果做进一步排序。' iconClassName={draft.enableRerank ? 'bg-blue-500/10 text-blue-500' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, enableRerank: checked }))} icon={<Sparkles className='h-4 w-4' />} />
          <ConfigPopoverPicker label='Rerank 模型' tooltip='检索重排序使用的模型。' buttonLabel={selectedRerankLabel} open={isRerankPickerOpen} onOpenChange={setIsRerankPickerOpen} emptyText='没有匹配的 rerank 模型' groups={groupedRerankOptions} selectedId={draft.rerankModelId} disabled={!draft.enableRerank} onSelect={(id) => onDraftChange((current) => ({ ...current, rerankModelId: id }))} />
          <ConfigSwitch checked={draft.persistentContextEnabled} title='回答补充说明' tooltip='关闭后，本会话不再注入知识库或文档补充说明。' description='仅影响当前会话' iconClassName={draft.persistentContextEnabled ? 'bg-emerald-500/10 text-emerald-600' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, persistentContextEnabled: checked }))} icon={<Database className='h-4 w-4' />} />
        </section>

        <section className='space-y-4'>
          <div className='flex items-center gap-1.5 px-1'>
            <div className='h-3 w-1 rounded-full bg-blue-500/50' />
            <Label className='font-bold text-xs uppercase tracking-widest text-muted-foreground/60'>检索高级</Label>
          </div>

          <details className='rounded-xl border border-slate-200 bg-slate-50/70 p-4 shadow-sm' open>
            <summary className='cursor-pointer list-none select-none [&::-webkit-details-marker]:hidden'>
              <div className='flex items-center justify-between gap-3'>
                <div>
                  <div className='text-[11px] font-bold text-foreground/70'>召回阈值与候选池</div>
                  <div className='mt-1 text-[10px] text-muted-foreground/60'>控制向量/关键词的候选规模与基础过滤阈值</div>
                </div>
                <ChevronDown className='h-4 w-4 text-muted-foreground/50 transition-transform duration-200 group-open:rotate-180' />
              </div>
            </summary>
            <div className='mt-4 space-y-4'>
              <ConfigSlider label='向量相似度阈值' tooltip='低于该阈值的向量召回结果会被过滤。' value={draft.vectorSimilarityThreshold} min={0} max={1} step={0.05} formatValue={(value) => value.toFixed(2)} onChange={(value) => onDraftChange((current) => ({ ...current, vectorSimilarityThreshold: value }))} />
              <ConfigSlider label='关键词相关度阈值' tooltip='低于该阈值的全文检索结果会被过滤。' value={draft.keywordRelevanceThreshold} min={0} max={1} step={0.05} formatValue={(value) => value.toFixed(2)} onChange={(value) => onDraftChange((current) => ({ ...current, keywordRelevanceThreshold: value }))} />
              <ConfigSlider label='向量候选池' tooltip='向量召回先取多少条进入后续融合。' value={draft.vectorTopK} min={1} max={200} step={1} formatValue={(value) => String(value)} onChange={(value) => onDraftChange((current) => ({ ...current, vectorTopK: value }))} />
              <ConfigSlider label='关键词候选池' tooltip='全文检索先取多少条进入后续融合。' value={draft.keywordTopK} min={1} max={200} step={1} formatValue={(value) => String(value)} onChange={(value) => onDraftChange((current) => ({ ...current, keywordTopK: value }))} />
            </div>
          </details>

          <details className='rounded-xl border border-slate-200 bg-slate-50/70 p-4 shadow-sm'>
            <summary className='cursor-pointer list-none select-none [&::-webkit-details-marker]:hidden'>
              <div className='flex items-center justify-between gap-3'>
                <div>
                  <div className='text-[11px] font-bold text-foreground/70'>查询改写与术语处理</div>
                  <div className='mt-1 text-[10px] text-muted-foreground/60'>控制问题改写、同义词归一化和手动补充上下文</div>
                </div>
                <ChevronDown className='h-4 w-4 text-muted-foreground/50 transition-transform duration-200 group-open:rotate-180' />
              </div>
            </summary>
            <div className='mt-4 space-y-4'>
              <div className='rounded-xl border border-border/40 bg-background/60 p-4 shadow-sm'>
                <div className='flex items-start justify-between gap-3'>
                  <div className='flex items-start gap-2'>
                    <div className={cn('mt-0.5 rounded-lg p-1.5 transition-colors', queryRewriteStatusMeta.iconClassName)}>
                      <Database className='h-4 w-4' />
                    </div>
                    <div className='space-y-1'>
                      <div className='text-[11px] font-bold text-foreground/70'>查询改写</div>
                    </div>
                  </div>
                  <div className='rounded-full border border-border/40 bg-background/70 px-2.5 py-1 text-[10px] font-bold text-foreground/55'>
                    {queryRewriteStatusMeta.statusLabel}
                  </div>
                </div>
                <RadioGroup value={draft.queryRewriteMode} onValueChange={(value) => onDraftChange((current) => ({ ...current, queryRewriteMode: value === 'enabled' || value === 'disabled' || value === 'inherit' ? value : 'inherit' }))} className='mt-4 gap-2'>
                  <RadioCard checked={draft.queryRewriteMode === 'inherit'} value='inherit' title='继承知识库默认' />
                  <RadioCard checked={draft.queryRewriteMode === 'enabled'} value='enabled' title='开启' />
                  <RadioCard checked={draft.queryRewriteMode === 'disabled'} value='disabled' title='关闭' />
                </RadioGroup>
              </div>

              <ConfigSwitch checked={draft.synonymRewriteEnabled} title='同义词改写' tooltip='把简称、别名、近义说法扩成更适合检索的词项。' description='推荐默认开启' iconClassName={draft.synonymRewriteEnabled ? 'bg-cyan-500/10 text-cyan-600' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, synonymRewriteEnabled: checked }))} icon={<Database className='h-4 w-4' />} />

              <details className='rounded-lg border border-slate-200/70 bg-white/80 p-3'>
                <summary className='cursor-pointer list-none text-[11px] font-bold text-foreground/70 [&::-webkit-details-marker]:hidden'>
                  <div className='flex items-center justify-between gap-3'>
                    <span>查询改写上下文</span>
                    <ChevronDown className='h-4 w-4 text-muted-foreground/50 transition-transform duration-200 group-open:rotate-180' />
                  </div>
                </summary>
                <div className='mt-3 space-y-3'>
                  <div className='flex items-start justify-between gap-3'>
                    <div className='text-[11px] leading-5 text-muted-foreground'>可手动补充多轮上下文；会和当前会话最近几轮真实消息一起参与查询改写。</div>
                    <Button type='button' variant='outline' size='sm' className='h-8 px-2 text-[11px]' onClick={() => onDraftChange((current) => ({ ...current, queryRewriteContext: [...(current.queryRewriteContext || []), { role: (current.queryRewriteContext || []).length % 2 === 0 ? 'user' : 'assistant', content: '' }] }))}>
                      <Plus className='mr-1 h-3.5 w-3.5' />
                      添加一条
                    </Button>
                  </div>
                  {draft.queryRewriteContext.length > 0 ? draft.queryRewriteContext.map((item, index) => (
                    <div key={`rewrite-context-${index}`} className='rounded-lg border border-slate-200/80 bg-slate-50/70 p-3'>
                      <div className='flex items-center justify-between gap-3'>
                        <div className='flex items-center gap-2'>
                          <span className='rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700'>历史 {index + 1}</span>
                          <select value={item.role} className='h-8 rounded-md border border-input bg-background px-2 text-xs' onChange={(event) => onDraftChange((current) => ({ ...current, queryRewriteContext: current.queryRewriteContext.map((entry, currentIndex) => currentIndex === index ? { ...entry, role: event.target.value === 'assistant' ? 'assistant' : 'user' } : entry) }))}>
                            <option value='user'>用户</option>
                            <option value='assistant'>助手</option>
                          </select>
                        </div>
                        <Button type='button' variant='ghost' size='sm' className='h-8 px-2 text-[11px] text-muted-foreground' onClick={() => onDraftChange((current) => ({ ...current, queryRewriteContext: current.queryRewriteContext.filter((_, currentIndex) => currentIndex !== index) }))}>
                          <Trash2 className='mr-1 h-3.5 w-3.5' />
                          删除
                        </Button>
                      </div>
                      <Textarea value={item.content} onChange={(event) => onDraftChange((current) => ({ ...current, queryRewriteContext: current.queryRewriteContext.map((entry, currentIndex) => currentIndex === index ? { ...entry, content: event.target.value } : entry) }))} placeholder={item.role === 'user' ? '例如：那赣州的呢？' : '例如：上一轮助手回答的关键摘要'} rows={3} className='mt-3 min-h-[84px] resize-y text-sm leading-relaxed' />
                    </div>
                  )) : (
                    <div className='rounded-lg border border-dashed border-slate-200 bg-slate-50/40 px-3 py-4 text-[11px] leading-relaxed text-muted-foreground'>当前未设置手动上下文。此时只使用当前会话真实历史消息参与查询改写。</div>
                  )}
                </div>
              </details>
            </div>
          </details>

          <details className='rounded-xl border border-slate-200 bg-slate-50/70 p-4 shadow-sm'>
            <summary className='cursor-pointer list-none select-none [&::-webkit-details-marker]:hidden'>
              <div className='flex items-center justify-between gap-3'>
                <div>
                  <div className='text-[11px] font-bold text-foreground/70'>自动过滤抽取</div>
                  <div className='mt-1 text-[10px] text-muted-foreground/60'>从问题里自动识别目录、标签、元数据和复杂过滤表达式</div>
                </div>
                <ChevronDown className='h-4 w-4 text-muted-foreground/50 transition-transform duration-200 group-open:rotate-180' />
              </div>
            </summary>
            <div className='mt-4 space-y-4'>
              <div className='rounded-xl border border-border/40 bg-background/60 p-4 shadow-sm'>
                <div className='mb-3 text-[11px] font-bold text-foreground/70'>自动过滤模式</div>
                <RadioGroup value={draft.autoFilterMode} onValueChange={(value) => onDraftChange((current) => ({ ...current, autoFilterMode: value === 'rule' || value === 'llm_candidate' || value === 'hybrid' ? value : 'disabled' }))} className='gap-2'>
                  <RadioCard checked={draft.autoFilterMode === 'disabled'} value='disabled' title='关闭自动过滤' activeClassName='border-indigo-300 bg-indigo-50/80' />
                  <RadioCard checked={draft.autoFilterMode === 'rule'} value='rule' title='仅规则抽取' activeClassName='border-indigo-300 bg-indigo-50/80' />
                  <RadioCard checked={draft.autoFilterMode === 'llm_candidate'} value='llm_candidate' title='仅 LLM 候选' activeClassName='border-indigo-300 bg-indigo-50/80' />
                  <RadioCard checked={draft.autoFilterMode === 'hybrid'} value='hybrid' title='规则 + LLM 候选' activeClassName='border-indigo-300 bg-indigo-50/80' />
                </RadioGroup>
              </div>

              {enableLlmAutoFilter ? (
                <>
                  <ConfigSwitch checked={draft.enableLlmFilterExpression} title='LLM 统一过滤表达式' tooltip='LLM 在返回候选时可顺带产出复杂表达式。' iconClassName={draft.enableLlmFilterExpression ? 'bg-indigo-500/10 text-indigo-600' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, enableLlmFilterExpression: checked }))} icon={<Sparkles className='h-4 w-4' />} />
                  <div className='space-y-4 rounded-xl border border-border/40 bg-background/60 p-4 shadow-sm'>
                    <div className='text-[11px] font-bold text-foreground/70'>LLM 候选校验</div>
                    <ConfigSlider label='LLM 最小置信度' tooltip='低于该值的 LLM 候选会在校验阶段被拒绝。' value={draft.llmCandidateMinConfidence} min={0} max={1} step={0.01} formatValue={(value) => value.toFixed(2)} onChange={(value) => onDraftChange((current) => ({ ...current, llmCandidateMinConfidence: value }))} />
                    {enableHybridUpgrade ? (
                      <>
                        <ConfigSlider label='硬过滤升级阈值' tooltip='只在 hybrid 模式下生效。' value={draft.llmUpgradeConfidenceThreshold} min={0} max={1} step={0.01} formatValue={(value) => value.toFixed(2)} onChange={(value) => onDraftChange((current) => ({ ...current, llmUpgradeConfidenceThreshold: value }))} />
                        <ConfigSlider label='最大升级数量' tooltip='只在 hybrid 模式下生效。' value={draft.llmMaxUpgradeCount} min={1} max={8} step={1} formatValue={(value) => String(Math.round(value))} onChange={(value) => onDraftChange((current) => ({ ...current, llmMaxUpgradeCount: Math.round(value) }))} />
                      </>
                    ) : null}
                  </div>
                </>
              ) : null}
            </div>
          </details>

          <details className='rounded-xl border border-slate-200 bg-slate-50/70 p-4 shadow-sm'>
            <summary className='cursor-pointer list-none select-none [&::-webkit-details-marker]:hidden'>
              <div className='flex items-center justify-between gap-3'>
                <div>
                  <div className='text-[11px] font-bold text-foreground/70'>层级召回与结果聚合</div>
                  <div className='mt-1 text-[10px] text-muted-foreground/60'>控制父块、邻近块和按内容组收敛结果的策略</div>
                </div>
                <ChevronDown className='h-4 w-4 text-muted-foreground/50 transition-transform duration-200 group-open:rotate-180' />
              </div>
            </summary>
            <div className='mt-4 space-y-4'>
              <div className='rounded-xl border border-border/40 bg-background/60 p-4 shadow-sm'>
                <div className='mb-3 text-[11px] font-bold text-foreground/70'>层级召回模式</div>
                <RadioGroup value={draft.hierarchicalRetrievalMode} onValueChange={(value) => onDraftChange((current) => ({ ...current, hierarchicalRetrievalMode: value === 'leaf_only' || value === 'auto_merge' ? value : 'recursive' }))} className='gap-2'>
                  <RadioCard checked={draft.hierarchicalRetrievalMode === 'leaf_only'} value='leaf_only' title='仅叶子块' activeClassName='border-blue-300 bg-blue-50/80' />
                  <RadioCard checked={draft.hierarchicalRetrievalMode === 'recursive'} value='recursive' title='递归父上下文' activeClassName='border-blue-300 bg-blue-50/80' />
                  <RadioCard checked={draft.hierarchicalRetrievalMode === 'auto_merge'} value='auto_merge' title='自动父块合并' activeClassName='border-blue-300 bg-blue-50/80' />
                </RadioGroup>
              </div>
              <ConfigSlider label='邻近块补充' tooltip='为命中块额外补充前后相邻的内容块。' value={draft.neighborWindowSize} min={0} max={5} step={1} formatValue={(value) => String(value)} onChange={(value) => onDraftChange((current) => ({ ...current, neighborWindowSize: value }))} />
              <ConfigSwitch checked={draft.enableParentContext} title='补充父块上下文' tooltip='把命中块所在的父级上下文一并带回。' iconClassName={draft.enableParentContext ? 'bg-blue-500/10 text-blue-500' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, enableParentContext: checked }))} icon={<Database className='h-4 w-4' />} />
              <ConfigSwitch checked={draft.groupByContentGroup} title='按内容组聚合' tooltip='减少同一内容组的重复命中。' iconClassName={draft.groupByContentGroup ? 'bg-blue-500/10 text-blue-500' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, groupByContentGroup: checked }))} icon={<Database className='h-4 w-4' />} />
            </div>
          </details>

          <ConfigSwitch checked={draft.filterInheritanceEnabled} title='延续上一轮范围' tooltip='开启后，系统会判断当前问题是否要沿用上一轮检索范围。' description='仅影响当前会话' iconClassName={draft.filterInheritanceEnabled ? 'bg-violet-500/10 text-violet-600' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, filterInheritanceEnabled: checked }))} icon={<Database className='h-4 w-4' />} />
          <ConfigSwitch checked={draft.filterInheritanceEvaluationEnabled} title='评估范围延续收益' tooltip='额外对比延续与不延续的检索差异，用于调试观察。' description='仅影响当前会话，调试时建议开启' iconClassName={draft.filterInheritanceEvaluationEnabled ? 'bg-amber-500/10 text-amber-600' : 'bg-muted text-muted-foreground/40'} onCheckedChange={(checked) => onDraftChange((current) => ({ ...current, filterInheritanceEvaluationEnabled: checked }))} icon={<Database className='h-4 w-4' />} />
        </section>
      </div>

      <div className='border-t border-border/40 bg-muted/5 p-5'>
        {hasUnsavedChanges ? (
          <div className='mb-3 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-700'>
            <div className='flex items-center gap-2'>
              <span className='h-2 w-2 rounded-full bg-red-500' />
              <span className='font-semibold'>当前修改尚未保存</span>
            </div>
            <span className='text-red-600/80'>建议保存为会话默认</span>
          </div>
        ) : null}
        <Button className='h-10 w-full rounded-xl bg-blue-600 text-[11px] font-bold uppercase tracking-widest text-white shadow-lg shadow-blue-500/20 transition-all hover:translate-y-[-1px] hover:bg-blue-500 hover:shadow-blue-500/30 active:translate-y-[0.1px] disabled:opacity-50' onClick={() => onSave(draft)} disabled={!session || isSaving}>
          {isSaving ? (
            <div className='flex items-center gap-2'>
              <div className='h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white' />
              保存中...
            </div>
          ) : (
            <>
              {hasUnsavedChanges ? <span className='mr-2 inline-flex h-2 w-2 rounded-full bg-red-300' /> : null}
              <Save className='mr-2 h-3.5 w-3.5' />
              保存当前配置
            </>
          )}
        </Button>
      </div>

      <KnowledgeBaseSelectorDialog
        open={isKnowledgeBaseDialogOpen}
        excludeIds={draft.selectedKnowledgeBaseIds}
        onOpenChange={setIsKnowledgeBaseDialogOpen}
        onConfirm={(addedIds) => {
          onDraftChange((current) => ({
            ...current,
            selectedKnowledgeBaseIds: [...new Set([...current.selectedKnowledgeBaseIds, ...addedIds])],
            knowledgeBaseScopes: {
              ...(current.knowledgeBaseScopes || {}),
              ...Object.fromEntries(
                addedIds
                  .filter((id) => !current.knowledgeBaseScopes?.[id])
                  .map((id) => [
                    id,
                    {
                      kbDocIds: [],
                      folderIds: [],
                      folderTagIds: [],
                      includeDescendantFolders: true,
                      tagIds: [],
                      metadata: {},
                      filterExpressionText: '',
                    },
                  ])
              ),
            },
          }))
          setExpandedKnowledgeBaseId(null)
          setIsKnowledgeBaseDialogOpen(false)
        }}
      />
    </aside>
  )
}

function groupOptionsByProvider(options: Array<{ id: string; name: string; extra?: Record<string, any> }>) {
  const grouped = new Map<string, typeof options>()
  for (const option of options) {
    const providerName = (String(option.extra?.provider_display_name || option.extra?.provider_name || option.extra?.provider_code || '').trim() || '未分组厂商')
    const currentGroup = grouped.get(providerName) || []
    currentGroup.push(option)
    grouped.set(providerName, currentGroup)
  }
  return Array.from(grouped.entries()).map(([title, groupedOptions]) => ({
    title,
    options: groupedOptions,
  }))
}

function ConfigPopoverPicker(props: {
  label: string
  tooltip: string
  buttonLabel: string
  open: boolean
  onOpenChange: (open: boolean) => void
  emptyText: string
  groups: Array<{ title: string; options: Array<{ id: string; name: string }> }>
  selectedId: string
  onSelect: (id: string) => void
  disabled?: boolean
}) {
  return (
    <div className='space-y-2'>
      <div className='flex items-center gap-1.5 px-1'>
        <Label className='mb-0 text-[11px] font-bold text-foreground/60'>{props.label}</Label>
        <InlineHelpTip content={props.tooltip} />
      </div>
      <Popover open={props.open} onOpenChange={props.onOpenChange}>
        <PopoverTrigger asChild>
          <Button type='button' variant='outline' role='combobox' aria-expanded={props.open} disabled={props.disabled} className='w-full justify-between rounded-xl border-border/40 bg-muted/20 font-normal transition-colors hover:bg-muted/30'>
            <span className='truncate text-left'>{props.buttonLabel}</span>
            <ChevronsUpDown className='ml-2 h-4 w-4 shrink-0 opacity-50' />
          </Button>
        </PopoverTrigger>
        <PopoverContent className='w-[--radix-popover-trigger-width] rounded-xl border-border/60 p-0 shadow-xl'>
          <Command>
            <CommandInput placeholder={`搜索${props.label}`} />
            <CommandList>
              <CommandEmpty>{props.emptyText}</CommandEmpty>
              {props.groups.map((group) => (
                <CommandGroup key={group.title} heading={group.title}>
                  {group.options.map((option) => (
                    <CommandItem key={`${group.title}-${option.id || 'default'}`} value={`${option.name} ${group.title}`} onSelect={() => {
                      props.onSelect(option.id)
                      props.onOpenChange(false)
                    }}>
                      <Check className={cn('h-4 w-4', props.selectedId === option.id ? 'opacity-100' : 'opacity-0')} />
                      {option.name}
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  )
}

function ConfigSlider(props: {
  label: string
  tooltip: string
  value: number
  min: number
  max: number
  step: number
  formatValue: (value: number) => string
  onChange: (value: number) => void
}) {
  return (
    <div className='space-y-3 px-1'>
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-1.5'>
          <Label className='mb-0 text-[11px] font-bold text-foreground/60'>{props.label}</Label>
          <InlineHelpTip content={props.tooltip} />
        </div>
        <div className='text-[10px] font-black tabular-nums text-blue-500/60'>{props.formatValue(props.value)}</div>
      </div>
      <Slider value={[props.value]} min={props.min} max={props.max} step={props.step} className='[&_[role=slider]]:h-4 [&_[role=slider]]:w-4 [&_[role=slider]]:border-blue-500 [&_[role=slider]]:bg-background [&_.relative]:bg-blue-500/20 [&_.absolute]:bg-blue-500' onValueChange={(value) => props.onChange(value[0] ?? props.value)} />
    </div>
  )
}

function ConfigSwitch(props: {
  checked: boolean
  title: string
  tooltip: string
  description?: string
  iconClassName: string
  icon: ReactNode
  onCheckedChange: (checked: boolean) => void
}) {
  return (
    <div className='flex items-center justify-between rounded-xl border border-border/40 bg-muted/10 p-4 shadow-sm'>
      <div className='flex items-center gap-2'>
        <div className={cn('rounded-lg p-1.5 transition-colors', props.iconClassName)}>{props.icon}</div>
        <div className='space-y-0.5'>
          <div className='flex items-center gap-1.5'>
            <span className='text-[11px] font-bold text-foreground/70'>{props.title}</span>
            <InlineHelpTip content={props.tooltip} />
          </div>
          {props.description ? <div className='text-[10px] font-medium text-muted-foreground/40'>{props.description}</div> : null}
        </div>
      </div>
      <Switch checked={props.checked} onCheckedChange={props.onCheckedChange} />
    </div>
  )
}

function RadioCard(props: {
  checked: boolean
  value: string
  title: string
  activeClassName?: string
}) {
  return (
    <label className={cn('flex cursor-pointer items-start gap-3 rounded-lg border border-border/40 bg-background/60 px-3 py-2 transition-colors hover:bg-muted/40', props.checked ? props.activeClassName || 'border-sky-300 bg-sky-50/80' : '')}>
      <RadioGroupItem value={props.value} className='mt-0.5' />
      <div className='text-[11px] font-bold text-foreground/70'>{props.title}</div>
    </label>
  )
}
