/**
 * 格式化工具函数
 */

import {
  WEB_PAGE_SYNC_STATUS_LABELS,
  WEB_PAGE_SYNC_STATUS_CLASSES,
  RUN_STATUS_LABELS,
  FETCH_MODE_LABELS,
} from '../constants'

/**
 * 格式化时间字符串
 */
export function formatTime(dateString?: string | null): string {
  if (!dateString) return '-'
  const value = new Date(dateString)
  if (Number.isNaN(value.getTime())) return '-'
  return value.toLocaleString('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * 将绝对时间点按指定时区拆分为 YYYY-MM-DD / HH:MM。
 * 这里固定按中国时区格式化，避免 once 规则混用 UTC 日期和本地时间导致跨天偏移。
 */
export function formatDateTimeForTimezone(
  date: Date,
  timezone: string
): { runDate: string; runTime: string } {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)

  const getPart = (type: Intl.DateTimeFormatPartTypes) => parts.find(part => part.type === type)?.value || ''

  return {
    runDate: `${getPart('year')}-${getPart('month')}-${getPart('day')}`,
    runTime: `${getPart('hour')}:${getPart('minute')}`,
  }
}

/**
 * 格式化网页同步状态为中文
 */
export function formatWebPageSyncStatus(status?: string | null): string {
  return WEB_PAGE_SYNC_STATUS_LABELS[String(status || '').toLowerCase()] || String(status || '-')
}

/**
 * 获取网页同步状态对应的 Badge 样式类名
 */
export function getWebPageSyncStatusClass(status?: string | null): string {
  return WEB_PAGE_SYNC_STATUS_CLASSES[String(status || '').toLowerCase()] || 'bg-slate-100 text-slate-600 border-none shadow-none'
}

/**
 * 格式化运行状态为中文
 */
export function formatRunStatus(status?: string | null): string {
  return RUN_STATUS_LABELS[String(status || '').toLowerCase()] || String(status || '-')
}

/**
 * 格式化抓取模式为中文
 */
export function formatFetchMode(fetchMode?: string | null): string {
  return FETCH_MODE_LABELS[String(fetchMode || '').toLowerCase()] || '自动回退'
}
