/**
 * 权限路由守卫组件 - 纯权限检查层
 * 
 * 职责：仅负责细粒度的菜单/路径权限检查
 * 前置条件：用户已通过 globalRouteGuard 的认证检查
 * 
 * 注意：
 * - 不处理用户认证（Token、用户信息）- 由 globalRouteGuard 统一处理
 * - 不重新加载用户信息和菜单 - 信任全局守卫已完成数据准备
 * - 仅在需要额外权限检查时使用（如特殊功能页面）
 * 
 * 权限检查逻辑：
 * - 使用 auth-store 中的 permissions（权限code集合）进行权限判断
 * - 使用 permission-store 中的菜单树结构进行路径查找
 */
import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from '@tanstack/react-router'
import { usePermissionStore } from '@/stores/permission-store'
import { usePermission } from '@/hooks/use-permission'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

interface PermissionRouteGuardProps {
  children: React.ReactNode
  requiredPermission?: string // 可选：需要的权限代码（如 "menu:settings:users"）
  /**
   * 无权限时的重定向路径
   * - undefined：跳转到 /403
   * - string：跳转到指定路径
   */
  redirectTo?: string
  /**
   * 权限检查失败时的回调
   */
  onPermissionDenied?: (path: string) => void
}

// 白名单路由（不需要权限检查）
const WHITELIST_ROUTES = [
  '/',           // 首页
  '/login',      // 登录页面
  '/refresh',    //刷新token
  '/sign-in',    // 登录页面（备用）
  '/sign-in-2',  // 登录页面（备用2）
  '/sign-up',    // 注册页面
  '/forgot-password', // 忘记密码
  '/otp',        // OTP验证
  '/401',        // 未认证页面
  '/403',        // 无权限页面
  '/404',        // 未找到页面
  '/500',        // 服务器错误页面
  '/503',        // 服务不可用页面
]

// 检查路径是否在白名单中
function isWhitelistRoute(path: string): boolean {
  return WHITELIST_ROUTES.some(route => {
    // 精确匹配
    if (route === path) {
      return true
    }
    // 前缀匹配（用于动态路由）
    if (path.startsWith(route + '/')) {
      return true
    }
    return false
  })
}

// 检查路径是否匹配菜单路径
function matchMenuPath(menuPath: string, currentPath: string): boolean {
  if (!menuPath) {
    return false
  }
  
  // 精确匹配
  if (menuPath === currentPath) {
    return true
  }
  
  // 前缀匹配（菜单路径是当前路径的前缀）
  // 例如：菜单路径 /settings，当前路径 /settings/users
  if (currentPath.startsWith(menuPath + '/')) {
    return true
  }
  
  // 动态路由匹配（支持 :id 等参数）
  // 例如：菜单路径 /users/:id，当前路径 /users/123
  const menuSegments = menuPath.split('/')
  const currentSegments = currentPath.split('/')
  
  if (menuSegments.length !== currentSegments.length) {
    return false
  }
  
  return menuSegments.every((segment, index) => {
    // 动态参数匹配
    if (segment.startsWith(':')) {
      return true
    }
    // 精确匹配
    return segment === currentSegments[index]
  })
}

export function PermissionRouteGuard({
  children,
  requiredPermission,
  redirectTo = '/403',
  onPermissionDenied,
}: PermissionRouteGuardProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { hasPermission } = usePermission() // 使用 auth-store 的权限检查
  const { getFlatMenus, isLoaded, loading: isLoading, findMenuByPath } = usePermissionStore()
  const [isChecking, setIsChecking] = useState(true)
  
  useEffect(() => {
    const checkPermission = () => {
      setIsChecking(true)
      
      try {
        const currentPath = location.pathname
        
        // 1. 白名单路由直接放行
        if (isWhitelistRoute(currentPath)) {
          setIsChecking(false)
          return
        }
        
        // 2. 等待菜单加载完成
        // 注意：用户认证和菜单加载由 globalRouteGuard 负责
        // 这里只需等待加载状态即可
        if (isLoading || !isLoaded) {
          console.log('[PermissionRouteGuard] 等待菜单加载完成...')
          return
        }
        
        // 3. 权限检查 - 核心职责
        if (requiredPermission) {
          // 3.1 如果指定了权限代码，使用 auth-store 的权限检查
          if (!hasPermission(requiredPermission)) {
            console.warn(`[PermissionRouteGuard] 无权限访问: ${requiredPermission}`)
            onPermissionDenied?.(currentPath)
            navigate({ to: redirectTo })
            return
          }
        } else {
          // 3.2 如果没有指定权限，检查当前路径是否在用户的菜单中
          const flatMenus = getFlatMenus()
          
          // 尝试精确匹配
          const exactMatch = findMenuByPath(currentPath)
          if (exactMatch) {
            // 找到菜单项，使用其 code 检查权限
            if (hasPermission(exactMatch.code)) {
              setIsChecking(false)
              return
            } else {
              console.warn(`[PermissionRouteGuard] 无权限访问菜单: ${exactMatch.code}`)
              onPermissionDenied?.(currentPath)
              navigate({ to: redirectTo })
              return
            }
          }
          
          // 尝试模糊匹配
          const matchedMenu = flatMenus.find(
            (menu) => menu.path && matchMenuPath(menu.path, currentPath)
          )
          
          if (matchedMenu) {
            // 找到匹配的菜单项，检查其权限
            if (hasPermission(matchedMenu.code)) {
              setIsChecking(false)
              return
            } else {
              console.warn(`[PermissionRouteGuard] 无权限访问菜单: ${matchedMenu.code}`)
              onPermissionDenied?.(currentPath)
              navigate({ to: redirectTo })
              return
            }
          }
          
          // 未找到匹配的菜单
          console.warn(`[PermissionRouteGuard] 未找到匹配的菜单路径: ${currentPath}`)
          onPermissionDenied?.(currentPath)
          navigate({ to: redirectTo })
          return
        }
        
        setIsChecking(false)
      } catch (error) {
        console.error('[PermissionRouteGuard] 权限检查失败:', error)
        setIsChecking(false)
      }
    }
    
    checkPermission()
  }, [
    isLoaded, 
    isLoading,
    requiredPermission, 
    location.pathname,
    hasPermission,
    getFlatMenus,
    findMenuByPath,
    navigate,
    redirectTo,
    onPermissionDenied
  ])
  
  // 显示加载占位符
  if (isChecking || isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="text-sm text-muted-foreground">正在验证权限...</p>
          <div className="space-y-2 max-w-md mx-auto">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4 mx-auto" />
            <Skeleton className="h-4 w-1/2 mx-auto" />
          </div>
        </div>
      </div>
    )
  }
  
  return <>{children}</>
}
