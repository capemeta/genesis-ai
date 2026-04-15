import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { AxiosError } from 'axios'
import {
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { toast } from 'sonner'
import { APP_BASE_PATH, stripAppBasePath } from '@/lib/app-base'
import { DirectionProvider } from './context/direction-provider'
import { FontProvider } from './context/font-provider'
import { ThemeProvider } from './context/theme-provider'
// Generated Routes
import { routeTree } from './routeTree.gen'
// Fonts (self-hosted via Fontsource)
import '@fontsource-variable/inter'
import '@fontsource-variable/manrope'
// Styles
import './styles/index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // eslint-disable-next-line no-console
        if (import.meta.env.DEV) console.log({ failureCount, error })

        if (failureCount >= 0 && import.meta.env.DEV) return false
        if (failureCount > 3 && import.meta.env.PROD) return false

        return !(
          error instanceof AxiosError &&
          [401, 403].includes(error.response?.status ?? 0)
        )
      },
      refetchOnWindowFocus: import.meta.env.PROD,
      staleTime: 10 * 1000, // 10s
    },
    mutations: {
      onError: () => {
        // handleServerError(error)

        // if (error instanceof AxiosError) {
        //   if (error.response?.status === 304) {
        //     toast.error('Content not modified!')
        //   }
        // }
      },
    },
  },
  queryCache: new QueryCache({
    onError: (error) => {
      if (error instanceof AxiosError) {
        if (error.response?.status === 401) {
          // 🔥 401 错误：axios 拦截器已尝试刷新 token
          // 如果到这里，说明刷新失败或是认证接口本身的错误
          // 这里负责 UI 层处理：显示提示 + 跳转登录页
          
          // 只在非登录页显示提示
          if (
            typeof window !== 'undefined' &&
            stripAppBasePath(window.location.pathname) !== '/login'
          ) {
            toast.error('登录已过期，请重新登录')
            
            // 跳转到登录页
            const redirect = `${router.history.location.href}`
            router.navigate({ to: '/login', search: { redirect } })
          }
        }
        if (error.response?.status === 500) {
          toast.error('服务器错误，请稍后重试')
          // Only navigate to error page in production to avoid disrupting HMR in development
          if (import.meta.env.PROD) {
            router.navigate({ to: '/500' })
          }
        }
        if (error.response?.status === 403) {
          toast.error('无权限访问')
          // router.navigate("/forbidden", { replace: true });
        }
      }
    },
  }),
})

// Create a new router instance
const router = createRouter({
  routeTree,
  basepath: APP_BASE_PATH,
  context: { queryClient },
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
})

// Register the router instance for type safety
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

// Render the app
const rootElement = document.getElementById('root')!
if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement)
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <FontProvider>
            <DirectionProvider>
              <RouterProvider router={router} />
            </DirectionProvider>
          </FontProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </StrictMode>
  )
}
