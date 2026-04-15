/**
 * Genesis AI 登录路由
 */
import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { GenesisSignIn } from '@/features/auth/sign-in/genesis-sign-in'

const searchSchema = z.object({
  redirect: z.string().optional(),
})

export const Route = createFileRoute('/(auth)/login')({
  // 🔥 移除 beforeLoad 逻辑，认证检查现在统一在全局路由守卫中处理
  // 全局路由守卫会处理已认证用户访问 /login 页面的重定向
  component: GenesisSignIn,
  validateSearch: searchSchema,
})
