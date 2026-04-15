import { Search } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ProviderSection } from '../shared'
import type { ProviderSettingsTabProps } from './types'

type ProviderListPanelProps = Pick<
  ProviderSettingsTabProps,
  | 'providerSearch'
  | 'onProviderSearchChange'
  | 'providerCapabilityFilterOptions'
  | 'providerCapabilityFilter'
  | 'onProviderCapabilityFilterChange'
  | 'configuredProviders'
  | 'unconfiguredProviders'
  | 'selectedProvider'
  | 'onSelectProvider'
>

/**
 * 左侧只负责厂商选择与筛选，避免和右侧配置细节耦合。
 */
export function ProviderListPanel({
  providerSearch,
  onProviderSearchChange,
  providerCapabilityFilterOptions,
  providerCapabilityFilter,
  onProviderCapabilityFilterChange,
  configuredProviders,
  unconfiguredProviders,
  selectedProvider,
  onSelectProvider,
}: ProviderListPanelProps) {
  return (
    <Card className='overflow-hidden border-border/70'>
      <CardHeader className='pb-4'>
        <CardTitle>内置厂商</CardTitle>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='relative'>
          <Search className='pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
          <Input
            value={providerSearch}
            onChange={(event) => onProviderSearchChange(event.target.value)}
            placeholder='搜索厂商、协议或地址'
            className='pl-9'
            autoComplete='off'
          />
        </div>

        <div className='flex flex-wrap gap-2'>
          {providerCapabilityFilterOptions.map((option) => {
            const isActive = providerCapabilityFilter === option.value
            return (
              <button
                key={option.value}
                type='button'
                onClick={() => onProviderCapabilityFilterChange(option.value)}
                className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                  isActive
                    ? 'border-foreground bg-foreground text-background'
                    : 'border-border bg-muted/40 text-muted-foreground hover:bg-muted'
                }`}
              >
                {option.label}
              </button>
            )
          })}
        </div>

        <div className='space-y-5'>
          <ProviderSection
            title='已配置'
            description='已完成基础接入，可以继续测试连接、同步模型和设置默认值。'
            providers={configuredProviders}
            selectedProviderDefinitionId={selectedProvider?.provider_definition_id ?? null}
            onSelect={onSelectProvider}
          />
          <ProviderSection
            title='未配置'
            description='平台已内置这些厂商定义，但当前租户还没有完成配置。'
            providers={unconfiguredProviders}
            selectedProviderDefinitionId={selectedProvider?.provider_definition_id ?? null}
            onSelect={onSelectProvider}
          />
        </div>
      </CardContent>
    </Card>
  )
}
