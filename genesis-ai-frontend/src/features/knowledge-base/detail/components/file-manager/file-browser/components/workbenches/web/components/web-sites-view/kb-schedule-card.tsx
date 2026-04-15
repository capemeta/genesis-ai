/**
 * 知识库默认调度规则卡片
 */

import { Globe } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ScheduleFormState } from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/shared/schedule-rule-builder'
import ScheduleRuleBuilder from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/shared/schedule-rule-builder'
import type { WebScheduleItem } from '@/lib/api/web-sync'
import { buildSchedulePayload } from '../../utils'

export interface KbScheduleCardProps {
  effectiveCrawlDepth: number
  kbDefaultSchedule: WebScheduleItem | undefined
  kbScheduleForm: ScheduleFormState
  onKbScheduleFormChange: (form: ScheduleFormState) => void
  onSave: (payload: Parameters<typeof buildSchedulePayload>[1]) => void
  isSaving: boolean
}

export function KbScheduleCard({
  effectiveCrawlDepth,
  kbDefaultSchedule,
  kbScheduleForm,
  onKbScheduleFormChange,
  onSave,
  isSaving,
}: KbScheduleCardProps) {
  return (
    <Card className="flex min-h-0 flex-1 flex-col overflow-hidden border-slate-200/70 bg-white shadow-sm ring-1 ring-slate-950/5">
      <CardHeader className="relative shrink-0 space-y-0 overflow-hidden border-b border-sky-100/80 bg-gradient-to-br from-sky-50 via-cyan-50/85 to-violet-50/55 px-4 py-3 sm:px-5">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_85%_55%_at_95%_0%,rgba(255,255,255,0.42),transparent_50%)]"
          aria-hidden
        />
        <div className="relative z-[1] flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/85 text-sky-600 shadow-sm ring-1 ring-sky-100/90">
              <Globe className="h-4 w-4" strokeWidth={2} />
            </div>
            <div>
              <CardTitle className="text-base font-semibold leading-tight text-slate-800">站点抓取与同步策略</CardTitle>
              <p className="mt-0.5 text-[11px] leading-snug text-slate-500">
                现阶段抓取深度只支持 {effectiveCrawlDepth || 1} 层 · 知识库默认定时；单页覆盖请在「网页页面」配置
              </p>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 space-y-6 overflow-y-auto p-4 sm:p-5">
        <section className="space-y-4">
          <ScheduleRuleBuilder
            title="知识库默认定时"
            description="对全部网页页面生效。推荐优先使用「间隔」或「每日」模式；需要更复杂的节奏时再切换到 Cron。"
            form={kbScheduleForm}
            onChange={onKbScheduleFormChange}
            nextTriggerAt={kbDefaultSchedule?.next_trigger_at}
            saveLabel="保存默认规则"
            saveDisabled={isSaving}
            isSaving={isSaving}
            onSave={() => onSave(kbScheduleForm)}
          />
        </section>
      </CardContent>
    </Card>
  )
}
