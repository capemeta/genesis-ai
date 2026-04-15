/**
 * 网页页面列表相关 Hooks
 */

import { useQuery } from '@tanstack/react-query'
import { listAllWebPages, listWebPages, type WebPageItem } from '@/lib/api/web-sync'
import type { WebWorkbenchView } from '../types'

export interface UseWebPagesOptions {
  kbId: string
  view: WebWorkbenchView
  selectedFolderId: string | null
  includeSubfolders: boolean
  pageSearchKeyword: string
  pageListPage: number
}

export interface UseWebPagesReturn {
  /** 所有页面数据（用于选择器等） */
  allPagesData: WebPageItem[]
  /** 当前范围的所有页面数据 */
  scopedAllPagesData: WebPageItem[]
  /** 分页页面数据 */
  pagedPagesData: {
    items: WebPageItem[]
    total: number
  } | undefined
  /** 是否正在加载分页数据 */
  isLoadingPagedPages: boolean
  /** 是否正在重新获取分页数据 */
  isFetchingPagedPages: boolean
  /** 是否正在刷新（非首次加载） */
  isRefetchingPagedPages: boolean
}

/**
 * 网页页面列表查询 Hook
 */
export function useWebPages(options: UseWebPagesOptions): UseWebPagesReturn {
  const { kbId, view, selectedFolderId, includeSubfolders, pageSearchKeyword, pageListPage } = options

  // 所有页面数据（用于选择器等）
  const { data: allPagesData = [] } = useQuery({
    queryKey: ['kb-web-pages-all', kbId],
    queryFn: () => listAllWebPages({ kb_id: kbId, include_subfolders: true }),
    staleTime: 10_000,
    enabled: view !== 'files',
  })

  // 当前范围的所有页面数据
  const { data: scopedAllPagesData = [] } = useQuery({
    queryKey: ['kb-web-pages-all', kbId, selectedFolderId, includeSubfolders, 'scoped'],
    queryFn: () =>
      listAllWebPages({
        kb_id: kbId,
        folder_id: selectedFolderId,
        include_subfolders: includeSubfolders,
      }),
    staleTime: 10_000,
    enabled: view === 'web-pages',
  })

  // 分页页面数据
  const {
    data: pagedPagesData,
    isLoading: isLoadingPagedPages,
    isFetching: isFetchingPagedPages,
  } = useQuery({
    queryKey: ['kb-web-pages-panel', kbId, selectedFolderId, includeSubfolders, pageSearchKeyword, pageListPage],
    queryFn: () =>
      listWebPages({
        kb_id: kbId,
        page: pageListPage,
        page_size: 20,
        search: pageSearchKeyword.trim() || undefined,
        folder_id: selectedFolderId,
        include_subfolders: includeSubfolders,
      }),
    staleTime: 5_000,
    enabled: view === 'web-pages',
  })

  const isRefetchingPagedPages = isFetchingPagedPages && !isLoadingPagedPages

  return {
    allPagesData,
    scopedAllPagesData,
    pagedPagesData: pagedPagesData ? { items: pagedPagesData.items || [], total: pagedPagesData.total || 0 } : undefined,
    isLoadingPagedPages,
    isFetchingPagedPages,
    isRefetchingPagedPages,
  }
}

/**
 * 统计信息计算
 */
export function useWebPagesStats(allPagesData: WebPageItem[]) {
  return {
    total: allPagesData.length,
    running: allPagesData.filter(item => item.sync_status === 'syncing').length,
    failed: allPagesData.filter(item => item.sync_status === 'failed').length,
    outdated: allPagesData.filter(item => item.last_check_status === 'outdated').length,
  }
}
