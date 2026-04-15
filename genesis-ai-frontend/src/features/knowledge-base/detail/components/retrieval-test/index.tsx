import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Search } from 'lucide-react'
import { toast } from 'sonner'
import {
  fetchKnowledgeBase,
  runKnowledgeBaseRetrievalTest,
  updateKnowledgeBase,
  type KnowledgeBase,
} from '@/lib/api/knowledge-base'
import { DEFAULT_RETRIEVAL_TEST_CONFIG } from './constants'
import { RetrievalTestQueryBox } from './retrieval-test-query-box'
import { RetrievalTestResults } from './retrieval-test-results'
import { RetrievalTestSettingsPanel } from './retrieval-test-settings-panel'
import type { RetrievalTestPageProps, RetrievalTestRunState } from './types'
import {
  buildConfigFromFormState,
  buildFormStateFromConfig,
  buildRetrievalTestRequest,
  isSameConfig,
  validateRetrievalTestFormState,
} from './utils'

function getSavedRetrievalTestConfig(kb?: KnowledgeBase) {
  const retrievalTestConfig = kb?.retrieval_config?.retrieval_test ?? {}
  const queryAnalysisConfig = kb?.retrieval_config?.query_analysis ?? {}
  return {
    ...DEFAULT_RETRIEVAL_TEST_CONFIG,
    ...queryAnalysisConfig,
    ...retrievalTestConfig,
  }
}

interface RetrievalTestEditorProps {
  kb: KnowledgeBase
}

function formatRunTimeLabel(run?: RetrievalTestRunState | null) {
  if (!run) {
    return '未执行'
  }
  if (!run.executedAt) {
    return run.mode === 'mock' ? '模拟数据' : '刚刚执行'
  }
  const date = new Date(run.executedAt)
  if (Number.isNaN(date.getTime())) {
    return run.executedAt
  }
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

/** 校验 localStorage 反序列化后的单轮结果结构，避免脏数据导致崩溃 */
function parseStoredRunState(raw: unknown): RetrievalTestRunState | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const obj = raw as Record<string, unknown>
  if (!Array.isArray(obj.items)) {
    return null
  }
  return raw as RetrievalTestRunState
}

