/**
 * 权限分配对话框
 * 
 * 为角色分配权限
 */
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Loader2, Key } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  fetchRolePermissions,
  assignRolePermissions,
  type Permission,
  type Role,
} from '@/lib/api/role'
import { getPermissionTree, type PermissionTreeNode } from '@/lib/api/permission'
import { PermissionTree } from './permission-tree'

interface PermissionAssignDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role: Role | null
}

export function PermissionAssignDialog({
  open,
  onOpenChange,
  role,
}: PermissionAssignDialogProps) {
  const queryClient = useQueryClient()
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<'all' | 'menu' | 'function'>('all')

  // 查询所有权限树
  const { data: allPermissionsData, isLoading: isLoadingAllPermissions } = useQuery({
    queryKey: ['permission-tree', 'all'],
    queryFn: () => getPermissionTree(),
    enabled: open,
  })

  // 查询菜单权限树
  const { data: menuPermissionsData, isLoading: isLoadingMenuPermissions } = useQuery({
    queryKey: ['permission-tree', 'menu'],
    queryFn: () => getPermissionTree('menu'),
    enabled: open,
  })

  // 查询功能权限树
  const { data: functionPermissionsData, isLoading: isLoadingFunctionPermissions } = useQuery({
    queryKey: ['permission-tree', 'function'],
    queryFn: () => getPermissionTree('function'),
    enabled: open,
  })

  // 查询角色当前权限
  const { data: rolePermissionsData, isLoading: isLoadingRolePermissions } = useQuery({
    queryKey: ['role-permissions', role?.id],
    queryFn: () => fetchRolePermissions(role!.id),
    enabled: open && !!role,
  })

  // 初始化选中的权限
  useEffect(() => {
    if (rolePermissionsData) {
      setSelectedPermissionIds(rolePermissionsData.map((perm: Permission) => perm.id))
    }
  }, [rolePermissionsData])

  // 分配权限
  const { mutate: handleAssign, isPending } = useMutation({
    mutationFn: assignRolePermissions,
    onSuccess: () => {
      toast.success('权限分配成功')
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      queryClient.invalidateQueries({ queryKey: ['role-permissions', role?.id] })
      onOpenChange(false)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '分配失败')
    },
  })

  const handleSubmit = () => {
    if (!role) return
    handleAssign({
      role_id: role.id,
      permission_ids: selectedPermissionIds,
    })
  }

  const handleTogglePermission = (permissionId: string) => {
    setSelectedPermissionIds((prev) =>
      prev.includes(permissionId)
        ? prev.filter((id) => id !== permissionId)
        : [...prev, permissionId]
    )
  }

  const handleSelectAll = () => {
    // 获取当前标签页的所有权限 ID
    const getAllPermissionIds = (nodes: PermissionTreeNode[]): string[] => {
      let ids: string[] = []
      nodes.forEach((node) => {
        ids.push(node.id)
        if (node.children) {
          ids = ids.concat(getAllPermissionIds(node.children))
        }
      })
      return ids
    }

    let currentData: PermissionTreeNode[] | undefined
    if (activeTab === 'all') {
      currentData = allPermissionsData
    } else if (activeTab === 'menu') {
      currentData = menuPermissionsData
    } else {
      currentData = functionPermissionsData
    }

    if (currentData) {
      const allIds = getAllPermissionIds(currentData)
      setSelectedPermissionIds((prev) => {
        const newIds = [...prev]
        allIds.forEach((id) => {
          if (!newIds.includes(id)) {
            newIds.push(id)
          }
        })
        return newIds
      })
    }
  }

  const handleDeselectAll = () => {
    // 取消选中当前标签页的所有权限
    const getAllPermissionIds = (nodes: PermissionTreeNode[]): string[] => {
      let ids: string[] = []
      nodes.forEach((node) => {
        ids.push(node.id)
        if (node.children) {
          ids = ids.concat(getAllPermissionIds(node.children))
        }
      })
      return ids
    }

    let currentData: PermissionTreeNode[] | undefined
    if (activeTab === 'all') {
      currentData = allPermissionsData
    } else if (activeTab === 'menu') {
      currentData = menuPermissionsData
    } else {
      currentData = functionPermissionsData
    }

    if (currentData) {
      const allIds = getAllPermissionIds(currentData)
      setSelectedPermissionIds((prev) => prev.filter((id) => !allIds.includes(id)))
    }
  }

  const isLoading =
    isLoadingAllPermissions ||
    isLoadingMenuPermissions ||
    isLoadingFunctionPermissions ||
    isLoadingRolePermissions

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            分配权限
          </DialogTitle>
          <DialogDescription>
            为角色 "{role?.name}" 分配权限
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
            <div className="flex items-center justify-between">
              <TabsList>
                <TabsTrigger value="all">全部权限</TabsTrigger>
                <TabsTrigger value="menu">菜单权限</TabsTrigger>
                <TabsTrigger value="function">功能权限</TabsTrigger>
              </TabsList>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleSelectAll}
                >
                  全选
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleDeselectAll}
                >
                  取消全选
                </Button>
              </div>
            </div>

            <ScrollArea className="h-[400px] mt-4 pr-4">
              <TabsContent value="all" className="mt-0">
                {allPermissionsData && allPermissionsData.length > 0 ? (
                  <PermissionTree
                    nodes={allPermissionsData}
                    selectedIds={selectedPermissionIds}
                    onToggle={handleTogglePermission}
                  />
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    暂无权限数据
                  </div>
                )}
              </TabsContent>

              <TabsContent value="menu" className="mt-0">
                {menuPermissionsData && menuPermissionsData.length > 0 ? (
                  <PermissionTree
                    nodes={menuPermissionsData}
                    selectedIds={selectedPermissionIds}
                    onToggle={handleTogglePermission}
                  />
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    暂无菜单权限
                  </div>
                )}
              </TabsContent>

              <TabsContent value="function" className="mt-0">
                {functionPermissionsData && functionPermissionsData.length > 0 ? (
                  <PermissionTree
                    nodes={functionPermissionsData}
                    selectedIds={selectedPermissionIds}
                    onToggle={handleTogglePermission}
                  />
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    暂无功能权限
                  </div>
                )}
              </TabsContent>
            </ScrollArea>
          </Tabs>
        )}

        <DialogFooter>
          <div className="flex items-center justify-between w-full">
            <div className="text-sm text-muted-foreground">
              已选择 {selectedPermissionIds.length} 个权限
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                取消
              </Button>
              <Button onClick={handleSubmit} disabled={isPending || isLoading}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                保存
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
