import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import { BadgeCheck, Database, Loader2, RotateCcw, Save } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  confirmTableStructure,
  fetchKnowledgeBase,
  fetchKnowledgeBaseDocuments,
  updateKnowledgeBase,
  type ChunkingConfig,
  type KnowledgeBase,
  type TableSchemaStatus,
} from '@/lib/api/knowledge-base'
import {
  DEFAULT_CHUNKING_CONFIG,
  DEFAULT_TABLE_RETRIEVAL_CONFIG,
} from '@/features/knowledge-base/detail/components/shared-config/constants'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'
import { TableStructureSection } from './table-structure-section'

interface TableStructureManagerProps {
  kbId: string
  /** 引导用户去上传区（由详情页传入，结构页可后续接按钮） */
  onRequestUploadDraft?: () => void
  onNavigateToFiles?: () => void
  onNavigateToData?: () => void
}

function getEffectiveSchemaStatus(
  kb: KnowledgeBase | undefined,
  draftConfig: ConfigState | null,
  hasAttachedFiles: boolean
): TableSchemaStatus {
  const rawStatus = String(
    draftConfig?.retrieval_config?.table?.schema_status ?? kb?.retrieval_config?.table?.schema_status ?? ''
  ).toLowerCase()
  if (rawStatus === 'draft' || rawStatus === 'confirmed') {
    return rawStatus
  }
  if (hasAttachedFiles && Array.isArray(kb?.retrieval_config?.table?.schema?.columns) && kb.retrieval_config.table.schema.columns.length > 0) {
    return 'confirmed'
  }
  return 'draft'
}

function getTableChunkingConfig(config: ConfigState): ChunkingConfig {
  const raw = (config.chunking_config || {}) as Partial<ChunkingConfig>
  return {
    ...DEFAULT_CHUNKING_CONFIG,
    ...raw,
    chunk_strategy: 'excel_table',
    max_embed_tokens: Number(raw.max_embed_tokens || 512),
  }
}

