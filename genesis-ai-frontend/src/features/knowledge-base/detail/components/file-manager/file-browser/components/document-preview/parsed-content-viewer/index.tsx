/**
 * 解析内容查看器（路由分发）
 */
import type { DocumentPreviewConfig } from '../types'
import { MarkdownViewer } from './markdown-viewer'

interface ParsedContentViewerProps {
  config: DocumentPreviewConfig
}

export function ParsedContentViewer({ config }: ParsedContentViewerProps) {
  const { parsedContentType, kbDocId, fileName } = config

  // 根据解析内容类型路由到对应的查看器
  switch (parsedContentType) {
    case 'markdown':
      return <MarkdownViewer kbDocId={kbDocId} fileName={fileName} />

    case 'json':
      // 未来扩展：JSON 查看器
      return <div className="p-4 text-muted-foreground">JSON 查看器（待实现）</div>

    case 'html':
      // 未来扩展：HTML 查看器
      return <div className="p-4 text-muted-foreground">HTML 查看器（待实现）</div>

    case 'text':
      // 未来扩展：纯文本查看器
      return <div className="p-4 text-muted-foreground">文本查看器（待实现）</div>

    default:
      return <div className="p-4 text-muted-foreground">不支持的解析内容类型</div>
  }
}
