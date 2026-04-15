import { createFileRoute } from '@tanstack/react-router'
import { ModelsPage } from '@/features/settings/models'

export const Route = createFileRoute('/_top-nav/settings/models')({
  component: ModelsPage,
})
