/**
 * 文件夹树组件的共享类型定义
 */
import type { FolderTreeNode } from '@/lib/api/folder.types'

// 标签类型从共享模块复用，与 resource_tags（folder/kb_doc）语义一致
export type { TagFormData, TagDefinition } from '../shared/tag-types'

// 文件夹表单数据类型
export interface FolderFormData {
  name: string
  summary: string
  tags: string[]
}

// 文件夹树组件 Props
export interface FolderTreeProps {
  kbId: string
  selectedFolderId?: string
  onSelectFolder?: (folderId: string | null) => void
  canCreate?: boolean
  canEdit?: boolean
  canDelete?: boolean
}

// 文件夹节点组件 Props
export interface FolderTreeNodeProps {
  folder: FolderTreeNode
  level: number
  selectedFolderId?: string
  expandedFolders: Set<string>
  canCreate: boolean
  canEdit: boolean
  canDelete: boolean
  onToggleExpand: (folderId: string) => void
  onSelectFolder: (folderId: string) => void
  onCreateChild: (folder: FolderTreeNode) => void
  onEdit: (folder: FolderTreeNode) => void
  onView: (folder: FolderTreeNode) => void
  onDelete: (folder: FolderTreeNode) => void
}
