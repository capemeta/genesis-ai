import { lazy, Suspense, useState, useEffect } from 'react'
import { useParams, Link, useNavigate, useSearch } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { fetchKnowledgeBase, fetchKnowledgeBaseDocuments, getKnowledgeBaseTags, type AttachDocumentsResponse } from '@/lib/api/knowledge-base'
import { ActivityBar, type KBTab } from './components/activity-bar'
import { FileBrowser, FolderTree } from './components/file-manager'
import { RetrievalTest } from './components/retrieval-test'
import { KnowledgeBaseSettings } from './components/global-config/index'
import { TagManagement } from './components/tag-management'
import { GlossaryManagement } from './components/glossary-management'
import { SynonymManagement } from './components/synonym-management'
import { Database, Loader2, ChevronRight, PanelLeft, PanelLeftClose } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getKbTypeMeta } from '@/features/knowledge-base/kb-type-meta'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

const TableManager = lazy(async () => {
  const module = await import('./components/file-manager/file-browser/components/workbenches/table/data-view')
  return { default: module.TableManager }
})

const TableStructureManager = lazy(async () => {
  const module = await import('./components/file-manager/file-browser/components/workbenches/table/structure')
  return { default: module.TableStructureManager }
})

const QADataManager = lazy(async () => {
  const module = await import('./components/file-manager/file-browser/components/workbenches/qa/data-view')
  return { default: module.QADataManager }
})

const QAConfigPanel = lazy(async () => {
  const module = await import('./components/file-manager/file-browser/components/workbenches/qa/config-panel')
  return { default: module.QAConfigPanel }
})

const WebSyncWorkbench = lazy(async () => {
  const module = await import('./components/file-manager/file-browser/components/workbenches/web')
  return { default: module.WebSyncWorkbench }
})

const GeneralWorkbench = lazy(async () => {
  const module = await import('./components/file-manager/file-browser/components/workbenches/general')
  return { default: module.GeneralWorkbench }
})

const AdvancedConfigWorkbench = lazy(async () => {
  const module = await import('./components/file-manager/file-browser/components/workbenches/shared/intelligence')
  return { default: module.AdvancedConfigWorkbench }
})

