/**
 * 查看文件夹详情对话框（只读）
 */
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { getTagColorClass } from './tag-color-utils'
import type { FolderTreeNode, Tag } from '@/lib/api/folder.types'
import type { TagDefinition } from './folder-tree-types'

interface FolderTreeViewDialogProps {
  open: boolean
  folder: FolderTreeNode | null
  tags: Tag[]
  tagDefinitions: TagDefinition[]
  canEdit: boolean
  onOpenChange: (open: boolean) => void
  onEdit: () => void
}

export function FolderTreeViewDialog({
  open,
  folder,
  tags,
  tagDefinitions,
  canEdit,
  onOpenChange,
  onEdit,
}: FolderTreeViewDialogProps) {
  // 优先从 tags 中获取详细信息，如果 tags 中信息不全则从 tagDefinitions 中获取
  const getTagInfo = (tag: Tag) => {
    const tagDef = tagDefinitions.find((t) => t.id === tag.id || t.name === tag.name)
    return {
      name: tag.name,
      color: tag.color || tagDef?.color,
      description: tag.description || tagDef?.description
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="text-xl">查看文件夹详情</DialogTitle>
          <DialogDescription>文件夹 "{folder?.name}" 的详细信息</DialogDescription>
        </DialogHeader>
        <div className="space-y-5 py-4">
          {/* 文件夹名称 */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">文件夹名称</Label>
            <div className="px-3 py-2 rounded-md border bg-muted/30">
              <p className="text-sm">{folder?.name}</p>
            </div>
          </div>

          {/* 文件夹摘要 */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">文件夹摘要</Label>
            <div className="px-3 py-2 rounded-md border bg-muted/30 min-h-[80px]">
              {folder?.summary ? (
                <p className="text-sm whitespace-pre-wrap">{folder.summary}</p>
              ) : (
                <p className="text-sm text-muted-foreground">暂无摘要</p>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              💡 摘要可以帮助 AI 更好地理解文件夹的内容，提升检索准确度
            </p>
          </div>

          {/* 标签 */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">标签</Label>
            {tags.length > 0 ? (
              <div className="flex flex-wrap gap-2 p-3 rounded-lg border bg-muted/30">
                {tags.map((tag) => {
                  const tagInfo = getTagInfo(tag)
                  return (
                    <Badge
                      key={tag.id || tag.name}
                      variant="secondary"
                      className={cn('text-sm', getTagColorClass(tagInfo.color))}
                    >
                      {tagInfo.name}
                      {tagInfo.description && (
                        <span className="text-xs opacity-70 ml-1">({tagInfo.description})</span>
                      )}
                    </Badge>
                  )
                })}
              </div>
            ) : (
              <div className="px-3 py-2 rounded-md border bg-muted/30">
                <p className="text-sm text-muted-foreground">暂无标签</p>
              </div>
            )}
          </div>

          {/* 元数据信息 */}
          <div className="space-y-3 pt-2 border-t">
            <Label className="text-sm font-medium">元数据</Label>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-muted-foreground mb-1">创建人</p>
                <p className="font-medium">{folder?.created_by_name || '未知'}</p>
              </div>
              <div>
                <p className="text-muted-foreground mb-1">创建时间</p>
                <p className="font-medium">
                  {folder?.created_at
                    ? new Date(folder.created_at).toLocaleString('zh-CN')
                    : '未知'}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground mb-1">最后修改人</p>
                <p className="font-medium">{folder?.updated_by_name || '未知'}</p>
              </div>
              <div>
                <p className="text-muted-foreground mb-1">最后修改时间</p>
                <p className="font-medium">
                  {folder?.updated_at
                    ? new Date(folder.updated_at).toLocaleString('zh-CN')
                    : '未知'}
                </p>
              </div>
            </div>
          </div>
        </div>
        <DialogFooter>
          {canEdit && (
            <Button onClick={onEdit}>编辑</Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
