import { CircleHelp } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

/** 标题旁「?」，悬停展示较长说明 */
export function InlineHelpTip({ content }: { content: string }) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type='button'
            className='inline-flex shrink-0 items-center text-muted-foreground transition-colors hover:text-foreground'
            aria-label='说明'
          >
            <CircleHelp className='h-3.5 w-3.5' />
          </button>
        </TooltipTrigger>
        <TooltipContent side='top' className='max-w-xs text-xs leading-5'>
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
