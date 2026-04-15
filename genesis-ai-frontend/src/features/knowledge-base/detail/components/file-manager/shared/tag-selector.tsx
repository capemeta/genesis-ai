/**
 * 标签选择器组件
 * 
 * 功能：
 * - 展示知识库内所有已有标签（按资源类型过滤）
 * - 支持搜索和过滤
 * - 快速点击选择已有标签
 * - 快速输入添加新标签（暂存状态）
 * - 详细设置创建规范标签（立即保存）
 * - 区分新旧标签（虚线边框）
 */
import { useState, useMemo } from 'react'
import { Plus, X, Search, Tag as TagIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { useAvailableTags } from '@/hooks/use-available-tags'

interface TagSelectorProps {
  kbId: string
  targetType: 'folder' | 'kb_doc'  // 资源类型
  selectedTags: string[]  // 已选中的标签名称
  onTagsChange: (tags: string[]) => void
  onCreateTag: () => void  // 打开详细设置弹窗
}

export function TagSelector({
  kbId,
  targetType,
  selectedTags,
  onTagsChange,
  onCreateTag,
}: TagSelectorProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [newTagInput, setNewTagInput] = useState('')

  // 获取知识库的可选标签（按资源类型过滤）
  const { data: availableTagsData, isLoading } = useAvailableTags(kbId, targetType, {
    search: searchQuery || undefined,
    limit: 200
  })

  const allTags = useMemo(() => {
    return availableTagsData?.data.tags || []
  }, [availableTagsData])

  // 过滤标签（搜索）
  const filteredTags = useMemo(() => {
    if (!searchQuery.trim()) return allTags
    
    const query = searchQuery.toLowerCase()
    return allTags.filter(tag => 
      tag.name.toLowerCase().includes(query) ||
      tag.description?.toLowerCase().includes(query) ||
      tag.aliases?.some(alias => alias.toLowerCase().includes(query))
    )
  }, [allTags, searchQuery])

  // 未选中的标签
  const unselectedTags = useMemo(() => {
    return filteredTags.filter(tag => !selectedTags.includes(tag.name))
  }, [filteredTags, selectedTags])

  // 切换标签选中状态
  const toggleTag = (tagName: string) => {
    if (selectedTags.includes(tagName)) {
      onTagsChange(selectedTags.filter(t => t !== tagName))
    } else {
      onTagsChange([...selectedTags, tagName])
    }
  }

  // 快速添加新标签（暂存状态）
  const handleQuickAdd = () => {
    const tagName = newTagInput.trim()
    
    if (!tagName) {
      return
    }

    // 检查是否已存在
    const existingTag = allTags.find(t => t.name === tagName)
    if (existingTag) {
      // 已存在，直接选中
      if (!selectedTags.includes(tagName)) {
        onTagsChange([...selectedTags, tagName])
      }
      setNewTagInput('')
      return
    }

    // 检查是否已在选中列表中
    if (selectedTags.includes(tagName)) {
      setNewTagInput('')
      return
    }

    // 新标签，添加到选中列表（暂存状态）
    onTagsChange([...selectedTags, tagName])
    setNewTagInput('')
  }

  // 移除标签
  const removeTag = (tagName: string) => {
    onTagsChange(selectedTags.filter(t => t !== tagName))
  }

  // 获取标签对象
  const getTagObject = (tagName: string) => {
    return allTags.find(t => t.name === tagName)
  }

  return (
    <div className="space-y-4">
      {/* 已选中的标签 */}
      {selectedTags.length > 0 && (
        <div className="space-y-2">
          <Label className="text-sm font-medium">
            已选标签 ({selectedTags.length})
          </Label>
          <div className="flex flex-wrap gap-2 p-3 rounded-lg border bg-muted/30 min-h-[60px]">
            {selectedTags.map((tagName) => {
              const tagObj = getTagObject(tagName)
              const isNewTag = !tagObj  // 新标签（快速添加的）
              
              return (
                <Badge
                  key={tagName}
                  variant="secondary"
                  className={cn(
                    'gap-1 pr-1 text-sm h-7',
                    // 新标签 - 虚线边框
                    isNewTag && 'border-dashed border-2 border-primary/50 bg-primary/10 text-primary'
                  )}
                >
                  <TagIcon className="h-3 w-3" />
                  {tagName}
                  {isNewTag && (
                    <span className="text-xs opacity-70 ml-1">(新)</span>
                  )}
                  {tagObj?.description && (
                    <span className="text-xs opacity-70 ml-1">
                      - {tagObj.description}
                    </span>
                  )}
                  <button
                    onClick={() => removeTag(tagName)}
                    className="ml-1 hover:bg-destructive/20 rounded-full p-0.5 transition-colors"
                    title="移除标签"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              )
            })}
          </div>
        </div>
      )}

      <Separator />

      {/* 快速添加 */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">快速添加</Label>
        <div className="flex gap-2">
          <Input
            placeholder="输入标签名称，按回车添加"
            value={newTagInput}
            onChange={(e) => setNewTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleQuickAdd()
              }
            }}
          />
          <Button 
            onClick={handleQuickAdd} 
            size="icon" 
            variant="outline"
            disabled={!newTagInput.trim()}
            title="快速添加"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          💡 输入新标签名称快速添加（暂存），或从下方选择已有标签
        </p>
      </div>

      <Separator />

      {/* 已有标签列表 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">
            知识库标签 ({allTags.length})
          </Label>
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1.5"
            onClick={onCreateTag}
          >
            <Plus className="h-3 w-3" />
            详细设置
          </Button>
        </div>

        {/* 搜索框 */}
        {allTags.length > 0 && (
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索标签名称、描述、别名..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>
        )}

        {/* 标签列表 */}
        <ScrollArea className="h-[200px] rounded-md border">
          <div className="p-2 space-y-1">
            {isLoading ? (
              <div className="text-sm text-muted-foreground text-center py-8">
                加载中...
              </div>
            ) : allTags.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-8">
                <TagIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>暂无标签</p>
                <p className="text-xs mt-1">点击"详细设置"创建第一个标签</p>
              </div>
            ) : unselectedTags.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-8">
                {searchQuery ? '未找到匹配的标签' : '所有标签已选中'}
              </div>
            ) : (
              unselectedTags.map((tag) => (
                <button
                  key={tag.id}
                  onClick={() => toggleTag(tag.name)}
                  className={cn(
                    'w-full flex items-start gap-2 p-2 rounded-md text-left transition-colors',
                    'hover:bg-accent border border-transparent hover:border-border'
                  )}
                >
                  <TagIcon className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm">{tag.name}</div>
                    {tag.description && (
                      <div className="text-xs text-muted-foreground line-clamp-1">
                        {tag.description}
                      </div>
                    )}
                    {tag.aliases && tag.aliases.length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        别名: {tag.aliases.join(', ')}
                      </div>
                    )}
                  </div>
                  <Plus className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                </button>
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      {/* 提示信息 */}
      <div className="text-xs text-muted-foreground space-y-1 bg-muted/50 p-3 rounded-md">
        <p>💡 <strong>快速添加</strong>：输入新标签名称，确认创建文件夹时保存</p>
        <p>💡 <strong>选择已有</strong>：点击上方标签快速选择</p>
        <p>💡 <strong>详细设置</strong>：创建带描述和别名的标签，立即保存到知识库</p>
      </div>
    </div>
  )
}
