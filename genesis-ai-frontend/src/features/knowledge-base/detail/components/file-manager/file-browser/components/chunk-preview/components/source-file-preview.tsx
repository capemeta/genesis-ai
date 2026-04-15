/**
 * 切片预览组件 - 源文件预览
 */
import { useState } from 'react'
import { Loader2, AlertCircle, Eye, Code2, BookOpen, FileText } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { DocxPreview } from '@/components/docx-preview-viewer'
import { cn } from '@/lib/utils'
import type { SourceFilePreviewProps } from '../types'

/**
 * 源文件预览组件
 * 支持 Markdown、纯文本、Word 文档的预览
 */
export function SourceFilePreview({
  fileName,
  content,
  isLoading,
  error,
}: SourceFilePreviewProps) {
  // 从文件名推断类型
  const extension = fileName.split('.').pop()?.toLowerCase() || ''
  const typeLabel =
    {
      pdf: 'PDF 文档',
      docx: 'Word 文档',
      doc: 'Word 文档',
      xlsx: 'Excel 表格',
      xls: 'Excel 表格',
      pptx: 'PPT 演示文稿',
      ppt: 'PPT 演示文稿',
      md: 'Markdown',
      txt: '纯文本',
      csv: 'CSV 数据',
      json: 'JSON 文件',
      html: 'HTML 页面',
    }[extension] || '文件'

  const isPreviewable =
    extension === 'md' || extension === 'txt' || extension === 'docx'
  const isDocx = extension === 'docx'

  // 视图模式：渲染视图 vs 源代码视图
  const [viewMode, setViewMode] = useState<'rendered' | 'source'>('rendered')

  return (
    <div className='flex h-full flex-col'>
      {/* 源文件面板 Header */}
      <div className='flex h-10 shrink-0 items-center justify-between border-b bg-muted/30 px-4'>
        <div className='flex items-center gap-2'>
          <Eye className='h-3.5 w-3.5 text-muted-foreground' />
          <span className='text-xs font-medium text-muted-foreground'>
            源文件预览
          </span>
          <Badge variant='outline' className='h-4 px-1.5 py-0 text-[10px]'>
            {typeLabel}
          </Badge>
        </div>
        <div className='flex items-center gap-2'>
          {isLoading && (
            <Loader2 className='h-3 w-3 animate-spin text-muted-foreground' />
          )}

          {/* 视图切换按钮 - 仅在 Markdown 文件时显示 */}
          {isPreviewable && extension === 'md' && !isLoading && !error && (
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant='ghost'
                    size='icon'
                    className={cn(
                      'h-7 w-7',
                      viewMode === 'source' &&
                        'bg-amber-50 text-amber-600 dark:bg-amber-900/30'
                    )}
                    onClick={() =>
                      setViewMode(
                        viewMode === 'rendered' ? 'source' : 'rendered'
                      )
                    }
                  >
                    {viewMode === 'rendered' ? (
                      <Code2 className='h-3.5 w-3.5' />
                    ) : (
                      <BookOpen className='h-3.5 w-3.5' />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side='bottom' className='text-xs'>
                  {viewMode === 'rendered' ? '查看源代码' : '渲染视图'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>

      {/* 源文件内容区域 */}
      <div className='flex-1 overflow-auto bg-white dark:bg-slate-950'>
        {!isPreviewable ? (
          <div className='flex h-full w-full flex-col items-center justify-center gap-5 p-8'>
            {/* 图标区域 */}
            <div className='relative'>
              <div className='flex h-20 w-20 items-center justify-center rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-indigo-50 shadow-sm dark:border-blue-900 dark:from-blue-950/30 dark:to-indigo-950/30'>
                <FileText className='h-9 w-9 text-blue-400 dark:text-blue-500' />
              </div>
              {/* 装饰角标 */}
              <div className='absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full border border-amber-200 bg-amber-100 dark:border-amber-800 dark:bg-amber-900/30'>
                <span className='text-[9px] font-bold text-amber-600 dark:text-amber-400'>
                  {extension.toUpperCase().slice(0, 3)}
                </span>
              </div>
            </div>

            {/* 说明文字 */}
            <div className='max-w-[280px] space-y-2 text-center'>
              <h3 className='text-sm font-medium text-foreground/80'>
                暂不支持此类文件预览
              </h3>
              <p className='text-xs leading-relaxed text-muted-foreground'>
                目前支持 Markdown (.md)、纯文本 (.txt) 和 Word (.docx)
                的在线预览。
              </p>
            </div>

            <div className='flex max-w-[200px] items-center gap-2 truncate rounded-lg border border-dashed bg-muted/50 px-3 py-1.5 font-mono text-xs text-muted-foreground'>
              {fileName}
            </div>
          </div>
        ) : isLoading ? (
          <div className='flex h-full w-full items-center justify-center'>
            <div className='flex flex-col items-center gap-3'>
              <Loader2 className='h-8 w-8 animate-spin text-primary/50' />
              <p className='animate-pulse text-xs text-muted-foreground'>
                正在加载文件内容...
              </p>
            </div>
          </div>
        ) : error ? (
          <div className='flex h-full w-full flex-col items-center justify-center gap-3 p-8'>
            <AlertCircle className='h-10 w-10 text-destructive/50' />
            <p className='text-sm text-muted-foreground'>内容加载失败</p>
            <p className='max-w-[200px] text-center text-[10px] break-all text-muted-foreground/60'>
              {error instanceof Error ? error.message : '请检查网络或后端服务'}
            </p>
          </div>
        ) : (
          <div className={cn('min-h-full', !isDocx && 'p-6')}>
            {isDocx && content instanceof Blob ? (
              <div className='flex min-h-full flex-col overflow-auto bg-slate-200/50 dark:bg-slate-900/50'>
                <DocxPreview
                  blob={content}
                  fileName={fileName}
                  className='min-h-full'
                />
              </div>
            ) : extension === 'md' ? (
              viewMode === 'rendered' ? (
                // 渲染视图
                <div className='prose prose-sm max-w-none prose-slate dark:prose-invert'>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw, rehypeHighlight]}
                  >
                    {(content as string) || ''}
                  </ReactMarkdown>
                </div>
              ) : (
                // 源代码视图
                <div className='relative'>
                  <pre className='overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap text-slate-300 shadow-inner'>
                    {content as string}
                  </pre>
                  <Badge
                    variant='outline'
                    className='absolute top-2 right-2 border-slate-700 bg-slate-800 text-[9px] text-slate-400'
                  >
                    RAW
                  </Badge>
                </div>
              )
            ) : (
              <pre className='font-mono text-sm leading-relaxed whitespace-pre-wrap text-slate-700 dark:text-slate-300'>
                {content as string}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
