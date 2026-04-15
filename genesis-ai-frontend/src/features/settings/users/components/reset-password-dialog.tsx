/**
 * 重置密码对话框
 */
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
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
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { resetPassword, type User } from '@/lib/api/user'

// 表单验证 Schema
const passwordFormSchema = z
  .object({
    new_password: z.string().min(8, '密码至少 8 个字符'),
    confirm_password: z.string().min(8, '密码至少 8 个字符'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: '两次输入的密码不一致',
    path: ['confirm_password'],
  })

type PasswordFormData = z.infer<typeof passwordFormSchema>

interface ResetPasswordDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: User | null
}

export function ResetPasswordDialog({
  open,
  onOpenChange,
  user,
}: ResetPasswordDialogProps) {
  const queryClient = useQueryClient()

  const form = useForm<PasswordFormData>({
    resolver: zodResolver(passwordFormSchema),
    defaultValues: {
      new_password: '',
      confirm_password: '',
    },
  })

  // 重置密码
  const { mutate: handleReset, isPending } = useMutation({
    mutationFn: resetPassword,
    onSuccess: () => {
      toast.success('密码重置成功')
      queryClient.invalidateQueries({ queryKey: ['users'] })
      onOpenChange(false)
      form.reset()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '重置失败')
    },
  })

  const onSubmit = (data: PasswordFormData) => {
    if (!user) return
    handleReset({
      id: user.id,
      new_password: data.new_password,
    })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(open) => {
        onOpenChange(open)
        if (!open) {
          form.reset()
        }
      }}
    >
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            重置密码
          </DialogTitle>
          <DialogDescription>
            为用户 "{user?.nickname}" 重置密码
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* 新密码 */}
            <FormField
              control={form.control}
              name="new_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>新密码 *</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="请输入新密码"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>密码至少 8 个字符</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 确认密码 */}
            <FormField
              control={form.control}
              name="confirm_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>确认密码 *</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="请再次输入新密码"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                取消
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                重置密码
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