export function TableStructureManager({ kbId }: TableStructureManagerProps) {
  const queryClient = useQueryClient()
  const { data: kb, isLoading } = useQuery({
    queryKey: ['knowledge-base', kbId],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: !!kbId,
  })
  const { data: documentList } = useQuery({
    queryKey: ['kb-documents', kbId, 'structure-lock'],
    queryFn: () =>
      fetchKnowledgeBaseDocuments(kbId, {
        page: 1,
        page_size: 1,
      }),
    enabled: !!kbId,
  })

  const [draftConfig, setDraftConfig] = useState<ConfigState | null>(null)
  const hasAttachedFiles = Number(documentList?.total || 0) > 0

  const config = useMemo<ConfigState>(() => {
    if (draftConfig) {
      return draftConfig
    }
    if (!kb) {
      return {
        retrieval_config: { table: DEFAULT_TABLE_RETRIEVAL_CONFIG },
        chunking_mode: 'custom',
        chunking_config: getTableChunkingConfig({}),
      }
    }
    return {
      chunking_mode: kb.chunking_mode || 'custom',
      chunking_config: getTableChunkingConfig({
        chunking_config: kb.chunking_config || {},
      }),
      retrieval_config:
        kb.type === 'table'
          ? {
              ...(kb.retrieval_config || {}),
              table: {
                ...DEFAULT_TABLE_RETRIEVAL_CONFIG,
                ...((kb.retrieval_config || {}).table || {}),
              },
            }
          : kb.retrieval_config || {},
    }
  }, [draftConfig, kb])

  const schemaStatus = useMemo<TableSchemaStatus>(
    () => getEffectiveSchemaStatus(kb, draftConfig, hasAttachedFiles),
    [draftConfig, hasAttachedFiles, kb]
  )

  const columnCount = Array.isArray(config.retrieval_config?.table?.schema?.columns)
    ? config.retrieval_config.table.schema.columns.length
    : 0
  const lockedColumnCount = hasAttachedFiles && Array.isArray(kb?.retrieval_config?.table?.schema?.columns)
    ? kb.retrieval_config.table.schema.columns.length
    : 0

  const saveMutation = useMutation({
    mutationFn: async () => {
      const columns = Array.isArray(config.retrieval_config?.table?.schema?.columns)
        ? config.retrieval_config.table.schema.columns
        : []
      const emptyNameIndex = columns.findIndex((column) => !String(column?.name || '').trim())
      if (emptyNameIndex >= 0) {
        throw new Error(`第 ${emptyNameIndex + 1} 个字段名称不能为空`)
      }
      const payload: Partial<KnowledgeBase> = {
        chunking_mode: config.chunking_mode || 'custom',
        chunking_config: getTableChunkingConfig(config),
        retrieval_config: {
          ...config.retrieval_config,
          table: {
            ...(config.retrieval_config?.table || {}),
            schema_status: schemaStatus,
          },
        },
      }
      return updateKnowledgeBase(kbId, payload)
    },
    onSuccess: async () => {
      toast.success(schemaStatus === 'confirmed' ? '结构配置已保存' : '结构草稿已保存')
      setDraftConfig(null)
      await queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] })
      await queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
    },
    onError: (error: unknown) => {
      const msg =
        error instanceof AxiosError
          ? error.response?.data?.message ?? error.response?.data?.detail ?? error.message
          : error instanceof Error
            ? error.message
          : '保存表格结构失败'
      toast.error(msg)
    },
  })

  const confirmMutation = useMutation({
    mutationFn: async () => {
      const columns = Array.isArray(config.retrieval_config?.table?.schema?.columns)
        ? config.retrieval_config.table.schema.columns
        : []
      const emptyNameIndex = columns.findIndex((column) => !String(column?.name || '').trim())
      if (emptyNameIndex >= 0) {
        throw new Error(`第 ${emptyNameIndex + 1} 个字段名称不能为空`)
      }
      return confirmTableStructure(kbId, {
        ...(config.retrieval_config || {}),
        table: {
          ...(config.retrieval_config?.table || {}),
          schema_status: 'confirmed',
        },
      })
    },
    onSuccess: async () => {
      toast.success('结构已定稿，后续上传会按当前结构严格校验')
      setDraftConfig(null)
      await queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] })
      await queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
    },
    onError: (error: unknown) => {
      const msg =
        error instanceof AxiosError
          ? error.response?.data?.message ?? error.response?.data?.detail ?? error.message
          : error instanceof Error
            ? error.message
          : '确认结构失败'
      toast.error(msg)
    },
  })

  const isStructureLoading = isLoading || !kb

  return (
    <div className='flex h-full min-h-0 flex-col bg-background'>
      <div className='border-b px-6 py-3'>
        <div className='flex items-start justify-between gap-4'>
          <div className='space-y-2'>
            <div className='flex items-center gap-2'>
              <Database className='h-4 w-4 text-primary' />
              <h2 className='text-lg font-semibold text-foreground'>结构定义</h2>
              <span
                className={
                  schemaStatus === 'confirmed'
                    ? 'inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700'
                    : 'inline-flex items-center rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700'
                }
              >
                {isStructureLoading ? '加载中' : schemaStatus === 'confirmed' ? '已定稿' : '结构草稿'}
              </span>
            </div>
            <p className='text-sm text-muted-foreground'>
              表格知识库要求上传文件的第 1 行为表头、第 2 行起为数据，且后续文档表头必须与定稿结构严格一致。
            </p>
            {schemaStatus === 'draft' ? (
              <div className='inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-700'>
                结构草稿未确认前，除了首个草稿源文档外，不允许继续正式导入其他文档。
              </div>
            ) : !hasAttachedFiles ? (
              <div className='inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs text-blue-700'>
                当前已无已导入文档，结构已解锁，可清空或重新调整全部字段后再继续定稿。
              </div>
            ) : (
              <div className='inline-flex items-center rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-700'>
                已定稿后，既有字段名称与顺序会锁定；可新增可空字段，也可放宽既有字段的非空约束。
              </div>
            )}
            {!hasAttachedFiles && (
              <div className='flex flex-wrap items-center gap-2'>
                <Button
                  variant='outline'
                  size='sm'
                  onClick={() => {
                    setDraftConfig({
                      ...config,
                      retrieval_config: {
                        ...(config.retrieval_config || {}),
                        table: {
                          ...DEFAULT_TABLE_RETRIEVAL_CONFIG,
                          ...(config.retrieval_config?.table || {}),
                          schema: { columns: [] },
                          key_columns: [],
                          field_map: {},
                          schema_status: 'draft',
                        },
                      },
                    })
                    toast.success('已清空当前表格结构，可重新定义字段')
                  }}
                >
                  <RotateCcw className='mr-2 h-4 w-4' />
                  清空结构定义
                </Button>
              </div>
            )}
          </div>

          <div className='flex items-center gap-2'>
            <Button
              variant='outline'
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || isStructureLoading}
            >
              {saveMutation.isPending ? (
                <Loader2 className='mr-2 h-4 w-4 animate-spin' />
              ) : (
                <Save className='mr-2 h-4 w-4' />
              )}
              {schemaStatus === 'confirmed' ? '保存配置' : '保存草稿'}
            </Button>
            {schemaStatus === 'draft' && (
              <Button
                onClick={() => confirmMutation.mutate()}
                disabled={confirmMutation.isPending || columnCount === 0 || isStructureLoading}
              >
                {confirmMutation.isPending ? (
                  <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                ) : (
                  <BadgeCheck className='mr-2 h-4 w-4' />
                )}
                确认结构
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className='min-h-0 flex-1 overflow-y-auto px-6 py-5'>
        <div className='mx-auto max-w-[1360px]'>
          {isStructureLoading ? (
            <section>
              <div className='rounded-xl border bg-card p-4 shadow-sm'>
                <div className='space-y-4'>
                  <div className='flex items-center justify-between gap-3'>
                    <div className='space-y-2'>
                      <div className='h-4 w-20 animate-pulse rounded bg-muted' />
                      <div className='h-3 w-80 animate-pulse rounded bg-muted/80' />
                    </div>
                    <div className='h-9 w-24 animate-pulse rounded-md bg-muted' />
                  </div>
                  <div className='overflow-hidden rounded-lg border'>
                    <div className='grid grid-cols-[2fr_1.2fr_repeat(4,0.7fr)_90px] gap-0 border-b bg-muted/30 px-3 py-2'>
                      {Array.from({ length: 7 }).map((_, index) => (
                        <div key={index} className='h-4 animate-pulse rounded bg-muted' />
                      ))}
                    </div>
                    <div className='space-y-0'>
                      {Array.from({ length: 6 }).map((_, index) => (
                        <div
                          key={index}
                          className='grid grid-cols-[2fr_1.2fr_repeat(4,0.7fr)_90px] items-center gap-3 border-b px-3 py-3 last:border-b-0'
                        >
                          <div className='h-9 animate-pulse rounded bg-muted/80' />
                          <div className='h-9 animate-pulse rounded bg-muted/80' />
                          {Array.from({ length: 4 }).map((__, switchIndex) => (
                            <div key={switchIndex} className='mx-auto h-6 w-10 animate-pulse rounded-full bg-muted/80' />
                          ))}
                          <div className='ml-auto h-8 w-14 animate-pulse rounded bg-muted/80' />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </section>
          ) : (
            <div className='space-y-4'>
              <section className='rounded-xl border bg-card p-4 shadow-sm'>
                <div className='flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between'>
                  <div className='min-w-0 xl:max-w-[720px]'>
                    <h3 className='text-sm font-semibold text-foreground'>表格分块参数</h3>
                    <p
                      className='mt-1 overflow-hidden text-xs leading-5 text-muted-foreground'
                      style={{
                        display: '-webkit-box',
                        WebkitBoxOrient: 'vertical',
                        WebkitLineClamp: 2,
                      }}
                    >
                      表格模式固定使用 tokenizer 计算 token，并始终保留 sheet 根节点；这里只需要配置每个检索块的分块大小。
                    </p>
                  </div>
                  <div className='grid w-full gap-1 xl:w-[320px] xl:flex-none'>
                    <div className='flex items-center gap-2'>
                      <Label htmlFor='table-max-embed-tokens' className='shrink-0 text-xs text-muted-foreground'>
                        最大分块大小（max_embed_tokens）
                      </Label>
                      <Input
                        id='table-max-embed-tokens'
                        type='number'
                        min={128}
                        max={8192}
                        value={getTableChunkingConfig(config).max_embed_tokens}
                        onChange={(e) =>
                          setDraftConfig(prev => ({
                            ...(prev || config),
                            chunking_mode: 'custom',
                            chunking_config: {
                              ...getTableChunkingConfig(prev || config),
                              max_embed_tokens: Number(e.target.value || 512),
                            },
                          }))
                        }
                      />
                      <TooltipProvider delayDuration={150}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type='button'
                              className='inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs text-muted-foreground transition-colors hover:text-foreground'
                              aria-label='分块大小说明'
                            >
                              ?
                            </button>
                          </TooltipTrigger>
                          <TooltipContent className='text-xs'>
                            超出模型安全上限时，后端会自动收口。
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                  </div>
                </div>
              </section>

              <TableStructureSection
                config={config}
                onConfigChange={setDraftConfig}
                schemaStatus={schemaStatus}
                lockedColumnCount={lockedColumnCount}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
