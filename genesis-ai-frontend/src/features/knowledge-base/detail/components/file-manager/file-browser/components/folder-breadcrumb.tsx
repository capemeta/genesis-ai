/**
 * 文件夹面包屑导航组件
 * 显示当前文件夹的完整路径，支持点击跳转
 */
import { ChevronRight, Folder as FolderIcon } from 'lucide-react'
import type { Folder } from '@/lib/api/folder.types'
import { cn } from '@/lib/utils'

interface FolderBreadcrumbProps {
  folderPath: Folder[]
  onNavigate: (folderId: string | null) => void
  className?: string
}

export function FolderBreadcrumb({ folderPath, onNavigate, className }: FolderBreadcrumbProps) {
  if (folderPath.length === 0) {
    return null
  }

  return (
    <nav
      className={cn(
        'flex items-center gap-1.5 text-sm overflow-x-auto pb-1',
        'scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent',
        className
      )}
      aria-label='文件夹路径'
    >
      {/* 根目录 */}
      <button
        onClick={() => onNavigate(null)}
        className='flex items-center gap-1.5 px-2.5 py-1.5 rounded-md hover:bg-accent transition-colors text-muted-foreground hover:text-foreground flex-shrink-0 group'
        aria-label='返回根目录'
      >
        <FolderIcon className='h-4 w-4 text-blue-600 dark:text-blue-400 group-hover:scale-110 transition-transform' />
        <span className='font-medium'>根目录</span>
      </button>

      {/* 路径分隔符和文件夹 */}
      {folderPath.map((folder, index) => {
        const isLast = index === folderPath.length - 1
        return (
          <div key={folder.id} className='flex items-center gap-1.5 flex-shrink-0'>
            <ChevronRight className='h-4 w-4 text-muted-foreground/60' aria-hidden='true' />
            <button
              onClick={() => !isLast && onNavigate(folder.id)}
              className={cn(
                'px-2.5 py-1.5 rounded-md transition-all',
                isLast
                  ? 'bg-accent text-foreground font-semibold cursor-default shadow-sm'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground hover:shadow-sm'
              )}
              disabled={isLast}
              aria-current={isLast ? 'page' : undefined}
              title={folder.summary || folder.name}
            >
              <span className='max-w-[200px] truncate inline-block align-bottom'>
                {folder.name}
              </span>
            </button>
          </div>
        )
      })}
    </nav>
  )
}
