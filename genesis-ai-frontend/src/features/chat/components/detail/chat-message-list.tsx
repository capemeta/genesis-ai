import { useEffect, useRef, useState } from 'react'
import { Bot, Database, Loader2, MessageSquare, RotateCcw, User2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  RetrievalDebugCandidateSummaryList,
  RetrievalDebugJsonBlock,
  RetrievalDebugRow,
  RetrievalDebugSection,
  RetrievalDebugSheet,
  RetrievalDebugStat,
  RetrievalHitList,
  formatRetrievalDebugNumber,
} from '@/features/shared/retrieval-debug'
import { formatRelativeTime, getMessageText } from '@/features/chat/utils/chat-format'
import type { ChatMessage } from '@/features/chat/types/chat'
import 'highlight.js/styles/github.css'

interface ChatMessageListProps {
  messages: ChatMessage[]
  isStreaming: boolean
  isLoading?: boolean
  isRetrying?: boolean
  onRetryMessage?: (message: ChatMessage) => void
}

export function ChatMessageList({
  messages,
  isStreaming,
  isLoading = false,
  isRetrying = false,
  onRetryMessage,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isStreaming])

  return (
    <div className='min-h-0 flex-1 overflow-y-auto bg-white px-4 py-6 md:px-8'>
      <div className='mx-auto flex max-w-4xl flex-col gap-6'>
        {(messages.length === 0 && isLoading) ? (
          <div className='space-y-8'>
            {[1, 2, 3].map((i) => (
              <div key={i} className={`flex gap-4 md:gap-6 ${i % 2 === 0 ? 'flex-row-reverse' : ''} animate-pulse`}>
                <div className='h-12 w-12 rounded-2xl bg-blue-100/80' />
                <div className={`flex flex-1 flex-col gap-3 ${i % 2 === 0 ? 'items-end' : ''}`}>
                  <div className='h-3 w-24 rounded bg-blue-100/80' />
                  <div className='h-20 w-[60%] rounded-3xl bg-blue-100/70' />
                </div>
              </div>
            ))}
          </div>
        ) : messages.map((message, index) => {
          const isAssistant = message.role === 'assistant'
          const text = getMessageText(message)

          return (
            <div
              key={message.id || index}
              className={`flex gap-3.5 md:gap-5 ${isAssistant ? 'animate-in fade-in slide-in-from-left-3 duration-300' : 'flex-row-reverse animate-in fade-in slide-in-from-right-3 duration-300'}`}
            >
              {isAssistant ? (
                <div className='flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-sky-500 text-white shadow-sm ring-1 ring-sky-200'>
                  <Bot className='h-4.5 w-4.5' />
                </div>
              ) : (
                <Avatar className='h-10 w-10 border border-blue-200/70 bg-blue-50 shadow-sm'>
                  <AvatarFallback className='bg-blue-100 text-blue-700'>
                    <User2 className='h-4.5 w-4.5' />
                  </AvatarFallback>
                </Avatar>
              )}

              <div className={`flex min-w-0 flex-1 flex-col gap-2 ${isAssistant ? '' : 'items-end'}`}>
                <div
                  className={`flex items-center gap-2 text-[11px] text-blue-700/80 ${
                    isAssistant ? '' : 'justify-end pr-1'
                  }`}
                >
                  <span className={`font-medium ${isAssistant ? 'text-primary' : 'text-foreground/80'}`}>
                    {isAssistant ? 'Genesis' : '你'}
                  </span>
                  <span className='h-1 w-1 rounded-full bg-muted-foreground/20' />
                  <span className='tabular-nums'>{formatRelativeTime(message.created_at)}</span>
                  <Badge variant='outline' className={`h-4 border-none px-1.5 text-[9px] font-medium ${
                    isAssistant ? 'bg-blue-100 text-blue-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {message.status}
                  </Badge>
                </div>

                <div
                  className={`group relative max-w-[88%] rounded-2xl px-4.5 py-3.5 text-sm leading-7 transition-colors duration-200 ${
                    isAssistant
                      ? 'rounded-tl-md border border-white/95 bg-white/60 shadow-[0_8px_24px_rgba(15,23,42,0.08)] ring-1 ring-white/75 backdrop-blur-xl'
                      : 'rounded-tr-md border border-emerald-300/70 bg-emerald-500 text-white shadow-[0_8px_24px_rgba(16,185,129,0.25)] ring-1 ring-emerald-200/40'
                  }`}
                >
                  <div className='break-words'>
                    {message.status === 'streaming' && !text ? (
                      <span className='flex items-center gap-2 text-primary/80 transition-opacity duration-300'>
                        <Loader2 className='h-3.5 w-3.5 animate-spin' />
                        <span className='text-[11px]'>正在思考中...</span>
                      </span>
                    ) : (
                      <>
                        <div className='prose prose-sm max-w-none prose-headings:mb-2 prose-headings:mt-3 prose-p:my-1 prose-li:my-0 prose-ul:my-2 prose-ol:my-2 prose-pre:my-2 prose-table:my-2'>
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw, rehypeHighlight]}
                            components={{
                              h1({ children }) {
                                return <h1 className={`mb-2 mt-3 text-xl font-semibold leading-7 ${isAssistant ? 'text-slate-900' : 'text-white'}`}>{children}</h1>
                              },
                              h2({ children }) {
                                return <h2 className={`mb-2 mt-3 text-lg font-semibold leading-7 ${isAssistant ? 'text-slate-900' : 'text-white'}`}>{children}</h2>
                              },
                              h3({ children }) {
                                return <h3 className={`mb-1.5 mt-2.5 text-base font-semibold leading-6 ${isAssistant ? 'text-slate-900' : 'text-white'}`}>{children}</h3>
                              },
                              p({ children }) {
                                return <p className={`my-1 leading-6 ${isAssistant ? 'text-slate-800' : 'text-white'}`}>{children}</p>
                              },
                              ul({ children }) {
                                return <ul className='my-2 list-disc pl-5'>{children}</ul>
                              },
                              ol({ children }) {
                                return <ol className='my-2 list-decimal pl-5'>{children}</ol>
                              },
                              li({ children }) {
                                return <li className={`my-0.5 leading-6 ${isAssistant ? 'text-slate-800' : 'text-white'}`}>{children}</li>
                              },
                              pre({ children }) {
                                return (
                                  <pre className={`my-2 overflow-x-auto rounded-lg p-3 text-[12px] leading-5 ${isAssistant ? 'bg-slate-900 text-slate-50' : 'bg-emerald-700/90 text-emerald-50'}`}>
                                    {children}
                                  </pre>
                                )
                              },
                              code({ className, children }) {
                                const isBlock = Boolean(className && className.includes('language-'))
                                if (isBlock) {
                                  return <code className={className}>{children}</code>
                                }
                                return (
                                  <code className={isAssistant ? 'rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12px] text-slate-800' : 'rounded bg-white/20 px-1.5 py-0.5 font-mono text-[12px] text-white'}>
                                    {children}
                                  </code>
                                )
                              },
                              table({ children }) {
                                return (
                                  <div className={`my-2 overflow-x-auto rounded-lg border ${isAssistant ? 'border-slate-200 bg-white/85' : 'border-white/30 bg-white/10'}`}>
                                    <table className={`min-w-full divide-y text-xs ${isAssistant ? 'divide-slate-200' : 'divide-white/25'}`}>{children}</table>
                                  </div>
                                )
                              },
                              th({ children }) {
                                return (
                                  <th className={`px-2 py-1.5 text-left font-semibold ${isAssistant ? 'bg-slate-50 text-slate-800' : 'bg-white/15 text-white'}`}>
                                    {children}
                                  </th>
                                )
                              },
                              td({ children }) {
                                return <td className={`px-2 py-1.5 align-top ${isAssistant ? 'text-slate-800' : 'text-white/95'}`}>{children}</td>
                              },
                            }}
                          >
                            {text || '暂无内容'}
                          </ReactMarkdown>
                        </div>
                        {message.status === 'streaming' && text ? (
                          <span className='ml-1 inline-block h-4 w-1 animate-pulse rounded-full bg-primary align-middle' />
                        ) : null}
                      </>
                    )}
                  </div>

                  {message.status === 'failed' && message.error_message ? (
                    <div className='mt-3 rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-2 text-[12px] text-destructive/90'>
                      {message.error_message}
                    </div>
                  ) : null}
                </div>

                {isAssistant && message.status === 'failed' && onRetryMessage ? (
                  <div className='flex max-w-3xl justify-start'>
                    <Button
                      variant='outline'
                      size='sm'
                      className='h-7 rounded-lg border-destructive/20 text-[10px] font-bold text-destructive hover:bg-destructive/5'
                      disabled={isStreaming || isRetrying}
                      onClick={() => onRetryMessage(message)}
                    >
                      <RotateCcw className='mr-2 h-3 w-3' />
                      {isRetrying ? '重试中...' : '重新发送'}
                    </Button>
                  </div>
                ) : null}

                {message.citations?.length > 0 ? (
                  <div className='mt-1 flex max-w-3xl flex-wrap gap-2 pr-4'>
                    <div className='flex items-center gap-1.5 px-1 py-1 text-[10px] text-blue-700/80'>
                      <Database className='h-3 w-3 text-primary' /> 引用来源
                    </div>
                    {message.citations.map((citation) => (
                      <div
                        key={citation.id}
                        className='flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50/70 px-2.5 py-1.5 text-[11px] text-blue-800 transition-colors hover:bg-blue-100'
                      >
                        <div className='h-2 w-2 rounded-full bg-primary/45' />
                        <span className='line-clamp-1 max-w-[180px]'>{citation.source_anchor || citation.snippet || 'Knowledge Segment'}</span>
                      </div>
                    ))}
                  </div>
                ) : null}

                {isAssistant ? (
                  <DebugContextPanel message={message} />
                ) : null}
              </div>
            </div>
          )
        })}

        {(messages.length === 0 && !isLoading) ? (
          <div className='flex h-[380px] flex-col items-center justify-center rounded-3xl border border-dashed border-blue-200 bg-white px-8 text-center animate-in fade-in zoom-in-95 duration-500'>
            <div className='mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-600'>
              <MessageSquare className='h-8 w-8' />
            </div>
            <div className='text-2xl font-semibold tracking-tight text-blue-900'>Genesis AI Chat</div>
            <div className='mt-3 max-w-xs text-[13px] leading-relaxed text-blue-800/80'>
              准备就绪。Genesis AI 将结合您的私有知识库，通过深度检索为您提供专业、可溯源的 AI 问答服务。
            </div>
            <div className='mt-7 flex gap-2'>
              <div className='h-1 w-5 rounded-full bg-blue-200' />
              <div className='h-1 w-9 rounded-full bg-blue-500/70' />
              <div className='h-1 w-5 rounded-full bg-blue-200' />
            </div>
          </div>
        ) : null}

        <div ref={bottomRef} className='h-4' />
      </div>
    </div>
  )
}

function DebugContextPanel({ message }: { message: ChatMessage }) {
  const [debugDrawerOpen, setDebugDrawerOpen] = useState(false)
  const metadata = (message.metadata || {}) as Record<string, any>
  const persistentContext = (metadata.persistent_context || {}) as Record<string, any>
  const retrievalContext = (metadata.retrieval_context || {}) as Record<string, any>
  const llmPromptContext = (retrievalContext.llm_prompt_context || {}) as Record<string, any>
  const pipelineTraces = Array.isArray(retrievalContext.pipeline_traces) ? retrievalContext.pipeline_traces : []
  const filterInheritance = (metadata.filter_inheritance || retrievalContext.filter_inheritance || {}) as Record<string, any>
  const filterInheritanceEvaluation = (filterInheritance.effect_evaluation || {}) as Record<string, any>
  const kbContexts = Array.isArray(persistentContext.kb_contexts) ? persistentContext.kb_contexts : []
  const docContexts = Array.isArray(persistentContext.doc_contexts) ? persistentContext.doc_contexts : []
  const glossaryEntries = Array.isArray(llmPromptContext.glossary_entries) ? llmPromptContext.glossary_entries : []
  const resultHeaders = Array.isArray(llmPromptContext.result_headers) ? llmPromptContext.result_headers : []
  const filterInheritanceEnabled = filterInheritance.enabled !== false
  const filterDecisionCount = typeof filterInheritance.decision_count === 'number' ? filterInheritance.decision_count : 0
  const filterAppliedKbCount = typeof filterInheritance.applied_kb_count === 'number' ? filterInheritance.applied_kb_count : 0
  const filterEvaluationEnabled = Boolean(filterInheritanceEvaluation.enabled)

  if (kbContexts.length === 0 && docContexts.length === 0 && glossaryEntries.length === 0 && resultHeaders.length === 0 && !filterInheritance.status && !filterEvaluationEnabled && pipelineTraces.length === 0) {
    return null
  }

  return (
    <details className='mt-2 max-w-3xl rounded-xl border border-blue-200 bg-blue-50/70 px-3 py-2 text-xs text-blue-800/90'>
      <summary className='cursor-pointer select-none font-semibold text-blue-700'>
        本轮补充上下文
      </summary>
      <div className='mt-2 space-y-2'>
        {kbContexts.length > 0 ? (
          <div className='space-y-1'>
            <div className='font-medium text-blue-700'>知识库级</div>
            <div className='flex flex-wrap gap-2'>
              {kbContexts.map((item: Record<string, any>, index: number) => (
                <span key={`${item.kb_id || 'kb'}-${index}`} className='rounded-full bg-blue-500/10 px-2 py-1 text-[11px] text-blue-700'>
                  {item.kb_name || item.kb_id || '当前知识库'}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {docContexts.length > 0 ? (
          <div className='space-y-1'>
            <div className='font-medium text-blue-700'>文档级</div>
            <div className='flex flex-wrap gap-2'>
              {docContexts.map((item: Record<string, any>, index: number) => (
                <span key={`${item.kb_doc_id || 'doc'}-${index}`} className='rounded-full bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-700'>
                  {item.document_name || item.kb_doc_id || '命中文档'}
                  {item.source === 'kb_doc.summary' ? ' · 摘要回退' : ''}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {glossaryEntries.length > 0 || resultHeaders.length > 0 ? (
          <div className='space-y-1'>
            <div className='font-medium text-blue-700'>回答阶段上下文</div>
            <div className='flex flex-wrap gap-2'>
              {glossaryEntries.length > 0 ? (
                <span className='rounded-full bg-cyan-100 px-2 py-1 text-[11px] text-cyan-700'>
                  术语说明: {glossaryEntries.length}
                </span>
              ) : null}
              {resultHeaders.length > 0 ? (
                <span className='rounded-full bg-indigo-100 px-2 py-1 text-[11px] text-indigo-700'>
                  结构化头信息: {resultHeaders.length}
                </span>
              ) : null}
            </div>
          </div>
        ) : null}

        {filterInheritance.status ? (
          <div className='space-y-1'>
            <div className='font-medium text-blue-700'>范围延续</div>
            <div className='flex flex-wrap gap-2'>
              <span className='rounded-full bg-violet-500/10 px-2 py-1 text-[11px] text-violet-700'>
                {filterInheritanceEnabled ? '已启用' : '已关闭'}
              </span>
              <span className='rounded-full bg-blue-100 px-2 py-1 text-[11px] text-blue-700'>
                状态: {String(filterInheritance.status)}
              </span>
              {filterDecisionCount > 0 ? (
                <span className='rounded-full bg-blue-100 px-2 py-1 text-[11px] text-blue-700'>
                  决策知识库: {filterDecisionCount}
                </span>
              ) : null}
              {filterAppliedKbCount > 0 ? (
                <span className='rounded-full bg-blue-100 px-2 py-1 text-[11px] text-blue-700'>
                  实际延续: {filterAppliedKbCount}
                </span>
              ) : null}
              {filterInheritance.previous_query ? (
                <span className='rounded-full bg-blue-100 px-2 py-1 text-[11px] text-blue-700'>
                  上一轮: {String(filterInheritance.previous_query)}
                </span>
              ) : null}
            </div>
          </div>
        ) : null}

        {filterEvaluationEnabled ? (
          <div className='space-y-1'>
            <div className='font-medium text-blue-700'>延续收益评估</div>
            <div className='flex flex-wrap gap-2'>
              {typeof filterInheritanceEvaluation.evaluated_kb_count === 'number' ? (
                <span className='rounded-full bg-amber-500/10 px-2 py-1 text-[11px] text-amber-700'>
                  评估知识库: {filterInheritanceEvaluation.evaluated_kb_count}
                </span>
              ) : null}
              {typeof filterInheritanceEvaluation.positive_kb_count === 'number' ? (
                <span className='rounded-full bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-700'>
                  正向: {filterInheritanceEvaluation.positive_kb_count}
                </span>
              ) : null}
              {typeof filterInheritanceEvaluation.neutral_kb_count === 'number' ? (
                <span className='rounded-full bg-cyan-100 px-2 py-1 text-[11px] text-cyan-700'>
                  持平: {filterInheritanceEvaluation.neutral_kb_count}
                </span>
              ) : null}
              {typeof filterInheritanceEvaluation.negative_kb_count === 'number' ? (
                <span className='rounded-full bg-rose-500/10 px-2 py-1 text-[11px] text-rose-700'>
                  负向: {filterInheritanceEvaluation.negative_kb_count}
                </span>
              ) : null}
              {typeof filterInheritanceEvaluation.avg_hit_delta === 'number' ? (
                <span className='rounded-full bg-blue-100 px-2 py-1 text-[11px] text-blue-700'>
                  平均结果变化: {filterInheritanceEvaluation.avg_hit_delta > 0 ? '+' : ''}{filterInheritanceEvaluation.avg_hit_delta.toFixed(2)}
                </span>
              ) : null}
              {typeof filterInheritanceEvaluation.avg_score_delta === 'number' ? (
                <span className='rounded-full bg-blue-100 px-2 py-1 text-[11px] text-blue-700'>
                  平均分变化: {filterInheritanceEvaluation.avg_score_delta > 0 ? '+' : ''}{filterInheritanceEvaluation.avg_score_delta.toFixed(2)}
                </span>
              ) : null}
            </div>
          </div>
        ) : null}

        {pipelineTraces.length > 0 ? (
          <div className='flex flex-wrap items-center gap-2 pt-1'>
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='h-7 rounded-full border-blue-200 bg-blue-50 px-3 text-[11px] font-bold text-blue-700 hover:bg-blue-100'
              onClick={() => setDebugDrawerOpen(true)}
            >
              查看检索诊断详情
            </Button>
            <span className='text-[11px] text-blue-700/80'>
              已记录 {pipelineTraces.length} 个知识库检索链路
            </span>
          </div>
        ) : null}
      </div>
      <ChatRetrievalDebugDrawer
        open={debugDrawerOpen}
        onOpenChange={setDebugDrawerOpen}
        message={message}
        pipelineTraces={pipelineTraces}
        retrievalContext={retrievalContext}
      />
    </details>
  )
}

function ChatRetrievalDebugDrawer({
  open,
  onOpenChange,
  message,
  pipelineTraces,
  retrievalContext,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  message: ChatMessage
  pipelineTraces: Array<Record<string, any>>
  retrievalContext: Record<string, any>
}) {
  return (
    <RetrievalDebugSheet
      open={open}
      onOpenChange={onOpenChange}
      title='聊天检索诊断'
      description='本轮回答关联的知识库检索链路，包含问题改写、过滤、召回和评分拆解。'
      widthClassName='sm:max-w-[820px]'
    >
        <div className='space-y-5 p-6'>
          <div className='rounded-3xl border border-blue-200 bg-blue-50/70 p-5 shadow-sm'>
            <div className='text-xs uppercase tracking-[0.24em] text-blue-700'>Assistant Message</div>
            <div className='mt-2 text-sm text-blue-700'>消息状态: {message.status}</div>
            <div className='mt-4 grid gap-3 sm:grid-cols-3'>
              <RetrievalDebugStat label='知识库数' value={retrievalContext.knowledge_bases?.length ?? pipelineTraces.length} tone='cyan' />
              <RetrievalDebugStat label='总结果数' value={retrievalContext.result_count} tone='emerald' />
              <RetrievalDebugStat label='入选上下文' value={retrievalContext.selected_count} tone='amber' />
            </div>
          </div>

          {pipelineTraces.map((entry, index) => {
            const trace = (entry.pipeline_trace || {}) as Record<string, any>
            const queryAnalysisItems = Array.isArray(retrievalContext.query_analysis) ? retrievalContext.query_analysis : []
            const matchedQueryAnalysis = (queryAnalysisItems.find((item) => String(item?.kb_id || '') === String(entry.kb_id || '')) || queryAnalysisItems[index] || {}) as Record<string, any>
            const traceInput = (trace.input || {}) as Record<string, any>
            const traceConfig = (trace.config || {}) as Record<string, any>
            const normalizedConfig = (traceConfig.normalized_config || {}) as Record<string, any>
            const traceFilters = (trace.filters || {}) as Record<string, any>
            const traceRetrieval = (trace.retrieval || {}) as Record<string, any>
            const traceFusion = (trace.fusion || {}) as Record<string, any>
            const traceResults = (trace.results || {}) as Record<string, any>
            const lexicalQueryDebug = (traceRetrieval.lexical_query_debug || entry.lexical_query_debug || {}) as Record<string, any>
            const candidateBreakdown = (matchedQueryAnalysis.candidate_breakdown || {}) as Record<string, any>
            const ruleCandidates = Array.isArray(candidateBreakdown.rule_candidates) ? candidateBreakdown.rule_candidates : []
            const llmCandidates = Array.isArray(candidateBreakdown.llm_candidates) ? candidateBreakdown.llm_candidates : []
            const correctedRuleCandidates = Array.isArray(candidateBreakdown.corrected_rule_candidates) ? candidateBreakdown.corrected_rule_candidates : []
            const folderRuleCandidates = filterCandidatesByType(ruleCandidates, 'folder_id')
            const folderLlmCandidates = filterCandidatesByType(llmCandidates, 'folder_id')
            const correctedFolderCandidates = filterCandidatesByType(correctedRuleCandidates, 'folder_id')
            const llmDebug = (matchedQueryAnalysis.llm_debug || {}) as Record<string, any>
            const queryRewriteDebug = (matchedQueryAnalysis.query_rewrite_debug || {}) as Record<string, any>
            const llmPromptContext = (retrievalContext.llm_prompt_context || {}) as Record<string, any>
            const llmPromptKbContexts = Array.isArray(llmPromptContext.kb_contexts) ? llmPromptContext.kb_contexts : []
            const llmPromptDocContexts = Array.isArray(llmPromptContext.doc_contexts) ? llmPromptContext.doc_contexts : []
            const llmPromptGlossaryEntries = Array.isArray(llmPromptContext.glossary_entries) ? llmPromptContext.glossary_entries : []
            const llmPromptResultHeaders = Array.isArray(llmPromptContext.result_headers) ? llmPromptContext.result_headers : []
            const stopwordHits = asDebugStringList(lexicalQueryDebug.stopword_hits)
            const stopwordCount = Number(lexicalQueryDebug.stopword_count || 0)
            const lexicalHits = Array.isArray(traceRetrieval.lexical_hits) ? traceRetrieval.lexical_hits : []
            const vectorHits = Array.isArray(traceRetrieval.vector_hits) ? traceRetrieval.vector_hits : []
            const resultItems = Array.isArray(traceResults.items) ? traceResults.items : []

            return (
              <section key={`${String(entry.kb_id || 'kb')}-${index}`} className='rounded-3xl border border-blue-200 bg-blue-50/55 p-5 shadow-sm'>
                <div className='flex flex-wrap items-start justify-between gap-3'>
                  <div>
                    <div className='text-xs uppercase tracking-[0.2em] text-primary'>Knowledge Base</div>
                    <div className='mt-1 text-lg font-semibold text-blue-900'>{String(entry.kb_name || entry.kb_id || '未命名知识库')}</div>
                    <div className='mt-1 text-xs text-blue-700/75'>绑定角色: {String(entry.binding_role || 'default')}</div>
                  </div>
                  <div className='flex gap-2'>
                    <RetrievalDebugStat label='向量' value={traceRetrieval.vector_hit_count} tone='emerald' compact />
                    <RetrievalDebugStat label='全文' value={traceRetrieval.lexical_hit_count} tone='amber' compact />
                    <RetrievalDebugStat label='结果' value={traceResults.item_count} tone='cyan' compact />
                  </div>
                </div>

                <div className='mt-5 grid gap-4 lg:grid-cols-2'>
                  <RetrievalDebugSection title='问题链路' className='mt-4 rounded-2xl'>
                    <RetrievalDebugRow label='原始输入' value={String(traceInput.raw_query || '无')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='独立问题' value={String(traceInput.standalone_query || matchedQueryAnalysis.standalone_query || traceInput.raw_query || '未改写')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='改写后' value={String(traceInput.rewritten_query || '未改写')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='全文查询' value={String(traceInput.lexical_query || '无')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow
                      label='命中停用词'
                      value={stopwordHits.length > 0 ? `${stopwordHits.join('、')}（词表 ${stopwordCount} 项）` : `无（词表 ${stopwordCount} 项）`}
                      labelWidthClassName='sm:grid-cols-[92px_1fr]'
                      textSizeClassName='text-xs'
                    />
                    <RetrievalDebugRow label='发生改写' value={traceInput.query_rewritten ? '是' : '否'} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                  </RetrievalDebugSection>

                  <RetrievalDebugSection title='策略配置' className='mt-4 rounded-2xl'>
                    <RetrievalDebugRow label='向量范围' value={Array.isArray(normalizedConfig.vector_scopes) ? normalizedConfig.vector_scopes.join(' / ') : '无'} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='全文范围' value={Array.isArray(normalizedConfig.lexical_scopes) ? normalizedConfig.lexical_scopes.join(' / ') : '无'} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='向量权重' value={formatRetrievalDebugNumber(normalizedConfig.vector_weight)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='重排模型' value={String(normalizedConfig.rerank_model || '未启用')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                  </RetrievalDebugSection>
                </div>

                <div className='mt-4 grid gap-4 lg:grid-cols-2'>
                  <RetrievalDebugSection title='过滤结果' className='mt-4 rounded-2xl'>
                    {(() => {
                      const explicitFilters = (traceFilters.explicit_filters || {}) as Record<string, any>
                      const resolvedFilters = (traceFilters.resolved_filters || {}) as Record<string, any>
                      const expressionDebug = (resolvedFilters.expression_debug || {}) as Record<string, any>
                      return (
                        <div className='space-y-3'>
                          <div className='rounded-xl border border-slate-200 bg-slate-50/70 p-3'>
                            <div className='mb-2 text-[11px] font-semibold text-slate-700'>请求侧 · 显式过滤</div>
                            <RetrievalDebugRow label='文件夹' value={formatDebugIdList(explicitFilters.folder_ids)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='文档标签' value={formatDebugIdList(explicitFilters.tag_ids)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='文件夹标签' value={formatDebugIdList(explicitFilters.folder_tag_ids)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='kb 文档' value={formatDebugIdList(explicitFilters.kb_doc_ids)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='业务文档' value={formatDebugIdList(explicitFilters.document_ids)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='文档元数据' value={formatDebugRecord(explicitFilters.document_metadata)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs break-all' />
                            <RetrievalDebugRow label='单元元数据' value={formatDebugRecord(explicitFilters.search_unit_metadata)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs break-all' />
                            <RetrievalDebugRow label='统一表达式' value={formatDebugRecord(explicitFilters.filter_expression)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs break-all' />
                          </div>

                          <div className='rounded-xl border border-indigo-200 bg-indigo-50/60 p-3'>
                            <div className='mb-2 text-[11px] font-semibold text-indigo-800'>落地侧 · 候选解析结果</div>
                            <RetrievalDebugRow label='已应用过滤' value={resolvedFilters.filter_applied === true ? '是' : resolvedFilters.filter_applied === false ? '否' : '—'} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='解析 kb 文档' value={formatDebugIdList(resolvedFilters.kb_doc_ids)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='解析业务文档' value={formatDebugIdList(resolvedFilters.document_ids)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='解析内容组' value={formatDebugIdList(resolvedFilters.content_group_ids)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                            <RetrievalDebugRow label='解析表达式' value={formatDebugRecord(resolvedFilters.filter_expression)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs break-all' />
                            <RetrievalDebugRow
                              label='表达式状态'
                              value={[
                                expressionDebug.requested ? '请求中有表达式' : '请求中无表达式',
                                expressionDebug.resolved ? '已归一化' : '',
                                expressionDebug.document_scope_applied ? '文档层已参与' : '',
                                expressionDebug.search_unit_scope_applied ? '搜索单元层已参与' : '',
                              ].filter(Boolean).join(' · ') || '—'}
                              labelWidthClassName='sm:grid-cols-[92px_1fr]'
                              textSizeClassName='text-xs break-all'
                            />
                          </div>
                        </div>
                      )
                    })()}
                  </RetrievalDebugSection>

                  <RetrievalDebugSection title='融合概览' className='mt-4 rounded-2xl'>
                    <RetrievalDebugRow label='融合分组数' value={formatRetrievalDebugNumber(traceFusion.grouped_hit_count)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='最终结果数' value={formatRetrievalDebugNumber(traceResults.item_count)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                  </RetrievalDebugSection>
                </div>

                <div className='mt-4 grid gap-4 lg:grid-cols-2'>
                  <RetrievalDebugSection title='查询分析分层' className='mt-4 rounded-2xl'>
                    <RetrievalDebugRow label='规则候选' value={String(ruleCandidates.length)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='LLM 候选' value={String(llmCandidates.length)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='纠偏规则' value={String(correctedRuleCandidates.length)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='目录候选' value={`${folderRuleCandidates.length} / ${folderLlmCandidates.length} / ${correctedFolderCandidates.length}`} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='改写后问题' value={String(matchedQueryAnalysis.rewritten_query || traceInput.rewritten_query || '未改写')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                  </RetrievalDebugSection>

                  <RetrievalDebugSection title='LLM 表达式' className='mt-4 rounded-2xl'>
                    <RetrievalDebugRow label='是否参与' value={Object.keys(llmDebug).length > 0 ? '是' : '否'} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='候选状态' value={`${llmDebug.validated_candidate_count ?? 0}/${llmDebug.rejected_candidate_count ?? 0}/${llmDebug.conflict_candidate_count ?? 0}`} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='升级硬过滤' value={String(llmDebug.upgraded_candidate_count ?? 0)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='表达式合并' value={String(llmDebug.filter_expression_merge_mode || '无')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                  </RetrievalDebugSection>
                </div>

                {Object.keys(queryRewriteDebug).length > 0 ? (
                  <RetrievalDebugSection title='查询改写诊断' className='mt-4 rounded-2xl'>
                    <RetrievalDebugRow label='状态' value={String(queryRewriteDebug.status || 'unknown')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='改写原因' value={String(queryRewriteDebug.rewrite_reason || queryRewriteDebug.reason || '—')} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='历史上下文数' value={String(queryRewriteDebug.history_count ?? 0)} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow label='目录建议' value={queryRewriteDebug.folder_routing_enabled ? '启用' : '未启用'} labelWidthClassName='sm:grid-cols-[92px_1fr]' textSizeClassName='text-xs' />
                    <RetrievalDebugRow
                      label='主 / 次目录候选'
                      value={`${Array.isArray(queryRewriteDebug.folder_routing_hints?.primary_folder_candidates) ? queryRewriteDebug.folder_routing_hints.primary_folder_candidates.length : 0} / ${Array.isArray(queryRewriteDebug.folder_routing_hints?.secondary_folder_candidates) ? queryRewriteDebug.folder_routing_hints.secondary_folder_candidates.length : 0}`}
                      labelWidthClassName='sm:grid-cols-[92px_1fr]'
                      textSizeClassName='text-xs'
                    />
                  </RetrievalDebugSection>
                ) : null}

                {folderRuleCandidates.length > 0 || correctedFolderCandidates.length > 0 || folderLlmCandidates.length > 0 ? (
                  <RetrievalDebugSection title='目录候选命中（文件夹名称 / 路径）' className='mt-4 rounded-2xl'>
                    {folderRuleCandidates.length > 0 ? (
                      <div className='mb-4'>
                        <div className='mb-2 text-xs font-medium text-slate-700'>规则目录候选</div>
                        <RetrievalDebugCandidateSummaryList candidates={folderRuleCandidates} emptyText='无规则目录候选' />
                      </div>
                    ) : null}
                    {correctedFolderCandidates.length > 0 ? (
                      <div className='mb-4'>
                        <div className='mb-2 text-xs font-medium text-slate-700'>被 LLM 纠偏的目录候选</div>
                        <RetrievalDebugCandidateSummaryList candidates={correctedFolderCandidates} emptyText='无被纠偏目录候选' />
                      </div>
                    ) : null}
                    {folderLlmCandidates.length > 0 ? (
                      <div>
                        <div className='mb-2 text-xs font-medium text-slate-700'>LLM 目录候选</div>
                        <RetrievalDebugCandidateSummaryList candidates={folderLlmCandidates} emptyText='无 LLM 目录候选' />
                      </div>
                    ) : null}
                  </RetrievalDebugSection>
                ) : null}

                {ruleCandidates.length > 0 || correctedRuleCandidates.length > 0 || llmCandidates.length > 0 || llmDebug.filter_expression ? (
                  <RetrievalDebugSection title='查询分析详情' className='mt-4 rounded-2xl'>
                    {ruleCandidates.length > 0 ? (
                      <div className='mb-4'>
                        <div className='mb-2 text-xs font-medium text-slate-700'>规则候选</div>
                        <RetrievalDebugJsonBlock value={ruleCandidates} />
                      </div>
                    ) : null}
                    {correctedRuleCandidates.length > 0 ? (
                      <div className='mb-4'>
                        <div className='mb-2 text-xs font-medium text-slate-700'>被 LLM 纠偏的规则候选</div>
                        <RetrievalDebugJsonBlock value={correctedRuleCandidates} />
                      </div>
                    ) : null}
                    {llmCandidates.length > 0 ? (
                      <div className='mb-4'>
                        <div className='mb-2 text-xs font-medium text-slate-700'>LLM 候选</div>
                        <RetrievalDebugJsonBlock value={llmCandidates} />
                      </div>
                    ) : null}
                    {llmDebug.filter_expression ? (
                      <div>
                        <div className='mb-2 text-xs font-medium text-slate-700'>LLM 统一过滤表达式</div>
                        <RetrievalDebugJsonBlock value={llmDebug.filter_expression} />
                      </div>
                    ) : null}
                  </RetrievalDebugSection>
                ) : null}

                {llmPromptKbContexts.length > 0 || llmPromptDocContexts.length > 0 || llmPromptGlossaryEntries.length > 0 || llmPromptResultHeaders.length > 0 ? (
                  <RetrievalDebugSection title='回答 LLM 上下文' className='mt-4 rounded-2xl'>
                    {llmPromptResultHeaders.length > 0 ? (
                      <div className='mb-4'>
                        <div className='mb-2 text-xs font-medium text-slate-700'>命中结果结构化头信息</div>
                        <div className='space-y-2'>
                          {llmPromptResultHeaders.map((item: Record<string, any>, headerIndex: number) => {
                            const promptHeader = (item.prompt_header || {}) as Record<string, any>
                            const docTags = Array.isArray(promptHeader.doc_tags) ? promptHeader.doc_tags : []
                            const folderTags = Array.isArray(promptHeader.folder_tags) ? promptHeader.folder_tags : []
                            const metadataSummary = (promptHeader.metadata || {}) as Record<string, any>
                            return (
                              <div key={`${String(item.title || 'header')}-${headerIndex}`} className='rounded-xl border border-slate-200 bg-slate-50/70 p-3'>
                                <div className='flex items-start justify-between gap-3'>
                                  <div className='text-sm font-medium text-slate-800'>
                                    [{String(item.rank || headerIndex + 1)}] {String(item.title || item.document_name || '未命名文档')}
                                  </div>
                                  <div className='font-mono text-xs text-slate-500'>{formatRetrievalDebugNumber(item.score)}</div>
                                </div>
                                <div className='mt-2 space-y-1 text-xs text-slate-700'>
                                  <div>命中域: {Array.isArray(item.matched_scopes) && item.matched_scopes.length > 0 ? item.matched_scopes.join(' / ') : 'default'}</div>
                                  {docTags.length > 0 ? <div>文档标签: {docTags.join('、')}</div> : null}
                                  {folderTags.length > 0 ? <div>文件夹业务标签: {folderTags.join('、')}</div> : null}
                                  {Object.keys(metadataSummary).length > 0 ? <div>文档元数据: {formatDebugRecord(metadataSummary)}</div> : null}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    ) : null}

                    {llmPromptDocContexts.length > 0 ? (
                      <div className='mb-4'>
                        <div className='mb-2 text-xs font-medium text-slate-700'>文档补充背景</div>
                        <div className='space-y-2'>
                          {llmPromptDocContexts.map((item: Record<string, any>, contextIndex: number) => (
                            <div key={`${String(item.kb_doc_id || 'docctx')}-${contextIndex}`} className='rounded-xl border border-emerald-200 bg-emerald-50/60 p-3'>
                              <div className='text-sm font-medium text-emerald-800'>
                                {String(item.document_name || '命中文档')}
                                {item.source === 'kb_doc.summary' ? ' · 摘要背景' : item.source === 'doc_persistent_context' ? ' · 文档持久上下文' : ''}
                              </div>
                              <div className='mt-1 text-xs text-emerald-700/80'>{String(item.content_preview || '无')}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {llmPromptKbContexts.length > 0 ? (
                      <div className='mb-4'>
                        <div className='mb-2 text-xs font-medium text-slate-700'>知识库补充背景</div>
                        <div className='space-y-2'>
                          {llmPromptKbContexts.map((item: Record<string, any>, contextIndex: number) => (
                            <div key={`${String(item.kb_id || 'kbctx')}-${contextIndex}`} className='rounded-xl border border-cyan-200 bg-cyan-50/60 p-3'>
                              <div className='text-sm font-medium text-cyan-800'>{String(item.kb_name || item.kb_id || '当前知识库')}</div>
                              <div className='mt-1 text-xs text-cyan-700/80'>{String(item.content_preview || '无')}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {llmPromptGlossaryEntries.length > 0 ? (
                      <div>
                        <div className='mb-2 text-xs font-medium text-slate-700'>术语说明</div>
                        <div className='space-y-2'>
                          {llmPromptGlossaryEntries.map((item: Record<string, any>, glossaryIndex: number) => (
                            <div key={`${String(item.term || 'term')}-${glossaryIndex}`} className='rounded-xl border border-indigo-200 bg-indigo-50/60 p-3'>
                              <div className='text-sm font-medium text-indigo-800'>
                                {String(item.term || '术语')}
                                {item.kb_name ? ` · ${String(item.kb_name)}` : ''}
                              </div>
                              <div className='mt-1 text-xs text-indigo-700/80'>{String(item.definition || '无')}</div>
                              {String(item.examples || '').trim() ? (
                                <div className='mt-1 text-xs text-indigo-700/70'>示例: {String(item.examples)}</div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </RetrievalDebugSection>
                ) : null}

                <RetrievalDebugSection title='召回命中' className='mt-4 rounded-2xl'>
                  <div className='grid gap-3 lg:grid-cols-2'>
                    <RetrievalHitList title='向量召回' hits={vectorHits} maxItems={5} />
                    <RetrievalHitList title='全文召回' hits={lexicalHits} maxItems={5} />
                  </div>
                </RetrievalDebugSection>

                <RetrievalDebugSection title='最终结果评分' className='mt-4 rounded-2xl'>
                  <div className='space-y-2'>
                    {resultItems.slice(0, 5).map((item: Record<string, any>, itemIndex: number) => (
                      <div key={`${String(item.id || 'item')}-${itemIndex}`} className='rounded-2xl border border-blue-200 bg-blue-50/55 p-3'>
                        <div className='flex items-start justify-between gap-3'>
                          <div>
                            <div className='text-sm font-medium text-blue-900'>{String(item.title || item.id || '结果')}</div>
                            <div className='mt-1 text-xs text-blue-700/80'>投影: {Array.isArray(item.matched_scopes) ? item.matched_scopes.join(' / ') : '无'}</div>
                          </div>
                          <div className='font-mono text-sm text-primary'>{formatRetrievalDebugNumber(item.score)}</div>
                        </div>
                        <div className='mt-2 grid gap-2 text-xs text-blue-800/80 sm:grid-cols-3'>
                          <span>向量: {formatRetrievalDebugNumber(item.vector_score)}</span>
                          <span>全文: {formatRetrievalDebugNumber(item.keyword_score)}</span>
                          <span>重排: {formatRetrievalDebugNumber(item.score_trace?.rerank_score)}</span>
                        </div>
                      </div>
                    ))}
                    {resultItems.length === 0 ? <div className='text-sm text-blue-700/80'>没有最终结果。</div> : null}
                  </div>
                </RetrievalDebugSection>

                <details className='mt-4 rounded-2xl border border-blue-200 bg-blue-50/70 p-3'>
                  <summary className='cursor-pointer text-sm font-semibold text-blue-700'>查看原始 JSON</summary>
                  <div className='mt-3'>
                    <RetrievalDebugJsonBlock value={entry} />
                  </div>
                </details>
              </section>
            )
          })}

          {pipelineTraces.length === 0 ? (
            <div className='rounded-3xl border border-blue-200 bg-blue-50/60 p-6 text-sm text-blue-700'>
              当前消息没有记录检索诊断。请确认后端已重启并且本轮聊天启用了知识库检索。
            </div>
          ) : null}
        </div>
    </RetrievalDebugSheet>
  )
}

function asDebugStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item).trim()).filter(Boolean) : []
}

function filterCandidatesByType(candidates: unknown, filterType: string) {
  const source = Array.isArray(candidates) ? candidates : []
  return source.filter((item) => String((item as Record<string, any>)?.filter_type || '').trim() === filterType) as Array<Record<string, any>>
}

function formatDebugIdList(value: unknown): string {
  const items = Array.isArray(value) ? value.map((item) => String(item).trim()).filter(Boolean) : []
  return items.length > 0 ? items.join('、') : '无'
}

function formatDebugRecord(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return '无'
  }
  const record = value as Record<string, unknown>
  if (Object.keys(record).length === 0) {
    return '无'
  }
  try {
    return JSON.stringify(record)
  }
  catch {
    return String(value)
  }
}
