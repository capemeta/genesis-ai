import { useState } from 'react'
import { Bug, Copy, KeyRound, Link2, Loader2, RefreshCw, Save } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { FieldPanel, InlineSwitch, ProviderAvatar, ProviderCapabilityBadge } from '../shared'
import { formatDateTime } from '../../utils'
import { ModelDebugPanel } from './model-debug-panel'
import { ProviderCapabilityOverrides } from './provider-capability-overrides'
import { ProviderModelsPanel } from './provider-models-panel'
import type { ProviderSettingsTabProps } from './types'

type ProviderDetailPanelProps = Omit<
  ProviderSettingsTabProps,
  | 'providerSearch'
  | 'onProviderSearchChange'
  | 'providerCapabilityFilterOptions'
  | 'providerCapabilityFilter'
  | 'onProviderCapabilityFilterChange'
  | 'configuredProviders'
  | 'unconfiguredProviders'
  | 'onSelectProvider'
>

/**
 * 右侧详情专注于当前厂商的配置与模型管理。
 */
export function ProviderDetailPanel({
  selectedProvider,
  providerDraft,
  configurableCapabilityOverrides,
  isProviderDirty,
  onProviderDraftChange,
  onCapabilityBaseUrlChange,
  onCapabilityOverrideChange,
  onProviderToggle,
  onSaveProvider,
  onResetProviderDraft,
  onProviderAction,
  onArchiveProvider,
  onOpenManualModelDialog,
  modelDrafts,
  pendingModelActionKey,
  pendingBatchAction,
  defaultModelMap,
  onBatchModelAction,
  onModelEnabledChange,
  onModelVisibleChange,
  onModelDraftChange,
  onSaveModelMeta,
  onResetModelMeta,
  saveProviderPending,
  testProviderPending,
  syncProviderPending,
  archiveProviderPending,
  batchUpdatePending,
  updateModelPending,
}: ProviderDetailPanelProps) {
  const [debugSheetOpen, setDebugSheetOpen] = useState(false)

  return (
    <>
      <Card className='border-border/70'>
        <CardHeader className='pb-4'>
          <div className='flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between'>
            <div className='flex items-center gap-3'>
              {selectedProvider && <ProviderAvatar name={selectedProvider.display_name} large />}
              <div className='space-y-1'>
                <CardTitle>{selectedProvider?.display_name ?? '请选择厂商实例'}</CardTitle>
                <CardDescription>
                  {selectedProvider ? '配置厂商连接信息后，同步模型并按分组管理启用状态。' : '左侧选择一个厂商实例查看详情。'}
                </CardDescription>
              </div>
            </div>
            {selectedProvider && (
              <div className='flex flex-wrap items-center gap-3'>
                <Badge variant='outline'>{selectedProvider.protocol_type}</Badge>
                <Badge variant='outline'>{selectedProvider.provider_code}</Badge>
                {selectedProvider.runtime_supported_capabilities.map((capability) => (
                  <ProviderCapabilityBadge
                    key={`${selectedProvider.provider_definition_id}-detail-${capability}`}
                    capability={capability}
                  />
                ))}
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className='space-y-5'>
          {selectedProvider ? (
            <>
              <div className='grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]'>
                <FieldPanel icon={KeyRound} label='API 密钥'>
                  <Input
                    value={providerDraft.apiKey}
                    onChange={(event) =>
                      onProviderDraftChange((current) => ({
                        ...current,
                        apiKey: event.target.value,
                      }))
                    }
                    placeholder={selectedProvider.has_primary_credential ? '留空则保持现有密钥不变' : '输入 API Key 或访问令牌'}
                    type='password'
                    autoComplete='new-password'
                  />
                  {selectedProvider.has_primary_credential && (
                    <p className='text-xs text-muted-foreground'>
                      当前已配置密钥
                      {selectedProvider.credential_masked_summary
                        ? `：${selectedProvider.credential_masked_summary}`
                        : '，留空则保持不变'}
                    </p>
                  )}
                </FieldPanel>
                <FieldPanel icon={Link2} label='API 地址'>
                  <div className='relative'>
                    <Input
                      value={providerDraft.baseUrl}
                      onChange={(event) =>
                        onProviderDraftChange((current) => ({
                          ...current,
                          baseUrl: event.target.value,
                        }))
                      }
                      placeholder='输入服务地址'
                      disabled={!selectedProvider.is_base_url_editable}
                      className='pr-10'
                    />
                    {providerDraft.baseUrl && (
                      <Button
                        size='sm'
                        variant='ghost'
                        className='absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 p-0'
                        onClick={() => {
                          navigator.clipboard.writeText(providerDraft.baseUrl)
                          toast.success('已复制到剪贴板')
                        }}
                      >
                        <Copy className='h-4 w-4' />
                      </Button>
                    )}
                  </div>
                  {!selectedProvider.is_base_url_editable && (
                    <p className='text-xs text-muted-foreground'>该厂商的默认地址由后端统一维护，前端不可修改。</p>
                  )}
                </FieldPanel>
              </div>

              <ProviderCapabilityOverrides
                selectedProvider={selectedProvider}
                providerDraft={providerDraft}
                configurableCapabilityOverrides={configurableCapabilityOverrides}
                onCapabilityBaseUrlChange={onCapabilityBaseUrlChange}
                onCapabilityOverrideChange={onCapabilityOverrideChange}
              />

              <div className='flex flex-wrap items-center gap-3 rounded-2xl border bg-muted/20 px-4 py-3'>
                <InlineSwitch
                  label='启用厂商'
                  checked={providerDraft.isEnabled}
                  onCheckedChange={(checked) => onProviderToggle('isEnabled', checked)}
                  compact
                />
                <InlineSwitch
                  label='前端可见'
                  checked={providerDraft.isVisibleInUI}
                  onCheckedChange={(checked) => onProviderToggle('isVisibleInUI', checked)}
                  compact
                />
                <span className='text-sm text-muted-foreground'>状态：{selectedProvider.is_configured ? '已配置' : '待配置'}</span>
                {selectedProvider.has_primary_credential && (
                  <span className='text-sm text-muted-foreground'>密钥：{selectedProvider.credential_masked_summary ?? '已配置'}</span>
                )}
                <span className='text-sm text-muted-foreground'>
                  最近同步：{selectedProvider.last_sync_at ? formatDateTime(selectedProvider.last_sync_at) : '尚未同步'}
                </span>
                {selectedProvider.supported_capabilities.length > selectedProvider.runtime_supported_capabilities.length && (
                  <span className='text-sm text-amber-700'>
                    已按当前平台实现收敛可运行能力，部分声明能力需要额外适配后才能调用
                  </span>
                )}
                {isProviderDirty && <span className='text-sm text-amber-700'>当前有未保存修改</span>}
              </div>
              <p className='text-xs leading-5 text-muted-foreground'>
                “启用厂商”会影响模型实际调用；“前端可见”会影响聊天等业务页面是否展示该厂商下的模型候选，但不会删除厂商和模型配置。
              </p>

              <div className='flex flex-wrap gap-2'>
                <Button onClick={onSaveProvider} disabled={saveProviderPending || !isProviderDirty}>
                  {saveProviderPending ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <Save className='mr-2 h-4 w-4' />}
                  {selectedProvider.tenant_provider_id ? '更新配置' : '保存配置'}
                </Button>
                <Button variant='outline' onClick={onResetProviderDraft} disabled={!isProviderDirty}>
                  重置修改
                </Button>
                <Button variant='outline' onClick={() => onProviderAction('test')} disabled={testProviderPending}>
                  {testProviderPending && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
                  测试连接
                </Button>
                <Button variant='outline' onClick={() => onProviderAction('sync')} disabled={syncProviderPending}>
                  {syncProviderPending ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <RefreshCw className='mr-2 h-4 w-4' />}
                  同步模型
                </Button>
                <Button variant='outline' onClick={() => setDebugSheetOpen(true)}>
                  <Bug className='mr-2 h-4 w-4' />
                  路由调试
                </Button>
                {!selectedProvider.is_builtin && (
                  <Button variant='outline' onClick={onArchiveProvider} disabled={archiveProviderPending}>
                    {archiveProviderPending && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
                    归档厂商
                  </Button>
                )}
              </div>

              <Separator />

              <ProviderModelsPanel
                selectedProvider={selectedProvider}
                defaultModelMap={defaultModelMap}
                modelDrafts={modelDrafts}
                pendingModelActionKey={pendingModelActionKey}
                pendingBatchAction={pendingBatchAction}
                onBatchModelAction={onBatchModelAction}
                onOpenManualModelDialog={onOpenManualModelDialog}
                onModelEnabledChange={onModelEnabledChange}
                onModelVisibleChange={onModelVisibleChange}
                onModelDraftChange={onModelDraftChange}
                onSaveModelMeta={onSaveModelMeta}
                onResetModelMeta={onResetModelMeta}
                batchUpdatePending={batchUpdatePending}
                updateModelPending={updateModelPending}
              />
            </>
          ) : (
            <div className='rounded-2xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground'>
              暂无可查看的厂商定义
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet open={debugSheetOpen} onOpenChange={setDebugSheetOpen}>
        <SheetContent side='right' className='flex w-full flex-col gap-0 p-0 sm:max-w-3xl'>
          <SheetHeader className='border-b px-6 py-5 text-start'>
            <SheetTitle>路由调试</SheetTitle>
            <SheetDescription>
              调试能力路由、最小请求和模型级覆盖，避免打断当前厂商配置与模型管理流程。
            </SheetDescription>
          </SheetHeader>
          <div className='flex-1 overflow-y-auto p-6'>
            {selectedProvider ? <ModelDebugPanel selectedProvider={selectedProvider} /> : null}
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}
