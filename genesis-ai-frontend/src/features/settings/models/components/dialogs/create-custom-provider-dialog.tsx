import { Bot, KeyRound, Layers3, Link2, Loader2, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { CapabilityType } from '@/lib/api/model-platform'
import { capabilityMeta, emptyCustomProviderForm, getRuntimeCapabilitiesForProtocol } from '../../constants'
import { FieldPanel, InlineSwitch } from '../shared'
import type { CustomProviderForm, ProviderEndpointType } from '../../types'

type CreateCustomProviderDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  form: CustomProviderForm
  onFormChange: (updater: (current: CustomProviderForm) => CustomProviderForm) => void
  onToggleCapability: (capability: CapabilityType) => void
  onSubmit: () => void
  isSubmitting: boolean
}

export function CreateCustomProviderDialog({
  open,
  onOpenChange,
  form,
  onFormChange,
  onToggleCapability,
  onSubmit,
  isSubmitting,
}: CreateCustomProviderDialogProps) {
  const runtimeCapabilities = getRuntimeCapabilitiesForProtocol(form.protocolType)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-2xl'>
        <DialogHeader>
          <DialogTitle>添加自定义厂商</DialogTitle>
          <DialogDescription>创建自定义厂商定义，并同时生成当前租户可用的厂商实例。</DialogDescription>
        </DialogHeader>

        <div className='grid gap-4 py-2 md:grid-cols-2'>
          <FieldPanel icon={Plus} label='厂商名称'>
            <Input
              value={form.displayName}
              onChange={(event) => onFormChange((current) => ({ ...current, displayName: event.target.value }))}
              placeholder='例如：My Internal Gateway'
            />
          </FieldPanel>

          <FieldPanel icon={Layers3} label='厂商编码'>
            <Input
              value={form.providerCode}
              onChange={(event) => onFormChange((current) => ({ ...current, providerCode: event.target.value }))}
              placeholder='可选，不填则按名称自动生成'
            />
          </FieldPanel>

          <FieldPanel icon={Bot} label='协议类型'>
            <Select
              value={form.protocolType}
              onValueChange={(value) =>
                onFormChange((current) => {
                  const nextProtocol = value as CustomProviderForm['protocolType']
                  const nextRuntimeCapabilities = getRuntimeCapabilitiesForProtocol(nextProtocol)
                  return {
                    ...current,
                    protocolType: nextProtocol,
                    capabilities: current.capabilities.filter((capability) => nextRuntimeCapabilities.includes(capability)),
                  }
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='openai_compatible'>OpenAI Compatible</SelectItem>
                <SelectItem value='openai'>OpenAI</SelectItem>
                <SelectItem value='azure_openai'>Azure OpenAI</SelectItem>
                <SelectItem value='ollama'>Ollama</SelectItem>
                <SelectItem value='vllm'>vLLM</SelectItem>
                <SelectItem value='gemini_native'>Gemini Native</SelectItem>
                <SelectItem value='anthropic_native'>Anthropic Native</SelectItem>
                <SelectItem value='bedrock'>Bedrock</SelectItem>
                <SelectItem value='custom'>Custom</SelectItem>
              </SelectContent>
            </Select>
          </FieldPanel>

          <FieldPanel icon={Link2} label='接入类型'>
            <Select
              value={form.endpointType}
              onValueChange={(value) =>
                onFormChange((current) => ({
                  ...current,
                  endpointType: value as ProviderEndpointType,
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='official'>官方服务</SelectItem>
                <SelectItem value='openai_compatible'>兼容网关</SelectItem>
                <SelectItem value='local'>本地部署</SelectItem>
                <SelectItem value='proxy'>平台代理</SelectItem>
              </SelectContent>
            </Select>
          </FieldPanel>

          <div className='md:col-span-2'>
            <FieldPanel icon={Link2} label='接入地址'>
              <Input
                value={form.baseUrl}
                onChange={(event) => onFormChange((current) => ({ ...current, baseUrl: event.target.value }))}
                placeholder='例如：https://my-gateway.example.com/v1'
              />
            </FieldPanel>
          </div>

          <div className='md:col-span-2'>
            <FieldPanel icon={KeyRound} label='API 密钥'>
              <Input
                value={form.apiKey}
                onChange={(event) => onFormChange((current) => ({ ...current, apiKey: event.target.value }))}
                placeholder='可选，若协议不需要可留空'
                type='password'
                autoComplete='off'
              />
            </FieldPanel>
          </div>

          <div className='md:col-span-2'>
              <FieldPanel icon={Layers3} label='支持能力'>
                <div className='flex flex-wrap gap-2'>
                  {(Object.keys(capabilityMeta) as CapabilityType[]).map((capability) => {
                    const selected = form.capabilities.includes(capability)
                    const supportedAtRuntime = runtimeCapabilities.includes(capability)
                    return (
                      <button
                        key={capability}
                        type='button'
                        disabled={!supportedAtRuntime}
                        onClick={() => onToggleCapability(capability)}
                        className={`rounded-full border px-3 py-1.5 text-sm transition ${
                          selected
                            ? 'border-primary bg-primary/10 text-primary'
                            : supportedAtRuntime
                              ? 'border-border text-muted-foreground'
                              : 'cursor-not-allowed border-dashed border-border/70 text-muted-foreground/50'
                        }`}
                      >
                        {capabilityMeta[capability].label}
                      </button>
                    )
                  })}
                </div>
                <p className='text-xs text-muted-foreground'>
                  当前协议默认可直接运行：
                  {runtimeCapabilities.length > 0
                    ? runtimeCapabilities.map((capability) => capabilityMeta[capability].label).join('、')
                    : '暂无。Custom 协议通常需要后续补充专用适配器或高级覆盖后才能真正调用。'}
                </p>
              </FieldPanel>
            </div>

          <div className='md:col-span-2'>
            <FieldPanel icon={Bot} label='说明'>
              <Input
                value={form.description}
                onChange={(event) => onFormChange((current) => ({ ...current, description: event.target.value }))}
                placeholder='可选，记录这个厂商的用途或接入说明'
              />
            </FieldPanel>
          </div>

          <div className='md:col-span-2 flex flex-wrap gap-3'>
            <InlineSwitch
              label='创建后启用'
              checked={form.isEnabled}
              onCheckedChange={(checked) => onFormChange((current) => ({ ...current, isEnabled: checked }))}
              compact
            />
            <InlineSwitch
              label='前端可见'
              checked={form.isVisibleInUI}
              onCheckedChange={(checked) => onFormChange((current) => ({ ...current, isVisibleInUI: checked }))}
              compact
            />
          </div>
          <div className='md:col-span-2 text-xs leading-5 text-muted-foreground'>
            “创建后启用”会影响实际调用；“前端可见”会影响聊天等业务页面是否展示该厂商下的模型候选，但不会删除配置。
          </div>
        </div>

        <DialogFooter>
          <Button
            variant='outline'
            onClick={() => {
              onOpenChange(false)
              onFormChange(() => emptyCustomProviderForm)
            }}
          >
            取消
          </Button>
          <Button onClick={onSubmit} disabled={isSubmitting}>
            {isSubmitting && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
            创建厂商
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
