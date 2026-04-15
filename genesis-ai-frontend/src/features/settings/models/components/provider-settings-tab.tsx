import { ProviderDetailPanel } from './provider-settings/provider-detail-panel'
import { ProviderListPanel } from './provider-settings/provider-list-panel'
import type { ProviderSettingsTabProps } from './provider-settings/types'

/**
 * 厂商设置页只负责布局拼装，具体内容交给左右面板实现。
 */
export function ProviderSettingsTab(props: ProviderSettingsTabProps) {
  return (
    <div className='grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)] 2xl:grid-cols-[420px_minmax(0,1fr)]'>
      <ProviderListPanel {...props} />
      <ProviderDetailPanel {...props} />
    </div>
  )
}
