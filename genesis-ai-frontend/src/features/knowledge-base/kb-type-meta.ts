import {
  type LucideIcon,
  FileText,
  MessageSquare,
  Table as TableIcon,
  Globe,
  Mic,
  Puzzle,
} from 'lucide-react'

/** 知识库类型：展示文案、图标与图标淡色提示（与创建弹窗类型含义对齐） */
export interface KbTypeMeta {
  label: string
  /** 仅图标略带上类型色，正文用 muted，避免大块色块突兀 */
  iconClass: string
  Icon: LucideIcon
}

export const KB_TYPE_META: Record<
  'general' | 'qa' | 'table' | 'web' | 'media' | 'connector',
  KbTypeMeta
> = {
  general: {
    label: '通用文档',
    iconClass: 'text-blue-600/75 dark:text-blue-400/85',
    Icon: FileText,
  },
  qa: {
    label: 'QA 问答对',
    iconClass: 'text-emerald-600/75 dark:text-emerald-400/85',
    Icon: MessageSquare,
  },
  table: {
    label: '结构化表格',
    iconClass: 'text-orange-600/75 dark:text-orange-400/85',
    Icon: TableIcon,
  },
  web: {
    label: '网页同步',
    iconClass: 'text-cyan-600/75 dark:text-cyan-400/85',
    Icon: Globe,
  },
  media: {
    label: '音视频转录',
    iconClass: 'text-red-600/75 dark:text-red-400/85',
    Icon: Mic,
  },
  connector: {
    label: '同步应用',
    iconClass: 'text-violet-600/75 dark:text-violet-400/85',
    Icon: Puzzle,
  },
}

/** 未知或后端新类型时回退为通用文档样式 */
export function getKbTypeMeta(type: string): KbTypeMeta {
  const meta = KB_TYPE_META[type as keyof typeof KB_TYPE_META]
  return meta ?? KB_TYPE_META.general
}
