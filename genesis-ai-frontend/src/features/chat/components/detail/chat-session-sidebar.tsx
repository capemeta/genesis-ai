import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Archive, ArrowLeft, ChevronLeft, ChevronRight, MessageSquare, MoreHorizontal, Pin, Plus, RefreshCw, Search, SquarePen, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { formatRelativeTime, getSessionDisplayTitle } from '@/features/chat/utils/chat-format'
import type { ChatSession, ChatSpace } from '@/features/chat/types/chat'

interface ChatSessionSidebarProps {
  space?: ChatSpace
  sessions: ChatSession[]
  activeSessionId?: string
  onCreateSession: () => void
  onSelectSession: (sessionId: string) => void
  onRenameSession: (session: ChatSession) => void
  onTogglePinSession: (session: ChatSession) => void
  onArchiveSession: (session: ChatSession) => void
  onDeleteSession: (session: ChatSession) => void
  onRefreshActiveSessions?: () => void
  onRefreshArchivedSessions?: () => void
  isRefreshingActiveSessions?: boolean
  isRefreshingArchivedSessions?: boolean
  /** 编辑当前聊天空间（标题与说明放在侧栏，避免占用中间对话区） */
  onEditSpace?: () => void
  className?: string
}

export function ChatSessionSidebar({
  space,
  sessions,
  activeSessionId,
  onCreateSession,
  onSelectSession,
  onRenameSession,
  onTogglePinSession,
  onArchiveSession,
  onDeleteSession,
  onRefreshActiveSessions,
  onRefreshArchivedSessions,
  isRefreshingActiveSessions = false,
  isRefreshingArchivedSessions = false,
  onEditSpace,
  className,
}: ChatSessionSidebarProps) {
  const [section, setSection] = useState<'active' | 'archived'>('active')
  const [activePage, setActivePage] = useState(1)
  const [archivedPage, setArchivedPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const pageSize = 12
  const normalizedKeyword = keyword.trim().toLowerCase()
  const matchesKeyword = (session: ChatSession) => {
    if (!normalizedKeyword) {
      return true
    }
    const title = (session.title || '').toLowerCase()
    const summary = (session.summary || '').toLowerCase()
    return title.includes(normalizedKeyword) || summary.includes(normalizedKeyword)
  }
  const activeSessions = sessions.filter(
    (session) => session.status === 'active' && matchesKeyword(session)
  )
  const archivedSessions = sessions.filter(
    (session) => session.status === 'archived' && matchesKeyword(session)
  )
  const activeTotalPages = Math.max(1, Math.ceil(activeSessions.length / pageSize))
  const archivedTotalPages = Math.max(1, Math.ceil(archivedSessions.length / pageSize))

  useEffect(() => {
    setActivePage((current) => Math.min(current, activeTotalPages))
  }, [activeTotalPages])

  useEffect(() => {
    setArchivedPage((current) => Math.min(current, archivedTotalPages))
  }, [archivedTotalPages])

  useEffect(() => {
    if (section === 'archived' && archivedSessions.length === 0) {
      setSection('active')
    }
  }, [archivedSessions.length, section])

  useEffect(() => {
    setActivePage(1)
    setArchivedPage(1)
  }, [normalizedKeyword])

  const pagedActiveSessions = useMemo(
    () => activeSessions.slice((activePage - 1) * pageSize, activePage * pageSize),
    [activePage, activeSessions]
  )
  const pagedArchivedSessions = useMemo(
    () => archivedSessions.slice((archivedPage - 1) * pageSize, archivedPage * pageSize),
    [archivedPage, archivedSessions]
  )

  return (
    <aside className={cn('flex h-full min-h-0 w-full max-w-80 flex-col border-r bg-card', className)}>
      <div className='flex flex-col gap-5 p-5 pb-3'>
        {/* Header: Back + Title + Edit */}
        <div className='space-y-3'>
          <div className='flex items-center justify-between gap-2.5'>
            <div className='flex items-center gap-2.5 min-w-0 flex-1'>
              <Link to='/chat'>
                <Button variant='ghost' size='icon' className='h-8 w-8 shrink-0 rounded-lg bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors'>
                  <ArrowLeft className='h-3.5 w-3.5' />
                </Button>
              </Link>
              <div 
                className='truncate text-base font-bold tracking-tight text-foreground/90' 
                title={space?.name || '聊天空间'}
              >
                {space?.name || '聊天空间'}
              </div>
            </div>
            {onEditSpace && (
              <Button
                variant='ghost'
                size='icon'
                className='h-7 w-7 shrink-0 text-muted-foreground/30 hover:text-foreground/60 transition-colors'
                onClick={onEditSpace}
              >
                <SquarePen className='h-3.5 w-3.5' />
              </Button>
            )}
          </div>
          
          <div className='rounded-xl bg-muted/20 px-3.5 py-2.5 border border-border/40'>
             <div className='text-[10px] leading-relaxed text-muted-foreground/50 font-medium line-clamp-1' title={space?.description || ''}>
                {space?.description || '在此切换会话；中间区域专注当前对话内容。'}
             </div>
          </div>
        </div>

        {/* Primary Action (Vibrant Blue) */}
        <Button 
          className='h-10 w-full justify-center gap-2 rounded-xl bg-blue-600 text-[11px] font-bold uppercase tracking-[0.15em] text-white shadow-md shadow-blue-500/20 transition-all hover:translate-y-[-1px] active:translate-y-[0px] hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-500/25' 
          onClick={onCreateSession}
        >
          <Plus className='h-3.5 w-3.5' />
          新建会话
        </Button>
      </div>

      <div className='border-b border-border/40 px-4 pb-3'>
        <Tabs value={section} onValueChange={(value) => setSection(value as 'active' | 'archived')}>
          <TabsList className='grid h-10 w-full grid-cols-2 rounded-xl border border-border/50 bg-muted/30 p-1'>
            <TabsTrigger value='active' className='rounded-lg text-xs font-bold text-muted-foreground data-[state=active]:border data-[state=active]:border-blue-200 data-[state=active]:bg-blue-50 data-[state=active]:text-blue-700 data-[state=active]:shadow-sm'>
              当前会话
              <span className='ml-1 text-[10px] opacity-60'>{activeSessions.length}</span>
            </TabsTrigger>
            <TabsTrigger value='archived' className='rounded-lg text-xs font-bold text-muted-foreground data-[state=active]:border data-[state=active]:border-blue-200 data-[state=active]:bg-blue-50 data-[state=active]:text-blue-700 data-[state=active]:shadow-sm'>
              已归档
              <span className='ml-1 text-[10px] opacity-60'>{archivedSessions.length}</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <div className='relative mt-3'>
          <Search className='pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/40' />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder='按名称筛选会话'
            className='h-9 rounded-xl border-border/40 bg-muted/15 pl-9 text-xs'
          />
        </div>
      </div>

      <ScrollArea className='min-h-0 flex-1'>
        <div className='p-4 pt-3'>
          {section === 'active' ? (
            <section className='space-y-2.5'>
            <div className='flex items-center justify-between gap-2 px-2'>
              <div className='text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/40'>
                当前会话
              </div>
              <Button
                type='button'
                variant='ghost'
                size='icon'
                className='h-6 w-6 text-muted-foreground/40 hover:text-foreground/70'
                onClick={onRefreshActiveSessions}
                disabled={!onRefreshActiveSessions || isRefreshingActiveSessions}
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${isRefreshingActiveSessions ? 'animate-spin' : ''}`}
                />
              </Button>
            </div>
            {pagedActiveSessions.length > 0 ? (
              pagedActiveSessions.map((session, index) => {
                const absoluteIndex = (activePage - 1) * pageSize + index
                const isActive = session.id === activeSessionId
                const Icon = MessageSquare

                return (
                  <div
                    key={session.id}
                    role='button'
                    tabIndex={0}
                    onClick={() => onSelectSession(session.id)}
                    className={`group relative w-full overflow-hidden rounded-xl border p-3 text-left transition-all duration-200 ${
                      isActive
                        ? 'border-blue-500/30 bg-blue-500/[0.04] shadow-sm'
                        : 'border-border/40 bg-muted/10 hover:border-blue-500/30 hover:bg-muted/30'
                    }`}
                  >
                    {isActive && (
                      <div className='absolute inset-y-2.5 left-0 w-0.5 rounded-r-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]' />
                    )}
                    
                    <div className='flex items-center gap-3'>
                      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-all duration-200 ${
                        isActive 
                          ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20' 
                          : 'bg-muted text-muted-foreground/40 group-hover:bg-blue-500/10 group-hover:text-blue-500'
                      }`}>
                        <Icon className='h-3.5 w-3.5' />
                      </div>
                      
                      <div className='min-w-0 flex-1'>
                        <div className='flex items-center justify-between gap-2 mb-0.5'>
                          <div className='flex min-w-0 items-center gap-1.5'>
                            {session.is_pinned ? (
                              <Pin className='h-3 w-3 shrink-0 fill-blue-500 text-blue-500' />
                            ) : null}
                            <div className={`line-clamp-1 text-xs font-bold tracking-tight transition-colors ${
                              isActive ? 'text-blue-600' : 'text-foreground/70 group-hover:text-foreground'
                            }`}>
                              {getSessionDisplayTitle(session, absoluteIndex)}
                            </div>
                          </div>
                          
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                              <Button variant='ghost' size='icon' className='h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity'>
                                <MoreHorizontal className='h-3 w-3' />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align='end' className='w-40 rounded-xl shadow-xl border-border/60'>
                              <DropdownMenuItem className='gap-2 py-2 text-xs font-semibold' onClick={(e) => { e.stopPropagation(); onRenameSession(session); }}>
                                <SquarePen className='h-3 w-3.5 opacity-60' /> 重命名
                              </DropdownMenuItem>
                              <DropdownMenuItem className='gap-2 py-2 text-xs font-semibold' onClick={(e) => { e.stopPropagation(); onTogglePinSession(session); }}>
                                <Pin className='h-3 w-3.5 opacity-60' /> {session.is_pinned ? '取消置顶' : '置顶会话'}
                              </DropdownMenuItem>
                              <DropdownMenuItem className='gap-2 py-2 text-xs font-semibold' onClick={(e) => { e.stopPropagation(); onArchiveSession(session); }}>
                                <Archive className='h-3 w-3.5 opacity-60' /> 归档
                              </DropdownMenuItem>
                              <DropdownMenuSeparator className='bg-border/40' />
                              <DropdownMenuItem className='gap-2 py-2 text-xs font-semibold text-destructive focus:text-destructive' onClick={(e) => { e.stopPropagation(); onDeleteSession(session); }}>
                                <Trash2 className='h-3 w-3.5 opacity-60' /> 删除
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>

                        <div className='flex items-center justify-between gap-2'>
                          <div className='line-clamp-1 text-[10px] font-medium text-muted-foreground/40 flex-1'>
                            {session.summary || '无预览内容'}
                          </div>
                          <div className='flex items-center gap-1.5 shrink-0'>
                             <span className='text-[8px] font-bold text-muted-foreground/30 tabular-nums uppercase'>
                                {formatRelativeTime(session.last_message_at || session.updated_at)}
                             </span>
                             {session.stats?.message_count ? (
                               <div className={`flex h-3.5 min-w-[18px] items-center justify-center rounded-sm px-1 text-[8px] font-black transition-colors ${
                                 isActive ? 'bg-blue-500/20 text-blue-600' : 'bg-muted/40 text-muted-foreground/40 group-hover:bg-blue-500/10 group-hover:text-blue-500'
                               }`}>
                                  {session.stats.message_count}
                               </div>
                             ) : null}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })
            ) : (
              <div className='rounded-xl border border-dashed p-4 text-[11px] font-bold uppercase tracking-widest text-muted-foreground/30 border-muted/40 text-center italic'>
                {normalizedKeyword ? '没有匹配的活跃会话' : '暂无活跃会话'}
              </div>
            )}
            {activeSessions.length > pageSize ? (
              <div className='mt-4 flex items-center justify-between rounded-xl border border-border/40 bg-muted/10 px-3 py-2'>
                <div className='text-[10px] font-bold text-muted-foreground/50'>
                  第 {activePage} / {activeTotalPages} 页
                </div>
                <div className='flex items-center gap-1'>
                  <Button
                    type='button'
                    variant='ghost'
                    size='icon'
                    className='h-7 w-7'
                    disabled={activePage <= 1}
                    onClick={() => setActivePage((current) => Math.max(1, current - 1))}
                  >
                    <ChevronLeft className='h-4 w-4' />
                  </Button>
                  <Button
                    type='button'
                    variant='ghost'
                    size='icon'
                    className='h-7 w-7'
                    disabled={activePage >= activeTotalPages}
                    onClick={() => setActivePage((current) => Math.min(activeTotalPages, current + 1))}
                  >
                    <ChevronRight className='h-4 w-4' />
                  </Button>
                </div>
              </div>
            ) : null}
          </section>
          ) : (
            <section className='space-y-2.5'>
              <div className='flex items-center justify-between gap-2 px-2'>
                <div className='flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/40'>
                  <Archive className='h-3 w-3' />
                  已归档
                </div>
                <Button
                  type='button'
                  variant='ghost'
                  size='icon'
                  className='h-6 w-6 text-muted-foreground/40 hover:text-foreground/70'
                  onClick={onRefreshArchivedSessions}
                  disabled={!onRefreshArchivedSessions || isRefreshingArchivedSessions}
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${isRefreshingArchivedSessions ? 'animate-spin' : ''}`}
                  />
                </Button>
              </div>
              {pagedArchivedSessions.length > 0 ? (
                pagedArchivedSessions.map((session, index) => {
                  const absoluteIndex = (archivedPage - 1) * pageSize + index
                  return (
                    <div
                      key={session.id}
                      role='button'
                      tabIndex={0}
                      onClick={() => onSelectSession(session.id)}
                      className={`group relative w-full rounded-xl border p-3 text-left transition-all duration-200 ${
                        session.id === activeSessionId
                          ? 'border-primary/20 bg-muted/30 shadow-sm'
                          : 'border-transparent hover:bg-muted/20'
                      }`}
                    >
                      <div className='flex items-center justify-between gap-3'>
                        <div className='min-w-0 flex-1 transition-opacity group-hover:opacity-100 opacity-60'>
                          <div className='mb-0.5 flex min-w-0 items-center gap-1.5'>
                            {session.is_pinned ? (
                              <Pin className='h-3 w-3 shrink-0 fill-blue-500 text-blue-500' />
                            ) : null}
                            <div className='line-clamp-1 text-xs font-bold tracking-tight text-foreground/70'>
                              {getSessionDisplayTitle(session, absoluteIndex)}
                            </div>
                          </div>
                          <div className='text-[9px] font-bold uppercase tracking-widest text-muted-foreground/30 tabular-nums'>
                            {formatRelativeTime(session.archived_at || session.updated_at)}
                          </div>
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            asChild
                            onClick={(event) => event.stopPropagation()}
                          >
                            <Button
                              variant='ghost'
                              size='icon'
                              className='h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity'
                            >
                              <MoreHorizontal className='h-3.5 w-3.5' />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align='end' className='w-40 rounded-xl shadow-xl border-border/60'>
                            <DropdownMenuItem
                              className='gap-2 py-2 text-xs font-semibold'
                              onClick={(event) => {
                                event.stopPropagation()
                                onRenameSession(session)
                              }}
                            >
                              <SquarePen className='h-3.5 w-3.5 opacity-60' />
                              重命名
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className='gap-2 py-2 text-xs font-semibold'
                              onClick={(event) => {
                                event.stopPropagation()
                                onTogglePinSession(session)
                              }}
                            >
                              <Pin className='h-3.5 w-3.5 opacity-60' />
                              {session.is_pinned ? '取消置顶' : '置顶会话'}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className='gap-2 py-2 text-xs font-semibold'
                              onClick={(event) => {
                                event.stopPropagation()
                                onArchiveSession(session)
                              }}
                            >
                              <Archive className='h-3.5 w-3.5 opacity-60' />
                              恢复会话
                            </DropdownMenuItem>
                            <DropdownMenuSeparator className='bg-border/40' />
                            <DropdownMenuItem
                              className='gap-2 py-2 text-xs font-semibold text-destructive focus:text-destructive'
                              onClick={(event) => {
                                event.stopPropagation()
                                onDeleteSession(session)
                              }}
                            >
                              <Trash2 className='h-3.5 w-3.5 opacity-60' />
                              删除
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  )
                })
              ) : (
                <div className='rounded-xl border border-dashed p-4 text-[11px] font-bold uppercase tracking-widest text-muted-foreground/30 border-muted/40 text-center italic'>
                  {normalizedKeyword ? '没有匹配的归档会话' : '暂无归档会话'}
                </div>
              )}
              {archivedSessions.length > pageSize ? (
                <div className='mt-4 flex items-center justify-between rounded-xl border border-border/40 bg-muted/10 px-3 py-2'>
                  <div className='text-[10px] font-bold text-muted-foreground/50'>
                    第 {archivedPage} / {archivedTotalPages} 页
                  </div>
                  <div className='flex items-center gap-1'>
                    <Button
                      type='button'
                      variant='ghost'
                      size='icon'
                      className='h-7 w-7'
                      disabled={archivedPage <= 1}
                      onClick={() => setArchivedPage((current) => Math.max(1, current - 1))}
                    >
                      <ChevronLeft className='h-4 w-4' />
                    </Button>
                    <Button
                      type='button'
                      variant='ghost'
                      size='icon'
                      className='h-7 w-7'
                      disabled={archivedPage >= archivedTotalPages}
                      onClick={() => setArchivedPage((current) => Math.min(archivedTotalPages, current + 1))}
                    >
                      <ChevronRight className='h-4 w-4' />
                    </Button>
                  </div>
                </div>
              ) : null}
            </section>
          )}
        </div>
      </ScrollArea>
    </aside>
  )
}
