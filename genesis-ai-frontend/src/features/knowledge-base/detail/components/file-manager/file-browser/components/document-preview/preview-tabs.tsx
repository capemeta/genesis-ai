/**
 * 预览标签页组件
 */
import { FileText, BookOpen, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PreviewMode, DocumentPreviewConfig } from './types'
import { getFileTypeLabel } from './utils'

interface PreviewTabsProps {
  mode: PreviewMode
  onModeChange: (mode: PreviewMode) => void
  config: DocumentPreviewConfig
}

export function PreviewTabs({ mode, onModeChange, config }: PreviewTabsProps) {
  return (
    <div className="h-11 border-b px-4 flex items-center justify-between shrink-0 bg-gradient-to-r from-slate-50/80 to-blue-50/30 dark:from-slate-900/80 dark:to-blue-950/30">
      {/* 标签页 */}
      <div className="flex items-center gap-1 bg-white/60 dark:bg-slate-900/60 rounded-lg p-1 border border-slate-200/60 dark:border-slate-700/60 shadow-sm">
        {/* 源文件标签 */}
        {config.hasSourcePreview && (
          <button
            onClick={() => onModeChange('source')}
            className={cn(
              'relative flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200',
              mode === 'source'
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100/50 dark:hover:bg-slate-800/50'
            )}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>源文件</span>
            <span
              className={cn(
                'text-[10px] px-1.5 py-0.5 rounded font-mono',
                mode === 'source'
                  ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
              )}
            >
              {getFileTypeLabel(config.sourceFileType)}
            </span>
            {mode === 'source' && (
              <div className="absolute inset-0 rounded-md ring-2 ring-blue-500/20 dark:ring-blue-400/20 pointer-events-none" />
            )}
          </button>
        )}

        {/* 解析视图标签 */}
        {config.hasParsedPreview && (
          <button
            onClick={() => onModeChange('parsed')}
            className={cn(
              'relative flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200',
              mode === 'parsed'
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100/50 dark:hover:bg-slate-800/50'
            )}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>解析视图</span>
            <span
              className={cn(
                'text-[10px] px-1.5 py-0.5 rounded font-mono',
                mode === 'parsed'
                  ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
              )}
            >
              Markdown
            </span>
            {mode === 'parsed' && (
              <div className="absolute inset-0 rounded-md ring-2 ring-emerald-500/20 dark:ring-emerald-400/20 pointer-events-none" />
            )}
          </button>
        )}
      </div>

      {/* 右侧提示信息 */}
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        {mode === 'source' && (
          <>
            <FileText className="h-3.5 w-3.5" />
            <span>原始上传的文件</span>
          </>
        )}
        {mode === 'parsed' && (
          <>
            <Sparkles className="h-3.5 w-3.5 text-emerald-500" />
            <span>系统解析后的内容</span>
          </>
        )}
      </div>
    </div>
  )
}
