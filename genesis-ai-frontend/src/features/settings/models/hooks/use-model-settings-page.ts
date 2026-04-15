import { useModelSettingsActions } from './use-model-settings-actions'
import { useModelSettingsOverview } from './use-model-settings-overview'
import { useModelSettingsState } from './use-model-settings-state'

/**
 * 页面级组合 Hook，只负责拼装状态、查询结果与动作。
 */
export function useModelSettingsPage() {
  const state = useModelSettingsState()
  const overview = useModelSettingsOverview({
    deferredProviderSearch: state.deferredProviderSearch,
    providerCapabilityFilter: state.providerCapabilityFilter,
    selectedProviderDefinitionId: state.selectedProviderDefinitionId,
    providerDrafts: state.providerDrafts,
  })
  const actions = useModelSettingsActions({
    selectedProvider: overview.selectedProvider,
    providerDraft: overview.providerDraft,
    customProviderForm: state.customProviderForm,
    setCustomProviderForm: state.setCustomProviderForm,
    setCreateDialogOpen: state.setCreateDialogOpen,
    manualModelForm: state.manualModelForm,
    setManualModelForm: state.setManualModelForm,
    setManualModelDialogOpen: state.setManualModelDialogOpen,
    setSelectedProviderDefinitionId: state.setSelectedProviderDefinitionId,
    setProviderDrafts: state.setProviderDrafts,
    setModelDrafts: state.setModelDrafts,
    setPendingModelActionKey: state.setPendingModelActionKey,
    setPendingBatchAction: state.setPendingBatchAction,
  })

  return {
    ...state,
    ...overview,
    ...actions,
  }
}
