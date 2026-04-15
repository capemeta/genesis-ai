/**
 * 编辑页面弹窗
 */

import { useState, useEffect } from 'react'
import { Loader2, Type, Settings, Layers, Clock, Info, Lock, Save } from 'lucide-react'
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
import type { WebPageItem } from '@/lib/api/web-sync'
import type { FetchMode, WebChunkingDraft } from '../../types'
import { DEFAULT_CHUNKING_CONFIG, DEFAULT_TIMEOUT_SECONDS } from '../../constants'
import { validateCssSelectorSyntax, getWebPageConfigDraft, buildWebPageConfigPayload } from '../../utils'

export interface EditPageDialogProps {
  editingPage: WebPageItem | null
  onOpenChange: (open: boolean) => void
  kbId: string
  isPending: boolean
  onUpdate: (payload: {
    kb_web_page_id: string
    display_name: string
    folder_id: string | undefined
    fetch_mode: FetchMode
    page_config: ReturnType<typeof buildWebPageConfigPayload>
  }) => void
}

export function EditPageDialog({
  editingPage,
  onOpenChange,
  kbId,
  isPending,
  onUpdate,
}: EditPageDialogProps) {
  const [editDisplayName, setEditDisplayName] = useState('')
  const [editFolderId, setEditFolderId] = useState<string | null>(null)
  const [editFetchMode, setEditFetchMode] = useState<FetchMode>('auto')
  const [editTimeoutSeconds, setEditTimeoutSeconds] = useState(DEFAULT_TIMEOUT_SECONDS)
  const [editContentSelector, setEditContentSelector] = useState('')
  const [editChunking, setEditChunking] = useState<WebChunkingDraft>({ ...DEFAULT_CHUNKING_CONFIG })

  // 当 editingPage 变化时初始化表单
  useEffect(() => {
    if (editingPage) {
      setEditDisplayName(editingPage.name || '')
      setEditFolderId(editingPage.folder_id ?? null)
      setEditFetchMode((editingPage.fetch_mode || 'auto') as FetchMode)
      const configDraft = getWebPageConfigDraft(editingPage.page_config)
      setEditTimeoutSeconds(configDraft.timeoutSeconds)
      setEditContentSelector(configDraft.contentSelector)
      setEditChunking(configDraft.chunking)
    }
  }, [editingPage])

  const handleSave = () => {
    if (!editingPage) return
    const selectorError = validateCssSelectorSyntax(editContentSelector)
    if (selectorError) {
      toast.error(selectorError)
      return
    }
    onUpdate({
      kb_web_page_id: editingPage.kb_web_page_id,
      display_name: editDisplayName.trim(),
      folder_id: editFolderId !== (editingPage.folder_id ?? null)
        ? (editFolderId === null ? '__root__' : editFolderId)
        : undefined,
      fetch_mode: editFetchMode,
      page_config: buildWebPageConfigPayload(editTimeoutSeconds, editContentSelector, editChunking),
    })
  }

  const handleClose = (open: boolean) => {
    if (!open) {
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={Boolean(editingPage)} onOpenChange={handleClose}>
      <DialogContent className="max-w-xl border-none p-0 shadow-2xl">
        <div className="relative overflow-hidden rounded-lg bg-white">
          {/* Header Section - Light System */}
          <div className="border-b border-slate-100 bg-white px-6 py-6 transition-all">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 shadow-sm ring-1 ring-indigo-100/50 transition-colors group-hover:bg-indigo-100">
                <Settings className="h-6 w-6 transition-transform hover:scale-110" />
              </div>
              <div className="space-y-1">
                <DialogTitle className="text-xl font-bold tracking-tight text-slate-900">编辑网页页面</DialogTitle>
                <DialogDescription className="text-[13px] text-slate-500 font-medium">
                  管理当前页面的元信息与同步策略。
                </DialogDescription>
              </div>
            </div>
          </div>

          <div className="p-6">
            <div className="space-y-6">
              {/* Essential Config Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-100 pb-2">
                  <Type className="h-4 w-4 text-blue-600" />
                  <span className="text-sm font-semibold text-slate-800">基本信息</span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="md:col-span-2">
                    <FolderMountField
                      kbId={kbId}
                      value={editFolderId}
                      onChange={setEditFolderId}
                      label="挂载目录"
                    />
                  </div>

                  <div className="space-y-2 md:col-span-2">
                    <Label className="flex items-center gap-1.5 text-[13px] font-medium text-slate-700">
                      页面 URL <span className="text-slate-400 font-normal italic">(不可编辑)</span>
                    </Label>
                    <div className="relative group">
                      <div className="flex h-10 items-center truncate rounded-md border border-slate-100 bg-slate-50 pl-3 pr-10 text-sm text-slate-500 select-all font-mono">
                        {editingPage?.url}
                      </div>
                      <div className="absolute right-3 top-3">
                        <Lock className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2 md:col-span-2">
                    <Label className="flex items-center gap-1.5 text-[13px] font-medium text-slate-700">
                      页面标题 <span className="text-red-500">*</span>
                    </Label>
                    <div className="relative group">
                      <Input
                        placeholder="请输入页面标题"
                        value={editDisplayName}
                        onChange={e => setEditDisplayName(e.target.value)}
                        className="h-10 pl-3 pr-10 border-slate-200 focus-visible:ring-blue-500 transition-all group-hover:border-blue-400"
                      />
                      <div className="absolute right-3 top-3 pointer-events-none">
                        <Type className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Advanced Controls Section */}
              <div className="rounded-xl border border-blue-100 bg-blue-50/30 p-5 space-y-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="rounded-md bg-blue-100 p-1">
                      <Settings className="h-4 w-4 text-blue-600" />
                    </div>
                    <span className="text-sm font-semibold text-blue-900 italic">同步与分块深度配置</span>
                  </div>
                  <div className="flex items-center gap-1 text-[11px] text-blue-600 font-medium">
                    <Info className="h-3 w-3" />
                    更改后将在下次同步生效
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label className="flex items-center gap-1.5 text-[12px] font-medium text-slate-600">
                      抓取模式
                    </Label>
                    <Select value={editFetchMode} onValueChange={value => setEditFetchMode(value as FetchMode)}>
                      <SelectTrigger className="h-9 border-slate-200 bg-white shadow-none">
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
                        value={editTimeoutSeconds}
                        onChange={e => setEditTimeoutSeconds(Number(e.target.value || DEFAULT_TIMEOUT_SECONDS))}
                        className="h-9 pr-10 border-slate-200 bg-white transition-all group-hover:border-blue-400"
                      />
                      <div className="absolute right-3 top-2.5 pointer-events-none">
                        <Clock className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="flex items-center gap-1.5 text-[12px] font-medium text-slate-600">
                      CSS 选择器 <span className="text-slate-400 font-normal">(指定内容区)</span>
                    </Label>
                    <div className="relative group">
                      <Input
                        placeholder="main, article, .content"
                        value={editContentSelector}
                        onChange={e => setEditContentSelector(e.target.value)}
                        className="h-9 pr-10 border-slate-200 bg-white transition-all group-hover:border-blue-400 text-xs font-mono"
                      />
                      <div className="absolute right-3 top-2.5 pointer-events-none">
                        <Layers className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="flex items-center gap-1.5 text-[12px] font-medium text-slate-600">
                      Token 上限 (分块大小)
                    </Label>
                    <Input
                      type="number"
                      min={128}
                      max={8192}
                      value={editChunking.max_embed_tokens}
                      onChange={e => setEditChunking(prev => ({ ...prev, max_embed_tokens: Number(e.target.value || DEFAULT_CHUNKING_CONFIG.max_embed_tokens) }))}
                      className="h-9 border-slate-200 bg-white transition-all group-hover:border-blue-400"
                    />
                  </div>
                </div>
                <p className="text-[11px] text-blue-600/70 leading-relaxed italic border-l-2 border-blue-200 pl-2 py-0.5">
                  修改后并不会立即重新加载内容，请手动发起同步以刷新知识库块。
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
                disabled={!editingPage || isPending}
                onClick={handleSave}
              >
                {isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    正在保存...
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    保存修改
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
