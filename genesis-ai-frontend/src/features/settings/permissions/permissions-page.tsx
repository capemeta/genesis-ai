/**
 * 权限管理页面（系统管理）
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { PermissionButton } from '@/components/permission-button'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus, Loader2, ArrowDownUp } from 'lucide-react'
import { toast } from 'sonner'
import { fetchPermissions, getPermission, deletePermission, type Permission, type PermissionListItem } from '@/lib/api/permission'
import { PermissionFormDialog } from './components/permission-form-dialog'
import { PermissionSearchBar } from './components/permission-search-bar'
import { PermissionTable } from './components/permission-table'
import { ConfirmDialog } from '@/components/confirm-dialog'

export function PermissionsPage() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useState<{
    search?: string
    type?: string
    status?: string
  }>({})

  // 展开/折叠状态
  const [expandAll, setExpandAll] = useState(false)

  // 对话框状态
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [addChildDialogOpen, setAddChildDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedPermission, setSelectedPermission] = useState<PermissionListItem | null>(null)
  const [editingPermission, setEditingPermission] = useState<Permission | null>(null)
  const [parentPermission, setParentPermission] = useState<Permission | null>(null)

  // 查询权限列表
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['permissions', searchParams],
    queryFn: () => {
      return fetchPermissions({
        search: searchParams.search || undefined,
        type: searchParams.type || undefined,
        status: searchParams.status !== undefined ? parseInt(searchParams.status) : undefined,
      })
    },
  })

  // 获取权限详情（用于编辑）
  const fetchPermissionDetail = async (id: string) => {
    try {
      return await getPermission(id)
    } catch (error) {
      throw error
    }
  }

  // 删除权限
  const { mutate: handleDelete, isPending: isDeleting } = useMutation({
    mutationFn: deletePermission,
    onSuccess: () => {
      toast.success('权限删除成功')
      queryClient.invalidateQueries({ queryKey: ['permissions'] })
      setDeleteDialogOpen(false)
      setSelectedPermission(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '删除失败')
    },
  })

  // 搜索处理
  const handleSearch = (params: {
    search?: string
    type?: string
    status?: string
  }) => {
    setSearchParams(params)
    // 强制刷新查询
    setTimeout(() => refetch(), 0)
  }

  // 编辑处理
  const handleEdit = async (permission: PermissionListItem) => {
    setSelectedPermission(permission)
    try {
      const fullPermission = await fetchPermissionDetail(permission.id)
      setEditingPermission(fullPermission)
      setEditDialogOpen(true)
    } catch (error) {
      toast.error('获取权限详情失败')
    }
  }

  // 新增子权限处理
  const handleAddChild = async (permission: PermissionListItem) => {
    setSelectedPermission(permission)
    try {
      // 直接使用 getPermission 获取权限详情
      const fullPermission = await getPermission(permission.id)
      setParentPermission(fullPermission)
      setAddChildDialogOpen(true)
    } catch (error) {
      toast.error('获取权限详情失败')
    }
  }
  
  // 计算要删除的权限数量（包括子权限）
  const getDeleteCount = (permission: PermissionListItem | null): number => {
    if (!permission || !data?.data) return 0
    
    let count = 1 // 自己
    
    // 递归计算子权限数量
    const countChildren = (parentId: string) => {
      data.data.forEach((item) => {
        if (item.parent_id === parentId) {
          count++
          countChildren(item.id)
        }
      })
    }
    
    countChildren(permission.id)
    return count
  }
  
  const deleteCount = getDeleteCount(selectedPermission)
  
  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            {/* <Lock className="h-8 w-8" /> */}
            权限管理
          </h1>
          <p className="text-muted-foreground mt-2">管理系统权限（菜单权限和功能权限）</p>
        </div>

        {/* 创建权限按钮 */}
        <PermissionButton
          permission='settings:permissions:create'
          size="lg"
          onClick={() => setCreateDialogOpen(true)}
        >
          <Plus className="mr-2 h-4 w-4" />
          创建权限
        </PermissionButton>
      </div>

      {/* 权限列表 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>权限列表</CardTitle>
              <CardDescription>共 {data?.total || 0} 个权限</CardDescription>
            </div>

            {/* 工具栏 */}
            <div className="flex items-center gap-3">
              {/* 搜索栏 */}
              <PermissionSearchBar onSearch={handleSearch} />

              {/* 展开/折叠按钮 */}
              <Button
                variant="outline"
                size="default"
                onClick={() => setExpandAll(!expandAll)}
              >
                <ArrowDownUp className="mr-2 h-4 w-4" />
                展开/折叠
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-center py-8 text-destructive">加载失败，请重试</div>
          ) : (
            <>
              {/* 权限表格 */}
              <PermissionTable
                data={data?.data || []}
                expandAll={expandAll}
                onEdit={handleEdit}
                onAddChild={handleAddChild}
                onDelete={(permission) => {
                  setSelectedPermission(permission)
                  setDeleteDialogOpen(true)
                }}
              />
            </>
          )}
        </CardContent>
      </Card>

      {/* 对话框 */}
      <PermissionFormDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        mode="create"
      />

      <PermissionFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        mode="edit"
        permission={editingPermission}
      />

      <PermissionFormDialog
        open={addChildDialogOpen}
        onOpenChange={setAddChildDialogOpen}
        mode="add-child"
        parentPermission={parentPermission}
      />

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="删除权限"
        description={
          deleteCount > 1
            ? `确定要删除权限 "${selectedPermission?.name}" 吗？此操作将同时删除 ${deleteCount - 1} 个子权限，共计 ${deleteCount} 个权限。此操作无法撤销。`
            : `确定要删除权限 "${selectedPermission?.name}" 吗？此操作无法撤销。`
        }
        onConfirm={() => selectedPermission && handleDelete(selectedPermission.id)}
        loading={isDeleting}
      />
    </div>
  )
}
