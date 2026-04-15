import { cn } from '@/lib/utils'
import { Files, Search, Settings2, Tag, BookOpen, Shuffle, LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

export type KBTab = 'files' | 'retrieval' | 'tags' | 'glossary' | 'synonyms' | 'config'

interface ActivityBarProps {
    activeTab: KBTab
    onTabChange: (tab: KBTab) => void
}

interface NavItem {
    id: KBTab
    icon: LucideIcon
    label: string
}

const navItems: NavItem[] = [
    { id: 'files', icon: Files, label: '内容管理' },
    { id: 'config', icon: Settings2, label: '知识库设置' },
    { id: 'tags', icon: Tag, label: '标签管理' },
    { id: 'glossary', icon: BookOpen, label: '术语管理' },
    { id: 'synonyms', icon: Shuffle, label: '同义词管理' },
    { id: 'retrieval', icon: Search, label: '检索测试' },
]

export function ActivityBar({ activeTab, onTabChange }: ActivityBarProps) {
    return (
        <aside className='w-14 flex-none bg-muted/30 border-r flex flex-col items-center py-4 gap-4'>
            <TooltipProvider delayDuration={0}>
                {navItems.map((item) => (
                    <Tooltip key={item.id}>
                        <TooltipTrigger asChild>
                            <Button
                                variant='ghost'
                                size='icon'
                                className={cn(
                                    'h-10 w-10 rounded-xl transition-all duration-300',
                                    activeTab === item.id
                                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25 ring-4 ring-blue-500/5'
                                        : 'text-slate-400 hover:bg-slate-100/80 hover:text-slate-600'
                                )}
                                onClick={() => onTabChange(item.id)}
                            >
                                <item.icon className='h-5 w-5' />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent side='right' sideOffset={10}>
                            <p className='text-xs font-medium'>{item.label}</p>
                        </TooltipContent>
                    </Tooltip>
                ))}
            </TooltipProvider>
        </aside>
    )
}
