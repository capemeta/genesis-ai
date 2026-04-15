/**
 * 权限检查 Hook
 * 
 * 🔥 使用统一的 auth-store 中的权限数据（从 /auth/me 接口获取）
 */
import { useAuthStore } from '@/stores/auth-store';

/**
 * 权限检查 Hook
 * 
 * 🔥 使用统一的 auth-store 中的权限数据
 */
export function usePermission() {
  const { user, roles, permissions, hasPermission, hasAnyPermission, hasAllPermissions, hasRole } = useAuthStore();
  
  return {
    // 用户信息
    user,
    // 权限数据（独立于 user 对象）
    permissions,
    roles,
    // 权限检查方法
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    hasRole,
  };
}
