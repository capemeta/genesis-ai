/**
 * 同步记录相关 Hooks
 */

import { useQuery } from '@tanstack/react-query'
import { listWebSyncRuns, type WebSyncRunItem } from '@/lib/api/web-sync'
import type { WebWorkbenchView, RunStatusFilter } from '../types'

export interface UseWebSyncRunsOptions {
  kbId: string
  view: WebWorkbenchView
  selectedPageId: string
  runStatusFilter: RunStatusFilter
  runsPage: number
}

export interface UseWebSyncRunsReturn {
  /** 同步记录数据 */
  runsData: {
    items: WebSyncRunItem[]
    total: number
  } | undefined
  /** 是否正在加载 */
  isLoadingRuns: boolean
  /** 重新获取数据 */
  refetchRuns: () => Promise<unknown>
}

/**
 * 同步记录查询 Hook（web-runs 视图用）
 */
export function useWebSyncRuns(options: UseWebSyncRunsOptions): UseWebSyncRunsReturn {
  const { kbId, view, selectedPageId, runStatusFilter, runsPage } = options

  const { data: runsData, isLoading: isLoadingRuns, refetch: refetchRuns } = useQuery({
    queryKey: ['kb-web-sync-runs', kbId, selectedPageId, runStatusFilter, runsPage],
    queryFn: () =>
      listWebSyncRuns({
        kb_id: kbId,
        page: runsPage,
        page_size: 20,
        kb_web_page_id: selectedPageId || undefined,
        status: runStatusFilter === 'all' ? undefined : runStatusFilter,
      }),
    staleTime: 3_000,
    enabled: view === 'web-runs',
    refetchInterval: query => {
      const hasActive = (query.state.data?.items || []).some(item => item.status === 'queued' || item.status === 'running')
      return hasActive ? 3000 : false
    },
  })

  return {
    runsData: runsData ? { items: runsData.items || [], total: runsData.total || 0 } : undefined,
    isLoadingRuns,
    refetchRuns,
  }
}

export interface UseSelectedPageRunsOptions {
  kbId: string
  view: WebWorkbenchView
  selectedPageId: string
  dialogRunsPage: number
}

export interface UseSelectedPageRunsReturn {
  /** 同步记录数据 */
  selectedPageRunsData: {
    items: WebSyncRunItem[]
    total: number
  } | undefined
  /** 是否正在加载 */
  isLoadingSelectedPageRuns: boolean
  /** 重新获取数据 */
  refetchSelectedPageRuns: () => Promise<unknown>
}

/**
 * 选中页面的同步记录查询 Hook（弹窗用）
 */
export function useSelectedPageRuns(options: UseSelectedPageRunsOptions): UseSelectedPageRunsReturn {
  const { kbId, view, selectedPageId, dialogRunsPage } = options

  const {
    data: selectedPageRunsData,
    isLoading: isLoadingSelectedPageRuns,
    refetch: refetchSelectedPageRuns,
  } = useQuery({
    queryKey: ['kb-web-page-runs', kbId, selectedPageId, dialogRunsPage],
    queryFn: () =>
      listWebSyncRuns({
        kb_id: kbId,
        page: dialogRunsPage,
        page_size: 10,
        kb_web_page_id: selectedPageId || undefined,
      }),
    staleTime: 3_000,
    enabled: view === 'web-pages' && Boolean(selectedPageId),
    refetchInterval: query => {
      const hasActive = (query.state.data?.items || []).some(item => item.status === 'queued' || item.status === 'running')
      return hasActive ? 3000 : false
    },
  })

  return {
    selectedPageRunsData: selectedPageRunsData ? { items: selectedPageRunsData.items || [], total: selectedPageRunsData.total || 0 } : undefined,
    isLoadingSelectedPageRuns,
    refetchSelectedPageRuns,
  }
}
