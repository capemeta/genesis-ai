import { Link } from '@tanstack/react-router'
import { ArrowRight, Database, MessageSquare, Sparkles } from 'lucide-react'
import homeHeroBg from '@/assets/home/home-hero-bg5.svg'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

export function HomeHero() {
  return (
    <section className='relative min-h-[240px] overflow-hidden rounded-3xl border border-border/60 bg-[#E8F2FF] p-6 shadow-sm md:min-h-[250px] md:p-8'>
      <img
        src={homeHeroBg}
        alt=''
        aria-hidden='true'
        className='pointer-events-none absolute inset-0 h-full w-full object-cover object-right'
      />

      <div className='relative flex flex-col gap-6'>
        <div className='space-y-3'>
          <Badge variant='outline' className='w-fit gap-1.5 rounded-full border-border/70 bg-background/85 px-3 backdrop-blur'>
            <Sparkles className='h-3.5 w-3.5 text-primary' />
            启元AI平台
          </Badge>
          <h1 className='max-w-3xl text-3xl font-semibold tracking-tight text-foreground/95 md:text-4xl'>
            启智新纪，元创未来
          </h1>
          <p className='max-w-2xl text-sm leading-6 text-muted-foreground md:text-base'>
            统一编排知识库、聊天、智能体，快速构建可扩展的企业级 AI 工作流。
          </p>
        </div>

        <div className='flex flex-wrap items-center gap-3'>
          <Button asChild size='lg' className='gap-2 rounded-full bg-[#1D4ED8] px-6 text-white shadow-sm shadow-blue-200/70 hover:bg-[#1E40AF] dark:bg-primary dark:text-primary-foreground'>
            <Link to='/knowledge-base'>
              进入知识库
              <Database className='h-4 w-4' />
            </Link>
          </Button>
          <Button asChild variant='outline' size='lg' className='gap-2 rounded-full border-[#BFDBFE] bg-white/85 px-6 text-[#1E3A8A] backdrop-blur hover:border-[#93C5FD] hover:bg-white'>
            <Link to='/chat'>
              进入聊天
              <MessageSquare className='h-4 w-4' />
            </Link>
          </Button>
          <Button asChild variant='ghost' className='gap-2 rounded-full bg-[#EEF4FF]/80 px-4 text-[#335CA8] hover:bg-[#E2ECFF] hover:text-[#1E3A8A]'>
            <Link to='/agents'>
              浏览智能体
              <ArrowRight className='h-4 w-4' />
            </Link>
          </Button>
        </div>
      </div>
    </section>
  )
}
