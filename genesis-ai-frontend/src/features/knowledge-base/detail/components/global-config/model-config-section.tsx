import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { BrainCircuit, Languages, Eye, HelpCircle } from 'lucide-react'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'
import type { ModelSettingsOverviewResponse, ModelSettingsProviderModel } from '@/lib/api/model-platform'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface ModelConfigSectionProps {
  config: ConfigState
  onConfigChange: (config: ConfigState) => void
  modelOverview?: ModelSettingsOverviewResponse
}

interface ModelOption {
  tenantModelId: string
  providerDisplayName: string
  displayName: string
  rawModelName: string
}

const TENANT_DEFAULT_OPTION = '__tenant_default__'

function buildModelOptions(
  modelOverview: ModelSettingsOverviewResponse | undefined,
  capability: 'embedding' | 'chat' | 'vision'
): ModelOption[] {
  const providers = modelOverview?.providers ?? []
  const options: ModelOption[] = []
  const seen = new Set<string>()
  providers
    .filter((provider) => provider.is_configured && provider.is_enabled)
    .forEach((provider) => {
      provider.models
        .filter((model) => model.is_enabled && model.capabilities.includes(capability))
        .forEach((model: ModelSettingsProviderModel) => {
          if (seen.has(model.tenant_model_id)) {
            return
          }
          seen.add(model.tenant_model_id)
          options.push({
            tenantModelId: model.tenant_model_id,
            providerDisplayName: provider.display_name,
            displayName: model.display_name,
            rawModelName: model.raw_model_name,
          })
        })
    })
  return options.sort((left, right) => {
    const providerOrder = left.providerDisplayName.localeCompare(right.providerDisplayName, 'zh-CN')
    if (providerOrder !== 0) {
      return providerOrder
    }
    return left.displayName.localeCompare(right.displayName, 'zh-CN')
  })
}

function resolveDefaultModelId(
  modelOverview: ModelSettingsOverviewResponse | undefined,
  capability: 'embedding' | 'chat' | 'vision'
): string | undefined {
  return modelOverview?.default_models.find((item) => item.capability_type === capability)?.tenant_model_id
}

function resolveSelectedModelValue(
  explicitModelId: string | undefined,
  defaultModelId: string | undefined,
  options: ModelOption[]
): string | undefined {
  if (explicitModelId && options.some((item) => item.tenantModelId === explicitModelId)) {
    return explicitModelId
  }
  if (defaultModelId && options.some((item) => item.tenantModelId === defaultModelId)) {
    return TENANT_DEFAULT_OPTION
  }
  return undefined
}

function resolveSelectedModelSource(
  explicitModelId: string | undefined,
  defaultModelId: string | undefined,
  options: ModelOption[]
): 'explicit' | 'default' | 'unconfigured' {
  if (explicitModelId && options.some((item) => item.tenantModelId === explicitModelId)) {
    return 'explicit'
  }
  if (defaultModelId && options.some((item) => item.tenantModelId === defaultModelId)) {
    return 'default'
  }
  return 'unconfigured'
}

function findModelOption(options: ModelOption[], tenantModelId: string | undefined): ModelOption | undefined {
  if (!tenantModelId) {
    return undefined
  }
  return options.find((item) => item.tenantModelId === tenantModelId)
}

function buildStatusText(
  source: 'explicit' | 'default' | 'unconfigured',
  explicitOption: ModelOption | undefined,
  defaultOption: ModelOption | undefined
): string {
  if (source === 'explicit' && explicitOption) {
    return `当前使用知识库专属模型：${explicitOption.providerDisplayName} / ${explicitOption.displayName} (${explicitOption.rawModelName})`
  }
  if (source === 'default' && defaultOption) {
    return `当前沿用租户默认模型：${defaultOption.providerDisplayName} / ${defaultOption.displayName} (${defaultOption.rawModelName})`
  }
  return '当前未显式配置模型，保存前请先选择模型或设置租户默认模型'
}

function groupOptionsByProvider(options: ModelOption[]): Array<{ providerName: string; options: ModelOption[] }> {
  const grouped = options.reduce<Record<string, ModelOption[]>>((acc, option) => {
    if (!acc[option.providerDisplayName]) {
      acc[option.providerDisplayName] = []
    }
    acc[option.providerDisplayName].push(option)
    return acc
  }, {})
  return Object.entries(grouped).map(([providerName, providerOptions]) => ({
    providerName,
    options: providerOptions,
  }))
}

