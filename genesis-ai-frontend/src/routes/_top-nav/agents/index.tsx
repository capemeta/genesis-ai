import { createFileRoute } from '@tanstack/react-router'
import { Construction, Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export const Route = createFileRoute('/_top-nav/agents/')({
  component: AgentsPage,
})

function AgentsPage() {
  return (
    <div className='w-full max-w-[1920px] mx-auto min-h-[calc(100vh-9rem)] bg-white px-6 py-8 md:px-8 lg:px-12 xl:px-16'>
      <div className='mx-auto flex h-full max-w-3xl items-center justify-center'>
        <Card className='w-full border-2 border-dashed border-zinc-300 bg-white shadow-lg'>
          <CardHeader className='items-center space-y-3 pb-2 text-center'>
            <div className='flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-100 ring-1 ring-zinc-300/80'>
              <Construction className='h-8 w-8 text-zinc-800' />
            </div>
            <Badge className='bg-zinc-900 text-white hover:bg-zinc-800'>
              功能建设中
            </Badge>
            <CardTitle className='text-3xl font-extrabold tracking-tight text-zinc-900'>
              暂未实现，敬请期待
            </CardTitle>
            <CardDescription className='mx-auto max-w-lg text-base leading-7 text-zinc-700'>
              智能体管理能力正在加速开发中，我们会尽快开放可用功能。
            </CardDescription>
          </CardHeader>
          <CardContent className='flex items-center justify-center pb-8'>
            <div className='inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-zinc-100 px-4 py-2 text-sm text-zinc-800'>
              <Sparkles className='h-4 w-4' />
              新能力上线后将在此页面展示
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
