import { cn } from '@/lib/utils'

/** 全站统一的开源归属文案（单一来源，便于后续修改） */
export const TECH_SUPPORT_TEXT = '本项目由江西开普元科技有限公司开源'

type TechSupportFooterProps = {
  className?: string
}

/**
 * 页脚归属信息，用于主布局与登录等独立布局底部展示。
 */
export function TechSupportFooter({ className }: TechSupportFooterProps) {
  return (
    <footer
      className={cn(
        'shrink-0 border-t border-border/50 bg-background/95 px-4 py-2 text-center text-[11px] text-muted-foreground sm:text-xs',
        className
      )}
      role='contentinfo'
    >
      {TECH_SUPPORT_TEXT}
    </footer>
  )
}
