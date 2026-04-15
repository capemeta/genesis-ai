/**
 * 调度规则相关 Hooks
 */

import { useQuery } from '@tanstack/react-query'
import { listWebSchedules, type WebScheduleItem } from '@/lib/api/web-sync'
import type { WebWorkbenchView } from '../types'

export interface UseWebSchedulesOptions {
  kbId: string
  view: WebWorkbenchView
}

export interface UseWebSchedulesReturn {
  /** 所有调度规则 */
  schedules: WebScheduleItem[]
  /** 知识库默认调度规则 */
  kbDefaultSchedule: WebScheduleItem | undefined
}

/**
 * 调度规则查询 Hook
 */
export function useWebSchedules(options: UseWebSchedulesOptions): UseWebSchedulesReturn {
  const { kbId, view } = options

  const { data: schedules = [] } = useQuery({
    queryKey: ['kb-web-schedules', kbId],
    queryFn: () => listWebSchedules({ kb_id: kbId }),
    staleTime: 5_000,
    enabled: view !== 'files',
  })

  // 知识库默认调度规则
  const kbDefaultSchedule = schedules.find(item => item.scope_level === 'kb_default')

  return {
    schedules,
    kbDefaultSchedule,
  }
}

/**
 * 获取指定页面的调度规则
 */
export function usePageSchedule(schedules: WebScheduleItem[], selectedPageId: string): WebScheduleItem | undefined {
  return schedules.find(item => item.scope_level === 'page_override' && item.kb_web_page_id === selectedPageId)
}
