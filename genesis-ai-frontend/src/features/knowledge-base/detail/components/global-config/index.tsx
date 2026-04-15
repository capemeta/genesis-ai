import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Info, Loader2, Save, Settings2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { fetchKnowledgeBase, getKnowledgeBaseTags, setKnowledgeBaseTags, updateKnowledgeBase, type KnowledgeBase, type KnowledgeBaseUpdate } from '@/lib/api/knowledge-base'
import { fetchModelSettingsOverview } from '@/lib/api/model-platform'
import { DEFAULT_CHUNKING_CONFIG, DEFAULT_ENHANCEMENT_CONFIG, DEFAULT_INTELLIGENCE_CONFIG, DEFAULT_TABLE_RETRIEVAL_CONFIG } from '@/features/knowledge-base/detail/components/shared-config/constants'
import { BasicInfoSection } from './basic-info-section'
import { ModelConfigSection } from './model-config-section'
import { RetrievalAnswerSection } from './retrieval-answer-section'
import type { ConfigState, KnowledgeBaseSettingsProps } from '@/features/knowledge-base/detail/components/shared-config/types'
import { useScopedTags } from '@/hooks/use-available-tags'

const EMPTY_TAGS: Awaited<ReturnType<typeof getKnowledgeBaseTags>>['tags'] = []

function formatApiErrorMessage(error: any): string {
  const data = error?.response?.data
  const baseMessage = data?.message ?? data?.detail ?? '保存失败，请重试'
  const detailMessages = Array.isArray(data?.details)
    ? data.details
      .map((item: any) => item?.msg ?? item?.message)
      .filter((item: unknown) => typeof item === 'string' && item)
    : []
  return detailMessages.length > 0 ? `${baseMessage}：${detailMessages.join('；')}` : baseMessage
}

function sanitizeRetrievalConfig(rawRetrievalConfig: Record<string, unknown>) {
  const nextRetrievalConfig = { ...rawRetrievalConfig }
  const rawQueryAnalysis = ((nextRetrievalConfig.query_analysis as Record<string, any> | undefined) || {})
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

  nextRetrievalConfig.query_analysis = nextQueryAnalysis
  return nextRetrievalConfig
}

/** 将后端 KB 数据标准化为可编辑配置，避免界面层重复判空。 */
function buildConfigFromKb(kb: KnowledgeBase): ConfigState {
  const { metadata_schema: _metadataSchema, ...retrievalConfigWithoutMetadataSchema } = kb.retrieval_config || {}
  const intelligenceConfig = kb.intelligence_config || {}
  const persistentContextConfig = {
    enabled: false,
    content: '',
    enable_doc_summary_as_context: false,
    enable_doc_summary_retrieval: false,
    ...((retrievalConfigWithoutMetadataSchema as any).persistent_context || {}),
  }
  const tableRetrievalConfig = kb.type === 'table'
    ? {
      ...retrievalConfigWithoutMetadataSchema,
      persistent_context: persistentContextConfig,
      table: {
        ...DEFAULT_TABLE_RETRIEVAL_CONFIG,
        ...(retrievalConfigWithoutMetadataSchema.table || {}),
      },
    }
    : {
      ...retrievalConfigWithoutMetadataSchema,
      persistent_context: persistentContextConfig,
    }

  const tableChunkingConfig = kb.type === 'table'
    ? {
      ...DEFAULT_CHUNKING_CONFIG,
      ...(kb.chunking_config ?? DEFAULT_CHUNKING_CONFIG),
      chunk_strategy: 'excel_table' as const,
      max_embed_tokens: kb.chunking_config?.max_embed_tokens ?? 512,
      token_count_method: 'tokenizer' as const,
      enable_summary_chunk: true,
    }
    : {
      ...DEFAULT_CHUNKING_CONFIG,
      ...(kb.chunking_config ?? {}),
      pdf_chunk_strategy: 'markdown' as const,
    }

  return {
    type: kb.type,
    name: kb.name,
    description: kb.description,
    visibility: kb.visibility,
    embedding_model: kb.embedding_model,
    embedding_model_id: kb.embedding_model_id,
    chunking_mode: kb.chunking_mode ?? 'smart',
    chunking_config: tableChunkingConfig,
    index_model: kb.index_model,
    index_model_id: kb.index_model_id,
    vision_model: kb.vision_model,
    vision_model_id: kb.vision_model_id,
    retrieval_config: tableRetrievalConfig,
    intelligence_config: {
      ...DEFAULT_INTELLIGENCE_CONFIG,
      ...intelligenceConfig,
      enhancement: {
        ...DEFAULT_ENHANCEMENT_CONFIG,
        ...(intelligenceConfig.enhancement || {}),
      },
      knowledge_graph: {
        ...DEFAULT_INTELLIGENCE_CONFIG.knowledge_graph,
        ...(intelligenceConfig.knowledge_graph || {}),
      },
      raptor: {
        ...DEFAULT_INTELLIGENCE_CONFIG.raptor,
        ...(intelligenceConfig.raptor || {}),
      },
    },
    pdf_parser_config: kb.pdf_parser_config ?? {
      parser: 'native',
      enable_ocr: true,
      ocr_engine: 'tesseract',
      ocr_languages: ['ch', 'en'],
      extract_images: true,
      extract_tables: true,
    },
  }
}

