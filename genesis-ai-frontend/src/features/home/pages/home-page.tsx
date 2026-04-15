import { HomeHero } from '@/features/home/components/home-hero'
import { HomeStatCard } from '@/features/home/components/home-stat-card'
import { HomeActivityList } from '@/features/home/components/home-activity-list'
import { useHomeOverview } from '@/features/home/hooks/use-home-overview'
import { Button } from '@/components/ui/button'
import { RefreshCcw } from 'lucide-react'

export function HomePage() {
  const { statItems, activityItems, statsLoading, activityLoading, latestRefreshText, refreshAll, refreshing } = useHomeOverview()

  return (
    <div className='mx-auto w-full max-w-[1700px] space-y-8 px-6 py-8 md:px-8 xl:px-14'>
      <HomeHero />

      <section className='space-y-4'>
        <div className='flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between'>
          <div className='space-y-1'>
            <h2 className='text-xl font-semibold tracking-tight'>运行概览</h2>
            <p className='text-sm text-muted-foreground'>首页已接入部分实时指标，并提供手动刷新。</p>
          </div>
          <div className='flex items-center gap-3'>
            <span className='text-xs text-muted-foreground'>最近刷新：{latestRefreshText}</span>
            <Button
              variant='outline'
              size='sm'
              className='gap-2 border-border/70 bg-background/80 hover:bg-muted/40'
              onClick={() => void refreshAll()}
              disabled={refreshing}
            >
              <RefreshCcw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              {refreshing ? '刷新中...' : '刷新'}
            </Button>
          </div>
        </div>
        <div className='grid gap-4 xl:grid-cols-[1.2fr_1fr]'>
          <div className='grid gap-4 sm:grid-cols-2'>
            {statItems.map((item) => (
              <HomeStatCard
                key={item.label}
                label={item.label}
                value={item.value}
                hint={item.hint}
                icon={item.icon}
              tone={item.tone}
                loading={statsLoading}
              />
            ))}
          </div>
          <HomeActivityList items={activityItems} loading={activityLoading} />
        </div>
      </section>
    </div>
  )
}
