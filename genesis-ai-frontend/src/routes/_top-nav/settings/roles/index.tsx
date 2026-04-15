import { createFileRoute } from '@tanstack/react-router'
import { RolesPage } from '@/features/settings/roles/roles-page'
import { requirePermission } from '@/lib/auth/permission-guard'

export const Route = createFileRoute('/_top-nav/settings/roles/')({
  beforeLoad: () => {
    requirePermission(['settings:roles:list'])
  },
  component: RolesPage,
})
