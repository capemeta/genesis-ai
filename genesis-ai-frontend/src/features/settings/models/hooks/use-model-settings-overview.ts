import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchModelSettingsOverview,
  type CapabilityType,
} from '@/lib/api/model-platform'
import { capabilityMeta, capabilityUrlOverrideCandidates, emptyDraft, hiddenProviderCodes } from '../constants'
import type { DefaultCapabilityEntry, ProviderDraft } from '../types'
import { getProviderCapabilities } from '../utils'

type UseModelSettingsOverviewParams = {
  deferredProviderSearch: string
  providerCapabilityFilter: 'all' | CapabilityType
  selectedProviderDefinitionId: string
  providerDrafts: Record<string, ProviderDraft>
}

/**
 * 统一收敛页面查询结果与派生数据，避免动作层重复推导。
 */
export function useModelSettingsOverview({
  deferredProviderSearch,
  providerCapabilityFilter,
  selectedProviderDefinitionId,
  providerDrafts,
}: UseModelSettingsOverviewParams) {
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['model-platform-settings-overview'],
    queryFn: fetchModelSettingsOverview,
  })

  const providers = useMemo(
    () => (data?.providers ?? []).filter((provider) => !hiddenProviderCodes.has(provider.provider_code)),
    [data?.providers]
  )

  const defaultModelMap = useMemo(
    () => new Map((data?.default_models ?? []).map((item) => [item.capability_type, item.tenant_model_id])),
    [data?.default_models]
  )

  const filteredProviders = useMemo(() => {
    const keyword = deferredProviderSearch.trim().toLowerCase()
    return providers.filter((provider) => {
      const matchesKeyword =
        !keyword ||
        [provider.display_name, provider.provider_code, provider.protocol_type, provider.base_url]
          .join(' ')
          .toLowerCase()
          .includes(keyword)
      if (!matchesKeyword) return false
      if (providerCapabilityFilter === 'all') return true
      return getProviderCapabilities(provider).includes(providerCapabilityFilter)
    })
  }, [deferredProviderSearch, providerCapabilityFilter, providers])

  const configuredProviders = useMemo(
    () => filteredProviders.filter((provider) => provider.is_configured),
    [filteredProviders]
  )

  const unconfiguredProviders = useMemo(
    () => filteredProviders.filter((provider) => !provider.is_configured),
    [filteredProviders]
  )

  const effectiveSelectedProviderDefinitionId =
    providers.some((provider) => provider.provider_definition_id === selectedProviderDefinitionId)
      ? selectedProviderDefinitionId
      : providers[0]?.provider_definition_id ?? ''

  const selectedProvider = useMemo(
    () =>
      providers.find((provider) => provider.provider_definition_id === effectiveSelectedProviderDefinitionId) ??
      filteredProviders[0] ??
      null,
    [effectiveSelectedProviderDefinitionId, filteredProviders, providers]
  )

  const providerDraft = useMemo(() => {
    if (!selectedProvider) return emptyDraft
    return (
      providerDrafts[selectedProvider.provider_definition_id] ?? {
        baseUrl: selectedProvider.base_url,
        apiKey: '',
        endpointType: selectedProvider.endpoint_type,
        isEnabled: selectedProvider.is_enabled,
        isVisibleInUI: selectedProvider.is_visible_in_ui,
        capabilityBaseUrls: selectedProvider.capability_base_urls || {},
        capabilityOverrides: selectedProvider.capability_overrides || {},
      }
    )
  }, [providerDrafts, selectedProvider])

  const configuredModels = useMemo(
    () =>
      providers
        .filter((provider) => provider.is_configured && provider.is_enabled)
        .flatMap((provider) =>
          provider.models
            .filter((model) => model.is_enabled)
            .map((model) => ({
              ...model,
              provider_display_name: provider.display_name,
            }))
        ),
    [providers]
  )

  const defaultCapabilityEntries = useMemo<DefaultCapabilityEntry[]>(
    () =>
      (Object.keys(capabilityMeta) as CapabilityType[]).map((capability) => {
        const options = configuredModels
          .filter((item) => item.capabilities.includes(capability))
          .filter(
            (item, index, items) =>
              items.findIndex((candidate) => candidate.tenant_model_id === item.tenant_model_id) === index
          )
          .sort((left, right) => {
            const providerOrder = left.provider_display_name.localeCompare(right.provider_display_name, 'zh-CN')
            if (providerOrder !== 0) {
              return providerOrder
            }
            return left.display_name.localeCompare(right.display_name, 'zh-CN')
          })
        const tenantModelId = defaultModelMap.get(capability) ?? null
        const model = options.find((item) => item.tenant_model_id === tenantModelId) ?? null
        return { capability, model, options }
      }),
    [configuredModels, defaultModelMap]
  )

  const isProviderDirty = useMemo(() => {
    if (!selectedProvider) return false
    const currentBaseUrls = selectedProvider.capability_base_urls || {}
    const draftBaseUrls = providerDraft.capabilityBaseUrls
    const baseUrlsChanged = JSON.stringify(currentBaseUrls) !== JSON.stringify(draftBaseUrls)
    const currentCapabilityOverrides = selectedProvider.capability_overrides || {}
    const capabilityOverridesChanged =
      JSON.stringify(currentCapabilityOverrides) !== JSON.stringify(providerDraft.capabilityOverrides)
    return (
      providerDraft.baseUrl !== selectedProvider.base_url ||
      providerDraft.endpointType !== selectedProvider.endpoint_type ||
      providerDraft.isEnabled !== selectedProvider.is_enabled ||
      providerDraft.isVisibleInUI !== selectedProvider.is_visible_in_ui ||
      providerDraft.apiKey.trim().length > 0 ||
      baseUrlsChanged ||
      capabilityOverridesChanged
    )
  }, [providerDraft, selectedProvider])

  const configurableCapabilityOverrides = useMemo(
    () =>
      capabilityUrlOverrideCandidates.filter((capability) => selectedProvider?.runtime_supported_capabilities.includes(capability)),
    [selectedProvider]
  )

  return {
    isLoading,
    isFetching,
    providers,
    defaultModelMap,
    configuredProviders,
    unconfiguredProviders,
    selectedProvider,
    providerDraft,
    defaultCapabilityEntries,
    isProviderDirty,
    configurableCapabilityOverrides,
  }
}
