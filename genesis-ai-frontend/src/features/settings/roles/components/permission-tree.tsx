/**
 * 权限树组件
 * 
 * 递归渲染权限树，支持复选框选择
 */
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import type { PermissionTreeNode } from '@/lib/api/permission'

interface PermissionTreeProps {
  nodes: PermissionTreeNode[]
  selectedIds: string[]
  onToggle: (id: string) => void
  level?: number
}

export function PermissionTree({
  nodes,
  selectedIds,
  onToggle,
  level = 0,
}: PermissionTreeProps) {
  return (
    <div className={level > 0 ? 'ml-6 mt-2' : ''}>
      {nodes.map((node) => (
        <PermissionTreeNode
          key={node.id}
          node={node}
          selectedIds={selectedIds}
          onToggle={onToggle}
          level={level}
        />
      ))}
    </div>
  )
}

interface PermissionTreeNodeProps {
  node: PermissionTreeNode
  selectedIds: string[]
  onToggle: (id: string) => void
  level: number
}

function PermissionTreeNode({
  node,
  selectedIds,
  onToggle,
  level,
}: PermissionTreeNodeProps) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children && node.children.length > 0
  const isChecked = selectedIds.includes(node.id)

  return (
    <div className="space-y-2">
      <div className="flex items-center space-x-2 py-2 hover:bg-accent rounded-md px-2">
        {/* 展开/折叠按钮 */}
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="p-0.5 hover:bg-accent-foreground/10 rounded"
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        ) : (
          <div className="w-5" />
        )}

        {/* 复选框 */}
        <Checkbox
          id={node.id}
          checked={isChecked}
          onCheckedChange={() => onToggle(node.id)}
        />

        {/* 标签 */}
        <div className="flex-1 flex items-center gap-2">
          <Label
            htmlFor={node.id}
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
          >
            {node.name}
          </Label>
          <Badge variant={node.type === 'menu' ? 'default' : 'secondary'} className="text-xs">
            {node.type === 'menu' ? '菜单' : '功能'}
          </Badge>
          <span className="text-xs text-muted-foreground">{node.code}</span>
        </div>
      </div>

      {/* 子节点 */}
      {hasChildren && expanded && (
        <PermissionTree
          nodes={node.children!}
          selectedIds={selectedIds}
          onToggle={onToggle}
          level={level + 1}
        />
      )}
    </div>
  )
}
