/**
 * 切片预览组件 - 滚动辅助按钮
 */
import { useState, useEffect } from 'react'
import { ChevronsDown, ChevronsUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ScrollAssistButtonsProps } from '../types'

/**
 * 滚动辅助按钮组件
 * 根据滚动位置动态显示向上/向下滚动按钮
 */
export function ScrollAssistButtons({
  containerRef,
  watchDeps = [],
  className,
}: ScrollAssistButtonsProps) {
  const [canScrollUp, setCanScrollUp] = useState(false)
  const [canScrollDown, setCanScrollDown] = useState(false)
  const watchDepsKey = JSON.stringify(watchDeps)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // 根据滚动位置动态控制按钮显隐，减少界面干扰。
    const updateScrollState = () => {
      const { scrollTop, clientHeight, scrollHeight } = container
      const maxScrollTop = Math.max(scrollHeight - clientHeight, 0)
      setCanScrollUp(scrollTop > 24)
      setCanScrollDown(maxScrollTop - scrollTop > 24)
    }

    updateScrollState()
    container.addEventListener('scroll', updateScrollState, { passive: true })

    return () => {
      container.removeEventListener('scroll', updateScrollState)
    }
  }, [containerRef, watchDepsKey])

  const scrollToTop = () => {
    containerRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const scrollToBottom = () => {
    const container = containerRef.current
    if (!container) return
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
  }

  if (!canScrollUp && !canScrollDown) {
    return null
  }

  return (
    <div
      className={cn(
        'absolute right-4 bottom-4 z-20 flex flex-col gap-2',
        className
      )}
    >
      {canScrollUp && (
        <Button
          variant='outline'
          size='icon'
          className='h-9 w-9 rounded-full border-slate-200/80 bg-white/90 shadow-lg backdrop-blur-sm transition-all hover:-translate-y-0.5 dark:border-slate-700/80 dark:bg-slate-900/90'
          onClick={scrollToTop}
          title='滚动到顶部'
          aria-label='滚动到顶部'
        >
          <ChevronsUp className='h-4 w-4' />
        </Button>
      )}
      {canScrollDown && (
        <Button
          variant='outline'
          size='icon'
          className='h-9 w-9 rounded-full border-slate-200/80 bg-white/90 shadow-lg backdrop-blur-sm transition-all hover:translate-y-0.5 dark:border-slate-700/80 dark:bg-slate-900/90'
          onClick={scrollToBottom}
          title='滚动到底部'
          aria-label='滚动到底部'
        >
          <ChevronsDown className='h-4 w-4' />
        </Button>
      )}
    </div>
  )
}
