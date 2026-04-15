import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Pencil, Trash2, Building2 } from 'lucide-react'
import { toast } from 'sonner'

import { fetchTenants, deleteTenant, type Tenant } from '@/lib/api/tenant'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { TenantFormDialog } from '@/features/tenants/components/tenant-form-dialog'

export const Route = createFileRoute('/_top-nav/settings/tenants/')({
  component: TenantsPage,
})

function TenantsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null)
  const [deletingTenant, setDeletingTenant] = useState<Tenant | null>(null)

  // 查询租户列表
  const { data, isLoading } = useQuery({
    queryKey: ['tenants', page, search],
    queryFn: () => fetchTenants({ page, page_size: 20, search: search || undefined }),
  })

  // 删除租户
  const { mutate: handleDelete, isPending: isDeleting } = useMutation({
    mutationFn: deleteTenant,
    onSuccess: () => {
      toast.success('租户删除成功')
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      setDeletingTenant(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '删除失败')
    },
  })

  const handleSearch = () => {
    setSearch(searchInput)
    setPage(1)
  }

  const handleEdit = (tenant: Tenant) => {
    setEditingTenant(tenant)
  }

  const totalPages = data ? Math.ceil(data.total / 20) : 0

  return (
    <div className="container p-6 space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">租户管理</h1>
          <p className="text-muted-foreground mt-2">
            管理系统中的所有租户，配置租户配额和权限
          </p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          创建租户
        </Button>
      </div>

      {/* 搜索和筛选 */}
      <Card>
        <CardHeader>
          <CardTitle>租户列表</CardTitle>
          <CardDescription>共 {data?.total || 0} 个租户</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-6">
            <div className="flex-1 flex items-center gap-2">
              <Search className="h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索租户名称..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="max-w-sm"
              />
              <Button onClick={handleSearch} variant="secondary">
                搜索
              </Button>
            </div>
          </div>

          {/* 表格 */}
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">加载中...</div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>租户名称</TableHead>
                    <TableHead>描述</TableHead>
                    <TableHead>配额</TableHead>
                    <TableHead>创建人</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.data.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-32 text-center">
                        <div className="flex flex-col items-center justify-center">
                          <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
                          <p className="text-muted-foreground">暂无租户数据</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    data?.data.map((tenant) => (
                      <TableRow key={tenant.id}>
                        <TableCell className="font-medium">{tenant.name}</TableCell>
                        <TableCell className="max-w-xs truncate">
                          {tenant.description || '-'}
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            {tenant.limits.max_users && (
                              <div>用户: {tenant.limits.max_users}</div>
                            )}
                            {tenant.limits.max_storage_gb && (
                              <div>存储: {tenant.limits.max_storage_gb}GB</div>
                            )}
                            {!tenant.limits.max_users && !tenant.limits.max_storage_gb && '-'}
                          </div>
                        </TableCell>
                        <TableCell>{tenant.created_by_name || '-'}</TableCell>
                        <TableCell>
                          {new Date(tenant.created_at).toLocaleString('zh-CN')}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleEdit(tenant)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeletingTenant(tenant)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>

              {/* 分页 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-muted-foreground">
                    第 {page} 页，共 {totalPages} 页
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      上一页
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* 创建/编辑对话框 */}
      <TenantFormDialog
        open={isCreateOpen || !!editingTenant}
        onOpenChange={(open) => {
          if (!open) {
            setIsCreateOpen(false)
            setEditingTenant(null)
          }
        }}
        tenant={editingTenant}
        onSuccess={() => {
          setIsCreateOpen(false)
          setEditingTenant(null)
          queryClient.invalidateQueries({ queryKey: ['tenants'] })
        }}
      />

      {/* 删除确认对话框 */}
      <AlertDialog open={!!deletingTenant} onOpenChange={() => setDeletingTenant(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除租户 "{deletingTenant?.name}" 吗？此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deletingTenant && handleDelete(deletingTenant.id)}
              disabled={isDeleting}
            >
              {isDeleting ? '删除中...' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
