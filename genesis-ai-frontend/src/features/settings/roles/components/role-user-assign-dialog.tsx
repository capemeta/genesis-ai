/**
 * 角色分配用户对话框组件（右侧滑出）
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
import { fetchRoleUsers, fetchAvailableUsers, assignRoleUsers, removeRoleUser, type RoleListItem } from '@/lib/api/role'
import { Loader2, Search, Trash2 } from 'lucide-react'

interface RoleUserAssignDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role: RoleListItem
  onSuccess: () => void
}

export function RoleUserAssignDialog({ open, onOpenChange, role, onSuccess }: RoleUserAssignDialogProps) {
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'assigned' | 'available'>('assigned')
  const [assignedPagination, setAssignedPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const [availablePagination, setAvailablePagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const queryClient = useQueryClient()

  // 查询已分配的用户
  const { data: assignedUsers, isLoading: isLoadingAssigned } = useQuery({
    queryKey: ['role-users', role.id, searchQuery, assignedPagination],
    queryFn: async () => {
      console.log('[RoleUserAssign] Fetching assigned users for role:', role.id)
      const result = await fetchRoleUsers(role.id, { search: searchQuery })
      console.log('[RoleUserAssign] Assigned users:', result)
      return result
    },
    enabled: open,
  })

  // 查询可分配的用户（打开弹窗时立即加载）
  const { data: availableUsers, isLoading: isLoadingAvailable } = useQuery({
    queryKey: ['available-users', role.id, searchQuery, availablePagination],
    queryFn: async () => {
      console.log('[RoleUserAssign] Fetching available users for role:', role.id)
      const result = await fetchAvailableUsers(role.id, { search: searchQuery })
      console.log('[RoleUserAssign] Available users:', result)
      return result
    },
    enabled: open,
  })

  // 分配用户
  const assignMutation = useMutation({
    mutationFn: assignRoleUsers,
  })

  // 移除用户
  const removeMutation = useMutation({
    mutationFn: ({ role_id, user_id }: { role_id: string; user_id: string }) =>
      removeRoleUser(role_id, user_id),
  })

  // 对话框关闭时清空状态
  useEffect(() => {
    if (!open) {
      setSelectedUserIds([])
      setSearchQuery('')
      setActiveTab('assigned')
      setAssignedPagination({ pageIndex: 0, pageSize: 10 })
      setAvailablePagination({ pageIndex: 0, pageSize: 10 })
    }
  }, [open])

  // 处理分配用户
  const handleAssignUsers = () => {
    if (selectedUserIds.length === 0) {
      toast.error('请选择至少一个用户')
      return
    }

    assignMutation.mutate(
      {
        role_id: role.id,
        user_ids: selectedUserIds,
      },
      {
        onSuccess: async () => {
          toast.success('分配成功')
          setSelectedUserIds([])
          setSearchQuery('')
          // 刷新两个列表的缓存
          await queryClient.invalidateQueries({ queryKey: ['role-users', role.id] })
          await queryClient.invalidateQueries({ queryKey: ['available-users', role.id] })
          setActiveTab('assigned')
          onSuccess()
        },
        onError: () => {
          toast.error('分配失败')
        },
      }
    )
  }

  // 处理移除用户
  const handleRemoveUser = (userId: string) => {
    removeMutation.mutate(
      { role_id: role.id, user_id: userId },
      {
        onSuccess: async () => {
          toast.success('移除成功')
          // 刷新两个列表的缓存
          await queryClient.invalidateQueries({ queryKey: ['role-users', role.id] })
          await queryClient.invalidateQueries({ queryKey: ['available-users', role.id] })
          onSuccess()
        },
        onError: () => {
          toast.error('移除失败')
        },
      }
    )
  }

  // 处理全选
  const handleSelectAll = () => {
    const users = activeTab === 'assigned' ? assignedUsers?.data : availableUsers?.data
    if (users) {
      if (selectedUserIds.length === users.length) {
        setSelectedUserIds([])
      } else {
        setSelectedUserIds(users.map((u) => u.id))
      }
    }
  }

  // 处理单个选择
  const handleSelectUser = (userId: string) => {
    setSelectedUserIds((prev) =>
      prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId]
    )
  }

  const isLoading = activeTab === 'assigned' ? isLoadingAssigned : isLoadingAvailable
  const users = activeTab === 'assigned' ? assignedUsers?.data : availableUsers?.data
  const allSelected = users && users.length > 0 && selectedUserIds.length === users.length

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[700px] sm:max-w-[700px] flex flex-col p-0 gap-0">
        <SheetHeader className="px-6 py-4 border-b space-y-0">
          <div className="flex items-center justify-between">
            <div>
              <SheetTitle>分配用户</SheetTitle>
              <div className="text-sm text-muted-foreground mt-1">
                为角色 "{role.name}" 分配用户
              </div>
            </div>
          </div>
        </SheetHeader>

        <div className="flex flex-col flex-1 overflow-hidden">
          {/* 标签页 */}
          <div className="flex border-b px-6 pt-4">
            <button
              onClick={() => {
                setActiveTab('assigned')
                setSelectedUserIds([])
                setSearchQuery('')
                setAssignedPagination({ pageIndex: 0, pageSize: 10 })
              }}
              className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
                activeTab === 'assigned'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              已分配用户 ({assignedUsers?.total || 0})
            </button>
            <button
              onClick={() => {
                setActiveTab('available')
                setSelectedUserIds([])
                setSearchQuery('')
                setAvailablePagination({ pageIndex: 0, pageSize: 10 })
              }}
              className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
                activeTab === 'available'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              可分配用户 ({availableUsers?.total || 0})
            </button>
          </div>

          {/* 搜索栏 */}
          <div className="px-6 py-4 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索用户..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          {/* 用户列表 */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : users && users.length > 0 ? (
              <div className="space-y-4">
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">
                          {activeTab === 'available' && (
                            <Checkbox
                              checked={allSelected}
                              onCheckedChange={handleSelectAll}
                            />
                          )}
                        </TableHead>
                        <TableHead>用户名</TableHead>
                        <TableHead>昵称</TableHead>
                        <TableHead>邮箱</TableHead>
                        <TableHead>状态</TableHead>
                        {activeTab === 'assigned' && <TableHead className="text-right">操作</TableHead>}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((user) => (
                        <TableRow key={user.id}>
                          <TableCell>
                            {activeTab === 'available' ? (
                              <Checkbox
                                checked={selectedUserIds.includes(user.id)}
                                onCheckedChange={() => handleSelectUser(user.id)}
                              />
                            ) : (
                              <div className="w-4" />
                            )}
                          </TableCell>
                          <TableCell className="font-mono text-sm">{user.username}</TableCell>
                          <TableCell>{user.nickname}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {user.email || '-'}
                          </TableCell>
                          <TableCell>
                            {user.status === 'active' ? (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                正常
                              </span>
                            ) : user.status === 'disabled' ? (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                禁用
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                锁定
                              </span>
                            )}
                          </TableCell>
                          {activeTab === 'assigned' && (
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleRemoveUser(user.id)}
                                disabled={removeMutation.isPending}
                                title="取消关联"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                
                {/* 分页组件 */}
                <div className="flex justify-between items-center">
                  <div className="text-sm text-muted-foreground">
                    共 {activeTab === 'assigned' ? assignedUsers?.total : availableUsers?.total} 条记录
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (activeTab === 'assigned') {
                          setAssignedPagination((prev) => ({
                            ...prev,
                            pageIndex: Math.max(0, prev.pageIndex - 1),
                          }))
                        } else {
                          setAvailablePagination((prev) => ({
                            ...prev,
                            pageIndex: Math.max(0, prev.pageIndex - 1),
                          }))
                        }
                      }}
                      disabled={
                        activeTab === 'assigned'
                          ? assignedPagination.pageIndex === 0
                          : availablePagination.pageIndex === 0
                      }
                    >
                      上一页
                    </Button>
                    <div className="flex items-center gap-2">
                      <span className="text-sm">
                        第 {activeTab === 'assigned' ? assignedPagination.pageIndex + 1 : availablePagination.pageIndex + 1} 页
                      </span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (activeTab === 'assigned') {
                          const maxPage = Math.ceil((assignedUsers?.total || 0) / 10)
                          setAssignedPagination((prev) => ({
                            ...prev,
                            pageIndex: Math.min(maxPage - 1, prev.pageIndex + 1),
                          }))
                        } else {
                          const maxPage = Math.ceil((availableUsers?.total || 0) / 10)
                          setAvailablePagination((prev) => ({
                            ...prev,
                            pageIndex: Math.min(maxPage - 1, prev.pageIndex + 1),
                          }))
                        }
                      }}
                      disabled={
                        activeTab === 'assigned'
                          ? (assignedPagination.pageIndex + 1) * 10 >= (assignedUsers?.total || 0)
                          : (availablePagination.pageIndex + 1) * 10 >= (availableUsers?.total || 0)
                      }
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center py-12 text-muted-foreground">
                {activeTab === 'assigned' ? '暂无已分配用户' : '暂无可分配用户'}
              </div>
            )}
          </div>

          {/* 底部操作栏 */}
          {activeTab === 'available' && (
            <div className="flex justify-between items-center px-6 py-4 border-t bg-background">
              <div className="text-sm text-muted-foreground">
                已选择 {selectedUserIds.length} 个用户
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  关闭
                </Button>
                <Button
                  onClick={handleAssignUsers}
                  disabled={assignMutation.isPending || selectedUserIds.length === 0}
                >
                  {assignMutation.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  分配用户
                </Button>
              </div>
            </div>
          )}

          {activeTab === 'assigned' && (
            <div className="flex justify-end px-6 py-4 border-t bg-background">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                关闭
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
