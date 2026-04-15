import React, { useMemo } from 'react'
import { Search, GripVertical, Brain } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { COMPONENT_PALETTE, ICON_MAP, COLOR_CLASSES } from '../../../constants'
import { ComponentItem } from '../../../types'

interface LeftSidebarProps {
  searchTerm: string
  setSearchTerm: (term: string) => void
  addNodeToCenter: (item: ComponentItem) => void
}

export const LeftSidebar = ({ searchTerm, setSearchTerm, addNodeToCenter }: LeftSidebarProps) => {
  const filteredPalette = useMemo(() => {
    if (!searchTerm) return COMPONENT_PALETTE
    
    return COMPONENT_PALETTE.map(section => ({
      ...section,
      items: section.items.filter(item =>
        item.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.description.toLowerCase().includes(searchTerm.toLowerCase())
      ),
    })).filter(section => section.items.length > 0)
  }, [searchTerm])

  const onDragStart = (event: React.DragEvent, item: ComponentItem) => {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('application/reactflow', JSON.stringify(item))
  }

  return (
    <aside className='w-72 border-r bg-card flex flex-col'>
      <div className='p-3 border-b'>
        <div className='relative'>
          <Search className='absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none' />
          <Input
            placeholder='搜索组件...'
            className='pl-9 h-9 bg-background'
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      <ScrollArea className='flex-1 p-3'>
        <div className='space-y-5'>
          {filteredPalette.length === 0 ? (
            <div className='text-center py-8 text-sm text-muted-foreground'>
              未找到匹配的组件
            </div>
          ) : (
            filteredPalette.map((section, index) => (
              <div key={index}>
                <h3 className='text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2.5 px-1'>
                  {section.category}
                </h3>
                <div className='space-y-2'>
                  {section.items.map((item, itemIndex) => {
                    const Icon = ICON_MAP[item.iconName] || Brain
                    const colors = COLOR_CLASSES[item.color as keyof typeof COLOR_CLASSES] || COLOR_CLASSES.blue
                    
                    return (
                      <div
                        key={itemIndex}
                        draggable
                        onDragStart={(e) => onDragStart(e, item)}
                        onDoubleClick={() => addNodeToCenter(item)}
                        className='group flex items-start gap-2.5 p-2.5 rounded-lg border bg-background hover:border-primary/50 hover:shadow-sm cursor-grab active:cursor-grabbing transition-all hover:scale-[1.02]'
                        title='拖拽到画布或双击添加'
                      >
                        <div className={`h-9 w-9 rounded-lg flex items-center justify-center flex-shrink-0 border ${colors.badge}`}>
                          <Icon className='h-4 w-4' />
                        </div>
                        <div className='flex-1 min-w-0'>
                          <div className='font-medium text-sm mb-0.5'>{item.label}</div>
                          <p className='text-xs text-muted-foreground line-clamp-2'>
                            {item.description}
                          </p>
                        </div>
                        <GripVertical className='h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-1' />
                      </div>
                    )
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      <div className='p-3 border-t bg-muted/30'>
        <div className='text-xs space-y-1.5'>
          <div className='flex items-center justify-between text-muted-foreground'>
            <span>拖拽到画布</span>
            <GripVertical className='h-3 w-3' />
          </div>
          <div className='flex items-center justify-between text-muted-foreground'>
            <span>双击添加到中心</span>
            <Badge variant='outline' className='text-[10px] h-4 px-1'>2x</Badge>
          </div>
          <div className='flex items-center justify-between text-muted-foreground'>
            <span>删除节点</span>
            <kbd className='px-1.5 py-0.5 rounded text-xs border bg-background'>Del</kbd>
          </div>
        </div>
      </div>
    </aside>
  )
}
