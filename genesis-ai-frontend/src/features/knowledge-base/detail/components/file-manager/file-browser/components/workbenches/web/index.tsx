/**
 * Web 同步工作台主入口
 * 根据视图类型渲染对应的子视图组件
 */

import { FileBrowser } from '@/features/knowledge-base/detail/components/file-manager'
import type { WebSyncWorkbenchProps } from './types'
import { WebPagesView } from './components/web-pages-view'
import { WebRunsView } from './components/web-runs-view'
import { WebSitesView } from './components/web-sites-view'

export type { WebWorkbenchView, WebChunkingDraft, WebSyncWorkbenchProps } from './types'

/**
 * Web 同步工作台组件
 */
export function WebSyncWorkbench({
  kbId,
  view,
  selectedFolderId,
  onFolderChange,
  isFolderTreeCollapsed,
  onToggleFolderTree,
  onSetFolderTreeCollapsed,
}: WebSyncWorkbenchProps) {
  // 文件视图直接使用 FileBrowser
  if (view === 'files') {
    return (
      <FileBrowser
        kbId={kbId}
        kbType="web"
        selectedFolderId={selectedFolderId}
        onFolderChange={onFolderChange}
        isFolderTreeCollapsed={isFolderTreeCollapsed}
        onToggleFolderTree={onToggleFolderTree}
        onSetFolderTreeCollapsed={onSetFolderTreeCollapsed}
      />
    )
  }

  // 网页页面视图
  if (view === 'web-pages') {
    return (
      <WebPagesView
        kbId={kbId}
        selectedFolderId={selectedFolderId}
      />
    )
  }

  // 同步记录视图
  if (view === 'web-runs') {
    return (
      <WebRunsView
        kbId={kbId}
      />
    )
  }

  // 站点配置视图（web-sites）
  return (
    <WebSitesView
      kbId={kbId}
    />
  )
}

// 默认导出
export default WebSyncWorkbench
