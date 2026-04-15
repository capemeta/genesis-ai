import { type QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { Toaster } from '@/components/ui/sonner'
import { NavigationProgress } from '@/components/navigation-progress'
import { GlobalLoading } from '@/components/global-loading'
import { GeneralError } from '@/features/errors/general-error'
import { NotFoundError } from '@/features/errors/not-found-error'
import { globalRouteGuard } from '@/lib/auth/global-route-guard'



function RootComponent() {
  return (
    <>
      <NavigationProgress />
      <Outlet />
      <Toaster 
        duration={5000} 
        position='top-right' 
        closeButton={true}
        richColors={true}
        expand={true}
      />
      {import.meta.env.MODE === 'development' && (
        <>
          <ReactQueryDevtools buttonPosition='bottom-left' />
          <TanStackRouterDevtools position='bottom-right' />
        </>
      )}
    </>
  )
}

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient
}>()({
  beforeLoad: async ({ location }) => {
    // 🔥 统一的路由守卫入口（在这里加载用户信息）
    await globalRouteGuard(location.pathname)
  },
  // 🔥 关键：在 beforeLoad 期间显示加载组件
  pendingComponent: GlobalLoading,
  component: RootComponent,
  notFoundComponent: NotFoundError,
  errorComponent: GeneralError,
})
