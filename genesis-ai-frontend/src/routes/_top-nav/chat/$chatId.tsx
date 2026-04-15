import { createFileRoute } from '@tanstack/react-router'
import { ChatSpaceDetailPage } from '@/features/chat/pages/chat-space-detail-page'

export const Route = createFileRoute('/_top-nav/chat/$chatId')({
  validateSearch: (search: Record<string, unknown>) => ({
    sessionId: typeof search.sessionId === 'string' ? search.sessionId : undefined,
  }),
  component: ChatSpaceDetailPage,
})
