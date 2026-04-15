import { createFileRoute } from '@tanstack/react-router'
import { SettingsAppearance } from '@/features/settings/appearance'

export const Route = createFileRoute('/_top-nav/settings/appearance')({
  component: SettingsAppearance,
})
