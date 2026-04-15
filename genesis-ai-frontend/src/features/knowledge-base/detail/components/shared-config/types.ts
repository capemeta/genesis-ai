import type { KnowledgeBase } from '@/lib/api/knowledge-base'

export interface KnowledgeBaseSettingsProps {
  kbId: string
  focusArea?: string
  onOpenTagManagement?: () => void
}

export type ConfigState = Partial<KnowledgeBase>
