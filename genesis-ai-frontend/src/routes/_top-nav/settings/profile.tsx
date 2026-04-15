import { createFileRoute } from '@tanstack/react-router'
import { SettingsProfile } from '@/features/settings/profile'

export const Route = createFileRoute('/_top-nav/settings/profile')({
  component: SettingsProfile,
})
