import { FileSearch, KeyRound, MessageSquarePlus } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'
import { DEFAULT_ENHANCEMENT_CONFIG, DEFAULT_INTELLIGENCE_CONFIG } from '@/features/knowledge-base/detail/components/shared-config/constants'

interface EnhancementPipelineSectionProps {
  config: ConfigState
  onConfigChange: (config: ConfigState) => void
}

export function EnhancementPipelineSection({
  config,
  onConfigChange,
}: EnhancementPipelineSectionProps) {
  const intelligenceConfig = config.intelligence_config || DEFAULT_INTELLIGENCE_CONFIG
  const enhancement = {
    ...DEFAULT_ENHANCEMENT_CONFIG,
    ...(intelligenceConfig.enhancement || {}),
  }
  const keywordConfig = {
    ...DEFAULT_ENHANCEMENT_CONFIG.keywords,
    ...(enhancement.keywords || {}),
  }
  const questionConfig = {
    ...DEFAULT_ENHANCEMENT_CONFIG.questions,
    ...(enhancement.questions || {}),
  }
  const summaryConfig = {
    ...DEFAULT_ENHANCEMENT_CONFIG.summary,
    ...(enhancement.summary || {}),
  }
  const keywordCount = keywordConfig.top_n ?? 0
  const isKeywordEnabled = Boolean(keywordConfig.enabled)

  const updateEnhancement = (patch: Partial<typeof enhancement>) => {
    onConfigChange({
      ...config,
      intelligence_config: {
        ...intelligenceConfig,
        enhancement: {
          ...enhancement,
          ...patch,
        },
      },
    })
  }

  return (
    <section className='space-y-4 text-left font-sans'>
      <div className='flex items-center gap-2'>
        <MessageSquarePlus className='h-4 w-4 text-primary' />
        <h3 className='text-sm font-semibold tracking-tight text-foreground'>智能增强</h3>
      </div>

      <div className='grid gap-4 rounded-xl border bg-card p-4 shadow-sm'>
        <div className='grid grid-cols-1 gap-3 xl:grid-cols-2'>
          <div className='flex items-center justify-between gap-3 rounded-lg border bg-muted/20 p-3 transition-colors hover:bg-muted/30'>
            <div className='flex min-w-0 items-center gap-2'>
              <FileSearch className='h-3.5 w-3.5 shrink-0 text-green-500' />
              <div className='min-w-0'>
                <span className='block text-xs font-medium leading-none'>分块摘要生成</span>
                <p className='mt-0.5 text-[10px] text-muted-foreground'>针对分块生成摘要，用于语义匹配与预览</p>
              </div>
            </div>
            <Switch
              checked={Boolean(summaryConfig.enabled)}
              onCheckedChange={(checked) =>
                updateEnhancement({
                  summary: {
                    ...summaryConfig,
                    enabled: checked,
                  },
                })}
              className='shrink-0 data-[state=checked]:bg-green-500'
            />
          </div>

          <div className='flex items-center justify-between gap-3 rounded-lg border bg-muted/20 p-3 transition-colors hover:bg-muted/30'>
            <div className='flex min-w-0 items-center gap-2'>
              <KeyRound className='h-3.5 w-3.5 shrink-0 text-amber-500' />
              <div className='min-w-0'>
                <span className='block text-xs font-medium leading-none'>分块关键词提取</span>
                <p className='mt-0.5 text-[10px] text-muted-foreground'>针对分块提取检索关键词，提升混合检索命中</p>
              </div>
            </div>
            <div className='flex shrink-0 items-center gap-2'>
              <Input
                type='number'
                min={1}
                max={20}
                value={String(isKeywordEnabled ? keywordCount : DEFAULT_ENHANCEMENT_CONFIG.keywords?.top_n ?? 5)}
                onChange={(e) =>
                  updateEnhancement({
                    keywords: {
                      ...keywordConfig,
                      top_n: Math.max(1, Math.min(20, Number(e.target.value) || 1)),
                    },
                  })}
                className='h-7 w-12 border-muted-foreground/20 px-2 text-xs'
                disabled={!isKeywordEnabled}
              />
              <span className='text-[10px] text-muted-foreground'>个</span>
              <Switch
                checked={isKeywordEnabled}
                onCheckedChange={(checked) =>
                  updateEnhancement({
                    keywords: {
                      ...keywordConfig,
                      enabled: checked,
                      top_n: checked
                        ? Math.max(1, keywordCount || DEFAULT_ENHANCEMENT_CONFIG.keywords?.top_n || 5)
                        : keywordConfig.top_n ?? DEFAULT_ENHANCEMENT_CONFIG.keywords?.top_n ?? 5,
                    },
                  })}
                className='shrink-0 data-[state=checked]:bg-amber-500'
              />
            </div>
          </div>

          <div className='flex items-center justify-between gap-3 rounded-lg border bg-muted/20 p-3 transition-colors hover:bg-muted/30'>
            <div className='flex min-w-0 items-center gap-2'>
              <MessageSquarePlus className='h-3.5 w-3.5 shrink-0 text-sky-500' />
              <div className='min-w-0'>
                <span className='block text-xs font-medium leading-none'>分块自动问题生成</span>
                <p className='mt-0.5 text-[10px] text-muted-foreground'>针对分块扩展问法，增强召回</p>
              </div>
            </div>
            <div className='flex shrink-0 items-center gap-2'>
              <Input
                type='number'
                min={1}
                max={20}
                value={String(questionConfig.top_n ?? DEFAULT_ENHANCEMENT_CONFIG.questions?.top_n ?? 3)}
                onChange={(e) =>
                  updateEnhancement({
                    questions: {
                      ...questionConfig,
                      top_n: Math.max(1, Math.min(20, Number(e.target.value) || 1)),
                    },
                  })}
                className='h-7 w-16 text-xs'
                disabled={!questionConfig.enabled}
              />
              <Switch
                checked={Boolean(questionConfig.enabled)}
                onCheckedChange={(checked) =>
                  updateEnhancement({
                    questions: {
                      ...questionConfig,
                      enabled: checked,
                    },
                  })}
                className='shrink-0'
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
