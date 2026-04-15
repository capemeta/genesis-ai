import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { CapabilityType } from '@/lib/api/model-platform'
import { capabilityMeta } from '../constants'
import type { DefaultCapabilityEntry } from '../types'

type DefaultModelsTabProps = {
  defaultCapabilityEntries: DefaultCapabilityEntry[]
  defaultModelMap: Map<string, string>
  onSetDefaultModel: (capability: CapabilityType, tenantModelId: string) => void
  isUpdating: boolean
}

export function DefaultModelsTab({
  defaultCapabilityEntries,
  defaultModelMap,
  onSetDefaultModel,
  isUpdating,
}: DefaultModelsTabProps) {
  return (
    <Card className='border-border/70'>
      <CardHeader>
        <CardTitle>默认模型</CardTitle>
        <CardDescription>默认模型直接读写租户默认模型表；所有能力都会展示，没有可选模型时仅不可选择。</CardDescription>
      </CardHeader>
      <CardContent className='space-y-3'>
        {defaultCapabilityEntries.map(({ capability, model, options }) => {
          const meta = capabilityMeta[capability]
          const Icon = meta.icon

          return (
            <div
              key={capability}
              className='grid gap-3 rounded-2xl border px-4 py-4 lg:grid-cols-[200px_minmax(0,1fr)_minmax(0,220px)] lg:items-center'
            >
              <div className='flex items-center gap-3'>
                <div className={`rounded-2xl border p-3 ${meta.tone}`}>
                  <Icon className='h-5 w-5' />
                </div>
                <div>
                  <div className='font-medium'>{meta.label}</div>
                  <div className='text-sm text-muted-foreground'>平台默认入口</div>
                </div>
              </div>

              <div className='text-sm text-muted-foreground'>
                {model ? `${model.provider_display_name} / ${model.display_name}` : '未设置默认模型'}
              </div>

              <Select
                value={(defaultModelMap.get(capability) as string | undefined) ?? '__none__'}
                onValueChange={(value) => onSetDefaultModel(capability, value)}
                disabled={isUpdating || options.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder={options.length === 0 ? '暂无可选模型' : '选择默认模型'} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='__none__'>不设置默认模型</SelectItem>
                  {Object.entries(
                    options.reduce<Record<string, typeof options>>((acc, option) => {
                      if (!acc[option.provider_display_name]) {
                        acc[option.provider_display_name] = []
                      }
                      acc[option.provider_display_name].push(option)
                      return acc
                    }, {})
                  ).map(([providerName, groupedOptions]) => (
                    <SelectGroup key={providerName}>
                      <SelectLabel>{providerName}</SelectLabel>
                      {groupedOptions.map((option) => (
                        <SelectItem key={option.tenant_model_id} value={option.tenant_model_id}>
                          {option.display_name}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
