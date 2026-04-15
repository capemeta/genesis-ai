/**
 * 带权限控制的按钮组件
 * 
 * 权限检查逻辑：
 * - 使用 auth-store 中的 permissions 进行权限判断
 * - 使用 permission-store 获取加载状态
 * 
 * 用法：
 * <PermissionButton permission="user:create">
 *   创建用户
 * </PermissionButton>
 * 
 * <PermissionButton permission={["user:create", "admin"]}>
 *   创建用户
 * </PermissionButton>
 * 
 * <PermissionButton 
 *   permission="user:create"
 *   mode="disable"
 *   tooltip="您没有创建用户的权限"
 * >
 *   创建用户
 * </PermissionButton>
 */
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { usePermission } from '@/hooks/use-permission'
import { usePermissionStore } from '@/stores/permission-store'
import { Loader2 } from 'lucide-react'
import type { VariantProps } from 'class-variance-authority'
import { buttonVariants } from '@/components/ui/button'

interface PermissionButtonProps extends React.ComponentProps<'button'>, VariantProps<typeof buttonVariants> {
  /**
   * 所需权限
   * - 字符串：单个权限
   * - 数组：多个权限（OR 逻辑，拥有任意一个即可）
   */
  permission: string | string[]
  
  /**
   * 无权限时的替代内容
   * - undefined：不渲染任何内容
   * - React.ReactNode：渲染指定内容
   */
  fallback?: React.ReactNode
  
  /**
   * 无权限时的行为模式
   * - 'hide'：完全隐藏按钮（默认）
   * - 'disable'：显示禁用状态的按钮
   */
  mode?: 'hide' | 'disable'
  
  /**
   * 无权限时的提示文本（仅在 mode='disable' 时有效）
   */
  tooltip?: string
  
  /**
   * @deprecated 使用 mode='disable' 替代
   */
  disableWhenNoPermission?: boolean
}

export function PermissionButton({
  permission,
  fallback,
  mode = 'hide',
  tooltip = '您没有执行此操作的权限',
  disableWhenNoPermission,
  children,
  disabled,
  variant,
  size,
  className,
  ...props
}: PermissionButtonProps) {
  const { hasPermission } = usePermission()
  const { loading, isLoaded } = usePermissionStore()
  
  // 兼容旧的 API
  const effectiveMode = disableWhenNoPermission ? 'disable' : mode
  
  // 权限加载中
  if (loading || !isLoaded) {
    return (
      <Button variant={variant} size={size} className={className} disabled>
        <Loader2 className="h-4 w-4 animate-spin mr-2" />
        {children}
      </Button>
    )
  }
  
  const allowed = hasPermission(permission)
  
  // 无权限且隐藏模式
  if (!allowed && effectiveMode === 'hide') {
    return fallback ? <>{fallback}</> : null
  }
  
  // 无权限且禁用模式
  if (!allowed && effectiveMode === 'disable') {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0}>
              <Button variant={variant} size={size} className={className} disabled>
                {children}
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <p>{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }
  
  // 有权限，正常渲染
  return (
    <Button variant={variant} size={size} className={className} disabled={disabled} {...props}>
      {children}
    </Button>
  )
}
