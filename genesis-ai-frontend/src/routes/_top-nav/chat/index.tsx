import { createFileRoute } from '@tanstack/react-router'
import { ChatSpaceListPage } from '@/features/chat/pages/chat-space-list-page'

export const Route = createFileRoute('/_top-nav/chat/')({
  component: ChatSpaceListPage,
})
