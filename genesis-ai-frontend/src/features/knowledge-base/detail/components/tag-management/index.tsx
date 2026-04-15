import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import {
  BookOpen,
  Edit3,
  FileText,
  FolderOpen,
  Link2,
  Plus,
  Search,
  Tag as TagIcon,
  Trash2,
  Unlink2,
  X,
  Layers,
  CheckCircle2,
  Circle,
  LayoutGrid,
  List,
  ChevronLeft,
  ChevronRight,
  Info,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Tag, TagTargetType } from '@/lib/api/folder.types'
import { createTag, deleteTag, getTagUsageDetail, getTagUsageSummary, listScopedTags, updateTag, type TagUsageSummaryItem } from '@/lib/api/tag'
import { getKnowledgeBaseTags, setKnowledgeBaseTags } from '@/lib/api/knowledge-base'

interface TagManagementProps {
  kbId: string
}

interface TagFormState {
  name: string
  description: string
  aliasesText: string
  color: string
  scope: 'global' | 'kb'
  allowedTargetTypes: TagTargetType[]
}

const DEFAULT_FORM: TagFormState = {
  name: '',
  description: '',
  aliasesText: '',
  color: 'blue',
  scope: 'kb',
  allowedTargetTypes: ['kb'],
}

const COLOR_MAP: Record<string, { bg: string; text: string; dot: string; border: string; iconBg: string }> = {
  blue:   { bg: 'bg-blue-50',    text: 'text-blue-700',    dot: 'bg-blue-500',    border: 'border-blue-200',    iconBg: 'bg-blue-100' },
  green:  { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500', border: 'border-emerald-200', iconBg: 'bg-emerald-100' },
  purple: { bg: 'bg-purple-50',  text: 'text-purple-700',  dot: 'bg-purple-500',  border: 'border-purple-200',  iconBg: 'bg-purple-100' },
  red:    { bg: 'bg-red-50',     text: 'text-red-700',     dot: 'bg-red-500',     border: 'border-red-200',     iconBg: 'bg-red-100' },
  yellow: { bg: 'bg-amber-50',   text: 'text-amber-700',   dot: 'bg-amber-500',   border: 'border-amber-200',   iconBg: 'bg-amber-100' },
  gray:   { bg: 'bg-slate-50',   text: 'text-slate-700',   dot: 'bg-slate-500',   border: 'border-slate-200',   iconBg: 'bg-slate-100' },
}

const TARGET_TYPE_OPTIONS: Array<{
  value: TagTargetType
  label: string
  description: string
  icon: typeof BookOpen
  color: string
}> = [
  {
    value: 'kb',
    label: '知识库',
    description: '适合知识库分类、路由和选库提示',
    icon: BookOpen,
    color: 'blue',
  },
  {
    value: 'kb_doc',
    label: '文档',
    description: '适合文件列表中的文档内容、状态和批次标记',
    icon: FileText,
    color: 'emerald',
  },
  {
    value: 'folder',
    label: '文件夹',
    description: '适合目录分类和文件夹层级下的组织标签',
    icon: FolderOpen,
    color: 'amber',
  },
]

// 每页显示数量选项
const PAGE_SIZE_OPTIONS = [12, 24, 48]

export function TagManagement({ kbId }: TagManagementProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState('')
  // 标签来源（原作用域）：'all' | 'global'=公共标签 | 'kb'=本库私有标签
  const [scopeFilter, setScopeFilter] = useState<'all' | 'global' | 'kb'>('all')
  // 适用对象多选筛选
  const [targetFilters, setTargetFilters] = useState<TagTargetType[]>([])
  // 使用状态：标签是否被挂载到任意资源
  const [usageFilter, setUsageFilter] = useState<'all' | 'used' | 'unused'>('all')
  // 关联状态：标签是否已关联到当前知识库实体
  const [associationFilter, setAssociationFilter] = useState<'all' | 'bound' | 'unbound'>('all')

  // 关联状态依赖鉴定：只有适用对象包含 'kb' 时才有意义
  // 情况：未选任何适用对象（不限），或选了包含 kb 的送项
  const associationFilterEnabled =
    targetFilters.length === 0 || targetFilters.includes('kb' as any)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedTag, setSelectedTag] = useState<Tag | null>(null)
  const [open, setOpen] = useState(false)
  const [editingTag, setEditingTag] = useState<Tag | null>(null)
  const [tagPendingDelete, setTagPendingDelete] = useState<Tag | null>(null)
  const [form, setForm] = useState<TagFormState>(DEFAULT_FORM)

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(24)

  const resetFilters = () => {
    setKeyword('')
    setScopeFilter('all')
    setTargetFilters([])
    setUsageFilter('all')
    setAssociationFilter('all')
    setCurrentPage(1)
  }

  const hasActiveFilters =
    keyword.trim().length > 0 ||
    scopeFilter !== 'all' ||
    targetFilters.length > 0 ||
    usageFilter !== 'all' ||
    // 关联状态禁用时不计入活跃筛选计数
    (associationFilterEnabled && associationFilter !== 'all')

  const openKnowledgeBase = (targetKbId: string, initialTab: 'files' | 'tags' = 'files') => {
    navigate({
      to: '/knowledge-base/$folderId',
      params: { folderId: targetKbId },
      search: {
        initialTab,
        tableGuide: undefined,
      },
    })
  }

  // 获取标签列表：所有筛选条件均发送到服务端，不再做客户端二次过滤
  const { data: tagsResponse, isLoading } = useQuery({
    queryKey: [
      'tags', 'scoped', kbId,
      keyword, scopeFilter, targetFilters, usageFilter, associationFilter,
      currentPage, pageSize,
    ],
    queryFn: async () => {
      const response = await listScopedTags({
        kb_id: kbId,
        include_global: true,
        include_kb: true,
        scope: scopeFilter,
        target_types: targetFilters.length > 0 ? targetFilters : undefined,
        usage_status: usageFilter !== 'all' ? usageFilter : undefined,
        // 适用对象不含 kb 时，关联状态筛选无意义，不传该参数
        association_status: (associationFilterEnabled && associationFilter !== 'all')
          ? associationFilter
          : undefined,
        search: keyword || undefined,
        page: currentPage,
        page_size: pageSize,
      })
      return response.data
    },
    enabled: !!kbId,
  })

  const scopedTags = tagsResponse?.tags || []
  // total 来自服务端返回的真实总数
  const totalTags = tagsResponse?.total || 0

  const { data: selectedTags = [] } = useQuery({
    queryKey: ['kb-tags', kbId],
    queryFn: async () => (await getKnowledgeBaseTags(kbId)).tags,
    enabled: !!kbId,
  })
  const selectedTagIds = useMemo(() => new Set(selectedTags.map((tag) => tag.id)), [selectedTags])

  const { data: usageSummary = [] } = useQuery({
    queryKey: ['tags', 'usage-summary', kbId, scopedTags.map((tag) => tag.id).join(',')],
    queryFn: async () => (await getTagUsageSummary(scopedTags.map((tag) => tag.id), kbId)).data.items,
    enabled: !!kbId && scopedTags.length > 0,
  })

  const usageSummaryMap = useMemo(
    () => usageSummary.reduce<Record<string, TagUsageSummaryItem>>((acc, item) => {
      acc[item.tag_id] = item
      return acc
    }, {}),
    [usageSummary]
  )

  const { data: usageDetail } = useQuery({
    queryKey: ['tags', 'usage-detail', kbId, selectedTag?.id],
    queryFn: async () => {
      if (!selectedTag) return null
      return (await getTagUsageDetail(selectedTag.id)).data
    },
    enabled: !!selectedTag,
  })

  // 服务端已过滤，直接使用返回的 tags
  const filteredTags = scopedTags
  const publicTags = filteredTags.filter((tag) => !tag.kb_id)
  const kbTags = filteredTags.filter((tag) => tag.kb_id === kbId)

  // 分页信息（基于服务端返回的真实 total）
  const filteredTotal = totalTags
  const totalPages = Math.ceil(filteredTotal / pageSize) || 1
  const startIndex = (currentPage - 1) * pageSize
  const endIndex = Math.min(startIndex + pageSize, filteredTotal)
  // 当前页标签已在服务端分好，直接展示
  const paginatedPublicTags = publicTags
  const paginatedKbTags = kbTags

  // 当总页数变小后当前页超出范围，自动退回第一页
  useEffect(() => {
    if (currentPage > totalPages && totalPages > 0) {
      setCurrentPage(1)
    }
  }, [totalPages, currentPage])

  const stats = useMemo(() => {
    // 统计数据均基于当前页的展示数据
    const total = totalTags
    const bound = filteredTags.filter((t) => selectedTagIds.has(t.id)).length
    const used = filteredTags.filter((t) => {
      const u = usageSummaryMap[t.id]
      return u && (u.kb_count > 0 || u.kb_doc_count > 0 || u.folder_count > 0)
    }).length
    return { total, bound, used }
  }, [filteredTags, totalTags, selectedTagIds, usageSummaryMap])

  const pendingDeleteUsage = tagPendingDelete ? usageSummaryMap[tagPendingDelete.id] : undefined
  const isDeleteBlocked = Boolean(
    pendingDeleteUsage && (pendingDeleteUsage.kb_count > 0 || pendingDeleteUsage.kb_doc_count > 0 || pendingDeleteUsage.folder_count > 0)
  )

  const createMutation = useMutation({
    mutationFn: async () => {
      const aliases = form.aliasesText
        .split(/[,，;；\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
      return createTag({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        aliases,
        color: form.color,
        allowed_target_types: form.allowedTargetTypes,
        kb_id: form.scope === 'kb' ? kbId : undefined,
      })
    },
    onSuccess: () => {
      toast.success('标签创建成功')
      setOpen(false)
      resetForm()
      invalidateTagQueries(queryClient, kbId)
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail ?? '创建标签失败')
    },
  })

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!editingTag) return null
      const aliases = form.aliasesText
        .split(/[,，;；\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
      return updateTag(editingTag.id, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        aliases,
        color: form.color,
        allowed_target_types: form.allowedTargetTypes,
      })
    },
    onSuccess: () => {
      toast.success('标签更新成功')
      setOpen(false)
      resetForm()
      invalidateTagQueries(queryClient, kbId)
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail ?? '更新标签失败')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTag,
    onSuccess: () => {
      toast.success('标签删除成功')
      setTagPendingDelete(null)
      if (selectedTag?.id === tagPendingDelete?.id) setSelectedTag(null)
      invalidateTagQueries(queryClient, kbId)
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail ?? '删除标签失败')
    },
  })

  const bindMutation = useMutation({
    mutationFn: async (nextTagIds: string[]) => setKnowledgeBaseTags(kbId, nextTagIds),
    onSuccess: () => {
      toast.success('知识库标签已更新')
      invalidateTagQueries(queryClient, kbId)
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail ?? '更新知识库标签失败')
    },
  })

  const submit = async () => {
    if (!form.name.trim()) {
      toast.error('请输入标签名称')
      return
    }
    if (form.allowedTargetTypes.length === 0) {
      toast.error('请至少选择一个适用对象')
      return
    }
    if (editingTag) {
      await updateMutation.mutateAsync()
      return
    }
    await createMutation.mutateAsync()
  }

  const openCreate = (scope: 'global' | 'kb') => {
    setEditingTag(null)
    setForm({ ...DEFAULT_FORM, scope })
    setOpen(true)
  }

  const openEdit = (tag: Tag) => {
    setEditingTag(tag)
    setForm({
      name: tag.name,
      description: tag.description || '',
      aliasesText: Array.isArray(tag.aliases) ? tag.aliases.join('，') : '',
      color: tag.color || 'blue',
      scope: tag.kb_id ? 'kb' : 'global',
      allowedTargetTypes: tag.allowed_target_types?.length ? tag.allowed_target_types : ['kb_doc'],
    })
    setOpen(true)
  }

  const resetForm = () => {
    setEditingTag(null)
    setForm(DEFAULT_FORM)
  }

  const handleToggleBinding = (tag: Tag) => {
    const nextTagIds = selectedTagIds.has(tag.id)
      ? selectedTags.filter((item) => item.id !== tag.id).map((item) => item.id)
      : [...selectedTags.map((item) => item.id), tag.id]
    bindMutation.mutate(nextTagIds)
  }

  const getTagColorClasses = (color?: string) => COLOR_MAP[color || 'blue'] ?? COLOR_MAP['blue']

  // 分页控制
  const goToPage = (page: number) => {
    const safePage = Math.max(1, Math.min(page, totalPages))
    setCurrentPage(safePage)
  }

  const goToFirstPage = () => goToPage(1)
  const goToLastPage = () => goToPage(totalPages)
  const goToPrevPage = () => goToPage(currentPage - 1)
  const goToNextPage = () => goToPage(currentPage + 1)

  return (
    <div className="flex h-full">
      {/* 左侧导航面板 */}
      <div className="w-64 flex-shrink-0 border-r bg-card flex flex-col h-full overflow-hidden">
        <div className="p-4 border-b flex-shrink-0">
          <div className="flex items-center gap-2">
            <TagIcon className="h-5 w-5 text-blue-600" />
            <span className="text-base font-semibold text-blue-700">标签管理</span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            管理公共标签与知识库标签
          </p>
        </div>

        <ScrollArea className="flex-1 min-h-0">
          <div className="p-4 space-y-6">
            {/* 标签来源（原作用域）筛选 */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Layers className="h-4 w-4" />
                <span>标签来源</span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3.5 w-3.5 cursor-help opacity-60" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[200px]">
                    <p>公共标签：全租户共享，任意知识库可关联</p>
                    <p>本库私有标签：仅属于当前知识库</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <div className="space-y-1">
                <FilterButton
                  active={scopeFilter === 'all'}
                  onClick={() => { setScopeFilter('all'); setCurrentPage(1) }}
                  label="全部标签"
                  count={scopedTags.length}
                />
                <FilterButton
                  active={scopeFilter === 'global'}
                  onClick={() => { setScopeFilter('global'); setCurrentPage(1) }}
                  label="公共标签"
                  count={scopedTags.filter((t) => !t.kb_id).length}
                />
                <FilterButton
                  active={scopeFilter === 'kb'}
                  onClick={() => { setScopeFilter('kb'); setCurrentPage(1) }}
                  label="本库私有"
                  count={scopedTags.filter((t) => t.kb_id === kbId).length}
                />
              </div>
            </div>

            <Separator />

            {/* 适用对象筛选 - 多选，空 = 不限制（显示全部） */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <LayoutGrid className="h-4 w-4" />
                  <span>适用对象</span>
                </div>
                {targetFilters.length > 0 ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-auto py-0 px-2 text-xs text-muted-foreground"
                    onClick={() => { setTargetFilters([]); setCurrentPage(1) }}
                  >
                    全部
                  </Button>
                ) : (
                  // 无勾选时显示提示，说明当前为不限制状态
                  <span className="text-xs text-muted-foreground/60">不限</span>
                )}
              </div>
              <div className="space-y-1">
                {TARGET_TYPE_OPTIONS.map((opt) => (
                  <FilterCheckbox
                    key={opt.value}
                    checked={targetFilters.includes(opt.value)}
                    onChange={() => {
                      setTargetFilters((prev) =>
                        prev.includes(opt.value)
                          ? prev.filter((v) => v !== opt.value)
                          : [...prev, opt.value]
                      )
                      setCurrentPage(1)
                    }}
                    label={opt.label}
                    icon={opt.icon}
                    color={opt.color}
                  />
                ))}
              </div>
              {targetFilters.length > 0 && (
                <div className="text-xs text-muted-foreground px-3">
                  已选 {targetFilters.length} / {TARGET_TYPE_OPTIONS.length} 项
                </div>
              )}
            </div>

            <Separator />

            {/* 使用状态筛选 */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <CheckCircle2 className="h-4 w-4" />
                <span>使用状态</span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3.5 w-3.5 cursor-help opacity-60" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[200px]">
                    <p>标签是否被挂到了<strong>任意资源</strong>（知识库 / 文档 / 文件夹）</p>
                    <p className="mt-1 opacity-80">与"关联状态"区别：使用状态涵盖所有资源类型，关联状态仅指当前知识库</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <div className="space-y-1">
                <FilterButton
                  active={usageFilter === 'all'}
                  onClick={() => { setUsageFilter('all'); setCurrentPage(1) }}
                  label="全部状态"
                />
                <FilterButton
                  active={usageFilter === 'used'}
                  onClick={() => { setUsageFilter('used'); setCurrentPage(1) }}
                  label="已使用"
                />
                <FilterButton
                  active={usageFilter === 'unused'}
                  onClick={() => { setUsageFilter('unused'); setCurrentPage(1) }}
                  label="未使用"
                />
              </div>
            </div>

            <Separator />

            {/* 关联状态筛选 - 仅当适用对象包含知识库时可用 */}
            <div className={[
              "space-y-2 transition-opacity",
              associationFilterEnabled ? "opacity-100" : "opacity-40 pointer-events-none",
            ].join(' ')}>
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Link2 className="h-4 w-4" />
                <span>本库关联</span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3.5 w-3.5 cursor-help opacity-60" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[220px]">
                    {associationFilterEnabled ? (
                      <>
                        <p>标签是否已关联到<strong>当前知识库</strong>本身</p>
                        <p className="mt-1 opacity-80">即知识库列表页的标签打标，不包含库内文档/文件夹的标签</p>
                      </>
                    ) : (
                      <p>当前适用对象不包含「知识库」，关联状态无意义，已自动禁用</p>
                    )}
                  </TooltipContent>
                </Tooltip>
                {/* 适用对象不含 kb 时显示警示小标记 */}
                {!associationFilterEnabled && (
                  <span className="text-[10px] text-amber-500 font-normal">不可用</span>
                )}
              </div>
              <div className="space-y-1">
                <FilterButton
                  active={associationFilter === 'all'}
                  onClick={() => { setAssociationFilter('all'); setCurrentPage(1) }}
                  label="全部"
                />
                <FilterButton
                  active={associationFilter === 'bound'}
                  onClick={() => { setAssociationFilter('bound'); setCurrentPage(1) }}
                  label="已关联本库"
                />
                <FilterButton
                  active={associationFilter === 'unbound'}
                  onClick={() => { setAssociationFilter('unbound'); setCurrentPage(1) }}
                  label="未关联本库"
                />
              </div>
            </div>
          </div>
        </ScrollArea>

        {/* 底部统计 */}
        <div className="p-4 border-t bg-muted/30 flex-shrink-0">
          <div className="text-xs text-muted-foreground space-y-1">
            <div className="flex justify-between">
              <span>共 {stats.total} 个标签</span>
            </div>
            <div className="flex justify-between">
              <span>已关联</span>
              <span className="font-medium">{stats.bound}</span>
            </div>
            <div className="flex justify-between">
              <span>已使用</span>
              <span className="font-medium">{stats.used}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col min-w-0 bg-slate-50/30 h-full overflow-hidden">
        {/* 顶部操作栏 */}
        <div className="h-16 border-b bg-card px-4 flex items-center justify-between gap-4 flex-shrink-0">
          <div className="flex items-center gap-3 flex-1 max-w-2xl">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="搜索标签名称、描述、别名..."
                className="pl-9"
              />
              {keyword && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6"
                  onClick={() => setKeyword('')}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>

            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={resetFilters} className="text-muted-foreground whitespace-nowrap">
                清空筛选
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* 视图切换 */}
            <div className="flex items-center border rounded-md p-0.5 bg-muted/30">
              <Button
                variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                size="icon"
                className="h-8 w-8"
                onClick={() => setViewMode('grid')}
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === 'list' ? 'secondary' : 'ghost'}
                size="icon"
                className="h-8 w-8"
                onClick={() => setViewMode('list')}
              >
                <List className="h-4 w-4" />
              </Button>
            </div>

            <Separator orientation="vertical" className="h-6" />

            <Button variant="outline" size="sm" onClick={() => openCreate('global')}>
              <Plus className="mr-1.5 h-4 w-4" />
              公共标签
            </Button>
            <Button variant="outline" size="sm" className="bg-blue-600 hover:bg-blue-700 text-white border-blue-600" onClick={() => openCreate('kb')}>
              <Plus className="mr-1.5 h-4 w-4" />
              本库标签
            </Button>
          </div>
        </div>

        {/* 标签列表 - 使用普通div配合overflow-auto实现滚动 */}
        <div className="flex-1 overflow-auto min-h-0">
          <div className="p-6">
            {isLoading ? (
              <div className="text-center py-20 text-muted-foreground">加载中...</div>
            ) : filteredTags.length === 0 ? (
              <EmptyState onReset={resetFilters} hasFilters={hasActiveFilters} />
            ) : (
              <div className="space-y-6">
                {/* 公共标签组 */}
                {publicTags.length > 0 && (
                  <TagSection
                    title="公共标签"
                    description="适合多个知识库共享的分类标签"
                    tags={paginatedPublicTags}
                    totalCount={publicTags.length}
                    viewMode={viewMode}
                    selectedTagIds={selectedTagIds}
                    usageSummaryMap={usageSummaryMap}
                    selectedTag={selectedTag}
                    onSelect={setSelectedTag}
                    onEdit={openEdit}
                    onDelete={setTagPendingDelete}
                    onToggleBinding={handleToggleBinding}
                    getTagColorClasses={getTagColorClasses}
                    isUpdating={bindMutation.isPending}
                  />
                )}

                {/* 本库标签组 */}
                {kbTags.length > 0 && (
                  <TagSection
                    title="本库标签"
                    description="只属于当前知识库的私有标签"
                    tags={paginatedKbTags}
                    totalCount={kbTags.length}
                    viewMode={viewMode}
                    selectedTagIds={selectedTagIds}
                    usageSummaryMap={usageSummaryMap}
                    selectedTag={selectedTag}
                    onSelect={setSelectedTag}
                    onEdit={openEdit}
                    onDelete={setTagPendingDelete}
                    onToggleBinding={handleToggleBinding}
                    getTagColorClasses={getTagColorClasses}
                    isUpdating={bindMutation.isPending}
                  />
                )}
              </div>
            )}
          </div>
        </div>

        {/* 分页栏 */}
        {filteredTags.length > 0 && (
          <div className="h-14 border-t bg-card px-4 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>
                显示 {startIndex + 1} - {endIndex} 条，共 {filteredTotal} 条
              </span>
              <div className="flex items-center gap-2">
                <span>每页</span>
                <Select
                  value={pageSize.toString()}
                  onValueChange={(value) => {
                    setPageSize(Number(value))
                    setCurrentPage(1)
                  }}
                >
                  <SelectTrigger className="w-16 h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PAGE_SIZE_OPTIONS.map((size) => (
                      <SelectItem key={size} value={size.toString()}>
                        {size}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span>条</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToFirstPage}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="h-4 w-4" />
                <ChevronLeft className="h-4 w-4 -ml-2" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToPrevPage}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>

              <div className="flex items-center gap-1 px-2">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  // 计算显示的页码范围
                  let pageNum = i + 1
                  if (totalPages > 5) {
                    if (currentPage > 3) {
                      pageNum = currentPage - 2 + i
                    }
                    if (currentPage > totalPages - 2) {
                      pageNum = totalPages - 4 + i
                    }
                  }

                  return (
                    <Button
                      key={pageNum}
                      variant={currentPage === pageNum ? 'default' : 'outline'}
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => goToPage(pageNum)}
                    >
                      {pageNum}
                    </Button>
                  )
                })}
              </div>

              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToNextPage}
                disabled={currentPage === totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToLastPage}
                disabled={currentPage === totalPages}
              >
                <ChevronRight className="h-4 w-4" />
                <ChevronRight className="h-4 w-4 -ml-2" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* 右侧详情面板 */}
      {selectedTag && (
        <div className="w-80 flex-shrink-0 border-l bg-card flex flex-col h-full">
          <div className="p-4 border-b flex items-center justify-between flex-shrink-0">
            <span className="font-medium">标签详情</span>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setSelectedTag(null)}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          <ScrollArea className="flex-1">
            <div className="p-4 space-y-6">
              {/* 标签头部 */}
              <div className="flex items-start gap-3">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${getTagColorClasses(selectedTag.color).bg}`}>
                  <TagIcon className={`h-5 w-5 ${getTagColorClasses(selectedTag.color).text}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-lg">{selectedTag.name}</h3>
                  <p className="text-sm text-muted-foreground">
                    {selectedTag.kb_id ? '本库标签' : '公共标签'}
                  </p>
                </div>
              </div>

              {/* 操作按钮：永远不用黑色背景，已关联用绿色轮廃，未关联用蓝色轮廃 */}
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className={`flex-1 ${
                    selectedTagIds.has(selectedTag.id)
                      ? 'border-amber-300 text-amber-700 hover:bg-amber-50'
                      : 'border-blue-300 text-blue-700 hover:bg-blue-50'
                  }`}
                  onClick={() => handleToggleBinding(selectedTag)}
                  disabled={bindMutation.isPending}
                >
                  {selectedTagIds.has(selectedTag.id) ? (
                    <><Unlink2 className="mr-1.5 h-4 w-4" /> 解除关联</>
                  ) : (
                    <><Link2 className="mr-1.5 h-4 w-4" /> 关联到本库</>
                  )}
                </Button>
                <Button variant="outline" size="icon" className="h-9 w-9" onClick={() => openEdit(selectedTag)}>
                  <Edit3 className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-9 w-9"
                  disabled={usageSummaryMap[selectedTag.id] && (
                    usageSummaryMap[selectedTag.id].kb_count > 0 ||
                    usageSummaryMap[selectedTag.id].kb_doc_count > 0 ||
                    usageSummaryMap[selectedTag.id].folder_count > 0
                  )}
                  onClick={() => setTagPendingDelete(selectedTag)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>

              <Separator />

              {/* 描述 */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground">描述</label>
                <p className="text-sm">{selectedTag.description || '暂无描述'}</p>
              </div>

              {/* 别名 */}
              {selectedTag.aliases && selectedTag.aliases.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">别名</label>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedTag.aliases.map((alias) => (
                      <Badge key={alias} variant="secondary" className="text-xs">
                        {alias}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* 适用对象 */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground">适用对象</label>
                <div className="flex flex-wrap gap-2">
                  {(selectedTag.allowed_target_types || []).map((type) => {
                    const opt = TARGET_TYPE_OPTIONS.find((o) => o.value === type)
                    if (!opt) return null
                    const Icon = opt.icon
                    return (
                      <Badge key={type} variant="outline" className="gap-1.5">
                        <Icon className="h-3 w-3" />
                        {opt.label}
                      </Badge>
                    )
                  })}
                </div>
              </div>

              <Separator />

              {/* 使用统计 */}
              <div className="space-y-3">
                <label className="text-sm font-medium text-muted-foreground">使用统计</label>
                {usageDetail ? (
                  <div className="grid grid-cols-3 gap-2">
                    <StatCard
                      label="知识库"
                      value={usageDetail.kb_usages.length}
                      color="blue"
                    />
                    <StatCard
                      label="文档"
                      value={usageDetail.kb_doc_usages.length}
                      color="emerald"
                    />
                    <StatCard
                      label="文件夹"
                      value={usageDetail.folder_usages.length}
                      color="amber"
                    />
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">加载中...</div>
                )}
              </div>

              {/* 使用详情列表 */}
              {usageDetail && (
                <div className="space-y-4">
                  {usageDetail.kb_usages.length > 0 && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium">使用的知识库</label>
                      <div className="space-y-1">
                        {usageDetail.kb_usages.slice(0, 5).map((kb) => (
                          <div
                            key={kb.id}
                            className="text-sm px-3 py-2 rounded-md bg-muted/50 hover:bg-muted cursor-pointer"
                            onClick={() => openKnowledgeBase(kb.id, 'files')}
                          >
                            {kb.name}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {usageDetail.kb_doc_usages.length > 0 && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium">使用的文档</label>
                      <div className="space-y-1">
                        {usageDetail.kb_doc_usages.slice(0, 5).map((doc) => (
                          <div key={doc.id} className="text-sm px-3 py-2 rounded-md bg-muted/50">
                            <div className="font-medium truncate">{doc.name}</div>
                            {doc.kb_name && (
                              <div className="text-xs text-muted-foreground">{doc.kb_name}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* 新建/编辑对话框 */}
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen)
          if (!nextOpen) resetForm()
        }}
      >
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>{editingTag ? '编辑标签' : '新建标签'}</DialogTitle>
            <DialogDescription>
              {editingTag
                ? '修改标签定义，已使用此标签的地方会同步显示最新名称和描述。'
                : '创建公共标签或当前知识库标签。'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {!editingTag ? (
              <div className="space-y-2">
                <Label>作用域</Label>
                <Select value={form.scope} onValueChange={(value: 'global' | 'kb') => setForm((prev) => ({ ...prev, scope: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">公共标签</SelectItem>
                    <SelectItem value="kb">当前知识库标签</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ) : (
              <div className="space-y-2">
                <Label>作用域</Label>
                <div className="rounded-lg border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                  {editingTag.kb_id ? '当前知识库标签' : '公共标签'}
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label>适用对象</Label>
              <div className="grid gap-3 sm:grid-cols-3">
                {TARGET_TYPE_OPTIONS.map((option) => {
                  const active = form.allowedTargetTypes.includes(option.value)
                  const Icon = option.icon
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setForm((prev) => {
                          const exists = prev.allowedTargetTypes.includes(option.value)
                          const next = exists
                            ? prev.allowedTargetTypes.filter((item) => item !== option.value)
                            : [...prev.allowedTargetTypes, option.value]
                          return { ...prev, allowedTargetTypes: next }
                        })
                      }}
                      className={[
                        'rounded-xl border px-3 py-3 text-left transition-all',
                        active
                          ? `border-${option.color}-300 bg-${option.color}-50 text-${option.color}-700 shadow-sm`
                          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50',
                      ].join(' ')}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <Icon className="h-4 w-4" />
                            <span className="text-sm font-semibold">{option.label}</span>
                          </div>
                          <p className="text-xs leading-relaxed opacity-80">
                            {option.description}
                          </p>
                        </div>
                        <div
                          className={[
                            'mt-0.5 flex h-5 min-w-5 items-center justify-center rounded-full border text-[10px] font-bold',
                            active
                              ? 'border-current bg-white/70'
                              : 'border-slate-300 bg-slate-100 text-slate-400',
                          ].join(' ')}
                        >
                          {active ? '开' : '关'}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
              <p className="text-xs text-muted-foreground">
                决定这个标签会出现在知识库、文档或文件夹的候选列表里
              </p>
            </div>

            <div className="space-y-2">
              <Label>标签名称</Label>
              <Input value={form.name} onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))} placeholder="例如：财务制度" />
            </div>

            <div className="space-y-2">
              <Label>标签描述</Label>
              <Textarea
                value={form.description}
                onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="描述标签适合覆盖的内容范围，便于团队理解"
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label>别名</Label>
              <Input
                value={form.aliasesText}
                onChange={(e) => setForm((prev) => ({ ...prev, aliasesText: e.target.value }))}
                placeholder="多个别名可用逗号或分号分隔"
              />
            </div>

            <div className="space-y-2">
              <Label>颜色</Label>
              <div className="flex gap-2">
                {Object.keys(COLOR_MAP).map((color) => (
                  <button
                    key={color}
                    type="button"
                    onClick={() => setForm((prev) => ({ ...prev, color }))}
                    className={[
                      'w-8 h-8 rounded-full transition-all',
                      COLOR_MAP[color].dot,
                      form.color === color ? 'ring-2 ring-offset-2 ring-slate-400 scale-110' : 'hover:scale-105',
                    ].join(' ')}
                  />
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={submit} disabled={createMutation.isPending || updateMutation.isPending}>
              {editingTag ? '保存修改' : '创建标签'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <AlertDialog open={!!tagPendingDelete} onOpenChange={(nextOpen) => !nextOpen && setTagPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {isDeleteBlocked ? '标签仍在使用中' : '确认删除标签？'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {tagPendingDelete ? (
                isDeleteBlocked ? (
                  <>
                    标签「{tagPendingDelete.name}」当前仍被
                    {pendingDeleteUsage?.kb_count ?? 0} 个知识库、
                    {pendingDeleteUsage?.kb_doc_count ?? 0} 个文档、
                    {pendingDeleteUsage?.folder_count ?? 0} 个文件夹使用。
                    请先解除关联，再执行删除。
                  </>
                ) : (
                  <>
                    标签「{tagPendingDelete.name}」当前未被使用，可以安全删除。
                    删除后将无法恢复。
                  </>
                )
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>

          {isDeleteBlocked && (
            <div className="rounded-xl border bg-slate-50/70 p-4 text-sm text-muted-foreground">
              <div>建议操作：</div>
              <div className="mt-2">1. 查看该标签的使用情况</div>
              <div>2. 从相关知识库或文档中移除标签</div>
              <div>3. 确认未使用后再删除</div>
            </div>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel>关闭</AlertDialogCancel>
            {!isDeleteBlocked && (
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={(e) => {
                  e.preventDefault()
                  if (!tagPendingDelete) return
                  deleteMutation.mutate(tagPendingDelete.id)
                }}
              >
                确认删除
              </AlertDialogAction>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// 筛选按钮组件
function FilterButton({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean
  onClick: () => void
  label: string
  count?: number
}) {
  return (
    <button
      onClick={onClick}
      className={[
        'w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors',
        active
          ? 'bg-primary/10 text-primary font-medium'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      ].join(' ')}
    >
      <span className="flex items-center gap-2">
        {active ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
        {label}
      </span>
      {count !== undefined && <span className="text-xs">{count}</span>}
    </button>
  )
}

// 筛选复选框组件
function FilterCheckbox({
  checked,
  onChange,
  label,
  icon: Icon,
  color,
}: {
  checked: boolean
  onChange: () => void
  label: string
  icon?: typeof BookOpen
  color?: string
}) {
  return (
    <button
      onClick={onChange}
      className={[
        'w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors',
        checked
          ? 'bg-primary/10 text-primary font-medium'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      ].join(' ')}
    >
      {checked ? (
        <div className="h-4 w-4 rounded bg-primary flex items-center justify-center">
          <CheckCircle2 className="h-3 w-3 text-primary-foreground" />
        </div>
      ) : (
        <div className="h-4 w-4 rounded border border-muted-foreground/30" />
      )}
      {Icon && <Icon className={`h-4 w-4 ${color ? `text-${color}-500` : ''}`} />}
      {label}
    </button>
  )
}

// 标签区块组件
function TagSection({
  title,
  description,
  tags,
  totalCount,
  viewMode,
  selectedTagIds,
  usageSummaryMap,
  selectedTag,
  onSelect,
  onEdit,
  onDelete,
  onToggleBinding,
  getTagColorClasses,
  isUpdating,
}: {
  title: string
  description: string
  tags: Tag[]
  totalCount: number
  viewMode: 'grid' | 'list'
  selectedTagIds: Set<string>
  usageSummaryMap: Record<string, TagUsageSummaryItem>
  selectedTag: Tag | null
  onSelect: (tag: Tag) => void
  onEdit: (tag: Tag) => void
  onDelete: (tag: Tag) => void
  onToggleBinding: (tag: Tag) => void
  getTagColorClasses: (color?: string) => { bg: string; text: string; dot: string; border: string; iconBg: string }
  isUpdating: boolean
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h3 className="font-semibold text-lg">{title}</h3>
        <span className="text-sm text-muted-foreground">{description}</span>
        <Badge variant="secondary">{totalCount}</Badge>
      </div>

      {viewMode === 'grid' ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {tags.map((tag) => (
            <TagCard
              key={tag.id}
              tag={tag}
              usage={usageSummaryMap[tag.id]}
              isSelected={selectedTag?.id === tag.id}
              isBound={selectedTagIds.has(tag.id)}
              onSelect={() => onSelect(tag)}
              onEdit={() => onEdit(tag)}
              onDelete={() => onDelete(tag)}
              onToggleBinding={() => onToggleBinding(tag)}
              getTagColorClasses={getTagColorClasses}
              isUpdating={isUpdating}
            />
          ))}
        </div>
      ) : (
        <div className="border rounded-lg bg-card divide-y">
          {tags.map((tag) => (
            <TagListItem
              key={tag.id}
              tag={tag}
              usage={usageSummaryMap[tag.id]}
              isSelected={selectedTag?.id === tag.id}
              isBound={selectedTagIds.has(tag.id)}
              onSelect={() => onSelect(tag)}
              onEdit={() => onEdit(tag)}
              onDelete={() => onDelete(tag)}
              onToggleBinding={() => onToggleBinding(tag)}
              getTagColorClasses={getTagColorClasses}
              isUpdating={isUpdating}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// 标签卡片组件
function TagCard({
  tag,
  usage,
  isSelected,
  isBound,
  onSelect,
  onEdit,
  onDelete,
  onToggleBinding,
  getTagColorClasses,
  isUpdating,
}: {
  tag: Tag
  usage?: TagUsageSummaryItem
  isSelected: boolean
  isBound: boolean
  onSelect: () => void
  onEdit: () => void
  onDelete: () => void
  onToggleBinding: () => void
  getTagColorClasses: (color?: string) => { bg: string; text: string; dot: string; border: string; iconBg: string }
  isUpdating: boolean
}) {
  const colors = getTagColorClasses(tag.color)
  const isUsed = usage && (usage.kb_count > 0 || usage.kb_doc_count > 0 || usage.folder_count > 0)
  const totalUsage = (usage?.kb_count || 0) + (usage?.kb_doc_count || 0) + (usage?.folder_count || 0)

  return (
    <div
      onClick={onSelect}
      className={[
        // 统一白色卡片背景，不再用颜色志和边框区分已关联
        'group relative rounded-xl border bg-card cursor-pointer transition-all hover:shadow-md hover:border-primary/40',
        isSelected ? 'ring-2 ring-primary border-primary shadow-md' : 'border-border',
      ].join(' ')}
    >
      <div className="p-4">
        {/* 头部：图标 + 名称 + 已关联 chip（hover 时淡出，让操作按钮浮出） */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${colors.bg}`}>
              <TagIcon className={`h-4 w-4 ${colors.text}`} />
            </div>
            <span className="font-semibold truncate text-sm">{tag.name}</span>
          </div>
          {/* 已关联本库 chip：固定绿色，hover 时淡出让位置空出给操作按钮 */}
          {isBound && (
            <span className="flex-shrink-0 inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border transition-opacity group-hover:opacity-0 bg-emerald-50 text-emerald-700 border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              已关联本库
            </span>
          )}
        </div>

        {/* 描述 */}
        <p className="mt-2.5 text-xs text-muted-foreground line-clamp-2 min-h-[32px] leading-relaxed">
          {tag.description || '暂无描述'}
        </p>

        {/* 别名 */}
        {tag.aliases && tag.aliases.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1">
            {tag.aliases.slice(0, 3).map((alias) => (
              <span
                key={alias}
                className="inline-block text-[10px] px-1.5 py-0.5 rounded border bg-muted/60 text-muted-foreground border-border"
              >
                {alias}
              </span>
            ))}
            {tag.aliases.length > 3 && (
              <span className="inline-block text-[10px] px-1.5 py-0.5 rounded border bg-muted/60 text-muted-foreground border-border">
                +{tag.aliases.length - 3}
              </span>
            )}
          </div>
        )}

        {/* 底部：使用统计 */}
        <div className="mt-3 pt-2.5 border-t border-border/40 flex items-center gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <BookOpen className="h-3 w-3" />
            {usage?.kb_count || 0}
          </span>
          <span className="flex items-center gap-1">
            <FileText className="h-3 w-3" />
            {usage?.kb_doc_count || 0}
          </span>
          <span className="flex items-center gap-1">
            <FolderOpen className="h-3 w-3" />
            {usage?.folder_count || 0}
          </span>
          {totalUsage > 0 && (
            <span className="ml-auto text-[10px] font-medium text-muted-foreground/70">共 {totalUsage}</span>
          )}
          {!isUsed && (
            <span className="ml-auto text-[10px] text-muted-foreground/50">未使用</span>
          )}
        </div>
      </div>

      {/* 操作按钮 - 悬浮时出现，覆盖右上角 */}
      <div
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1"
        onClick={(e) => e.stopPropagation()}
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shadow-sm border bg-card border-border hover:bg-muted"
              onClick={onToggleBinding}
              disabled={isUpdating}
            >
              {isBound
                ? <Unlink2 className="h-3.5 w-3.5 text-amber-600" />
                : <Link2 className="h-3.5 w-3.5 text-blue-600" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{isBound ? '解除关联' : '关联到本库'}</TooltipContent>
        </Tooltip>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shadow-sm border bg-card border-border hover:bg-muted"
          onClick={onEdit}
        >
          <Edit3 className="h-3.5 w-3.5" />
        </Button>
        {!isUsed && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shadow-sm border bg-card border-border hover:bg-red-50"
            onClick={onDelete}
          >
            <Trash2 className="h-3.5 w-3.5 text-destructive" />
          </Button>
        )}
      </div>
    </div>
  )
}

// 标签列表项组件
function TagListItem({
  tag,
  usage,
  isSelected,
  isBound,
  onSelect,
  onEdit,
  onDelete,
  onToggleBinding,
  getTagColorClasses,
  isUpdating,
}: {
  tag: Tag
  usage?: TagUsageSummaryItem
  isSelected: boolean
  isBound: boolean
  onSelect: () => void
  onEdit: () => void
  onDelete: () => void
  onToggleBinding: () => void
  getTagColorClasses: (color?: string) => { bg: string; text: string; dot: string; border: string; iconBg: string }
  isUpdating: boolean
}) {
  const colors = getTagColorClasses(tag.color)
  const isUsed = usage && (usage.kb_count > 0 || usage.kb_doc_count > 0 || usage.folder_count > 0)

  return (
    <div
      onClick={onSelect}
      className={[
        'group flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors hover:bg-muted/50',
        isSelected ? 'bg-primary/5 border-l-2 border-l-primary' : '',
      ].join(' ')}
    >
      {/* 颜色圆形图标 */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${colors.bg}`}>
        <TagIcon className={`h-4 w-4 ${colors.text}`} />
      </div>

      {/* 标签名 + 描述 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{tag.name}</span>
          {isBound && (
            <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border bg-emerald-50 text-emerald-700 border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              已关联本库
            </span>
          )}
          {!isUsed && (
            <span className="text-[10px] px-1.5 py-0.5 rounded border border-border bg-muted/60 text-muted-foreground/60">
              未使用
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground truncate mt-0.5">
          {tag.description || '暂无描述'}
        </p>
      </div>

      {/* 使用统计 */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <BookOpen className="h-3.5 w-3.5" />
          {usage?.kb_count || 0}
        </span>
        <span className="flex items-center gap-1">
          <FileText className="h-3.5 w-3.5" />
          {usage?.kb_doc_count || 0}
        </span>
        <span className="flex items-center gap-1">
          <FolderOpen className="h-3.5 w-3.5" />
          {usage?.folder_count || 0}
        </span>
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onToggleBinding} disabled={isUpdating}>
              {isBound ? <Unlink2 className="h-3.5 w-3.5 text-amber-600" /> : <Link2 className="h-3.5 w-3.5 text-blue-600" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{isBound ? '解除关联' : '关联到本库'}</TooltipContent>
        </Tooltip>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onEdit}>
          <Edit3 className="h-3.5 w-3.5" />
        </Button>
        {!isUsed && (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5 text-destructive" />
          </Button>
        )}
      </div>
    </div>
  )
}

// 统计卡片组件
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`rounded-lg bg-${color}-50 border border-${color}-200 p-3 text-center`}>
      <div className={`text-2xl font-bold text-${color}-600`}>{value}</div>
      <div className={`text-xs text-${color}-700`}>{label}</div>
    </div>
  )
}

// 空状态组件
function EmptyState({ onReset, hasFilters }: { onReset: () => void; hasFilters: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
        <TagIcon className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="font-medium text-lg mb-1">
        {hasFilters ? '没有找到匹配的标签' : '暂无标签'}
      </h3>
      <p className="text-sm text-muted-foreground mb-4">
        {hasFilters ? '尝试调整筛选条件' : '创建第一个标签来开始管理'}
      </p>
      {hasFilters && (
        <Button variant="outline" onClick={onReset}>
          清空筛选
        </Button>
      )}
    </div>
  )
}

function invalidateTagQueries(queryClient: ReturnType<typeof useQueryClient>, kbId: string) {
  queryClient.invalidateQueries({ queryKey: ['kb-tags', kbId] })
  queryClient.invalidateQueries({ queryKey: ['tags', 'scoped', kbId] })
  queryClient.invalidateQueries({ queryKey: ['tags', 'scoped', 'public'] })
  queryClient.invalidateQueries({ queryKey: ['tags', 'available', kbId] })
  queryClient.invalidateQueries({ queryKey: ['tags', 'usage-summary', kbId] })
  queryClient.invalidateQueries({ queryKey: ['tags', 'usage-detail'] })
}
