/**
 * 确认对话框组件
 * 
 * 用于需要用户确认的操作（如删除）
 */
import { Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { buttonVariants } from '@/components/ui/button'

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  desc?: ReactNode
  onConfirm?: () => void
  handleConfirm?: () => void
  loading?: boolean
  disabled?: boolean
  confirmText?: string
  cancelText?: string
  cancelBtnText?: string
  variant?: 'default' | 'destructive'
  destructive?: boolean
  className?: string
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  desc,
  onConfirm,
  handleConfirm,
  loading = false,
  disabled = false,
  confirmText = '确认',
  cancelText = '取消',
  cancelBtnText,
  variant = 'destructive',
  destructive = false,
  className,
}: ConfirmDialogProps) {
  const resolvedDescription = description ?? desc ?? ''
  const resolvedCancelText = cancelBtnText ?? cancelText
  const isDestructive = variant === 'destructive' || destructive
  const confirmHandler = onConfirm ?? handleConfirm

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className={className}>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className='text-sm text-muted-foreground'>{resolvedDescription}</div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>{resolvedCancelText}</AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault()
              if (typeof confirmHandler === 'function') {
                confirmHandler()
              }
            }}
            disabled={loading || disabled || typeof confirmHandler !== 'function'}
            className={isDestructive ? buttonVariants({ variant: 'destructive' }) : undefined}
          >
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
