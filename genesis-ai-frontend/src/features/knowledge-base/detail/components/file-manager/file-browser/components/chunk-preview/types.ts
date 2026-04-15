/**
 * 切片预览组件 - 类型定义
 */
import type { Chunk as ChunkType } from '@/lib/api/chunks'

// 重新导出 Chunk 类型供其他组件使用
export type { ChunkType as Chunk }

/**
 * 通用对象类型
 */
export type ChunkPreviewRecord = Record<string, unknown>

/**
 * 轻量知识库文档类型
 */
export interface ChunkPreviewKBDoc {
  markdown_document_id?: string | null
}

/**
 * ChunkPreview 主组件 Props
 */
export interface ChunkPreviewProps {
  fileName: string
  kbDocId: string
  kbType?: string
  kbDoc?: ChunkPreviewKBDoc
  onBack: () => void
  onReparse?: () => void
  isFolderTreeCollapsed?: boolean
  onToggleFolderTree?: () => void
}

/**
 * 切片源锚点信息
 */
export interface ChunkSourceAnchor {
  page_no?: number
  page_number?: number
  bbox?: number[]
  element_index?: number
  element_type?: string
}

/**
 * 层级角色类型
 */
export type HierarchyRole = 'root' | 'intermediate' | 'leaf'

/**
 * 滚动辅助按钮 Props
 */
export interface ScrollAssistButtonsProps {
  containerRef: { current: HTMLElement | null }
  watchDeps?: Array<string | number | boolean | null | undefined>
  className?: string
}

/**
 * 源文件预览 Props
 */
export interface SourceFilePreviewProps {
  fileName: string
  content?: string | Blob
  isLoading?: boolean
  error?: Error | null
}

/**
 * 切片卡片 Props
 */
export interface ChunkCardProps {
  chunk: ChunkType
  index: number
  depth?: number
  extension?: string
  kbType?: string
  isSelected?: boolean
  onSelect?: (chunkId: number) => void
}

/**
 * 切片内容渲染器 Props
 */
export interface ChunkContentRendererProps {
  chunk: ChunkType
  extension?: string
  kbType?: string
}

/**
 * 切片编辑对话框 Props
 */
export interface ChunkEditDialogProps {
  chunk: ChunkType
  open: boolean
  kbType?: string
  onOpenChange: (open: boolean) => void
}

/**
 * 图片块类型
 */
export type ImageBlockType = 'vision' | 'ocr' | 'captioned' | 'pure'

/**
 * 图片块 Props
 */
export interface ChunkImageBlockProps {
  url: string
  alt?: string
  caption?: string[]
  contentBlocks?: ChunkPreviewRecord[]
  chunkParser?: string
  mode?: 'compact' | 'full'
}
