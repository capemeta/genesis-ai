import { type ComponentProps } from 'react'
import { cn } from '@/lib/utils'

/** 与 `public/images/favicon.svg` 一致，便于单文件维护 */
const LOGO_SRC = `${import.meta.env.BASE_URL}images/favicon.svg`

export function Logo({ className, alt = 'Genesis AI Platform', ...props }: ComponentProps<'img'>) {
  return (
    <img
      src={LOGO_SRC}
      alt={alt}
      decoding="async"
      className={cn('h-10 w-10 shrink-0 object-contain', className)}
      {...props}
    />
  )
}
