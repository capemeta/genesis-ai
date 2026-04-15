import { Bot, BrainCircuit, Copy, Eye, Layers3, Link2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import type { CapabilityOverrideConfig } from '@/lib/api/model-platform'
import { capabilityMeta, capabilityOverridePlaceholders } from '../../constants'
import { CapabilityBadge, FieldHint, FieldPanel } from '../shared'
import type { ProviderSettingsTabProps } from './types'

type ProviderCapabilityOverridesProps = Pick<
  ProviderSettingsTabProps,
  | 'selectedProvider'
  | 'providerDraft'
  | 'configurableCapabilityOverrides'
  | 'onCapabilityBaseUrlChange'
  | 'onCapabilityOverrideChange'
>

/**
 * 能力级覆盖单独成块，便于后续继续扩展更多高级路由字段。
 */
export function ProviderCapabilityOverrides({
  selectedProvider,
  providerDraft,
  configurableCapabilityOverrides,
  onCapabilityBaseUrlChange,
  onCapabilityOverrideChange,
}: ProviderCapabilityOverridesProps) {
  if (!selectedProvider || configurableCapabilityOverrides.length === 0) {
    return null
  }

  return (
    <>
      <details className='rounded-2xl border border-border/70 bg-muted/10 px-4 py-3'>
        <summary className='cursor-pointer list-none text-sm font-medium'>能力专用 API 地址</summary>
        <div className='mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]'>
          {configurableCapabilityOverrides.map((capability) => (
            <FieldPanel
              key={`${selectedProvider.provider_definition_id}-${capability}-base-url`}
              icon={Link2}
              label={`${capabilityMeta[capability].label} API 地址`}
            >
              <div className='relative'>
                <Input
                  value={providerDraft.capabilityBaseUrls[capability] || ''}
                  onChange={(event) => onCapabilityBaseUrlChange(capability, event.target.value)}
                  placeholder={`可选，填写后优先使用此地址调用 ${capabilityMeta[capability].label}`}
                  className='pr-10'
                />
                {providerDraft.capabilityBaseUrls[capability] && (
                  <Button
                    size='sm'
                    variant='ghost'
                    className='absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 p-0'
                    onClick={() => {
                      navigator.clipboard.writeText(providerDraft.capabilityBaseUrls[capability] || '')
                      toast.success('已复制到剪贴板')
                    }}
                  >
                    <Copy className='h-4 w-4' />
                  </Button>
                )}
              </div>
              <p className='text-xs text-muted-foreground'>填写后将覆盖默认地址用于 {capabilityMeta[capability].label} 调用</p>
            </FieldPanel>
          ))}
        </div>
      </details>

      <details className='rounded-2xl border border-border/70 bg-muted/10 px-4 py-3'>
        <summary className='cursor-pointer list-none text-sm font-medium'>能力级高级覆盖</summary>
        <div className='mt-4 space-y-4'>
          {configurableCapabilityOverrides.map((capability) => {
            const override = providerDraft.capabilityOverrides[capability] || {}
            const placeholderMeta = capabilityOverridePlaceholders[capability]
            return (
              <div
                key={`${selectedProvider.provider_definition_id}-${capability}-advanced`}
                className='rounded-2xl border border-border/60 bg-background/70 p-4'
              >
                <div className='flex flex-wrap items-center gap-2'>
                  <CapabilityBadge capability={capability} />
                  <span className='text-sm text-muted-foreground'>
                    {placeholderMeta?.helperText || '仅在能力协议、endpoint 或实现方式特殊时使用。'}
                  </span>
                </div>
                <div className='mt-4 grid gap-4 xl:grid-cols-2'>
                  <FieldPanel icon={Layers3} label='Adapter'>
                    <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                      <span>决定最终由谁来发起调用</span>
                      <FieldHint content='Adapter 用来指定调用执行器。litellm 适合标准兼容协议；native/custom 适合厂商原生或特殊接口；openai_sdk 适合直接使用 OpenAI SDK 的能力。' />
                    </div>
                    <Select
                      value={override.adapter_type || '__empty__'}
                      onValueChange={(value) =>
                        onCapabilityOverrideChange(capability, {
                          adapter_type: value === '__empty__' ? undefined : (value as CapabilityOverrideConfig['adapter_type']),
                        })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder='默认继承后端策略' />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value='__empty__'>默认继承后端策略</SelectItem>
                        <SelectItem value='native'>native</SelectItem>
                        <SelectItem value='custom'>custom</SelectItem>
                        <SelectItem value='litellm'>litellm</SelectItem>
                        <SelectItem value='openai_sdk'>openai_sdk</SelectItem>
                      </SelectContent>
                    </Select>
                  </FieldPanel>

                  <FieldPanel icon={Layers3} label='Request Schema'>
                    <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                      <span>决定统一请求如何翻译成上游请求体</span>
                      <FieldHint content='Request Schema 表示请求协议模板。比如统一 rerank 请求，可以翻译成 openai_rerank，也可以翻译成 dashscope_text_rerank_v1。' />
                    </div>
                    <Input
                      value={override.request_schema || ''}
                      onChange={(event) => onCapabilityOverrideChange(capability, { request_schema: event.target.value })}
                      placeholder={placeholderMeta?.requestSchema || '如 openai_compatible_schema'}
                    />
                  </FieldPanel>

                  <FieldPanel icon={Link2} label='Endpoint Path'>
                    <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                      <span>决定最终拼接的接口路径</span>
                      <FieldHint content='Endpoint Path 会和对应能力的 base_url 组合，形成最终请求地址。仅当某个能力的默认路径不对时才需要填写。' />
                    </div>
                    <Input
                      value={override.endpoint_path || ''}
                      onChange={(event) => onCapabilityOverrideChange(capability, { endpoint_path: event.target.value })}
                      placeholder={placeholderMeta?.endpointPath || '可选，留空则走默认推导'}
                    />
                  </FieldPanel>

                  <FieldPanel icon={BrainCircuit} label='Response Schema'>
                    <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                      <span>决定上游响应如何归一化</span>
                      <FieldHint content='Response Schema 表示响应解析模板。它告诉后端应该用哪一种 normalizer 把厂商返回值转成平台统一响应。通常不填时默认等于 Request Schema。' />
                    </div>
                    <Input
                      value={override.response_schema || ''}
                      onChange={(event) => onCapabilityOverrideChange(capability, { response_schema: event.target.value })}
                      placeholder='为空则默认等于 request schema'
                    />
                  </FieldPanel>

                  <FieldPanel icon={Bot} label='Implementation Key'>
                    <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                      <span>决定协议族里的具体实现</span>
                      <FieldHint content='Implementation Key 用来选细分实现。例如同样是 rerank，可能分别对应 openai_compatible_rerank、dashscope_text_rerank_v1、dashscope_multimodal_rerank_v1。' />
                    </div>
                    <Input
                      value={override.implementation_key || ''}
                      onChange={(event) => onCapabilityOverrideChange(capability, { implementation_key: event.target.value })}
                      placeholder={placeholderMeta?.implementationKey || '如 provider_native_impl'}
                    />
                  </FieldPanel>

                  <FieldPanel icon={Eye} label='支持多模态输入'>
                    <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                      <span>允许 text/image/audio/video 混合输入</span>
                      <FieldHint content='只有当该能力本身支持多模态文档时才需要开启，比如多模态 rerank 或视觉理解类能力。普通文本 embedding / rerank 一般保持关闭。' />
                    </div>
                    <div className='flex min-h-10 items-center justify-between rounded-xl border border-dashed px-3'>
                      <span className='text-sm text-muted-foreground'>允许 text / image / audio / video 等混合输入</span>
                      <Switch
                        checked={Boolean(override.supports_multimodal_input)}
                        onCheckedChange={(checked) =>
                          onCapabilityOverrideChange(capability, { supports_multimodal_input: checked || undefined })
                        }
                      />
                    </div>
                  </FieldPanel>
                </div>
              </div>
            )
          })}
        </div>
        <p className='mt-3 text-xs text-muted-foreground'>
          默认情况下只需配置 base URL。只有厂商不同能力协议不一致，或单个能力的网关行为特殊时，才需要这里的高级覆盖。
        </p>
      </details>
    </>
  )
}
