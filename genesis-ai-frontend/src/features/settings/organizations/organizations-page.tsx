/**
 * 组织机构管理页面
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, ArrowDownUp, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { PermissionButton } from '@/components/permission-button'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  fetchOrganizations,
  deleteOrganization,
  type OrganizationListItem,
} from '@/lib/api/organization'
import { OrganizationSearchBar } from './components/organization-search-bar'
import { OrganizationTable } from './components/organization-table'
import { OrganizationFormDialog } from './components/organization-form-dialog'

export function OrganizationsPage() {
  const queryClient = useQueryClient()

  // 搜索参数
  const [searchParams, setSearchParams] = useState<{
    name?: string
    status?: string
  }>({})

  // 展开/折叠状态
  const [expandAll, setExpandAll] = useState(false)

  // 对话框状态
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [addChildDialogOpen, setAddChildDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedOrg, setSelectedOrg] = useState<OrganizationListItem | null>(null)
  const [parentOrg, setParentOrg] = useState<OrganizationListItem | null>(null)

  // 查询组织列表
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['organizations', searchParams],
    queryFn: () => fetchOrganizations(searchParams),
  })

  // 删除组织
  const { mutate: handleDelete, isPending: isDeleting } = useMutation({
    mutationFn: deleteOrganization,
    onSuccess: () => {
      toast.success('删除成功')
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
      queryClient.invalidateQueries({ queryKey: ['organization-tree'] })
      setDeleteDialogOpen(false)
      setSelectedOrg(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '删除失败')
    },
  })

  // 搜索处理
  const handleSearch = (params: { name?: string; status?: string }) => {
    setSearchParams(params)
    // 强制刷新查询
    setTimeout(() => refetch(), 0)
  }

  // 编辑处理
  const handleEdit = (org: OrganizationListItem) => {
    setSelectedOrg(org)
    setEditDialogOpen(true)
  }

  // 新增子部门处理
  const handleAddChild = (org: OrganizationListItem) => {
    setParentOrg(org)
    setAddChildDialogOpen(true)
  }

  // 删除处理
  const handleDeleteClick = (org: OrganizationListItem) => {
    setSelectedOrg(org)
    setDeleteDialogOpen(true)
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            {/* <Building2 className="h-8 w-8" /> */}
            组织机构管理
          </h1>
          <p className="text-muted-foreground mt-2">
            管理组织架构、部门层级和人员归属
          </p>
        </div>

        {/* 新增部门按钮 */}
        <PermissionButton
          permission='settings:organizations:create'
          size="lg"
          onClick={() => setCreateDialogOpen(true)}
        >
          <Plus className="mr-2 h-4 w-4" />
          创建部门
        </PermissionButton>
      </div>

      {/* 组织列表 */}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>组织列表</CardTitle>
              <CardDescription>
                共 {data?.total || 0} 个部门
              </CardDescription>
            </div>

            {/* 工具栏 */}
            <div className="flex items-center gap-3">
              {/* 搜索栏 */}
              <OrganizationSearchBar onSearch={handleSearch} />

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
            <div className="text-center py-8 text-destructive">
              加载失败，请重试
            </div>
          ) : !data?.data || data.data.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              暂无数据
            </div>
          ) : (
            <OrganizationTable
              data={data.data}
              expandAll={expandAll}
              onEdit={handleEdit}
              onAddChild={handleAddChild}
              onDelete={handleDeleteClick}
            />
          )}
        </CardContent>
      </Card>

      {/* 对话框 */}
      <OrganizationFormDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        mode="create"
      />

      <OrganizationFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        mode="edit"
        organization={selectedOrg}
      />

      <OrganizationFormDialog
        open={addChildDialogOpen}
        onOpenChange={setAddChildDialogOpen}
        mode="add-child"
        parentOrganization={parentOrg}
      />

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="删除部门"
        description={`确定要删除部门 "${selectedOrg?.name}" 吗？如果该部门下存在子部门或关联用户，将无法删除。`}
        onConfirm={() => selectedOrg && handleDelete(selectedOrg.id)}
        loading={isDeleting}
      />
    </div>
  )
}
