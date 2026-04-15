/**
 * 角色表单对话框组件
 */
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
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
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import {
  createRole,
  updateRole,
  type RoleListItem,
} from '@/lib/api/role'

// 表单验证 Schema
const formSchema = z.object({
  name: z.string().min(1, '角色名称不能为空').max(100, '角色名称不能超过100个字符'),
  code: z.string().min(1, '角色编码不能为空').max(50, '角色编码不能超过50个字符'),
  status: z.enum(['0', '1']).default('0'),
  sort_order: z.coerce.number().int().min(0, '排序号不能为负数').default(0),
  description: z.string().optional(),
})

type FormInput = z.input<typeof formSchema>
type FormValues = z.infer<typeof formSchema>

/**
 * 统一角色表单默认值，避免输入/输出类型在 reset 时漂移。
 */
const defaultFormValues: FormInput = {
  name: '',
  code: '',
  status: '0',
  sort_order: 0,
  description: '',
}

interface RoleFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role?: RoleListItem
  onSuccess: () => void
}

export function RoleFormDialog({
  open,
  onOpenChange,
  role,
  onSuccess,
}: RoleFormDialogProps) {
  const isEdit = !!role

  // 表单
  const form = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: defaultFormValues,
  })

  // 当对话框打开时，重置表单
  useEffect(() => {
    if (open) {
      if (isEdit && role) {
        // 编辑模式：填充现有数据
        form.reset({
          name: role.name,
          code: role.code,
          status: role.status as FormInput['status'],
          sort_order: role.sort_order,
          description: role.description || '',
        })
      } else {
        // 创建模式：重置为默认值
        form.reset(defaultFormValues)
      }
    }
  }, [open, isEdit, role, form])

  // 创建/更新 Mutation
  const { mutate: handleSubmit, isPending } = useMutation({
    mutationFn: async (values: FormValues) => {
      if (isEdit && role) {
        return updateRole({
          id: role.id,
          ...values,
          description: values.description || undefined,
        })
      } else {
        return createRole({
          ...values,
          description: values.description || undefined,
        })
      }
    },
    onSuccess: () => {
      toast.success(isEdit ? '更新成功' : '创建成功')
      onOpenChange(false)
      onSuccess()
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.message || (isEdit ? '更新失败' : '创建失败')
      )
    },
  })

  const onSubmit = (values: FormValues) => {
    handleSubmit(values)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-2xl max-h-[90vh] flex flex-col p-0'>
        <DialogHeader className='px-6 pt-6 pb-4 border-b'>
          <DialogTitle>{isEdit ? '编辑角色' : '新建角色'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '修改角色信息' : '填写角色信息'}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className='flex flex-col flex-1 overflow-hidden'
          >
            <div className='flex-1 overflow-y-auto px-6 py-4 space-y-4'>
              {/* 角色名称 */}
              <FormField
                control={form.control}
                name='name'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      角色名称 <span className='text-destructive'>*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder='请输入角色名称' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 角色编码 */}
              <FormField
                control={form.control}
                name='code'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      角色编码 <span className='text-destructive'>*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder='如：admin、user、readonly'
                        disabled={isEdit}
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>
                      {isEdit
                        ? '角色编码创建后不可修改'
                        : '角色编码用于系统内部标识，创建后不可修改'}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 角色状态 */}
              <FormField
                control={form.control}
                name='status'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>状态</FormLabel>
                    <FormControl>
                      <RadioGroup
                        value={field.value}
                        onValueChange={field.onChange}
                        className='flex items-center gap-4'
                      >
                        <div className='flex items-center space-x-2'>
                          <RadioGroupItem value='0' id='status-normal' />
                          <Label htmlFor='status-normal'>正常</Label>
                        </div>
                        <div className='flex items-center space-x-2'>
                          <RadioGroupItem value='1' id='status-disabled' />
                          <Label htmlFor='status-disabled'>停用</Label>
                        </div>
                      </RadioGroup>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 显示排序 */}
              <FormField
                control={form.control}
                name='sort_order'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>显示排序</FormLabel>
                    <FormControl>
                      <Input
                        type='number'
                        placeholder='0'
                        {...field}
                        value={typeof field.value === 'number' ? field.value : ''}
                      />
                    </FormControl>
                    <FormDescription>
                      数字越小越靠前，默认为0
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 角色描述 */}
              <FormField
                control={form.control}
                name='description'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>角色描述</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder='请输入角色描述'
                        className='resize-none'
                        rows={3}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter className='px-6 py-4 border-t'>
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
                {isEdit ? '保存' : '创建'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
