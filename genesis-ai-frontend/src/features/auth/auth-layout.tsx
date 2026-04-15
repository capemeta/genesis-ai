import { Logo } from '@/assets/logo'
import { TechSupportFooter } from '@/components/layout/tech-support-footer'

type AuthLayoutProps = {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className='flex min-h-svh flex-col'>
      <div className='container flex flex-1 max-w-none flex-col items-center justify-center'>
        <div className='mx-auto flex w-full flex-col justify-center space-y-2 py-8 sm:w-[480px] sm:p-8'>
          <div className='mb-4 flex items-center justify-center'>
            <Logo className='me-2' />
            <h1 className='text-xl font-medium'>启元AI平台</h1>
          </div>
          {children}
        </div>
      </div>
      <TechSupportFooter />
    </div>
  )
}
