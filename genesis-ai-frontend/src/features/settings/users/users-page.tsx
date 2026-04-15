/**
 * 用户管理页面
 */
import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Plus, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import type { PaginationState } from '@tanstack/react-table'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PermissionButton } from '@/components/permission-button'
import { fetchUsers, deleteUser, type UserListItem } from '@/lib/api/user'
import { fetchOrganizationTree } from '@/lib/api/organization'
import { UserSearchBar } from './components/user-search-bar'
import { UserTable } from './components/user-table'
import { UserFormDialog } from './components/user-form-dialog'
import { UserDetailSheet } from './components/user-detail-sheet'
import { UserRoleAssignDialog } from './components/user-role-assign-dialog'
import { UserPasswordResetDialog } from './components/user-password-reset-dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'

export function UsersPage() {
  // 搜索参数
  const [searchParams, setSearchParams] = useState<{
    search?: string
    status?: string
    organization_id?: string
  }>({})

  // 分页状态
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })

  // 对话框状态
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [assignRolesDialogOpen, setAssignRolesDialogOpen] = useState(false)
  const [resetPasswordDialogOpen, setResetPasswordDialogOpen] = useState(false)

  // 选中的用户
  const [selectedUser, setSelectedUser] = useState<UserListItem | null>(null)

  // 查询用户列表
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['users', searchParams, pagination],
    queryFn: () =>
      fetchUsers({
        page: pagination.pageIndex + 1,
        page_size: pagination.pageSize,
        ...searchParams,
      }),
  })

  const { data: organizationTree = [] } = useQuery({
    queryKey: ['organization-tree', 'users-filter'],
    queryFn: () => fetchOrganizationTree({ status: '0' }),
  })

  // 删除用户
  const { mutate: handleDeleteMutation, isPending: isDeleting } = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      toast.success('删除成功')
      setDeleteDialogOpen(false)
      setSelectedUser(null)
      refetch()
    },
    onError: () => {
      toast.error('删除失败')
    },
  })

  // 处理搜索
  const handleSearch = (params: any) => {
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
    setSelectedUser(null)
    setCreateDialogOpen(true)
  }

  // 处理编辑
  const handleEdit = (user: UserListItem) => {
    setSelectedUser(user)
    setEditDialogOpen(true)
  }

  // 处理查看详情
  const handleView = (user: UserListItem) => {
    setSelectedUser(user)
    setDetailDialogOpen(true)
  }

  // 处理删除
  const handleDelete = (user: UserListItem) => {
    setSelectedUser(user)
    setDeleteDialogOpen(true)
  }

  // 处理分配角色
  const handleAssignRoles = (user: UserListItem) => {
    setSelectedUser(user)
    setAssignRolesDialogOpen(true)
  }

  // 处理重置密码
  const handleResetPassword = (user: UserListItem) => {
    setSelectedUser(user)
    setResetPasswordDialogOpen(true)
  }

  // 处理确认删除
  const handleConfirmDelete = () => {
    if (selectedUser) {
      handleDeleteMutation(selectedUser.id)
    }
  }

  // 处理成功
  const handleSuccess = () => {
    refetch()
  }

  return (
    <div className='space-y-6'>
      {/* 页面标题 */}
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-3xl font-bold tracking-tight'>用户管理</h1>
          <p className='text-muted-foreground mt-2'>
            管理系统用户、基础资料和权限分配。用户名、邮箱、手机号按全局唯一规则校验。
          </p>
        </div>

        {/* 新建用户按钮 */}
        <PermissionButton
          permission='settings:users:create'
          size='lg'
          onClick={handleCreate}
        >
          <Plus className='mr-2 h-4 w-4' />
          创建用户
        </PermissionButton>
      </div>

      {/* 用户列表 */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>用户列表</CardTitle>
            <CardDescription>共 {data?.total || 0} 个用户</CardDescription>
          </div>
        </CardHeader>
        <CardContent className='space-y-4'>
          {/* 搜索栏 */}
          <UserSearchBar onSearch={handleSearch} organizationTree={organizationTree} />

          {isLoading ? (
            <div className='flex items-center justify-center py-8'>
              <Loader2 className='h-8 w-8 animate-spin text-muted-foreground' />
            </div>
          ) : error ? (
            <div className='text-center py-8 text-destructive'>加载失败，请重试</div>
          ) : !data?.data || data.data.length === 0 ? (
            <div className='text-center py-8 text-muted-foreground'>暂无数据</div>
          ) : (
            <UserTable
              data={data.data}
              total={data.total}
              isLoading={isLoading}
              pagination={pagination}
              onPaginationChange={handlePaginationChange}
              onView={handleView}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onAssignRoles={handleAssignRoles}
              onResetPassword={handleResetPassword}
            />
          )}
        </CardContent>
      </Card>

      {/* 创建/编辑用户对话框 */}
      <UserFormDialog
        open={createDialogOpen || editDialogOpen}
        onOpenChange={(isOpen) => {
          if (!isOpen) {
            setCreateDialogOpen(false)
            setEditDialogOpen(false)
          }
        }}
        user={editDialogOpen ? selectedUser || undefined : undefined}
        onSuccess={handleSuccess}
      />

      {/* 用户详情抽屉 */}
      <UserDetailSheet
        open={detailDialogOpen}
        onOpenChange={setDetailDialogOpen}
        user={selectedUser || undefined}
      />

      {/* 分配角色对话框 */}
      <UserRoleAssignDialog
        open={assignRolesDialogOpen}
        onOpenChange={setAssignRolesDialogOpen}
        user={selectedUser || undefined}
        onSuccess={handleSuccess}
      />

      {/* 重置密码对话框 */}
      <UserPasswordResetDialog
        open={resetPasswordDialogOpen}
        onOpenChange={setResetPasswordDialogOpen}
        user={selectedUser || undefined}
        onSuccess={handleSuccess}
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title='删除用户'
        description={`确定要删除用户 "${selectedUser?.username}" 吗？此操作不可撤销。`}
        onConfirm={handleConfirmDelete}
        loading={isDeleting}
      />
    </div>
  )
}
