import type { CSSProperties } from 'react'
import { Handle, Position, type HandleProps } from 'reactflow'

interface CustomHandleProps extends HandleProps {
  className?: string
  style?: CSSProperties
}

export const CustomHandle = ({ className, style, ...props }: CustomHandleProps) => {
  return (
    <Handle
      {...props}
      className={`!w-4 !h-4 !bg-white !border-[3px] !border-blue-500 !shadow-sm hover:!scale-125 transition-transform ${className ?? ''}`}
      style={{
        ...(props.position === Position.Left ? { left: -8 } : { right: -8 }),
        ...style,
      }}
    />
  )
}
