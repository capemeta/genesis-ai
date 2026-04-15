/**
 * 组织树形表格组件
 */
import { useState, useMemo, Fragment } from 'react'
import type { ReactElement } from 'react'
import { ChevronRight, ChevronDown, Edit, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { PermissionButton } from '@/components/permission-button'
import type { OrganizationListItem } from '@/lib/api/organization'

interface OrganizationTableProps {
  data: OrganizationListItem[]
  expandAll: boolean
  onEdit: (org: OrganizationListItem) => void
  onAddChild: (org: OrganizationListItem) => void
  onDelete: (org: OrganizationListItem) => void
}

interface TreeNode extends OrganizationListItem {
  children: TreeNode[]
}

export function OrganizationTable({
  data,
  expandAll,
  onEdit,
  onAddChild,
  onDelete,
}: OrganizationTableProps) {
  // 展开状态（记录展开的节点ID）
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  // 记录上一次的 expandAll 状态
  const [prevExpandAll, setPrevExpandAll] = useState(expandAll)

  // 当 expandAll 改变时，清空手动展开/折叠的状态
  if (prevExpandAll !== expandAll) {
    setPrevExpandAll(expandAll)
    setExpandedIds(new Set())
  }

  // 构建树形结构
  const treeData = useMemo(() => {
    const map = new Map<string, TreeNode>()
    const roots: TreeNode[] = []

    // 第一遍：创建所有节点
    data.forEach((item) => {
      map.set(item.id, { ...item, children: [] })
    })

    // 第二遍：建立父子关系
    data.forEach((item) => {
      const node = map.get(item.id)!
      if (item.parent_id && map.has(item.parent_id)) {
        const parent = map.get(item.parent_id)!
        parent.children.push(node)
      } else {
        roots.push(node)
      }
    })

    // 递归排序
    const sortChildren = (nodes: TreeNode[]) => {
      nodes.sort((a, b) => {
        if (a.order_num !== b.order_num) {
          return a.order_num - b.order_num
        }
        return a.name.localeCompare(b.name)
      })
      nodes.forEach((node) => {
        if (node.children.length > 0) {
          sortChildren(node.children)
        }
      })
    }

    sortChildren(roots)
    return roots
  }, [data])

  // 切换展开状态
  const toggleExpand = (id: string) => {
    const newExpandedIds = new Set(expandedIds)
    if (newExpandedIds.has(id)) {
      newExpandedIds.delete(id)
    } else {
      newExpandedIds.add(id)
    }
    setExpandedIds(newExpandedIds)
  }

  // 判断节点是否展开
  const isExpanded = (id: string) => {
    // 如果 expandAll 为 true，所有节点默认展开，除非手动折叠
    if (expandAll) {
      return !expandedIds.has(id)
    }
    // 如果 expandAll 为 false，所有节点默认折叠，除非手动展开
    return expandedIds.has(id)
  }

  // 递归渲染树节点
  const renderTreeNode = (node: TreeNode, level: number = 0): ReactElement => {
    const hasChildren = node.children.length > 0
    const expanded = isExpanded(node.id)

    return (
      <Fragment key={node.id}>
        <TableRow key={node.id}>
          {/* 部门名称（树形展示） */}
          <TableCell>
            <div
              className="flex items-center gap-2"
              style={{ paddingLeft: `${level * 20}px` }}
            >
              {/* 展开/折叠图标 */}
              {hasChildren ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0"
                  onClick={() => toggleExpand(node.id)}
                >
                  {expanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </Button>
              ) : (
                <div className="w-6" />
              )}
              <span className="font-medium">{node.name}</span>
            </div>
          </TableCell>

          {/* 排序 */}
          <TableCell>{node.order_num}</TableCell>

          {/* 状态 */}
          <TableCell>
            {node.status === '0' ? (
              <Badge variant="default">正常</Badge>
            ) : (
              <Badge variant="secondary">停用</Badge>
            )}
          </TableCell>

          {/* 负责人 */}
          <TableCell>{node.leader_name || '-'}</TableCell>

          {/* 联系电话 */}
          <TableCell>{node.phone || '-'}</TableCell>

          {/* 创建时间 */}
          <TableCell>{node.created_at}</TableCell>

          {/* 操作 */}
          <TableCell className="text-right">
            <div className="flex items-center justify-end gap-2">
              {/* 修改 */}
              <PermissionButton
                permission='settings:organizations:edit'
                size="sm"
                variant="ghost"
                onClick={() => onEdit(node)}
              >
                <Edit className="h-4 w-4" />
              </PermissionButton>

              {/* 新增子部门 */}
              <PermissionButton
                permission='settings:organizations:create'
                size="sm"
                variant="ghost"
                onClick={() => onAddChild(node)}
              >
                <Plus className="h-4 w-4" />
              </PermissionButton>

              {/* 删除 */}
              <PermissionButton
                permission='settings:organizations:delete'
                size="sm"
                variant="ghost"
                onClick={() => onDelete(node)}
              >
                <Trash2 className="h-4 w-4" />
              </PermissionButton>
            </div>
          </TableCell>
        </TableRow>

        {/* 递归渲染子节点 */}
        {hasChildren && expanded && node.children.map((child) => renderTreeNode(child, level + 1))}
      </Fragment>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>部门名称</TableHead>
          <TableHead>排序</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>负责人</TableHead>
          <TableHead>联系电话</TableHead>
          <TableHead>创建时间</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {treeData.length === 0 ? (
          <TableRow>
            <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
              暂无数据
            </TableCell>
          </TableRow>
        ) : (
          treeData.map((node) => renderTreeNode(node))
        )}
      </TableBody>
    </Table>
  )
}
