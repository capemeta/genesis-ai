import { useMemo } from 'react'
import { CronExpressionParser } from 'cron-parser'
import cron from 'cron-validate'
import cronstrue from 'cronstrue'
import 'cronstrue/locales/zh_CN'
import { Clock3, Loader2, Repeat2, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

/** 通用调度类型：供不同知识库/连接器复用。 */
export type ScheduleType = 'manual' | 'interval' | 'daily' | 'cron'

/** 通用调度表单状态：尽量保持最小闭包，便于上层页面直接管理。 */
export interface ScheduleFormState {
  scheduleType: ScheduleType
  intervalValue: number
  intervalUnit: 'minute' | 'hour' | 'day'
  runTime: string
  cronExpr: string
  isEnabled: boolean
  /** 间隔模式是否为一次性执行（勾选后仅触发一次） */
  intervalOnce?: boolean
}

interface ScheduleRuleBuilderProps {
  title: string
  description: string
  form: ScheduleFormState
  onChange: (next: ScheduleFormState) => void
  onSave: () => void
  saveLabel: string
  nextTriggerAt?: string | null
  /** 已存储的调度类型，用于标签展示（非表单临时值） */
  savedScheduleType?: ScheduleType
  saveDisabled?: boolean
  isSaving?: boolean
  className?: string
  secondaryActionLabel?: string
  onSecondaryAction?: () => void
  secondaryActionDisabled?: boolean
}

interface CronPreset {
  label: string
  expr: string
  hint: string
}

const CRON_PRESETS: CronPreset[] = [
  { label: '每 15 分钟', expr: '*/15 * * * *', hint: '适合高频轮询' },
  { label: '每小时', expr: '0 * * * *', hint: '整点执行一次' },
  { label: '每 6 小时', expr: '0 */6 * * *', hint: '适合普通站点' },
  { label: '每天 02:00', expr: '0 2 * * *', hint: '夜间低峰执行' },
  { label: '工作日 09:00', expr: '0 9 * * 1-5', hint: '适合业务日同步' },
]

function formatTime(dateString?: string | null): string {
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

function validateCronExpression(expression: string): { valid: boolean; message?: string } {
  const normalized = String(expression || '').trim()
  if (!normalized) {
    return { valid: false, message: '请输入 Cron 表达式' }
  }
  const result = cron(normalized, {
    preset: 'default',
    override: {
      useSeconds: false,
      useYears: false,
      useAliases: true,
      useBlankDay: true,
      allowOnlyOneBlankDayField: false,
    },
  })
  if (result.isValid()) {
    return { valid: true }
  }
  return { valid: false, message: result.getError().join('；') || 'Cron 表达式不合法' }
}

function describeCronExpression(expression: string): string {
  const normalized = String(expression || '').trim()
  if (!normalized) return '请输入 Cron 表达式'

  try {
    return cronstrue.toString(normalized, {
      locale: 'zh_CN',
      use24HourTimeFormat: true,
      throwExceptionOnParseError: true,
    })
  } catch {
    return '自定义 Cron 规则'
  }
}

function describeSchedule(form: ScheduleFormState): string {
  if (form.scheduleType === 'manual') return '手动触发，人工确认后再执行'
  if (form.scheduleType === 'interval') {
    const timeDesc = `${Math.max(1, form.intervalValue)} ${formatIntervalUnit(form.intervalUnit)}`
    return form.intervalOnce ? `延迟 ${timeDesc}后执行一次` : `每隔 ${timeDesc}重复执行`
  }
  if (form.scheduleType === 'daily') return `每天 ${form.runTime || '02:00'} 执行一次`
  return describeCronExpression(form.cronExpr)
}

function getManualHint(): string {
  return '仅在人工点击「立即同步」后执行，不会自动创建定时任务'
}

function formatIntervalUnit(unit: ScheduleFormState['intervalUnit']): string {
  if (unit === 'minute') return '分钟'
  if (unit === 'hour') return '小时'
  return '天'
}

function getPreviewAccent(scheduleType: ScheduleType): string {
  if (scheduleType === 'manual') return 'from-slate-100 to-slate-50'
  if (scheduleType === 'interval') return 'from-sky-100 to-blue-50'
  if (scheduleType === 'daily') return 'from-amber-100 to-orange-50'
  return 'from-blue-100 to-indigo-50'
}

/**
 * 通用调度规则编辑器。
 * 当前已在 web 知识库默认调度、页面级覆盖中使用，后续 QA / 表格 / 连接器也可直接复用。
 */
export function ScheduleRuleBuilder({
  title,
  description,
  form,
  onChange,
  onSave,
  saveLabel,
  nextTriggerAt,
  savedScheduleType,
  saveDisabled,
  isSaving,
  className,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionDisabled,
}: ScheduleRuleBuilderProps) {
  const cronValidation = validateCronExpression(form.cronExpr)
  const isCronInvalid = form.scheduleType === 'cron' && !cronValidation.valid
  const isSaveDisabled = Boolean(saveDisabled || isSaving || isCronInvalid)
  const upcomingTriggers = useMemo(() => {
    try {
      let expression = ''
      if (form.scheduleType === 'daily') {
        const [hour, minute] = String(form.runTime || '02:00').split(':')
        expression = `${minute || '00'} ${hour || '02'} * * *`
      } else if (form.scheduleType === 'cron' && cronValidation.valid) {
        expression = String(form.cronExpr || '').trim()
      } else if (form.scheduleType === 'interval') {
        // 间隔模式：基于当前时间计算未来触发时间
        const now = new Date()
        const intervalMs = Math.max(1, form.intervalValue) * (
          form.intervalUnit === 'hour' ? 3600 * 1000 :
          form.intervalUnit === 'day' ? 86400 * 1000 :
          60 * 1000
        )
        const count = form.intervalOnce ? 1 : 3
        return [1, 2, 3].slice(0, count).map(i => {
          const next = new Date(now.getTime() + intervalMs * i)
          return formatTime(next.toISOString())
        })
      }

      if (!expression) return []

      const interval = CronExpressionParser.parse(expression, {
        currentDate: new Date(),
        tz: 'Asia/Shanghai',
      })

      return interval.take(3).map(item => formatTime(item.toDate().toISOString()))
    } catch {
      return []
    }
  }, [cronValidation.valid, form.cronExpr, form.runTime, form.scheduleType, form.intervalValue, form.intervalUnit])

  return (
    <section className={cn('rounded-2xl border border-slate-200 bg-white shadow-sm', className)}>
      <div className='border-b border-slate-200 bg-gradient-to-r from-blue-50/50 via-indigo-50/30 to-white px-4 py-3'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div className='flex flex-wrap items-center gap-2'>
            <h3 className='text-sm font-semibold text-slate-800'>{title}</h3>
            {/* 规则来源标签 */}
            <span className={cn(
              'inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium shadow-sm',
              nextTriggerAt ? 'bg-amber-100 text-amber-700' : 'bg-indigo-100 text-indigo-700'
            )}>
              {nextTriggerAt ? '独立规则' : '继承知识库配置'}
            </span>
            {/* 下次触发标签 */}
            <span className={cn(
              'inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium shadow-sm',
              savedScheduleType === 'manual'
                ? 'bg-blue-100 text-blue-700'
                : nextTriggerAt
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-slate-100 text-slate-500'
            )}>
              {savedScheduleType === 'manual' ? '手动触发' : `下次触发：${nextTriggerAt ? formatTime(nextTriggerAt) : '-'}`}
            </span>
            <p className='mt-1 w-full text-xs leading-relaxed text-slate-500'>{description}</p>
          </div>
          <div className='flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 shadow-sm'>
            <span className={cn('text-xs font-medium', form.isEnabled ? 'text-emerald-600' : 'text-slate-400')}>
              {form.isEnabled ? '已启用' : '已停用'}
            </span>
            <Switch checked={form.isEnabled} onCheckedChange={checked => onChange({ ...form, isEnabled: checked })} />
          </div>
        </div>
      </div>

      <div className='grid gap-4 p-4 lg:grid-cols-[minmax(0,1.5fr)_280px]'>
        <div className='space-y-4'>
          <Tabs
            value={form.scheduleType}
            onValueChange={value => onChange({
              ...form,
              scheduleType: value as ScheduleType,
              // “延迟执行一次”仅对间隔模式生效，切走后必须立即清空，避免把 manual/daily 误提交成 once。
              intervalOnce: value === 'interval' ? (form.intervalOnce || false) : false,
            })}
          >
            <TabsList className='grid h-auto w-full grid-cols-4 rounded-xl bg-slate-100 p-1'>
              <TabsTrigger value='manual' className='h-9 rounded-lg text-xs'>手动</TabsTrigger>
              <TabsTrigger value='interval' className='h-9 rounded-lg text-xs'>间隔</TabsTrigger>
              <TabsTrigger value='daily' className='h-9 rounded-lg text-xs'>每日</TabsTrigger>
              <TabsTrigger value='cron' className='h-9 rounded-lg text-xs'>Cron</TabsTrigger>
            </TabsList>

            <TabsContent value='manual' className='mt-4'>
              <div className='rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4 text-sm text-slate-600'>
                手动模式不会自动创建定时任务，适合仅在人工确认后再执行同步。
              </div>
            </TabsContent>

            <TabsContent value='interval' className='mt-4'>
              <div className='space-y-3'>
                <div className='grid gap-3 sm:grid-cols-[120px_160px_1fr]'>
                  <div className='space-y-1.5'>
                    <Label className='text-xs font-medium text-slate-600'>
                      {form.intervalOnce ? '延迟时间' : '间隔时间'}
                    </Label>
                    <Input
                      className='h-10 border-slate-200 bg-white shadow-sm'
                      type='number'
                      min={1}
                      value={form.intervalValue}
                      onChange={event => onChange({ ...form, intervalValue: Number(event.target.value || 1) })}
                    />
                  </div>
                  <div className='space-y-1.5'>
                    <Label className='text-xs font-medium text-slate-600'>单位</Label>
                    <Select value={form.intervalUnit} onValueChange={value => onChange({ ...form, intervalUnit: value as ScheduleFormState['intervalUnit'] })}>
                      <SelectTrigger className='h-10 border-slate-200 bg-white shadow-sm'>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value='minute'>分钟</SelectItem>
                        <SelectItem value='hour'>小时</SelectItem>
                        <SelectItem value='day'>天</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className='flex items-end rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2 text-xs text-slate-500'>
                    推荐从 30 分钟或 1 小时开始，避免对站点造成过密抓取压力。
                  </div>
                </div>
                {/* 延迟执行开关 */}
                <div className='flex items-center gap-2.5 rounded-lg border border-dashed border-slate-300 bg-amber-50/50 p-3'>
                  <Switch
                    id='interval-once'
                    checked={form.intervalOnce || false}
                    onCheckedChange={checked => onChange({ ...form, intervalOnce: checked })}
                  />
                  <div className='flex-1'>
                    <Label htmlFor='interval-once' className='cursor-pointer text-sm font-medium text-slate-700'>
                      延迟执行一次
                    </Label>
                    <p className='mt-0.5 text-xs text-slate-500'>
                      {form.intervalOnce
                        ? '开启后，仅在指定延迟时间后执行一次'
                        : '关闭则周期性重复执行'
                      }
                    </p>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value='daily' className='mt-4'>
              <div className='grid gap-3 sm:grid-cols-[180px_1fr]'>
                <div className='space-y-1.5'>
                  <Label className='text-xs font-medium text-slate-600'>每日执行时间</Label>
                  <Input
                    className='h-10 border-slate-200 bg-white shadow-sm'
                    type='time'
                    value={form.runTime}
                    onChange={event => onChange({ ...form, runTime: event.target.value })}
                  />
                </div>
                <div className='flex items-end rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2 text-xs text-slate-500'>
                  适合固定时段批量同步，建议选业务低峰时段，例如凌晨或午间。
                </div>
              </div>
            </TabsContent>

            <TabsContent value='cron' className='mt-4 space-y-3'>
              <div className='space-y-1.5'>
                <Label className='text-xs font-medium text-slate-600'>Cron 表达式</Label>
                <Input
                  className={cn(
                    'h-10 border-slate-200 bg-white font-mono text-sm shadow-sm',
                    isCronInvalid && 'border-red-300 focus-visible:ring-red-500'
                  )}
                  placeholder='例如：0 */6 * * *'
                  value={form.cronExpr}
                  onChange={event => onChange({ ...form, cronExpr: event.target.value })}
                />
                <div className='flex flex-wrap items-center gap-2 text-[11px] text-slate-500'>
                  <span>格式：分 时 日 月 周</span>
                  {isCronInvalid ? <span className='font-medium text-red-500'>{cronValidation.message}</span> : <span>支持常用 5 段 Cron</span>}
                </div>
              </div>

              <div className='space-y-2'>
                <div className='flex items-center gap-2 text-xs font-medium text-slate-600'>
                  <Sparkles className='h-3.5 w-3.5 text-blue-500' />
                  常用模板
                </div>
                <div className='flex flex-wrap gap-2'>
                  {CRON_PRESETS.map(preset => {
                    const isActive = form.cronExpr.trim() === preset.expr
                    return (
                      <button
                        key={preset.expr}
                        type='button'
                        onClick={() => onChange({ ...form, scheduleType: 'cron', cronExpr: preset.expr })}
                        className={cn(
                          'rounded-lg border px-3 py-1.5 text-xs font-medium transition-all',
                          isActive
                            ? 'border-blue-400 bg-blue-500 text-white shadow-md shadow-blue-200'
                            : 'border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600'
                        )}
                      >
                        {preset.label}
                      </button>
                    )
                  })}
                </div>
                <div className={cn(
                  'text-[11px]',
                  form.cronExpr.trim() && !CRON_PRESETS.find(p => p.expr === form.cronExpr.trim()) ? 'text-blue-600 font-medium' : 'text-slate-500'
                )}>
                  {CRON_PRESETS.find(item => item.expr === form.cronExpr.trim())?.hint || (form.cronExpr.trim() ? '自定义表达式' : '选择模板或输入自定义表达式')}
                </div>
              </div>
            </TabsContent>
          </Tabs>

          <div className='flex flex-wrap items-center justify-end gap-2 rounded-xl border border-slate-200 bg-gradient-to-r from-slate-50 to-white px-4 py-3 shadow-sm'>
            <div className='flex flex-wrap items-center gap-2'>
              {secondaryActionLabel && onSecondaryAction && (
                <Button
                  type='button'
                  size='sm'
                  variant='outline'
                  className='border-slate-300 hover:border-slate-400 hover:bg-slate-50'
                  disabled={secondaryActionDisabled}
                  onClick={onSecondaryAction}
                >
                  {secondaryActionLabel}
                </Button>
              )}
              <Button
                size='sm'
                className={cn(
                  'shadow-sm',
                  isSaveDisabled ? 'bg-slate-400' : 'bg-blue-600 hover:bg-blue-700 shadow-blue-200'
                )}
                disabled={isSaveDisabled}
                onClick={onSave}
              >
                {isSaving ? (
                  <>
                    <Loader2 className='mr-1.5 h-3.5 w-3.5 animate-spin' />
                    保存中...
                  </>
                ) : saveLabel}
              </Button>
            </div>
          </div>
        </div>

        <aside className={cn('rounded-2xl border border-slate-200 bg-gradient-to-br p-4 shadow-sm', getPreviewAccent(form.scheduleType))}>
          <div className='flex items-center gap-2 text-slate-700'>
            <Repeat2 className='h-4 w-4 text-blue-600' />
            <span className='text-xs font-semibold'>规则预览</span>
          </div>
          <p className='mt-3 text-sm font-semibold leading-6 text-slate-800'>{describeSchedule(form)}</p>
          <div className='mt-4 flex flex-wrap gap-2'>
            <Badge variant='secondary' className='bg-white/80 text-slate-700 shadow-sm'>模式：{form.scheduleType === 'manual' ? '手动' : form.scheduleType === 'interval' ? '间隔' : form.scheduleType === 'daily' ? '每日' : 'Cron'}</Badge>
            <Badge variant='secondary' className={cn('shadow-sm', form.isEnabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600')}>{form.isEnabled ? '已启用' : '未启用'}</Badge>
          </div>
          <div className='mt-5 space-y-3 rounded-xl border border-white/70 bg-white/70 p-3 backdrop-blur-sm shadow-sm'>
            {upcomingTriggers.length > 0 && (
              <div className='space-y-1 text-xs text-slate-600'>
                <div className='flex items-center gap-1.5 font-medium text-slate-700'>
                  <Clock3 className='h-3.5 w-3.5' />
                  未来触发
                </div>
                {upcomingTriggers.map(item => (
                  <div key={item} className='rounded-lg border border-slate-200/70 bg-white/80 px-2.5 py-1.5 shadow-sm'>
                    {item}
                  </div>
                ))}
              </div>
            )}
            {form.scheduleType === 'cron' && (
              <div className={cn('text-xs leading-5', isCronInvalid ? 'text-red-600' : 'text-slate-600')}>
                {isCronInvalid ? '请先修正 Cron 表达式后再保存。' : '建议先从模板生成再调整。'}
              </div>
            )}
            {form.scheduleType === 'manual' && (
              <div className='rounded-lg border border-slate-200/70 bg-white/80 px-3 py-2 text-xs leading-relaxed text-slate-600 shadow-sm'>
                {getManualHint()}
              </div>
            )}
          </div>
        </aside>
      </div>
    </section>
  )
}

export default ScheduleRuleBuilder
