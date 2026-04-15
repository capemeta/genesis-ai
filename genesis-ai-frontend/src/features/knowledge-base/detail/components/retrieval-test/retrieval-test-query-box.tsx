import type { KeyboardEvent } from 'react'
import { Loader2, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface RetrievalTestQueryBoxProps {
  query: string
  isRunning: boolean
  onQueryChange: (value: string) => void
  onSubmit: () => void
}

export function RetrievalTestQueryBox({
  query,
  isRunning,
  onQueryChange,
  onSubmit,
}: RetrievalTestQueryBoxProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSubmit()
    }
  }

  return (
    <div className='bg-transparent p-4'>
      <div className='relative mx-auto max-w-4xl'>
        <div className='group relative'>
          <div className='absolute -inset-1 rounded-2xl bg-gradient-to-r from-primary/20 to-sky-500/20 opacity-25 blur transition duration-1000 group-focus-within:opacity-100 group-focus-within:duration-200' />
          <div className='relative flex flex-col rounded-2xl border border-blue-100/60 bg-card/60 shadow-sm transition-all focus-within:border-blue-300/60'>
            <Textarea
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder='输入检索问题，按 Enter 开始检索...'
              className='min-h-[88px] resize-none border-none bg-transparent p-4 pb-12 text-sm leading-relaxed placeholder:text-muted-foreground/50 focus-visible:ring-0'
            />
            <div className='absolute bottom-3 right-3 flex items-center gap-2'>
              <div className='hidden rounded bg-muted/50 px-2 py-1 text-[10px] text-muted-foreground sm:block'>
                Shift + Enter 换行
              </div>
              <Button
                className='h-9 w-9 rounded-xl p-0 shadow-lg shadow-primary/20 transition-transform active:scale-95'
                onClick={onSubmit}
                disabled={isRunning}
              >
                {isRunning ? <Loader2 className='h-4 w-4 animate-spin' /> : <Send className='h-4 w-4' />}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
