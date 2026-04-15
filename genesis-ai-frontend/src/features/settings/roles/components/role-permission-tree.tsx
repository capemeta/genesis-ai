/**
 * 角色权限树形选择器
 * 专用于角色授权，支持多选和树形展示
 */
import { useState, useEffect } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface PermissionTreeNode {
  id: string
  code: string
  name: string
  type: 'menu' | 'function' | 'directory'
  module: string
  parent_id?: string | null
  children?: PermissionTreeNode[]
}

interface RolePermissionTreeProps {
  treeData: PermissionTreeNode[]
  selectedIds: string[]
  onSelectionChange: (selectedIds: string[]) => void
  expandAll?: boolean
  cascadeSelect?: boolean
}

export function RolePermissionTree({
  treeData,
  selectedIds,
  onSelectionChange,
  expandAll = false,
  cascadeSelect = true,
}: RolePermissionTreeProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  // 当expandAll改变时，更新展开状态
  useEffect(() => {
    if (expandAll) {
      // 展开所有节点
      const allIds = new Set<string>()
      const traverse = (nodes: PermissionTreeNode[]) => {
        nodes.forEach((node) => {
          if (node.children && node.children.length > 0) {
            allIds.add(node.id)
            traverse(node.children)
          }
        })
      }
      traverse(treeData)
      setExpandedIds(allIds)
    } else {
      // 折叠所有节点
      setExpandedIds(new Set())
    }
  }, [expandAll, treeData])

  // 切换展开/折叠
  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // 获取节点的所有子节点ID（递归）
  const getAllChildIds = (node: PermissionTreeNode): string[] => {
    const ids: string[] = []
    if (node.children) {
      node.children.forEach((child) => {
        ids.push(child.id)
        ids.push(...getAllChildIds(child))
      })
    }
    return ids
  }

  // 检查节点是否被选中
  const isNodeChecked = (nodeId: string): boolean => {
    return selectedIds.includes(nodeId)
  }

  // 检查节点是否半选中（部分子节点被选中）
  const isNodeIndeterminate = (node: PermissionTreeNode): boolean => {
    if (!node.children || node.children.length === 0) return false
    
    const childIds = getAllChildIds(node)
    const checkedCount = childIds.filter((id) => selectedIds.includes(id)).length
    
    return checkedCount > 0 && checkedCount < childIds.length
  }

  // 处理节点选中/取消选中
  const handleNodeCheck = (node: PermissionTreeNode, checked: boolean) => {
    if (cascadeSelect) {
      // 层级关联模式：选中/取消选中当前节点和所有子节点
      const childIds = getAllChildIds(node)
      const allIds = [node.id, ...childIds]

      if (checked) {
        // 选中：添加当前节点和所有子节点
        const newSelectedIds = [...new Set([...selectedIds, ...allIds])]
        onSelectionChange(newSelectedIds)
      } else {
        // 取消选中：移除当前节点和所有子节点
        const newSelectedIds = selectedIds.filter((id) => !allIds.includes(id))
        onSelectionChange(newSelectedIds)
      }
    } else {
      // 层级独立模式：只选中/取消选中当前节点
      if (checked) {
        onSelectionChange([...selectedIds, node.id])
      } else {
        onSelectionChange(selectedIds.filter((id) => id !== node.id))
      }
    }
  }

  // 渲染树节点
  const renderTreeNode = (node: PermissionTreeNode, level: number = 0) => {
    const hasChildren = node.children && node.children.length > 0
    const isExpanded = expandedIds.has(node.id)
    const isChecked = isNodeChecked(node.id)
    const isIndeterminate = isNodeIndeterminate(node)

    return (
      <div key={node.id}>
        <div
          className={cn(
            'flex items-center gap-2 py-2 px-3 hover:bg-accent rounded-md cursor-pointer',
            level > 0 && 'ml-6'
          )}
        >
          {/* 展开/折叠图标 */}
          {hasChildren ? (
            <button
              type="button"
              onClick={() => toggleExpand(node.id)}
              className="flex-shrink-0 w-4 h-4 flex items-center justify-center"
            >
              {isExpanded ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronRight className="w-4 h-4" />
              )}
            </button>
          ) : (
            <div className="w-4 h-4" />
          )}

          {/* 复选框 */}
          <Checkbox
            checked={isChecked}
            onCheckedChange={(checked) => handleNodeCheck(node, checked as boolean)}
            className={cn(isIndeterminate && 'data-[state=checked]:bg-primary/50')}
          />

          {/* 节点信息 */}
          <div className="flex-1 flex items-center gap-2">
            <span className="text-sm">{node.name}</span>
            {node.type === 'directory' && (
              <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">
                目录
              </span>
            )}
            {node.type === 'menu' && (
              <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                菜单
              </span>
            )}
            {node.type === 'function' && (
              <span className="text-xs px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded">
                功能
              </span>
            )}
          </div>
        </div>

        {/* 子节点 */}
        {hasChildren && isExpanded && (
          <div className="ml-4">
            {node.children!.map((child) => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {treeData.map((node) => renderTreeNode(node, 0))}
    </div>
  )
}
