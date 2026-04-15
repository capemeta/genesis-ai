import { Bot, Layers3, Link2, Loader2 } from 'lucide-react'
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
import { FieldHint, FieldPanel, InlineSwitch } from '../shared'
import type { CapabilityType } from '@/lib/api/model-platform'
import { capabilityMeta } from '../../constants'
import type { ManualModelForm } from '../../types'

type ManualModelDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  form: ManualModelForm
  onFormChange: (updater: (current: ManualModelForm) => ManualModelForm) => void
  onSubmit: () => void
  onCancel: () => void
  isSubmitting: boolean
}

export function ManualModelDialog({
  open,
  onOpenChange,
  form,
  onFormChange,
  onSubmit,
  onCancel,
  isSubmitting,
}: ManualModelDialogProps) {
  const toggleCapability = (capability: CapabilityType) => {
    onFormChange((current) => {
      const currentSet = new Set(current.capabilities)
      if (currentSet.has(capability)) {
        currentSet.delete(capability)
      } else {
        currentSet.add(capability)
      }
      currentSet.add(current.modelType)
      return {
        ...current,
        capabilities: Array.from(currentSet),
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='flex max-h-[90vh] w-[min(92vw,960px)] flex-col overflow-hidden p-0 sm:max-w-4xl'>
        <DialogHeader>
          <div className='px-6 pt-6'>
            <DialogTitle>手动添加模型</DialogTitle>
          </div>
          <DialogDescription className='px-6'>
            当厂商不支持自动发现模型时，可手动添加模型。支持添加不同能力的模型（如 embedding、rerank）。
          </DialogDescription>
        </DialogHeader>
        <div className='flex-1 overflow-y-auto px-6 py-4'>
          <div className='grid gap-4'>
            <div className='grid gap-4 lg:grid-cols-2'>
              <FieldPanel icon={Bot} label='模型唯一键'>
                <Input
                  value={form.modelKey}
                  onChange={(event) => onFormChange((current) => ({ ...current, modelKey: event.target.value }))}
                  placeholder='如 text-embedding-v3'
                />
                <p className='text-xs text-muted-foreground'>平台唯一标识，建议使用模型原始名称</p>
              </FieldPanel>
              <FieldPanel icon={Bot} label='原始模型名'>
                <Input
                  value={form.rawModelName}
                  onChange={(event) => onFormChange((current) => ({ ...current, rawModelName: event.target.value }))}
                  placeholder='如 text-embedding-v3'
                />
              </FieldPanel>
              <FieldPanel icon={Bot} label='展示名称'>
                <Input
                  value={form.displayName}
                  onChange={(event) => onFormChange((current) => ({ ...current, displayName: event.target.value }))}
                  placeholder='如 文本嵌入模型 v3'
                />
              </FieldPanel>
              <FieldPanel icon={Layers3} label='模型类型'>
                <Select
                  value={form.modelType}
                  onValueChange={(value) =>
                    onFormChange((current) => ({
                      ...current,
                      modelType: value as CapabilityType,
                      capabilities: Array.from(new Set([value as CapabilityType, ...current.capabilities])),
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='chat'>LLM 对话</SelectItem>
                    <SelectItem value='embedding'>Embedding 向量</SelectItem>
                    <SelectItem value='rerank'>Rerank 重排序</SelectItem>
                    <SelectItem value='vision'>视觉理解 / VLM</SelectItem>
                    <SelectItem value='asr'>ASR 语音识别</SelectItem>
                    <SelectItem value='tts'>TTS 语音合成</SelectItem>
                  </SelectContent>
                </Select>
                <div className='mt-2 flex items-center gap-2 text-xs text-muted-foreground'>
                  <span>多模态对话模型通常仍归为 chat，再额外声明 vision 或开启多模态输入</span>
                  <FieldHint content='如果模型既能聊天又能看图，主类型通常仍选 chat；vision 更适合“专用视觉理解模型”或需要单独作为视觉能力路由的模型。这样默认模型、聊天入口和能力路由会更稳定。' />
                </div>
              </FieldPanel>
            </div>

            <FieldPanel icon={Layers3} label='附加能力'>
              <div className='flex flex-wrap gap-2'>
                {(Object.keys(capabilityMeta) as CapabilityType[])
                  .filter((capability) => ['chat', 'vision', 'embedding', 'rerank', 'asr', 'tts'].includes(capability))
                  .map((capability) => {
                    const selected = form.capabilities.includes(capability)
                    const isPrimary = capability === form.modelType
                    return (
                      <button
                        key={capability}
                        type='button'
                        onClick={() => !isPrimary && toggleCapability(capability)}
                        className={`rounded-full border px-3 py-1.5 text-sm transition ${
                          selected
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border text-muted-foreground'
                        } ${isPrimary ? 'cursor-default opacity-90' : ''}`}
                      >
                        {capabilityMeta[capability].label}
                        {isPrimary ? '（主类型）' : ''}
                      </button>
                    )
                  })}
              </div>
              <div className='mt-2 flex items-center gap-2 text-xs text-muted-foreground'>
                <span>主类型会自动包含在能力列表中。多模态聊天模型建议额外勾选“视觉理解 / VLM”。</span>
                <FieldHint content='能力列表用于描述“这个模型还会什么”，不等同于主类型。比如 GPT-4o 这类模型可以设置为 model_type=chat，同时 capabilities=[chat, vision]。' />
              </div>
            </FieldPanel>

            <FieldPanel icon={Layers3} label='分组名称'>
              <Input
                value={form.groupName}
                onChange={(event) => onFormChange((current) => ({ ...current, groupName: event.target.value }))}
                placeholder='如 embedding-models'
              />
            </FieldPanel>

            <div className='grid gap-4 lg:grid-cols-3'>
              <FieldPanel icon={Layers3} label='上下文窗口'>
                <Input
                  value={form.contextWindow}
                  onChange={(event) => onFormChange((current) => ({ ...current, contextWindow: event.target.value }))}
                  placeholder='可选，如 131072'
                  inputMode='numeric'
                />
                <p className='text-xs text-muted-foreground'>私有化部署或自定义网关可在这里填写模型最大输入上下文。</p>
              </FieldPanel>
              <FieldPanel icon={Layers3} label='最大输出 Token'>
                <Input
                  value={form.maxOutputTokens}
                  onChange={(event) => onFormChange((current) => ({ ...current, maxOutputTokens: event.target.value }))}
                  placeholder='可选，如 8192'
                  inputMode='numeric'
                />
                <p className='text-xs text-muted-foreground'>用于展示和后续参数校验预留，不会自动覆盖每次调用的 max_tokens。</p>
              </FieldPanel>
              <FieldPanel icon={Layers3} label='向量维度'>
                <Input
                  value={form.embeddingDimension}
                  onChange={(event) => onFormChange((current) => ({ ...current, embeddingDimension: event.target.value }))}
                  placeholder='embedding 可选，如 1024'
                  inputMode='numeric'
                />
                <p className='text-xs text-muted-foreground'>仅 embedding 模型建议填写，便于知识库向量配置识别。</p>
              </FieldPanel>
            </div>

            <FieldPanel icon={Layers3} label='模型并发上限'>
              <Input
                value={form.concurrencyLimit}
                onChange={(event) => onFormChange((current) => ({ ...current, concurrencyLimit: event.target.value }))}
                placeholder='可选，如 4'
                inputMode='numeric'
              />
              <div className='mt-2 flex items-center gap-2 text-xs text-muted-foreground'>
                <span>只控制这个模型在平台内的总体并发，不涉及 RPM、TPM 或套餐配额</span>
                <FieldHint content='当前阶段只建议先配置单模型总体并发。留空表示仅使用平台全局并发控制，不额外叠加模型级限制。' />
              </div>
            </FieldPanel>

            <div className='rounded-2xl border border-border/60 bg-muted/20 p-4'>
              <div className='space-y-1'>
                <p className='text-sm font-medium'>高级路由覆盖</p>
                <p className='text-xs leading-5 text-muted-foreground'>
                  默认情况下模型会继承厂商级配置。只有当某个模型的协议、endpoint 或输入结构特殊时，才需要填写下面这些字段。
                </p>
              </div>
              <div className='mt-4 grid gap-4 md:grid-cols-2'>
                <FieldPanel icon={Layers3} label='适配器类型'>
                  <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                    <span>决定这个模型由哪类执行器调用</span>
                    <FieldHint content='大多数模型保持“继承默认路由”即可。只有某个模型必须单独走 LiteLLM、原生接口、OpenAI SDK 或自定义实现时，才需要显式指定。' />
                  </div>
                  <Select
                    value={form.adapterOverrideType || '__auto__'}
                    onValueChange={(value) =>
                      onFormChange((current) => ({
                        ...current,
                        adapterOverrideType: value === '__auto__' ? '' : value,
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='__auto__'>继承默认路由</SelectItem>
                      <SelectItem value='litellm'>LiteLLM</SelectItem>
                      <SelectItem value='native'>Native</SelectItem>
                      <SelectItem value='openai_sdk'>OpenAI SDK</SelectItem>
                      <SelectItem value='custom'>Custom</SelectItem>
                    </SelectContent>
                  </Select>
                </FieldPanel>
                <FieldPanel icon={Layers3} label='实现键'>
                  <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                    <span>用于选择具体实现逻辑</span>
                    <FieldHint content='当同一能力下存在多套实现时，用实现键区分。例如 Tongyi 的 rerank 可以按 openai_compatible_rerank、dashscope_text_rerank_v1 等实现处理。' />
                  </div>
                  <Input
                    value={form.implementationKeyOverride}
                    onChange={(event) =>
                      onFormChange((current) => ({ ...current, implementationKeyOverride: event.target.value }))
                    }
                    placeholder='如 dashscope_text_rerank_v1'
                  />
                </FieldPanel>
                <FieldPanel icon={Link2} label='请求协议'>
                  <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                    <span>决定统一请求如何转换成上游请求</span>
                    <FieldHint content='请求协议表示 Request Schema。它告诉后端如何把平台统一 DTO 转成目标厂商的请求体，例如 openai_rerank 或 dashscope_text_rerank_v1。' />
                  </div>
                  <Input
                    value={form.requestSchemaOverride}
                    onChange={(event) =>
                      onFormChange((current) => ({ ...current, requestSchemaOverride: event.target.value }))
                    }
                    placeholder='如 openai_rerank'
                  />
                </FieldPanel>
                <FieldPanel icon={Link2} label='Endpoint Path'>
                  <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                    <span>决定最终请求路径</span>
                    <FieldHint content='只有这个模型的接口路径和默认能力路径不同，才需要在这里单独覆盖。例如 /compatible-api/v1/reranks。' />
                  </div>
                  <Input
                    value={form.endpointPathOverride}
                    onChange={(event) =>
                      onFormChange((current) => ({ ...current, endpointPathOverride: event.target.value }))
                    }
                    placeholder='如 /compatible-api/v1/reranks'
                  />
                </FieldPanel>
                <div className='md:col-span-2'>
                  <FieldPanel icon={Link2} label='运行时 Base URL 覆盖'>
                    <div className='mb-2 flex items-center gap-2 text-xs text-muted-foreground'>
                      <span>决定这个模型的专用入口地址</span>
                      <FieldHint content='当模型不应复用厂商级 base_url 或能力级 base_url 时，再使用这个字段。它会作为模型级最高优先级的 base_url 覆盖。' />
                    </div>
                    <Input
                      value={form.runtimeBaseUrlOverride}
                      onChange={(event) =>
                        onFormChange((current) => ({ ...current, runtimeBaseUrlOverride: event.target.value }))
                      }
                      placeholder='如 https://dashscope.aliyuncs.com'
                    />
                  </FieldPanel>
                </div>
                <div className='md:col-span-2'>
                  <InlineSwitch
                    label='支持多模态输入'
                    checked={form.supportsMultimodalInput}
                    onCheckedChange={(checked) =>
                      onFormChange((current) => ({ ...current, supportsMultimodalInput: checked }))
                    }
                    compact
                  />
                  <div className='mt-2 flex items-center gap-2 text-xs text-muted-foreground'>
                    <span>开启后表示该模型接收图像、音频、视频等混合输入</span>
                    <FieldHint content='只有模型本身支持多模态文档时才需要开启。普通文本 embedding、纯文本 rerank 一般不要开启，否则会让前后端都误以为它能接收复杂输入。' />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <DialogFooter className='border-t px-6 py-4'>
          <Button variant='outline' onClick={onCancel}>
            取消
          </Button>
          <Button onClick={onSubmit} disabled={isSubmitting}>
            {isSubmitting && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
            添加模型
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
