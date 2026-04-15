import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, KeyRound, Laptop, Loader2, LogOut } from 'lucide-react'
import { toast } from 'sonner'
import { withAppAssetPath } from '@/lib/app-base'
import { getFileUrl } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth-store'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { PasswordInput } from '@/components/password-input'
import { useTheme } from '@/context/theme-provider'
import type { ChangePasswordRequest, UpdateMyProfileRequest } from '@/lib/api/profile'
import {
  changeMyPassword,
  getMyProfile,
  getMySessions,
  revokeMySession,
  revokeOtherSessions,
  uploadMyAvatar,
  updateMyProfile,
} from '@/lib/api/profile'

const phoneRegex = /^1[3-9]\d{9}$/

const profileFormSchema = z.object({
  nickname: z.string().min(1, '昵称不能为空').max(255),
  email: z.union([z.string().email('邮箱格式不正确'), z.literal('')]).optional(),
  phone: z.union([z.string().regex(phoneRegex, '手机号格式不正确'), z.literal('')]).optional(),
  job_title: z.string().max(100, '职位不能超过100个字符').optional(),
  bio: z.string().max(500, '个人简介不能超过500个字符').optional(),
  language: z.enum(['zh', 'en']),
  timezone: z.enum(['Asia/Shanghai', 'UTC']),
  theme: z.enum(['light', 'dark', 'system']),
})

type ProfileFormValues = z.infer<typeof profileFormSchema>

