import { Link } from '@tanstack/react-router'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { AlertCircle } from 'lucide-react'
import { AuthLayout } from '../auth-layout'

export function SignUp() {
  return (
    <AuthLayout>
      <Card className='gap-4'>
        <CardHeader>
          <CardTitle className='flex items-center gap-2 text-lg tracking-tight'>
            <AlertCircle className='h-5 w-5 text-amber-500' />
            暂不开放自助注册
          </CardTitle>
          <CardDescription>
            当前环境的账号由后台管理员统一创建。
            <br />
            如需开通账号，请联系管理员；已有账号可直接前往{' '}
            <Link
              to='/sign-in'
              className='underline underline-offset-4 hover:text-primary'
            >
              登录页
            </Link>
          </CardDescription>
        </CardHeader>
      </Card>
    </AuthLayout>
  )
}
