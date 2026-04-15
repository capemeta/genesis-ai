import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Bug, Check, ChevronsUpDown, Clipboard, Loader2, Play, RefreshCw, Volume2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import {
  invokeModelDebugRequest,
  previewModelRuntimeProfile,
  type CapabilityType,
  type ModelDebugInvokeRequest,
  type ModelSettingsProvider,
} from '@/lib/api/model-platform'
import { capabilityMeta } from '../../constants'
import { getErrorMessage } from '../../utils'

type ModelDebugPanelProps = {
  selectedProvider: ModelSettingsProvider
}

const DEBUG_CAPABILITIES: CapabilityType[] = ['chat', 'embedding', 'rerank', 'asr', 'tts']

/**
 * 轻量调试面板：优先解决“最终走哪条路”和“能不能发一条最小请求”。
 */
export function ModelDebugPanel({ selectedProvider }: ModelDebugPanelProps) {
  const isProviderReadyForDebug = Boolean(
    selectedProvider.tenant_provider_id && selectedProvider.is_enabled && selectedProvider.is_configured
  )
  const allCandidateModels = useMemo(
    () =>
      selectedProvider.models.filter(
        (model) => model.is_enabled && model.capabilities.some((capability) => DEBUG_CAPABILITIES.includes(capability))
      ),
    [selectedProvider.models]
  )

  const [selectedCapability, setSelectedCapability] = useState<CapabilityType | ''>('')
  const [selectedModelId, setSelectedModelId] = useState<string>(allCandidateModels[0]?.tenant_model_id ?? '')
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false)
  const [prompt, setPrompt] = useState('你好，请用一句话介绍你自己。')
  const [query, setQuery] = useState('什么是文本排序模型')
  const [documentsText, setDocumentsText] = useState(
    '文本排序模型广泛用于搜索引擎和推荐系统中。\n量子计算是计算科学的一个前沿领域。\n预训练语言模型推动了文本排序模型的发展。'
  )
  const [audioUrl, setAudioUrl] = useState('')
  const [voice, setVoice] = useState('alloy')

  const providerCapabilityOptions = useMemo(
    () =>
      Array.from(
        new Set(
          allCandidateModels.flatMap((model) => model.capabilities.filter((capability) => DEBUG_CAPABILITIES.includes(capability)))
        )
      ) as CapabilityType[],
    [allCandidateModels]
  )

  const effectiveSelectedCapability =
    selectedCapability && providerCapabilityOptions.includes(selectedCapability)
      ? selectedCapability
      : providerCapabilityOptions[0] ?? ''

  const candidateModels = useMemo(
    () =>
      effectiveSelectedCapability
        ? allCandidateModels.filter((model) => model.capabilities.includes(effectiveSelectedCapability))
        : allCandidateModels,
    [allCandidateModels, effectiveSelectedCapability]
  )

  const effectiveSelectedModel = useMemo(
    () => candidateModels.find((model) => model.tenant_model_id === selectedModelId) ?? candidateModels[0] ?? null,
    [candidateModels, selectedModelId]
  )

  const previewMutation = useMutation({
    mutationFn: previewModelRuntimeProfile,
    onError: (error) => {
      toast.error(getErrorMessage(error, '运行时画像预览失败'))
    },
  })

  const invokeMutation = useMutation({
    mutationFn: invokeModelDebugRequest,
    onError: (error) => {
      toast.error(getErrorMessage(error, '最小调试调用失败'))
    },
  })

  const handlePreview = () => {
    if (!isProviderReadyForDebug) {
      toast.info('请先确保厂商已保存、已启用且配置完整，再进行模型调试')
      return
    }
    if (!effectiveSelectedModel || !effectiveSelectedCapability) {
      toast.info('请先选择模型和能力')
      return
    }
    previewMutation.mutate({
      tenant_model_id: effectiveSelectedModel.tenant_model_id,
      capability_type: effectiveSelectedCapability,
    })
  }

  const handleInvoke = () => {
    if (!isProviderReadyForDebug) {
      toast.info('请先确保厂商已保存、已启用且配置完整，再进行模型调试')
      return
    }
    if (!effectiveSelectedModel || !effectiveSelectedCapability) {
      toast.info('请先选择模型和能力')
      return
    }
    const payload: ModelDebugInvokeRequest = {
      tenant_model_id: effectiveSelectedModel.tenant_model_id,
      capability_type: effectiveSelectedCapability,
    }
    if (effectiveSelectedCapability === 'chat' || effectiveSelectedCapability === 'embedding' || effectiveSelectedCapability === 'tts') {
      payload.prompt = prompt
    }
    if (effectiveSelectedCapability === 'tts') {
      payload.voice = voice
    }
    if (effectiveSelectedCapability === 'rerank') {
      payload.query = query
      payload.documents = documentsText
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean)
    }
    if (effectiveSelectedCapability === 'asr') {
      payload.audio_url = audioUrl.trim()
      payload.prompt = prompt.trim() || undefined
    }
    invokeMutation.mutate(payload)
  }

  const latestProfile = invokeMutation.data?.profile ?? previewMutation.data ?? null
  const latestResult = invokeMutation.data?.result ?? null
  const latestTtsAudioUrl = useMemo(() => {
    if (effectiveSelectedCapability !== 'tts') return null
    const audioBase64 = typeof latestResult?.audio_base64 === 'string' ? latestResult.audio_base64 : ''
    const contentType = typeof latestResult?.content_type === 'string' ? latestResult.content_type : 'audio/mpeg'
    if (!audioBase64) return null
    return `data:${contentType};base64,${audioBase64}`
  }, [effectiveSelectedCapability, latestResult])

  const handleCopyAsrText = async () => {
    const text = typeof latestResult?.text === 'string' ? latestResult.text : ''
    if (!text) {
      toast.info('当前没有可复制的识别文本')
      return
    }
    await navigator.clipboard.writeText(text)
    toast.success('识别文本已复制')
  }

  const executionAdapterType =
    typeof latestResult?.adapter_type === 'string' ? latestResult.adapter_type : null
  const plannedAdapterTypeFromResult =
    typeof latestResult?.planned_adapter_type === 'string' ? latestResult.planned_adapter_type : null
  const executionPath =
    typeof latestResult?.execution_path === 'string' ? latestResult.execution_path : null

  return (
    <Card className='border-border/70'>
      <CardHeader className='pb-4'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <CardTitle className='flex items-center gap-2'>
              <Bug className='h-4 w-4' />
              路由调试
            </CardTitle>
            <CardDescription>先选能力，再筛模型并发起最小测试，适合排查能力级和模型级覆盖是否生效。</CardDescription>
          </div>
          <div className='flex gap-2'>
            <Button
              variant='outline'
              onClick={handlePreview}
              disabled={previewMutation.isPending || !effectiveSelectedModel || !effectiveSelectedCapability || !isProviderReadyForDebug}
            >
              {previewMutation.isPending ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <RefreshCw className='mr-2 h-4 w-4' />}
              预览路由
            </Button>
            <Button
              onClick={handleInvoke}
              disabled={invokeMutation.isPending || !effectiveSelectedModel || !effectiveSelectedCapability || !isProviderReadyForDebug}
            >
              {invokeMutation.isPending ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <Play className='mr-2 h-4 w-4' />}
              最小测试
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='grid gap-4 xl:grid-cols-[minmax(0,220px)_minmax(0,1fr)]'>
          <div className='space-y-2'>
            <div className='text-sm font-medium'>调试能力</div>
            <Select
              value={effectiveSelectedCapability || '__empty__'}
              onValueChange={(value) => {
                setSelectedCapability(value === '__empty__' ? '' : (value as CapabilityType))
                setSelectedModelId('')
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder='选择能力' />
              </SelectTrigger>
              <SelectContent>
                {providerCapabilityOptions.length > 0 ? (
                  providerCapabilityOptions.map((capability) => (
                    <SelectItem key={capability} value={capability}>
                      {capabilityMeta[capability].label}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value='__empty__' disabled>
                    当前厂商没有可调试能力
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <div className='text-sm font-medium'>调试模型</div>
            <Popover open={modelSelectorOpen} onOpenChange={setModelSelectorOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant='outline'
                  role='combobox'
                  aria-expanded={modelSelectorOpen}
                  className='w-full justify-between'
                  disabled={candidateModels.length === 0}
                >
                  <span className='truncate text-left'>
                    {effectiveSelectedModel?.display_name || '选择模型'}
                  </span>
                  <ChevronsUpDown className='ml-2 h-4 w-4 shrink-0 opacity-50' />
                </Button>
              </PopoverTrigger>
              <PopoverContent className='w-[360px] p-0' align='start'>
                <Command shouldFilter>
                  <CommandInput placeholder={`搜索模型，当前 ${candidateModels.length} 个...`} />
                  <CommandList className='max-h-[320px]'>
                    <CommandEmpty>没有匹配的模型</CommandEmpty>
                    <CommandGroup>
                      {candidateModels.map((model) => (
                        <CommandItem
                          key={model.tenant_model_id}
                          value={`${model.display_name} ${model.model_key} ${model.raw_model_name} ${model.model_alias || ''}`}
                          onSelect={() => {
                            setSelectedModelId(model.tenant_model_id)
                            setModelSelectorOpen(false)
                          }}
                          className='flex items-center justify-between gap-3'
                        >
                          <div className='min-w-0 flex-1'>
                            <div className='truncate'>{model.display_name}</div>
                            <div className='truncate text-xs text-muted-foreground'>
                              {model.raw_model_name}
                            </div>
                            <div className='mt-1 flex flex-wrap gap-1'>
                              {model.capabilities
                                .filter((capability) => DEBUG_CAPABILITIES.includes(capability))
                                .slice(0, 3)
                                .map((capability) => (
                                  <Badge key={`${model.tenant_model_id}-${capability}`} variant='outline' className='px-1.5 py-0 text-[10px]'>
                                    {capabilityMeta[capability].label}
                                  </Badge>
                                ))}
                            </div>
                          </div>
                          <Check
                            className={cn(
                              'h-4 w-4 shrink-0',
                              effectiveSelectedModel?.tenant_model_id === model.tenant_model_id ? 'opacity-100' : 'opacity-0'
                            )}
                          />
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            <p className='text-xs text-muted-foreground'>
              已按当前调试能力过滤模型，支持按展示名、原始模型名和模型键模糊搜索。
            </p>
          </div>
        </div>

        {!isProviderReadyForDebug && (
          <div className='rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm text-amber-800'>
            当前厂商尚未满足调试条件。请先保存配置，并确保厂商处于启用状态且显示为“已配置”。
          </div>
        )}

        {effectiveSelectedCapability === 'chat' || effectiveSelectedCapability === 'embedding' || effectiveSelectedCapability === 'tts' ? (
          <div className='space-y-2'>
            <div className='text-sm font-medium'>{effectiveSelectedCapability === 'tts' ? '合成文本' : '测试文本'}</div>
            <Textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} />
          </div>
        ) : null}

        {effectiveSelectedCapability === 'rerank' ? (
          <div className='grid gap-4 xl:grid-cols-2'>
            <div className='space-y-2'>
              <div className='text-sm font-medium'>Query</div>
              <Textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={4} />
            </div>
            <div className='space-y-2'>
              <div className='text-sm font-medium'>Documents</div>
              <Textarea
                value={documentsText}
                onChange={(event) => setDocumentsText(event.target.value)}
                rows={6}
                placeholder='每行一条文档'
              />
            </div>
          </div>
        ) : null}

        {effectiveSelectedCapability === 'asr' ? (
          <div className='grid gap-4 xl:grid-cols-2'>
            <div className='space-y-2'>
              <div className='text-sm font-medium'>音频 URL</div>
              <Input value={audioUrl} onChange={(event) => setAudioUrl(event.target.value)} placeholder='输入可访问的音频地址' />
            </div>
            <div className='space-y-2'>
              <div className='text-sm font-medium'>可选 Prompt</div>
              <Textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} placeholder='可选，作为识别提示' />
            </div>
          </div>
        ) : null}

        {effectiveSelectedCapability === 'tts' ? (
          <div className='space-y-2'>
            <div className='text-sm font-medium'>Voice</div>
            <Input value={voice} onChange={(event) => setVoice(event.target.value)} placeholder='如 alloy' />
          </div>
        ) : null}

        {latestProfile ? (
          <div className='rounded-2xl border bg-muted/10 p-4'>
            <div className='mb-3 flex flex-wrap items-center gap-2'>
              <div className='text-sm font-medium'>最终路由解析</div>
              <Badge variant='outline'>{latestProfile.capability_type}</Badge>
              <Badge variant='outline'>{latestProfile.adapter_type}</Badge>
              {executionAdapterType && (
                <Badge variant='outline' className='border-emerald-200 bg-emerald-50 text-emerald-700'>
                  实际执行：{executionAdapterType}
                </Badge>
              )}
            </div>
            {executionPath && (
              <div className='mb-3 rounded-xl border border-emerald-200 bg-emerald-50/70 px-3 py-2 text-sm text-emerald-800'>
                本次最小测试实际命中路径：`{executionPath}`
                {plannedAdapterTypeFromResult && executionAdapterType && plannedAdapterTypeFromResult !== executionAdapterType
                  ? `，计划适配器为 ${plannedAdapterTypeFromResult}，最终回退为 ${executionAdapterType}`
                  : ''}
              </div>
            )}
            <div className='grid gap-3 md:grid-cols-2 xl:grid-cols-3'>
              <ProfileItem label='Provider' value={`${latestProfile.provider_name} / ${latestProfile.provider_code}`} />
              <ProfileItem label='Model' value={`${latestProfile.display_name} / ${latestProfile.model_name}`} />
              <ProfileItem
                label='Implementation'
                value={latestProfile.implementation_key}
                source={latestProfile.sources.implementation_key}
              />
              <ProfileItem
                label='Request Schema'
                value={latestProfile.request_schema}
                source={latestProfile.sources.request_schema}
              />
              <ProfileItem
                label='Response Schema'
                value={latestProfile.response_schema}
                source={latestProfile.sources.response_schema}
              />
              <ProfileItem label='Timeout' value={`${latestProfile.timeout_seconds}s`} />
              <ProfileItem
                label='Model Concurrency'
                value={latestProfile.concurrency_limit ? String(latestProfile.concurrency_limit) : '未配置'}
                source={latestProfile.sources.concurrency_limit}
              />
              <ProfileItem
                label='Concurrency Mode'
                value={latestProfile.concurrency_mode || '继承全局'}
              />
              <ProfileItem
                label='Concurrency Wait Timeout'
                value={
                  latestProfile.concurrency_wait_timeout_seconds !== null &&
                  latestProfile.concurrency_wait_timeout_seconds !== undefined
                    ? `${latestProfile.concurrency_wait_timeout_seconds}s`
                    : '继承全局'
                }
              />
              <ProfileItem label='Base URL' value={latestProfile.base_url} source={latestProfile.sources.base_url} />
              <ProfileItem
                label='Endpoint Path'
                value={latestProfile.endpoint_path || '-'}
                source={latestProfile.sources.endpoint_path}
              />
              <ProfileItem label='Effective URL' value={latestProfile.effective_url} />
              <ProfileItem label='Adapter' value={latestProfile.adapter_type} source={latestProfile.sources.adapter_type} />
              <ProfileItem
                label='Multimodal'
                value={latestProfile.supports_multimodal_input ? 'enabled' : 'disabled'}
                source={latestProfile.sources.supports_multimodal_input}
              />
            </div>
          </div>
        ) : null}

        {latestResult ? (
          <div className='space-y-2'>
            <div className='flex flex-wrap items-center justify-between gap-2'>
              <div className='text-sm font-medium'>最小测试结果</div>
              <div className='flex gap-2'>
                {effectiveSelectedCapability === 'asr' && (
                  <Button size='sm' variant='outline' onClick={handleCopyAsrText}>
                    <Clipboard className='mr-2 h-3.5 w-3.5' />
                    复制文本
                  </Button>
                )}
                {effectiveSelectedCapability === 'tts' && latestTtsAudioUrl && (
                  <Button size='sm' variant='outline' asChild>
                    <a href={latestTtsAudioUrl} download='debug-tts-audio'>
                      <Volume2 className='mr-2 h-3.5 w-3.5' />
                      下载音频
                    </a>
                  </Button>
                )}
              </div>
            </div>
            {effectiveSelectedCapability === 'tts' && latestTtsAudioUrl ? (
              <audio controls className='w-full'>
                <source src={latestTtsAudioUrl} />
              </audio>
            ) : null}
            <pre className='max-h-96 overflow-auto rounded-2xl border bg-muted/20 p-4 text-xs leading-6'>
              {JSON.stringify(latestResult, null, 2)}
            </pre>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function ProfileItem({ label, value, source }: { label: string; value: string; source?: string }) {
  return (
    <div className='rounded-xl border bg-background px-3 py-2'>
      <div className='text-[11px] uppercase tracking-wide text-muted-foreground'>{label}</div>
      <div className='mt-1 break-all text-sm'>{value}</div>
      {source ? <div className='mt-2 text-[11px] text-muted-foreground'>来源：{source}</div> : null}
    </div>
  )
}
