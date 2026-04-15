/**
 * 用户角色分配对话框组件（右侧滑出）
 */
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
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
import { Checkbox } from '@/components/ui/checkbox'
import { toast } from 'sonner'
import type { PaginationState } from '@tanstack/react-table'
import { fetchAssignableRoles, type RoleListResponse } from '@/lib/api/role'
import { getUserRoles, assignRoles, type UserListItem } from '@/lib/api/user'
import { Loader2, Search } from 'lucide-react'

interface UserRoleAssignDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user?: UserListItem
  onSuccess: () => void
}

export function UserRoleAssignDialog({ open, onOpenChange, user, onSuccess }: UserRoleAssignDialogProps) {
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const queryClient = useQueryClient()

  // 查询可分配的角色列表（分页）
  const { data: rolesData, isLoading } = useQuery({
    queryKey: ['assignable-roles-paginated', searchQuery, pagination],
    queryFn: async () => {
      const result = await fetchAssignableRoles({
        page: pagination.pageIndex + 1,
        page_size: pagination.pageSize,
        search: searchQuery || undefined,
      })
      return result as RoleListResponse
    },
    enabled: open && !!user,
  })

  // 查询用户当前角色
  const { data: userRoles } = useQuery({
    queryKey: ['user-roles', user?.id],
    queryFn: () => (user ? getUserRoles(user.id) : Promise.resolve([])),
    enabled: open && !!user,
  })

  // 对话框打开时初始化选中的角色，关闭时重置状态
  useEffect(() => {
    if (open && userRoles) {
      // 打开时：回显用户已有的角色
      setSelectedRoleIds(userRoles.map((role) => role.id))
    } else if (!open) {
      // 关闭时：重置所有状态
      setSelectedRoleIds([])
      setSearchQuery('')
      setPagination({ pageIndex: 0, pageSize: 10 })
    }
  }, [open, userRoles])

  // 分配角色
  const assignMutation = useMutation({
    mutationFn: assignRoles,
    onSuccess: async () => {
      toast.success('分配成功')
      // 更新缓存
      if (user) {
        await queryClient.invalidateQueries({ queryKey: ['user-roles', user.id] })
      }
      await queryClient.invalidateQueries({ queryKey: ['users'] })
      onOpenChange(false)
      onSuccess()
    },
    onError: (error: any) => {
      toast.error('分配失败', {
        description: error.response?.data?.message || '分配角色失败',
      })
    },
  })

  // 处理保存
  const handleSave = () => {
    if (!user) return
    assignMutation.mutate({
      id: user.id,
      role_ids: selectedRoleIds,
    })
  }

  // 处理全选
  const handleSelectAll = () => {
    const roles = rolesData?.data || []
    if (roles.length === 0) return

    const currentPageRoleIds = roles.map((r) => r.id)
    const allSelected = currentPageRoleIds.every((id) => selectedRoleIds.includes(id))

    if (allSelected) {
      // 取消当前页所有选择
      setSelectedRoleIds((prev) => prev.filter((id) => !currentPageRoleIds.includes(id)))
    } else {
      // 选中当前页所有
      setSelectedRoleIds((prev) => {
        const newIds = [...prev]
        currentPageRoleIds.forEach((id) => {
          if (!newIds.includes(id)) {
            newIds.push(id)
          }
        })
        return newIds
      })
    }
  }

  // 处理单个选择
  const handleSelectRole = (roleId: string) => {
    setSelectedRoleIds((prev) =>
      prev.includes(roleId) ? prev.filter((id) => id !== roleId) : [...prev, roleId]
    )
  }

  const roles = rolesData?.data || []
  const currentPageRoleIds = roles.map((r) => r.id)
  const allSelected = currentPageRoleIds.length > 0 && currentPageRoleIds.every((id) => selectedRoleIds.includes(id))

  if (!user) {
    return null
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[700px] sm:max-w-[700px] flex flex-col p-0 gap-0">
        <SheetHeader className="px-6 py-4 border-b space-y-0">
          <div className="flex items-center justify-between">
            <div>
              <SheetTitle>分配角色</SheetTitle>
              <div className="text-sm text-muted-foreground mt-1">
                为用户 "{user.nickname || user.username}" 分配角色
              </div>
            </div>
          </div>
        </SheetHeader>

        <div className="flex flex-col flex-1 overflow-hidden">
          {/* 搜索栏 */}
          <div className="px-6 py-4 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索角色名称或编码..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setPagination({ pageIndex: 0, pageSize: 10 })
                }}
                className="pl-10"
              />
            </div>
          </div>

          {/* 角色列表 */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : roles.length > 0 ? (
              <div className="space-y-4">
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">
                          <Checkbox
                            checked={allSelected}
                            onCheckedChange={handleSelectAll}
                          />
                        </TableHead>
                        <TableHead>角色名称</TableHead>
                        <TableHead>角色编码</TableHead>
                        <TableHead>创建时间</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {roles.map((role) => (
                        <TableRow key={role.id}>
                          <TableCell>
                            <Checkbox
                              checked={selectedRoleIds.includes(role.id)}
                              onCheckedChange={() => handleSelectRole(role.id)}
                            />
                          </TableCell>
                          <TableCell className="font-medium">{role.name}</TableCell>
                          <TableCell className="font-mono text-sm text-muted-foreground">
                            {role.code}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(role.created_at).toLocaleString('zh-CN', {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                
                {/* 分页组件 */}
                <div className="flex justify-between items-center">
                  <div className="text-sm text-muted-foreground">
                    共 {rolesData?.total || 0} 条记录
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setPagination((prev) => ({
                          ...prev,
                          pageIndex: Math.max(0, prev.pageIndex - 1),
                        }))
                      }}
                      disabled={pagination.pageIndex === 0}
                    >
                      上一页
                    </Button>
                    <div className="flex items-center gap-2">
                      <span className="text-sm">
                        第 {pagination.pageIndex + 1} 页
                      </span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const maxPage = Math.ceil((rolesData?.total || 0) / pagination.pageSize)
                        setPagination((prev) => ({
                          ...prev,
                          pageIndex: Math.min(maxPage - 1, prev.pageIndex + 1),
                        }))
                      }}
                      disabled={
                        (pagination.pageIndex + 1) * pagination.pageSize >= (rolesData?.total || 0)
                      }
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center py-12 text-muted-foreground">
                暂无可分配角色
              </div>
            )}
          </div>

          {/* 底部操作栏 */}
          <div className="flex justify-between items-center px-6 py-4 border-t bg-background">
            <div className="text-sm text-muted-foreground">
              已选择 {selectedRoleIds.length} 个角色
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                取消
              </Button>
              <Button
                onClick={handleSave}
                disabled={assignMutation.isPending}
              >
                {assignMutation.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                保存
              </Button>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
