/**
 * 新增页面弹窗
 */

import { useState } from 'react'
import { Plus, Loader2, Globe, Type, Settings, Layers, Clock, Info } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { FolderMountField } from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/workbenches/shared/folder-mount-field'
import type { FetchMode, WebChunkingDraft } from '../../types'
import { DEFAULT_CHUNKING_CONFIG, DEFAULT_TIMEOUT_SECONDS } from '../../constants'
import { validateCssSelectorSyntax } from '../../utils'
import { buildWebPageConfigPayload } from '../../utils'

export interface AddPageDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kbId: string
  selectedFolderId: string | null
  isPending: boolean
  onCreate: (payload: {
    kb_id: string
    url: string
    folder_id: string | null
    display_name?: string
    fetch_mode: FetchMode
    page_config: ReturnType<typeof buildWebPageConfigPayload>
  }) => void
}

export function AddPageDialog({
  open,
  onOpenChange,
  kbId,
  selectedFolderId,
  isPending,
  onCreate,
}: AddPageDialogProps) {
  const [url, setUrl] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [createFolderId, setCreateFolderId] = useState<string | null>(selectedFolderId)
  const [createFetchMode, setCreateFetchMode] = useState<FetchMode>('auto')
  const [createTimeoutSeconds, setCreateTimeoutSeconds] = useState(DEFAULT_TIMEOUT_SECONDS)
  const [createContentSelector, setCreateContentSelector] = useState('')
  const [createChunking, setCreateChunking] = useState<WebChunkingDraft>({ ...DEFAULT_CHUNKING_CONFIG })

  const handleCreate = () => {
    if (!url.trim()) {
      toast.error('请输入 URL')
      return
    }
    const selectorError = validateCssSelectorSyntax(createContentSelector)
    if (selectorError) {
      toast.error(selectorError)
      return
    }
    onCreate({
      kb_id: kbId,
      url: url.trim(),
      folder_id: createFolderId,
      display_name: displayName.trim() || undefined,
      fetch_mode: createFetchMode,
      page_config: buildWebPageConfigPayload(createTimeoutSeconds, createContentSelector, createChunking),
    })
  }

  const handleClose = (open: boolean) => {
    onOpenChange(open)
    if (!open) {
      setUrl('')
      setDisplayName('')
      setCreateFolderId(selectedFolderId)
      setCreateFetchMode('auto')
      setCreateTimeoutSeconds(DEFAULT_TIMEOUT_SECONDS)
      setCreateContentSelector('')
      setCreateChunking({ ...DEFAULT_CHUNKING_CONFIG })
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-xl border-none p-0 shadow-2xl">
        <div className="relative overflow-hidden rounded-lg bg-white">
          {/* Header Section - Light System */}
          <div className="border-b border-slate-100 bg-white px-6 py-6 transition-all">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 shadow-sm ring-1 ring-blue-100/50">
                <Globe className="h-6 w-6 transition-transform hover:scale-110" />
              </div>
              <div className="space-y-1">
                <DialogTitle className="text-xl font-bold tracking-tight text-slate-900">新增网页页面</DialogTitle>
                <DialogDescription className="text-[13px] text-slate-500 leading-relaxed font-medium">
                  同步外部网页资源至知识库，可灵活配置抓取深度与分块策略。
                </DialogDescription>
              </div>
            </div>
          </div>

          <div className="p-6">
            <div className="space-y-6">
              {/* Basic Settings Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-100 pb-2">
                  <Globe className="h-4 w-4 text-blue-600" />
                  <span className="text-sm font-semibold text-slate-800">基本信息</span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="md:col-span-2">
                    <FolderMountField
                      kbId={kbId}
                      value={createFolderId}
                      onChange={setCreateFolderId}
                      label="挂载目录"
                    />
                  </div>

                  <div className="space-y-2 md:col-span-2">
                    <Label className="flex items-center gap-1.5 text-[13px] font-medium text-slate-700">
                      页面 URL <span className="text-red-500">*</span>
                    </Label>
                    <div className="relative group">
                      <Input
                        placeholder="https://docs.example.com/guide"
                        value={url}
                        onChange={e => setUrl(e.target.value)}
                        className="h-10 pl-3 pr-10 border-slate-200 focus-visible:ring-blue-500 transition-all group-hover:border-blue-400"
                      />
                      <div className="absolute right-3 top-3 pointer-events-none">
                        <Globe className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2 md:col-span-2">
                    <Label className="flex items-center gap-1.5 text-[13px] font-medium text-slate-700">
                      显示名称 <span className="text-slate-400 font-normal">(可选)</span>
                    </Label>
                    <div className="relative group">
                      <Input
                        placeholder="给页面起个好记的名字"
                        value={displayName}
                        onChange={e => setDisplayName(e.target.value)}
                        className="h-10 pl-3 pr-10 border-slate-200 focus-visible:ring-blue-500 transition-all group-hover:border-blue-400"
                      />
                      <div className="absolute right-3 top-3 pointer-events-none">
                        <Type className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Advanced Settings Section */}
              <div className="rounded-xl border border-blue-100 bg-blue-50/30 p-5 space-y-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="rounded-md bg-blue-100 p-1">
                      <Settings className="h-4 w-4 text-blue-600" />
                    </div>
                    <span className="text-sm font-semibold text-blue-900 italic">高级抓取与分块设置</span>
                  </div>
                  <div className="flex items-center gap-1 text-[11px] text-blue-600 font-medium">
                    <Info className="h-3 w-3" />
                    按标题和元素精确提取
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label className="flex items-center gap-1.5 text-[12px] font-medium text-slate-600">
                      抓取模式
                    </Label>
                    <Select value={createFetchMode} onValueChange={value => setCreateFetchMode(value as FetchMode)}>
                      <SelectTrigger className="h-9 border-slate-200 bg-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="auto">自动回退 (推荐)</SelectItem>
                        <SelectItem value="static">仅静态 HTML</SelectItem>
                        <SelectItem value="browser">浏览器渲染 (动态加速)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label className="flex items-center gap-1.5 text-[12px] font-medium text-slate-600">
                      抓取超时 (秒)
                    </Label>
                    <div className="relative group">
                      <Input
                        type="number"
                        min={5}
                        max={120}
                        value={createTimeoutSeconds}
                        onChange={e => setCreateTimeoutSeconds(Number(e.target.value || DEFAULT_TIMEOUT_SECONDS))}
                        className="h-9 pr-10 border-slate-200 bg-white transition-all group-hover:border-blue-400"
                      />
                      <div className="absolute right-3 top-2.5 pointer-events-none">
                        <Clock className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="flex items-center gap-1.5 text-[12px] font-medium text-slate-600">
                      CSS 选择器 <span className="text-slate-400 font-normal">(指定范围)</span>
                    </Label>
                    <div className="relative group">
                      <Input
                        placeholder="main, article, .content"
                        value={createContentSelector}
                        onChange={e => setCreateContentSelector(e.target.value)}
                        className="h-9 pr-10 border-slate-200 bg-white transition-all group-hover:border-blue-400 text-xs font-mono"
                      />
                      <div className="absolute right-3 top-2.5 pointer-events-none">
                        <Layers className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="flex items-center gap-1.5 text-[12px] font-medium text-slate-600">
                      最大 Token 数 (分块大小)
                    </Label>
                    <Input
                      type="number"
                      min={128}
                      max={8192}
                      value={createChunking.max_embed_tokens}
                      onChange={e => setCreateChunking(prev => ({ ...prev, max_embed_tokens: Number(e.target.value || DEFAULT_CHUNKING_CONFIG.max_embed_tokens) }))}
                      className="h-9 border-slate-200 bg-white transition-all group-hover:border-blue-400"
                    />
                  </div>
                </div>
                <p className="text-[11px] text-blue-600/70 leading-relaxed">
                  网页会先按结构树自动化抽取，分块策略由 `max_embed_tokens` 与模型安全上限共同约束，确保检索效率。
                </p>
              </div>
            </div>

            <DialogFooter className="mt-8">
              <Button
                variant="outline"
                onClick={() => handleClose(false)}
                className="hover:bg-slate-50 border-slate-200"
              >
                取消
              </Button>
              <Button
                className="bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-200 px-6"
                disabled={isPending}
                onClick={handleCreate}
              >
                {isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    创建中...
                  </>
                ) : (
                  <>
                    <Plus className="mr-2 h-4 w-4" />
                    确认新增
                  </>
                )}
              </Button>
            </DialogFooter>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
