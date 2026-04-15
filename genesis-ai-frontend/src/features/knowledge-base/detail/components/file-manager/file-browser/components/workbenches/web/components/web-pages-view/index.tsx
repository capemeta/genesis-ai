/**
 * 网页页面视图主组件
 */

import { useState, useEffect, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useMutation } from '@tanstack/react-query'
import type { WebPageItem, WebPagePreviewResponse } from '@/lib/api/web-sync'
import { previewWebPageExtract } from '@/lib/api/web-sync'
import { fetchFolderPath } from '@/lib/api/folder'
import type { ScheduleFormState } from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/shared/schedule-rule-builder'
import type { FetchMode } from '../../types'
import { useWebPages, useWebSchedules, usePageSchedule, useSelectedPageRuns } from '../../hooks'
import {
  useCreatePageMutation,
  useUpdatePageMutation,
  useDeletePageMutation,
  useSaveScheduleMutation,
  useDeleteScheduleMutation,
  useLatestCheckMutation,
  useSyncNowMutation,
} from '../../hooks'
import {
  fromSchedule,
  isScheduleFormSameAsKbDefault,
  buildSchedulePayload,
  getWebPageConfigDraft,
} from '../../utils'
import { PageListSidebar } from './page-list-sidebar'
import { PageDetailPanel } from './page-detail-panel'
import {
  AddPageDialog,
  EditPageDialog,
  DeletePageDialog,
  PreviewExtractDialog,
  RecentRunsDialog,
  SyncNowConfirmDialog,
} from '../dialogs'

export interface WebPagesViewProps {
  kbId: string
  selectedFolderId: string | null
}

