import { createFileRoute } from '@tanstack/react-router'
import { requirePermission } from '@/lib/auth/permission-guard'
import { PermissionsPage } from '@/features/settings/permissions/permissions-page'

export const Route = createFileRoute('/_top-nav/settings/permissions/')({
  beforeLoad: () => {
    requirePermission(['settings:permissions:list'])
  },
  component: PermissionsPage,
})
