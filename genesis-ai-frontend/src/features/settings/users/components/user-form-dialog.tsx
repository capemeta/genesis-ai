/**
 * 用户表单对话框组件
 */
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Check, X } from 'lucide-react'
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
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { cn } from '@/lib/utils'
import {
  createUser,
  updateUser,
  type UserListItem,
  getUserRoles,
} from '@/lib/api/user'
import { fetchAssignableRoles, type RoleListItem } from '@/lib/api/role'
import { fetchOrganizationTree } from '@/lib/api/organization'
import { OrganizationTreeSelect } from './organization-tree-select'

// 密码验证规则
const passwordSchema = z.string()
  .min(8, '密码长度必须为8-20位')
  .max(20, '密码长度必须为8-20位')
  .regex(/[A-Z]/, '密码必须包含大写字母')
  .regex(/[a-z]/, '密码必须包含小写字母')
  .regex(/[0-9]/, '密码必须包含数字')
  .regex(/[&*^%$#@!]/, '密码必须包含特殊字符(&*^%$#@!中的一个)')

// 手机号验证规则（中国大陆）
const phoneSchema = z.string()
  .regex(/^1[3-9]\d{9}$/, '手机号格式不正确')

// 表单验证 Schema
const formSchema = z.object({
  username: z.string()
    .min(1, '用户名不能为空')
    .max(100, '用户名不能超过100个字符'),
  nickname: z.string()
    .min(1, '昵称不能为空')
    .max(255, '昵称不能超过255个字符'),
  password: z.union([z.literal(''), passwordSchema]).optional(),
  email: z.string().email('邮箱格式不正确').optional().or(z.literal('')),
  phone: z.union([z.literal(''), phoneSchema]).optional(),
  job_title: z.string().max(100, '职位不能超过100个字符').optional().or(z.literal('')),
  employee_no: z.string().max(100, '工号不能超过100个字符').optional().or(z.literal('')),
  bio: z.string().max(500, '个人简介不能超过500个字符').optional().or(z.literal('')),
  organization_id: z.string().optional().nullable(),
  status: z.enum(['active', 'disabled', 'locked']),
  role_ids: z.array(z.string()),
})

type FormValues = z.infer<typeof formSchema>

interface UserFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user?: UserListItem
  onSuccess: () => void
}

export function UserFormDialog({
  open,
  onOpenChange,
  user,
  onSuccess,
}: UserFormDialogProps) {
  const isEdit = !!user
  const [openRolePopover, setOpenRolePopover] = useState(false)
  const queryClient = useQueryClient()

  // 表单
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      username: '',
      nickname: '',
      password: undefined,
      email: undefined,
      phone: undefined,
      job_title: undefined,
      employee_no: undefined,
      bio: undefined,
      organization_id: undefined,
      status: 'active',
      role_ids: [],
    },
  })

  // 查询可分配的角色列表（不分页，用于表单下拉选择）
  const { data: rolesData } = useQuery({
    queryKey: ['assignable-roles'],
    queryFn: async () => {
      const result = await fetchAssignableRoles()
      return result as RoleListItem[]
    },
  })

  // 查询组织树形结构
  const { data: organizationTree } = useQuery({
    queryKey: ['organization-tree'],
    queryFn: () => fetchOrganizationTree({ status: '0' }),
  })

  // 查询用户角色（编辑时）
  const { data: userRoles } = useQuery({
    queryKey: ['user-roles', user?.id],
    queryFn: () => (user ? getUserRoles(user.id) : Promise.resolve([])),
    enabled: isEdit && !!user?.id,
  })

  // 当对话框打开时，重置表单
  useEffect(() => {
    if (open) {
      if (isEdit && user) {
        // 编辑模式：填充现有数据
        const roleIds = userRoles?.map((r) => r.id) || []
        form.reset({
          username: user.username,
          nickname: user.nickname || '',
          password: undefined,
          email: user.email || undefined,
          phone: user.phone || undefined,
          job_title: user.job_title || undefined,
          employee_no: user.employee_no || undefined,
          bio: user.bio || undefined,
          organization_id: user.organization_id ? String(user.organization_id) : undefined,
          status: user.status as 'active' | 'disabled' | 'locked',
          role_ids: roleIds,
        })
      } else {
        // 创建模式：重置为默认值
        form.reset({
          username: '',
          nickname: '',
          password: undefined,
          email: undefined,
          phone: undefined,
          job_title: undefined,
          employee_no: undefined,
          bio: undefined,
          organization_id: undefined,
          status: 'active',
          role_ids: [],
        })
      }
    }
  }, [open, isEdit, user, userRoles, form])

  // 创建/更新 Mutation
  const { mutate: handleSubmit, isPending } = useMutation({
    mutationFn: async (values: FormValues) => {
      if (isEdit && user) {
        // 更新用户（包含角色分配）
        await updateUser({
          id: user.id,
          nickname: values.nickname,
          email: values.email || undefined,
          phone: values.phone,
          job_title: values.job_title || undefined,
          employee_no: values.employee_no || undefined,
          bio: values.bio || undefined,
          organization_id: values.organization_id || undefined,
          status: values.status,
          password: values.password,
          role_ids: values.role_ids,
        })
      } else {
        // 创建用户（包含角色分配）
        if (!values.password) {
          throw new Error('创建用户时密码不能为空')
        }
        await createUser({
          username: values.username,
          nickname: values.nickname,
          password: values.password,
          email: values.email || undefined,
          phone: values.phone,
          job_title: values.job_title || undefined,
          employee_no: values.employee_no || undefined,
          bio: values.bio || undefined,
          organization_id: values.organization_id || undefined,
          status: values.status,
          role_ids: values.role_ids,
        })
      }
    },
    onSuccess: () => {
      // 更新缓存
      if (isEdit && user) {
        // 清除用户角色缓存，强制重新获取
        queryClient.invalidateQueries({
          queryKey: ['user-roles', user.id],
        })
        // 清除用户列表缓存，确保列表数据最新
        queryClient.invalidateQueries({
          queryKey: ['users'],
        })
      } else {
        // 创建新用户时，清除用户列表缓存
        queryClient.invalidateQueries({
          queryKey: ['users'],
        })
      }
      
      toast.success(isEdit ? '更新成功' : '创建成功')
      onOpenChange(false)
      onSuccess()
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.message || error.message || (isEdit ? '更新失败' : '创建失败')
      )
    },
  })

  const onSubmit = (values: FormValues) => {
    // 创建用户时验证密码
    if (!isEdit && !values.password) {
      toast.error('创建用户时密码不能为空')
      return
    }
    handleSubmit(values)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-2xl max-h-[90vh] flex flex-col p-0'>
        <DialogHeader className='px-6 pt-6 pb-4 border-b'>
          <DialogTitle>{isEdit ? '编辑用户' : '新建用户'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '修改用户信息' : '填写用户信息'}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className='flex flex-col flex-1 overflow-hidden'
          >
            <div className='flex-1 overflow-y-auto px-6 py-4 space-y-4'>
              {/* 用户名 */}
              <FormField
                control={form.control}
                name='username'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      用户名 <span className='text-destructive'>*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder='请输入用户名'
                        disabled={isEdit}
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>
                      {isEdit ? '用户名创建后不可修改' : '用户名全局唯一，用于登录'}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 昵称 */}
              <FormField
                control={form.control}
                name='nickname'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      昵称 <span className='text-destructive'>*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder='请输入昵称' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 密码 */}
              {!isEdit && (
                <FormField
                  control={form.control}
                  name='password'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        密码 <span className='text-destructive'>*</span>
                      </FormLabel>
                      <FormControl>
                        <Input
                          type='password'
                          placeholder='请输入密码'
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        密码要求：8-20位，必须包含大小写字母、数字和特殊字符(&*^%$#@!中的一个)
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {/* 邮箱 */}
              <FormField
                control={form.control}
                name='email'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>邮箱</FormLabel>
                    <FormControl>
                      <Input type='email' placeholder='请输入邮箱' {...field} value={field.value ?? ''} />
                    </FormControl>
                    <FormDescription>邮箱全局唯一，可用于通知和后续验证</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 手机号 */}
              <FormField
                control={form.control}
                name='phone'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>手机号</FormLabel>
                    <FormControl>
                      <Input placeholder='请输入手机号' {...field} value={field.value ?? ''} />
                    </FormControl>
                    <FormDescription>手机号全局唯一，后续可用于短信登录或找回密码</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 职位 */}
              <FormField
                control={form.control}
                name='job_title'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>职位</FormLabel>
                    <FormControl>
                      <Input placeholder='请输入职位' {...field} value={field.value ?? ''} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 工号 */}
              <FormField
                control={form.control}
                name='employee_no'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>工号</FormLabel>
                    <FormControl>
                      <Input placeholder='请输入工号' {...field} value={field.value ?? ''} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 个人简介 */}
              <FormField
                control={form.control}
                name='bio'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>个人简介</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder='请输入个人简介'
                        className='min-h-24'
                        {...field}
                        value={field.value ?? ''}
                      />
                    </FormControl>
                    <FormDescription>最多 500 个字符，可用于补充用户背景和职责说明</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 所属部门 */}
              <FormField
                control={form.control}
                name='organization_id'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>所属部门</FormLabel>
                    <FormControl>
                      <OrganizationTreeSelect
                        value={field.value || null}
                        onChange={field.onChange}
                        treeData={organizationTree || []}
                        placeholder='请选择部门'
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 用户状态 */}
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
                          <RadioGroupItem value='active' id='status-active' />
                          <Label htmlFor='status-active'>正常</Label>
                        </div>
                        <div className='flex items-center space-x-2'>
                          <RadioGroupItem value='disabled' id='status-disabled' />
                          <Label htmlFor='status-disabled'>禁用</Label>
                        </div>
                        <div className='flex items-center space-x-2'>
                          <RadioGroupItem value='locked' id='status-locked' />
                          <Label htmlFor='status-locked'>锁定</Label>
                        </div>
                      </RadioGroup>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 角色 */}
              <FormField
                control={form.control}
                name='role_ids'
                render={({ field }) => {
                  const selectedRoles = rolesData?.filter((role) =>
                    field.value.includes(role.id)
                  ) || []

                  return (
                    <FormItem>
                      <FormLabel>角色</FormLabel>
                      <FormControl>
                        <Popover open={openRolePopover} onOpenChange={setOpenRolePopover}>
                          <PopoverTrigger asChild>
                            <div className='flex items-center gap-2 min-h-9 px-3 py-2 rounded-md border border-input bg-transparent text-sm shadow-xs transition-[color,box-shadow] outline-none focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:bg-input/30 dark:hover:bg-input/50 dark:aria-invalid:ring-destructive/40 flex-wrap gap-1 cursor-pointer'>
                              {selectedRoles.length > 0 ? (
                                <>
                                  {selectedRoles.map((role) => (
                                    <div
                                      key={role.id}
                                      className='inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-900 rounded text-sm'
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <span>{role.name}</span>
                                      <button
                                        type='button'
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          field.onChange(
                                            field.value.filter((id) => id !== role.id)
                                          )
                                        }}
                                        className='ml-1 hover:opacity-70'
                                      >
                                        <X className='h-3 w-3' />
                                      </button>
                                    </div>
                                  ))}
                                  {field.value.length > 0 && (
                                    <button
                                      type='button'
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        field.onChange([])
                                      }}
                                      className='ml-auto text-gray-400 hover:text-gray-600'
                                      title='清空所有'
                                    >
                                      <X className='h-4 w-4' />
                                    </button>
                                  )}
                                </>
                              ) : (
                                <span className='text-muted-foreground'>请选择角色</span>
                              )}
                            </div>
                          </PopoverTrigger>
                          <PopoverContent className='w-full p-0' align='start'>
                            <Command>
                              <CommandInput placeholder='搜索角色...' />
                              <CommandEmpty>未找到角色</CommandEmpty>
                              <CommandList
                                className='max-h-[280px] overflow-y-auto overscroll-contain [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-thumb]:rounded-full'
                                style={{
                                  overflowY: 'auto',
                                  WebkitOverflowScrolling: 'touch',
                                  pointerEvents: 'auto',
                                  touchAction: 'auto',
                                } as React.CSSProperties}
                                onWheel={(e) => {
                                  e.stopPropagation()
                                }}
                              >
                                <CommandGroup>
                                  {rolesData?.map((role) => (
                                    <CommandItem
                                      key={role.id}
                                      value={role.id}
                                      onSelect={(currentValue) => {
                                        const newRoleIds = field.value.includes(currentValue)
                                          ? field.value.filter((id) => id !== currentValue)
                                          : [...field.value, currentValue]
                                        field.onChange(newRoleIds)
                                      }}
                                    >
                                      <Check
                                        className={cn(
                                          'mr-2 h-4 w-4',
                                          field.value.includes(role.id)
                                            ? 'opacity-100'
                                            : 'opacity-0'
                                        )}
                                      />
                                      {role.name}
                                    </CommandItem>
                                  ))}
                                </CommandGroup>
                              </CommandList>
                            </Command>
                          </PopoverContent>
                        </Popover>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )
                }}
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
