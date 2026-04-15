/**
 * 调度规则辅助函数
 */

import type { ScheduleFormState, ScheduleType } from '@/features/knowledge-base/detail/components/file-manager/file-browser/components/shared/schedule-rule-builder'
import type { WebScheduleCreateRequest, WebScheduleItem } from '@/lib/api/web-sync'
import { formatDateTimeForTimezone } from './formatters'

/**
 * 从后端调度记录转换为前端表单状态
 */
export function fromSchedule(schedule?: WebScheduleItem): ScheduleFormState {
  if (!schedule) {
    return {
      scheduleType: 'manual',
      intervalValue: 30,
      intervalUnit: 'minute',
      runTime: '02:00',
      cronExpr: '0 2 * * *',
      isEnabled: true,
      intervalOnce: false,
    }
  }
  // 兼容后端的 once 类型：interval 模式下通过 intervalOnce 字段控制
  const isOnce = schedule.schedule_type === 'once'
  return {
    scheduleType: isOnce ? 'interval' : (schedule.schedule_type as ScheduleType) || 'manual',
    intervalValue: schedule.interval_value || 30,
    intervalUnit: schedule.interval_unit || 'minute',
    runTime: schedule.run_time ? schedule.run_time.slice(0, 5) : '02:00',
    cronExpr: schedule.cron_expr || '0 2 * * *',
    isEnabled: schedule.is_enabled,
    intervalOnce: isOnce,
  }
}

/**
 * 判断页面级规则是否与知识库默认规则一致
 * 用于在保存时决定是删除页面级规则还是保存覆盖
 */
export function isScheduleFormSameAsKbDefault(form: ScheduleFormState, kbSchedule?: WebScheduleItem): boolean {
  const kbDefault = fromSchedule(kbSchedule)

  // 比较关键字段
  if (form.scheduleType !== kbDefault.scheduleType) return false
  if (form.isEnabled !== kbDefault.isEnabled) return false

  if (form.scheduleType === 'interval') {
    if (form.intervalValue !== kbDefault.intervalValue) return false
    if (form.intervalUnit !== kbDefault.intervalUnit) return false
    if (form.intervalOnce !== kbDefault.intervalOnce) return false
  }

  if (form.scheduleType === 'daily') {
    if (form.runTime !== kbDefault.runTime) return false
  }

  if (form.scheduleType === 'cron') {
    if (form.cronExpr !== kbDefault.cronExpr) return false
  }

  return true
}

/**
 * 构建调度规则请求载荷
 */
export function buildSchedulePayload(
  base: { kb_id: string; kb_web_page_id?: string | null; scope_level: 'kb_default' | 'page_override' },
  form: ScheduleFormState
): WebScheduleCreateRequest {
  const scheduleTimezone = 'Asia/Shanghai'
  // 只有“间隔”模式下勾选“延迟执行一次”时，才映射为后端的 once 类型。
  const effectiveType = form.scheduleType === 'interval' && form.intervalOnce ? 'once' : form.scheduleType
  const payload: WebScheduleCreateRequest = {
    ...base,
    schedule_type: effectiveType,
    timezone: scheduleTimezone,
    is_enabled: form.isEnabled,
  }
  if (form.scheduleType === 'interval') {
    payload.interval_value = form.intervalValue
    payload.interval_unit = form.intervalUnit

    // 延迟执行一次时，计算 run_date（当前时间 + 延迟时间）
    if (form.intervalOnce) {
      const now = new Date()
      const intervalMs = form.intervalValue * (
        form.intervalUnit === 'hour' ? 3600 * 1000 :
        form.intervalUnit === 'day' ? 86400 * 1000 :
        60 * 1000
      )
      const runDate = new Date(now.getTime() + intervalMs)
      const formatted = formatDateTimeForTimezone(runDate, scheduleTimezone)
      payload.run_date = formatted.runDate
      payload.run_time = formatted.runTime
    }
  }
  if (form.scheduleType === 'daily') {
    payload.run_time = `${form.runTime || '02:00'}:00`
  }
  if (form.scheduleType === 'cron') {
    payload.cron_expr = form.cronExpr.trim()
  }
  return payload
}
