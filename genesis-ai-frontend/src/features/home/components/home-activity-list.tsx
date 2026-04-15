import { type ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type ActivityItem = {
  title: string
  description: string
  time: string
  status: string
  icon: ReactNode
}

type HomeActivityListProps = {
  items: ActivityItem[]
  loading?: boolean
}

export function HomeActivityList({ items, loading = false }: HomeActivityListProps) {
  const skeletonRows = Array.from({ length: 4 }, (_, index) => index)

  return (
    <Card className='h-full border-border/70 bg-gradient-to-b from-background to-muted/15 shadow-sm'>
      <CardHeader className='border-b border-border/50 pb-4'>
        <CardTitle className='text-lg'>最近动态</CardTitle>
      </CardHeader>
      <CardContent className='p-0'>
        <div className='divide-y divide-border/50'>
          {loading
            ? skeletonRows.map((row) => (
              <div key={row} className='flex items-center justify-between gap-4 px-6 py-4'>
                <div className='flex min-w-0 items-center gap-3'>
                  <div className='h-9 w-9 animate-pulse rounded-lg bg-muted' />
                  <div className='min-w-0 space-y-2'>
                    <div className='h-4 w-28 animate-pulse rounded bg-muted' />
                    <div className='h-3 w-52 animate-pulse rounded bg-muted' />
                  </div>
                </div>
                <div className='flex shrink-0 items-center gap-2'>
                  <div className='h-6 w-14 animate-pulse rounded-full bg-muted' />
                  <div className='h-3 w-12 animate-pulse rounded bg-muted' />
                </div>
              </div>
            ))
            : items.map((item) => (
              <div key={`${item.title}-${item.time}`} className='flex items-center justify-between gap-4 px-6 py-4 transition-colors hover:bg-muted/35'>
                <div className='flex min-w-0 items-center gap-3'>
                  <div className='flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/80 text-muted-foreground'>
                    {item.icon}
                  </div>
                  <div className='min-w-0'>
                    <p className='truncate text-sm font-medium'>{item.title}</p>
                    <p className='truncate text-xs text-muted-foreground'>{item.description}</p>
                  </div>
                </div>
                <div className='flex shrink-0 items-center gap-2'>
                  <Badge variant='secondary' className='rounded-full'>
                    {item.status}
                  </Badge>
                  <span className='text-xs text-muted-foreground'>{item.time}</span>
                </div>
              </div>
            ))}
        </div>
      </CardContent>
    </Card>
  )
}
