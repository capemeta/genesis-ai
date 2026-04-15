import type { CapabilityType, ModelSettingsProvider } from '@/lib/api/model-platform'

export function findProviderNameByModel(providers: ModelSettingsProvider[], tenantModelId: string): string {
  const provider = providers.find((item) => item.models.some((model) => model.tenant_model_id === tenantModelId))
  return provider?.display_name ?? '未知厂商'
}

export function getProviderCapabilities(provider: ModelSettingsProvider): CapabilityType[] {
  const modelCapabilities = provider.models.flatMap((model) => model.capabilities)
  const mergedCapabilities = modelCapabilities.length ? modelCapabilities : provider.runtime_supported_capabilities
  return Array.from(new Set(mergedCapabilities))
}

export function getProviderCapabilityLabel(capability: CapabilityType): string {
  switch (capability) {
    case 'chat':
      return 'LLM'
    case 'embedding':
      return 'Embedding'
    case 'rerank':
      return 'Rerank'
    case 'tts':
      return 'TTS'
    case 'asr':
      return 'ASR'
    case 'vision':
      return 'VLM'
    case 'ocr':
      return 'OCR'
    case 'document_parse':
      return 'Parse'
    case 'image':
      return 'Image'
    case 'video':
      return 'Video'
    default:
      return capability
  }
}

export function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

export function getErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null) {
    const maybeError = error as {
      response?: {
        data?: {
          message?: string
          detail?: string
        }
      }
      message?: string
    }
    return maybeError.response?.data?.message || maybeError.response?.data?.detail || maybeError.message || fallback
  }
  return fallback
}
