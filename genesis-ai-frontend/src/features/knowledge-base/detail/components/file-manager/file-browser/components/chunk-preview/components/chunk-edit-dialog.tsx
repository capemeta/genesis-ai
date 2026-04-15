import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import { toast } from 'sonner'
import { Loader2, X, Plus } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  buildChunkMetadataInfo,
  getChunkEnhancement,
  updateChunk,
} from '@/lib/api/chunks'
import type { Chunk } from '../types'

// ============================================================
// ChunkEditDialog - 切片编辑对话框
// ============================================================

interface ChunkEditDialogProps {
  chunk: Chunk
  open: boolean
  kbType?: string
  onOpenChange: (open: boolean) => void
}

export function ChunkEditDialog({
  chunk,
  open,
  kbType,
  onOpenChange,
}: ChunkEditDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <ChunkEditDialogContent
          key={`${chunk.id}-${open ? 'open' : 'closed'}`}
          chunk={chunk}
          kbType={kbType}
          onOpenChange={onOpenChange}
        />
      )}
    </Dialog>
  )
}

function ChunkEditDialogContent({
  chunk,
  kbType,
  onOpenChange,
}: {
  chunk: Chunk
  kbType?: string
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const enhancement = getChunkEnhancement(chunk.metadata_info)
  const [content, setContent] = useState(chunk.content)
  const [summary, setSummary] = useState(chunk.summary || '')
  const [keywords, setKeywords] = useState<string[]>(enhancement.keywords || [])
  const [newKeyword, setNewKeyword] = useState('')
  const [retrievalQuestions, setRetrievalQuestions] = useState<string[]>(
    enhancement.questions || []
  )
  const [newQuestion, setNewQuestion] = useState('')
  const [isActive, setIsActive] = useState(chunk.is_active)
  const isTableKnowledgeBase = kbType === 'table'
  const hasEditedContent = Boolean(chunk.is_content_edited)
  const canRestoreOriginal =
    hasEditedContent && Boolean(chunk.original_content)

  const { mutate: updateChunkMutation, isPending } = useMutation({
    mutationFn: () =>
      updateChunk(chunk.id, {
        content,
        summary: summary || undefined,
        is_active: isActive,
        metadata_info: buildChunkMetadataInfo(chunk.metadata_info, {
          keywords,
          questions: retrievalQuestions,
        }),
      }),
    onSuccess: () => {
      toast.success('切片更新成功')
      queryClient.invalidateQueries({ queryKey: ['chunks', chunk.kb_doc_id] })
      onOpenChange(false)
    },
    onError: (error: unknown) => {
      const message =
        error instanceof AxiosError
          ? ((error.response?.data as { detail?: string } | undefined)?.detail ??
            error.message)
          : error instanceof Error
            ? error.message
            : '更新失败'
      toast.error(message)
    },
  })

  const handleAddKeyword = () => {
    if (newKeyword.trim() && !keywords.includes(newKeyword.trim())) {
      setKeywords([...keywords, newKeyword.trim()])
      setNewKeyword('')
    }
  }

  const handleRemoveKeyword = (keywordToRemove: string) => {
    setKeywords(keywords.filter((keyword) => keyword !== keywordToRemove))
  }

  const handleAddQuestion = () => {
    if (
      newQuestion.trim() &&
      !retrievalQuestions.includes(newQuestion.trim())
    ) {
      setRetrievalQuestions([...retrievalQuestions, newQuestion.trim()])
      setNewQuestion('')
    }
  }

  const handleRemoveQuestion = (questionToRemove: string) => {
    setRetrievalQuestions(
      retrievalQuestions.filter((question) => question !== questionToRemove)
    )
  }

  const handleSubmit = () => {
    updateChunkMutation()
  }

  const handleRestoreOriginal = () => {
    if (!chunk.original_content) return
    setContent(chunk.original_content)
  }

  return (
    <DialogContent className='mx-auto max-h-[90vh] w-[90vw] !max-w-5xl overflow-y-auto'>
      <DialogHeader>
        <DialogTitle>编辑切片 #{chunk.position}</DialogTitle>
        <DialogDescription>
          修改切片内容、摘要、关键词和检索问题。
        </DialogDescription>
      </DialogHeader>

      <div className='space-y-4 py-4'>
        {/* 激活状态切换 */}
        <div className='flex items-center justify-between rounded-lg border bg-muted/30 p-3'>
          <div className='space-y-0.5'>
            <Label className='text-sm font-medium'>切片状态</Label>
            <p className='text-xs text-muted-foreground'>
              禁用后该切片不会参与检索
            </p>
          </div>
          <div className='flex items-center gap-2'>
            <span
              className={cn(
                'text-sm',
                isActive ? 'text-green-600' : 'text-gray-500'
              )}
            >
              {isActive ? '已启用' : '已禁用'}
            </span>
            <Switch checked={isActive} onCheckedChange={setIsActive} />
          </div>
        </div>

        {/* 类型提示 */}
        <div className='flex items-center gap-2 rounded bg-muted/20 p-2 text-sm text-muted-foreground'>
          <span>当前类型:</span>
          <Badge variant='outline'>{chunk.chunk_type}</Badge>
          {hasEditedContent && (
            <Badge
              variant='outline'
              className='border-orange-300 bg-orange-100 text-orange-700 dark:border-orange-800 dark:bg-orange-950/40 dark:text-orange-300'
            >
              已编辑
            </Badge>
          )}
          <span className='text-xs'>(暂不支持修改类型)</span>
        </div>

        {hasEditedContent && (
          <div className='flex items-start justify-between gap-3 rounded-lg border border-orange-200 bg-orange-50/80 px-3 py-2.5 dark:border-orange-900 dark:bg-orange-950/20'>
            <div className='space-y-1'>
              <div className='text-sm font-medium text-orange-800 dark:text-orange-300'>
                当前切片内容已被人工修改
              </div>
              <p className='text-xs text-orange-700/80 dark:text-orange-300/80'>
                原始定位和 content_blocks
                仍保持分块时的结构；当前编辑仅影响检索文本。
              </p>
            </div>
            {canRestoreOriginal && (
              <Button
                type='button'
                variant='outline'
                size='sm'
                className='shrink-0 border-orange-300 bg-white/80 text-orange-700 hover:bg-orange-100 dark:border-orange-800 dark:bg-orange-950/30 dark:text-orange-300'
                onClick={handleRestoreOriginal}
              >
                恢复默认内容
              </Button>
            )}
          </div>
        )}

        {isTableKnowledgeBase && (
          <div className='rounded-lg border border-blue-200 bg-blue-50/80 px-3 py-2.5 dark:border-blue-900 dark:bg-blue-950/20'>
            <p className='text-sm font-medium text-blue-800 dark:text-blue-300'>
              表格型知识库的分块内容为只读
            </p>
            <p className='mt-1 text-xs text-blue-700/80 dark:text-blue-300/80'>
              这类分块由表格行结构自动生成，当前仅支持调整状态、摘要和检索增强信息，不支持手工改写 content。
            </p>
          </div>
        )}

        {/* 内容编辑 */}
        <div className='space-y-2'>
          <Label htmlFor='content'>
            内容 (Markdown/Text)
            {isTableKnowledgeBase && ' · 只读'}
          </Label>
          <Textarea
            id='content'
            value={content}
            onChange={(event) => setContent(event.target.value)}
            rows={10}
            className='font-mono text-sm'
            readOnly={isTableKnowledgeBase}
          />
          <div className='flex gap-4'>
            <p className='text-xs text-muted-foreground'>
              当前 Token 数: {chunk.token_count}
            </p>
            <p className='text-xs text-muted-foreground'>
              文本长度:{' '}
              {chunk.text_length ??
                chunk.metadata_info?.text_length ??
                content.length}
            </p>
          </div>
        </div>

        {/* 摘要编辑 */}
        <div className='space-y-2'>
          <Label htmlFor='summary'>摘要（可选）</Label>
          <Textarea
            id='summary'
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            rows={3}
            placeholder='输入切片摘要...'
          />
        </div>

        {/* 关键词编辑 */}
        <div className='space-y-2'>
          <Label>关键词</Label>
          <div className='flex min-h-[60px] flex-wrap gap-2 rounded-lg border border-dashed bg-muted/30 p-3'>
            {keywords.map((keyword) => (
              <Badge
                key={keyword}
                className='flex items-center gap-1 border-blue-200 bg-blue-100 py-1 pr-1 pl-2 text-blue-700 hover:bg-blue-200 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300 dark:hover:bg-blue-900'
              >
                {keyword}
                <button
                  type='button'
                  className='ml-1 transition-colors hover:text-red-500'
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    handleRemoveKeyword(keyword)
                  }}
                >
                  <X className='h-3 w-3' />
                </button>
              </Badge>
            ))}
            <div className='flex items-center gap-2'>
              <Input
                value={newKeyword}
                onChange={(event) => setNewKeyword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    event.stopPropagation()
                    handleAddKeyword()
                  }
                }}
                placeholder='添加关键词...'
                className='h-8 w-32 border-none bg-transparent px-2 text-xs shadow-none focus-visible:ring-0'
              />
              <Button
                type='button'
                size='icon'
                variant='ghost'
                className='h-6 w-6 rounded-full'
                onClick={handleAddKeyword}
              >
                <Plus className='h-3 w-3' />
              </Button>
            </div>
          </div>
        </div>

        {/* 检索问题编辑 */}
        <div className='space-y-2'>
          <Label>检索问题</Label>
          <div className='min-h-[100px] space-y-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-800 dark:bg-emerald-950/20'>
            {retrievalQuestions.length > 0 ? (
              <ul className='mb-2 space-y-2'>
                {retrievalQuestions.map((question, index) => (
                  <li
                    key={index}
                    className='flex items-start gap-2 rounded bg-white p-2 dark:bg-emerald-900/20'
                  >
                    <span className='min-w-[28px] text-sm font-semibold text-emerald-600 dark:text-emerald-500'>
                      Q{index + 1}:
                    </span>
                    <span className='flex-1 text-sm text-emerald-900 dark:text-emerald-300'>
                      {question}
                    </span>
                    <X
                      className='mt-0.5 h-4 w-4 flex-shrink-0 cursor-pointer transition-colors hover:text-red-500'
                      onClick={() => handleRemoveQuestion(question)}
                    />
                  </li>
                ))}
              </ul>
            ) : (
              <p className='mb-2 text-xs text-emerald-600 dark:text-emerald-400'>
                暂无检索问题
              </p>
            )}
            <div className='flex gap-2'>
              <Input
                value={newQuestion}
                onChange={(event) => setNewQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    event.stopPropagation()
                    handleAddQuestion()
                  }
                }}
                placeholder='添加检索问题...'
                className='h-9 flex-1 text-sm'
              />
              <Button
                type='button'
                size='sm'
                variant='secondary'
                onClick={handleAddQuestion}
              >
                <Plus className='mr-1 h-4 w-4' />
                添加
              </Button>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button
          variant='outline'
          onClick={() => onOpenChange(false)}
          disabled={isPending}
        >
          取消
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={isPending}
          className='bg-blue-600 text-white hover:bg-blue-700'
        >
          {isPending ? (
            <>
              <Loader2 className='mr-2 h-4 w-4 animate-spin' />
              保存中...
            </>
          ) : (
            '保存'
          )}
        </Button>
      </DialogFooter>
    </DialogContent>
  )
}
