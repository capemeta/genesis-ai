/**
 * 文件拖拽上传区域
 */
import { useCallback, useRef, useState } from 'react'
import { Upload, FileText, PlusCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

/** 未指定时与历史行为一致（较宽的通用列表） */
const DEFAULT_ACCEPT =
  '.pdf,.docx,.txt,.md,.xlsx,.xls,.pptx,.ppt,.csv,.zip,.html,.json,.xml,.yaml,.yml,.jpg,.jpeg,.png,.webp'

const DEFAULT_FORMAT_TAGS = ['PDF', 'DOCX', 'XLSX', 'IMG', 'ZIP', 'JSON']

interface FileUploadDropzoneProps {
  onFilesSelected: (files: File[]) => void
  className?: string
  compact?: boolean
  compactText?: string
  compactHint?: string
  /** 文件选择器过滤；不传则用通用默认 */
  accept?: string
  /** 底部「支持格式」角标；不传则沿用通用默认并显示「& More」 */
  formatTags?: string[]
}

export function FileUploadDropzone({
  onFilesSelected,
  className,
  compact = false,
  compactText,
  compactHint,
  accept: acceptProp,
  formatTags: formatTagsProp,
}: FileUploadDropzoneProps) {
  const accept = acceptProp ?? DEFAULT_ACCEPT
  const formatTags = formatTagsProp ?? DEFAULT_FORMAT_TAGS
  const showMoreFormats = formatTagsProp === undefined
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  /**
   * 处理拖拽进入
   */
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  /**
   * 处理拖拽离开
   */
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  /**
   * 处理拖拽悬停
   */
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  /**
   * 处理文件放置
   */
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)

      const files = Array.from(e.dataTransfer.files)
      if (files.length > 0) {
        onFilesSelected(files)
      }
    },
    [onFilesSelected]
  )

  /**
   * 处理文件选择
   */
  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || [])
      if (files.length > 0) {
        onFilesSelected(files)
      }
      // 重置 input，允许选择相同文件
      e.target.value = ''
    },
    [onFilesSelected]
  )

  /**
   * 触发文件选择
   */
  const handleClick = useCallback(() => {
    inputRef.current?.click()
  }, [])

  if (compact) {
    return (
      <div
        className={cn(
          'w-full rounded-lg border-2 border-dashed px-5 py-4 text-center transition-all duration-300 cursor-pointer',
          isDragging
            ? 'border-primary bg-primary/5 text-primary shadow-sm'
            : 'border-gray-300 text-muted-foreground hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50/50 dark:border-gray-700 dark:hover:bg-blue-950/20',
          className
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          className="hidden"
          onChange={handleFileSelect}
        />
        <div className="flex flex-col items-center gap-1.5">
          <div className="flex items-center gap-2 font-medium">
            <Upload className={cn('h-4 w-4', isDragging && 'animate-bounce')} />
            <span>{compactText ?? '继续添加文件'}</span>
          </div>
          <p className="text-xs text-muted-foreground/80">
            {compactHint ?? '支持拖拽到这里，或点击选择文件'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'group relative border-2 border-dashed rounded-3xl p-12 text-center transition-all duration-500 cursor-pointer overflow-hidden flex items-center justify-center min-h-[360px]',
        isDragging
          ? 'border-primary bg-primary/[0.02] scale-[1.01] shadow-2xl shadow-primary/5'
          : 'border-muted-foreground/15 hover:border-primary/30 hover:bg-muted/20',
        className
      )}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      {/* 极简背景氛围 */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-b from-transparent to-muted/10 opacity-50 pointer-events-none" />

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        className="hidden"
        onChange={handleFileSelect}
      />

      <div className="flex flex-col items-center gap-8 max-w-[280px]">
        {isDragging ? (
          <div className="animate-in zoom-in duration-500 flex flex-col items-center">
            <div className="relative mb-6">
              <div className="absolute inset-0 bg-primary/20 blur-3xl rounded-full scale-150" />
              <div className="relative bg-primary text-primary-foreground p-5 rounded-2xl shadow-xl shadow-primary/20 ring-1 ring-white/20">
                <Upload className="h-10 w-10 animate-bounce" />
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xl font-bold text-primary tracking-tight">在这里松开</p>
              <p className="text-sm text-primary/60 font-medium">释放后即可自动流式上传</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <div className="relative mb-8 group-hover:scale-105 transition-transform duration-700">
              <div className="absolute inset-0 bg-primary/10 blur-2xl rounded-full scale-125 opacity-0 group-hover:opacity-100 transition-opacity duration-1000" />
              <div className="relative rounded-2xl border bg-background/80 p-5 shadow-sm backdrop-blur-sm group-hover:shadow-md transition-shadow">
                <FileText className="h-10 w-10 text-primary/80" />
                <div className="absolute -bottom-1 -right-1 bg-primary text-white rounded-full p-1 shadow-lg border-2 border-background scale-0 group-hover:scale-100 transition-transform duration-300">
                  <PlusCircle className="h-3 w-3" />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <p className="text-lg font-bold tracking-tight text-foreground/80 leading-snug">
                  拖拽文件到这里
                </p>
                <p className="text-sm font-medium">
                  或者 <span className="text-primary hover:underline decoration-primary/30 underline-offset-4">点击浏览文件</span>
                </p>
              </div>

              <div className="pt-2">
                <p className="text-[11px] text-muted-foreground/60 font-bold uppercase tracking-[0.1em] mb-3">支持格式</p>
                <div className="flex flex-wrap items-center justify-center gap-1.5 text-[10px]">
                  {formatTags.map((ext) => (
                    <span
                      key={ext}
                      className="px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground/70 font-bold border border-border/40"
                    >
                      {ext}
                    </span>
                  ))}
                  {showMoreFormats ? (
                    <span className="text-muted-foreground/40 font-bold px-1">& More</span>
                  ) : null}
                </div>
              </div>

              <div className="pt-4 space-y-1">
                <p className="text-[11px] text-muted-foreground/50 font-medium">
                  单个文件上限 100MB
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