interface KnowledgeBaseSettingsEditorProps {
  kbId: string
  kb: KnowledgeBase
  onOpenTagManagement: () => void
}

function KnowledgeBaseSettingsEditor({ kbId, kb, onOpenTagManagement }: KnowledgeBaseSettingsEditorProps) {
  const queryClient = useQueryClient()
  const [config, setConfig] = useState<ConfigState>(() => buildConfigFromKb(kb))
  const [tagSearch, setTagSearch] = useState('')
  // 保存当前选中的 Tab，避免保存后跳回默认 tab
  const [activeTab, setActiveTab] = useState<'basic' | 'retrieval' | 'model'>('basic')
  const [currentKbId, setCurrentKbId] = useState(kbId)

  // 当知识库切换时，重置配置和状态
  useEffect(() => {
    if (kbId !== currentKbId) {
      setCurrentKbId(kbId)
      setConfig(buildConfigFromKb(kb))
      setActiveTab('basic')
    }
  }, [kbId, kb, currentKbId])
  const { data: currentTagsData } = useQuery({
    queryKey: ['kb-tags', kbId],
    queryFn: async () => (await getKnowledgeBaseTags(kbId)).tags,
    enabled: !!kbId,
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
  })
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([])
  const { data: modelOverview } = useQuery({
    queryKey: ['model-platform-settings-overview'],
    queryFn: fetchModelSettingsOverview,
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
  })
  const currentTags = currentTagsData ?? EMPTY_TAGS
  const { data: scopedTags = [] } = useScopedTags(kbId, {
    includeGlobal: true,
    includeKb: true,
    targetType: 'kb',
    enabled: !!kbId,
  })

  useEffect(() => {
    const nextTagIds = currentTags.map((tag) => tag.id)
    setSelectedTagIds((prev) => {
      if (
        prev.length === nextTagIds.length &&
        prev.every((tagId, index) => tagId === nextTagIds[index])
      ) {
        return prev
      }
      return nextTagIds
    })
  }, [currentTags])

  const { mutate: updateKB, isPending } = useMutation({
    mutationFn: async () => {
      const normalizedChunkingConfig = kb.type === 'table'
        ? {
          ...config.chunking_config,
          chunk_strategy: 'excel_table' as any,
        }
        : {
          ...config.chunking_config,
          pdf_chunk_strategy: 'markdown' as const,
        }

      const { metadata_schema: _metadataSchema, ...normalizedRetrievalConfig } =
        (config.retrieval_config || {}) as Record<string, unknown>
      const sanitizedRetrievalConfig = sanitizeRetrievalConfig(normalizedRetrievalConfig)
      const payload: KnowledgeBaseUpdate = {
        ...config,
        name: config.name,
        description: config.description,
        visibility: config.visibility,
        embedding_model: config.embedding_model,
        embedding_model_id: config.embedding_model_id,
        chunking_mode: config.chunking_mode,
        chunking_config: normalizedChunkingConfig as any,
        index_model: config.index_model,
        index_model_id: config.index_model_id,
        vision_model: config.vision_model,
        vision_model_id: config.vision_model_id,
        retrieval_config: sanitizedRetrievalConfig,
        intelligence_config: config.intelligence_config,
      }
      // PDF 解析配置仅对通用文档类型生效，避免在其他类型中写入无关配置。
      if (kb.type === 'general') {
        payload.pdf_parser_config = config.pdf_parser_config
      }
      const updatedKb = await updateKnowledgeBase(kbId, payload)
      await setKnowledgeBaseTags(kbId, selectedTagIds)
      return updatedKb
    },
    onSuccess: () => {
      toast.success('配置已保存')
      queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] })
      queryClient.invalidateQueries({ queryKey: ['kb-tags', kbId] })
      queryClient.invalidateQueries({ queryKey: ['tags', 'scoped', kbId] })
    },
    onError: (error: any) => {
      toast.error(formatApiErrorMessage(error))
    },
  })

  return (
    <div className='flex h-full min-h-0 flex-col bg-background'>
      {/* 顶部标题栏 */}
      <div className='sticky top-0 z-10 flex items-center justify-between border-b bg-background/95 px-6 py-3 backdrop-blur-sm'>
        <div className='flex items-center gap-2'>
          <div className='flex h-7 w-7 items-center justify-center rounded-md bg-blue-100 text-blue-600'>
            <Settings2 className='h-3.5 w-3.5' />
          </div>
          <h2 className='text-base font-semibold text-blue-700'>知识库设置</h2>
        </div>
        <Button
          onClick={() => updateKB()}
          disabled={isPending}
          size='sm'
          className='bg-blue-600 hover:bg-blue-700 text-white'
        >
          {isPending ? <Loader2 className='h-3.5 w-3.5 animate-spin' /> : <Save className='h-3.5 w-3.5' />}
          保存配置
        </Button>
      </div>

      <div className='flex-1 overflow-y-auto'>
        <div className='mx-auto max-w-3xl px-6 py-6 space-y-5'>
          {/* 提示条 */}
          <div className='flex items-start gap-3 rounded-lg border border-amber-200/80 bg-amber-50/60 px-4 py-3 dark:border-amber-800/40 dark:bg-amber-950/20'>
            <Info className='mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400' />
            <p className='text-sm leading-relaxed text-amber-800/90 dark:text-amber-300/80'>
               知识库级设置，修改后需点击<span className='mx-1 font-semibold'>保存配置</span>方可生效。
            </p>
          </div>

          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'basic' | 'retrieval' | 'model')} className='w-full'>
            {/* Tab 切换栏 - 浅灰背景，非黑色 */}
            <TabsList className='h-10 w-full rounded-xl bg-slate-100 p-1 mb-0 dark:bg-muted/50'>
              <TabsTrigger
                value='basic'
                className='flex-1 rounded-lg text-sm font-medium text-slate-500 transition-all
                  data-[state=active]:bg-white data-[state=active]:text-slate-800
                  data-[state=active]:shadow-sm
                  dark:text-muted-foreground
                  dark:data-[state=active]:bg-background dark:data-[state=active]:text-foreground'
              >
                基础设置
              </TabsTrigger>
              <TabsTrigger
                value='model'
                className='flex-1 rounded-lg text-sm font-medium text-slate-500 transition-all
                  data-[state=active]:bg-white data-[state=active]:text-slate-800
                  data-[state=active]:shadow-sm
                  dark:text-muted-foreground
                  dark:data-[state=active]:bg-background dark:data-[state=active]:text-foreground'
              >
                模型配置
              </TabsTrigger>
              <TabsTrigger
                value='retrieval'
                className='flex-1 rounded-lg text-sm font-medium text-slate-500 transition-all
                  data-[state=active]:bg-white data-[state=active]:text-slate-800
                  data-[state=active]:shadow-sm
                  dark:text-muted-foreground
                  dark:data-[state=active]:bg-background dark:data-[state=active]:text-foreground'
              >
                检索与回答
              </TabsTrigger>
            </TabsList>

            {/* Tab 内容区 - 白色卡片背景 + 圆角 + 阴影 */}
            <TabsContent
              value='basic'
              className='mt-0 focus-visible:outline-none rounded-b-xl rounded-tr-xl border border-slate-200 bg-white px-5 py-6 shadow-sm dark:border-border dark:bg-card'
            >
              <BasicInfoSection
                config={config}
                onConfigChange={setConfig}
                kbTags={scopedTags}
                selectedTagIds={selectedTagIds}
                tagSearch={tagSearch}
                onTagSearchChange={setTagSearch}
                onTagIdsChange={setSelectedTagIds}
                onOpenTagManagement={onOpenTagManagement}
              />
            </TabsContent>

            <TabsContent
              value='retrieval'
              className='mt-0 focus-visible:outline-none rounded-b-xl rounded-tr-xl border border-slate-200 bg-white px-5 py-6 shadow-sm dark:border-border dark:bg-card'
            >
              <RetrievalAnswerSection config={config} onConfigChange={setConfig} />
            </TabsContent>

            <TabsContent
              value='model'
              className='mt-0 focus-visible:outline-none rounded-b-xl rounded-tr-xl border border-slate-200 bg-white px-5 py-6 shadow-sm dark:border-border dark:bg-card'
            >
              <ModelConfigSection config={config} onConfigChange={setConfig} modelOverview={modelOverview} />
            </TabsContent>
          </Tabs>

        </div>
      </div>
    </div>
  )
}

export function KnowledgeBaseSettings({
  kbId,
  focusArea: _focusArea,
  onOpenTagManagement,
}: KnowledgeBaseSettingsProps) {
  const { data: kb, isLoading } = useQuery({
    queryKey: ['knowledge-base', kbId],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: !!kbId,
  })

  if (isLoading) {
    return (
      <div className='flex h-full flex-col items-center justify-center gap-4'>
        <Loader2 className='h-8 w-8 animate-spin text-primary' />
        <p className='animate-pulse text-base text-muted-foreground'>正在获取知识库设置...</p>
      </div>
    )
  }

  if (!kb) {
    return (
      <div className='flex h-full items-center justify-center text-sm text-muted-foreground'>
        未获取到知识库配置
      </div>
    )
  }

  // 仅用 kbId 作为 key，知识库切换时重建编辑器
  return (
    <KnowledgeBaseSettingsEditor
      key={kbId}
      kbId={kbId}
      kb={kb}
      onOpenTagManagement={onOpenTagManagement || (() => {})}
    />
  )
}
