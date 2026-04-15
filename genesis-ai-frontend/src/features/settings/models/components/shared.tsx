import { type ReactNode, useState } from 'react'
import { ChevronRight, CircleHelp, Loader2, Save, type LucideIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { CapabilityType, ModelSettingsProvider } from '@/lib/api/model-platform'
import { capabilityMeta, endpointTypeLabelMap, providerLogoMap, providerThemeMap } from '../constants'
import type { ModelDraft } from '../types'
import { getProviderCapabilities, getProviderCapabilityLabel } from '../utils'

export function ProviderAvatar({ name, large = false }: { name: string; large?: boolean }) {
  const label = name
    .split(/[\s-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
  const theme = providerThemeMap[name] ?? 'bg-slate-100 text-slate-700'
  const logo = providerLogoMap[name]

  return (
    <div className={`flex shrink-0 items-center justify-center overflow-hidden rounded-2xl ${large ? 'h-14 w-14' : 'h-10 w-10'}`}>
      {logo ? (
        <img src={logo} alt={`${name} logo`} className='h-full w-full object-cover' />
      ) : (
        <div className={`flex h-full w-full items-center justify-center font-semibold ${large ? 'text-lg' : 'text-sm'} ${theme}`}>
          {label}
        </div>
      )}
    </div>
  )
}

export function ProviderSection({
  title,
  description,
  providers,
  selectedProviderDefinitionId,
  onSelect,
}: {
  title: string
  description: string
  providers: ModelSettingsProvider[]
  selectedProviderDefinitionId: string | null
  onSelect: (providerDefinitionId: string) => void
}) {
  if (!providers.length) {
    return null
  }

  return (
    <div className='space-y-2'>
      <div className='px-1'>
        <div className='text-sm font-medium'>{title}</div>
        <div className='text-xs text-muted-foreground'>{description}</div>
      </div>
      <div className='space-y-2'>
        {providers.map((provider) => {
          const isActive = selectedProviderDefinitionId === provider.provider_definition_id

          return (
            <button
              key={provider.provider_definition_id}
              type='button'
              onClick={() => onSelect(provider.provider_definition_id)}
              className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                isActive
                  ? 'border-primary bg-primary/5 shadow-sm'
                  : 'border-border/70 bg-card hover:border-primary/40 hover:bg-accent/30'
              }`}
            >
              <div className='flex items-start gap-3'>
                <ProviderAvatar name={provider.display_name} />
                <div className='min-w-0 flex-1 space-y-1'>
                  <div className='flex flex-wrap items-center gap-2'>
                    <span className='min-w-0 truncate font-medium'>{provider.display_name}</span>
                    <span className='shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground'>
                      {provider.is_enabled ? 'ON' : 'OFF'}
                    </span>
                    {!provider.is_configured && (
                      <span className='shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] text-amber-700'>未配置</span>
                    )}
                  </div>
                  <div className='flex flex-wrap items-center gap-2 text-xs text-muted-foreground'>
                    <span>{endpointTypeLabelMap[provider.endpoint_type]}</span>
                    <span>·</span>
                    <span>{provider.models.length} 个模型</span>
                  </div>
                  <div className='flex flex-wrap gap-1.5 pt-1'>
                    {getProviderCapabilities(provider).map((capability) => (
                      <ProviderCapabilityBadge key={`${provider.provider_definition_id}-${capability}`} capability={capability} />
                    ))}
                  </div>
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function FieldPanel({
  icon: Icon,
  label,
  children,
}: {
  icon: LucideIcon
  label: string
  children: ReactNode
}) {
  return (
    <div className='space-y-2 rounded-2xl border bg-muted/10 p-4'>
      <div className='flex items-center gap-2 text-sm text-muted-foreground'>
        <Icon className='h-4 w-4' />
        <span>{label}</span>
      </div>
      {children}
    </div>
  )
}

export function FieldHint({ content }: { content: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type='button'
          className='inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground'
          aria-label='查看字段说明'
        >
          <CircleHelp className='h-4 w-4' />
        </button>
      </TooltipTrigger>
      <TooltipContent side='top' sideOffset={6} className='max-w-80 whitespace-pre-line text-left leading-5'>
        {content}
      </TooltipContent>
    </Tooltip>
  )
}

export function InlineSwitch({
  label,
  checked,
  onCheckedChange,
  compact = false,
  disabled = false,
}: {
  label: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  compact?: boolean
  disabled?: boolean
}) {
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-xl border bg-background px-3 py-2 ${
        compact ? 'min-w-[132px]' : ''
      }`}
    >
      <span className='text-sm text-muted-foreground'>{label}</span>
      <Switch checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </div>
  )
}

export function CapabilityBadge({ capability }: { capability: CapabilityType }) {
  const meta = capabilityMeta[capability]
  const Icon = meta.icon
  return (
    <Badge variant='outline' className={`gap-1.5 ${meta.tone}`}>
      <Icon className='h-3.5 w-3.5' />
      {meta.label}
    </Badge>
  )
}

export function ProviderCapabilityBadge({ capability }: { capability: CapabilityType }) {
  return (
    <span className='rounded-full bg-muted px-1.5 py-0.5 text-[10px] leading-none text-muted-foreground'>
      {getProviderCapabilityLabel(capability)}
    </span>
  )
}

function formatModelNumber(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('zh-CN') : ''
}

function formatModelSize(value: unknown): string {
  const size = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(size) || size <= 0) {
    return ''
  }
  if (size >= 1024 ** 3) {
    return `${(size / 1024 ** 3).toFixed(1)} GB`
  }
  if (size >= 1024 ** 2) {
    return `${(size / 1024 ** 2).toFixed(1)} MB`
  }
  return `${Math.round(size / 1024).toLocaleString('zh-CN')} KB`
}

function getSourcePayload(model: ModelSettingsProvider['models'][number]): Record<string, unknown> {
  const sourcePayload = model.metadata_info?.source_payload
  return sourcePayload && typeof sourcePayload === 'object' && !Array.isArray(sourcePayload)
    ? (sourcePayload as Record<string, unknown>)
    : {}
}

function getDiscoveredMetadata(model: ModelSettingsProvider['models'][number]): Record<string, unknown> {
  const discoveredMetadata = model.metadata_info?.discovered_metadata
  return discoveredMetadata && typeof discoveredMetadata === 'object' && !Array.isArray(discoveredMetadata)
    ? (discoveredMetadata as Record<string, unknown>)
    : {}
}

export function CompactModelTable({
  models,
  defaultModelMap,
  modelDrafts,
  pendingModelActionKey,
  onEnabledChange,
  onVisibleChange,
  onDraftChange,
  onSaveMeta,
  onResetMeta,
  isSaving,
  forceExpandAll = false,
}: {
  models: ModelSettingsProvider['models']
  defaultModelMap: Map<string, string>
  modelDrafts: Record<string, ModelDraft>
  pendingModelActionKey: string | null
  onEnabledChange: (tenantModelId: string, checked: boolean) => void
  onVisibleChange: (tenantModelId: string, checked: boolean) => void
  onDraftChange: (
    tenantModelId: string,
    patch: Partial<ModelDraft>,
    fallback: {
      modelAlias: string
      groupName: string
      contextWindow: string
      maxOutputTokens: string
      concurrencyLimit: string
      modelRuntimeConfig?: Record<string, unknown>
    }
  ) => void
  onSaveMeta: (
    tenantModelId: string,
    draft: ModelDraft,
    fallback: {
      modelAlias: string
      groupName: string
      contextWindow: string
      maxOutputTokens: string
      concurrencyLimit: string
      modelRuntimeConfig?: Record<string, unknown>
    }
  ) => void
  onResetMeta: (tenantModelId: string) => void
  isSaving: boolean
  forceExpandAll?: boolean
}) {
  const groups = models.reduce<Record<string, ModelSettingsProvider['models']>>((acc, model) => {
    const groupKey = model.group_name || capabilityMeta[model.model_type].label
    acc[groupKey] = acc[groupKey] || []
    acc[groupKey].push(model)
    return acc
  }, {})
  const groupEntries = Object.entries(groups).sort(([left], [right]) => left.localeCompare(right, 'zh-CN'))
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())

  const toggleGroup = (groupName: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(groupName)) {
        next.delete(groupName)
      } else {
        next.add(groupName)
      }
      return next
    })
  }

  return (
    <div className='space-y-3'>
      {groupEntries.map(([groupName, items]) => {
        const isExpanded = forceExpandAll || expandedGroups.has(groupName)
        return (
          <div key={groupName} className='rounded-2xl border'>
            <div
              className={`flex items-center justify-between border-b bg-muted/20 px-4 py-3 ${
                forceExpandAll ? '' : 'cursor-pointer'
              }`}
              onClick={forceExpandAll ? undefined : () => toggleGroup(groupName)}
            >
              <div className='flex items-center gap-2'>
                <ChevronRight className={`h-4 w-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                <div className='font-medium'>{groupName}</div>
              </div>
              <div className='text-xs text-muted-foreground'>{items.length} 个模型</div>
            </div>
            {isExpanded && (
              <div className='max-h-96 overflow-y-auto'>
                <div className='divide-y'>
                  {items.map((model) => {
                    const boundCapabilities = (Object.keys(capabilityMeta) as CapabilityType[]).filter(
                      (capability) => defaultModelMap.get(capability) === model.tenant_model_id
                    )
                    const fallback = {
                      modelAlias: model.display_name,
                      groupName: model.group_name ?? '',
                      contextWindow: String(model.context_window ?? ''),
                      maxOutputTokens: String(model.max_output_tokens ?? ''),
                      concurrencyLimit: String((model.rate_limit_config?.concurrency_limit as number | undefined) ?? ''),
                      modelRuntimeConfig: model.model_runtime_config,
                    }
                    const draft = modelDrafts[model.tenant_model_id] ?? fallback
                    const isMetaDirty =
                      draft.modelAlias !== fallback.modelAlias ||
                      draft.groupName !== fallback.groupName ||
                      draft.contextWindow !== fallback.contextWindow ||
                      draft.maxOutputTokens !== fallback.maxOutputTokens ||
                      draft.concurrencyLimit !== fallback.concurrencyLimit
                    const isRowPending = pendingModelActionKey === model.tenant_model_id
                    const sourcePayload = getSourcePayload(model)
                    const discoveredMetadata = getDiscoveredMetadata(model)
                    const sourceOwner = String(sourcePayload.owned_by || sourcePayload.owner || '').trim()
                    const modelSize = formatModelSize(sourcePayload.size)
                    const parameterSize = String(discoveredMetadata.parameter_size || '').trim()
                    const quantizationLevel = String(discoveredMetadata.quantization_level || '').trim()

                    return (
                      <div key={model.tenant_model_id} className='flex flex-col gap-3 px-4 py-3'>
                        <div className='min-w-0 flex-1 space-y-3'>
                          <div className='flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between'>
                            <div className='min-w-0'>
                              <div className='font-medium'>{model.display_name}</div>
                              <div className='flex flex-wrap gap-x-2 gap-y-1 text-xs text-muted-foreground'>
                                <span>{model.raw_model_name}</span>
                                {model.source_type ? <span>来源: {model.source_type === 'manual' ? '手动' : '同步'}</span> : null}
                                {sourceOwner ? <span>归属: {sourceOwner}</span> : null}
                                {model.model_family ? <span>家族: {model.model_family}</span> : null}
                                {model.release_channel ? <span>通道: {model.release_channel}</span> : null}
                                {modelSize ? <span>大小: {modelSize}</span> : null}
                                {parameterSize ? <span>参数: {parameterSize}</span> : null}
                                {quantizationLevel ? <span>量化: {quantizationLevel}</span> : null}
                              </div>
                            </div>
                            <div className='flex shrink-0 gap-2 sm:justify-end'>
                              <Button
                                size='sm'
                                variant='outline'
                                onClick={() => onSaveMeta(model.tenant_model_id, draft, fallback)}
                                disabled={!isMetaDirty || isSaving || isRowPending}
                              >
                                {isRowPending ? <Loader2 className='mr-2 h-3.5 w-3.5 animate-spin' /> : <Save className='mr-2 h-3.5 w-3.5' />}
                                保存
                              </Button>
                              <Button size='sm' variant='ghost' onClick={() => onResetMeta(model.tenant_model_id)} disabled={!isMetaDirty || isRowPending}>
                                重置
                              </Button>
                            </div>
                          </div>
                          <div className='flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between'>
                            <div className='grid min-w-0 flex-1 gap-3 lg:grid-cols-[220px_150px_150px_150px]'>
                              <Input
                                value={draft.groupName}
                                onChange={(event) =>
                                  onDraftChange(model.tenant_model_id, { groupName: event.target.value }, fallback)
                                }
                                placeholder='分组名称，例如 deepseek-v3'
                              />
                              <Input
                                value={draft.contextWindow}
                                onChange={(event) =>
                                  onDraftChange(model.tenant_model_id, { contextWindow: event.target.value }, fallback)
                                }
                                placeholder='上下文窗口'
                                inputMode='numeric'
                              />
                              <Input
                                value={draft.maxOutputTokens}
                                onChange={(event) =>
                                  onDraftChange(model.tenant_model_id, { maxOutputTokens: event.target.value }, fallback)
                                }
                                placeholder='最大输出'
                                inputMode='numeric'
                              />
                              <Input
                                value={draft.concurrencyLimit}
                                onChange={(event) =>
                                  onDraftChange(model.tenant_model_id, { concurrencyLimit: event.target.value }, fallback)
                                }
                                placeholder='并发上限，如 4'
                                inputMode='numeric'
                              />
                            </div>
                            <div className='flex shrink-0 flex-wrap gap-3 xl:justify-end'>
                              <InlineSwitch
                                label={model.is_enabled ? '已启用' : '已禁用'}
                                checked={model.is_enabled}
                                onCheckedChange={(checked) => onEnabledChange(model.tenant_model_id, checked)}
                                compact
                                disabled={isRowPending}
                              />
                              <InlineSwitch
                                label={model.is_visible_in_ui ? '可见' : '隐藏'}
                                checked={model.is_visible_in_ui}
                                onCheckedChange={(checked) => onVisibleChange(model.tenant_model_id, checked)}
                                compact
                                disabled={isRowPending}
                              />
                            </div>
                          </div>
                          <div className='flex flex-wrap gap-2'>
                            {model.capabilities.map((capability) => (
                              <CapabilityBadge key={`${model.tenant_model_id}-${capability}`} capability={capability} />
                            ))}
                            {typeof model.rate_limit_config?.concurrency_limit === 'number' && model.rate_limit_config.concurrency_limit > 0 ? (
                              <Badge variant='outline'>
                                并发上限 {model.rate_limit_config.concurrency_limit}
                              </Badge>
                            ) : null}
                            {model.context_window ? <Badge variant='outline'>上下文 {formatModelNumber(model.context_window)}</Badge> : null}
                            {model.max_output_tokens ? <Badge variant='outline'>最大输出 {formatModelNumber(model.max_output_tokens)}</Badge> : null}
                            {model.embedding_dimension ? <Badge variant='outline'>向量维度 {formatModelNumber(model.embedding_dimension)}</Badge> : null}
                            {model.supports_stream ? <Badge variant='outline'>流式</Badge> : null}
                            {model.supports_tools ? <Badge variant='outline'>工具调用</Badge> : null}
                            {model.supports_structured_output ? <Badge variant='outline'>结构化输出</Badge> : null}
                            {model.supports_vision_input ? <Badge variant='outline'>视觉输入</Badge> : null}
                            {model.supports_audio_input ? <Badge variant='outline'>音频输入</Badge> : null}
                            {model.supports_audio_output ? <Badge variant='outline'>音频输出</Badge> : null}
                            {boundCapabilities.map((capability) => (
                              <Badge key={`${model.tenant_model_id}-${capability}-bound`} variant='secondary'>
                                默认 {capabilityMeta[capability].label}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
