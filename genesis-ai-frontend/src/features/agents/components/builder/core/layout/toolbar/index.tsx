import {
  Play,
  Rocket,
  ChevronLeft,
  Code2,
  Undo2,
  Redo2,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'

interface ToolbarProps {
  undo: () => void
  redo: () => void
  historyIndex: number
  historyLength: number
}

export const Toolbar = ({ undo, redo, historyIndex, historyLength }: ToolbarProps) => {
  return (
    <header className='flex h-14 items-center justify-between border-b bg-card px-4 shadow-sm'>
      <div className='flex items-center gap-3'>
        <Button variant='ghost' size='icon' className='h-8 w-8'>
          <ChevronLeft className='h-4 w-4' />
        </Button>
        <Separator orientation='vertical' className='h-6' />
        <div className='flex items-center gap-2'>
          <div className='flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10'>
            <Sparkles className='h-3.5 w-3.5 text-primary' />
          </div>
          <span className='text-sm font-semibold'>Customer Support Bot v1</span>
          <Badge variant='secondary' className='text-xs'>编辑中</Badge>
        </div>
      </div>

      <div className='flex items-center gap-2'>
        <div className='flex items-center gap-1 mr-2'>
          <Button 
            variant='ghost' 
            size='icon' 
            className='h-8 w-8'
            onClick={undo}
            disabled={historyIndex <= 0}
            title='撤销 (Ctrl+Z)'
          >
            <Undo2 className='h-4 w-4' />
          </Button>
          <Button 
            variant='ghost' 
            size='icon' 
            className='h-8 w-8'
            onClick={redo}
            disabled={historyIndex >= historyLength - 1}
            title='重做 (Ctrl+Y)'
          >
            <Redo2 className='h-4 w-4' />
          </Button>
        </div>
        
        <Separator orientation='vertical' className='h-6' />
        
        <div className='flex items-center text-xs text-muted-foreground ml-2 bg-muted/50 px-2.5 py-1 rounded-md'>
          <div className='w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5 animate-pulse' />
          已自动保存
        </div>
        
        <Button variant='outline' size='sm' className='gap-1.5 h-8'>
          <Code2 className='h-3.5 w-3.5' />
          变量
        </Button>
        <Button variant='outline' size='sm' className='gap-1.5 h-8'>
          <Play className='h-3.5 w-3.5' />
          测试
        </Button>
        <Button size='sm' className='gap-1.5 h-8'>
          <Rocket className='h-3.5 w-3.5' />
          发布
        </Button>
      </div>
    </header>
  )
}
