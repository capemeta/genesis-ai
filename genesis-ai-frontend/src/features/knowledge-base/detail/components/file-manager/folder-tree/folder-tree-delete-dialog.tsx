/**
 * 删除文件夹确认对话框
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
import type { FolderTreeNode } from '@/lib/api/folder.types'

interface FolderTreeDeleteDialogProps {
  open: boolean
  folder: FolderTreeNode | null
  isDeleting: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

export function FolderTreeDeleteDialog({
  open,
  folder,
  isDeleting,
  onOpenChange,
  onConfirm,
}: FolderTreeDeleteDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>确认删除</AlertDialogTitle>
          <AlertDialogDescription className="space-y-3">
            <p>确定要删除文件夹 "{folder?.name}" 吗？</p>

            {folder?.children && folder.children.length > 0 && (
              <div className="p-3 bg-muted rounded-md">
                <p className="text-sm font-medium mb-1">
                  此文件夹包含 {folder.children.length} 个子文件夹
                </p>
                <p className="text-sm text-muted-foreground">将同时删除所有子文件夹</p>
              </div>
            )}

            <div className="p-3 bg-blue-50 dark:bg-blue-950/20 rounded-md border border-blue-200 dark:border-blue-800">
              <p className="text-sm text-blue-600 dark:text-blue-400">
                💡 提示：只能删除空文件夹。如果文件夹中有文档，请先删除文档。
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>取消</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isDeleting}
            className="bg-destructive hover:bg-destructive/90"
          >
            {isDeleting ? '删除中...' : '删除'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
