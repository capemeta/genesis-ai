import type { CapabilityOverrideConfig, CapabilityType, ModelSettingsProvider } from '@/lib/api/model-platform'
import type { ModelDraft, ProviderDraft } from '../../types'

export type ProviderSettingsTabProps = {
  providerSearch: string
  onProviderSearchChange: (value: string) => void
  providerCapabilityFilterOptions: Array<{ value: 'all' | CapabilityType; label: string }>
  providerCapabilityFilter: 'all' | CapabilityType
  onProviderCapabilityFilterChange: (value: 'all' | CapabilityType) => void
  configuredProviders: ModelSettingsProvider[]
  unconfiguredProviders: ModelSettingsProvider[]
  selectedProvider: ModelSettingsProvider | null
  providerDraft: ProviderDraft
  configurableCapabilityOverrides: CapabilityType[]
  isProviderDirty: boolean
  onSelectProvider: (providerDefinitionId: string) => void
  onProviderDraftChange: (updater: (draft: ProviderDraft) => ProviderDraft) => void
  onCapabilityBaseUrlChange: (capability: CapabilityType, value: string) => void
  onCapabilityOverrideChange: (capability: CapabilityType, patch: Partial<CapabilityOverrideConfig>) => void
  onProviderToggle: (field: 'isEnabled' | 'isVisibleInUI', checked: boolean) => void
  onSaveProvider: () => void
  onResetProviderDraft: () => void
  onProviderAction: (action: 'sync' | 'test') => void
  onArchiveProvider: () => void
  onOpenManualModelDialog: () => void
  modelDrafts: Record<string, ModelDraft>
  pendingModelActionKey: string | null
  pendingBatchAction: 'enable-all' | 'disable-all' | 'show-all' | 'hide-all' | null
  defaultModelMap: Map<string, string>
  onBatchModelAction: (action: 'enable-all' | 'disable-all' | 'show-all' | 'hide-all', models: ModelSettingsProvider['models']) => void
  onModelEnabledChange: (tenantModelId: string, checked: boolean) => void
  onModelVisibleChange: (tenantModelId: string, checked: boolean) => void
  onModelDraftChange: (
    tenantModelId: string,
    patch: Partial<ModelDraft>,
    fallback: {
      modelAlias: string
      groupName: string
      contextWindow: string
      maxOutputTokens: string
      concurrencyLimit: string
      modelRuntimeConfig?: Record<string, unknown>
    }
  ) => void
  onSaveModelMeta: (
    tenantModelId: string,
    draft: ModelDraft,
    fallback: {
      modelAlias: string
      groupName: string
      contextWindow: string
      maxOutputTokens: string
      concurrencyLimit: string
      modelRuntimeConfig?: Record<string, unknown>
    }
  ) => void
  onResetModelMeta: (tenantModelId: string) => void
  saveProviderPending: boolean
  testProviderPending: boolean
  syncProviderPending: boolean
  archiveProviderPending: boolean
  batchUpdatePending: boolean
  updateModelPending: boolean
}
