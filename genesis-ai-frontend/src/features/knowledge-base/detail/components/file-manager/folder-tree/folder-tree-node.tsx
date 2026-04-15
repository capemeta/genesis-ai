/**
 * 文件夹树节点组件
 */
import {
  Folder,
  FolderPlus,
  MoreVertical,
  Pencil,
  Trash2,
  ChevronRight,
  Eye,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { FolderTreeNodeProps } from './folder-tree-types'

export function FolderTreeNode({
  folder,
  level,
  selectedFolderId,
  expandedFolders,
  canCreate,
  canEdit,
  canDelete,
  onToggleExpand,
  onSelectFolder,
  onCreateChild,
  onEdit,
  onView,
  onDelete,
}: FolderTreeNodeProps) {
  const isExpanded = expandedFolders.has(folder.id)
  const isSelected = selectedFolderId === folder.id
  const hasChildren = folder.children && folder.children.length > 0
  const isRootLevel = level === 0

  return (
    <div>
      <div
        className={cn(
          'group flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors',
          isSelected
            ? 'bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800'
            : 'hover:bg-accent/50',
          isRootLevel && 'font-medium'
        )}
        style={{ paddingLeft: `${level * 16 + 12}px` }}
        onClick={() => onSelectFolder(folder.id)}
      >
        {/* 展开/折叠按钮 */}
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleExpand(folder.id)
            }}
            className="p-0.5 hover:bg-background/80 rounded transition-colors flex-shrink-0"
          >
            <ChevronRight
              className={cn(
                'h-4 w-4 text-muted-foreground transition-transform',
                isExpanded && 'rotate-90'
              )}
            />
          </button>
        ) : (
          <div className="w-5 flex-shrink-0" />
        )}

        {/* 文件夹图标和名称 */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Folder
            className={cn(
              'flex-shrink-0 h-4 w-4 transition-colors',
              isSelected
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-muted-foreground'
            )}
          />
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className={cn(
                    'truncate text-sm transition-colors',
                    isSelected ? 'font-semibold text-blue-700 dark:text-blue-300' : ''
                  )}
                >
                  {folder.name}
                </span>
              </TooltipTrigger>
              <TooltipContent side="right" align="start" className="max-w-xs">
                <p className="break-words">{folder.name}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* 操作菜单 */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
              onClick={(e) => e.stopPropagation()}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onView(folder)}>
              <Eye className="h-4 w-4 mr-2" />
              查看详情
            </DropdownMenuItem>

            {canCreate && (
              <DropdownMenuItem onClick={() => onCreateChild(folder)}>
                <FolderPlus className="h-4 w-4 mr-2" />
                新建子文件夹
              </DropdownMenuItem>
            )}

            {canEdit && (
              <DropdownMenuItem onClick={() => onEdit(folder)}>
                <Pencil className="h-4 w-4 mr-2" />
                编辑
              </DropdownMenuItem>
            )}

            {canDelete && (
              <DropdownMenuItem onClick={() => onDelete(folder)} className="text-destructive focus:text-destructive">
                <Trash2 className="h-4 w-4 mr-2" />
                删除
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* 子文件夹 */}
      {isExpanded && hasChildren && (
        <div className="mt-0.5">
          {folder.children!.map((child) => (
            <FolderTreeNode
              key={child.id}
              folder={child}
              level={level + 1}
              selectedFolderId={selectedFolderId}
              expandedFolders={expandedFolders}
              canCreate={canCreate}
              canEdit={canEdit}
              canDelete={canDelete}
              onToggleExpand={onToggleExpand}
              onSelectFolder={onSelectFolder}
              onCreateChild={onCreateChild}
              onEdit={onEdit}
              onView={onView}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  )
}
