/**
 * Web 同步工作台相关类型定义
 */

export type WebWorkbenchView = 'files' | 'web-pages' | 'web-runs' | 'web-sites'

export type RunStatusFilter = 'all' | 'queued' | 'running' | 'success' | 'failed'

export type FetchMode = 'auto' | 'static' | 'browser'

/**
 * 网页分块配置草稿（前端表单用）
 */
export interface WebChunkingDraft {
  max_embed_tokens: number
}

/**
 * Web 同步工作台组件 Props
 */
export interface WebSyncWorkbenchProps {
  kbId: string
  view: WebWorkbenchView
  selectedFolderId: string | null
  onFolderChange: (folderId: string | null) => void
  isFolderTreeCollapsed?: boolean
  onToggleFolderTree?: () => void
  onSetFolderTreeCollapsed?: (collapsed: boolean) => void
}
