import { useEffect, useMemo, useState } from 'react'
import { Bot, Loader2, Plus, Workflow } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type {
  ChatBootstrapData,
  ChatCreateSpaceFormValues,
  ChatEntrypointType,
} from '@/features/chat/types/chat'

interface CreateChatSpaceDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  bootstrap?: ChatBootstrapData
  onSubmit: (values: ChatCreateSpaceFormValues) => void
  isSubmitting?: boolean
}

const EMPTY_VALUE = '__none__'

/** 浅色下主题 primary 偏深，与首页 Hero 一致使用品牌蓝作为主操作色 */
const DIALOG_PRIMARY_BTN =
  'bg-[#1D4ED8] text-white shadow-sm shadow-blue-200/70 hover:bg-[#1E40AF] dark:bg-primary dark:text-primary-foreground dark:shadow-none dark:hover:bg-primary/90'

/** 与首页 Hero 次要按钮一致的浅底描边样式 */
const DIALOG_SECONDARY_BTN =
  'border-[#BFDBFE] bg-white text-[#1E3A8A] hover:border-[#93C5FD] hover:bg-[#F8FAFF] dark:border-border dark:bg-background dark:text-foreground dark:hover:bg-accent/40'

const INITIAL_VALUES: ChatCreateSpaceFormValues = {
  name: '',
  description: '',
  entrypointType: 'assistant',
  workflowId: '',
}

