import { Loader2, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { emptyManualModelForm, providerCapabilityFilterOptions } from './constants'
import { CreateCustomProviderDialog } from './components/dialogs/create-custom-provider-dialog'
import { ManualModelDialog } from './components/dialogs/manual-model-dialog'
import { DefaultModelsTab } from './components/default-models-tab'
import { ProviderSettingsTab } from './components/provider-settings-tab'
import { useModelSettingsPage } from './hooks/use-model-settings-page'

export function ModelsPage() {
  const {
    activeTab,
    setActiveTab,
    providerSearch,
    setProviderSearch,
    providerCapabilityFilter,
    setProviderCapabilityFilter,
    setSelectedProviderDefinitionId,
    createDialogOpen,
    setCreateDialogOpen,
    customProviderForm,
    setCustomProviderForm,
    manualModelDialogOpen,
    setManualModelDialogOpen,
    manualModelForm,
    setManualModelForm,
    modelDrafts,
    pendingModelActionKey,
    pendingBatchAction,
    isLoading,
    isFetching,
    defaultModelMap,
    configuredProviders,
    unconfiguredProviders,
    selectedProvider,
    providerDraft,
    defaultCapabilityEntries,
    configurableCapabilityOverrides,
    isProviderDirty,
    saveProviderMutation,
    updateModelMutation,
    updateDefaultMutation,
    testProviderMutation,
    syncProviderMutation,
    createCustomProviderMutation,
    archiveCustomProviderMutation,
    createManualModelMutation,
    batchUpdateModelsMutation,
    handleProviderAction,
    handleCreateCustomProvider,
    handleToggleCustomCapability,
    handleSaveProvider,
    handleProviderToggle,
    handleCapabilityOverrideChange,
    handleCapabilityBaseUrlChange,
    handleModelStateChange,
    handleModelDraftChange,
    handleSaveModelMeta,
    handleResetModelMeta,
    handleBatchModelAction,
    handleSetDefaultModel,
    handleResetProviderDraft,
    handleSubmitManualModel,
    onProviderDraftChange,
  } = useModelSettingsPage()

  if (isLoading) {
    return (
      <div className='flex min-h-[420px] items-center justify-center'>
        <div className='flex items-center gap-3 text-sm text-muted-foreground'>
          <Loader2 className='h-4 w-4 animate-spin' />
          正在加载模型设置
        </div>
      </div>
    )
  }

  return (
    <div className='space-y-5'>
      <div className='flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between'>
        <div className='space-y-2'>
          <div>
            <h1 className='text-3xl font-bold tracking-tight'>模型服务</h1>
            <p className='mt-2 text-sm text-muted-foreground'>
              内置厂商直接从平台定义读取，配置密钥后即可同步模型；默认模型只来自当前真实可用配置。
            </p>
          </div>
        </div>

        <div className='flex items-center gap-2'>
          {isFetching && <Loader2 className='h-4 w-4 animate-spin text-muted-foreground' />}
          <Button variant='outline' onClick={() => handleProviderAction('create')}>
            <Plus className='mr-2 h-4 w-4' />
            添加自定义厂商
          </Button>
        </div>
      </div>

      <CreateCustomProviderDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        form={customProviderForm}
        onFormChange={setCustomProviderForm}
        onToggleCapability={handleToggleCustomCapability}
        onSubmit={handleCreateCustomProvider}
        isSubmitting={createCustomProviderMutation.isPending}
      />

      <ManualModelDialog
        open={manualModelDialogOpen}
        onOpenChange={setManualModelDialogOpen}
        form={manualModelForm}
        onFormChange={setManualModelForm}
        onCancel={() => {
          setManualModelDialogOpen(false)
          setManualModelForm(emptyManualModelForm)
        }}
        onSubmit={handleSubmitManualModel}
        isSubmitting={createManualModelMutation.isPending}
      />

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as typeof activeTab)} className='space-y-4'>
        <TabsList className='grid w-full grid-cols-2 lg:w-[220px]'>
          <TabsTrigger value='providers'>模型服务</TabsTrigger>
          <TabsTrigger value='defaults'>默认模型</TabsTrigger>
        </TabsList>

        <TabsContent value='providers'>
          <ProviderSettingsTab
            providerSearch={providerSearch}
            onProviderSearchChange={setProviderSearch}
            providerCapabilityFilterOptions={providerCapabilityFilterOptions}
            providerCapabilityFilter={providerCapabilityFilter}
            onProviderCapabilityFilterChange={setProviderCapabilityFilter}
            configuredProviders={configuredProviders}
            unconfiguredProviders={unconfiguredProviders}
            selectedProvider={selectedProvider}
            providerDraft={providerDraft}
            configurableCapabilityOverrides={configurableCapabilityOverrides}
            isProviderDirty={isProviderDirty}
            onSelectProvider={setSelectedProviderDefinitionId}
            onProviderDraftChange={onProviderDraftChange}
            onCapabilityBaseUrlChange={handleCapabilityBaseUrlChange}
            onCapabilityOverrideChange={handleCapabilityOverrideChange}
            onProviderToggle={handleProviderToggle}
            onSaveProvider={handleSaveProvider}
            onResetProviderDraft={handleResetProviderDraft}
            onProviderAction={handleProviderAction}
            onArchiveProvider={() =>
              selectedProvider &&
              archiveCustomProviderMutation.mutate({
                provider_definition_id: selectedProvider.provider_definition_id,
              })
            }
            onOpenManualModelDialog={() => setManualModelDialogOpen(true)}
            modelDrafts={modelDrafts}
            pendingModelActionKey={pendingModelActionKey}
            pendingBatchAction={pendingBatchAction}
            defaultModelMap={defaultModelMap}
            onBatchModelAction={handleBatchModelAction}
            onModelEnabledChange={(tenantModelId, checked) =>
              handleModelStateChange(tenantModelId, { is_enabled: checked }, checked ? '模型已启用' : '模型已禁用')
            }
            onModelVisibleChange={(tenantModelId, checked) =>
              handleModelStateChange(
                tenantModelId,
                { is_visible_in_ui: checked },
                checked ? '模型已对前端展示' : '模型已从前端隐藏'
              )
            }
            onModelDraftChange={handleModelDraftChange}
            onSaveModelMeta={handleSaveModelMeta}
            onResetModelMeta={handleResetModelMeta}
            saveProviderPending={saveProviderMutation.isPending}
            testProviderPending={testProviderMutation.isPending}
            syncProviderPending={syncProviderMutation.isPending}
            archiveProviderPending={archiveCustomProviderMutation.isPending}
            batchUpdatePending={batchUpdateModelsMutation.isPending}
            updateModelPending={updateModelMutation.isPending}
          />
        </TabsContent>

        <TabsContent value='defaults'>
          <DefaultModelsTab
            defaultCapabilityEntries={defaultCapabilityEntries}
            defaultModelMap={defaultModelMap}
            onSetDefaultModel={handleSetDefaultModel}
            isUpdating={updateDefaultMutation.isPending}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
