import { createFileRoute } from '@tanstack/react-router'
import { HomePage } from '@/features/home/pages/home-page'

export const Route = createFileRoute('/_top-nav/')({
  component: HomePage,
})