export function CreateChatSpaceDialog({
  open,
  onOpenChange,
  bootstrap,
  onSubmit,
  isSubmitting = false,
}: CreateChatSpaceDialogProps) {
  const [formValues, setFormValues] = useState<ChatCreateSpaceFormValues>(INITIAL_VALUES)

  useEffect(() => {
    if (!open) {
      setFormValues(INITIAL_VALUES)
    }
  }, [open])

  const hasWorkflowOptions = (bootstrap?.workflows || []).length > 0

  const entrypointOptions = useMemo(
    () =>
      [
        {
          value: 'assistant' as ChatEntrypointType,
          label: '自由对话',
          description: '像平时聊天一样提问；若关联了资料库，会优先从资料里找答案',
          icon: Bot,
          disabled: false,
          badge: '',
        },
        hasWorkflowOptions
          ? {
              value: 'workflow' as ChatEntrypointType,
              label: '按流程办理',
              description: '一步步完成事项，适合审批、分步填报等有固定环节的工作',
              icon: Workflow,
              disabled: false,
              badge: '',
            }
          : {
              value: 'workflow' as ChatEntrypointType,
              label: '按流程办理',
              description: '流程入口需要先配置工作流后才能启用',
              icon: Workflow,
              disabled: true,
              badge: '需先配置',
            },
        {
          value: 'agent' as ChatEntrypointType,
          label: '智能体协作',
          description: '面向更复杂的多工具、多步骤任务处理，后续会接入',
          icon: Bot,
          disabled: true,
          badge: '敬请期待',
        },
      ].filter(Boolean),
    [hasWorkflowOptions]
  )

  const handleSubmit = () => {
    if (!formValues.name.trim()) {
      return
    }

    onSubmit({
      ...formValues,
      name: formValues.name.trim(),
      description: formValues.description.trim(),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-2xl max-h-[min(90vh,720px)] gap-0 overflow-hidden border-[#BFDBFE]/50 bg-gradient-to-b from-[#F5FAFF] via-white to-white p-0 dark:border-border dark:from-background dark:via-background dark:to-background'>
        <div className='max-h-[min(90vh,720px)] overflow-y-auto px-6 pt-6 pr-12 sm:pr-14'>
          <DialogHeader>
            <DialogTitle className='flex items-center gap-2 text-xl font-semibold tracking-tight'>
              <span className='flex h-9 w-9 items-center justify-center rounded-lg bg-[#DBEAFE] text-[#1D4ED8] dark:bg-primary/15 dark:text-primary'>
                <Plus className='h-5 w-5' />
              </span>
              新建聊天空间
            </DialogTitle>
            <DialogDescription>
              创建后进入空间，您还可以进一步配置核心模型、资料库范围及检索等参数。
            </DialogDescription>
          </DialogHeader>

          <div className='space-y-5 py-5'>
            <div className='space-y-2'>
              <Label htmlFor='chat-space-name'>空间名称</Label>
              <Input
                id='chat-space-name'
                value={formValues.name}
                onChange={(event) =>
                  setFormValues((current) => ({ ...current, name: event.target.value }))
                }
                placeholder='例如：Q4 财务分析'
                className='border-[#BFDBFE]/80 bg-white focus-visible:border-[#93C5FD] focus-visible:ring-blue-500/25 dark:border-input dark:bg-background'
              />
            </div>

            <div className='space-y-2'>
              <Label htmlFor='chat-space-description'>空间描述（可选）</Label>
              <Textarea
                id='chat-space-description'
                value={formValues.description}
                onChange={(event) =>
                  setFormValues((current) => ({ ...current, description: event.target.value }))
                }
                placeholder='简要说明用途，便于在列表中区分不同空间'
                rows={3}
                className='resize-none border-[#BFDBFE]/80 bg-white focus-visible:border-[#93C5FD] focus-visible:ring-blue-500/25 dark:border-input dark:bg-background'
              />
            </div>

            <div className='space-y-2'>
              <Label>入口方式</Label>
              <div className='grid gap-2'>
                {entrypointOptions.map((option) => {
                  const Icon = option.icon
                  const isActive = formValues.entrypointType === option.value

                  return (
                    <button
                      key={option.value}
                      type='button'
                      className={cn(
                        'group rounded-xl border p-3 text-left transition-colors',
                        option.disabled && 'cursor-not-allowed border-dashed opacity-60',
                        !option.disabled &&
                          isActive &&
                          'border-[#93C5FD] bg-[#EFF6FF] shadow-sm dark:border-primary dark:bg-primary/10',
                        !option.disabled &&
                          !isActive &&
                          'border-[#BFDBFE]/60 bg-white hover:border-[#93C5FD] hover:bg-[#F0F9FF] dark:border-border/60 dark:bg-background dark:hover:bg-accent/30'
                      )}
                      disabled={option.disabled}
                      onClick={() => {
                        if (option.disabled) return
                        setFormValues((current) => ({
                          ...current,
                          entrypointType: option.value,
                          workflowId: option.value === 'workflow' ? current.workflowId : '',
                        }))
                      }}
                    >
                      <div className='flex items-start gap-3'>
                        <div
                          className={cn(
                            'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors',
                            option.disabled && 'bg-[#EFF6FF]/90 text-slate-400 dark:bg-blue-950/25 dark:text-slate-500',
                            !option.disabled &&
                              isActive &&
                              'bg-[#1D4ED8] text-white dark:bg-primary dark:text-primary-foreground',
                            !option.disabled &&
                              !isActive &&
                              'bg-[#DBEAFE] text-[#1D4ED8] group-hover:bg-[#1D4ED8] group-hover:text-white dark:bg-blue-950/35 dark:text-blue-300 dark:group-hover:bg-primary dark:group-hover:text-primary-foreground'
                          )}
                        >
                          <Icon className='h-4 w-4' />
                        </div>
                        <div className='min-w-0 flex-1 space-y-1'>
                          <div className='flex flex-wrap items-center gap-2'>
                            <span className='text-sm font-medium'>{option.label}</span>
                            {option.badge ? (
                              <Badge
                                variant='outline'
                                className='border-[#BFDBFE] bg-[#F8FAFF] text-[10px] font-normal text-[#1E3A8A] dark:border-border dark:bg-background dark:text-slate-400'
                              >
                                {option.badge}
                              </Badge>
                            ) : null}
                          </div>
                          <p className='text-xs leading-relaxed text-muted-foreground'>
                            {option.description}
                          </p>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            {formValues.entrypointType === 'workflow' ? (
              <div className='space-y-2 rounded-xl border border-[#BFDBFE]/80 bg-[#FAFCFF] p-4 dark:border-border dark:bg-background'>
                <Label>选用工作流</Label>
                <Select
                  value={formValues.workflowId || EMPTY_VALUE}
                  onValueChange={(value) =>
                    setFormValues((current) => ({
                      ...current,
                      workflowId: value === EMPTY_VALUE ? '' : value,
                    }))
                  }
                >
                  <SelectTrigger className='border-[#BFDBFE]/80 bg-white dark:border-input dark:bg-background'>
                    <SelectValue placeholder='请选择流程' />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={EMPTY_VALUE}>暂不绑定</SelectItem>
                    {(bootstrap?.workflows || []).map((workflow) => (
                      <SelectItem key={workflow.id} value={workflow.id}>
                        {workflow.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
          </div>
        </div>

        <DialogFooter className='border-t border-[#BFDBFE]/50 bg-white px-6 py-4 sm:justify-end dark:border-border dark:bg-background'>
          <Button
            variant='outline'
            className={cn(DIALOG_SECONDARY_BTN)}
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            取消
          </Button>
          <Button
            className={cn(DIALOG_PRIMARY_BTN)}
            onClick={handleSubmit}
            disabled={isSubmitting || !formValues.name.trim()}
          >
            {isSubmitting ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : null}
            {isSubmitting ? '创建中…' : '确认并创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}


