import { Link } from '@tanstack/react-router'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { AuthLayout } from '../auth-layout'
import { ForgotPasswordForm } from './components/forgot-password-form'

export function ForgotPassword() {
  return (
    <AuthLayout>
      <Card className='gap-4'>
        <CardHeader>
          <CardTitle className='text-lg tracking-tight'>
            找回密码
          </CardTitle>
          <CardDescription>
            请输入管理员预留的邮箱地址。
            <br />
            系统会向该邮箱发送重置密码链接。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ForgotPasswordForm />
        </CardContent>
        <CardFooter>
          <p className='mx-auto px-8 text-center text-sm text-balance text-muted-foreground'>
            当前环境不开放自助注册，如需账号请联系管理员。
            <br />
            已有账号可直接前往{' '}
            <Link
              to='/sign-in'
              className='underline underline-offset-4 hover:text-primary'
            >
              登录页
            </Link>
          </p>
        </CardFooter>
      </Card>
    </AuthLayout>
  )
}
