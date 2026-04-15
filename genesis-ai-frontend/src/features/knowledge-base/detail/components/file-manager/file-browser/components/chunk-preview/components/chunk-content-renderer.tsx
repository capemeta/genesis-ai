import { memo, type ComponentPropsWithoutRef } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'
import 'highlight.js/styles/github-dark.css'
import { Badge } from '@/components/ui/badge'
import { ChunkType } from '@/lib/api/chunks'
import type { Chunk } from '../types'
import {
  parseExcelRowContentToPairs,
  getExcelSheetName,
  isExcelSheetRootChunk,
} from '../lib/excel'
import { sanitizeContent } from '../lib/sanitize'
import { getImageBlockMeta, normalizeImageAnalysis } from '../lib/image'
import { ChunkImageBlock } from './chunk-image-block'

// ============================================================
// ChunkContentRenderer - 根据类型渲染切片内容
// ============================================================

export const ChunkContentRenderer = memo(function ChunkContentRenderer({
  chunk,
  extension,
  kbType,
}: {
  chunk: Chunk
  extension?: string
  kbType?: string
}) {
  const content = sanitizeContent(chunk.content)
  const isTableKnowledgeBase = kbType === 'table'
  const shouldUseOriginalTableBlock =
    isTableKnowledgeBase && !chunk.is_content_edited
  const primaryTableBlockText =
    shouldUseOriginalTableBlock &&
    Array.isArray(chunk.content_blocks) &&
    chunk.content_blocks.length > 0
      ? chunk.content_blocks
          .map((block) => String(block?.text || '').trim())
          .find((text) => text.includes('|') && text.includes('\n'))
      : ''
  const tableMarkdownContent = sanitizeContent(
    primaryTableBlockText || chunk.content
  )
  // 从 metadata_info.parser 提取解析器名称，用于兼容旧数据（无 block.source 时回退判断）
  const chunkParser: string = chunk.metadata_info?.parser || ''

  // 1. 处理 HTML 类型
  if (chunk.chunk_type === ChunkType.HTML) {
    return (
      <div className='prose max-w-none dark:prose-invert'>
        <div
          className='overflow-x-auto rounded border bg-muted/20 p-2'
          dangerouslySetInnerHTML={{ __html: chunk.content }}
        />
      </div>
    )
  }

  // 2. 处理图片类型（独立图片 chunk）
  if (chunk.chunk_type === ChunkType.IMAGE) {
    // 优先从 content_blocks 中找到对应图片块的元数据（source/modality/caption/vision_text）
    const blockMeta = getImageBlockMeta(chunk.content, chunk.content_blocks)
    return (
      <div className='flex flex-col items-start gap-2'>
        <ChunkImageBlock
          src={chunk.content}
          alt={chunk.summary || '切片图片'}
          blockMeta={blockMeta}
          chunkParser={chunkParser}
          variant='full'
        />
        {/* 摘要在 blockMeta.caption 之外额外显示 */}
        {chunk.summary &&
          normalizeImageAnalysis(blockMeta).caption.length === 0 && (
            <p className='text-xs text-muted-foreground italic'>
              {chunk.summary}
            </p>
          )}
      </div>
    )
  }

  // 3. 处理 JSON 类型
  if (chunk.chunk_type === ChunkType.JSON) {
    let jsonData = chunk.content
    try {
      const parsed = JSON.parse(chunk.content)
      jsonData = JSON.stringify(parsed, null, 2)
    } catch {
      // 解析失败按原文本显示
    }

    return (
      <div className='relative'>
        <pre className='overflow-x-auto rounded-lg border border-slate-700 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 font-mono text-xs text-emerald-300 shadow-inner dark:border-slate-800 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-emerald-400'>
          <code>{jsonData}</code>
        </pre>
        <Badge
          variant='secondary'
          className='absolute top-2 right-2 border-slate-600 bg-slate-700/80 text-[10px] text-slate-100'
        >
          JSON
        </Badge>
      </div>
    )
  }

  // 4. 处理 Code 类型
  if (chunk.chunk_type === ChunkType.CODE) {
    const codeContent = `\`\`\`\n${content}\n\`\`\``
    return (
      <div className='prose prose-sm max-w-none break-words dark:prose-invert'>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw, rehypeHighlight]}
          components={{
            img: ({ node, ...props }) => {
              const blockMeta = getImageBlockMeta(
                props.src || '',
                chunk.content_blocks
              )
              return (
                <ChunkImageBlock
                  src={props.src!}
                  alt={props.alt}
                  blockMeta={blockMeta}
                  variant='compact'
                />
              )
            },
          }}
        >
          {codeContent}
        </ReactMarkdown>
      </div>
    )
  }

  // 5. TABLE 类型：主展示统一使用 content，保持与编辑结果和检索文本一致。
  if (chunk.chunk_type === ChunkType.TABLE) {
    const excelRowPairs = parseExcelRowContentToPairs(chunk)
    if (excelRowPairs.length > 0) {
      return (
        <div className='overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900'>
          <div className='border-b border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-medium text-slate-500 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-300'>
            结构化表格视图
          </div>
          <div className='overflow-x-auto'>
            <table className='w-full border-collapse text-sm'>
              <thead>
                <tr className='bg-slate-50/80 dark:bg-slate-800/60'>
                  <th className='w-44 border border-slate-200 px-3 py-2 text-left text-xs font-semibold text-slate-600 dark:border-slate-700 dark:text-slate-300'>
                    字段
                  </th>
                  <th className='border border-slate-200 px-3 py-2 text-left text-xs font-semibold text-slate-600 dark:border-slate-700 dark:text-slate-300'>
                    值
                  </th>
                </tr>
              </thead>
              <tbody>
                {excelRowPairs.map((pair) => (
                  <tr
                    key={pair.key}
                    className='align-top odd:bg-white even:bg-slate-50/40 dark:odd:bg-slate-900 dark:even:bg-slate-800/30'
                  >
                    <td className='border border-slate-200 px-3 py-2 text-xs font-medium whitespace-nowrap text-slate-600 dark:border-slate-700 dark:text-slate-300'>
                      {pair.key}
                    </td>
                    <td className='border border-slate-200 px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap text-slate-700 dark:border-slate-700 dark:text-slate-200'>
                      {pair.value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )
    }

    return (
      <div className='prose max-w-none overflow-x-auto rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900 dark:prose-invert'>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            table: ({ node, ...props }) => (
              <table {...props} className='w-full border-collapse text-sm' />
            ),
            th: ({ node, ...props }) => (
              <th
                {...props}
                className='border border-slate-300 bg-slate-50 px-2 py-1 text-left text-xs font-semibold dark:border-slate-600 dark:bg-slate-800'
              />
            ),
            td: ({ node, ...props }) => (
              <td
                {...props}
                className='border border-slate-300 px-2 py-1 text-xs dark:border-slate-600'
              />
            ),
          }}
        >
          {tableMarkdownContent}
        </ReactMarkdown>
      </div>
    )
  }

  // 6. SUMMARY 类型：以摘要卡片样式渲染
  if (chunk.chunk_type === ChunkType.SUMMARY) {
    const sheetName = getExcelSheetName(chunk)
    const summaryTitle =
      isExcelSheetRootChunk(chunk) && sheetName
        ? `表结构摘要 · Sheet: ${sheetName}`
        : '表结构摘要'

    return (
      <div className='rounded-lg border border-blue-200 bg-blue-50/50 p-3 dark:border-blue-800 dark:bg-blue-950/20'>
        <p className='mb-1.5 text-xs font-semibold text-blue-600 dark:text-blue-400'>
          {summaryTitle}
        </p>
        <p className='text-sm leading-relaxed whitespace-pre-wrap text-slate-700 dark:text-slate-300'>
          {content}
        </p>
      </div>
    )
  }

  // 7. 默认处理 (TEXT, MEDIA, QA, 以及其他未知类型)
  // 如果是 .txt 文件，或者 chunk_type 是 TEXT 且扩展名为 txt，我们应该保留所有换行符
  if (
    extension === 'txt' &&
    (chunk.chunk_type === ChunkType.TEXT || !chunk.chunk_type)
  ) {
    return (
      <pre className='py-2 font-sans text-sm leading-relaxed whitespace-pre-wrap text-slate-700 dark:text-slate-300'>
        {content}
      </pre>
    )
  }

  return (
    <div className='prose max-w-none break-words prose-slate dark:prose-invert prose-p:my-1.5 prose-p:leading-relaxed prose-p:whitespace-pre-wrap prose-p:text-slate-700 dark:prose-p:text-slate-300 prose-strong:font-semibold prose-strong:text-slate-900 dark:prose-strong:text-slate-100'>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeHighlight]}
        components={{
          h1: ({ node, ...props }) => (
            <h1
              {...props}
              className='mt-6 mb-4 rounded-tl rounded-tr border-b-4 border-blue-400 bg-gradient-to-r from-blue-50 to-transparent px-3 py-2 pb-2.5 text-2xl font-extrabold text-blue-700 dark:border-blue-600 dark:from-blue-950/30 dark:to-transparent dark:text-blue-300'
            />
          ),
          h2: ({ node, ...props }) => (
            <h2
              {...props}
              className='mt-5 mb-3 rounded-tl rounded-tr border-b-2 border-purple-300 bg-gradient-to-r from-purple-50/60 to-transparent px-2.5 py-1.5 pb-1.5 text-xl font-bold text-purple-700 dark:border-purple-700 dark:from-purple-950/20 dark:to-transparent dark:text-purple-300'
            />
          ),
          h3: ({ node, ...props }) => (
            <h3
              {...props}
              className='mt-4 mb-2 border-l-4 border-cyan-400 bg-cyan-50/40 py-1 pl-3 text-lg font-bold text-cyan-700 dark:border-cyan-600 dark:bg-cyan-950/20 dark:text-cyan-300'
            />
          ),
          h4: ({ node, ...props }) => (
            <h4
              {...props}
              className='mt-3 mb-1.5 border-l-3 border-orange-400 pl-2.5 text-base font-bold text-orange-700 dark:border-orange-600 dark:text-orange-300'
            />
          ),
          h5: ({ node, ...props }) => (
            <h5
              {...props}
              className='mt-2 mb-1 pl-2 text-sm font-bold text-pink-700 dark:text-pink-300'
            />
          ),
          h6: ({ node, ...props }) => (
            <h6
              {...props}
              className='mt-2 mb-1 pl-1.5 text-sm font-semibold text-emerald-700 dark:text-emerald-300'
            />
          ),
          a: ({ node, ...props }) => (
            <a
              {...props}
              target='_blank'
              rel='noopener noreferrer'
              className='font-medium text-blue-600 underline decoration-blue-400/50 decoration-2 underline-offset-2 transition-all hover:text-blue-700 hover:decoration-blue-600 dark:text-blue-400 dark:decoration-blue-500/50 dark:hover:text-blue-300 dark:hover:decoration-blue-400'
            />
          ),
          strong: ({ node, ...props }) => (
            <strong
              {...props}
              className='rounded bg-slate-100/50 px-0.5 font-bold text-slate-900 dark:bg-slate-800/50 dark:text-slate-50'
            />
          ),
          em: ({ node, ...props }) => (
            <em
              {...props}
              className='font-serif text-slate-600 italic not-italic dark:text-slate-400'
            />
          ),
          blockquote: ({ node, ...props }) => (
            <blockquote
              {...props}
              className='my-4 rounded-r-lg border-l-4 border-amber-500 bg-gradient-to-r from-amber-50 to-orange-50/30 py-3 pr-3 pl-4 text-slate-700 italic shadow-sm dark:border-amber-600 dark:from-amber-950/30 dark:to-orange-950/10 dark:text-slate-300'
            />
          ),
          ul: ({ node, ...props }) => (
            <ul
              {...props}
              className='my-3 list-inside list-disc space-y-1.5 text-slate-700 marker:text-blue-500 dark:text-slate-300 dark:marker:text-blue-400'
            />
          ),
          ol: ({ node, ...props }) => (
            <ol
              {...props}
              className='my-3 list-inside list-decimal space-y-1.5 text-slate-700 marker:font-semibold marker:text-purple-500 dark:text-slate-300 dark:marker:text-purple-400'
            />
          ),
          li: ({ node, ...props }) => (
            <li {...props} className='pl-1 text-sm leading-relaxed' />
          ),
          img: ({ node, ...props }) => {
            const blockMeta = getImageBlockMeta(
              props.src || '',
              chunk.content_blocks
            )
            return (
              <ChunkImageBlock
                src={props.src!}
                alt={props.alt}
                blockMeta={blockMeta}
                variant='compact'
              />
            )
          },
          hr: ({ node, ...props }) => (
            <hr
              {...props}
              className='border-gradient-to-r my-6 border-t-2 from-transparent via-slate-300 to-transparent dark:via-slate-600'
            />
          ),
          table: ({ node, ...props }) => (
            <div className='my-4 overflow-x-auto rounded-lg border border-slate-300 shadow-md dark:border-slate-700'>
              <table {...props} className='w-full text-sm' />
            </div>
          ),
          th: ({ node, ...props }) => (
            <th
              {...props}
              className='border-b-2 border-slate-300 bg-gradient-to-r from-slate-100 to-slate-50 px-4 py-2.5 text-left font-bold text-slate-800 dark:border-slate-600 dark:from-slate-800 dark:to-slate-900 dark:text-slate-200'
            />
          ),
          td: ({ node, ...props }) => (
            <td
              {...props}
              className='border-b border-slate-200 px-4 py-2 text-slate-700 dark:border-slate-700 dark:text-slate-300'
            />
          ),
          pre: ({ node, ...props }) => (
            <pre
              {...props}
              className='my-3 overflow-hidden rounded-lg border border-slate-700 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 !p-0 shadow-md dark:border-slate-800 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950'
            />
          ),
          code: ({
            node,
            className,
            children,
            ...props
          }: ComponentPropsWithoutRef<'code'> & { node?: unknown }) => {
            const match = /language-(\w+)/.exec(className || '')
            return match ? (
              <code {...props} className={className}>
                {children}
              </code>
            ) : (
              <code
                {...props}
                className='rounded-md border border-red-300 bg-gradient-to-r from-red-100 to-rose-100 px-2 py-0.5 font-mono text-sm font-semibold text-red-700 shadow-sm dark:border-red-800 dark:from-red-950/40 dark:to-rose-950/40 dark:text-red-300'
              >
                {children}
              </code>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
})
