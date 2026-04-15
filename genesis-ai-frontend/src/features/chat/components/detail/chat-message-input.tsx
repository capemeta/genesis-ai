import { useState } from 'react'
import { Loader2, Send, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface ChatMessageInputProps {
  isSending: boolean
  onSend: (content: string) => Promise<void>
  onStop?: () => void
}

export function ChatMessageInput({
  isSending,
  onSend,
  onStop,
}: ChatMessageInputProps) {
  const [value, setValue] = useState('')

  const handleSubmit = async () => {
    const nextValue = value.trim()
    if (!nextValue || isSending) {
      return
    }

    setValue('')
    await onSend(nextValue)
  }

  return (
    <div className='relative border-t border-blue-200 bg-white px-4 pt-4 pb-8 backdrop-blur-xl md:px-8'>
      <div className='pointer-events-none absolute inset-x-0 -top-10 h-10 bg-gradient-to-t from-background/90 to-transparent' />

      <div className='mx-auto max-w-4xl'>
        <div className='group relative rounded-3xl border border-blue-200 bg-blue-50/55 p-2 shadow-sm transition-all duration-200 focus-within:border-blue-400 focus-within:shadow-lg focus-within:shadow-blue-100'>
          <Textarea
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={async (event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                await handleSubmit()
              }
            }}
            placeholder='输入问题，按 Enter 发送，Shift + Enter 换行'
            className='min-h-[56px] max-h-[220px] resize-y border-0 bg-transparent px-5 py-2.5 text-sm leading-6 placeholder:text-blue-700/55 focus-visible:ring-0'
          />

          <div className='mt-0.5 flex items-center justify-between gap-2 px-4 pb-1'>
            <div className='flex items-center gap-2'>
              <div className='flex items-center gap-2 rounded-full border border-blue-200 bg-white/70 px-3 py-1'>
                <div className='h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_2px_rgba(16,185,129,0.15)]' />
                <span className='text-[11px] text-blue-700'>智能引擎在线</span>
              </div>
            </div>

            <div className='flex items-center gap-2.5'>
              {isSending ? (
                <Button
                  variant='outline'
                  size='sm'
                  onClick={onStop}
                  className='h-7 w-7 rounded-md border-blue-200 bg-white p-0 text-blue-700 transition-colors hover:border-destructive/30 hover:bg-destructive/5 hover:text-destructive'
                  aria-label='停止生成'
                >
                  <Square className='h-3 w-3 fill-current' />
                </Button>
              ) : null}

              <Button
                onClick={handleSubmit}
                disabled={!value.trim() || isSending}
                size='sm'
                className='h-7 w-7 rounded-md bg-blue-600 p-0 text-white shadow-sm transition-all hover:bg-blue-700 active:scale-[0.98] disabled:opacity-45'
                aria-label={isSending ? '发送中' : '发送'}
              >
                {isSending ? (
                  <Loader2 className='h-3.5 w-3.5 animate-spin' />
                ) : (
                  <Send className='h-3.5 w-3.5' />
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
