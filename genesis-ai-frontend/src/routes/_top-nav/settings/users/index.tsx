import { createFileRoute } from '@tanstack/react-router'
import { UsersPage } from '@/features/settings/users/users-page'
import { requirePermission } from '@/lib/auth/permission-guard'

export const Route = createFileRoute('/_top-nav/settings/users/')({
  beforeLoad: () => {
    requirePermission(['settings:users:list'])
  },
  component: UsersPage,
})
