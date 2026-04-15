/**
 * 词典管理 API 客户端（模块内聚）
 */
import axiosInstance from '@/lib/api/axios-instance'
import type { ListRequest, PaginatedResponse, ResourceResponse } from '@/lib/api/types'

export interface GlossaryItem {
  id: string
  tenant_id: string
  kb_id?: string | null
  term: string
  definition: string
  examples?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface GlossaryCreatePayload {
  kb_id?: string | null
  term: string
  definition: string
  examples?: string
  is_active?: boolean
}

export interface GlossaryUpdatePayload {
  kb_id?: string | null
  term?: string
  definition?: string
  examples?: string
  is_active?: boolean
}

export interface SynonymItem {
  id: string
  tenant_id: string
  kb_id?: string | null
  professional_term: string
  priority: number
  is_active: boolean
  description?: string | null
  created_at: string
  updated_at: string
}

export interface SynonymCreatePayload {
  kb_id?: string | null
  professional_term: string
  priority?: number
  is_active?: boolean
  description?: string
}

export interface SynonymUpdatePayload {
  kb_id?: string | null
  professional_term?: string
  priority?: number
  is_active?: boolean
  description?: string
}

export interface SynonymVariantItem {
  id: string
  synonym_id: string
  user_term: string
  is_active: boolean
  description?: string | null
  created_at: string
  updated_at: string
}

export interface BatchVariantItem {
  user_term: string
  is_active?: boolean
  description?: string
}

export interface BatchUpsertVariantsPayload {
  synonym_id: string
  variants: BatchVariantItem[]
  replace?: boolean
}

export interface BatchUpsertVariantsResult {
  synonym_id: string
  inserted_count: number
  updated_count: number
  deleted_count: number
  total_count: number
}

export interface RewritePreviewMatch {
  user_term: string
  professional_term: string
  synonym_id: string
  variant_id: string
  scope: 'kb' | 'tenant'
}

export interface RewritePreviewResult {
  raw_query: string
  rewritten_query: string
  matches: RewritePreviewMatch[]
}

type ListEnvelope<T> = { data: T[]; total: number }
const MAX_PAGE_SIZE = 200

function unwrapData<T>(payload: unknown): T {
  const maybe = payload as { data?: T }
  return (maybe?.data ?? payload) as T
}

async function listScopeItems<T>(url: string, request: ListRequest): Promise<PaginatedResponse<T>> {
  const response = await axiosInstance.post(url, request)
  const result = unwrapData<ListEnvelope<T>>(response.data)
  return {
    data: Array.isArray(result?.data) ? result.data : [],
    total: Number(result?.total ?? 0),
  }
}

async function listAllScopeItems<T>(url: string, request: Omit<ListRequest, 'page' | 'page_size'>): Promise<T[]> {
  let page = 1
  let total = 0
  const rows: T[] = []

  do {
    const result = await listScopeItems<T>(url, {
      ...request,
      page,
      page_size: MAX_PAGE_SIZE,
    })
    rows.push(...result.data)
    total = result.total
    page += 1
    if (result.data.length === 0) {
      break
    }
  } while (rows.length < total)

  return rows
}

export async function listGlossariesByScope(kbId: string, search?: string): Promise<GlossaryItem[]> {
  const [kbRows, globalRows] = await Promise.all([
    listAllScopeItems<GlossaryItem>('/api/v1/kb-glossaries/list', {
      search,
      filters: { kb_id: kbId },
    }),
    listAllScopeItems<GlossaryItem>('/api/v1/kb-glossaries/list', {
      search,
      advanced_filters: [{ field: 'kb_id', op: 'is_null' }],
    }),
  ])

  return [...kbRows, ...globalRows].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
}

export async function createGlossary(data: GlossaryCreatePayload): Promise<GlossaryItem> {
  const response = await axiosInstance.post<ResourceResponse<GlossaryItem>>('/api/v1/kb-glossaries/create', data)
  return unwrapData<GlossaryItem>(response.data)
}

export async function updateGlossary(id: string, data: GlossaryUpdatePayload): Promise<GlossaryItem> {
  const response = await axiosInstance.post<ResourceResponse<GlossaryItem>>('/api/v1/kb-glossaries/update', {
    id,
    ...data,
  })
  return unwrapData<GlossaryItem>(response.data)
}

export async function deleteGlossary(id: string): Promise<void> {
  await axiosInstance.post('/api/v1/kb-glossaries/delete', { id })
}

export async function listSynonymsByScope(kbId: string, search?: string): Promise<SynonymItem[]> {
  const [kbRows, globalRows] = await Promise.all([
    listAllScopeItems<SynonymItem>('/api/v1/kb-synonyms/list', {
      search,
      filters: { kb_id: kbId },
    }),
    listAllScopeItems<SynonymItem>('/api/v1/kb-synonyms/list', {
      search,
      advanced_filters: [{ field: 'kb_id', op: 'is_null' }],
    }),
  ])

  return [...kbRows, ...globalRows].sort((a, b) => {
    if (a.priority !== b.priority) {
      return a.priority - b.priority
    }
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })
}

export async function createSynonym(data: SynonymCreatePayload): Promise<SynonymItem> {
  const response = await axiosInstance.post<ResourceResponse<SynonymItem>>('/api/v1/kb-synonyms/create', data)
  return unwrapData<SynonymItem>(response.data)
}

export async function updateSynonym(id: string, data: SynonymUpdatePayload): Promise<SynonymItem> {
  const response = await axiosInstance.post<ResourceResponse<SynonymItem>>('/api/v1/kb-synonyms/update', {
    id,
    ...data,
  })
  return unwrapData<SynonymItem>(response.data)
}

export async function deleteSynonym(id: string): Promise<void> {
  await axiosInstance.post('/api/v1/kb-synonyms/delete', { id })
}

export async function listSynonymVariants(synonymId: string, search?: string): Promise<SynonymVariantItem[]> {
  const rows = await listAllScopeItems<SynonymVariantItem>('/api/v1/kb-synonym-variants/list', {
    search,
    filters: { synonym_id: synonymId },
  })
  return rows.sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
}

export async function batchUpsertSynonymVariants(
  payload: BatchUpsertVariantsPayload
): Promise<BatchUpsertVariantsResult> {
  const response = await axiosInstance.post('/api/v1/dictionary/synonyms/variants/batch-upsert', payload)
  return unwrapData<BatchUpsertVariantsResult>(response.data)
}

export async function rewriteSynonymPreview(kbId: string, query: string): Promise<RewritePreviewResult> {
  const response = await axiosInstance.post('/api/v1/dictionary/synonyms/rewrite-preview', {
    kb_id: kbId,
    query,
  })
  return unwrapData<RewritePreviewResult>(response.data)
}
