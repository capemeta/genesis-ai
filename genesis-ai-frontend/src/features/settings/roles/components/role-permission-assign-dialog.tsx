/**
 * 角色权限分配对话框组件（右侧滑出）
 */
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { toast } from 'sonner'
import { fetchRolePermissions, assignRolePermissions, type RoleListItem } from '@/lib/api/role'
import { fetchUserPermissionTree } from '@/lib/api/permission'
import { RolePermissionTree } from './role-permission-tree'
import { Loader2, MoreVertical } from 'lucide-react'

interface RolePermissionAssignDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role: RoleListItem
  onSuccess: () => void
}

export function RolePermissionAssignDialog({ open, onOpenChange, role, onSuccess }: RolePermissionAssignDialogProps) {
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>([])
  const [expandAll, setExpandAll] = useState(false)
  const [cascadeSelect, setCascadeSelect] = useState(true) // 默认层级关联
  const queryClient = useQueryClient()

  // 查询角色当前权限
  const { data: rolePermissions, isLoading: isLoadingRolePermissions } = useQuery({
    queryKey: ['role-permissions', role.id],
    queryFn: async () => {
      console.log('[RolePermissionAssign] Fetching role permissions for role:', role.id)
      const permissions = await fetchRolePermissions(role.id)
      console.log('[RolePermissionAssign] Role permissions:', permissions)
      return permissions
    },
    enabled: open,
  })

  // 查询当前用户的权限树（只显示用户拥有的权限）
  const { data: userPermissionTree, isLoading: isLoadingTree, error: treeError } = useQuery({
    queryKey: ['user-permission-tree'],
    queryFn: async () => {
      console.log('[RolePermissionAssign] Fetching user permission tree...')
      const tree = await fetchUserPermissionTree()
      console.log('[RolePermissionAssign] Permission tree:', tree)
      return tree
    },
    enabled: open,
  })

  // 显示错误信息
  useEffect(() => {
    if (treeError) {
      console.error('[RolePermissionAssign] Query error:', treeError)
      toast.error('获取权限树失败', {
        description: treeError instanceof Error ? treeError.message : '未知错误',
      })
    }
  }, [treeError])

  // 初始化选中的权限
  useEffect(() => {
    if (rolePermissions && open) {
      const permissionIds = rolePermissions.map((perm) => perm.id)
      console.log('[RolePermissionAssign] Initializing selected permissions:', permissionIds)
      setSelectedPermissionIds(permissionIds)
    }
  }, [rolePermissions, open])

  // 对话框关闭时清空状态
  useEffect(() => {
    if (!open) {
      // 清空选中状态，下次打开时会重新从服务器加载
      setSelectedPermissionIds([])
      // 重置展开状态
      setExpandAll(false)
    }
  }, [open])

  // 分配权限
  const assignMutation = useMutation({
    mutationFn: assignRolePermissions,
  })

  const handleSubmit = (e: React.FormEvent, closeAfterSave: boolean = true) => {
    e.preventDefault()
    assignMutation.mutate(
      {
        role_id: role.id,
        permission_ids: selectedPermissionIds,
      },
      {
        onSuccess: async () => {
          toast.success('保存成功')
          // 刷新角色权限查询缓存
          await queryClient.invalidateQueries({ 
            queryKey: ['role-permissions', role.id] 
          })
          if (closeAfterSave) {
            onOpenChange(false)
          }
          onSuccess()
        },
        onError: () => {
          toast.error('保存失败')
        },
      }
    )
  }

  // 处理取消操作
  const handleCancel = () => {
    // 直接关闭，useEffect 会自动清空状态
    onOpenChange(false)
  }

  const isLoading = isLoadingRolePermissions || isLoadingTree

  // 获取所有权限ID（递归）
  const getAllPermissionIds = (tree: any[]): string[] => {
    const ids: string[] = []
    const traverse = (nodes: any[]) => {
      nodes.forEach((node) => {
        ids.push(node.id)
        if (node.children && node.children.length > 0) {
          traverse(node.children)
        }
      })
    }
    traverse(tree)
    return ids
  }

  // 选择全部
  const handleSelectAll = () => {
    if (userPermissionTree) {
      const allIds = getAllPermissionIds(userPermissionTree)
      setSelectedPermissionIds(allIds)
    }
  }

  // 取消选择
  const handleDeselectAll = () => {
    setSelectedPermissionIds([])
  }

  // 展开全部
  const handleExpandAll = () => {
    setExpandAll(true)
  }

  // 折叠全部
  const handleCollapseAll = () => {
    setExpandAll(false)
  }

  // 切换层级关联
  const handleToggleCascade = () => {
    setCascadeSelect(!cascadeSelect)
    toast.success(cascadeSelect ? '已切换为层级独立' : '已切换为层级关联')
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[600px] sm:max-w-[600px] flex flex-col p-0 gap-0">
        <SheetHeader className="px-6 py-4 border-b space-y-0">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <SheetTitle>角色权限配置</SheetTitle>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-7 w-7">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-40">
                    <DropdownMenuItem onClick={handleSelectAll}>
                      选择全部
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={handleDeselectAll}>
                      取消选择
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={handleExpandAll}>
                      展开全部
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={handleCollapseAll}>
                      折叠全部
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={handleToggleCascade}>
                      {cascadeSelect ? '层级独立' : '层级关联'}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                所拥有的权限
              </div>
            </div>
          </div>
        </SheetHeader>
        
        {isLoading ? (
          <div className='flex items-center justify-center py-12'>
            <Loader2 className='w-8 h-8 animate-spin text-muted-foreground' />
          </div>
        ) : (
          <form onSubmit={handleSubmit} className='flex flex-col flex-1 overflow-hidden'>
            <div className='flex-1 overflow-y-auto px-6 py-4'>
              {userPermissionTree && userPermissionTree.length > 0 ? (
                <RolePermissionTree
                  treeData={userPermissionTree}
                  selectedIds={selectedPermissionIds}
                  onSelectionChange={setSelectedPermissionIds}
                  expandAll={expandAll}
                  cascadeSelect={cascadeSelect}
                />
              ) : (
                <div className='flex items-center justify-center py-12 text-muted-foreground'>
                  暂无可分配的权限
                </div>
              )}
            </div>
            
            <div className='flex justify-between items-center px-6 py-4 border-t bg-background'>
              <div className='text-sm text-muted-foreground'>
                已选择 {selectedPermissionIds.length} 个权限
              </div>
              <div className='flex gap-2'>
                <Button type='button' variant='outline' onClick={handleCancel}>
                  取消
                </Button>
                <Button 
                  type='button' 
                  variant='outline'
                  onClick={(e) => handleSubmit(e, false)}
                  disabled={assignMutation.isPending}
                >
                  {assignMutation.isPending && <Loader2 className='w-4 h-4 mr-2 animate-spin' />}
                  仅保存
                </Button>
                <Button 
                  type='submit' 
                  onClick={(e) => handleSubmit(e, true)}
                  disabled={assignMutation.isPending}
                >
                  {assignMutation.isPending && <Loader2 className='w-4 h-4 mr-2 animate-spin' />}
                  保存并关闭
                </Button>
              </div>
            </div>
          </form>
        )}
      </SheetContent>
    </Sheet>
  )
}
