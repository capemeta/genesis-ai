import { createFileRoute } from '@tanstack/react-router'
import { SettingsLayout } from '@/components/layout/settings-layout'
import { requirePermission } from '@/lib/auth/permission-guard'

export const Route = createFileRoute('/_top-nav/settings')({
  beforeLoad: () => {
    // 检查设置菜单基础权限
    requirePermission('menu:settings')
  },
  component: SettingsLayout,
})
