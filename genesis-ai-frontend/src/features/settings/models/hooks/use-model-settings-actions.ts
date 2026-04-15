import type { Dispatch, SetStateAction } from 'react'
import type { CustomProviderForm, ManualModelForm, ModelDraft, ProviderDraft } from '../types'
import type { ModelSettingsProvider } from '@/lib/api/model-platform'
import { useModelManagementActions } from './use-model-management-actions'
import { useProviderSettingsActions } from './use-provider-settings-actions'

type UseModelSettingsActionsParams = {
  selectedProvider: ModelSettingsProvider | null
  providerDraft: ProviderDraft
  customProviderForm: CustomProviderForm
  setCustomProviderForm: Dispatch<SetStateAction<CustomProviderForm>>
  setCreateDialogOpen: (open: boolean) => void
  manualModelForm: ManualModelForm
  setManualModelForm: Dispatch<SetStateAction<ManualModelForm>>
  setManualModelDialogOpen: (open: boolean) => void
  setSelectedProviderDefinitionId: (providerDefinitionId: string) => void
  setProviderDrafts: Dispatch<SetStateAction<Record<string, ProviderDraft>>>
  setModelDrafts: Dispatch<SetStateAction<Record<string, ModelDraft>>>
  setPendingModelActionKey: (key: string | null) => void
  setPendingBatchAction: (
    action: 'enable-all' | 'disable-all' | 'show-all' | 'hide-all' | null
  ) => void
}

/**
 * 聚合厂商动作与模型动作，供页面层保持稳定出口。
 */
export function useModelSettingsActions(params: UseModelSettingsActionsParams) {
  const providerActions = useProviderSettingsActions({
    selectedProvider: params.selectedProvider,
    providerDraft: params.providerDraft,
    customProviderForm: params.customProviderForm,
    setCustomProviderForm: params.setCustomProviderForm,
    setCreateDialogOpen: params.setCreateDialogOpen,
    setSelectedProviderDefinitionId: params.setSelectedProviderDefinitionId,
    setProviderDrafts: params.setProviderDrafts,
  })

  const modelActions = useModelManagementActions({
    selectedProvider: params.selectedProvider,
    manualModelForm: params.manualModelForm,
    setManualModelForm: params.setManualModelForm,
    setManualModelDialogOpen: params.setManualModelDialogOpen,
    setModelDrafts: params.setModelDrafts,
    setPendingModelActionKey: params.setPendingModelActionKey,
    setPendingBatchAction: params.setPendingBatchAction,
  })

  return {
    ...providerActions,
    ...modelActions,
  }
}
