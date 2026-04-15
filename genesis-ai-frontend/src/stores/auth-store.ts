/**
 * 认证状态管理
 * 使用 Zustand 管理用户认证和权限
 * 
 * 权限检查规则：
 * - 超级管理员权限：permissions 包含 SUPER_ADMIN_PERMISSION 则拥有所有权限
 * - 超级管理员角色：roles 包含 SUPER_ADMIN_ROLE 则拥有所有角色
 */
import axios from 'axios'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getCurrentUserInfo, login as loginApi, logout as logoutApi, type LoginRequest, type LoginResponse } from '@/lib/api/auth'
import { API_BASE_URL } from '@/lib/api/axios-instance'
import { SUPER_ADMIN_PERMISSION, SUPER_ADMIN_ROLE } from '@/lib/auth/auth-const'

export interface AuthUser {
  id: string
  username: string
  email: string
  nickname: string
  avatar_url?: string
  is_active: boolean
  is_superuser: boolean
  tenant_id: string
}

interface AuthState {
  // 核心用户信息和权限
  user: AuthUser | null
  roles: string[]
  permissions: string[]
  
  // access_token 用于路由守卫检查（HttpOnly Cookie 无法通过 JS 访问）
  access_token: string | null
  
  // refresh_token 持久化存储，用于 refreshToken() 方法备用（Cookie 模式优先）
  refresh_token: string | null
  
  // 基础状态管理方法
  setUser: (user: AuthUser | null) => void
  setRoles: (roles: string[]) => void
  setPermissions: (permissions: string[]) => void
  setUserWithPermissions: (data: { user: AuthUser; roles: string[]; permissions: string[] }) => void
  setAccessToken: (token: string | null) => void
  setRefreshToken: (token: string | null) => void
  setTokens: (tokens: { access_token: string; refresh_token: string }) => void
  reset: () => void
  
  // 权限检查方法
  hasPermission: (permission: string | string[]) => boolean
  hasAnyPermission: (permissions: string[]) => boolean
  hasAllPermissions: (permissions: string[]) => boolean
  hasRole: (role: string | string[]) => boolean
  
  // API 调用方法
  getUserInfo: () => Promise<{ user: AuthUser; roles: string[]; permissions: string[] }>
  login: (loginData: LoginRequest) => Promise<LoginResponse>
  logout: () => Promise<void>
  
  // 仅清除本地状态，不调用后端接口（session 已确认失效时使用）
  clearAuth: () => void
  
  // 统一管理刷新逻辑（调用后端 /refresh 接口，同步更新两个 token）
  refreshToken: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // 初始状态
      user: null,
      roles: [],
      permissions: [],
      access_token: null,
      refresh_token: null,
      
      // 基础状态管理方法
      setUser: (user) => set({ user }),
      setRoles: (roles) => set({ roles }),
      setPermissions: (permissions) => set({ permissions }),
      setUserWithPermissions: (data) => set({
        user: data.user,
        roles: data.roles,
        permissions: data.permissions
      }),
      setAccessToken: (access_token) => set({ access_token }),
      setRefreshToken: (refresh_token) => set({ refresh_token }),
      setTokens: ({ access_token, refresh_token }) => set({ access_token, refresh_token }),
      reset: () => set({
        user: null,
        roles: [],
        permissions: [],
        access_token: null,
        refresh_token: null
      }),
      
      // 权限检查方法
      hasPermission: (permission) => {
        const { permissions } = get()
        if (!permissions || permissions.length === 0) return false
        
        // 超级管理员拥有所有权限
        if (permissions.includes(SUPER_ADMIN_PERMISSION)) return true
        
        if (Array.isArray(permission)) {
          return permission.some(p => permissions.includes(p))
        }
        return permissions.includes(permission)
      },
      
      hasAnyPermission: (permissions) => {
        const { permissions: userPermissions } = get()
        if (!userPermissions || userPermissions.length === 0) return false
        
        // 超级管理员拥有所有权限
        if (userPermissions.includes(SUPER_ADMIN_PERMISSION)) return true
        
        return permissions.some(p => userPermissions.includes(p))
      },
      
      hasAllPermissions: (permissions) => {
        const { permissions: userPermissions } = get()
        if (!userPermissions || userPermissions.length === 0) return false
        
        // 超级管理员拥有所有权限
        if (userPermissions.includes(SUPER_ADMIN_PERMISSION)) return true
        
        return permissions.every(p => userPermissions.includes(p))
      },
      
