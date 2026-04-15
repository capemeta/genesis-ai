/**
 * 抽取预览弹窗
 */

import { useState, useEffect } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { WebPagePreviewResponse } from '@/lib/api/web-sync'
import type { FetchMode } from '../../types'
import { validateCssSelectorSyntax } from '../../utils'

export interface PreviewExtractDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  selectedPageId: string
  selectedPageConfig?: {
    timeoutSeconds: number
    contentSelector: string
  }
  selectedPageFetchMode?: FetchMode
  isPending: boolean
  previewResult: WebPagePreviewResponse | null
  onPreview: (payload: {
    kb_web_page_id: string
    fetch_mode: FetchMode
    timeout_seconds: number
    content_selector?: string
    include_raw_html: boolean
  }) => void
}

export function PreviewExtractDialog({
  open,
  onOpenChange,
  selectedPageId,
  selectedPageConfig,
  selectedPageFetchMode,
  isPending,
  previewResult,
  onPreview,
}: PreviewExtractDialogProps) {
  const [previewSelector, setPreviewSelector] = useState('')
  const [previewFetchMode, setPreviewFetchMode] = useState<FetchMode>('auto')
  const [previewTimeoutSeconds, setPreviewTimeoutSeconds] = useState(20)
  const [previewTab, setPreviewTab] = useState<'text' | 'html' | 'render'>('text')

  // 当配置变化时初始化
  useEffect(() => {
    if (selectedPageConfig) {
      setPreviewSelector(selectedPageConfig.contentSelector)
      setPreviewTimeoutSeconds(selectedPageConfig.timeoutSeconds)
    }
    if (selectedPageFetchMode) {
      setPreviewFetchMode(selectedPageFetchMode)
    }
  }, [selectedPageConfig, selectedPageFetchMode])

  const handlePreview = () => {
    const selectorError = validateCssSelectorSyntax(previewSelector)
    if (selectorError) {
      toast.error(selectorError)
      return
    }
    onPreview({
      kb_web_page_id: selectedPageId,
      fetch_mode: previewFetchMode,
      timeout_seconds: Math.max(5, Number(previewTimeoutSeconds || 20)),
      content_selector: previewSelector.trim() || undefined,
      include_raw_html: true,
    })
  }

  const handleClose = (open: boolean) => {
    onOpenChange(open)
    if (!open) {
      setPreviewTab('text')
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-5xl max-h-[86vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>网页抽取预览</DialogTitle>
          <DialogDescription>
            可直接预览当前页面在指定抓取模式和选择器下的抽取效果。渲染预览为参考视图，建议以提取文本和 HTML 代码为准。
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50/70 p-3 md:grid-cols-4">
          <div className="space-y-1.5 md:col-span-2">
            <Label className="text-xs text-slate-600">CSS 选择器（可选）</Label>
            <Input
              placeholder="例如：main, .article-content, #content"
              value={previewSelector}
              onChange={event => setPreviewSelector(event.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-slate-600">抓取模式</Label>
            <Select value={previewFetchMode} onValueChange={value => setPreviewFetchMode(value as FetchMode)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">自动回退</SelectItem>
                <SelectItem value="static">仅静态 HTML</SelectItem>
                <SelectItem value="browser">优先浏览器渲染</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-slate-600">超时（秒）</Label>
            <Input
              type="number"
              min={5}
              max={120}
              value={previewTimeoutSeconds}
              onChange={event => setPreviewTimeoutSeconds(Number(event.target.value || 20))}
            />
          </div>
          <div className="md:col-span-4 flex items-center justify-between">
            <div className="text-xs text-slate-500">
              {previewResult ? (
                <>
                  extractor: {previewResult.extractor} · HTTP: {previewResult.http_status ?? '—'} · selector命中: {previewResult.selector_summary.matched_count}
                </>
              ) : (
                '点击"执行预览"查看提取结果、HTML代码和渲染视图。'
              )}
            </div>
            <Button size="sm" disabled={!selectedPageId || isPending} onClick={handlePreview}>
              {isPending ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Search className="mr-1.5 h-3.5 w-3.5" />}
              执行预览
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
          <Button size="sm" variant={previewTab === 'text' ? 'default' : 'outline'} onClick={() => setPreviewTab('text')}>提取文本</Button>
          <Button size="sm" variant={previewTab === 'html' ? 'default' : 'outline'} onClick={() => setPreviewTab('html')}>HTML代码</Button>
          <Button size="sm" variant={previewTab === 'render' ? 'default' : 'outline'} onClick={() => setPreviewTab('render')}>渲染预览</Button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-slate-200 bg-white">
          {!previewResult ? (
            <div className="flex h-full min-h-[280px] items-center justify-center text-sm text-slate-500">
              暂无预览结果，请先执行预览
            </div>
          ) : previewTab === 'text' ? (
            <pre className="whitespace-pre-wrap break-words p-3 text-xs leading-5 text-slate-700">{previewResult.extracted_text || '（空）'}</pre>
          ) : previewTab === 'html' ? (
            <pre className="whitespace-pre-wrap break-all p-3 text-xs leading-5 text-slate-700">{previewResult.raw_html || '（空）'}</pre>
          ) : (
            <iframe
              title="网页渲染预览"
              className="h-[58vh] w-full"
              sandbox=""
              srcDoc={previewResult.raw_html || '<html><body>（空）</body></html>'}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
