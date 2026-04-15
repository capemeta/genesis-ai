import type { CapabilityOverrideConfig, CapabilityType } from '@/lib/api/model-platform'

export type ProviderEndpointType = 'official' | 'openai_compatible' | 'local' | 'proxy'

export type ProviderDraft = {
  baseUrl: string
  apiKey: string
  endpointType: ProviderEndpointType
  isEnabled: boolean
  isVisibleInUI: boolean
  capabilityBaseUrls: Record<string, string>
  capabilityOverrides: Record<string, CapabilityOverrideConfig>
}

export type ModelDraft = {
  modelAlias: string
  groupName: string
  contextWindow: string
  maxOutputTokens: string
  concurrencyLimit: string
}

export type DefaultCapabilityEntry = {
  capability: CapabilityType
  model: { tenant_model_id: string; display_name: string; provider_display_name: string } | null
  options: Array<{ tenant_model_id: string; display_name: string; provider_display_name: string }>
}

export type ManualModelForm = {
  modelKey: string
  rawModelName: string
  displayName: string
  modelType: CapabilityType
  capabilities: CapabilityType[]
  groupName: string
  contextWindow: string
  maxOutputTokens: string
  embeddingDimension: string
  adapterOverrideType: string
  implementationKeyOverride: string
  requestSchemaOverride: string
  endpointPathOverride: string
  runtimeBaseUrlOverride: string
  supportsMultimodalInput: boolean
  concurrencyLimit: string
}

export type CustomProviderForm = {
  displayName: string
  providerCode: string
  protocolType:
    | 'openai'
    | 'openai_compatible'
    | 'anthropic_native'
    | 'gemini_native'
    | 'azure_openai'
    | 'ollama'
    | 'vllm'
    | 'bedrock'
    | 'custom'
  endpointType: ProviderEndpointType
  baseUrl: string
  apiKey: string
  description: string
  capabilities: CapabilityType[]
  isEnabled: boolean
  isVisibleInUI: boolean
}