      hasRole: (role) => {
        const { roles } = get()
        if (!roles || roles.length === 0) return false
        
        // 超级管理员拥有所有角色
        if (roles.includes(SUPER_ADMIN_ROLE)) return true
        
        if (Array.isArray(role)) {
          return role.some(r => roles.includes(r))
        }
        return roles.includes(role)
      },
      
      // API 调用方法
      getUserInfo: async () => {
        console.log('[AuthStore] Getting user info...')
        
        try {
          const userInfo = await getCurrentUserInfo()
          
          // 更新用户信息
          set({
            user: userInfo.user,
            roles: userInfo.roles,
            permissions: userInfo.permissions
          })
          
          console.log('[AuthStore] User info loaded successfully:', {
            user: userInfo.user.username,
            roles: userInfo.roles,
            permissions_count: userInfo.permissions.length
          })
          
          return userInfo
        } catch (error) {
          console.error('[AuthStore] Failed to get user info:', error)
          throw error
        }
      },
      
      login: async (loginData) => {
        console.log('[AuthStore] Logging in...')
        
        try {
          const response = await loginApi(loginData)
          
          // 同时存储 access_token 和 refresh_token（用于路由守卫检查和刷新备用）
          set({ access_token: response.access_token, refresh_token: response.refresh_token })
          
          console.log('[AuthStore] Login successful, tokens stored')
          return response
        } catch (error) {
          console.error('[AuthStore] Login failed:', error)
          throw error
        }
      },
      
      logout: async () => {
        console.log('[AuthStore] Logging out...')
        
        try {
          await logoutApi()
        } catch (error) {
          console.error('[AuthStore] Logout API failed:', error)
          // 即使 API 失败，也清理本地状态
        } finally {
          // 清理认证状态（包括两个 token）
          set({
            user: null,
            roles: [],
            permissions: [],
            access_token: null,
            refresh_token: null
          })
          console.log('[AuthStore] Logout completed, state cleared')
        }
      },
      
      // 仅清除本地状态，不调用后端接口（session 已确认失效时使用，避免触发新的 401）
      clearAuth: () => {
        console.log('[AuthStore] Clearing auth state (no API call)...')
        set({
          user: null,
          roles: [],
          permissions: [],
          access_token: null,
          refresh_token: null
        })
        console.log('[AuthStore] Auth state cleared')
      },
      
      // 统一管理刷新逻辑：调用后端 /refresh 接口，Cookie 模式自动携带，同步更新两个 token
      refreshToken: async () => {
        console.log('[AuthStore] Refreshing token...')
        
        try {
          // Cookie 模式：withCredentials: true，refresh_token Cookie 自动携带
          const response = await axios.post(
            `${API_BASE_URL}/api/v1/auth/refresh`,
            {},
            { withCredentials: true }
          )
          
          const { access_token: newAccessToken, refresh_token: newRefreshToken } = response.data.data
          
          // 同步更新两个 token
          set({ access_token: newAccessToken, refresh_token: newRefreshToken })
          
          console.log('[AuthStore] Token refreshed successfully, both tokens updated')
        } catch (error: any) {
          // 如果遇到 refresh_token 正在被其他请求使用，等待 1 秒后重试一次
          if (error.response?.data?.detail?.includes('being used by another request')) {
            console.log('[AuthStore] Refresh token is being used, waiting 1s and retrying...')
            await new Promise(resolve => setTimeout(resolve, 1000))
            
            const retryResponse = await axios.post(
              `${API_BASE_URL}/api/v1/auth/refresh`,
              {},
              { withCredentials: true }
            )
            
            const { access_token: newAccessToken, refresh_token: newRefreshToken } = retryResponse.data.data
            set({ access_token: newAccessToken, refresh_token: newRefreshToken })
            console.log('[AuthStore] Token refreshed successfully (after retry)')
          } else {
            console.error('[AuthStore] Token refresh failed:', error)
            throw error
          }
        }
      }
    }),
    {
      name: 'auth-storage',
      // 持久化 access_token 和 refresh_token（两个 token 同步更新，用于路由守卫和刷新备用）
      partialize: (state) => ({
        access_token: state.access_token,
        refresh_token: state.refresh_token,
      }),
    }
  )
)
