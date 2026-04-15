import { type ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import { ArrowRight } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

type HomeEntryCardProps = {
  icon: ReactNode
  title: string
  description: string
  to: '/knowledge-base' | '/chat'
  accentClassName: string
}

export function HomeEntryCard({ icon, title, description, to, accentClassName }: HomeEntryCardProps) {
  return (
    <Link to={to} className='group block'>
      <Card className='h-full border-border/70 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg'>
        <CardHeader className='space-y-3'>
          <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${accentClassName}`}>
            {icon}
          </div>
          <CardTitle className='text-lg'>{title}</CardTitle>
          <CardDescription className='leading-relaxed'>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className='inline-flex items-center gap-1 text-sm font-medium text-primary'>
            立即进入
            <ArrowRight className='h-4 w-4 transition-transform group-hover:translate-x-0.5' />
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
