/**
 * Markdown 查看器组件
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeHighlight from 'rehype-highlight'
import { Loader2, AlertCircle, Code2, BookOpen, Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { fetchMarkdownPreview } from '@/lib/api/knowledge-base'
import { toast } from 'sonner'
import 'highlight.js/styles/github-dark.css'

interface MarkdownViewerProps {
  kbDocId: string
  fileName: string
}

export function MarkdownViewer({ kbDocId, fileName }: MarkdownViewerProps) {
  void fileName
  const [viewMode, setViewMode] = useState<'rendered' | 'source'>('rendered')
  const [copied, setCopied] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['markdown-preview', kbDocId],
    queryFn: () => fetchMarkdownPreview(kbDocId),
    staleTime: 1000 * 60 * 5, // 5分钟缓存
    gcTime: 1000 * 60,
  })

  const handleCopy = async () => {
    if (!data?.markdown_content) return

    try {
      await navigator.clipboard.writeText(data.markdown_content)
      setCopied(true)
      toast.success('已复制到剪贴板')
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      toast.error('复制失败')
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8 h-full">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground mr-2" />
        <span className="text-sm text-muted-foreground">加载解析视图...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-8 h-full gap-3">
        <AlertCircle className="w-12 h-12 text-destructive" />
        <p className="text-sm text-muted-foreground">加载失败</p>
        <p className="text-xs text-muted-foreground">
          {error instanceof Error ? error.message : '未知错误'}
        </p>
      </div>
    )
  }

  if (!data?.has_markdown) {
    return (
      <div className="flex flex-col items-center justify-center p-8 h-full gap-3">
        <AlertCircle className="w-12 h-12 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          {data?.message || '该文档不支持解析视图'}
        </p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* 工具栏 */}
      <div className="flex items-center justify-between p-3 border-b shrink-0">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">
            解析后的内容
          </Badge>
          <span className="text-xs text-muted-foreground">
            便于系统理解和检索
          </span>
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => setViewMode(viewMode === 'rendered' ? 'source' : 'rendered')}
          >
            {viewMode === 'rendered' ? (
              <>
                <Code2 className="h-3.5 w-3.5 mr-1" />
                源码
              </>
            ) : (
              <>
                <BookOpen className="h-3.5 w-3.5 mr-1" />
                渲染
              </>
            )}
          </Button>
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={handleCopy}>
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 mr-1" />
                已复制
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 mr-1" />
                复制
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-auto p-6">
        {viewMode === 'rendered' ? (
          <div className="prose prose-slate max-w-none dark:prose-invert prose-p:whitespace-pre-wrap">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw, rehypeHighlight]}
              components={{
                table({ children }) {
                  return (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-border">{children}</table>
                    </div>
                  )
                },
              }}
            >
              {data.markdown_content || ''}
            </ReactMarkdown>
          </div>
        ) : (
          <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto font-mono">
            <code>{data.markdown_content}</code>
          </pre>
        )}
      </div>
    </div>
  )
}
