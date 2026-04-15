/**
 * 角色管理页面
 */
import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Plus, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import type { PaginationState } from '@tanstack/react-table'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PermissionButton } from '@/components/permission-button'
import { fetchRoles, deleteRole, type RoleListItem } from '@/lib/api/role'
import { RoleSearchBar } from './components/role-search-bar'
import { RoleTable } from './components/role-table'
import { RoleFormDialog } from './components/role-form-dialog'
import { RolePermissionAssignDialog } from './components/role-permission-assign-dialog'
import { RoleUserAssignDialog } from './components/role-user-assign-dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'

export function RolesPage() {
  // 搜索参数
  const [searchParams, setSearchParams] = useState<{
    search?: string
  }>({})

  // 分页状态
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })

  // 对话框状态
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [assignPermissionsDialogOpen, setAssignPermissionsDialogOpen] = useState(false)
  const [assignUsersDialogOpen, setAssignUsersDialogOpen] = useState(false)

  // 选中的角色
  const [selectedRole, setSelectedRole] = useState<RoleListItem | null>(null)

  // 查询角色列表
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['roles', searchParams, pagination],
    queryFn: () =>
      fetchRoles({
        page: pagination.pageIndex + 1,
        page_size: pagination.pageSize,
        ...searchParams,
      }),
  })

  // 删除角色
  const { mutate: handleDeleteMutation, isPending: isDeleting } = useMutation({
    mutationFn: deleteRole,
    onSuccess: () => {
      toast.success('删除成功')
      setDeleteDialogOpen(false)
      setSelectedRole(null)
      refetch()
    },
    onError: () => {
      toast.error('删除失败')
    },
  })

  // 处理搜索
  const handleSearch = (params: { search?: string }) => {
    setSearchParams(params)
    // 搜索时重置到第一页
    setPagination({ ...pagination, pageIndex: 0 })
    // 强制刷新查询
    setTimeout(() => refetch(), 0)
  }

  // 处理分页变化
  const handlePaginationChange = (newPagination: PaginationState) => {
    setPagination(newPagination)
  }

  // 监听分页变化，自动刷新查询
  useEffect(() => {
    refetch()
  }, [pagination.pageIndex, pagination.pageSize, refetch])

  // 处理创建
  const handleCreate = () => {
    setSelectedRole(null)
    setCreateDialogOpen(true)
  }

  // 处理编辑
  const handleEdit = (role: RoleListItem) => {
    setSelectedRole(role)
    setEditDialogOpen(true)
  }

  // 处理删除
  const handleDeleteClick = (role: RoleListItem) => {
    setSelectedRole(role)
    setDeleteDialogOpen(true)
  }

  // 处理分配权限
  const handleAssignPermissions = (role: RoleListItem) => {
    setSelectedRole(role)
    setAssignPermissionsDialogOpen(true)
  }

  // 处理分配用户
  const handleAssignUsers = (role: RoleListItem) => {
    setSelectedRole(role)
    setAssignUsersDialogOpen(true)
  }

  return (
    <div className='space-y-6'>
      {/* 页面标题 */}
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-3xl font-bold tracking-tight'>角色管理</h1>
          <p className='text-muted-foreground mt-2'>管理系统角色和权限分配</p>
        </div>

        {/* 新建角色按钮 */}
        <PermissionButton
          permission='settings:roles:create'
          size='lg'
          onClick={handleCreate}
        >
          <Plus className='mr-2 h-4 w-4' />
          创建角色
        </PermissionButton>
      </div>

      {/* 角色列表 */}
      <Card>
        <CardHeader>
          <div className='flex items-center justify-between'>
            <div>
              <CardTitle>角色列表</CardTitle>
              <CardDescription>共 {data?.total || 0} 个角色</CardDescription>
            </div>

            {/* 搜索栏 */}
            <RoleSearchBar onSearch={handleSearch} />
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className='flex items-center justify-center py-8'>
              <Loader2 className='h-8 w-8 animate-spin text-muted-foreground' />
            </div>
          ) : error ? (
            <div className='text-center py-8 text-destructive'>加载失败，请重试</div>
          ) : !data?.data || data.data.length === 0 ? (
            <div className='text-center py-8 text-muted-foreground'>暂无数据</div>
          ) : (
            <RoleTable
              data={data.data}
              total={data.total}
              isLoading={isLoading}
              pagination={pagination}
              onPaginationChange={handlePaginationChange}
              onEdit={handleEdit}
              onDelete={handleDeleteClick}
              onAssignPermissions={handleAssignPermissions}
              onAssignUsers={handleAssignUsers}
            />
          )}
        </CardContent>
      </Card>

      {/* 创建对话框 */}
      <RoleFormDialog open={createDialogOpen} onOpenChange={setCreateDialogOpen} onSuccess={refetch} />

      {/* 编辑对话框 */}
      {selectedRole && (
        <RoleFormDialog
          open={editDialogOpen}
          onOpenChange={setEditDialogOpen}
          role={selectedRole}
          onSuccess={refetch}
        />
      )}

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title='删除角色'
        description={`确定要删除角色 "${selectedRole?.name}" 吗？此操作不可撤销。`}
        onConfirm={() => selectedRole && handleDeleteMutation(selectedRole.id)}
        loading={isDeleting}
      />

      {/* 权限分配对话框 */}
      {selectedRole && (
        <RolePermissionAssignDialog
          open={assignPermissionsDialogOpen}
          onOpenChange={setAssignPermissionsDialogOpen}
          role={selectedRole}
          onSuccess={refetch}
        />
      )}

      {/* 用户分配对话框 */}
      {selectedRole && (
        <RoleUserAssignDialog
          open={assignUsersDialogOpen}
          onOpenChange={setAssignUsersDialogOpen}
          role={selectedRole}
          onSuccess={refetch}
        />
      )}
    </div>
  )
}
