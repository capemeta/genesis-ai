/**
 * 删除页面确认弹窗
 */

import { Loader2 } from 'lucide-react'
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
import type { WebPageItem } from '@/lib/api/web-sync'

export interface DeletePageDialogProps {
  deletingPage: WebPageItem | null
  onOpenChange: (open: boolean) => void
  isPending: boolean
  onDelete: (pageItem: WebPageItem) => void
}

export function DeletePageDialog({
  deletingPage,
  onOpenChange,
  isPending,
  onDelete,
}: DeletePageDialogProps) {
  return (
    <AlertDialog open={Boolean(deletingPage)} onOpenChange={open => !open && onOpenChange(false)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>确认删除网页页面？</AlertDialogTitle>
          <AlertDialogDescription>
            删除后将移除该页面在当前知识库中的关联数据（含同步记录与分块结果），且不可恢复。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>取消</AlertDialogCancel>
          <AlertDialogAction
            disabled={!deletingPage || isPending}
            onClick={event => {
              event.preventDefault()
              if (deletingPage) {
                onDelete(deletingPage)
              }
            }}
          >
            {isPending ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            删除
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
