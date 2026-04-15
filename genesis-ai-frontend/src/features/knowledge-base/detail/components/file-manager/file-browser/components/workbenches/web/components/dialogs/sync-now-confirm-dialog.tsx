/**
 * 立即同步确认弹窗
 */

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

export interface SyncNowConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  pageName?: string
  onConfirm: () => void
}

export function SyncNowConfirmDialog({
  open,
  onOpenChange,
  pageName,
  onConfirm,
}: SyncNowConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>确认立即同步？</AlertDialogTitle>
          <AlertDialogDescription>
            将立即抓取「{pageName}」的最新网页内容并重建切片索引，该操作会覆盖已有数据。请确认是否继续。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>
            确认同步
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
