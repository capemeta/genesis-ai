import { createFileRoute } from '@tanstack/react-router'
import { TopNavLayout } from '@/components/layout/top-nav-layout'

export const Route = createFileRoute('/_top-nav')({
  // 不需要在这里做认证检查，全局路由守卫已处理
  component: TopNavLayout,
})
