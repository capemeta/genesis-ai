/**
 * Genesis AI 登录页面组件
 */
import { useSearch } from '@tanstack/react-router'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { AuthLayout } from '../auth-layout'
import { GenesisAuthForm } from './components/genesis-auth-form'

export function GenesisSignIn() {
  const { redirect } = useSearch({ from: '/(auth)/login' })

  return (
    <AuthLayout>
      <Card className='gap-4'>
        <CardHeader>
          <CardTitle className='text-lg tracking-tight'>
            登录 启元AI平台
          </CardTitle>
          <CardDescription>
            请输入您的凭据以访问您的账户
          </CardDescription>
        </CardHeader>
        <CardContent>
          <GenesisAuthForm redirectTo={redirect} />
        </CardContent>
        <CardFooter>
          <p className='px-8 text-center text-sm text-muted-foreground'>
            登录即表示您同意我们的{' '}
            <a
              href='/terms'
              className='underline underline-offset-4 hover:text-primary'
            >
              服务条款
            </a>{' '}
            和{' '}
            <a
              href='/privacy'
              className='underline underline-offset-4 hover:text-primary'
            >
              隐私政策
            </a>
            。
          </p>
        </CardFooter>
      </Card>
    </AuthLayout>
  )
}
