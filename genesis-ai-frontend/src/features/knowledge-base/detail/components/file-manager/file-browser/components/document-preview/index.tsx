/**
 * 文档预览主容器组件
 */
import { useState, useMemo } from 'react'
import { AlertCircle } from 'lucide-react'
import { PreviewTabs } from './preview-tabs'
import { SourceFileViewer } from './source-file-viewer'
import { ParsedContentViewer } from './parsed-content-viewer'
import { getDocumentPreviewConfig } from './utils'
import type { PreviewMode } from './types'

interface DocumentPreviewProps {
  kbDocId: string
  fileName: string
  kbDoc: any // KnowledgeBaseDocument 类型
  pdfHighlights?: any[]
}

export function DocumentPreview({ fileName, kbDoc, pdfHighlights = [] }: DocumentPreviewProps) {
  // 生成预览配置
  const config = useMemo(() => getDocumentPreviewConfig(fileName, kbDoc), [fileName, kbDoc])

  // 默认模式：优先显示源文件，如果源文件不支持则显示解析视图
  const defaultMode: PreviewMode = config.hasSourcePreview ? 'source' : 'parsed'
  const [mode, setMode] = useState<PreviewMode>(defaultMode)

  // 如果两种视图都不支持，显示占位符
  if (!config.hasSourcePreview && !config.hasParsedPreview) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 gap-3">
        <AlertCircle className="w-12 h-12 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">该文件类型暂不支持预览</p>
        <p className="text-xs text-muted-foreground">{fileName}</p>
      </div>
    )
  }

  // 确保当前模式有效
  const effectiveMode =
    mode === 'source' && !config.hasSourcePreview
      ? 'parsed'
      : mode === 'parsed' && !config.hasParsedPreview
        ? 'source'
        : mode

  return (
    <div className="flex flex-col h-full">
      {/* 标签页切换 */}
      <PreviewTabs mode={effectiveMode} onModeChange={setMode} config={config} />

      {/* 内容区域 */}
      <div className="flex-1 overflow-auto">
        {effectiveMode === 'source' && config.hasSourcePreview && (
          <SourceFileViewer config={config} pdfHighlights={pdfHighlights} />
        )}

        {effectiveMode === 'parsed' && config.hasParsedPreview && (
          <ParsedContentViewer config={config} />
        )}
      </div>
    </div>
  )
}
