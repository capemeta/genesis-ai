import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { fetchKnowledgeBase, updateKnowledgeBase } from '@/lib/api/knowledge-base'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'
import {
  DEFAULT_ENHANCEMENT_CONFIG,
  DEFAULT_INTELLIGENCE_CONFIG,
  DEFAULT_KNOWLEDGE_GRAPH_CONFIG,
  DEFAULT_RAPTOR_CONFIG,
} from '@/features/knowledge-base/detail/components/shared-config/constants'
import { EnhancementPipelineSection } from './components/enhancement-pipeline-section'
import { KnowledgeGraphSection } from './components/knowledge-graph-section'
import { RaptorConfigSection } from './components/raptor-config-section'

interface AdvancedConfigWorkbenchProps {
  kbId: string
}

function buildAdvancedConfigState(kb: any): ConfigState {
  const intelligenceConfig = kb.intelligence_config || {}
  return {
    type: kb.type,
    intelligence_config: {
      ...DEFAULT_INTELLIGENCE_CONFIG,
      ...intelligenceConfig,
      enhancement: {
        ...DEFAULT_ENHANCEMENT_CONFIG,
        ...(intelligenceConfig.enhancement || {}),
      },
      knowledge_graph: {
        ...DEFAULT_KNOWLEDGE_GRAPH_CONFIG,
        ...(intelligenceConfig.knowledge_graph || {}),
      },
      raptor: {
        ...DEFAULT_RAPTOR_CONFIG,
        ...(intelligenceConfig.raptor || {}),
      },
    },
  }
}

export function AdvancedConfigWorkbench({ kbId }: AdvancedConfigWorkbenchProps) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'enhancement' | 'advanced-index'>('enhancement')
  const { data: kb, isLoading } = useQuery({
    queryKey: ['knowledge-base', kbId, 'advanced-config-workbench'],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: !!kbId,
    staleTime: 10_000,
  })
  const [draftConfig, setDraftConfig] = useState<ConfigState | null>(null)

  const config = useMemo(() => {
    if (draftConfig) return draftConfig
    if (!kb) return null
    return buildAdvancedConfigState(kb)
  }, [draftConfig, kb])

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!config) return null
      return updateKnowledgeBase(kbId, {
        intelligence_config: config.intelligence_config,
      })
    },
    onSuccess: async () => {
      toast.success(activeTab === 'enhancement' ? '增强配置已保存' : '高级索引已保存')
      setDraftConfig(null)
      await queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] })
    },
  })

  if (isLoading || !config) {
    return (
      <div className='flex h-full items-center justify-center gap-2 text-sm text-muted-foreground'>
        <Loader2 className='h-4 w-4 animate-spin' />
        加载高级配置中...
      </div>
    )
  }

  return (
    <div className='flex h-full min-h-0 flex-col bg-background'>
      <div className='border-b px-6 py-3'>
        <div className='flex items-start justify-between gap-4'>
          <div className='space-y-2'>
            <div className='flex items-center gap-2'>
              <Sparkles className='h-4 w-4 text-primary' />
              <h2 className='text-lg font-semibold text-foreground'>高级配置</h2>
            </div>
          </div>
          <div className='flex items-center gap-2'>
            <Button
              variant='outline'
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? (
                <Loader2 className='mr-2 h-4 w-4 animate-spin' />
              ) : (
                <Save className='mr-2 h-4 w-4' />
              )}
              保存当前配置
            </Button>
          </div>
        </div>
      </div>

      <div className='min-h-0 flex-1 overflow-y-auto px-6 py-5'>
        <div className='mx-auto max-w-[1080px]'>
          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'enhancement' | 'advanced-index')} className='space-y-5'>
            <TabsList className='grid h-10 w-full max-w-[360px] grid-cols-2 rounded-xl bg-slate-100 p-1 dark:bg-muted/50'>
              <TabsTrigger value='enhancement' className='rounded-lg text-sm font-medium'>
                增强配置
              </TabsTrigger>
              <TabsTrigger value='advanced-index' className='rounded-lg text-sm font-medium'>
                高级索引
              </TabsTrigger>
            </TabsList>

            <TabsContent value='enhancement' className='mt-0 focus-visible:outline-none'>
              <div className='space-y-8'>
                <EnhancementPipelineSection config={config} onConfigChange={setDraftConfig} />
              </div>
            </TabsContent>

            <TabsContent value='advanced-index' className='mt-0 focus-visible:outline-none'>
              <div className='space-y-8 rounded-2xl border bg-card/60 p-5'>
                <KnowledgeGraphSection config={config} onConfigChange={setDraftConfig} />
                <RaptorConfigSection config={config} onConfigChange={setDraftConfig} />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
