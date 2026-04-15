import { useMemo, useState } from 'react'
import { Loader2, Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { CompactModelTable } from '../shared'
import type { ProviderSettingsTabProps } from './types'

type ProviderModelsPanelProps = Pick<
  ProviderSettingsTabProps,
  | 'selectedProvider'
  | 'defaultModelMap'
  | 'modelDrafts'
  | 'pendingModelActionKey'
  | 'pendingBatchAction'
  | 'onBatchModelAction'
  | 'onOpenManualModelDialog'
  | 'onModelEnabledChange'
  | 'onModelVisibleChange'
  | 'onModelDraftChange'
  | 'onSaveModelMeta'
  | 'onResetModelMeta'
  | 'batchUpdatePending'
  | 'updateModelPending'
>

/**
 * 模型列表区域单独拆分，后续如需增加筛选或批量操作更容易演进。
 */
export function ProviderModelsPanel({
  selectedProvider,
  defaultModelMap,
  modelDrafts,
  pendingModelActionKey,
  pendingBatchAction,
  onBatchModelAction,
  onOpenManualModelDialog,
  onModelEnabledChange,
  onModelVisibleChange,
  onModelDraftChange,
  onSaveModelMeta,
  onResetModelMeta,
  batchUpdatePending,
  updateModelPending,
}: ProviderModelsPanelProps) {
  const [searchKeyword, setSearchKeyword] = useState('')
  const normalizedKeyword = searchKeyword.trim().toLowerCase()
  const filteredModels = useMemo(() => {
    const modelItems = selectedProvider?.models ?? []
    if (!normalizedKeyword) {
      return modelItems
    }
    return modelItems.filter((model) => {
      const searchable = [
        model.display_name,
        model.raw_model_name,
        model.group_name,
        model.model_type,
        ...(model.capabilities || []),
      ]
      return searchable.some((value) => String(value || '').toLowerCase().includes(normalizedKeyword))
    })
  }, [normalizedKeyword, selectedProvider?.models])

  if (!selectedProvider) {
    return null
  }

  return (
    <div className='space-y-4'>
      <div className='flex items-center justify-between'>
        <div className='space-y-1'>
          <h3 className='font-medium'>模型</h3>
          <p className='text-sm text-muted-foreground'>模型按家族分组展示。厂商启用后，模型仍可单独启用或隐藏。</p>
        </div>
        <div className='flex flex-wrap items-center justify-end gap-2'>
          <span className='text-sm text-muted-foreground'>
            共 {selectedProvider.models.length} 个
            {normalizedKeyword ? ` · 命中 ${filteredModels.length} 个` : ''}
          </span>
          <Button
            size='sm'
            variant='outline'
            onClick={() => onBatchModelAction('enable-all', selectedProvider.models)}
            disabled={batchUpdatePending}
          >
            {pendingBatchAction === 'enable-all' && <Loader2 className='mr-2 h-3.5 w-3.5 animate-spin' />}
            全部启用
          </Button>
          <Button
            size='sm'
            variant='outline'
            onClick={() => onBatchModelAction('disable-all', selectedProvider.models)}
            disabled={batchUpdatePending}
          >
            {pendingBatchAction === 'disable-all' && <Loader2 className='mr-2 h-3.5 w-3.5 animate-spin' />}
            全部禁用
          </Button>
          <Button
            size='sm'
            variant='outline'
            onClick={() => onBatchModelAction('show-all', selectedProvider.models)}
            disabled={batchUpdatePending}
          >
            {pendingBatchAction === 'show-all' && <Loader2 className='mr-2 h-3.5 w-3.5 animate-spin' />}
            全部显示
          </Button>
          <Button
            size='sm'
            variant='outline'
            onClick={() => onBatchModelAction('hide-all', selectedProvider.models)}
            disabled={batchUpdatePending}
          >
            {pendingBatchAction === 'hide-all' && <Loader2 className='mr-2 h-3.5 w-3.5 animate-spin' />}
            全部隐藏
          </Button>
          <Button size='sm' variant='outline' onClick={onOpenManualModelDialog}>
            <Plus className='mr-2 h-3.5 w-3.5' />
            添加模型
          </Button>
        </div>
      </div>

      <div className='relative max-w-md'>
        <Search className='pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
        <Input
          value={searchKeyword}
          onChange={(event) => setSearchKeyword(event.target.value)}
          placeholder='搜索模型：展示名、原始模型名、分组、能力'
          className='pl-9'
        />
      </div>

      <CompactModelTable
        models={filteredModels}
        defaultModelMap={defaultModelMap}
        modelDrafts={modelDrafts}
        pendingModelActionKey={pendingModelActionKey}
        onEnabledChange={onModelEnabledChange}
        onVisibleChange={onModelVisibleChange}
        onDraftChange={onModelDraftChange}
        onSaveMeta={onSaveModelMeta}
        onResetMeta={onResetModelMeta}
        isSaving={updateModelPending}
        forceExpandAll={Boolean(normalizedKeyword)}
      />
      {normalizedKeyword && filteredModels.length === 0 ? (
        <div className='rounded-xl border border-dashed p-6 text-sm text-muted-foreground'>没有匹配的模型，换个关键词试试。</div>
      ) : null}
    </div>
  )
}
