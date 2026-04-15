import { createFileRoute } from '@tanstack/react-router'
import { requirePermission } from '@/lib/auth/permission-guard'
import { OrganizationsPage } from '@/features/settings/organizations/organizations-page'

export const Route = createFileRoute('/_top-nav/settings/organizations/')({
  beforeLoad: () => {
    requirePermission(['settings:organizations:list'])
  },
  component: OrganizationsPage,
})
