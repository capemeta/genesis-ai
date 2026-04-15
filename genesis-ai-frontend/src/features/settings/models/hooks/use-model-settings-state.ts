import { useDeferredValue, useState } from 'react'
import type { CapabilityType } from '@/lib/api/model-platform'
import { emptyCustomProviderForm, emptyManualModelForm } from '../constants'
import type { ManualModelForm, ModelDraft, ProviderDraft } from '../types'

/**
 * 收敛页面本地状态，避免查询与动作逻辑直接和 UI 状态耦合。
 */
export function useModelSettingsState() {
  const [activeTab, setActiveTab] = useState<'providers' | 'defaults'>('providers')
  const [selectedProviderDefinitionId, setSelectedProviderDefinitionId] = useState('')
  const [providerSearch, setProviderSearch] = useState('')
  const [providerCapabilityFilter, setProviderCapabilityFilter] = useState<'all' | CapabilityType>('all')
  const [providerDrafts, setProviderDrafts] = useState<Record<string, ProviderDraft>>({})
  const [modelDrafts, setModelDrafts] = useState<Record<string, ModelDraft>>({})
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [customProviderForm, setCustomProviderForm] = useState(emptyCustomProviderForm)
  const [pendingModelActionKey, setPendingModelActionKey] = useState<string | null>(null)
  const [pendingBatchAction, setPendingBatchAction] = useState<
    'enable-all' | 'disable-all' | 'show-all' | 'hide-all' | null
  >(null)
  const [manualModelDialogOpen, setManualModelDialogOpen] = useState(false)
  const [manualModelForm, setManualModelForm] = useState<ManualModelForm>(emptyManualModelForm)
  const deferredProviderSearch = useDeferredValue(providerSearch)

  return {
    activeTab,
    setActiveTab,
    selectedProviderDefinitionId,
    setSelectedProviderDefinitionId,
    providerSearch,
    setProviderSearch,
    providerCapabilityFilter,
    setProviderCapabilityFilter,
    providerDrafts,
    setProviderDrafts,
    modelDrafts,
    setModelDrafts,
    createDialogOpen,
    setCreateDialogOpen,
    customProviderForm,
    setCustomProviderForm,
    pendingModelActionKey,
    setPendingModelActionKey,
    pendingBatchAction,
    setPendingBatchAction,
    manualModelDialogOpen,
    setManualModelDialogOpen,
    manualModelForm,
    setManualModelForm,
    deferredProviderSearch,
  }
}
