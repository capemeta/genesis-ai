import { createFileRoute } from '@tanstack/react-router'
import { KnowledgeBaseDetail } from '@/features/knowledge-base/detail'

export const Route = createFileRoute('/_top-nav/knowledge-base/$folderId')({
  validateSearch: (search: Record<string, unknown>) => ({
    initialTab: typeof search.initialTab === 'string' ? search.initialTab : undefined,
    tableGuide: typeof search.tableGuide === 'string' ? search.tableGuide : undefined,
  }),
  component: KnowledgeBaseDetail,
})
