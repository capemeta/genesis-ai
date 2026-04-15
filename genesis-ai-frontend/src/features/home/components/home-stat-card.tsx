import { type ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'

type HomeStatCardProps = {
  label: string
  value: string
  hint: string
  icon: ReactNode
  loading?: boolean
  tone?: 'blue' | 'violet' | 'emerald' | 'slate'
}

const toneStyles: Record<NonNullable<HomeStatCardProps['tone']>, { line: string; icon: string }> = {
  blue: {
    line: 'from-sky-400/70 via-blue-500/65 to-transparent',
    icon: 'bg-blue-500/10 text-blue-600 dark:bg-blue-500/20 dark:text-blue-300',
  },
  violet: {
    line: 'from-violet-400/70 via-indigo-500/65 to-transparent',
    icon: 'bg-violet-500/10 text-violet-600 dark:bg-violet-500/20 dark:text-violet-300',
  },
  emerald: {
    line: 'from-emerald-400/70 via-green-500/65 to-transparent',
    icon: 'bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-300',
  },
  slate: {
    line: 'from-slate-400/70 via-slate-500/65 to-transparent',
    icon: 'bg-slate-500/10 text-slate-600 dark:bg-slate-500/20 dark:text-slate-300',
  },
}

export function HomeStatCard({ label, value, hint, icon, loading = false, tone = 'slate' }: HomeStatCardProps) {
  const currentTone = toneStyles[tone]

  return (
    <Card className='relative overflow-hidden border-border/70 bg-gradient-to-b from-background to-muted/20 shadow-sm dark:from-background dark:to-slate-900/20'>
      <div className={`absolute left-0 top-0 h-1 w-full bg-gradient-to-r ${currentTone.line}`} />
      <CardContent className='space-y-3 p-5'>
        <div className='flex items-center justify-between'>
          <p className='text-sm text-muted-foreground'>{label}</p>
          <div className={`rounded-md px-2 py-1 ${currentTone.icon}`}>{icon}</div>
        </div>
        {loading ? (
          <>
            <div className='h-9 w-24 animate-pulse rounded-md bg-muted' />
            <div className='h-3 w-36 animate-pulse rounded-md bg-muted' />
          </>
        ) : (
          <>
            <p className='text-3xl font-semibold tracking-tight'>{value}</p>
            <p className='text-xs text-muted-foreground'>{hint}</p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
