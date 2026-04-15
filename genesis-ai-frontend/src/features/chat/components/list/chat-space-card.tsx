import { Link } from '@tanstack/react-router'
import { Archive, Bot, MoreHorizontal, Pin, Trash2, Workflow } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatRelativeTime, getSpaceSubtitle } from '@/features/chat/utils/chat-format'
import type { ChatSpace } from '@/features/chat/types/chat'

interface ChatSpaceCardProps {
  space: ChatSpace
  viewMode?: 'grid' | 'list'
  onArchive: (space: ChatSpace) => void
  onDelete: (space: ChatSpace) => void
}

export function ChatSpaceCard({
  space,
  viewMode = 'grid',
  onArchive,
  onDelete,
}: ChatSpaceCardProps) {
  const EntrypointIcon = space.entrypoint_type === 'workflow' ? Workflow : Bot

  if (viewMode === 'list') {
    return (
      <Link to='/chat/$chatId' params={{ chatId: space.id }} search={{ sessionId: undefined }}>
        <div className='flex items-center justify-between p-4 bg-background border rounded-xl hover:shadow-md transition-all group'>
          <div className='flex items-center gap-4'>
            <div className='flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600/10 text-blue-600 shadow-sm group-hover:scale-105 transition-transform'>
              <EntrypointIcon className='h-5 w-5' />
            </div>
            <div>
              <h3 className='font-semibold text-base group-hover:text-primary transition-colors'>{space.name}</h3>
              <p className='text-xs text-muted-foreground line-clamp-1 max-w-md'>{space.description || '暂无描述。'}</p>
            </div>
          </div>

          <div className='flex items-center gap-8'>
            <div className='hidden md:flex items-center gap-6'>
              <div className='flex flex-col items-center gap-0.5'>
                <span className='text-[10px] text-muted-foreground uppercase font-bold tracking-wider'>入口</span>
                <span className='text-sm font-semibold'>{getSpaceSubtitle(space)}</span>
              </div>
              <div className='flex flex-col items-center gap-0.5'>
                <span className='text-[10px] text-muted-foreground uppercase font-bold tracking-wider'>活跃</span>
                <span className='text-sm font-medium text-muted-foreground'>{formatRelativeTime(space.last_session_at || space.updated_at)}</span>
              </div>
              <div className='flex flex-col items-center gap-0.5'>
                <span className='text-[10px] text-muted-foreground uppercase font-bold tracking-wider'>置顶</span>
                <span className='text-sm font-semibold'>{space.is_pinned ? '是' : '否'}</span>
              </div>
            </div>

            <div className='flex items-center gap-3'>
              <Badge variant={space.status === 'active' ? 'secondary' : 'outline'} className='text-[10px] px-2 py-0'>
                {space.status === 'active' ? '活跃中' : '已归档'}
              </Badge>
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(event) => event.preventDefault()}>
                  <Button variant='ghost' size='icon' className='h-8 w-8'>
                    <MoreHorizontal className='h-4 w-4' />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align='end'>
                  <DropdownMenuItem onClick={() => onArchive(space)} className='flex items-center gap-2'>
                    <Archive className='h-3.5 w-3.5 opacity-60' />
                    <span>{space.status === 'archived' ? '恢复空间' : '归档空间'}</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem className='flex items-center gap-2 text-destructive focus:text-destructive' onClick={() => onDelete(space)}>
                    <Trash2 className='h-3.5 w-3.5' />
                    <span>删除空间</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </Link>
    )
  }

  return (
    <Link to='/chat/$chatId' params={{ chatId: space.id }} search={{ sessionId: undefined }}>
      <Card className='group h-full gap-0 border-muted/60 py-0 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg'>
        <CardHeader className='space-y-3 p-4'>
          <div className='flex items-start justify-between'>
            <div className='flex items-center gap-2.5'>
              <div className='flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600/10 text-blue-600 shadow-sm transition-transform group-hover:scale-105'>
                <EntrypointIcon className='h-4.5 w-4.5' />
              </div>
              {space.is_pinned ? (
                <Badge variant='secondary' className='gap-1 text-[10px]'>
                  <Pin className='h-3 w-3 fill-current' />
                  <span>置顶</span>
                </Badge>
              ) : null}
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild onClick={(event) => event.preventDefault()}>
                <Button variant='ghost' size='icon' className='h-7 w-7 -mt-1 -mr-1'>
                  <MoreHorizontal className='h-4 w-4' />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align='end'>
                <DropdownMenuItem onClick={() => onArchive(space)} className='flex items-center gap-2'>
                  <Archive className='h-3.5 w-3.5 opacity-60' />
                  <span>{space.status === 'archived' ? '恢复空间' : '归档空间'}</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className='flex items-center gap-2 text-destructive focus:text-destructive' onClick={() => onDelete(space)}>
                  <Trash2 className='h-3.5 w-3.5' />
                  <span>删除空间</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className='space-y-1'>
            <CardTitle className='line-clamp-1 text-base group-hover:text-primary transition-colors'>
              {space.name}
            </CardTitle>
            <p className='line-clamp-2 min-h-[32px] text-xs text-muted-foreground'>
              {space.description || '暂无描述。'}
            </p>
          </div>
        </CardHeader>

        <CardContent className='border-t border-border/60 px-4 pb-2 pt-0'>
          <div className='space-y-3 pt-3'>
            <div className='flex items-center justify-between text-[11px]'>
              <div className='text-muted-foreground'>
                入口：<span className='font-medium text-foreground'>{getSpaceSubtitle(space)}</span>
              </div>
              <div className='text-muted-foreground'>
                最近活跃：
                <span className='ml-1 font-medium text-foreground tabular-nums'>
                  {formatRelativeTime(space.last_session_at || space.updated_at)}
                </span>
              </div>
            </div>

            <div className='flex items-center justify-end'>
              <Badge variant={space.status === 'active' ? 'secondary' : 'outline'} className='text-[10px]'>
                {space.status === 'active' ? '活跃中' : '已归档'}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