const passwordFormSchema = z.object({
  old_password: z.string().min(8, '当前密码至少 8 位'),
  new_password: z.string()
    .min(8, '新密码长度必须为8-20位')
    .max(20, '新密码长度必须为8-20位')
    .regex(/[A-Z]/, '新密码必须包含大写字母')
    .regex(/[a-z]/, '新密码必须包含小写字母')
    .regex(/[0-9]/, '新密码必须包含数字')
    .regex(/[&*^%$#@!]/, '新密码必须包含特殊字符(&*^%$#@!中的一个)'),
  confirm_password: z.string().min(8, '请再次输入新密码'),
  logout_all_devices: z.boolean(),
}).refine((data) => data.new_password === data.confirm_password, {
  message: '两次输入的新密码不一致',
  path: ['confirm_password'],
})

type PasswordFormValues = z.infer<typeof passwordFormSchema>

function formatDateTime(value?: string | null) {
  if (!value) return '未记录'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return date.toLocaleString('zh-CN', {
    hour12: false,
  })
}

export function ProfileForm() {
  const defaultAvatarUrl = withAppAssetPath('images/default-avatar.png')
  const queryClient = useQueryClient()
  const { setTheme } = useTheme()
  const avatarInputRef = useRef<HTMLInputElement | null>(null)
  const getUserInfo = useAuthStore((state) => state.getUserInfo)
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false)

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile-me'],
    queryFn: getMyProfile,
  })

  const { data: sessionData, isLoading: isSessionsLoading } = useQuery({
    queryKey: ['profile-sessions'],
    queryFn: getMySessions,
  })

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    defaultValues: {
      nickname: '',
      email: '',
      phone: '',
      job_title: '',
      bio: '',
      language: 'zh',
      timezone: 'Asia/Shanghai',
      theme: 'system',
    },
    mode: 'onChange',
  })

  const passwordForm = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordFormSchema),
    defaultValues: {
      old_password: '',
      new_password: '',
      confirm_password: '',
      logout_all_devices: false,
    },
  })

  useEffect(() => {
    if (!profile) return

    form.reset({
      nickname: profile.nickname ?? profile.username,
      email: profile.email ?? '',
      phone: profile.phone ?? '',
      job_title: profile.job_title ?? '',
      bio: profile.bio ?? '',
      language: (profile.language ?? 'zh') as 'zh' | 'en',
      timezone: (profile.timezone ?? 'Asia/Shanghai') as 'Asia/Shanghai' | 'UTC',
      theme: (profile.theme ?? 'system') as 'light' | 'dark' | 'system',
    })

    setTheme((profile.theme ?? 'system') as 'light' | 'dark' | 'system')
  }, [profile, form, setTheme])

  const { mutate: submit, isPending } = useMutation({
    mutationFn: async (values: ProfileFormValues) => {
      const payload: UpdateMyProfileRequest = {
        nickname: values.nickname,
        email: values.email === '' ? undefined : values.email,
        phone: values.phone === '' ? undefined : values.phone,
        job_title: values.job_title === '' ? undefined : values.job_title,
        bio: values.bio === '' ? undefined : values.bio,
        language: values.language,
        timezone: values.timezone,
        theme: values.theme,
      }
      return await updateMyProfile(payload)
    },
    onSuccess: async (updatedProfile) => {
      setTheme(updatedProfile.theme ?? 'system')
      await queryClient.invalidateQueries({ queryKey: ['profile-me'] })
      toast.success('个人资料已更新')
    },
    onError: (error: any) => {
      toast.error(error?.message || '更新失败')
    },
  })

  const { mutate: revokeOthers, isPending: isRevokingOthers } = useMutation({
    mutationFn: revokeOtherSessions,
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ['profile-sessions'] })
      toast.success(`已注销 ${data.revoked_count} 个其他设备会话`)
    },
    onError: (error: any) => {
      toast.error(error?.message || '注销其他设备失败')
    },
  })

  const { mutate: revokeOne, isPending: isRevokingOne } = useMutation({
    mutationFn: revokeMySession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['profile-sessions'] })
      toast.success('会话已注销')
    },
    onError: (error: any) => {
      toast.error(error?.message || '注销会话失败')
    },
  })

  const { mutate: uploadAvatarMutation, isPending: isUploadingAvatar } = useMutation({
    mutationFn: uploadMyAvatar,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['profile-me'] })
      // 🔥 更新全局状态中的用户信息，确保导航栏头像同步更新
      await getUserInfo()
      toast.success('头像已更新')
    },
    onError: (error: any) => {
      toast.error(error?.message || '头像上传失败')
    },
  })

  const { mutate: changePasswordMutation, isPending: isChangingPassword } = useMutation({
    mutationFn: (payload: ChangePasswordRequest) => changeMyPassword(payload),
    onSuccess: async (data) => {
      passwordForm.reset()
      setPasswordDialogOpen(false)
      await queryClient.invalidateQueries({ queryKey: ['profile-sessions'] })
      if ((data?.revoked_count ?? 0) > 0) {
        toast.success(`密码已修改，并登出了 ${data.revoked_count} 个其他设备`)
      } else {
        toast.success('密码已修改')
      }
    },
    onError: (error: any) => {
      toast.error(error?.message || '修改密码失败')
    },
  })

  const onSubmit = (values: ProfileFormValues) => {
    submit(values)
  }

  const onSubmitPassword = (values: PasswordFormValues) => {
    changePasswordMutation({
      old_password: values.old_password,
      new_password: values.new_password,
      logout_all_devices: values.logout_all_devices,
    })
  }

  const handleAvatarSelect = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (file.size > 5 * 1024 * 1024) {
      toast.error('头像文件不能超过 5MB')
      event.target.value = ''
      return
    }

    uploadAvatarMutation(file)
    event.target.value = ''
  }

  const profileAvatarUrl = profile?.avatar_url
    ? getFileUrl(profile.avatar_url)
    : defaultAvatarUrl

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-6'>
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>个人资料</CardTitle>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='flex items-center gap-3'>
              <img
                src={profileAvatarUrl}
                alt='avatar'
                className='h-12 w-12 rounded-full border object-cover'
                onError={(event) => {
                  if (event.currentTarget.src.endsWith(defaultAvatarUrl)) {
                    return
                  }
                  event.currentTarget.src = defaultAvatarUrl
                }}
              />
              <div className='space-y-1'>
                <div className='text-sm font-medium'>{profile?.nickname ?? profile?.username}</div>
                <div className='text-sm text-muted-foreground'>@{profile?.username ?? '未登录'}</div>
              </div>
              <div className='ml-auto'>
                <input
                  ref={avatarInputRef}
                  type='file'
                  accept='image/png,image/jpeg,image/jpg,image/gif'
                  className='hidden'
                  onChange={handleAvatarSelect}
                />
                <Button
                  type='button'
                  variant='outline'
                  size='sm'
                  disabled={isUploadingAvatar}
                  onClick={() => avatarInputRef.current?.click()}
                >
                  {isUploadingAvatar ? (
                    <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                  ) : (
                    <Camera className='mr-2 h-4 w-4' />
                  )}
                  更换头像
                </Button>
              </div>
            </div>

            <div className='grid grid-cols-1 gap-3 rounded-lg border bg-muted/20 p-3 text-sm md:grid-cols-2'>
              <div>
                <div className='text-muted-foreground'>所属租户</div>
                <div className='mt-1 font-medium'>{profile?.tenant_name ?? '-'}</div>
              </div>
              <div>
                <div className='text-muted-foreground'>所属组织</div>
                <div className='mt-1 font-medium'>{profile?.organization_name ?? '-'}</div>
              </div>
            </div>

            <FormField
              control={form.control}
              name='nickname'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>昵称</FormLabel>
                  <FormControl>
                    <Input placeholder='请输入昵称' {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className='grid grid-cols-1 gap-4 md:grid-cols-3'>
              <FormField
                control={form.control}
                name='email'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className='flex items-center gap-2'>
                      <span>邮箱</span>
                      <Badge variant={profile?.email_verified ? 'default' : 'secondary'}>
                        {profile?.email_verified ? '已验证' : '未验证'}
                      </Badge>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder='选填' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name='phone'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className='flex items-center gap-2'>
                      <span>手机号</span>
                      <Badge variant={profile?.phone_verified ? 'default' : 'secondary'}>
                        {profile?.phone_verified ? '已验证' : '未验证'}
                      </Badge>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder='选填' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name='job_title'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>职位</FormLabel>
                    <FormControl>
                      <Input placeholder='例如：AI 产品经理' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name='bio'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>个人简介</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder='介绍一下你的职责、关注方向或擅长领域'
                      className='min-h-28'
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className='text-base'>简单偏好</CardTitle>
          </CardHeader>
          <CardContent className='space-y-4'>
            <FormField
              control={form.control}
              name='language'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>语言</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder='选择语言' />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value='zh'>中文</SelectItem>
                      <SelectItem value='en'>English</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name='theme'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>主题</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder='选择主题' />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value='system'>跟随系统</SelectItem>
                      <SelectItem value='light'>浅色</SelectItem>
                      <SelectItem value='dark'>深色</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name='timezone'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>时区</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder='选择时区' />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value='Asia/Shanghai'>Asia/Shanghai</SelectItem>
                      <SelectItem value='UTC'>UTC</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className='text-base'>账号状态</CardTitle>
          </CardHeader>
          <CardContent className='grid grid-cols-1 gap-3 text-sm md:grid-cols-2'>
            <div className='rounded-lg border p-3'>
              <div className='text-muted-foreground'>账号状态</div>
              <div className='mt-1 font-medium'>{profile?.status ?? '-'}</div>
            </div>
            <div className='rounded-lg border p-3'>
              <div className='text-muted-foreground'>最后登录时间</div>
              <div className='mt-1 font-medium'>{formatDateTime(profile?.last_login_at)}</div>
            </div>
            <div className='rounded-lg border p-3'>
              <div className='text-muted-foreground'>最后活跃时间</div>
              <div className='mt-1 font-medium'>{formatDateTime(profile?.last_active_at)}</div>
            </div>
            <div className='rounded-lg border p-3'>
              <div className='text-muted-foreground'>最后登录 IP</div>
              <div className='mt-1 font-medium'>{profile?.last_login_ip ?? '未记录'}</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0'>
            <CardTitle className='text-base'>账号安全</CardTitle>
            <Button
              type='button'
              variant='outline'
              size='sm'
              onClick={() => setPasswordDialogOpen(true)}
            >
              <KeyRound className='mr-2 h-4 w-4' />
              修改密码
            </Button>
          </CardHeader>
          <CardContent className='grid grid-cols-1 gap-3 text-sm md:grid-cols-2'>
              <div className='rounded-lg border p-3'>
              <div className='text-muted-foreground'>最近修改密码</div>
              <div className='mt-1 font-medium'>{formatDateTime(profile?.password_changed_at)}</div>
            </div>
            <div className='rounded-lg border p-3'>
              <div className='text-muted-foreground'>安全建议</div>
              <div className='mt-1 text-muted-foreground'>
                建议定期修改密码，并在敏感操作后注销其他设备。
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0'>
            <CardTitle className='text-base'>活跃会话</CardTitle>
            <Button
              type='button'
              variant='outline'
              size='sm'
              disabled={isSessionsLoading || isRevokingOthers}
              onClick={() => revokeOthers()}
            >
              {isRevokingOthers ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <LogOut className='mr-2 h-4 w-4' />}
              注销其他设备
            </Button>
          </CardHeader>
          <CardContent className='space-y-3'>
            {isSessionsLoading ? (
              <div className='flex items-center justify-center py-6 text-muted-foreground'>
                <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                正在加载会话...
              </div>
            ) : sessionData?.sessions?.length ? (
              sessionData.sessions.map((session) => (
                <div
                  key={session.session_id}
                  className='flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between'
                >
                  <div className='space-y-2'>
                    <div className='flex items-center gap-2'>
                      <Laptop className='h-4 w-4 text-muted-foreground' />
                      <span className='font-medium'>
                        {session.is_current ? '当前设备' : '其他设备'}
                      </span>
                      <Badge variant={session.is_current ? 'default' : 'secondary'}>
                        {session.is_current ? '当前会话' : '活跃中'}
                      </Badge>
                    </div>
                    <div className='text-sm text-muted-foreground'>
                      IP：{session.client_ip || '未记录'}
                    </div>
                    <div className='text-sm text-muted-foreground break-all'>
                      设备：{session.user_agent || '未记录'}
                    </div>
                    <div className='grid grid-cols-1 gap-2 text-sm text-muted-foreground md:grid-cols-2'>
                      <div>创建时间：{formatDateTime(session.created_at)}</div>
                      <div>最近活跃：{formatDateTime(session.last_active_at)}</div>
                    </div>
                  </div>
                  <div>
                    {!session.is_current ? (
                      <Button
                        type='button'
                        variant='outline'
                        size='sm'
                        disabled={isRevokingOne}
                        onClick={() => revokeOne(session.session_id)}
                      >
                        {isRevokingOne ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : null}
                        注销此会话
                      </Button>
                    ) : (
                      <div className='text-sm text-muted-foreground'>当前登录设备不可在此处注销</div>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className='rounded-lg border border-dashed p-6 text-sm text-muted-foreground'>
                暂无其他活跃会话
              </div>
            )}
          </CardContent>
        </Card>

        <div className='flex items-center gap-3'>
          <Button type='submit' disabled={isLoading || isPending}>
            {isPending ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : null}
            保存
          </Button>
        </div>
      </form>

      <Dialog open={passwordDialogOpen} onOpenChange={setPasswordDialogOpen}>
        <DialogContent className='sm:max-w-md'>
          <DialogHeader>
            <DialogTitle>修改密码</DialogTitle>
            <DialogDescription>
              为了安全起见，需要先验证当前密码。修改后可选择是否登出所有设备。
            </DialogDescription>
          </DialogHeader>

          <Form {...passwordForm}>
            <form onSubmit={passwordForm.handleSubmit(onSubmitPassword)} className='space-y-4'>
              <FormField
                control={passwordForm.control}
                name='old_password'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>当前密码</FormLabel>
                    <FormControl>
                      <PasswordInput placeholder='请输入当前密码' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={passwordForm.control}
                name='new_password'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>新密码</FormLabel>
                    <FormControl>
                      <PasswordInput placeholder='请输入新密码' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={passwordForm.control}
                name='confirm_password'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>确认新密码</FormLabel>
                    <FormControl>
                      <PasswordInput placeholder='请再次输入新密码' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={passwordForm.control}
                name='logout_all_devices'
                render={({ field }) => (
                  <FormItem className='rounded-lg border p-3'>
                    <FormLabel>登出所有设备</FormLabel>
                    <div className='mt-1 text-sm text-muted-foreground'>
                      开启后会立即使当前设备和其他所有设备下线，需要重新登录。
                    </div>
                    <FormControl>
                      <label className='mt-3 flex items-center gap-2 text-sm'>
                        <input
                          type='checkbox'
                          checked={field.value}
                          onChange={(event) => field.onChange(event.target.checked)}
                        />
                        修改密码后登出所有设备
                      </label>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type='button'
                  variant='outline'
                  onClick={() => setPasswordDialogOpen(false)}
                  disabled={isChangingPassword}
                >
                  取消
                </Button>
                <Button type='submit' disabled={isChangingPassword}>
                  {isChangingPassword ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : null}
                  确认修改
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </Form>
  )
}