export function WebPagesView({ kbId, selectedFolderId }: WebPagesViewProps) {
  const queryClient = useQueryClient()

  // 列表状态
  const [pageSearchKeyword, setPageSearchKeyword] = useState('')
  const [pageListPage, setPageListPage] = useState(1)
  const [includeSubfolders, setIncludeSubfolders] = useState(true)

  // 选中页面
  const [selectedPageId, setSelectedPageId] = useState('')

  // 弹窗状态
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [editingPage, setEditingPage] = useState<WebPageItem | null>(null)
  const [deletingPage, setDeletingPage] = useState<WebPageItem | null>(null)
  const [syncNowConfirmOpen, setSyncNowConfirmOpen] = useState(false)
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false)
  const [previewResult, setPreviewResult] = useState<WebPagePreviewResponse | null>(null)
  const [recentRunsOpen, setRecentRunsOpen] = useState(false)
  const [dialogRunsPage, setDialogRunsPage] = useState(1)

  // 调度表单状态
  const [pageScheduleForm, setPageScheduleForm] = useState<ScheduleFormState>(fromSchedule())
  const [scheduleFormRestoredToDefault, setScheduleFormRestoredToDefault] = useState(false)

  // 数据查询
  const {
    allPagesData,
    scopedAllPagesData,
    pagedPagesData,
    isLoadingPagedPages,
    isFetchingPagedPages,
    isRefetchingPagedPages,
  } = useWebPages({
    kbId,
    view: 'web-pages',
    selectedFolderId,
    includeSubfolders,
    pageSearchKeyword,
    pageListPage,
  })

  const { schedules, kbDefaultSchedule } = useWebSchedules({ kbId, view: 'web-pages' })
  const selectedPageSchedule = usePageSchedule(schedules, selectedPageId)

  const { selectedPageRunsData, isLoadingSelectedPageRuns } = useSelectedPageRuns({
    kbId,
    view: 'web-pages',
    selectedPageId,
    dialogRunsPage,
  })

  // 选中页面信息
  const pagedPageOptions = useMemo(() => pagedPagesData?.items || [], [pagedPagesData])
  const scopedPageOptions = useMemo(() => scopedAllPagesData, [scopedAllPagesData])
  const pageOptions = useMemo(() => allPagesData, [allPagesData])

  const selectedPage = useMemo(
    () =>
      pagedPageOptions.find(item => item.kb_web_page_id === selectedPageId) ||
      scopedPageOptions.find(item => item.kb_web_page_id === selectedPageId) ||
      pageOptions.find(item => item.kb_web_page_id === selectedPageId),
    [pagedPageOptions, scopedPageOptions, pageOptions, selectedPageId]
  )

  const selectedPageConfigDraft = useMemo(
    () => getWebPageConfigDraft(selectedPage?.page_config),
    [selectedPage?.page_config]
  )

  // 获取所选页面的目录路径
  const { data: selectedPageFolderPath = [] } = useQuery({
    queryKey: ['folder-path', selectedPage?.folder_id],
    queryFn: () => fetchFolderPath(selectedPage!.folder_id!),
    enabled: Boolean(selectedPage?.folder_id),
    staleTime: 30_000,
  })

  const selectedPageFolderName = useMemo(() => {
    if (!selectedPage?.folder_id) return '根目录'
    if (selectedPageFolderPath.length === 0) return '已挂载'
    return selectedPageFolderPath.map(folder => folder.name).join(' / ')
  }, [selectedPage?.folder_id, selectedPageFolderPath])

  // Mutations
  const createPageMutation = useCreatePageMutation(kbId)
  const updatePageMutation = useUpdatePageMutation(kbId)
  const deletePageMutation = useDeletePageMutation(kbId)
  const saveScheduleMutation = useSaveScheduleMutation(kbId)
  const deleteScheduleMutation = useDeleteScheduleMutation(kbId)
  const latestCheckMutation = useLatestCheckMutation(kbId)
  const syncNowMutation = useSyncNowMutation(kbId)

  // 预览抽取 mutation
  const previewExtractMutation = useMutation({
    mutationFn: previewWebPageExtract,
    onSuccess: result => {
      setPreviewResult(result)
      setPreviewDialogOpen(true)
    },
  })

  // 刷新列表
  const handleRefreshList = () => {
    queryClient.invalidateQueries({ queryKey: ['kb-web-pages-panel', kbId] })
  }

  // 复制 URL
  const handleCopyUrl = async (pageUrl?: string | null) => {
    if (!pageUrl) {
      toast.error('当前页面没有可复制的 URL')
      return
    }
    try {
      await navigator.clipboard.writeText(pageUrl)
      toast.success('URL 已复制')
    } catch {
      toast.error('复制失败，请手动复制')
    }
  }

  // 打开 URL
  const handleOpenUrl = (pageUrl?: string | null) => {
    if (!pageUrl) {
      toast.error('当前页面没有可打开的 URL')
      return
    }
    window.open(pageUrl, '_blank', 'noopener,noreferrer')
  }

  // 页面选择
  const handlePageSelect = (pageId: string) => {
    setSelectedPageId(pageId)
    setScheduleFormRestoredToDefault(false)
    const schedule = schedules.find(item => item.scope_level === 'page_override' && item.kb_web_page_id === pageId)
    setPageScheduleForm(fromSchedule(schedule ?? kbDefaultSchedule))
  }

  // 初始化选中第一个页面
  useEffect(() => {
    if (!selectedPageId && pagedPageOptions.length > 0) {
      setSelectedPageId(pagedPageOptions[0].kb_web_page_id)
    }
    const existsInPaged = pagedPageOptions.some(item => item.kb_web_page_id === selectedPageId)
    const existsInScoped = scopedPageOptions.some(item => item.kb_web_page_id === selectedPageId)
    if (!existsInPaged && !existsInScoped && pagedPageOptions.length > 0) {
      setSelectedPageId(pagedPageOptions[0]?.kb_web_page_id || '')
    }
  }, [selectedPageId, pagedPageOptions, scopedPageOptions])

  // 更新调度表单
  useEffect(() => {
    setPageScheduleForm(fromSchedule(selectedPageSchedule ?? kbDefaultSchedule))
  }, [selectedPageSchedule, kbDefaultSchedule])

  // 创建页面
  const handleCreatePage = (payload: any) => {
    createPageMutation.mutate(payload, {
      onSuccess: data => {
        setAddDialogOpen(false)
        setSelectedPageId(data.kb_web_page_id)
      },
    })
  }

  // 更新页面
  const handleUpdatePage = (payload: any) => {
    updatePageMutation.mutate(payload, {
      onSuccess: () => {
        setEditingPage(null)
      },
    })
  }

  // 删除页面
  const handleDeletePage = (pageItem: WebPageItem) => {
    deletePageMutation.mutate(pageItem, {
      onSuccess: () => {
        setDeletingPage(null)
        if (selectedPageId === pageItem.kb_web_page_id) {
          setSelectedPageId('')
        }
      },
    })
  }

  // 保存调度规则
  const handleSaveSchedule = (form: ScheduleFormState) => {
    if (!selectedPageId) {
      toast.error('请先选择页面')
      return
    }
    const isSameAsKbDefault = isScheduleFormSameAsKbDefault(form, kbDefaultSchedule)
    if (isSameAsKbDefault && selectedPageSchedule?.schedule_id) {
      deleteScheduleMutation.mutate({ schedule_id: selectedPageSchedule.schedule_id })
      return
    }
    if (isSameAsKbDefault && !selectedPageSchedule?.schedule_id) {
      toast.info('当前规则与知识库默认规则一致，无需保存')
      return
    }
    saveScheduleMutation.mutate({
      scheduleId: selectedPageSchedule?.schedule_id,
      payload: buildSchedulePayload(
        { kb_id: kbId, kb_web_page_id: selectedPageId, scope_level: 'page_override' },
        form
      ),
    })
  }

  // 恢复默认规则
  const handleRestoreDefault = () => {
    setPageScheduleForm(fromSchedule(kbDefaultSchedule))
    setScheduleFormRestoredToDefault(true)
  }

  // 立即同步
  const handleSyncNow = (pageId?: string) => {
    if (pageId && pageId !== selectedPageId) {
      setSelectedPageId(pageId)
      setTimeout(() => setSyncNowConfirmOpen(true), 50)
    } else {
      setSyncNowConfirmOpen(true)
    }
  }

  const confirmSyncNow = () => {
    if (selectedPageId) {
      syncNowMutation.mutate({ kb_web_page_id: selectedPageId })
    }
    setSyncNowConfirmOpen(false)
  }

  // 最新校验
  const handleLatestCheck = (pageId?: string) => {
    latestCheckMutation.mutate({ kb_web_page_id: pageId || selectedPageId })
  }

  // 预览抽取
  const handlePreviewExtract = () => {
    if (!selectedPageId) return
    previewExtractMutation.mutate({
      kb_web_page_id: selectedPageId,
      fetch_mode: (selectedPage?.fetch_mode || 'auto') as FetchMode,
      timeout_seconds: selectedPageConfigDraft.timeoutSeconds,
      content_selector: selectedPageConfigDraft.contentSelector || undefined,
      include_raw_html: true,
    })
  }

  // 分页
  const totalPages = Math.max(1, Math.ceil((pagedPagesData?.total || 0) / 20))

  return (
    <div className="flex h-full min-h-0 bg-gradient-to-br from-slate-50 to-blue-50/30">
      <PageListSidebar
        pageSearchKeyword={pageSearchKeyword}
        onPageSearchKeywordChange={keyword => {
          setPageSearchKeyword(keyword)
          setPageListPage(1)
        }}
        pageListPage={pageListPage}
        totalPages={totalPages}
        totalItems={pagedPagesData?.total || 0}
        includeSubfolders={includeSubfolders}
        onIncludeSubfoldersChange={setIncludeSubfolders}
        isFetchingPagedPages={isFetchingPagedPages}
        isLoadingPagedPages={isLoadingPagedPages}
        isRefetchingPagedPages={isRefetchingPagedPages}
        pagedPageOptions={pagedPageOptions}
        selectedPageId={selectedPageId}
        onPageSelect={handlePageSelect}
        onAddPage={() => setAddDialogOpen(true)}
        onRefreshList={handleRefreshList}
        onSyncNow={handleSyncNow}
        onLatestCheck={handleLatestCheck}
        onEditPage={setEditingPage}
        onDeletePage={setDeletingPage}
        onCopyUrl={handleCopyUrl}
        onOpenUrl={handleOpenUrl}
        onPageChange={setPageListPage}
      />

      <PageDetailPanel
        selectedPage={selectedPage}
        selectedPageId={selectedPageId}
        selectedPageFolderName={selectedPageFolderName}
        selectedPageConfigDraft={selectedPageConfigDraft}
        kbDefaultSchedule={kbDefaultSchedule}
        selectedPageSchedule={selectedPageSchedule}
        pageScheduleForm={pageScheduleForm}
        onPageScheduleFormChange={setPageScheduleForm}
        scheduleFormRestoredToDefault={scheduleFormRestoredToDefault}
        onSaveSchedule={handleSaveSchedule}
        onDeleteSchedule={handleRestoreDefault}
        onCopyUrl={handleCopyUrl}
        onOpenUrl={handleOpenUrl}
        onOpenRecentRuns={() => setRecentRunsOpen(true)}
        onPreviewExtract={handlePreviewExtract}
        onLatestCheck={() => handleLatestCheck()}
        onSyncNow={() => handleSyncNow()}
        previewPending={previewExtractMutation.isPending}
        latestCheckPending={latestCheckMutation.isPending}
        syncNowPending={syncNowMutation.isPending}
        saveSchedulePending={saveScheduleMutation.isPending}
        deleteSchedulePending={deleteScheduleMutation.isPending}
        recentRunsCount={(selectedPageRunsData?.items || []).length}
      />

      {/* 弹窗组件 */}
      <AddPageDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        kbId={kbId}
        selectedFolderId={selectedFolderId}
        isPending={createPageMutation.isPending}
        onCreate={handleCreatePage}
      />

      <EditPageDialog
        editingPage={editingPage}
        onOpenChange={open => !open && setEditingPage(null)}
        kbId={kbId}
        isPending={updatePageMutation.isPending}
        onUpdate={handleUpdatePage}
      />

      <DeletePageDialog
        deletingPage={deletingPage}
        onOpenChange={open => !open && setDeletingPage(null)}
        isPending={deletePageMutation.isPending}
        onDelete={handleDeletePage}
      />

      <SyncNowConfirmDialog
        open={syncNowConfirmOpen}
        onOpenChange={setSyncNowConfirmOpen}
        pageName={selectedPage?.name}
        onConfirm={confirmSyncNow}
      />

      <PreviewExtractDialog
        open={previewDialogOpen}
        onOpenChange={setPreviewDialogOpen}
        selectedPageId={selectedPageId}
        selectedPageConfig={selectedPageConfigDraft}
        selectedPageFetchMode={(selectedPage?.fetch_mode || 'auto') as FetchMode}
        isPending={previewExtractMutation.isPending}
        previewResult={previewResult}
        onPreview={payload => previewExtractMutation.mutate(payload)}
      />

      <RecentRunsDialog
        open={recentRunsOpen}
        onOpenChange={setRecentRunsOpen}
        pageName={selectedPage?.name}
        isLoading={isLoadingSelectedPageRuns}
        runs={selectedPageRunsData?.items || []}
        total={selectedPageRunsData?.total || 0}
        page={dialogRunsPage}
        onPageChange={setDialogRunsPage}
      />
    </div>
  )
}