function RetrievalTestEditor({ kb }: RetrievalTestEditorProps) {
  const MAX_HISTORY_COUNT = 5
  const queryClient = useQueryClient()
  const kbId = kb.id
  const savedConfig = useMemo(() => getSavedRetrievalTestConfig(kb), [kb])
  const [form, setForm] = useState(() => buildFormStateFromConfig(savedConfig))
  const historyStorageKey = `retrieval-test-history:${kbId}`
  const currentResultStorageKey = `retrieval-test-current:${kbId}`

  const [historyResults, setHistoryResults] = useState<RetrievalTestRunState[]>(() => {
    if (typeof window === 'undefined') {
      return []
    }
    try {
      const rawValue = window.localStorage.getItem(historyStorageKey)
      if (!rawValue) {
        return []
      }
      const parsed = JSON.parse(rawValue)
      return Array.isArray(parsed) ? parsed.slice(0, MAX_HISTORY_COUNT) : []
    }
    catch {
      return []
    }
  })
  const [result, setResult] = useState<RetrievalTestRunState | null>(() => {
    if (typeof window === 'undefined') {
      return null
    }
    try {
      const rawValue = window.localStorage.getItem(currentResultStorageKey)
      if (!rawValue) {
        return null
      }
      return parseStoredRunState(JSON.parse(rawValue))
    }
    catch {
      return null
    }
  })
  const [selectedViewRunId, setSelectedViewRunId] = useState<string | null>(null)
  const configDirty = !isSameConfig(buildConfigFromFormState(form), savedConfig)
  const selectedHistoryResult = useMemo(
    () => historyResults.find((item) => item.runId === selectedViewRunId) || null,
    [historyResults, selectedViewRunId],
  )
  const latestAvailableResult = result || historyResults[0] || null
  const displayResult = selectedHistoryResult || latestAvailableResult
  const compareResult = useMemo(
    () => {
      if (!displayResult) {
        return null
      }
      if (selectedHistoryResult) {
        // 历史轮次作为主视图时，优先与最新结果对比；如果本身就是最新历史，则退化为上一条历史。
        if (result) {
          return result
        }
        const selectedIndex = historyResults.findIndex((item) => item.runId === selectedHistoryResult.runId)
        return selectedIndex >= 0 ? historyResults[selectedIndex + 1] || null : null
      }
      // 最新结果作为主视图时，若无实时结果则与次新历史对比。
      if (result) {
        return historyResults[0] || null
      }
      return historyResults[1] || null
    },
    [displayResult, historyResults, result, selectedHistoryResult],
  )
  const effectiveSelectedRunId = selectedViewRunId ?? (!result ? displayResult?.runId || null : null)

  /** 切换查询轮次时，把该轮次的问题同步到输入框，便于再次检索或微调 */
  const handleSelectViewRunId = (runId: string | null) => {
    setSelectedViewRunId(runId)
    if (runId === null) {
      if (result) {
        setForm((prev) => ({ ...prev, query: result.executedQuery }))
      }
      return
    }
    const run = historyResults.find((item) => item.runId === runId)
    if (run) {
      setForm((prev) => ({ ...prev, query: run.executedQuery }))
    }
  }

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    try {
      window.localStorage.setItem(historyStorageKey, JSON.stringify(historyResults.slice(0, MAX_HISTORY_COUNT)))
    }
    catch {
      // 忽略本地存储异常，避免影响检索测试主流程。
    }
  }, [historyResults, historyStorageKey])

  // 当前轮次仅保存在内存时，刷新页面会丢失；与历史列表一并持久化，避免选历史再查询后“查完就没了”。
  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    try {
      if (result) {
        window.localStorage.setItem(currentResultStorageKey, JSON.stringify(result))
      }
      else {
        window.localStorage.removeItem(currentResultStorageKey)
      }
    }
    catch {
      // 忽略本地存储异常
    }
  }, [result, currentResultStorageKey])

  const saveMutation = useMutation({
    mutationFn: async () => {
      validateRetrievalTestFormState(form)
      return updateKnowledgeBase(kbId, {
        retrieval_config: {
          ...(kb.retrieval_config || {}),
          retrieval_test: buildConfigFromFormState(form),
        },
      })
    },
    onSuccess: async () => {
      toast.success('检索测试配置已保存')
      await queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] })
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.message || error?.response?.data?.detail || error?.message || '保存失败，请重试'
      toast.error(msg)
    },
  })

  const runMutation = useMutation({
    mutationFn: async () => {
      validateRetrievalTestFormState(form)
      const request = buildRetrievalTestRequest(kbId, form)
      if (!request.query) {
        throw new Error('请输入测试问题')
      }
      const response = await runKnowledgeBaseRetrievalTest(request)
      return {
        items: response.items,
        elapsedMs: response.elapsed_ms,
        executedQuery: request.query,
        mode: 'server' as const,
        queryAnalysis: response.query_analysis || null,
        debug: response.debug || null,
        executedAt: new Date().toISOString(),
        runId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      }
    },
    onSuccess: (data) => {
      setHistoryResults((prev) => {
        const next = result ? [result, ...prev] : prev
        return next.slice(0, MAX_HISTORY_COUNT)
      })
      setResult(data)
      setSelectedViewRunId(null)
    },
    onError: (error: any) => {
      const message = error?.response?.data?.message || error?.response?.data?.detail || error?.message || '检索失败，请重试'
      toast.error(message)
    },
  })

  const handleReset = () => {
    setForm((prev) => ({
      ...buildFormStateFromConfig(savedConfig),
      query: prev.query,
      queryRewriteContext: prev.queryRewriteContext,
    }))
  }

  const handleRun = () => {
    runMutation.mutate()
  }

  const handleExportHistory = () => {
    if (typeof window === 'undefined') {
      return
    }
    const payload = {
      kb_id: kbId,
      kb_name: kb.name,
      exported_at: new Date().toISOString(),
      current_result: result,
      history_results: historyResults,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `retrieval-test-history-${kbId}.json`
    anchor.click()
    window.URL.revokeObjectURL(url)
    toast.success('测试记录已导出')
  }

  return (
    <div className='flex h-full flex-col overflow-hidden bg-background/50'>
      <header className='flex items-center justify-between border-b bg-blue-50/30 px-6 py-3 transition-colors duration-300'>
        <div className='flex items-center gap-4'>
          <div className='flex items-center gap-2'>
            <div className='flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100/50 text-blue-600'>
              <Search className='h-4 w-4' />
            </div>
            <h1 className='text-base font-semibold text-blue-700'>知识检索测试</h1>
          </div>
        </div>
      </header>

      <div className='flex min-h-0 flex-1 overflow-hidden rounded-xl border border-blue-100/60 bg-white/50 shadow-sm backdrop-blur-sm'>
        <RetrievalTestSettingsPanel
          kb={kb}
          kbType={kb.type}
          form={form}
          onFormChange={(updater) => setForm(updater)}
          onReset={handleReset}
          onSave={() => saveMutation.mutate()}
          saveDisabled={!configDirty}
          actionDisabled={saveMutation.isPending || runMutation.isPending}
          isSaving={saveMutation.isPending}
        />

        <main className='flex min-w-0 flex-1 overflow-hidden'>
          <aside className='w-72 flex-none border-r border-slate-200/80 bg-slate-50/80 p-4'>
            <div className='mb-4 px-1'>
              <div className='text-base font-semibold tracking-wide text-slate-800'>查询轮次</div>
              <div className='mt-1 text-xs text-slate-500'>可保留最近 5 轮结果，点击左侧条目切换查看。</div>
            </div>
            <div className='space-y-2'>
              {result ? (
                <button
                  type='button'
                  onClick={() => handleSelectViewRunId(null)}
                  className={`w-full rounded-xl border px-3 py-2.5 text-left text-sm shadow-sm transition-all ${
                    effectiveSelectedRunId === null
                      ? 'border-blue-200 bg-blue-50 text-blue-800 shadow-blue-100/60'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-blue-50/40'
                  }`}
                >
                  <div className='flex items-center justify-between gap-2'>
                    <span className='font-medium'>当前轮次</span>
                    <span className='text-[11px] text-muted-foreground'>{result.items.length} 条</span>
                  </div>
                  <div className='mt-1 line-clamp-1 text-xs text-muted-foreground'>{result.executedQuery || '未记录问题'}</div>
                  <div className='mt-1 text-[11px] text-muted-foreground'>{formatRunTimeLabel(result)}</div>
                </button>
              ) : null}
              {historyResults.map((run, index) => {
                const runId = run.runId || null
                const isSelected = effectiveSelectedRunId === runId
                return (
                  <button
                    key={run.runId || `history-run-${index}`}
                    type='button'
                    onClick={() => handleSelectViewRunId(runId)}
                    className={`w-full rounded-xl border px-3 py-2.5 text-left text-sm shadow-sm transition-all ${
                      isSelected
                        ? 'border-blue-200 bg-blue-50 text-blue-800 shadow-blue-100/60'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-blue-50/40'
                    }`}
                  >
                    <div className='flex items-center justify-between gap-2'>
                      <span className='font-medium'>历史第 {index + 1} 轮</span>
                      <span className='text-[11px] text-muted-foreground'>{run.items.length} 条</span>
                    </div>
                    <div className='mt-1 line-clamp-1 text-xs text-muted-foreground'>{run.executedQuery || '未记录问题'}</div>
                    <div className='mt-1 text-[11px] text-muted-foreground'>{formatRunTimeLabel(run)}</div>
                  </button>
                )
              })}
            </div>
          </aside>

          <div className='flex min-w-0 flex-1 flex-col overflow-hidden'>
            <RetrievalTestResults
              result={displayResult}
              isRunning={runMutation.isPending}
              compareResult={compareResult}
              historyResults={historyResults}
              onExportHistory={handleExportHistory}
              finalScoreThreshold={form.finalScoreThreshold}
            />
            <RetrievalTestQueryBox
              query={form.query}
              isRunning={runMutation.isPending}
              onQueryChange={(value) => setForm((prev) => ({ ...prev, query: value }))}
              onSubmit={handleRun}
            />
          </div>
        </main>
      </div>
    </div>
  )
}

export function RetrievalTest({ kbId }: RetrievalTestPageProps) {
  const { data: kb, isLoading } = useQuery({
    queryKey: ['knowledge-base', kbId],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: !!kbId,
  })

  if (isLoading) {
    return (
      <div className='flex h-full min-h-0 items-center justify-center'>
        <div className='flex items-center gap-2 text-sm text-muted-foreground'>
          <Loader2 className='h-4 w-4 animate-spin' />
          正在加载检索测试配置...
        </div>
      </div>
    )
  }

  if (!kb) {
    return (
      <div className='flex h-full min-h-0 items-center justify-center text-sm text-muted-foreground'>
        未获取到知识库信息，暂时无法使用检索测试。
      </div>
    )
  }

  return <RetrievalTestEditor key={`${kbId}:${kb.updated_at}`} kb={kb} />
}
