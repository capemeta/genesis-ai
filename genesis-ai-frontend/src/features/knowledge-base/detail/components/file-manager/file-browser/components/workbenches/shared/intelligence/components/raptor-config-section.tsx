import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Bird } from 'lucide-react'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'

interface RaptorConfigSectionProps {
  config: ConfigState
  onConfigChange: (config: ConfigState) => void
}

export function RaptorConfigSection({ config: _config, onConfigChange: _onConfigChange }: RaptorConfigSectionProps) {
  return (
    <section className='space-y-4 text-left'>
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <Bird className='h-5 w-5 text-emerald-500' />
          <h3 className='text-base font-semibold tracking-tight text-foreground'>
            RAPTOR 递归摘要策略
          </h3>
          <Badge variant='secondary'>暂未实现</Badge>
        </div>
        <Switch checked={false} disabled />
      </div>

      <div className='flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[12px] text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300'>
        <div className='w-1 shrink-0 rounded-full bg-amber-500' />
        当前阶段仅保留策略入口占位，递归聚类、摘要树构建与多层索引检索链路均暂未实现，暂不建议开启。
      </div>
    </section>
  )
}
