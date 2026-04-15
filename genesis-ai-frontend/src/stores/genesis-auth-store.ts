/**
 * Genesis AI 认证状态管理
 * 
 * 🔥 Cookie 认证模式：
 * - 后端设置 HttpOnly Cookie
 * - 前端不存储 token
 * - 浏览器自动携带 Cookie
 * - 通过 API 调用检查登录状态
 */
import { create } from 'zustand'
import type { User } from '@/lib/api/user'

export interface GenesisUser {
  id: string
  username: string
  email: string
  nickname: string
  is_active: boolean
  is_superuser: boolean
  avatar_url?: string
  tenant_id: string
}

/**
 * 将当前用户接口适配为认证仓库使用的用户结构。
 */
function normalizeGenesisUser(user: User): GenesisUser {
  return {
    id: user.id,
    username: user.username,
    email: user.email ?? '',
    nickname: user.nickname ?? user.username,
    is_active: user.status === 'active',
    is_superuser: false,
    avatar_url: user.avatar_url,
    tenant_id: user.tenant_id,
  }
}

interface GenesisAuthState {
  user: GenesisUser | null
  isAuthenticated: boolean
  isLoading: boolean
  initialized: boolean
  setUser: (user: GenesisUser | null) => void
  setLoading: (loading: boolean) => void
  setInitialized: (initialized: boolean) => void
  login: (user: GenesisUser) => void
  logout: () => void
  checkAuth: () => Promise<boolean>
}

export const useGenesisAuthStore = create<GenesisAuthState>()((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,  // 🔥 初始状态为 true，等待认证检查完成
  initialized: false,  // 🔥 初始化状态标志

  setUser: (user) =>
    set({
      user,
      isAuthenticated: !!user,
    }),

  setLoading: (loading) =>
    set({
      isLoading: loading,
    }),

  setInitialized: (initialized) =>
    set({
      initialized,
    }),

  login: (user) => {
    // 🔥 Cookie 模式：不需要存储 token
    // 后端已设置 HttpOnly Cookie，浏览器会自动携带
    set({
      user,
      isAuthenticated: true,
    })
  },

  logout: () => {
    // 🔥 Cookie 模式：不需要清除 token
    // 后端会清除 Cookie
    set({
      user: null,
      isAuthenticated: false,
    })
  },

  checkAuth: async () => {
    // 🔥 Cookie 模式：通过调用 API 检查登录状态
    // 如果 Cookie 有效，API 会返回用户信息
    // 如果 Cookie 无效，API 会返回 401
    try {
      const { getCurrentUser } = await import('@/lib/api/user')
      const user = normalizeGenesisUser(await getCurrentUser())
      set({
        user,
        isAuthenticated: true,
      })
      return true
    } catch (error) {
      set({
        user: null,
        isAuthenticated: false,
      })
      return false
    }
  },
}))
