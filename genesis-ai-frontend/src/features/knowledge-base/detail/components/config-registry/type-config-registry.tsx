import type { LucideIcon } from 'lucide-react'
import type { KnowledgeBase } from '@/lib/api/knowledge-base'
import type { ConfigState } from './types'

export interface TypeConfigSectionDefinition {
  id: string
  label: string
  icon: LucideIcon
  /**
   * 用于从外部引导直接聚焦到某个类型配置区。
   */
  focusAliases?: string[]
  render: (props: {
    kb: KnowledgeBase
    config: ConfigState
    onConfigChange: React.Dispatch<React.SetStateAction<ConfigState>>
    onRequestUploadDraft?: () => void
  }) => React.ReactNode
}

/**
 * 按知识库类型注册一等配置区。
 *
 * 设计目标：
 * 1. 避免把 table / qa / web 的专属配置继续塞进通用页签里。
 * 2. 后续新增类型时，只需要追加注册，而不是改动知识库设置主骨架。
 */
const TYPE_CONFIG_SECTION_REGISTRY: Partial<Record<KnowledgeBase['type'], TypeConfigSectionDefinition[]>> = {
  // 当前 table 类型的结构定义已迁移到“内容管理”工作区，不再在知识库设置中重复提供。
}

export function getTypeConfigSections(kbType?: KnowledgeBase['type']): TypeConfigSectionDefinition[] {
  if (!kbType) {
    return []
  }
  return TYPE_CONFIG_SECTION_REGISTRY[kbType] ?? []
}

export function resolveTypeConfigSectionId(
  kbType: KnowledgeBase['type'] | undefined,
  focusArea?: string
): string | undefined {
  if (!kbType || !focusArea) {
    return undefined
  }

  const sections = getTypeConfigSections(kbType)
  return sections.find((section) =>
    section.id === focusArea || section.focusAliases?.includes(focusArea)
  )?.id
}
