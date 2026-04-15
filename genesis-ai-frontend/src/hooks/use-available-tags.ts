/**
 * 可选标签 Hook
 * 
 * 提供便捷的标签查询功能，按资源类型过滤
 */
import { useQuery } from '@tanstack/react-query'
import { getAvailableTags, getFolderAvailableTags, getDocumentAvailableTags, listScopedTags } from '@/lib/api/tag'
import type { Tag, TagTargetType } from '@/lib/api/folder.types'

/**
 * 获取可选标签（通用）
 */
export function useAvailableTags(
  kbId: string,
  targetType: TagTargetType,
  options?: {
    search?: string
    limit?: number
    enabled?: boolean
  }
) {
  return useQuery({
    queryKey: ['tags', 'available', kbId, targetType, options?.search],
    queryFn: () => getAvailableTags({
      kb_id: kbId,
      target_type: targetType,
      search: options?.search,
      limit: options?.limit
    }),
    enabled: !!kbId && (options?.enabled !== false),
    staleTime: 30 * 1000, // 减少到30秒缓存，确保标签更新能及时反映
    refetchOnWindowFocus: true, // 窗口聚焦时重新获取
  })
}

/**
 * 获取文件夹可选标签
 */
export function useFolderAvailableTags(
  kbId: string,
  options?: {
    search?: string
    limit?: number
    enabled?: boolean
  }
) {
  return useQuery({
    queryKey: ['tags', 'folder-available', kbId, options?.search],
    queryFn: () => getFolderAvailableTags(kbId, options?.search, options?.limit),
    enabled: !!kbId && (options?.enabled !== false),
    staleTime: 30 * 1000, // 减少到30秒缓存
    refetchOnWindowFocus: true, // 窗口聚焦时重新获取
    select: (data): Tag[] => data, // 便捷方法直接返回标签数组
  })
}

/**
 * 获取文档可选标签
 */
export function useDocumentAvailableTags(
  kbId: string,
  options?: {
    search?: string
    limit?: number
    enabled?: boolean
  }
) {
  return useQuery({
    queryKey: ['tags', 'document-available', kbId, options?.search],
    queryFn: () => getDocumentAvailableTags(kbId, options?.search, options?.limit),
    enabled: !!kbId && (options?.enabled !== false),
    staleTime: 30 * 1000, // 减少到30秒缓存
    refetchOnWindowFocus: true, // 窗口聚焦时重新获取
    select: (data): Tag[] => data, // 便捷方法直接返回标签数组
  })
}

/**
 * 获取某个知识库当前可用的标签池（公共 + 本库）。
 */
export function useScopedTags(
  kbId?: string,
  options?: {
    targetType?: TagTargetType
    search?: string
    limit?: number
    includeGlobal?: boolean
    includeKb?: boolean
    enabled?: boolean
  }
) {
  return useQuery({
    queryKey: ['tags', 'scoped', kbId || 'public', options?.targetType, options?.search, options?.includeGlobal, options?.includeKb],
    queryFn: () => listScopedTags({
      kb_id: kbId,
      include_global: options?.includeGlobal ?? true,
      include_kb: options?.includeKb ?? true,
      target_type: options?.targetType,
      search: options?.search,
      limit: options?.limit,
    }),
    enabled: options?.enabled !== false,
    staleTime: 30 * 1000,
    refetchOnWindowFocus: true,
    select: (data): Tag[] => data.data.tags,
  })
}
