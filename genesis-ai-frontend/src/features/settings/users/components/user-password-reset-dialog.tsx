/**
 * 用户密码重置对话框组件
 */
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Loader2, Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'
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
import { resetPassword, type UserListItem } from '@/lib/api/user'

// 密码验证规则
const passwordSchema = z.string()
  .min(8, '密码长度必须为8-20位')
  .max(20, '密码长度必须为8-20位')
  .regex(/[A-Z]/, '密码必须包含大写字母')
  .regex(/[a-z]/, '密码必须包含小写字母')
  .regex(/[0-9]/, '密码必须包含数字')
  .regex(/[&*^%$#@!]/, '密码必须包含特殊字符(&*^%$#@!中的一个)')

// 表单验证 Schema
const formSchema = z.object({
  new_password: passwordSchema,
  confirm_password: z.string().min(1, '请确认密码'),
}).refine((data) => data.new_password === data.confirm_password, {
  message: '两次输入的密码不一致',
  path: ['confirm_password'],
})

type FormValues = z.infer<typeof formSchema>

interface UserPasswordResetDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user?: UserListItem
  onSuccess: () => void
}

export function UserPasswordResetDialog({
  open,
  onOpenChange,
  user,
  onSuccess,
}: UserPasswordResetDialogProps) {
  const [showPassword, setShowPassword] = useState(false)

  // 表单
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      new_password: '',
      confirm_password: '',
    },
  })

  // 当对话框打开/关闭时，重置表单和密码显示状态
  useEffect(() => {
    if (open) {
      form.reset({
        new_password: '',
        confirm_password: '',
      })
      setShowPassword(false)
    }
  }, [open, form])

  // 重置密码 Mutation
  const { mutate: handleSubmit, isPending } = useMutation({
    mutationFn: async (values: FormValues) => {
      if (!user) {
        throw new Error('用户信息不存在')
      }
      return await resetPassword({
        id: user.id,
        new_password: values.new_password,
      })
    },
    onSuccess: (result) => {
      toast.success('重置成功', {
        description: `密码已更新，并已撤销 ${result.revoked_count} 个活跃会话`,
      })
      onOpenChange(false)
      onSuccess()
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.message || error.message || '重置密码失败'
      )
    },
  })

  const onSubmit = (values: FormValues) => {
    handleSubmit(values)
  }

  if (!user) {
    return null
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-md'>
        <DialogHeader>
          <DialogTitle>重置密码</DialogTitle>
          <DialogDescription>
            为用户 "{user.nickname || user.username}{user.nickname ? `（${user.username}）` : ''}" 重置密码
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-4'>
            {/* 新密码 */}
            <FormField
              control={form.control}
              name='new_password'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    新密码 <span className='text-destructive'>*</span>
                  </FormLabel>
                  <FormControl>
                    <div className='relative'>
                      <Input
                        type={showPassword ? 'text' : 'password'}
                        placeholder='请输入新密码'
                        {...field}
                        className='pr-10'
                      />
                      <button
                        type='button'
                        onClick={() => setShowPassword(!showPassword)}
                        className='absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors'
                        tabIndex={-1}
                      >
                        {showPassword ? (
                          <EyeOff className='h-4 w-4' />
                        ) : (
                          <Eye className='h-4 w-4' />
                        )}
                      </button>
                    </div>
                  </FormControl>
                  <FormDescription>
                    密码要求：8-20位，必须包含大小写字母、数字和特殊字符(&*^%$#@!中的一个)
                    。重置后将强制该用户重新登录。
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 确认密码 */}
            <FormField
              control={form.control}
              name='confirm_password'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    确认密码 <span className='text-destructive'>*</span>
                  </FormLabel>
                  <FormControl>
                    <div className='relative'>
                      <Input
                        type={showPassword ? 'text' : 'password'}
                        placeholder='请再次输入新密码'
                        {...field}
                        className='pr-10'
                      />
                      <button
                        type='button'
                        onClick={() => setShowPassword(!showPassword)}
                        className='absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors'
                        tabIndex={-1}
                      >
                        {showPassword ? (
                          <EyeOff className='h-4 w-4' />
                        ) : (
                          <Eye className='h-4 w-4' />
                        )}
                      </button>
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button
                type='button'
                variant='outline'
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                取消
              </Button>
              <Button type='submit' disabled={isPending}>
                {isPending && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
                重置密码
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
