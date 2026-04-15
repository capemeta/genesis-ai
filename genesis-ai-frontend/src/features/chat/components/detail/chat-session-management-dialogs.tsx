import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { getSessionDisplayTitle } from '@/features/chat/utils/chat-format'
import type { ChatSession } from '@/features/chat/types/chat'

interface ChatSessionRenameDialogProps {
  open: boolean
  session?: ChatSession | null
  isSubmitting?: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (title: string) => Promise<void> | void
}

export function ChatSessionRenameDialog({
  open,
  session,
  isSubmitting = false,
  onOpenChange,
  onConfirm,
}: ChatSessionRenameDialogProps) {
  const [title, setTitle] = useState('')

  useEffect(() => {
    if (open) {
      setTitle(session?.title?.trim() || '')
    }
  }, [open, session?.id, session?.title])

  const trimmedTitle = title.trim()
  const canSubmit = trimmedTitle.length > 0 && trimmedTitle.length <= 255
  const currentTitle = session ? getSessionDisplayTitle(session) : '当前会话'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>重命名会话</DialogTitle>
          <DialogDescription>
            修改后会立即同步到左侧会话列表与当前详情页标题。
          </DialogDescription>
        </DialogHeader>

        <div className='space-y-2'>
          <div className='text-sm font-medium'>会话标题</div>
          <Input
            value={title}
            maxLength={255}
            placeholder='请输入会话标题'
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && canSubmit && !isSubmitting) {
                event.preventDefault()
                void onConfirm(trimmedTitle)
              }
            }}
          />
          <div className='flex items-center justify-between text-xs text-muted-foreground'>
            <span>当前名称：{currentTitle}</span>
            <span>{trimmedTitle.length}/255</span>
          </div>
        </div>

        <DialogFooter>
          <Button variant='outline' onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            取消
          </Button>
          <Button
            onClick={() => void onConfirm(trimmedTitle)}
            disabled={!canSubmit || isSubmitting}
          >
            {isSubmitting ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : null}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface ChatSessionArchiveDialogProps {
  open: boolean
  session?: ChatSession | null
  isSubmitting?: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

export function ChatSessionArchiveDialog({
  open,
  session,
  isSubmitting = false,
  onOpenChange,
  onConfirm,
}: ChatSessionArchiveDialogProps) {
  const isArchived = session?.status === 'archived'
  const sessionTitle = session ? getSessionDisplayTitle(session) : '当前会话'

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title={isArchived ? '恢复会话' : '归档会话'}
      description={
        isArchived
          ? `确认将“${sessionTitle}”恢复到当前会话列表吗？恢复后可以继续在活跃列表中管理它。`
          : `确认归档“${sessionTitle}”吗？归档后会移动到左侧“已归档”区域，但仍可继续查看。`
      }
      onConfirm={onConfirm}
      loading={isSubmitting}
      confirmText={isArchived ? '恢复会话' : '确认归档'}
      variant='default'
    />
  )
}

interface ChatSessionDeleteDialogProps {
  open: boolean
  session?: ChatSession | null
  isSubmitting?: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

export function ChatSessionDeleteDialog({
  open,
  session,
  isSubmitting = false,
  onOpenChange,
  onConfirm,
}: ChatSessionDeleteDialogProps) {
  const sessionTitle = session ? getSessionDisplayTitle(session) : '当前会话'

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title='删除会话'
      description={`确认删除“${sessionTitle}”吗？删除后该会话会从当前空间列表中移除，且本次操作不可撤销。`}
      onConfirm={onConfirm}
      loading={isSubmitting}
      confirmText='确认删除'
      variant='destructive'
    />
  )
}

interface ClearChatMessagesDialogProps {
  open: boolean
  session?: ChatSession | null
  isSubmitting?: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

/** 清空当前会话聊天记录（保留会话与配置） */
export function ClearChatMessagesDialog({
  open,
  session,
  isSubmitting = false,
  onOpenChange,
  onConfirm,
}: ClearChatMessagesDialogProps) {
  const sessionTitle = session ? getSessionDisplayTitle(session) : '当前会话'

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title='清空聊天记录'
      description={`确认清空“${sessionTitle}”的全部消息吗？清空后无法恢复，会话标题与配置仍会保留。`}
      onConfirm={onConfirm}
      loading={isSubmitting}
      confirmText='确认清空'
      variant='destructive'
    />
  )
}
