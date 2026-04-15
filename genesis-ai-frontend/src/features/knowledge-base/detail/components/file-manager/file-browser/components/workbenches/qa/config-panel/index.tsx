import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save, Settings2, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  fetchKnowledgeBase,
  fetchKnowledgeBaseDocuments,
  reparseDocuments,
  updateKnowledgeBase,
  type KnowledgeBase,
} from '@/lib/api/knowledge-base'

interface QAConfigPanelProps {
  kbId: string
}

type QAIndexMode = 'question_only' | 'question_answer'

interface QARetrievalDraft {
  index_mode: QAIndexMode
  query_weight: number
  answer_weight: number
  enable_keyword_recall: boolean
  enable_category_filter: boolean
  enable_tag_filter: boolean
}

const DEFAULT_DRAFT: QARetrievalDraft = {
  index_mode: 'question_only',
  query_weight: 0.8,
  answer_weight: 0.2,
  enable_keyword_recall: true,
  enable_category_filter: true,
  enable_tag_filter: true,
}

function normalizeWeight(value: number): number {
  const clamped = Math.max(0, Math.min(1, value))
  return Number(clamped.toFixed(2))
}

function normalizeDraft(value: any): QARetrievalDraft {
  const indexMode: QAIndexMode = value?.index_mode === 'question_answer' ? 'question_answer' : 'question_only'
  const queryWeight = Number(value?.query_weight)
  const answerWeight = Number(value?.answer_weight)
  const normalizedQueryWeight = Number.isFinite(queryWeight) ? normalizeWeight(queryWeight) : DEFAULT_DRAFT.query_weight
  const normalizedAnswerWeight = Number.isFinite(answerWeight)
    ? normalizeWeight(answerWeight)
    : normalizeWeight(1 - normalizedQueryWeight)
  const total = normalizedQueryWeight + normalizedAnswerWeight
  const finalQueryWeight = total > 0 ? normalizeWeight(normalizedQueryWeight / total) : DEFAULT_DRAFT.query_weight
  return {
    index_mode: indexMode,
    query_weight: finalQueryWeight,
    answer_weight: normalizeWeight(1 - finalQueryWeight),
    enable_keyword_recall: value?.enable_keyword_recall !== false,
    enable_category_filter: value?.enable_category_filter !== false,
    enable_tag_filter: value?.enable_tag_filter !== false,
  }
}

async function fetchAllKbDocIds(kbId: string): Promise<string[]> {
  const pageSize = 200
  let page = 1
  let total = 0
  const ids: string[] = []

  do {
    const resp = await fetchKnowledgeBaseDocuments(kbId, { page, page_size: pageSize })
    total = resp.total
    ids.push(...resp.data.map((item) => item.id))
    page += 1
  } while ((page - 1) * pageSize < total)

  return ids
}

