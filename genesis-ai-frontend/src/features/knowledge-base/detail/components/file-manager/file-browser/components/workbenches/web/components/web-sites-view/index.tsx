/**
 * 站点配置视图主组件
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchKnowledgeBase } from '@/lib/api/knowledge-base'
import type { ScheduleFormState } from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/shared/schedule-rule-builder'
import { useWebSchedules } from '../../hooks'
import { useSaveScheduleMutation } from '../../hooks'
import { fromSchedule, buildSchedulePayload } from '../../utils'
import { KbScheduleCard } from './kb-schedule-card'

export interface WebSitesViewProps {
  kbId: string
}

export function WebSitesView({ kbId }: WebSitesViewProps) {
  // 知识库配置
  const { data: kbConfig } = useQuery({
    queryKey: ['knowledge-base', kbId, 'web-site-config'],
    queryFn: () => fetchKnowledgeBase(kbId),
    staleTime: 10_000,
  })

  // 调度规则
  const { kbDefaultSchedule } = useWebSchedules({ kbId, view: 'web-sites' })
  const [kbScheduleForm, setKbScheduleForm] = useState<ScheduleFormState>(fromSchedule())

  // 同步表单
  useEffect(() => {
    setKbScheduleForm(fromSchedule(kbDefaultSchedule))
  }, [kbDefaultSchedule])

  // 保存 mutation
  const saveScheduleMutation = useSaveScheduleMutation(kbId)

  // 抓取深度
  const webRetrievalConfig = (kbConfig?.retrieval_config as any)?.web || {}
  const effectiveCrawlDepth = Number(webRetrievalConfig.crawl_depth || 1)

  // 保存调度规则
  const handleSaveSchedule = (form: ScheduleFormState) => {
    saveScheduleMutation.mutate({
      scheduleId: kbDefaultSchedule?.schedule_id,
      payload: buildSchedulePayload(
        { kb_id: kbId, scope_level: 'kb_default' },
        form
      ),
    })
  }

  return (
    <div className="flex h-full min-h-0 bg-gradient-to-br from-slate-50 via-white to-slate-50/80">
      <main className="flex h-full min-h-0 min-w-0 flex-1 flex-col px-6 pb-4 pt-0 md:pb-5">
        <KbScheduleCard
          effectiveCrawlDepth={effectiveCrawlDepth}
          kbDefaultSchedule={kbDefaultSchedule}
          kbScheduleForm={kbScheduleForm}
          onKbScheduleFormChange={setKbScheduleForm}
          onSave={handleSaveSchedule}
          isSaving={saveScheduleMutation.isPending}
        />
      </main>
    </div>
  )
}
