import { useEffect, useState } from 'react'
import { Loader2, SquarePen } from 'lucide-react'
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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { ChatSpace } from '@/features/chat/types/chat'

interface EditChatSpaceDialogProps {
  open: boolean
  space?: ChatSpace
  isSubmitting?: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (values: { name: string; description: string }) => Promise<void> | void
}

export function EditChatSpaceDialog({
  open,
  space,
  isSubmitting = false,
  onOpenChange,
  onSubmit,
}: EditChatSpaceDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (open) {
      setName(space?.name || '')
      setDescription(space?.description || '')
    }
  }, [open, space?.id, space?.name, space?.description])

  const trimmedName = name.trim()
  const trimmedDescription = description.trim()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-xl'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            <SquarePen className='h-4 w-4 text-primary' />
            编辑聊天空间
          </DialogTitle>
          <DialogDescription>
            改个更贴切的名字或补充说明，方便您在列表里一眼认出这个空间。
          </DialogDescription>
        </DialogHeader>

        <div className='space-y-5'>
          <div className='space-y-2'>
            <Label htmlFor='edit-chat-space-name'>空间名称</Label>
            <Input
              id='edit-chat-space-name'
              value={name}
              maxLength={255}
              placeholder='请输入空间名称'
              onChange={(event) => setName(event.target.value)}
            />
          </div>

          <div className='space-y-2'>
            <Label htmlFor='edit-chat-space-description'>空间描述</Label>
            <Textarea
              id='edit-chat-space-description'
              value={description}
              rows={4}
              placeholder='可选。简要说明这个空间主要做什么'
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant='outline' onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            取消
          </Button>
          <Button
            onClick={() => void onSubmit({ name: trimmedName, description: trimmedDescription })}
            disabled={!trimmedName || isSubmitting}
          >
            {isSubmitting ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : null}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
