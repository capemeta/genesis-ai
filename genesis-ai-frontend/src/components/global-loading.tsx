/**
 * 全局加载组件
 * 
 * 用于路由守卫加载用户信息和菜单时显示加载提示
 * 优化用户体验，避免页面空白
 * 
 * 🔥 作为 pendingComponent 使用，在 beforeLoad 期间显示
 */
import { Loader2 } from 'lucide-react'

export function GlobalLoading() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <p className="text-lg font-medium text-muted-foreground">
          正在加载...
        </p>
      </div>
    </div>
  )
}
