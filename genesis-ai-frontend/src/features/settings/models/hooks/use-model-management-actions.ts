import type { Dispatch, SetStateAction } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  batchUpdateTenantModelStates,
  createManualModel,
  type CapabilityType,
  type ModelSettingsProvider,
  upsertDefaultModel,
  updateTenantModelState,
} from '@/lib/api/model-platform'
import { emptyManualModelForm } from '../constants'
import type { ManualModelForm, ModelDraft } from '../types'
import { getErrorMessage } from '../utils'

type UseModelManagementActionsParams = {
  selectedProvider: ModelSettingsProvider | null
  manualModelForm: ManualModelForm
  setManualModelForm: Dispatch<SetStateAction<ManualModelForm>>
  setManualModelDialogOpen: (open: boolean) => void
  setModelDrafts: Dispatch<SetStateAction<Record<string, ModelDraft>>>
  setPendingModelActionKey: (key: string | null) => void
  setPendingBatchAction: (
    action: 'enable-all' | 'disable-all' | 'show-all' | 'hide-all' | null
  ) => void
}

/**
 * 处理模型层动作，包括启停、批量操作、默认模型与手动添加模型。
 */
export function useModelManagementActions({
  selectedProvider,
  manualModelForm,
  setManualModelForm,
  setManualModelDialogOpen,
  setModelDrafts,
  setPendingModelActionKey,
  setPendingBatchAction,
}: UseModelManagementActionsParams) {
  const queryClient = useQueryClient()

  const updateModelMutation = useMutation({
    mutationFn: updateTenantModelState,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model-platform-settings-overview'] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '模型更新失败'))
    },
    onSettled: () => {
      setPendingModelActionKey(null)
    },
  })

  const updateDefaultMutation = useMutation({
    mutationFn: upsertDefaultModel,
    onSuccess: (result) => {
      toast.success(result.detail)
      queryClient.invalidateQueries({ queryKey: ['model-platform-settings-overview'] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '默认模型保存失败'))
    },
  })

  const createManualModelMutation = useMutation({
    mutationFn: async (payload: {
      tenant_provider_id: string
      model_key: string
      raw_model_name: string
      display_name: string
      model_type: CapabilityType
      capabilities: CapabilityType[]
      group_name?: string
      adapter_override_type?: 'litellm' | 'native' | 'openai_sdk' | 'custom'
      implementation_key_override?: string
      request_schema_override?: string
      endpoint_path_override?: string
      model_runtime_config?: Record<string, unknown>
      context_window?: number
      max_output_tokens?: number
      embedding_dimension?: number
      rate_limit_config?: Record<string, unknown>
    }) => {
      await createManualModel({
        tenant_provider_id: payload.tenant_provider_id,
        model_key: payload.model_key,
        raw_model_name: payload.raw_model_name,
        display_name: payload.display_name,
        model_type: payload.model_type,
        capabilities: payload.capabilities,
        group_name: payload.group_name || undefined,
        adapter_override_type: payload.adapter_override_type,
        implementation_key_override: payload.implementation_key_override,
        request_schema_override: payload.request_schema_override,
        endpoint_path_override: payload.endpoint_path_override,
        context_window: payload.context_window,
        max_output_tokens: payload.max_output_tokens,
        embedding_dimension: payload.embedding_dimension,
        model_runtime_config: payload.model_runtime_config,
        rate_limit_config: payload.rate_limit_config,
        is_enabled: true,
        is_visible_in_ui: true,
      })
    },
    onSuccess: () => {
      toast.success('模型已添加')
      setManualModelDialogOpen(false)
      setManualModelForm(emptyManualModelForm)
      queryClient.invalidateQueries({ queryKey: ['model-platform-settings-overview'] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '模型添加失败'))
    },
  })

  const batchUpdateModelsMutation = useMutation({
    mutationFn: async (payload: { modelIds: string[]; patch: { is_enabled?: boolean; is_visible_in_ui?: boolean } }) => {
      await batchUpdateTenantModelStates({
        model_ids: payload.modelIds,
        ...payload.patch,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model-platform-settings-overview'] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, '批量模型操作失败'))
    },
    onSettled: () => {
      setPendingBatchAction(null)
    },
  })

  const buildManualModelRuntimeConfig = () => {
    const runtimeConfig: Record<string, unknown> = {}
    if (manualModelForm.runtimeBaseUrlOverride.trim()) {
      runtimeConfig.base_url_override = manualModelForm.runtimeBaseUrlOverride.trim()
    }
    if (manualModelForm.supportsMultimodalInput) {
      runtimeConfig.supports_multimodal_input = true
    }
    return Object.keys(runtimeConfig).length ? runtimeConfig : undefined
  }

  const parseOptionalPositiveInteger = (value: string, fieldName: string): number | undefined => {
    const normalizedValue = value.trim()
    if (!normalizedValue) {
      return undefined
    }
    const parsedValue = Number(normalizedValue)
    if (!Number.isInteger(parsedValue) || parsedValue <= 0) {
      throw new Error(`${fieldName}必须是正整数`)
    }
    return parsedValue
  }

  const buildModelRateLimitConfig = (concurrencyLimit: string): Record<string, unknown> | undefined => {
    const normalizedLimit = concurrencyLimit.trim()
    if (!normalizedLimit) {
      return undefined
    }
    const parsedLimit = Number(normalizedLimit)
    if (!Number.isInteger(parsedLimit) || parsedLimit <= 0) {
      throw new Error('模型并发上限必须是正整数')
    }
    return { concurrency_limit: parsedLimit }
  }

  const handleModelStateChange = (
    tenantModelId: string,
    patch: {
      model_alias?: string | null
      group_key?: string | null
      model_runtime_config?: Record<string, unknown>
      rate_limit_config?: Record<string, unknown>
      is_enabled?: boolean
      is_visible_in_ui?: boolean
    },
    successText: string
  ) => {
    setPendingModelActionKey(tenantModelId)
    updateModelMutation.mutate(
      { id: tenantModelId, ...patch },
      {
        onSuccess: () => toast.success(successText),
      }
    )
  }

  const handleModelDraftChange = (
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
  ) => {
    setModelDrafts((current) => ({
      ...current,
      [tenantModelId]: {
        modelAlias: current[tenantModelId]?.modelAlias ?? fallback.modelAlias,
        groupName: current[tenantModelId]?.groupName ?? fallback.groupName,
        contextWindow: current[tenantModelId]?.contextWindow ?? fallback.contextWindow,
        maxOutputTokens: current[tenantModelId]?.maxOutputTokens ?? fallback.maxOutputTokens,
        concurrencyLimit: current[tenantModelId]?.concurrencyLimit ?? fallback.concurrencyLimit,
        ...patch,
      },
    }))
  }

  const handleSaveModelMeta = (
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
  ) => {
    const nextAlias = draft.modelAlias.trim()
    const nextGroup = draft.groupName.trim()
    let nextRateLimitConfig: Record<string, unknown> | null = null
    const nextRuntimeConfig: Record<string, unknown> = { ...(fallback.modelRuntimeConfig ?? {}) }
    try {
      nextRateLimitConfig = buildModelRateLimitConfig(draft.concurrencyLimit) ?? {}
      const contextWindow = parseOptionalPositiveInteger(draft.contextWindow, '上下文窗口')
      const maxOutputTokens = parseOptionalPositiveInteger(draft.maxOutputTokens, '最大输出 Token')
      if (contextWindow && (draft.contextWindow !== fallback.contextWindow || 'context_window' in nextRuntimeConfig)) {
        nextRuntimeConfig.context_window = contextWindow
      } else if (draft.contextWindow !== fallback.contextWindow) {
        delete nextRuntimeConfig.context_window
      }
      if (maxOutputTokens && (draft.maxOutputTokens !== fallback.maxOutputTokens || 'max_output_tokens' in nextRuntimeConfig)) {
        nextRuntimeConfig.max_output_tokens = maxOutputTokens
      } else if (draft.maxOutputTokens !== fallback.maxOutputTokens) {
        delete nextRuntimeConfig.max_output_tokens
      }
    } catch (error) {
      toast.error(getErrorMessage(error, '模型参数配置无效'))
      return
    }
    handleModelStateChange(
      tenantModelId,
      {
        model_alias: nextAlias || fallback.modelAlias,
        group_key: nextGroup || null,
        model_runtime_config: nextRuntimeConfig,
        rate_limit_config: nextRateLimitConfig,
      },
      '模型展示信息已保存'
    )
    setModelDrafts((current) => {
      const next = { ...current }
      delete next[tenantModelId]
      return next
    })
  }

  const handleResetModelMeta = (tenantModelId: string) => {
    setModelDrafts((current) => {
      const next = { ...current }
      delete next[tenantModelId]
      return next
    })
  }

  const handleBatchModelAction = (
    action: 'enable-all' | 'disable-all' | 'show-all' | 'hide-all',
    models: ModelSettingsProvider['models']
  ) => {
    const modelIds = models.map((item) => item.tenant_model_id)
    if (!modelIds.length) {
      toast.info('当前厂商还没有可操作的模型')
      return
    }

    const patch =
      action === 'enable-all'
        ? { is_enabled: true }
        : action === 'disable-all'
          ? { is_enabled: false }
          : action === 'show-all'
            ? { is_visible_in_ui: true }
            : { is_visible_in_ui: false }

    const successText =
      action === 'enable-all'
        ? '当前厂商下的模型已全部启用'
        : action === 'disable-all'
          ? '当前厂商下的模型已全部禁用'
          : action === 'show-all'
            ? '当前厂商下的模型已全部显示'
            : '当前厂商下的模型已全部隐藏'

    setPendingBatchAction(action)
    batchUpdateModelsMutation.mutate(
      { modelIds, patch },
      {
        onSuccess: () => toast.success(successText),
      }
    )
  }

  const handleSetDefaultModel = (capability: CapabilityType, tenantModelId: string) => {
    updateDefaultMutation.mutate({
      capability_type: capability,
      tenant_model_id: tenantModelId === '__none__' ? null : tenantModelId,
    })
  }

  const handleSubmitManualModel = () => {
    if (!selectedProvider?.tenant_provider_id) {
      toast.error('请先保存厂商配置')
      return
    }
    if (!manualModelForm.modelKey.trim() || !manualModelForm.displayName.trim()) {
      toast.error('请填写模型名称')
      return
    }
    const normalizedCapabilities = Array.from(
      new Set([manualModelForm.modelType, ...manualModelForm.capabilities])
    )
    let rateLimitConfig: Record<string, unknown> | undefined
    let contextWindow: number | undefined
    let maxOutputTokens: number | undefined
    let embeddingDimension: number | undefined
    try {
      rateLimitConfig = buildModelRateLimitConfig(manualModelForm.concurrencyLimit)
      contextWindow = parseOptionalPositiveInteger(manualModelForm.contextWindow, '上下文窗口')
      maxOutputTokens = parseOptionalPositiveInteger(manualModelForm.maxOutputTokens, '最大输出 Token')
      embeddingDimension = parseOptionalPositiveInteger(manualModelForm.embeddingDimension, '向量维度')
    } catch (error) {
      toast.error(getErrorMessage(error, '模型参数配置无效'))
      return
    }
    createManualModelMutation.mutate({
      tenant_provider_id: selectedProvider.tenant_provider_id,
      model_key: manualModelForm.modelKey.trim(),
      raw_model_name: manualModelForm.rawModelName.trim() || manualModelForm.modelKey.trim(),
      display_name: manualModelForm.displayName.trim(),
      model_type: manualModelForm.modelType,
      capabilities: normalizedCapabilities,
      context_window: contextWindow,
      max_output_tokens: maxOutputTokens,
      embedding_dimension: embeddingDimension,
      group_name: manualModelForm.groupName.trim() || undefined,
      adapter_override_type: manualModelForm.adapterOverrideType
        ? (manualModelForm.adapterOverrideType as 'litellm' | 'native' | 'openai_sdk' | 'custom')
        : undefined,
      implementation_key_override: manualModelForm.implementationKeyOverride.trim() || undefined,
      request_schema_override: manualModelForm.requestSchemaOverride.trim() || undefined,
      endpoint_path_override: manualModelForm.endpointPathOverride.trim() || undefined,
      model_runtime_config: buildManualModelRuntimeConfig(),
      rate_limit_config: rateLimitConfig,
    })
  }

  return {
    updateModelMutation,
    updateDefaultMutation,
    createManualModelMutation,
    batchUpdateModelsMutation,
    handleModelStateChange,
    handleModelDraftChange,
    handleSaveModelMeta,
    handleResetModelMeta,
    handleBatchModelAction,
    handleSetDefaultModel,
    handleSubmitManualModel,
  }
}
