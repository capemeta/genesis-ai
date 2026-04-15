/**
 * 切片预览组件 - 数据查询与派生逻辑
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  type Chunk,
  type ChunkListParams,
  fetchAllChunksByKBDocId,
  fetchChunksByKBDocId,
} from '@/lib/api/chunks'
import { fetchDocumentContent, fetchDocumentRaw } from '@/lib/api/document'
import { getChunkHierarchyFlags } from '../lib/hierarchy'
import { buildPdfHighlightsFromChunk } from '../lib/pdf-highlights'

const PREVIEW_CACHE_TIME = 1000 * 60

interface UseChunkPreviewDataParams {
  fileName: string
  kbDocId: string
  page: number
  pageSize: number
  selectedChunkId: number | null
  showSourcePreview: boolean
  viewMode: 'all' | 'leaf' | 'intermediate' | 'root'
}

/**
 * 汇总切片预览所需的数据查询与派生状态，保持主组件只关注布局。
 */
export function useChunkPreviewData({
  fileName,
  kbDocId,
  page,
  pageSize,
  selectedChunkId,
  showSourcePreview,
  viewMode,
}: UseChunkPreviewDataParams) {
  const search = ''
  const extension = fileName.split('.').pop()?.toLowerCase() || ''
  const isTextFile = extension === 'md' || extension === 'txt'
  const isDocxFile = extension === 'docx'
  const isPreviewable = isTextFile || isDocxFile

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['chunks', kbDocId, page, pageSize, search, viewMode],
    queryFn: async () => {
      const params: ChunkListParams & {
        chunk_role?: 'leaf' | 'intermediate' | 'root'
      } = {
        page,
        page_size: pageSize,
        search,
      }
      if (viewMode !== 'all') {
        params.chunk_role = viewMode
      }

      return fetchChunksByKBDocId(kbDocId, params)
    },
    enabled: !!kbDocId,
    staleTime: 15 * 1000,
    gcTime: PREVIEW_CACHE_TIME,
  })

  const allChunks = useMemo(() => data?.data || [], [data?.data])
  const totalCount = data?.total || 0

  const { data: statsChunks = [] } = useQuery({
    queryKey: ['chunks', 'stats', kbDocId],
    queryFn: () => fetchAllChunksByKBDocId(kbDocId),
    enabled: !!kbDocId,
    staleTime: 30 * 1000,
    gcTime: PREVIEW_CACHE_TIME,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const selectedChunk = useMemo(
    () =>
      allChunks.find((chunk) => Number(chunk.id) === Number(selectedChunkId)) ||
      null,
    [allChunks, selectedChunkId]
  )

  const pdfHighlights = useMemo(
    () => buildPdfHighlightsFromChunk(selectedChunk),
    [selectedChunk]
  )

  const totalPages = Math.ceil(totalCount / pageSize)
  const fullDocumentChunkCount = statsChunks.length || totalCount

  const hierarchyStats = useMemo(() => {
    const stats = { root: 0, intermediate: 0, leaf: 0 }
    let hasHierarchical = false

    statsChunks.forEach((chunk) => {
      const flags = getChunkHierarchyFlags(chunk)
      if (!flags) return

      hasHierarchical = true
      if (flags.isRoot) stats.root += 1
      if (flags.isLeaf) stats.leaf += 1
      if (flags.isIntermediate) stats.intermediate += 1
    })

    return { ...stats, hasHierarchical }
  }, [statsChunks])

  const chunkDepthMap = useMemo(() => {
    // 预计算当前页所有切片的层级深度，避免在每次渲染时重复递归。
    const chunkMap = new Map<string | number, Chunk>()
    const depthMap = new Map<string | number, number>()

    allChunks.forEach((chunk) => {
      chunkMap.set(chunk.id, chunk)
      if (chunk.metadata_info?.node_id) {
        chunkMap.set(chunk.metadata_info.node_id, chunk)
      }
    })

    const resolveDepth = (
      chunk: Chunk,
      visited = new Set<string | number>
    ): number => {
      if (typeof chunk.metadata_info?.depth === 'number') {
        return chunk.metadata_info.depth
      }

      if (depthMap.has(chunk.id)) {
        return depthMap.get(chunk.id) ?? 0
      }

      const parentId = chunk.parent_id || chunk.metadata_info?.parent_id
      if (!parentId || visited.has(chunk.id)) {
        depthMap.set(chunk.id, 0)
        return 0
      }

      visited.add(chunk.id)
      const parent = chunkMap.get(parentId)
      const depth: number = parent ? 1 + resolveDepth(parent, visited) : 0
      depthMap.set(chunk.id, depth)
      return depth
    }

    allChunks.forEach((chunk) => {
      resolveDepth(chunk)
    })

    return depthMap
  }, [allChunks])

  const {
    data: sourceContent,
    isLoading: isSourceLoading,
    error: sourceError,
  } = useQuery<string | Blob, Error>({
    queryKey: ['source-content', kbDocId, isDocxFile],
    queryFn: async () => {
      if (isDocxFile) return fetchDocumentRaw(kbDocId)
      return fetchDocumentContent(kbDocId)
    },
    enabled: showSourcePreview && isPreviewable,
    staleTime: 1000 * 60 * 5,
    gcTime: PREVIEW_CACHE_TIME,
  })

  return {
    allChunks,
    chunkDepthMap,
    error,
    extension,
    fullDocumentChunkCount,
    hierarchyStats,
    isError,
    isLoading,
    isSourceLoading,
    pdfHighlights,
    sourceContent,
    sourceError,
    totalCount,
    totalPages,
  }
}
