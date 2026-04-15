import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_top-nav/settings/')({
  beforeLoad: () => {
    // 设置首页统一跳转到个人资料页
    throw redirect({ to: '/settings/profile' })
  },
})