// 标签颜色映射
const COLOR_MAP: Record<string, { bg: string; text: string; dot: string }> = {
  blue: { bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500' },
  green: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  purple: { bg: 'bg-purple-50', text: 'text-purple-700', dot: 'bg-purple-500' },
  red: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
  yellow: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
  gray: { bg: 'bg-slate-50', text: 'text-slate-700', dot: 'bg-slate-500' },
}

type SharedWorkbenchView = 'intelligence'
type TableWorkbenchView = 'files' | 'data' | 'structure' | SharedWorkbenchView
type QAWorkbenchView = 'files' | 'data' | 'config' | SharedWorkbenchView
type WebWorkbenchView = 'files' | 'web-pages' | 'web-runs' | 'web-sites' | SharedWorkbenchView
type GeneralWorkbenchView = 'files' | 'general-parsing' | SharedWorkbenchView

function resolveInitialActiveTab(initialTab: unknown): KBTab {
  if (initialTab === 'retrieval' || initialTab === 'tags' || initialTab === 'glossary' || initialTab === 'synonyms' || initialTab === 'config') {
    return initialTab
  }
  return 'files'
}

function resolveInitialTableWorkbenchView(initialTab: unknown): TableWorkbenchView {
  if (initialTab === 'data' || initialTab === 'structure' || initialTab === 'files' || initialTab === 'intelligence') {
    return initialTab
  }
  return 'files'
}

function resolveInitialQAWorkbenchView(initialTab: unknown): QAWorkbenchView {
  if (initialTab === 'data' || initialTab === 'files' || initialTab === 'qa-config' || initialTab === 'intelligence') {
    if (initialTab === 'qa-config') {
      return 'config'
    }
    return initialTab
  }
  return 'files'
}

function resolveInitialWebWorkbenchView(initialTab: unknown): WebWorkbenchView {
  if (initialTab === 'files' || initialTab === 'web-pages' || initialTab === 'web-runs' || initialTab === 'web-sites' || initialTab === 'intelligence') {
    return initialTab
  }
  return 'files'
}

function resolveInitialGeneralWorkbenchView(initialTab: unknown): GeneralWorkbenchView {
  if (initialTab === 'files' || initialTab === 'general-parsing' || initialTab === 'intelligence') {
    return initialTab
  }
  return 'files'
}

function TableWorkbenchFallback({ title }: { title: string }) {
  return (
    <div className='flex h-full min-h-0 flex-col bg-background'>
      <div className='border-b px-6 py-3'>
        <div className='flex items-center gap-2'>
          <Loader2 className='h-4 w-4 animate-spin text-muted-foreground' />
          <h2 className='text-lg font-semibold text-foreground'>{title}</h2>
        </div>
      </div>
      <div className='flex-1 px-6 py-5'>
        <div className='mx-auto max-w-[1360px] rounded-xl border bg-card p-4 shadow-sm'>
          <div className='space-y-4'>
            <div className='h-4 w-32 animate-pulse rounded bg-muted' />
            <div className='h-10 w-full animate-pulse rounded-lg bg-muted/80' />
            <div className='h-10 w-full animate-pulse rounded-lg bg-muted/70' />
            <div className='h-10 w-full animate-pulse rounded-lg bg-muted/60' />
          </div>
        </div>
      </div>
    </div>
  )
}

export function KnowledgeBaseDetail() {
  const { folderId } = useParams({ from: '/_top-nav/knowledge-base/$folderId' })
  const search = useSearch({ from: '/_top-nav/knowledge-base/$folderId' })
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<KBTab>(() => resolveInitialActiveTab(search.initialTab))
  const [tableWorkbenchView, setTableWorkbenchView] = useState<TableWorkbenchView>(() =>
    resolveInitialTableWorkbenchView(search.initialTab)
  )
  const [qaWorkbenchView, setQAWorkbenchView] = useState<QAWorkbenchView>(() =>
    resolveInitialQAWorkbenchView(search.initialTab)
  )
  const [webWorkbenchView, setWebWorkbenchView] = useState<WebWorkbenchView>(() =>
    resolveInitialWebWorkbenchView(search.initialTab)
  )
  const [generalWorkbenchView, setGeneralWorkbenchView] = useState<GeneralWorkbenchView>(() =>
    resolveInitialGeneralWorkbenchView(search.initialTab)
  )
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [isFolderTreeCollapsed, setIsFolderTreeCollapsed] = useState(false) // 默认展示文件夹树

  // 获取知识库信息
  const { data: knowledgeBase, isLoading } = useQuery({
    queryKey: ['knowledge-base', folderId],
    queryFn: () => fetchKnowledgeBase(folderId),
    enabled: !!folderId,
  })

  const { data: tableGuideDocuments } = useQuery({
    queryKey: ['kb-documents', folderId, 'table-guide'],
    queryFn: () =>
      fetchKnowledgeBaseDocuments(folderId, {
        page: 1,
        page_size: 1,
      }),
    enabled: !!folderId && knowledgeBase?.type === 'table',
    staleTime: 0,
  })
  const { data: knowledgeBaseTags = [] } = useQuery({
    queryKey: ['kb-tags', folderId, 'detail-header'],
    queryFn: async () => (await getKnowledgeBaseTags(folderId)).tags,
    enabled: !!folderId,
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
  })

  // 快捷键支持: Ctrl+B 切换侧边栏
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        if (activeTab === 'files') {
          e.preventDefault()
          setIsFolderTreeCollapsed(prev => !prev)
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeTab])

  if (isLoading) {
    return (
      <div className='flex items-center justify-center h-[calc(100vh-4rem)]'>
        <div className='flex flex-col items-center gap-2'>
          <Loader2 className='h-8 w-8 animate-spin text-muted-foreground' />
          <p className='text-sm text-muted-foreground'>加载中...</p>
        </div>
      </div>
    )
  }

  if (!knowledgeBase) {
    return (
      <div className='flex items-center justify-center h-[calc(100vh-4rem)]'>
        <div className='flex flex-col items-center gap-2'>
          <Database className='h-12 w-12 text-muted-foreground' />
          <p className='text-sm text-muted-foreground'>知识库不存在</p>
        </div>
      </div>
    )
  }

  const tableColumns = Array.isArray(knowledgeBase.retrieval_config?.table?.schema?.columns)
    ? knowledgeBase.retrieval_config?.table?.schema?.columns
    : []
  const hasTableSchema = tableColumns.length > 0
  const hasAttachedTableDocuments = (tableGuideDocuments?.total ?? 0) > 0
  const tableGuide = knowledgeBase.type === 'table' ? search.tableGuide : undefined
  const shouldShowTableGuideCard = (
    knowledgeBase.type === 'table' &&
    !hasTableSchema &&
    !hasAttachedTableDocuments &&
    activeTab === 'files' &&
    tableWorkbenchView === 'files'
  )
  const shouldShowFolderTree = activeTab === 'files'

  const handleActivityTabChange = (tab: KBTab) => {
    setActiveTab(tab)
    if (tab === 'files') {
      setTableWorkbenchView('files')
      setQAWorkbenchView('files')
      setWebWorkbenchView('files')
      setGeneralWorkbenchView('files')
    }
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId },
      search: {
        initialTab: tab,
        tableGuide: undefined,
      },
      replace: true,
    })
  }

  const handleTableWorkbenchChange = (view: TableWorkbenchView) => {
    setActiveTab('files')
    setTableWorkbenchView(view)
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId },
      search: {
        initialTab: view === 'files' ? 'files' : view,
        tableGuide: undefined,
      },
      replace: true,
    })
  }

  const handleQAWorkbenchChange = (view: QAWorkbenchView) => {
    setActiveTab('files')
    setQAWorkbenchView(view)
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId },
      search: {
        initialTab: view === 'config' ? 'qa-config' : view,
        tableGuide: undefined,
      },
      replace: true,
    })
  }

  const handleWebWorkbenchChange = (view: WebWorkbenchView) => {
    setActiveTab('files')
    setWebWorkbenchView(view)
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId },
      search: {
        initialTab: view,
        tableGuide: undefined,
      },
      replace: true,
    })
  }

  const handleGeneralWorkbenchChange = (view: GeneralWorkbenchView) => {
    setActiveTab('files')
    setGeneralWorkbenchView(view)
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId },
      search: {
        initialTab: view,
        tableGuide: undefined,
      },
      replace: true,
    })
  }

  const handleTableSchemaInitialized = (_payload: AttachDocumentsResponse) => {
    setActiveTab('files')
    setTableWorkbenchView('structure')
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId },
      search: {
        initialTab: 'structure',
        tableGuide: 'schema',
      },
      replace: true,
    })
  }

  const kbTypeMeta = getKbTypeMeta(knowledgeBase.type)
  const KbTypeIcon = kbTypeMeta.Icon

  const handleGuideAction = (guide: 'schema' | 'upload') => {
    if (guide === 'schema') {
      setActiveTab('files')
      setTableWorkbenchView('structure')
      navigate({
        to: '/knowledge-base/$folderId',
        params: { folderId },
        search: {
          initialTab: 'structure',
          tableGuide: 'schema',
        },
        replace: true,
      })
      return
    }

    setActiveTab('files')
    setTableWorkbenchView('files')
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId },
      search: {
        initialTab: 'files',
        tableGuide: 'upload',
      },
      replace: true,
    })
  }

  const handleOpenTagManagement = () => {
    setActiveTab('tags')
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId },
      search: {
        initialTab: 'tags',
        tableGuide: undefined,
      },
      replace: true,
    })
  }

  const renderFolderTreeToggleButton = () => (
    <button
      type='button'
      onClick={() => setIsFolderTreeCollapsed(!isFolderTreeCollapsed)}
      className={cn(
        'inline-flex h-9 w-9 items-center justify-center rounded-lg border transition',
        isFolderTreeCollapsed
          ? 'border-blue-200 bg-blue-50/80 text-blue-600'
          : 'border-border bg-background text-muted-foreground hover:bg-muted'
      )}
      aria-label={isFolderTreeCollapsed ? '展开文件夹侧边栏' : '隐藏文件夹侧边栏'}
      title={isFolderTreeCollapsed ? '展开文件夹侧边栏' : '隐藏文件夹侧边栏'}
    >
      {isFolderTreeCollapsed ? <PanelLeft className='h-4 w-4' /> : <PanelLeftClose className='h-4 w-4' />}
    </button>
  )

  return (
    <div className='flex flex-col h-[calc(100vh-4rem)] w-full overflow-hidden bg-background'>
      {/* 知识库信息头部 - 面包屑导航 */}
      <div className='border-b bg-card px-6 py-3'>
        <div className='flex items-start justify-between gap-4'>
          {/* 左侧：面包屑 + 名称；类型以「分隔线 + 小字说明」呈现，权重低于标题、不抢视觉 */}
          <div className='flex min-w-0 flex-1 flex-col gap-2'>
            <div className='flex min-w-0 max-w-full flex-wrap items-center gap-x-3 gap-y-1.5'>
              <div className='flex min-w-0 max-w-full items-center gap-2'>
                <Link
                  to='/knowledge-base'
                  className='shrink-0 text-sm text-muted-foreground hover:text-foreground transition-colors'
                >
                  知识库
                </Link>
                <ChevronRight className='h-4 w-4 shrink-0 text-muted-foreground' />
                <h1 className='min-w-0 truncate text-lg font-semibold'>{knowledgeBase.name}</h1>
                {knowledgeBaseTags.length > 0 && (
                  <TooltipProvider delayDuration={200}>
                    <div className='flex items-center gap-1.5'>
                      {knowledgeBaseTags.slice(0, 5).map((tag) => {
                        const colorClasses = COLOR_MAP[tag.color || 'blue']
                        return (
                          <button
                            key={tag.id}
                            type='button'
                            onClick={handleOpenTagManagement}
                            className={cn(
                              'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium transition hover:opacity-80',
                              colorClasses.bg,
                              colorClasses.text
                            )}
                            title={tag.name}
                          >
                            <span className={cn('h-1.5 w-1.5 rounded-full', colorClasses.dot)} />
                            <span className='truncate max-w-[80px]'>{tag.name}</span>
                          </button>
                        )
                      })}
                      {knowledgeBaseTags.length > 5 && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type='button'
                              onClick={handleOpenTagManagement}
                              className='inline-flex items-center justify-center rounded px-1.5 py-0.5 text-[11px] font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition'
                            >
                              +{knowledgeBaseTags.length - 5}
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side='bottom' className='max-w-[300px] p-2'>
                            <div className='flex flex-wrap gap-1'>
                              {knowledgeBaseTags.slice(5).map((tag) => {
                                const colorClasses = COLOR_MAP[tag.color || 'blue']
                                return (
                                  <span
                                    key={tag.id}
                                    className={cn(
                                      'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium',
                                      colorClasses.bg,
                                      colorClasses.text
                                    )}
                                  >
                                    <span className={cn('h-1.5 w-1.5 rounded-full', colorClasses.dot)} />
                                    <span>{tag.name}</span>
                                  </span>
                                )
                              })}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                  </TooltipProvider>
                )}
              </div>
            </div>
          </div>
          {/* 右侧：类型、创建者与可见性 */}
          <div className='flex shrink-0 items-center gap-3 text-xs text-muted-foreground'>
            {/* 知识库类型：移至最右侧 */}
            <div className='flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-muted/50 border border-border/40'>
              <KbTypeIcon
                className={cn('h-3 w-3 shrink-0 opacity-80', kbTypeMeta.iconClass)}
                aria-hidden={true}
              />
              <span className='font-medium text-[11px]'>{kbTypeMeta.label}</span>
            </div>

            <div className='h-3 w-px bg-border sm:block hidden' aria-hidden={true} />

            <div className='flex items-center gap-2'>
              <span className='truncate max-w-[140px]' title={knowledgeBase.created_by_name || '未知'}>
                {knowledgeBase.created_by_name || '未知'}
              </span>
              <span className='text-muted-foreground/50' aria-hidden>
                ·
              </span>
              <span>{knowledgeBase.visibility === 'private' ? '私有' : '团队可见'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 主内容区 */}
      <div className='flex flex-1 overflow-hidden'>
        {/* 1. 侧边活动轨道 (Activity Bar) */}
        <ActivityBar activeTab={activeTab} onTabChange={handleActivityTabChange} />

        {/* 2. 文件夹树侧边栏 (平滑动画容器) */}
        <div
          className={cn(
            'border-r bg-muted/20 transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0',
            shouldShowFolderTree
              ? (isFolderTreeCollapsed ? 'w-0 border-r-0 opacity-0' : 'w-64 opacity-100')
              : 'w-0 border-r-0 opacity-0'
          )}
        >
          <div className='w-64 h-full'> {/* 维持子组件宽度固定，防止折叠时内容被挤压 */}
            <FolderTree
              kbId={folderId}
              selectedFolderId={selectedFolderId || undefined}
              onSelectFolder={setSelectedFolderId}
            />
          </div>
        </div>

        {/* 3. 主内容区 (Main Content) */}
        <main className='flex-1 flex flex-col min-w-0 bg-background'>
          {knowledgeBase.type === 'table' && activeTab === 'files' && (
            <div className='border-b bg-background px-6 py-3'>
              <div className='flex items-center gap-2'>
                {renderFolderTreeToggleButton()}
                <div className='inline-flex items-center rounded-xl border bg-muted/30 p-1'>
                  <button
                    type='button'
                    onClick={() => handleTableWorkbenchChange('files')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      tableWorkbenchView === 'files'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    文件列表
                  </button>
                  <button
                    type='button'
                    onClick={() => handleTableWorkbenchChange('data')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      tableWorkbenchView === 'data'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    数据视图
                  </button>
                  <button
                    type='button'
                    onClick={() => handleTableWorkbenchChange('structure')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      tableWorkbenchView === 'structure'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    结构定义
                  </button>
                  <button
                    type='button'
                    onClick={() => handleTableWorkbenchChange('intelligence')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      tableWorkbenchView === 'intelligence'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    高级配置
                  </button>
                </div>
              </div>
            </div>
          )}
          {knowledgeBase.type === 'qa' && activeTab === 'files' && (
            <div className='border-b bg-background px-6 py-3'>
              <div className='flex items-center gap-2'>
                {renderFolderTreeToggleButton()}
                <div className='inline-flex items-center rounded-xl border bg-muted/30 p-1'>
                  <button
                    type='button'
                    onClick={() => handleQAWorkbenchChange('files')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      qaWorkbenchView === 'files'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    文件列表
                  </button>
                  <button
                    type='button'
                    onClick={() => handleQAWorkbenchChange('data')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      qaWorkbenchView === 'data'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    数据视图
                  </button>
                  <button
                    type='button'
                    onClick={() => handleQAWorkbenchChange('config')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      qaWorkbenchView === 'config'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    配置面板
                  </button>
                  <button
                    type='button'
                    onClick={() => handleQAWorkbenchChange('intelligence')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      qaWorkbenchView === 'intelligence'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    高级配置
                  </button>
                </div>
              </div>
            </div>
          )}
          {knowledgeBase.type === 'web' && activeTab === 'files' && (
            <div className='border-b bg-background px-6 py-3'>
              <div className='flex items-center gap-2'>
                {renderFolderTreeToggleButton()}
                <div className='inline-flex items-center rounded-xl border bg-muted/30 p-1'>
                  <button
                    type='button'
                    onClick={() => handleWebWorkbenchChange('files')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      webWorkbenchView === 'files'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    文件列表
                  </button>
                  <button
                    type='button'
                    onClick={() => handleWebWorkbenchChange('web-pages')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      webWorkbenchView === 'web-pages'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    网页页面
                  </button>
                  <button
                    type='button'
                    onClick={() => handleWebWorkbenchChange('web-sites')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      webWorkbenchView === 'web-sites'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    站点视图
                  </button>
                  <button
                    type='button'
                    onClick={() => handleWebWorkbenchChange('web-runs')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      webWorkbenchView === 'web-runs'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    同步记录
                  </button>
                  <button
                    type='button'
                    onClick={() => handleWebWorkbenchChange('intelligence')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      webWorkbenchView === 'intelligence'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    高级配置
                  </button>
                </div>
              </div>
            </div>
          )}
          {knowledgeBase.type === 'general' && activeTab === 'files' && (
            <div className='border-b bg-background px-6 py-3'>
              <div className='flex items-center gap-2'>
                {renderFolderTreeToggleButton()}
                <div className='inline-flex items-center rounded-xl border bg-muted/30 p-1'>
                  <button
                    type='button'
                    onClick={() => handleGeneralWorkbenchChange('files')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      generalWorkbenchView === 'files'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    文件列表
                  </button>
                  <button
                    type='button'
                    onClick={() => handleGeneralWorkbenchChange('general-parsing')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      generalWorkbenchView === 'general-parsing'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    解析配置
                  </button>
                  <button
                    type='button'
                    onClick={() => handleGeneralWorkbenchChange('intelligence')}
                    className={cn(
                      'rounded-lg px-4 py-2 text-sm font-medium transition',
                      generalWorkbenchView === 'intelligence'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    高级配置
                  </button>
                </div>
              </div>
            </div>
          )}
          {shouldShowTableGuideCard && (
            <div className='border-b bg-amber-50/70 px-6 py-4'>
              <div className='flex items-start justify-between gap-4 rounded-xl border border-amber-200 bg-background p-4'>
                <div>
                  <h2 className='text-sm font-semibold text-foreground'>先上传首个标准 Excel，再继续导入会更顺手</h2>
                  <p className='mt-1 text-sm text-muted-foreground'>
                    建议先上传一份标准 Excel，让系统生成结构草稿；确认无误后，再继续导入其他文档。如果暂时没有标准文件，也可以先手动定义结构。
                  </p>
                </div>
                <div className='flex shrink-0 items-center gap-2'>
                  <button
                    type='button'
                    onClick={() => handleGuideAction('schema')}
                    className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${tableGuide === 'schema'
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-border hover:border-primary/40'
                      }`}
                  >
                    手动定义结构
                  </button>
                  <button
                    type='button'
                    onClick={() => handleGuideAction('upload')}
                    className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${tableGuide === 'upload'
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-border hover:border-primary/40'
                      }`}
                  >
                    上传首个标准 Excel
                  </button>
                </div>
              </div>
            </div>
          )}
          {activeTab === 'files' && (
            knowledgeBase.type === 'table' ? (
              tableWorkbenchView === 'files' ? (
                <FileBrowser
                  kbId={folderId}
                  kbType={knowledgeBase.type}
                  selectedFolderId={selectedFolderId}
                  autoOpenUploadDialog={tableGuide === 'upload'}
                  onTableSchemaInitialized={handleTableSchemaInitialized}
                  onFolderChange={setSelectedFolderId}
                  isFolderTreeCollapsed={isFolderTreeCollapsed}
                  onToggleFolderTree={() => setIsFolderTreeCollapsed(!isFolderTreeCollapsed)}
                  onSetFolderTreeCollapsed={setIsFolderTreeCollapsed}
                />
              ) : tableWorkbenchView === 'data' ? (
                <Suspense fallback={<TableWorkbenchFallback title='数据视图' />}>
                  <TableManager kbId={folderId} selectedFolderId={selectedFolderId} />
                </Suspense>
              ) : tableWorkbenchView === 'structure' ? (
                <Suspense fallback={<TableWorkbenchFallback title='结构定义' />}>
                  <TableStructureManager
                    kbId={folderId}
                    onRequestUploadDraft={() => handleGuideAction('upload')}
                    onNavigateToFiles={() => handleTableWorkbenchChange('files')}
                    onNavigateToData={() => handleTableWorkbenchChange('data')}
                  />
                </Suspense>
              ) : (
                <Suspense fallback={<TableWorkbenchFallback title='高级配置' />}>
                  <AdvancedConfigWorkbench kbId={folderId} />
                </Suspense>
              )
            ) : knowledgeBase.type === 'qa' ? (
              qaWorkbenchView === 'files' ? (
                <FileBrowser
                  kbId={folderId}
                  kbType={knowledgeBase.type}
                  selectedFolderId={selectedFolderId}
                  onFolderChange={setSelectedFolderId}
                  isFolderTreeCollapsed={isFolderTreeCollapsed}
                  onToggleFolderTree={() => setIsFolderTreeCollapsed(!isFolderTreeCollapsed)}
                  onSetFolderTreeCollapsed={setIsFolderTreeCollapsed}
                />
              ) : qaWorkbenchView === 'data' ? (
                <Suspense fallback={<TableWorkbenchFallback title='数据视图' />}>
                  <QADataManager kbId={folderId} selectedFolderId={selectedFolderId} />
                </Suspense>
              ) : qaWorkbenchView === 'config' ? (
                <Suspense fallback={<TableWorkbenchFallback title='配置面板' />}>
                  <QAConfigPanel kbId={folderId} />
                </Suspense>
              ) : (
                <Suspense fallback={<TableWorkbenchFallback title='高级配置' />}>
                  <AdvancedConfigWorkbench kbId={folderId} />
                </Suspense>
              )
            ) : knowledgeBase.type === 'web' ? (
              webWorkbenchView === 'intelligence' ? (
                <Suspense fallback={<TableWorkbenchFallback title='高级配置' />}>
                  <AdvancedConfigWorkbench kbId={folderId} />
                </Suspense>
              ) : (
                <Suspense fallback={<TableWorkbenchFallback title='网页同步工作台' />}>
                  <WebSyncWorkbench
                    kbId={folderId}
                    view={webWorkbenchView}
                    selectedFolderId={selectedFolderId}
                    onFolderChange={setSelectedFolderId}
                    isFolderTreeCollapsed={isFolderTreeCollapsed}
                    onToggleFolderTree={() => setIsFolderTreeCollapsed(!isFolderTreeCollapsed)}
                    onSetFolderTreeCollapsed={setIsFolderTreeCollapsed}
                  />
                </Suspense>
              )
            ) : knowledgeBase.type === 'general' ? (
              generalWorkbenchView === 'intelligence' ? (
                <Suspense fallback={<TableWorkbenchFallback title='高级配置' />}>
                  <AdvancedConfigWorkbench kbId={folderId} />
                </Suspense>
              ) : (
                <Suspense fallback={<TableWorkbenchFallback title='通用文档工作台' />}>
                  <GeneralWorkbench
                    kbId={folderId}
                    view={generalWorkbenchView}
                    selectedFolderId={selectedFolderId}
                    onFolderChange={setSelectedFolderId}
                    isFolderTreeCollapsed={isFolderTreeCollapsed}
                    onToggleFolderTree={() => setIsFolderTreeCollapsed(!isFolderTreeCollapsed)}
                    onSetFolderTreeCollapsed={setIsFolderTreeCollapsed}
                  />
                </Suspense>
              )
            ) : (
              <FileBrowser
                kbId={folderId}
                kbType={knowledgeBase.type}
                selectedFolderId={selectedFolderId}
                onFolderChange={setSelectedFolderId}
                isFolderTreeCollapsed={isFolderTreeCollapsed}
                onToggleFolderTree={() => setIsFolderTreeCollapsed(!isFolderTreeCollapsed)}
                onSetFolderTreeCollapsed={setIsFolderTreeCollapsed}
              />
            )
          )}
          {activeTab === 'retrieval' && <RetrievalTest kbId={folderId} />}
          {activeTab === 'tags' && <TagManagement kbId={folderId} />}
          {activeTab === 'glossary' && <GlossaryManagement kbId={folderId} />}
          {activeTab === 'synonyms' && <SynonymManagement kbId={folderId} />}
          {activeTab === 'config' && <KnowledgeBaseSettings kbId={folderId} onOpenTagManagement={handleOpenTagManagement} />}
        </main>
      </div>
    </div>
  )
}