export function ModelConfigSection({ config, onConfigChange, modelOverview }: ModelConfigSectionProps) {
  const embeddingOptions = buildModelOptions(modelOverview, 'embedding')
  const chatOptions = buildModelOptions(modelOverview, 'chat')
  const visionOptions = buildModelOptions(modelOverview, 'vision')
  const defaultEmbeddingModelId = resolveDefaultModelId(modelOverview, 'embedding')
  const defaultChatModelId = resolveDefaultModelId(modelOverview, 'chat')
  const defaultVisionModelId = resolveDefaultModelId(modelOverview, 'vision')

  const embeddingValue = resolveSelectedModelValue(config.embedding_model_id, defaultEmbeddingModelId, embeddingOptions)
  const chatValue = resolveSelectedModelValue(config.index_model_id, defaultChatModelId, chatOptions)
  const visionValue = resolveSelectedModelValue(config.vision_model_id, defaultVisionModelId, visionOptions)

  const embeddingSource = resolveSelectedModelSource(config.embedding_model_id, defaultEmbeddingModelId, embeddingOptions)
  const chatSource = resolveSelectedModelSource(config.index_model_id, defaultChatModelId, chatOptions)
  const visionSource = resolveSelectedModelSource(config.vision_model_id, defaultVisionModelId, visionOptions)

  const defaultEmbeddingOption = findModelOption(embeddingOptions, defaultEmbeddingModelId)
  const defaultChatOption = findModelOption(chatOptions, defaultChatModelId)
  const defaultVisionOption = findModelOption(visionOptions, defaultVisionModelId)

  const explicitEmbeddingOption = findModelOption(embeddingOptions, config.embedding_model_id)
  const explicitChatOption = findModelOption(chatOptions, config.index_model_id)
  const explicitVisionOption = findModelOption(visionOptions, config.vision_model_id)

  const handleModelChange = (
    fieldName: 'embedding_model' | 'index_model' | 'vision_model',
    fieldIdName: 'embedding_model_id' | 'index_model_id' | 'vision_model_id',
    value: string,
    options: ModelOption[]
  ) => {
    if (value === TENANT_DEFAULT_OPTION) {
      // 选择"使用租户默认"时，显式设置为 null，以便后端能够清空旧值
      onConfigChange({
        ...config,
        [fieldName]: null,
        [fieldIdName]: null,
      })
      return
    }

    const selected = options.find((item) => item.tenantModelId === value)
    onConfigChange({
      ...config,
      [fieldName]: selected?.rawModelName ?? null,
      [fieldIdName]: selected?.tenantModelId ?? null,
    })
  }

  return (
    <div className='space-y-6'>
      {/* 向量嵌入模型 */}
      <div className='space-y-2'>
        <div className='flex items-center justify-between'>
          <Label htmlFor='embedding_model' className='text-sm font-semibold text-foreground'>
            向量嵌入模型
          </Label>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className='h-4 w-4 text-muted-foreground/40 cursor-help hover:text-muted-foreground transition-colors' />
              </TooltipTrigger>
              <TooltipContent className='max-w-xs'>
                <p className='text-xs leading-relaxed'>用于将文档转化为向量数组，决定了检索深度。更改此模型会导致已解析文档失效。</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <Select
          value={embeddingValue}
          onValueChange={(value) => handleModelChange('embedding_model', 'embedding_model_id', value, embeddingOptions)}
        >
          <SelectTrigger id='embedding_model' className='h-10 text-sm'>
            <div className='flex items-center gap-2.5'>
              <div className='h-6 w-6 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0'>
                <Languages className='h-3.5 w-3.5' />
              </div>
              <SelectValue placeholder='请选择嵌入模型' />
            </div>
          </SelectTrigger>
          <SelectContent>
            {embeddingOptions.length === 0 ? (
              <SelectItem value='__empty__' disabled className='py-2 text-sm'>暂无可用嵌入模型，请先到模型服务中配置</SelectItem>
            ) : (
              <>
                {defaultEmbeddingOption && (
                  <SelectItem value={TENANT_DEFAULT_OPTION} className='py-2 text-sm'>
                    使用租户默认模型: {defaultEmbeddingOption.providerDisplayName} / {defaultEmbeddingOption.displayName} ({defaultEmbeddingOption.rawModelName})
                  </SelectItem>
                )}
                {groupOptionsByProvider(embeddingOptions).map((group) => (
                  <SelectGroup key={group.providerName}>
                    <SelectLabel>{group.providerName}</SelectLabel>
                    {group.options.map((option) => (
                      <SelectItem key={option.tenantModelId} value={option.tenantModelId} className='py-2 text-sm'>
                        {option.displayName} ({option.rawModelName})
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </>
            )}
          </SelectContent>
        </Select>
        <p className='text-xs text-muted-foreground'>
          {buildStatusText(embeddingSource, explicitEmbeddingOption, defaultEmbeddingOption)}
        </p>
      </div>

      {/* 索引模型 */}
      <div className='space-y-2'>
        <Label htmlFor='index_model' className='text-sm font-semibold text-foreground'>
          理解与索引模型
        </Label>
        <Select
          value={chatValue}
          onValueChange={(value) => handleModelChange('index_model', 'index_model_id', value, chatOptions)}
        >
          <SelectTrigger id='index_model' className='h-10 text-sm'>
            <div className='flex items-center gap-2.5'>
              <div className='h-6 w-6 rounded-md bg-indigo-500/10 text-indigo-500 flex items-center justify-center shrink-0'>
                <BrainCircuit className='h-3.5 w-3.5' />
              </div>
              <SelectValue placeholder='请选择理解与索引模型' />
            </div>
          </SelectTrigger>
          <SelectContent>
            {chatOptions.length === 0 ? (
              <SelectItem value='__empty__' disabled className='py-2 text-sm'>暂无可用大模型，请先到模型服务中配置</SelectItem>
            ) : (
              <>
                {defaultChatOption && (
                  <SelectItem value={TENANT_DEFAULT_OPTION} className='py-2 text-sm'>
                    使用租户默认模型: {defaultChatOption.providerDisplayName} / {defaultChatOption.displayName} ({defaultChatOption.rawModelName})
                  </SelectItem>
                )}
                {groupOptionsByProvider(chatOptions).map((group) => (
                  <SelectGroup key={group.providerName}>
                    <SelectLabel>{group.providerName}</SelectLabel>
                    {group.options.map((option) => (
                      <SelectItem key={option.tenantModelId} value={option.tenantModelId} className='py-2 text-sm'>
                        {option.displayName} ({option.rawModelName})
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </>
            )}
          </SelectContent>
        </Select>
        <p className='text-xs text-muted-foreground'>
          {buildStatusText(chatSource, explicitChatOption, defaultChatOption)}
        </p>
      </div>

      {/* 视觉模型 */}
      <div className='space-y-2'>
        <Label htmlFor='vision_model' className='text-sm font-semibold text-foreground'>
          多模态视觉模型
        </Label>
        <Select
          value={visionValue}
          onValueChange={(value) => handleModelChange('vision_model', 'vision_model_id', value, visionOptions)}
        >
          <SelectTrigger id='vision_model' className='h-10 text-sm'>
            <div className='flex items-center gap-2.5'>
              <div className='h-6 w-6 rounded-md bg-purple-500/10 text-purple-500 flex items-center justify-center shrink-0'>
                <Eye className='h-3.5 w-3.5' />
              </div>
              <SelectValue placeholder='请选择视觉模型' />
            </div>
          </SelectTrigger>
          <SelectContent>
            {visionOptions.length === 0 ? (
              <SelectItem value='__empty__' disabled className='py-2 text-sm'>暂无可用视觉模型，可先使用通用大模型</SelectItem>
            ) : (
              <>
                {defaultVisionOption && (
                  <SelectItem value={TENANT_DEFAULT_OPTION} className='py-2 text-sm'>
                    使用租户默认模型: {defaultVisionOption.providerDisplayName} / {defaultVisionOption.displayName} ({defaultVisionOption.rawModelName})
                  </SelectItem>
                )}
                {groupOptionsByProvider(visionOptions).map((group) => (
                  <SelectGroup key={group.providerName}>
                    <SelectLabel>{group.providerName}</SelectLabel>
                    {group.options.map((option) => (
                      <SelectItem key={option.tenantModelId} value={option.tenantModelId} className='py-2 text-sm'>
                        {option.displayName} ({option.rawModelName})
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </>
            )}
          </SelectContent>
        </Select>
        <p className='text-xs text-muted-foreground'>
          {buildStatusText(visionSource, explicitVisionOption, defaultVisionOption)}
        </p>
      </div>
    </div>
  )
}
