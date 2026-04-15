/**
 * 单个上传文件项
 */
import {
  CheckCircle2,
  Loader2,
  X,
  AlertCircle,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { getFileTypeIconUrl } from '../../shared/file-type-icon'
import type { UploadFileItem } from '../hooks/use-file-upload'

interface FileUploadItemProps {
  file: UploadFileItem
  onRemove: () => void
  onCancel: () => void
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`
}

export function FileUploadItem({ file, onRemove, onCancel }: FileUploadItemProps) {
  const isUploading = file.status === 'uploading'
  const isUploaded = file.status === 'uploaded'
  const isError = file.status === 'error'
  const isPending = file.status === 'pending'

  const canRemove = isPending || isError || isUploaded
  const canCancel = isUploading

  return (
    <div
      className={cn(
        'group relative flex items-center gap-4 p-4 rounded-xl border bg-card transition-all duration-300 overflow-hidden',
        isError && 'border-destructive/30 bg-destructive/5',
        isUploaded && 'border-emerald-500/30 bg-emerald-500/[0.02]',
        isUploading && 'border-primary/20 shadow-sm'
      )}
    >
      {/* 成功时的侧边渐变装饰 */}
      {isUploaded && (
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-emerald-400 to-emerald-600" />
      )}

      {/* 文件图标背景装饰 */}
      <div className={cn(
        "flex items-center justify-center w-12 h-12 rounded-xl transition-colors duration-300",
        isUploaded ? "bg-emerald-100/50 dark:bg-emerald-900/20" :
          isError ? "bg-rose-100/50 dark:bg-rose-900/20" :
            "bg-secondary/50 group-hover:bg-secondary"
      )}>
        <img
          src={getFileTypeIconUrl(file.name, file.type)}
          alt=""
          className="h-6 w-6 transition-transform duration-300 group-hover:scale-110 object-contain"
        />
      </div>

      {/* 文件中心内容 */}
      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <TooltipProvider>
              <Tooltip delayDuration={300}>
                <TooltipTrigger asChild>
                  <span className="text-sm font-semibold truncate text-foreground/90 cursor-default">
                    {file.name}
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-md break-all">
                  <p className="text-sm">{file.name}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* 状态徽章 - 采用更现代的设计 */}
            {isUploaded && (
              <Badge variant="secondary" className="h-5 px-1.5 bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200/50 text-[10px] font-bold">
                {file.isDuplicate ? (
                  <span className="flex items-center gap-1"><Zap className="h-2.5 w-2.5" /> 秒传</span>
                ) : '上传成功'}
              </Badge>
            )}

            {isError && (
              <Badge variant="destructive" className="h-5 px-1.5 text-[10px] font-bold bg-rose-500">
                失败
              </Badge>
            )}
          </div>

          <span className="text-[11px] font-medium text-muted-foreground shrink-0">
            {formatFileSize(file.size)}
          </span>
        </div>

        {/* 动态进度展示区域 */}
        <div className="relative pt-1">
          {isUploading ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[10px] font-medium text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" /> 正在上传中...
                </span>
                <span>{file.progress}%</span>
              </div>
              <Progress value={file.progress} className="h-1.5 bg-secondary overflow-hidden">
                {/* 如果 Shadcn Progress 不支持内部渐变，可以通过自定义 class 覆盖 */}
                <div className="h-full bg-gradient-to-r from-primary/80 to-primary transition-all duration-500 ease-out" />
              </Progress>
            </div>
          ) : isUploaded ? (
            <div className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium animate-in fade-in slide-in-from-left-2">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {file.isDuplicate ? '文件已存在，秒传完成' : '文件上传成功'}
            </div>
          ) : isError ? (
            <div className="flex items-start gap-1.5 text-[11px] text-rose-600 dark:text-rose-400 font-medium leading-tight">
              <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>{file.error || '未知错误'}</span>
            </div>
          ) : (
            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              待上传
            </div>
          )}
        </div>
      </div>

      {/* 右侧操作区 */}
      <div className="flex items-center shrink-0">
        {canCancel && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 hover:bg-destructive/10 hover:text-destructive transition-colors shrink-0"
            onClick={onCancel}
            title="取消上传"
          >
            <X className="h-4 w-4" />
          </Button>
        )}

        {canRemove && (
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 text-muted-foreground hover:bg-secondary hover:text-foreground rounded-full transition-all shrink-0"
            onClick={onRemove}
            title="从此列表移除"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  )
}
