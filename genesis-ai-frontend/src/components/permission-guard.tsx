/**
 * 权限守卫组件
 * 
 * 用于包裹需要权限控制的内容
 * 
 * 用法：
 * <PermissionGuard permission="user:read">
 *   <UserList />
 * </PermissionGuard>
 * 
 * <PermissionGuard 
 *   permission={["user:read", "admin"]}
 *   fallback={<div>无权限访问</div>}
 * >
 *   <UserList />
 * </PermissionGuard>
 * 
 * <PermissionGuard 
 *   permission="user:read"
 *   loading={<Skeleton />}
 * >
 *   <UserList />
 * </PermissionGuard>
 */
import { usePermission } from '@/hooks/use-permission'
import { usePermissionStore } from '@/stores/permission-store'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ShieldAlert } from 'lucide-react'

interface PermissionGuardProps {
  /**
   * 所需权限
   * - 字符串：单个权限
   * - 数组：多个权限（OR 逻辑，拥有任意一个即可）
   */
  permission: string | string[]
  
  /**
   * 无权限时的替代内容
   * - undefined：显示默认的无权限提示
   * - React.ReactNode：渲染指定内容
   */
  fallback?: React.ReactNode
  
  /**
   * 权限加载中的占位符
   * - undefined：显示默认的骨架屏
   * - React.ReactNode：渲染指定内容
   */
  loading?: React.ReactNode
  
  /**
   * 需要权限保护的内容
   */
  children: React.ReactNode
}

export function PermissionGuard({
  permission,
  fallback,
  loading,
  children,
}: PermissionGuardProps) {
  const { hasPermission } = usePermission()
  const { loading: isLoading, isLoaded } = usePermissionStore()
  
  // 权限加载中
  if (isLoading || !isLoaded) {
    if (loading) {
      return <>{loading}</>
    }
    
    // 默认骨架屏
    return (
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    )
  }
  
  const allowed = hasPermission(permission)
  
  if (!allowed) {
    if (fallback) {
      return <>{fallback}</>
    }
    
    // 默认无权限提示
    return (
      <Alert variant="destructive">
        <ShieldAlert className="h-4 w-4" />
        <AlertTitle>无权限访问</AlertTitle>
        <AlertDescription>
          您没有访问此内容的权限，请联系管理员。
        </AlertDescription>
      </Alert>
    )
  }
  
  return <>{children}</>
}

/**
 * 多权限守卫组件（AND 逻辑）
 * 
 * 用于需要同时拥有多个权限的场景
 * 
 * 用法：
 * <PermissionGuardAll permissions={["user:read", "user:write"]}>
 *   <UserEditor />
 * </PermissionGuardAll>
 */
interface PermissionGuardAllProps {
  /**
   * 所需权限列表（AND 逻辑，必须全部拥有）
   */
  permissions: string[]
  
  /**
   * 无权限时的替代内容
   */
  fallback?: React.ReactNode
  
  /**
   * 权限加载中的占位符
   */
  loading?: React.ReactNode
  
  /**
   * 需要权限保护的内容
   */
  children: React.ReactNode
}

export function PermissionGuardAll({
  permissions,
  fallback,
  loading,
  children,
}: PermissionGuardAllProps) {
  const { hasAllPermissions } = usePermission()
  const { loading: isLoading, isLoaded } = usePermissionStore()
  
  // 权限加载中
  if (isLoading || !isLoaded) {
    if (loading) {
      return <>{loading}</>
    }
    
    // 默认骨架屏
    return (
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    )
  }
  
  const allowed = hasAllPermissions(permissions)
  
  if (!allowed) {
    if (fallback) {
      return <>{fallback}</>
    }
    
    // 默认无权限提示
    return (
      <Alert variant="destructive">
        <ShieldAlert className="h-4 w-4" />
        <AlertTitle>无权限访问</AlertTitle>
        <AlertDescription>
          您没有访问此内容的权限，请联系管理员。
        </AlertDescription>
      </Alert>
    )
  }
  
  return <>{children}</>
}
