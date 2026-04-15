import React from 'react'
import { Badge } from '@/components/ui/badge'
import { Settings, GripVertical } from 'lucide-react'
import { NodeData } from '../../types'
import { COLOR_CLASSES, ICON_MAP } from '../../constants'
import { Brain } from 'lucide-react'

interface BaseNodeProps {
  data: NodeData
  selected: boolean
  children?: React.ReactNode
}

export const BaseNode: React.FC<BaseNodeProps> = ({ data, selected, children }) => {
  const Icon = ICON_MAP[data.iconName] || Brain
  const colors = COLOR_CLASSES[data.color as keyof typeof COLOR_CLASSES] || COLOR_CLASSES.blue

  return (
    <div
      className={`
        w-[280px] bg-card rounded-xl border-2 shadow-lg
        hover:shadow-xl transition-all duration-200
        ${selected ? 'border-primary ring-4 ring-primary/20 scale-105' : 'border-border hover:border-primary/30'}
      `}
    >
      {/* 节点顶部条 */}
      <div className={`h-1.5 ${colors.bg} rounded-t-xl`} />
      
      {/* 节点头部 */}
      <div className='p-4 pb-3'>
        <div className='flex items-start gap-3'>
          <div className={`h-10 w-10 rounded-lg flex items-center justify-center flex-shrink-0 ${colors.bgLight}`}>
            <Icon className={`h-5 w-5 ${colors.text}`} />
          </div>
          <div className='flex-1 min-w-0'>
            <div className='flex items-center gap-2 mb-1'>
              <span className='text-[10px] font-bold uppercase tracking-wider text-muted-foreground'>
                {data.nodeType}
              </span>
              {selected && (
                <Badge variant='secondary' className='text-[10px] px-1 py-0'>
                  已选中
                </Badge>
              )}
            </div>
            <h4 className='font-semibold text-sm mb-1 truncate'>{data.title}</h4>
            {data.description && (
              <p className='text-xs text-muted-foreground line-clamp-2'>
                {data.description}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* 额外内容（插槽） */}
      {children}

      {/* 节点底部操作区 */}
      <div className='px-4 pb-3 pt-1 border-t border-border/50 flex items-center justify-between'>
        <div className='flex items-center gap-1 text-xs text-muted-foreground'>
          <Settings className='h-3 w-3' />
          <span>配置</span>
        </div>
        <div className='flex items-center gap-1'>
          <GripVertical className='h-3 w-3 text-muted-foreground' />
        </div>
      </div>
    </div>
  )
}
