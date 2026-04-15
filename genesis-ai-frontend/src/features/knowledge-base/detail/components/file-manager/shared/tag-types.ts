/**
 * 标签相关类型（共享）
 * 供文件夹树、文件列表、元数据编辑等复用，与后端 tags/resource_tags 语义对齐。
 *
 * 文档标签：resource_tags 中 target_type = 'kb_doc'，target_id = knowledge_base_documents.id
 * 文件夹标签：target_type = 'folder'，target_id = folder.id
 */

import type { TagTargetType } from '@/lib/api/folder.types'

/** 标签定义（与后端 TagRead 对齐，前端 synonyms 对应后端 aliases） */
export interface TagDefinition {
  id: string
  name: string
  description?: string
  color?: string
  synonyms?: string[]
  allowedTargetTypes?: TagTargetType[]
}

/** 标签编辑表单数据 */
export interface TagFormData {
  name: string
  description: string
  synonyms: string[]
  color: string
  allowedTargetTypes: TagTargetType[]
}
