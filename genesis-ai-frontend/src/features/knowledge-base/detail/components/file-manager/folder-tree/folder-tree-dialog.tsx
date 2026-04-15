/**
 * 文件夹创建/编辑对话框组件（弹窗模式）
 */
import { Plus, X, HelpCircle } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { getTagColorClass } from './tag-color-utils'
import type { FolderFormData, TagDefinition } from './folder-tree-types'
import type { Tag } from '@/lib/api/folder.types'

interface FolderTreeDialogProps {
  open: boolean
  mode: 'create' | 'edit'
  folderForm: FolderFormData
  newTag: string
  tagDefinitions: TagDefinition[]
  currentFolderTags?: Tag[]
  parentFolderName?: string
  isSubmitting: boolean
  onOpenChange: (open: boolean) => void
  onFolderFormChange: (form: FolderFormData) => void
  onNewTagChange: (value: string) => void
  onAddTag: () => void
  onRemoveTag: (tag: string) => void
  onSelectTag?: (tag: TagDefinition) => void
  onOpenTagDetail: (tag?: TagDefinition, tagName?: string) => void
  onSubmit: () => void
}

export function FolderTreeDialog({
  open,
  mode,
  folderForm,
  newTag,
  tagDefinitions,
  currentFolderTags = [],
  parentFolderName,
  isSubmitting,
  onOpenChange,
  onFolderFormChange,
  onNewTagChange,
  onAddTag,
  onRemoveTag,
  onSelectTag,
  onOpenTagDetail,
  onSubmit,
}: FolderTreeDialogProps) {
  const getTagDefinition = (tagName: string) => {
    // 优先从当前文件夹的完整标签数据中查找
    const folderTag = currentFolderTags.find((t) => t.name === tagName)
    if (folderTag) {
      return {
        id: folderTag.id,
        name: folderTag.name,
        color: folderTag.color || undefined,
        description: folderTag.description || undefined,
        synonyms: folderTag.aliases || undefined,
      } as TagDefinition
    }
    // 其次从全局标签定义中查找
    return tagDefinitions.find((t) => t.name === tagName)
  }

  return (
    <TooltipProvider>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto"
          onPointerDownOutside={(e) => e.preventDefault()}
          onEscapeKeyDown={(e) => e.preventDefault()}
        >
          <DialogHeader className="space-y-3">
            <DialogTitle className="text-2xl font-bold bg-gradient-to-r from-green-600 to-blue-600 bg-clip-text text-transparent">
              {mode === 'create' ? '新建文件夹' : '编辑文件夹'}
            </DialogTitle>
            {parentFolderName && (
              <DialogDescription className="text-sm text-muted-foreground">
                在 <span className="font-medium text-foreground">"{parentFolderName}"</span> 下创建子文件夹
              </DialogDescription>
            )}
          </DialogHeader>

          <div className="space-y-6 py-6">
            {/* 文件夹名称 */}
            <div className="space-y-3">
              <Label htmlFor="folder-name" className="text-base font-semibold text-gray-800 dark:text-gray-200">
                文件夹名称 <span className="text-red-500">*</span>
              </Label>
              <Input
                id="folder-name"
                placeholder="输入文件夹名称"
                value={folderForm.name}
                onChange={(e) => onFolderFormChange({ ...folderForm, name: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    onSubmit()
                  }
                }}
                className="h-11 border-2 focus:border-green-400 transition-colors"
                autoFocus
              />
            </div>

            {/* 文件夹摘要 */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Label htmlFor="folder-summary" className="text-base font-semibold text-gray-800 dark:text-gray-200">
                  文件夹摘要
                </Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className='h-4 w-4 text-muted-foreground hover:text-green-500 cursor-help transition-colors' />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs">
                    <p className="text-sm">摘要可以帮助 AI 更好地理解文件夹的内容，提升检索准确度</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Textarea
                id="folder-summary"
                placeholder="简要描述这个文件夹的用途和内容（可选）"
                value={folderForm.summary}
                onChange={(e) => onFolderFormChange({ ...folderForm, summary: e.target.value })}
                rows={3}
                className="resize-none border-2 focus:border-green-400 transition-colors"
              />
            </div>

            {/* 标签 */}
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <Label className="text-base font-semibold text-gray-800 dark:text-gray-200">标签</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className='h-4 w-4 text-muted-foreground hover:text-blue-500 cursor-help transition-colors' />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs">
                    <p className="text-sm">标签用于快速分类和筛选文件夹，支持颜色标记和语义描述</p>
                  </TooltipContent>
                </Tooltip>
                <div className="flex-1"></div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 gap-2 hover:bg-blue-50 hover:border-blue-300 dark:hover:bg-blue-950/30"
                  onClick={() => onOpenTagDetail(undefined, newTag.trim() || undefined)}
                >
                  <Plus className="h-3.5 w-3.5" />
                  详细设置
                </Button>
              </div>

              <div className="flex gap-3">
                <Input
                  placeholder="输入标签名称（快速添加）"
                  value={newTag}
                  onChange={(e) => onNewTagChange(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      onAddTag()
                    }
                  }}
                  className="flex-1 h-10 border-2 focus:border-blue-400 transition-colors"
                />
                <Button 
                  onClick={onAddTag} 
                  size="icon" 
                  className="h-10 w-10 bg-blue-600 hover:bg-blue-700 shadow-md" 
                  title="快速添加"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>

              {/* 输入提示 */}
              {newTag.trim() && (
                <div className='px-3 py-2 rounded-md bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800'>
                  <p className="text-sm">
                    {tagDefinitions.find((t) => t.name.toLowerCase() === newTag.trim().toLowerCase()) ? (
                      <span className="text-blue-700 dark:text-blue-300 font-medium">
                        ✓ 标签已存在，点击 + 直接添加
                      </span>
                    ) : (
                      <span className="text-blue-600 dark:text-blue-400">
                        + 将创建新标签 "{newTag.trim()}"
                      </span>
                    )}
                  </p>
                </div>
              )}

              {/* 可选标签 */}
              {tagDefinitions.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400">可选标签：</p>
                  <div className="flex flex-wrap gap-2 max-h-[120px] overflow-y-auto p-3 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30">
                    {tagDefinitions
                      .filter((t) => !folderForm.tags.includes(t.name))
                      .slice(0, 15)
                      .map((tag) => (
                        <Badge
                          key={tag.id}
                          variant="outline"
                          className={cn(
                            'cursor-pointer hover:scale-105 text-sm py-1 px-3 h-8 transition-all duration-200 gap-2 shadow-sm hover:shadow-md',
                            tag.color === 'blue' && 'border-blue-300 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-950/50',
                            tag.color === 'green' && 'border-green-300 text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-950/50',
                            tag.color === 'purple' && 'border-purple-300 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-950/50',
                            tag.color === 'red' && 'border-red-300 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-950/50',
                            tag.color === 'yellow' && 'border-yellow-300 text-yellow-700 dark:text-yellow-300 hover:bg-yellow-100 dark:hover:bg-yellow-950/50',
                            tag.color === 'gray' && 'border-gray-300 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800',
                            !tag.color && 'border-blue-300 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-950/50' // 默认蓝色
                          )}
                          onClick={() => {
                            onFolderFormChange({
                              ...folderForm,
                              tags: [...folderForm.tags, tag.name],
                            })
                            onSelectTag?.(tag)
                          }}
                        >
                          <Plus className="h-3.5 w-3.5 opacity-60" />
                          {tag.name}
                        </Badge>
                      ))}
                    {tagDefinitions.filter((t) => !folderForm.tags.includes(t.name)).length > 15 && (
                      <span className="text-xs text-muted-foreground self-center">还有更多...</span>
                    )}
                  </div>
                </div>
              )}

              {/* 已选标签 */}
              {folderForm.tags.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400">已选标签：</p>
                  <div className="flex flex-wrap gap-2 p-4 rounded-lg border-2 border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
                    {folderForm.tags.map((tag) => {
                      const tagDef = getTagDefinition(tag)
                      return (
                        <Badge
                          key={tag}
                          variant="secondary"
                          className={cn(
                            'gap-2 pr-2 text-sm py-1.5 px-3 cursor-pointer hover:scale-105 transition-all duration-200 shadow-sm hover:shadow-md border',
                            getTagColorClass(tagDef?.color)
                          )}
                          onClick={() => {
                            // 查找已存在的标签定义
                            const existingTag = tagDefinitions.find((t) => t.name === tag)
                            // 如果找到了，传递完整的标签对象；否则只传递标签名称
                            if (existingTag) {
                              onOpenTagDetail(existingTag)
                            } else {
                              onOpenTagDetail(undefined, tag)
                            }
                          }}
                          title={tagDef ? '点击编辑标签详情' : '点击为此标签添加详细信息'}
                        >
                          {tag}
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              onRemoveTag(tag)
                            }}
                            className="ml-1 hover:bg-red-500/20 rounded-full p-1 transition-colors"
                            title="移除标签"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </Badge>
                      )
                    })}
                  </div>
                </div>
              )}
              
              {folderForm.tags.length === 0 && (
                <div className='text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg'>
                  <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                    <Plus className="h-6 w-6 text-gray-400" />
                  </div>
                  <p className='text-sm'>暂无标签，请添加标签进行分类</p>
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="gap-3 pt-6 border-t">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting} className="px-6">
              取消
            </Button>
            <Button 
              onClick={onSubmit} 
              disabled={isSubmitting || !folderForm.name.trim()}
              className="px-6 bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700 shadow-md"
            >
              {isSubmitting
                ? mode === 'create'
                  ? '创建中...'
                  : '保存中...'
                : mode === 'create'
                  ? '创建文件夹'
                  : '保存更改'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  )
}
