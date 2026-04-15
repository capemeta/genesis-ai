import { useState } from 'react'
import { BookOpen, Code2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { getChunkEnhancement } from '@/lib/api/chunks'
import { cn } from '@/lib/utils'
import type { Chunk } from '../types'
import {
  getChunkHierarchyRole,
} from '../lib/hierarchy'
import { isExcelRowParentChunk } from '../lib/excel'
import { ExcelSheetRootBadge, ExcelRowParentBadge } from '../components/badges'
import { ChunkContentRenderer } from '../components/chunk-content-renderer'

// ============================================================
// FullHierarchyDetailView - 详细内容视图
// ============================================================

export function FullHierarchyDetailView({
  chunk,
  kbType,
}: {
  chunk: Chunk
  kbType?: string
}) {
  const [showRaw, setShowRaw] = useState(false)
  const pId = chunk.parent_id || chunk.metadata_info?.parent_id
  const cIds = chunk.metadata_info?.child_ids || []
  const depth = chunk.metadata_info?.depth ?? 0
  const hierarchyRole = getChunkHierarchyRole(chunk, depth) ?? 'intermediate'
  const isExcelRowParent = isExcelRowParentChunk(chunk)
  const enhancement = getChunkEnhancement(chunk.metadata_info)
  const retrievalQuestions = enhancement.questions || []
  const keywords = enhancement.keywords || []
  // 完整标题：与列表处一致
  const promptPaths = chunk.metadata_info?.prompt_header_paths
  const joinedPromptPaths =
    Array.isArray(promptPaths) && promptPaths.length > 0
      ? promptPaths.filter(Boolean).join(' / ')
      : ''
  const fullTitle =
    chunk.metadata_info?.header_path ||
    chunk.metadata_info?.budget_header_text ||
    chunk.metadata_info?.prompt_header_text ||
    joinedPromptPaths ||
    chunk.summary ||
    chunk.content?.split('\n')[0]?.trim().slice(0, 300) ||
    '（无完整标题）'
  const isEdited = Boolean(chunk.is_content_edited)

  return (
    <div className='space-y-6'>
      {/* 节点基本信息（含完整标题）- 紧凑布局 */}
      <div
        className={cn(
          'rounded-lg border border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50/30 p-3 dark:border-blue-900 dark:from-blue-950/30 dark:to-indigo-950/20',
          isExcelRowParent &&
            'border-slate-300 from-slate-50 to-slate-100/60 dark:border-slate-700 dark:from-slate-900/60 dark:to-slate-800/40'
        )}
      >
        <div className='mb-1.5 flex items-start justify-between gap-2'>
          <div className='min-w-0 flex-1'>
            <div className='flex flex-wrap items-center gap-2 gap-y-1'>
              <h3 className='text-base font-bold text-slate-900 dark:text-slate-100'>
                切片 #{chunk.position}
              </h3>
              <Badge
                variant='outline'
                className='bg-white/50 py-0 text-[10px] dark:bg-slate-900/50'
              >
                ID: {String(chunk.id).slice(0, 12)}
              </Badge>
              <Badge
                variant='outline'
                className={cn(
                  'py-0 text-[10px]',
                  hierarchyRole === 'root'
                    ? 'border-blue-200 bg-blue-50 text-blue-600'
                    : hierarchyRole === 'leaf'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-600'
                      : 'border-amber-200 bg-amber-50 text-amber-600'
                )}
              >
                {hierarchyRole === 'root'
                  ? '根块'
                  : hierarchyRole === 'leaf'
                    ? '叶子块'
                    : '中间块'}
              </Badge>
              <Badge
                variant='outline'
                className='bg-white/50 py-0 text-[10px] dark:bg-slate-900/50'
              >
                深度 {depth}
              </Badge>
              <Badge
                variant='outline'
                className='bg-white/50 py-0 text-[10px] dark:bg-slate-900/50'
              >
                {chunk.token_count || 0} tokens
              </Badge>
              <Badge
                variant='outline'
                className='bg-white/50 py-0 text-[10px] dark:bg-slate-900/50'
              >
                {chunk.text_length || chunk.content.length} chars
              </Badge>
              <ExcelSheetRootBadge chunk={chunk} />
              <ExcelRowParentBadge chunk={chunk} />
              {isEdited && (
                <Badge
                  variant='outline'
                  className='border-orange-300 bg-orange-100 py-0 text-[10px] text-orange-700 dark:border-orange-800 dark:bg-orange-950/40 dark:text-orange-300'
                >
                  已编辑
                </Badge>
              )}
            </div>
            <p
              className='mt-0.5 line-clamp-2 text-xs leading-tight break-words text-slate-600 dark:text-slate-400'
              title={fullTitle}
            >
              {fullTitle}
            </p>
          </div>
          <Button
            variant='outline'
            size='sm'
            onClick={() => setShowRaw(!showRaw)}
            className='h-7 shrink-0 gap-1 px-2 text-xs'
          >
            {showRaw ? (
              <BookOpen className='h-3.5 w-3.5' />
            ) : (
              <Code2 className='h-3.5 w-3.5' />
            )}
            {showRaw ? '渲染' : '原文'}
          </Button>
        </div>
        {/* 关系信息 - 单行 */}
        <div className='flex items-center gap-3 text-xs'>
          <span className='text-muted-foreground'>
            父:{' '}
            <span className='font-mono font-medium text-foreground'>
              {pId ? String(pId).slice(0, 12) : '无'}
            </span>
          </span>
          <span className='text-muted-foreground'>
            子:{' '}
            <span className='font-medium text-foreground'>
              {cIds.length} 个
            </span>
          </span>
        </div>
      </div>

      {/* 摘要 */}
      {chunk.summary && (
        <div className='rounded-lg border border-amber-200 bg-amber-50/50 p-4 dark:border-amber-900 dark:bg-amber-950/20'>
          <div className='mb-2 flex items-center gap-2'>
            <div className='h-4 w-1 rounded-full bg-amber-500' />
            <span className='text-xs font-bold tracking-wider text-amber-700 uppercase dark:text-amber-400'>
              摘要
            </span>
          </div>
          <p className='text-sm leading-relaxed text-slate-700 italic dark:text-slate-300'>
            {chunk.summary}
          </p>
        </div>
      )}

      {/* 正文区域（不展示"内容"二字，避免与实际正文混淆） */}
      <div className='rounded-xl border bg-white p-5 shadow-sm dark:bg-slate-900'>
        <div className='mb-3 flex items-center justify-end'>
          <Badge variant='secondary' className='text-[10px]'>
            {chunk.chunk_type}
          </Badge>
        </div>
        <div className='prose max-w-none prose-slate dark:prose-invert'>
          {showRaw ? (
            <pre className='overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap text-slate-300'>
              {chunk.content}
            </pre>
          ) : (
            <ChunkContentRenderer chunk={chunk} kbType={kbType} />
          )}
        </div>
      </div>

      {/* 检索问题 */}
      {retrievalQuestions.length > 0 && (
          <div className='rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 dark:border-emerald-900 dark:bg-emerald-950/20'>
            <div className='mb-3 flex items-center gap-2'>
              <div className='h-4 w-1 rounded-full bg-emerald-500' />
              <span className='text-xs font-bold tracking-wider text-emerald-700 uppercase dark:text-emerald-400'>
                检索问题
              </span>
            </div>
            <div className='space-y-2'>
              {retrievalQuestions.map((q: string, idx: number) => (
                <div key={idx} className='flex items-start gap-2 text-sm'>
                  <span className='shrink-0 font-bold text-emerald-600 dark:text-emerald-500'>
                    Q{idx + 1}:
                  </span>
                  <span className='text-slate-700 dark:text-slate-300'>
                    {q}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

      {keywords.length > 0 && (
        <div className='rounded-lg border border-blue-200 bg-blue-50/50 p-4 dark:border-blue-900 dark:bg-blue-950/20'>
          <div className='mb-3 flex items-center gap-2'>
            <div className='h-4 w-1 rounded-full bg-blue-500' />
            <span className='text-xs font-bold tracking-wider text-blue-700 uppercase dark:text-blue-400'>
              关键词
            </span>
          </div>
          <div className='flex flex-wrap gap-2'>
            {keywords.map((keyword: string) => (
              <Badge
                key={keyword}
                variant='outline'
                className='border-blue-200 bg-white/80 text-blue-700 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-300'
              >
                {keyword}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Excel 专属元数据（sheet_name / row_index / filter_fields） */}
      {chunk.metadata_info?.sheet_name && (
        <div className='rounded-lg border border-violet-200 bg-violet-50/40 p-3 dark:border-violet-800 dark:bg-violet-950/20'>
          <div className='mb-2 flex items-center gap-2'>
            <div className='h-4 w-1 rounded-full bg-violet-500' />
            <span className='text-xs font-bold tracking-wider text-violet-700 uppercase dark:text-violet-400'>
              Excel 元数据
            </span>
          </div>
          <div className='grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs'>
            <div className='text-muted-foreground'>工作表</div>
            <div className='font-medium text-slate-700 dark:text-slate-300'>
              {chunk.metadata_info.sheet_name}
            </div>
            {chunk.metadata_info.row_index !== undefined && (
              <>
                <div className='text-muted-foreground'>行号</div>
                <div className='font-medium text-slate-700 dark:text-slate-300'>
                  {chunk.metadata_info.row_index}
                </div>
              </>
            )}
            {chunk.metadata_info.row_start !== undefined && (
              <>
                <div className='text-muted-foreground'>行范围</div>
                <div className='font-medium text-slate-700 dark:text-slate-300'>
                  {chunk.metadata_info.row_start} –{' '}
                  {chunk.metadata_info.row_end}
                </div>
              </>
            )}
            {chunk.metadata_info.filter_fields &&
              Object.keys(chunk.metadata_info.filter_fields).length > 0 && (
                <>
                  <div className='text-muted-foreground'>过滤字段</div>
                  <div className='font-medium break-all text-slate-700 dark:text-slate-300'>
                    {Object.entries(chunk.metadata_info.filter_fields)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join('  |  ')}
                  </div>
                </>
              )}
            {chunk.metadata_info.is_row_overflow && (
              <>
                <div className='text-muted-foreground'>溢出分片</div>
                <div className='text-amber-600 dark:text-amber-400'>
                  是（超 token 上限）
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
