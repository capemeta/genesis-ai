/**
 * 源文件查看器（路由分发）
 */
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, AlertCircle, Code2, BookOpen, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { fetchDocumentContent, fetchDocumentRaw } from '@/lib/api/document'
import { DocxPreview } from '@/components/docx-preview-viewer'
import { PdfPreviewer } from '../pdf-previewer'
import { ExcelPreviewer } from '../excel-previewer'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeHighlight from 'rehype-highlight'
import { cn } from '@/lib/utils'
import type { DocumentPreviewConfig } from '../types'
import 'highlight.js/styles/github-dark.css'

interface SourceFileViewerProps {
  config: DocumentPreviewConfig
  pdfHighlights?: any[]
}

export function SourceFileViewer({ config, pdfHighlights = [] }: SourceFileViewerProps) {
  const { kbDocId, fileName, fileExtension } = config
  const [viewMode, setViewMode] = useState<'rendered' | 'source'>('rendered')
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)

  // 判断是否可预览
  const ext = fileExtension.toLowerCase()
  const isPdfFile = ext === 'pdf'
  const isTextFile = ext === 'md' || ext === 'txt'
  const isDocxFile = ext === 'docx'
  const isExcelFile = ext === 'xlsx' || ext === 'xls' || ext === 'csv'
  const isPreviewable = isTextFile || isDocxFile || isPdfFile || isExcelFile

  // 获取源文件内容
  const { data: sourceContent, isLoading, error } = useQuery<string | Blob, Error>({
    queryKey: ['source-content', kbDocId],
    queryFn: async () => {
      // PDF、Word、Excel 需要获取原始二进制流
      if (isDocxFile || isPdfFile || isExcelFile) return fetchDocumentRaw(kbDocId)
      return fetchDocumentContent(kbDocId)
    },
    enabled: isPreviewable,
    staleTime: 1000 * 60 * 5, // 5分钟缓存
    gcTime: 1000 * 60,
  })

  // 处理 PDF URL
  useEffect(() => {
    if (isPdfFile && sourceContent instanceof Blob) {
      const url = URL.createObjectURL(sourceContent)
      setPdfUrl(url)
      return () => {
        URL.revokeObjectURL(url)
      }
    }
  }, [isPdfFile, sourceContent])

  // 根据文件类型渲染不同的查看器
  const renderContent = () => {
    if (!isPreviewable) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center p-8 gap-5">
          <div className="relative">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 border border-blue-100 dark:border-blue-900 flex items-center justify-center shadow-sm">
              <FileText className="w-9 h-9 text-blue-400 dark:text-blue-500" />
            </div>
            <div className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-amber-100 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 flex items-center justify-center">
              <span className="text-[9px] font-bold text-amber-600 dark:text-amber-400">
                {fileExtension.toUpperCase().slice(0, 3)}
              </span>
            </div>
          </div>
          <div className="text-center space-y-2 max-w-[280px]">
            <h3 className="text-sm font-medium text-foreground/80">暂不支持此类文件预览</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              目前支持 PDF、Word (.docx)、Excel (.xlsx/.xls/.csv)、Markdown (.md) 和纯文本 (.txt) 的在线预览。
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/50 border border-dashed text-xs text-muted-foreground font-mono truncate max-w-[200px]">
            {fileName}
          </div>
        </div>
      )
    }

    if (isLoading) {
      return (
        <div className="w-full h-full flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary/50" />
            <p className="text-xs text-muted-foreground animate-pulse">正在加载文件内容...</p>
          </div>
        </div>
      )
    }

    if (error) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center p-8 gap-3">
          <AlertCircle className="h-10 w-10 text-destructive/50" />
          <p className="text-sm text-muted-foreground">内容加载失败</p>
          <p className="text-[10px] text-muted-foreground/60 break-all text-center max-w-[200px]">
            {error instanceof Error ? error.message : '请检查网络或后端服务'}
          </p>
        </div>
      )
    }

    // PDF 预览
    if (isPdfFile) {
      if (pdfUrl) {
        return <PdfPreviewer url={pdfUrl} highlights={pdfHighlights} />
      }
      return (
        <div className="w-full h-full flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-primary/30" />
        </div>
      )
    }

    // Word 文档
    if (isDocxFile) {
      if (sourceContent instanceof Blob) {
        return (
          <div className="bg-slate-200/50 dark:bg-slate-100/30 h-full w-full overflow-y-auto">
            <DocxPreview blob={sourceContent} fileName={fileName} className="w-full" />
          </div>
        )
      }
      return (
        <div className="w-full h-full flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-primary/30" />
        </div>
      )
    }

    // Excel 文件
    if (isExcelFile) {
      if (sourceContent instanceof Blob) {
        return <ExcelPreviewer blob={sourceContent} fileName={fileName} className="h-full" />
      }
      return (
        <div className="w-full h-full flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-primary/30" />
        </div>
      )
    }

    // Markdown 文件
    if (fileExtension === 'md') {
      return viewMode === 'rendered' ? (
        <div className="prose prose-slate dark:prose-invert max-w-none prose-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw, rehypeHighlight]}>
            {(sourceContent as string) || ''}
          </ReactMarkdown>
        </div>
      ) : (
        <div className="relative">
          <pre className="p-4 rounded-lg bg-slate-950 text-slate-300 overflow-x-auto font-mono text-xs whitespace-pre-wrap break-words leading-relaxed border border-slate-800 shadow-inner">
            {sourceContent as string}
          </pre>
          <Badge
            variant="outline"
            className="absolute top-2 right-2 text-[9px] bg-slate-800 text-slate-400 border-slate-700"
          >
            RAW
          </Badge>
        </div>
      )
    }

    // 纯文本文件
    return (
      <pre className="whitespace-pre-wrap font-mono text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
        {sourceContent as string}
      </pre>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="h-10 border-b px-4 flex items-center justify-between shrink-0 bg-muted/30">
        <div className="flex items-center gap-2">
          <FileText className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground">源文件</span>
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
            {fileExtension.toUpperCase()}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}

          {/* 视图切换按钮 - 仅在 Markdown 文件时显示 */}
          {fileExtension === 'md' && !isLoading && !error && (
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className={cn(
                      'h-7 w-7',
                      viewMode === 'source' && 'bg-amber-50 text-amber-600 dark:bg-amber-900/30'
                    )}
                    onClick={() => setViewMode(viewMode === 'rendered' ? 'source' : 'rendered')}
                  >
                    {viewMode === 'rendered' ? (
                      <Code2 className="h-3.5 w-3.5" />
                    ) : (
                      <BookOpen className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                  {viewMode === 'rendered' ? '查看源代码' : '渲染视图'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-hidden bg-white dark:bg-slate-950">
        <div className={cn('h-full', !isDocxFile && !isPdfFile && !isExcelFile && 'p-6 overflow-auto')}>
          {renderContent()}
        </div>
      </div>
    </div>
  )
}
