/**
 * 角色分配对话框
 * 
 * 为用户分配角色
 */
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Loader2, Shield } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { getUserRoles, assignRoles, type User } from '@/lib/api/user'
import { fetchRoles } from '@/lib/api/role'

interface RoleAssignDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: User | null
}

export function RoleAssignDialog({
  open,
  onOpenChange,
  user,
}: RoleAssignDialogProps) {
  const queryClient = useQueryClient()
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([])

  // 查询所有角色
  const { data: rolesData, isLoading: isLoadingRoles } = useQuery({
    queryKey: ['roles'],
    queryFn: () => fetchRoles({ page: 1, page_size: 100 }),
    enabled: open,
  })

  // 查询用户当前角色
  const { data: userRoles, isLoading: isLoadingUserRoles } = useQuery({
    queryKey: ['user-roles', user?.id],
    queryFn: () => getUserRoles(user!.id),
    enabled: open && !!user,
  })

  // 初始化选中的角色
  useEffect(() => {
    if (userRoles) {
      setSelectedRoleIds(userRoles.map((role) => role.id))
    }
  }, [userRoles])

  // 分配角色
  const { mutate: handleAssign, isPending } = useMutation({
    mutationFn: assignRoles,
    onSuccess: () => {
      toast.success('角色分配成功')
      queryClient.invalidateQueries({ queryKey: ['users'] })
      queryClient.invalidateQueries({ queryKey: ['user-roles', user?.id] })
      onOpenChange(false)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '分配失败')
    },
  })

  const handleSubmit = () => {
    if (!user) return
    handleAssign({
      id: user.id,
      role_ids: selectedRoleIds,
    })
  }

  const handleToggleRole = (roleId: string) => {
    setSelectedRoleIds((prev) =>
      prev.includes(roleId)
        ? prev.filter((id) => id !== roleId)
        : [...prev, roleId]
    )
  }

  const isLoading = isLoadingRoles || isLoadingUserRoles

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            分配角色
          </DialogTitle>
          <DialogDescription>
            为用户 "{user?.nickname}" 分配角色
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <ScrollArea className="max-h-[400px] pr-4">
            <div className="space-y-4">
              {rolesData?.data && rolesData.data.length > 0 ? (
                rolesData.data.map((role) => (
                  <div
                    key={role.id}
                    className="flex items-start space-x-3 rounded-lg border p-4 hover:bg-accent"
                  >
                    <Checkbox
                      id={role.id}
                      checked={selectedRoleIds.includes(role.id)}
                      onCheckedChange={() => handleToggleRole(role.id)}
                    />
                    <div className="flex-1 space-y-1">
                      <Label
                        htmlFor={role.id}
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                      >
                        {role.name}
                      </Label>
                      {role.description && (
                        <p className="text-sm text-muted-foreground">
                          {role.description}
                        </p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        代码: {role.code}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  暂无可用角色
                </div>
              )}
            </div>
          </ScrollArea>
        )}

        <DialogFooter>
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
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
