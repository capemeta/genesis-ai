/**
 * 网页页面增删改 Mutations
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  createWebPage,
  updateWebPage,
  deleteWebSchedule,
  createWebSchedule,
  updateWebSchedule,
  latestCheckWebPage,
  triggerWebSyncNow,
  type WebPageItem,
  type WebPageConfig,
  type WebScheduleCreateRequest,
} from '@/lib/api/web-sync'
import { detachDocumentsFromKB } from '@/lib/api/knowledge-base'
import type { FetchMode } from '../types'

/**
 * 刷新所有相关查询
 */
export function useRefreshAllQueries(kbId: string) {
  const queryClient = useQueryClient()

  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['kb-web-pages', kbId] }),
      queryClient.invalidateQueries({ queryKey: ['kb-web-pages-all', kbId] }),
      queryClient.invalidateQueries({ queryKey: ['kb-web-pages-panel', kbId] }),
      queryClient.invalidateQueries({ queryKey: ['kb-web-schedules', kbId] }),
      queryClient.invalidateQueries({ queryKey: ['kb-web-sync-runs', kbId] }),
      queryClient.invalidateQueries({ queryKey: ['kb-documents', kbId], exact: false }),
      queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] }),
    ])
  }
}

export interface CreatePageMutationPayload {
  kb_id: string
  url: string
  folder_id: string | null
  display_name?: string
  fetch_mode: FetchMode
  page_config: WebPageConfig
}

/**
 * 创建页面 Mutation
 */
export function useCreatePageMutation(kbId: string) {
  const refreshAllQueries = useRefreshAllQueries(kbId)

  return useMutation({
    mutationFn: (payload: CreatePageMutationPayload) =>
      createWebPage({
        kb_id: payload.kb_id,
        url: payload.url,
        folder_id: payload.folder_id,
        display_name: payload.display_name,
        trigger_sync_now: false,
        fetch_mode: payload.fetch_mode,
        page_config: payload.page_config,
      }),
    onSuccess: async data => {
      toast.success('URL 已添加')
      await refreshAllQueries()
      return data
    },
  })
}

export interface UpdatePageMutationPayload {
  kb_web_page_id: string
  display_name?: string
  folder_id?: string
  fetch_mode?: FetchMode
  page_config?: WebPageConfig
}

/**
 * 更新页面 Mutation
 */
export function useUpdatePageMutation(kbId: string) {
  const refreshAllQueries = useRefreshAllQueries(kbId)

  return useMutation({
    mutationFn: (payload: UpdatePageMutationPayload) =>
      updateWebPage({
        kb_web_page_id: payload.kb_web_page_id,
        display_name: payload.display_name,
        folder_id: payload.folder_id,
        fetch_mode: payload.fetch_mode,
        page_config: payload.page_config,
      }),
    onSuccess: async () => {
      toast.success('页面信息已更新')
      await refreshAllQueries()
    },
  })
}

/**
 * 删除页面 Mutation
 */
export function useDeletePageMutation(kbId: string) {
  const refreshAllQueries = useRefreshAllQueries(kbId)

  return useMutation({
    mutationFn: (pageItem: WebPageItem) => detachDocumentsFromKB(kbId, pageItem.kb_doc_id),
    onSuccess: async (_result, pageItem) => {
      toast.success('网页页面已删除')
      await refreshAllQueries()
      // 返回被删除的页面ID，用于清除选中状态
      return pageItem.kb_web_page_id
    },
  })
}

/**
 * 保存调度规则 Mutation
 */
export function useSaveScheduleMutation(kbId: string) {
  const refreshAllQueries = useRefreshAllQueries(kbId)

  return useMutation({
    mutationFn: (params: { scheduleId?: string; payload: WebScheduleCreateRequest }) => {
      if (params.scheduleId) {
        return updateWebSchedule({
          schedule_id: params.scheduleId,
          ...params.payload,
        })
      }
      return createWebSchedule(params.payload)
    },
    onSuccess: async () => {
      toast.success('定时规则已保存')
      await refreshAllQueries()
    },
  })
}

/**
 * 删除调度规则 Mutation
 */
export function useDeleteScheduleMutation(kbId: string) {
  const refreshAllQueries = useRefreshAllQueries(kbId)

  return useMutation({
    mutationFn: deleteWebSchedule,
    onSuccess: async () => {
      toast.success('已恢复继承默认规则')
      await refreshAllQueries()
    },
  })
}

/**
 * 最新校验 Mutation
 */
export function useLatestCheckMutation(kbId: string) {
  const refreshAllQueries = useRefreshAllQueries(kbId)

  return useMutation({
    mutationFn: latestCheckWebPage,
    onSuccess: async result => {
      toast.success(result.message)
      await refreshAllQueries()
    },
  })
}

/**
 * 立即同步 Mutation
 */
export function useSyncNowMutation(kbId: string) {
  const refreshAllQueries = useRefreshAllQueries(kbId)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: triggerWebSyncNow,
    onSuccess: async () => {
      toast.success('已触发同步任务')
      await refreshAllQueries()
      queryClient.invalidateQueries({ queryKey: ['kb-web-sync-runs', kbId] })
      queryClient.invalidateQueries({ queryKey: ['kb-web-page-runs', kbId] })
    },
  })
}
