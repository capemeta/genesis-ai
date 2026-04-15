/**
 * 初始化认证状态 Hook
 * 在应用启动时检查登录状态
 * 
 * 🔥 Cookie 模式：
 * - 通过调用 /users/me 检查登录状态
 * - 如果 Cookie 有效，返回用户信息
 * - 如果 Cookie 无效，返回 401
 * 
 * 🔥 注意：在登录页不执行检查，避免循环
 * 🔥 防止重复调用：使用 store 中的 initialized 状态，确保整个应用生命周期只初始化一次
 */
import { useEffect } from 'react'
import { stripAppBasePath } from '@/lib/app-base'
import { useGenesisAuthStore } from '@/stores/genesis-auth-store'

export function useAuthInit() {
  const { setUser, setLoading, setInitialized, logout, isAuthenticated, initialized } = useGenesisAuthStore()

  useEffect(() => {
    // 🔥 如果已经初始化过，不再重复执行
    if (initialized) {
      console.log('[AuthInit] Already initialized, skipping')
      return
    }

    // 🔥 如果在登录页，不检查认证状态（避免循环）
    if (
      typeof window !== 'undefined' &&
      stripAppBasePath(window.location.pathname) === '/login'
    ) {
      console.log('[AuthInit] On login page, skipping auth check')
      setLoading(false)
      setInitialized(true)
      return
    }

    const initAuth = async () => {
      // 🔥 如果已经认证，不需要重复检查
      if (isAuthenticated) {
        console.log('[AuthInit] Already authenticated, skipping check')
        setLoading(false)
        setInitialized(true)
        return
      }

      console.log('[AuthInit] Starting authentication check...')
      setLoading(true)

      try {
        // 🔥 Cookie 模式：通过 API 调用检查登录状态
        // 浏览器会自动携带 Cookie
        const { getCurrentUser } = await import('@/lib/api/user')
        
        console.log('[AuthInit] Checking auth status via API...')
        const rawUser = await getCurrentUser()
        const user = {
          id: rawUser.id,
          username: rawUser.username,
          email: rawUser.email ?? '',
          nickname: rawUser.nickname ?? rawUser.username,
          is_active: rawUser.status === 'active',
          is_superuser: false,
          avatar_url: rawUser.avatar_url,
          tenant_id: rawUser.tenant_id,
        }
        
        console.log('[AuthInit] User authenticated:', {
          id: user.id,
          username: user.username,
          email: user.email,
        })
        setUser(user)
      } catch (error: any) {
        console.log('[AuthInit] Not authenticated or session expired:', {
          status: error.response?.status,
          message: error.message,
        })
        // 未登录或 session 过期
        logout()
      } finally {
        setLoading(false)
        setInitialized(true)
        console.log('[AuthInit] Authentication check completed')
      }
    }

    initAuth()
  }, [initialized]) // 🔥 依赖 initialized 状态
}
