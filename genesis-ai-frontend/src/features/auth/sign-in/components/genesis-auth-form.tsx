/**
 * Genesis AI 登录表单（带验证码）
 * 
 * 🔥 Cookie 认证模式：
 * - 后端自动设置 HttpOnly Cookie
 * - 前端无需存储 token
 * - 浏览器自动携带 Cookie
 * - 更安全，防止 XSS 攻击
 * 
 * 🔥 安全增强：
 * - 始终要求验证码，提升安全性
 * - 所有文本已中文化
 */
import { useState } from 'react'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from '@tanstack/react-router'
import { Loader2, LogIn } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth-store'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { PasswordInput } from '@/components/password-input'
import { CaptchaInput } from './captcha-input'

const formSchema = z.object({
  username: z.string().min(1, '请输入用户名或邮箱'),
  password: z.string().min(1, '请输入密码'),
  captcha_code: z.string().min(1, '请输入验证码'),  // 🔥 验证码必填
  remember_me: z.boolean(),
})

interface GenesisAuthFormProps extends React.HTMLAttributes<HTMLFormElement> {
  redirectTo?: string
}

export function GenesisAuthForm({
  className,
  redirectTo,
  ...props
}: GenesisAuthFormProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [captchaToken, setCaptchaToken] = useState<string>('')
  const navigate = useNavigate()
  const authStore = useAuthStore()
  const [refreshKey, setRefreshKey] = useState(0)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      username: '',
      password: '',
      captcha_code: '',
      remember_me: true, // 🔥 默认勾选"记住我"，提供更好的用户体验
    },
  })

  // 刷新验证码
  const handleRefreshCaptcha = () => {
    setRefreshKey(prev => prev + 1)
  }

  async function onSubmit(data: z.infer<typeof formSchema>) {
    setIsLoading(true)

    try {
      // 🔥 验证验证码 token 是否已获取
      if (!captchaToken) {
        toast.error('验证码加载失败，请刷新页面重试')
        setIsLoading(false)
        return
      }

      // 准备登录数据
      const loginData = {
        username: data.username,
        password: data.password,
        remember_me: data.remember_me,
        captcha_token: captchaToken,
        captcha_code: data.captcha_code,
      }

      // 🔥 使用统一的 auth-store 的 login 方法
      await authStore.login(loginData)
      console.log('[Login] Login API successful, access_token stored in auth store')

      // 🔥 Cookie 模式：后端已设置 HttpOnly Cookie，前端无需存储 token
      // 浏览器会自动携带 Cookie，无需手动处理

      // 🔥 优化：移除重复的用户信息和菜单获取逻辑
      // 全局路由守卫会在跳转时自动检查并获取用户信息和菜单权限
      // 这样避免了重复请求，提升登录速度

      // 登录成功提示
      toast.success('登录成功', {
        duration: 1500  // 简化提示消息，避免挡住导航
      })

      // 跳转到目标页面
      // 🔥 路由守卫会自动处理用户信息和菜单权限的获取
      const targetPath = redirectTo || '/'
      navigate({ to: targetPath, replace: true })
    } catch (error: any) {
      console.error('Login error:', error)
      // 刷新验证码
      handleRefreshCaptcha()

    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className={cn('grid gap-3', className)}
        {...props}
      >
        <FormField
          control={form.control}
          name='username'
          render={({ field }) => (
            <FormItem>
              <FormLabel>用户名</FormLabel>
              <FormControl>
                <Input placeholder='请输入用户名' className='h-10' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name='password'
          render={({ field }) => (
            <FormItem className='relative'>
              <FormLabel>密码</FormLabel>
              <FormControl>
                <PasswordInput placeholder='请输入密码' inputClassName='h-10' {...field} />
              </FormControl>
              <FormMessage />
              <Link
                to='/forgot-password'
                className='absolute end-0 -top-0.5 text-sm font-medium text-muted-foreground hover:opacity-75'
              >
                忘记密码？
              </Link>
            </FormItem>
          )}
        />

        {/* 🔥 始终显示验证码 */}
        <FormField
          control={form.control}
          name='captcha_code'
          render={({ field }) => (
            <FormItem>
              <FormLabel>验证码</FormLabel>
              <FormControl>
                <CaptchaInput
                  value={field.value}
                  onChange={field.onChange}
                  onTokenChange={setCaptchaToken}
                  disabled={isLoading}
                  refreshKey={refreshKey}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name='remember_me'
          render={({ field }) => (
            <FormItem className='flex flex-row items-center space-x-2 space-y-0'>
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  disabled={isLoading}
                />
              </FormControl>
              <FormLabel className='text-sm font-normal cursor-pointer'>
                记住我
              </FormLabel>
            </FormItem>
          )}
        />

        <Button className='mt-2' disabled={isLoading}>
          {isLoading ? <Loader2 className='animate-spin' /> : <LogIn />}
          登录
        </Button>
      </form>
    </Form>
  )
}
