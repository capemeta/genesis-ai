import { useNavigate, useRouter } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'

export function NotFoundError() {
  const navigate = useNavigate()
  const { history } = useRouter()
  return (
    <div className='h-svh'>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
        <h1 className='text-[7rem] leading-tight font-bold'>404</h1>
        <span className='font-medium'>页面未找到</span>
        <p className='text-center text-muted-foreground'>
          您访问的页面不存在 <br />
          或可能已被删除
        </p>
        <div className='mt-6 flex gap-4'>
          <Button variant='outline' onClick={() => history.go(-1)}>
            返回
          </Button>
          <Button onClick={() => navigate({ to: '/' })}>回到首页</Button>
        </div>
      </div>
    </div>
  )
}