export function QAConfigPanel({ kbId }: QAConfigPanelProps) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<QARetrievalDraft>(DEFAULT_DRAFT)
  const [showConfirm, setShowConfirm] = useState(false)

  const { data: kb, isLoading } = useQuery({
    queryKey: ['knowledge-base', kbId],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: !!kbId,
  })

  const savedDraft = useMemo(() => {
    const source = (kb?.retrieval_config as any)?.qa
    return normalizeDraft(source)
  }, [kb?.retrieval_config])

  useEffect(() => {
    setDraft(savedDraft)
  }, [savedDraft])

  const isDirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(savedDraft), [draft, savedDraft])
  const isQuestionOnlyMode = draft.index_mode === 'question_only'

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!kb) {
        throw new Error('知识库不存在')
      }
      const nextRetrievalConfig = {
        ...(kb.retrieval_config || {}),
        qa: draft,
      } as KnowledgeBase['retrieval_config']

      await updateKnowledgeBase(kbId, {
        retrieval_config: nextRetrievalConfig,
      })

      const kbDocIds = await fetchAllKbDocIds(kbId)
      if (kbDocIds.length > 0) {
        await reparseDocuments(kbDocIds)
      }
      return kbDocIds.length
    },
    onSuccess: async (count) => {
      toast.success(`配置已保存，已触发 ${count} 个文件重新解析`)
      await queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] })
      await queryClient.invalidateQueries({ queryKey: ['kb-documents', kbId] })
      setShowConfirm(false)
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.message || error?.response?.data?.detail || error?.message || '保存失败，请重试'
      toast.error(msg)
    },
  })

  if (isLoading) {
    return (
      <div className='flex h-full min-h-0 items-center justify-center'>
        <div className='flex items-center gap-2 text-sm text-muted-foreground'>
          <Loader2 className='h-4 w-4 animate-spin' />
          加载配置中...
        </div>
      </div>
    )
  }

  return (
    <div className='flex h-full min-h-0 flex-col bg-background'>
      <div className='border-b px-6 py-3'>
        <div className='flex items-center justify-between gap-3'>
          <div className='flex items-center gap-2'>
            <Settings2 className='h-4 w-4 text-muted-foreground' />
            <h2 className='text-lg font-semibold text-foreground'>配置面板</h2>
          </div>
          <Button
            size='sm'
            className='gap-2'
            disabled={!isDirty || saveMutation.isPending}
            onClick={() => setShowConfirm(true)}
          >
            {saveMutation.isPending ? <Loader2 className='h-4 w-4 animate-spin' /> : <Save className='h-4 w-4' />}
            保存配置
          </Button>
        </div>
      </div>

      <div className='flex-1 overflow-y-auto px-6 py-5'>
        <div className='mx-auto max-w-[1000px] space-y-4'>
          <Card>
            <CardHeader>
              <CardTitle className='text-base'>FAQ 检索模式</CardTitle>
              <CardDescription>配置问句索引策略与答案参与方式，保存后统一触发该知识库下文件重新解析。</CardDescription>
            </CardHeader>
            <CardContent className='space-y-6'>
              <div className='grid grid-cols-2 gap-4'>
                <div className='space-y-2'>
                  <Label>索引模式</Label>
                  <Select
                    value={draft.index_mode}
                    onValueChange={(value) =>
                      setDraft((prev) => {
                        const nextMode = value as QAIndexMode
                        if (nextMode === 'question_only') {
                          return {
                            ...prev,
                            index_mode: nextMode,
                            query_weight: 1,
                            answer_weight: 0,
                          }
                        }
                        return {
                          ...prev,
                          index_mode: nextMode,
                          query_weight: prev.query_weight === 1 && prev.answer_weight === 0 ? DEFAULT_DRAFT.query_weight : prev.query_weight,
                          answer_weight: prev.query_weight === 1 && prev.answer_weight === 0 ? DEFAULT_DRAFT.answer_weight : prev.answer_weight,
                        }
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder='选择索引模式' />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='question_only'>question_only（问句优先）</SelectItem>
                      <SelectItem value='question_answer'>question_answer（问答联合）</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className='rounded-lg border bg-muted/20 px-3 py-2'>
                  <p className='text-sm font-medium'>自动生成问题</p>
                  <p className='mt-1 text-xs text-muted-foreground'>该能力属于知识库级分块配置（适用于所有知识库类型），请到“内容管理 → 解析配置”设置。</p>
                </div>
              </div>

              <div className='grid grid-cols-2 gap-4'>
                <div className='space-y-2'>
                  <Label>问句权重（0~1）</Label>
                  <Input
                    type='number'
                    min={0}
                    max={1}
                    step={0.05}
                    value={draft.query_weight}
                    onChange={(e) =>
                      setDraft((prev) => {
                        const nextQueryWeight = normalizeWeight(Number(e.target.value) || 0)
                        return {
                          ...prev,
                          query_weight: nextQueryWeight,
                          answer_weight: normalizeWeight(1 - nextQueryWeight),
                        }
                      })
                    }
                    disabled={isQuestionOnlyMode}
                  />
                </div>
                <div className='space-y-2'>
                  <Label>答案权重（0~1）</Label>
                  <Input
                    type='number'
                    min={0}
                    max={1}
                    step={0.05}
                    value={draft.answer_weight}
                    onChange={(e) =>
                      setDraft((prev) => {
                        const nextAnswerWeight = normalizeWeight(Number(e.target.value) || 0)
                        return {
                          ...prev,
                          answer_weight: nextAnswerWeight,
                          query_weight: normalizeWeight(1 - nextAnswerWeight),
                        }
                      })
                    }
                    disabled={isQuestionOnlyMode}
                  />
                </div>
              </div>

              {isQuestionOnlyMode && (
                <div className='rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700'>
                  问句优先模式下，答案不参与向量权重，仅用于生成上下文。
                </div>
              )}

              <div className='space-y-3 rounded-lg border bg-muted/20 p-4'>
                <div className='flex items-center justify-between'>
                  <div>
                    <p className='text-sm font-medium'>启用关键词召回</p>
                    <p className='text-xs text-muted-foreground'>与向量召回混合，提升短问句和术语命中率。</p>
                  </div>
                  <Switch
                    checked={draft.enable_keyword_recall}
                    onCheckedChange={(checked) => setDraft((prev) => ({ ...prev, enable_keyword_recall: checked }))}
                  />
                </div>

                <div className='flex items-center justify-between border-t pt-3'>
                  <div>
                    <p className='text-sm font-medium'>识别分类过滤</p>
                    <p className='text-xs text-muted-foreground'>可从问题中识别“分类”并收窄问答范围，适合 FAQ 分栏较清晰的数据集。</p>
                  </div>
                  <Switch
                    checked={draft.enable_category_filter}
                    onCheckedChange={(checked) => setDraft((prev) => ({ ...prev, enable_category_filter: checked }))}
                  />
                </div>

                <div className='flex items-center justify-between border-t pt-3'>
                  <div>
                    <p className='text-sm font-medium'>识别标签过滤</p>
                    <p className='text-xs text-muted-foreground'>可从问题中识别 QA 标签并优先筛选对应问答，适合标签体系稳定的数据集。</p>
                  </div>
                  <Switch
                    checked={draft.enable_tag_filter}
                    onCheckedChange={(checked) => setDraft((prev) => ({ ...prev, enable_tag_filter: checked }))}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <div className='rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900'>
            <div className='flex items-start gap-2'>
              <AlertTriangle className='mt-0.5 h-4 w-4 shrink-0' />
              <p>配置变更不会即时生效，必须点击“保存配置”。保存后系统会自动触发该知识库下文件重新解析。</p>
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={showConfirm}
        onOpenChange={setShowConfirm}
        title='保存配置并触发重新解析'
        desc='此操作会更新知识库级 QA 配置，并触发该知识库下所有文件重新解析。正在解析中的文件会被系统跳过并保留当前任务。'
        confirmText='保存并重新解析'
        cancelBtnText='取消'
        handleConfirm={() => saveMutation.mutate()}
      />
    </div>
  )
}
