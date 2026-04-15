import type { Dispatch, SetStateAction } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  archiveCustomProvider,
  createCustomProvider,
  syncProviderModels,
  testProviderConnection,
  type CapabilityOverrideConfig,
  type CapabilityType,
  type ModelSettingsProvider,
  upsertModelProviderSettings,
} from '@/lib/api/model-platform'
import { emptyCustomProviderForm } from '../constants'
import type { CustomProviderForm, ProviderDraft } from '../types'
import { getErrorMessage } from '../utils'

type UseProviderSettingsActionsParams = {
  selectedProvider: ModelSettingsProvider | null
  providerDraft: ProviderDraft
  customProviderForm: CustomProviderForm
  setCustomProviderForm: Dispatch<SetStateAction<CustomProviderForm>>
  setCreateDialogOpen: (open: boolean) => void
  setSelectedProviderDefinitionId: (providerDefinitionId: string) => void
  setProviderDrafts: Dispatch<SetStateAction<Record<string, ProviderDraft>>>
}

/**
 * 处理厂商配置相关动作，包含基础配置、连接测试、同步与自定义厂商管理。
 */
export function useProviderSettingsActions({
  selectedProvider,
  providerDraft,
  customProviderForm,
  setCustomProviderForm,
  setCreateDialogOpen,
  setSelectedProviderDefinitionId,
  setProviderDrafts,
}: UseProviderSettingsActionsParams) {
  const queryClient = useQueryClient()

  const saveProviderMutation = useMutation({
    mutationFn: () => {
      if (!selectedProvider) {
        throw new Error('请选择厂商')
      }
      return upsertModelProviderSettings({
        provider_definition_id: selectedProvider.provider_definition_id,
        tenant_provider_id: selectedProvider.tenant_provider_id,
        endpoint_type: providerDraft.endpointType,
        base_url: providerDraft.baseUrl,
        api_key: providerDraft.apiKey.trim() ? providerDraft.apiKey.trim() : undefined,
        capability_base_urls: providerDraft.capabilityBaseUrls,
        capability_overrides: providerDraft.capabilityOverrides,
        is_enabled: providerDraft.isEnabled,
        is_visible_in_ui: providerDraft.isVisibleInUI,
      })
    },
    onSuccess: (result) => {
      toast.success(result.detail)
      if (selectedProvider) {
        setProviderDrafts((current) => {
          const next = { ...current }
          delete next[selectedProvider.provider_definition_id]
          return next
        })
      }
      queryClient.invalidateQueries({ queryKey: ['model-platform-settings-overview'] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '厂商配置保存失败'))
    },
  })

  const testProviderMutation = useMutation({
    mutationFn: testProviderConnection,
    onSuccess: (result) => {
      toast.success(`${result.detail}，发现 ${result.discovered_model_count} 个模型`)
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '连接测试失败'))
    },
  })

  const syncProviderMutation = useMutation({
    mutationFn: syncProviderModels,
    onSuccess: (result) => {
      toast.success(`${result.detail}，新增 ${result.added_count} 个模型`)
      queryClient.invalidateQueries({ queryKey: ['model-platform-settings-overview'] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '模型同步失败'))
    },
  })

  const createCustomProviderMutation = useMutation({
    mutationFn: createCustomProvider,
    onSuccess: (result) => {
      toast.success(result.detail)
      setCreateDialogOpen(false)
      setCustomProviderForm(emptyCustomProviderForm)
      queryClient.invalidateQueries({ queryKey: ['model-platform-settings-overview'] })
      setSelectedProviderDefinitionId(result.provider_definition_id)
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '自定义厂商创建失败'))
    },
  })

  const archiveCustomProviderMutation = useMutation({
    mutationFn: archiveCustomProvider,
    onSuccess: (result) => {
      toast.success(result.detail)
      queryClient.invalidateQueries({ queryKey: ['model-platform-settings-overview'] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '厂商归档失败'))
    },
  })

  const onProviderDraftChange = (updater: (draft: ProviderDraft) => ProviderDraft) => {
    if (!selectedProvider) return
    setProviderDrafts((current) => ({
      ...current,
      [selectedProvider.provider_definition_id]: updater(providerDraft),
    }))
  }

  const handleSaveProvider = () => {
    if (!selectedProvider) return
    if (!providerDraft.baseUrl.trim()) {
      toast.error('请先填写厂商接入地址')
      return
    }
    saveProviderMutation.mutate()
  }

  const handleProviderToggle = (field: 'isEnabled' | 'isVisibleInUI', checked: boolean) => {
    if (!selectedProvider) return
    onProviderDraftChange((current) => ({ ...current, [field]: checked }))
  }

  const handleCapabilityOverrideChange = (capability: CapabilityType, patch: Partial<CapabilityOverrideConfig>) => {
    if (!selectedProvider) return
    const currentConfig = providerDraft.capabilityOverrides[capability] || {}
    const nextConfig = { ...currentConfig, ...patch }
    const normalizedConfig = Object.fromEntries(
      Object.entries(nextConfig).filter(([, value]) => value !== '' && value !== undefined && value !== null)
    ) as CapabilityOverrideConfig
    onProviderDraftChange((current) => ({
      ...current,
      capabilityOverrides:
        Object.keys(normalizedConfig).length > 0
          ? {
              ...current.capabilityOverrides,
              [capability]: normalizedConfig,
            }
          : Object.fromEntries(Object.entries(current.capabilityOverrides).filter(([key]) => key !== capability)),
    }))
  }

  const handleCapabilityBaseUrlChange = (capability: CapabilityType, value: string) => {
    if (!selectedProvider) return
    const normalizedValue = value.trim()
    onProviderDraftChange((current) => ({
      ...current,
      capabilityBaseUrls: normalizedValue
        ? {
            ...current.capabilityBaseUrls,
            [capability]: value,
          }
        : Object.fromEntries(Object.entries(current.capabilityBaseUrls).filter(([key]) => key !== capability)),
    }))
  }

  const handleProviderAction = (action: 'create' | 'sync' | 'test') => {
    if (action === 'create') {
      setCreateDialogOpen(true)
      return
    }
    if (!selectedProvider?.tenant_provider_id) {
      toast.info('请先保存厂商配置，再执行连接测试或模型同步。')
      return
    }
    if (action === 'test') {
      testProviderMutation.mutate(selectedProvider.tenant_provider_id)
      return
    }
    syncProviderMutation.mutate(selectedProvider.tenant_provider_id)
  }

  const handleCreateCustomProvider = () => {
    if (!customProviderForm.displayName.trim()) {
      toast.error('请填写厂商名称')
      return
    }
    if (!customProviderForm.baseUrl.trim()) {
      toast.error('请填写接入地址')
      return
    }
    if (!customProviderForm.capabilities.length) {
      toast.error('请至少选择一种能力')
      return
    }
    createCustomProviderMutation.mutate({
      display_name: customProviderForm.displayName.trim(),
      provider_code: customProviderForm.providerCode.trim() || undefined,
      protocol_type: customProviderForm.protocolType,
      endpoint_type: customProviderForm.endpointType,
      base_url: customProviderForm.baseUrl.trim(),
      api_key: customProviderForm.apiKey.trim() || undefined,
      description: customProviderForm.description.trim() || undefined,
      supported_capabilities: customProviderForm.capabilities,
      is_enabled: customProviderForm.isEnabled,
      is_visible_in_ui: customProviderForm.isVisibleInUI,
    })
  }

  const handleToggleCustomCapability = (capability: CapabilityType) => {
    setCustomProviderForm((current) => {
      const exists = current.capabilities.includes(capability)
      return {
        ...current,
        capabilities: exists
          ? current.capabilities.filter((item) => item !== capability)
          : [...current.capabilities, capability],
      }
    })
  }

  const handleResetProviderDraft = () => {
    if (!selectedProvider) return
    setProviderDrafts((current) => {
      const next = { ...current }
      delete next[selectedProvider.provider_definition_id]
      return next
    })
  }

  return {
    saveProviderMutation,
    testProviderMutation,
    syncProviderMutation,
    createCustomProviderMutation,
    archiveCustomProviderMutation,
    onProviderDraftChange,
    handleSaveProvider,
    handleProviderToggle,
    handleCapabilityOverrideChange,
    handleCapabilityBaseUrlChange,
    handleProviderAction,
    handleCreateCustomProvider,
    handleToggleCustomCapability,
    handleResetProviderDraft,
  }
}
