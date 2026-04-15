/**
 * 标签详细设置 Sheet（共享组件）
 * 以文件夹树侧边栏逻辑为基准，供文件夹树、文件列表、元数据编辑等复用。
 */
import { Plus, X, Loader2, Tag, Palette, FileText, Info } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import type { TagFormData, TagDefinition } from './tag-types'
import type { TagTargetType } from '@/lib/api/folder.types'

export interface TagDetailSheetProps {
  open: boolean
  tagForm: TagFormData
  newSynonym: string
  editingTag: TagDefinition | null
  defaultTargetType: TagTargetType
  isLoading?: boolean  // 新增：加载状态
  onOpenChange: (open: boolean) => void
  onTagFormChange: (form: TagFormData) => void
  onNewSynonymChange: (value: string) => void
  onAddSynonym: () => void
  onRemoveSynonym: (synonym: string) => void
  onSaveTagDefinition: () => void
}

export function TagDetailSheet({
  open,
  tagForm,
  newSynonym,
  editingTag,
  defaultTargetType,
  isLoading = false,  // 新增：默认为 false
  onOpenChange,
  onTagFormChange,
  onNewSynonymChange,
  onAddSynonym,
  onRemoveSynonym,
  onSaveTagDefinition,
}: TagDetailSheetProps) {
  const targetTypeOptions: Array<{ value: TagTargetType; label: string }> = [
    { value: 'kb', label: '知识库' },
    { value: 'kb_doc', label: '文档' },
    { value: 'folder', label: '文件夹' },
  ]

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:w-[540px] sm:max-w-[540px] p-0 flex flex-col">
        {/* 美化的头部 */}
        <SheetHeader className="px-6 py-5 border-b bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30">
              <Tag className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <SheetTitle className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                {editingTag ? '编辑标签' : '新建标签'}
              </SheetTitle>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                {editingTag 
                  ? '修改后将影响所有使用此标签的文件夹和文档' 
                  : '创建一个新的标签来组织和分类您的内容'
                }
              </p>
            </div>
          </div>
        </SheetHeader>

        {/* 美化的内容区域 */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-6 py-6 space-y-8">
            {/* 基本信息卡片 */}
            <div className="space-y-6">
              <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                <Info className="h-4 w-4" />
                基本信息
              </div>
              
              <div className="space-y-4 pl-6">
                <div className="space-y-3">
                  <Label htmlFor="tag-name" className="text-sm font-medium flex items-center gap-2">
                    标签名称 
                    <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="tag-name"
                    placeholder="输入标签名称，如：重要文档、技术资料"
                    value={tagForm.name}
                    onChange={(e) => onTagFormChange({ ...tagForm, name: e.target.value })}
                    autoFocus
                    className="transition-all duration-200 focus:ring-2 focus:ring-blue-500/20"
                  />
                  {editingTag ? (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800">
                      <div className="w-4 h-4 rounded-full bg-amber-500 flex items-center justify-center mt-0.5">
                        <span className="text-white text-xs font-bold">!</span>
                      </div>
                      <p className="text-xs text-amber-700 dark:text-amber-300">
                        修改标签名称会影响所有使用此标签的资源
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800">
                      <div className="w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center mt-0.5">
                        <span className="text-white text-xs">💡</span>
                      </div>
                      <p className="text-xs text-blue-700 dark:text-blue-300">
                        如果标签已存在，请从"可选标签"中选择
                      </p>
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <Label htmlFor="tag-description" className="text-sm font-medium flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    标签描述
                  </Label>
                  <Textarea
                    id="tag-description"
                    placeholder="描述这个标签的含义和用途，帮助团队成员更好地理解和使用..."
                    value={tagForm.description}
                    onChange={(e) => onTagFormChange({ ...tagForm, description: e.target.value })}
                    rows={3}
                    className="resize-none transition-all duration-200 focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
              </div>
            </div>

            <Separator className="my-6" />

            {/* 适用对象卡片 */}
            <div className="space-y-6">
              <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                <Info className="h-4 w-4" />
                适用对象
              </div>

              <div className="space-y-3 pl-6">
                <div className="flex flex-wrap gap-2">
                  {targetTypeOptions.map((option) => {
                    const active = tagForm.allowedTargetTypes.includes(option.value)
                    return (
                      <Button
                        key={option.value}
                        type="button"
                        variant={active ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => {
                          const exists = tagForm.allowedTargetTypes.includes(option.value)
                          const next = exists
                            ? tagForm.allowedTargetTypes.filter((item) => item !== option.value)
                            : [...tagForm.allowedTargetTypes, option.value]
                          onTagFormChange({
                            ...tagForm,
                            allowedTargetTypes: next,
                          })
                        }}
                      >
                        {option.label}
                      </Button>
                    )
                  })}
                </div>

                <div className="flex items-start gap-2 p-3 rounded-lg bg-purple-50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-800">
                  <div className="w-4 h-4 rounded-full bg-purple-500 flex items-center justify-center mt-0.5">
                    <span className="text-white text-xs">i</span>
                  </div>
                  <p className="text-xs text-purple-700 dark:text-purple-300">
                    当前入口默认建议创建为“{defaultTargetType === 'kb' ? '知识库' : defaultTargetType === 'kb_doc' ? '文档' : '文件夹'}”标签。
                    如需复用，也可以扩展到多个适用对象，但不能把仍在使用中的对象类型随意移除。
                  </p>
                </div>
              </div>
            </div>

            <Separator className="my-6" />

            {/* 同义词管理卡片 */}
            <div className="space-y-6">
              <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                <Tag className="h-4 w-4" />
                同义词管理
              </div>
              
              <div className="space-y-4 pl-6">
                <div className="flex gap-2">
                  <Input
                    placeholder="输入同义词，如：重要、关键、核心"
                    value={newSynonym}
                    onChange={(e) => onNewSynonymChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        onAddSynonym()
                      }
                    }}
                    className="transition-all duration-200 focus:ring-2 focus:ring-blue-500/20"
                  />
                  <Button 
                    onClick={onAddSynonym} 
                    size="icon" 
                    variant="outline" 
                    title="添加同义词"
                    className="shrink-0 hover:bg-blue-50 hover:border-blue-300 dark:hover:bg-blue-950/20"
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                
                {tagForm.synonyms.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex flex-wrap gap-2 p-4 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30">
                      {tagForm.synonyms.map((synonym) => (
                        <Badge 
                          key={synonym} 
                          variant="secondary" 
                          className="gap-1.5 pr-1 py-1.5 bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-300 transition-colors"
                        >
                          <span className="font-medium">{synonym}</span>
                          <button
                            onClick={() => onRemoveSynonym(synonym)}
                            className="ml-1 hover:bg-red-500/20 rounded-full p-1 transition-colors group"
                            title="删除同义词"
                          >
                            <X className="h-3 w-3 text-gray-500 group-hover:text-red-500" />
                          </button>
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                
                <div className="flex items-start gap-2 p-3 rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800">
                  <div className="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center mt-0.5">
                    <span className="text-white text-xs">💡</span>
                  </div>
                  <p className="text-xs text-green-700 dark:text-green-300">
                    同义词可以帮助 AI 更好地理解标签的含义，提升搜索和推荐的准确性
                  </p>
                </div>
              </div>
            </div>

            <Separator className="my-6" />

            {/* 颜色选择卡片 */}
            <div className="space-y-6">
              <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                <Palette className="h-4 w-4" />
                标签颜色
              </div>
              
              <div className="pl-6">
                <RadioGroup
                  value={tagForm.color}
                  onValueChange={(value) => onTagFormChange({ ...tagForm, color: value })}
                  className="grid grid-cols-3 gap-3"
                >
                  {[
                    { value: 'blue', label: '海洋蓝', class: 'bg-blue-500', lightClass: 'bg-blue-100 border-blue-300', darkClass: 'bg-blue-900/30 border-blue-600' },
                    { value: 'green', label: '森林绿', class: 'bg-green-500', lightClass: 'bg-green-100 border-green-300', darkClass: 'bg-green-900/30 border-green-600' },
                    { value: 'purple', label: '优雅紫', class: 'bg-purple-500', lightClass: 'bg-purple-100 border-purple-300', darkClass: 'bg-purple-900/30 border-purple-600' },
                    { value: 'red', label: '活力红', class: 'bg-red-500', lightClass: 'bg-red-100 border-red-300', darkClass: 'bg-red-900/30 border-red-600' },
                    { value: 'yellow', label: '阳光黄', class: 'bg-yellow-500', lightClass: 'bg-yellow-100 border-yellow-300', darkClass: 'bg-yellow-900/30 border-yellow-600' },
                    { value: 'gray', label: '经典灰', class: 'bg-gray-500', lightClass: 'bg-gray-100 border-gray-300', darkClass: 'bg-gray-700/30 border-gray-600' },
                  ].map((color) => (
                    <div key={color.value} className="flex items-center space-x-3">
                      <RadioGroupItem value={color.value} id={color.value} className="sr-only" />
                      <Label 
                        htmlFor={color.value} 
                        className={cn(
                          "flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all duration-200 hover:shadow-sm",
                          tagForm.color === color.value 
                            ? `${color.lightClass} dark:${color.darkClass} shadow-sm` 
                            : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
                        )}
                      >
                        <div className={cn('w-5 h-5 rounded-full shadow-sm', color.class)} />
                        <span className="text-sm font-medium">{color.label}</span>
                        {tagForm.color === color.value && (
                          <div className="ml-auto w-2 h-2 rounded-full bg-current opacity-60" />
                        )}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>
            </div>
          </div>
        </div>

        {/* 美化的底部操作栏 */}
        <div className="px-6 py-4 border-t bg-gray-50/50 dark:bg-gray-800/30">
          <div className="flex justify-end gap-3">
            <Button 
              variant="outline" 
              onClick={() => onOpenChange(false)}
              disabled={isLoading}
              className="px-6 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              取消
            </Button>
            <Button 
              onClick={onSaveTagDefinition} 
              disabled={!tagForm.name.trim() || tagForm.allowedTargetTypes.length === 0 || isLoading}
              className="px-6 bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
            >
              {isLoading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              {editingTag ? '更新标签' : '创建标签'}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
