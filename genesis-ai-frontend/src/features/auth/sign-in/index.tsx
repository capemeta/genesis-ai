import { useSearch } from '@tanstack/react-router'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { AuthLayout } from '../auth-layout'
import { GenesisAuthForm } from './components/genesis-auth-form'

export function SignIn() {
  const { redirect } = useSearch({ from: '/(auth)/sign-in' })

  return (
    <AuthLayout>
      <Card className='gap-4'>
        <CardHeader>
          <CardTitle className='text-lg tracking-tight'>账号登录</CardTitle>
        </CardHeader>
        <CardContent>
          <GenesisAuthForm redirectTo={redirect} />
        </CardContent>
      </Card>
    </AuthLayout>
  )
}
