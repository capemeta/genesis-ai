/**
 * 文件浏览器主组件
 * 协调所有子组件，管理状态和业务逻辑
 */
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { Upload, Filter, X, Check, Search, Folder as FolderIcon } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { ChunkPreview } from './components/chunk-preview'
import { FileTable, DEFAULT_COLUMNS, type ColumnConfig } from './components/file-table'
import { FileDetailSheet } from './components/file-detail-sheet'
import { Pagination } from './components/pagination'
import { BatchActionsBar } from './components/batch-actions-bar'
import { FolderBreadcrumb } from './components/folder-breadcrumb'
import { FileUploadDialog } from './dialogs/file-upload-dialog'
import {
    RenameDialog,
    ParseDialog,
    ChunkConfigDialog,
    BatchParseDialog,
    TagDetailSheet,
    MetadataDialog,
    BatchTagDialog,
    BatchMetadataDialog,
} from './dialogs/file-dialogs'
import type { FileItem, TagDefinition, ChunkConfig, MetadataField } from './types'
import { fetchFolderPath } from '@/lib/api/folder'
import { fetchTag, createTag, updateTag, checkTagDuplicate } from '@/lib/api/tag'
import { useDocumentAvailableTags } from '@/hooks/use-available-tags'
import type { Tag } from '@/lib/api/folder.types'
import { triggerWebSyncNowByKbDoc } from '@/lib/api/web-sync'
import {
    fetchKnowledgeBaseDocuments,
    renameDocument,
    updateDocumentTags,
    updateDocumentMetadata,
    updateDocumentTagsAndMetadata,
    getKbDocTags,
    reparseDocuments,
    cancelParseDocuments,
    type KnowledgeBaseDocument,
    type AttachDocumentsResponse
} from '@/lib/api/knowledge-base'

interface FileBrowserProps {
    kbId: string
    kbType?: string
    selectedFolderId?: string | null
    autoOpenUploadDialog?: boolean
    onTableSchemaInitialized?: (payload: AttachDocumentsResponse) => void
    onFolderChange?: (folderId: string | null) => void
    isFolderTreeCollapsed?: boolean
    onToggleFolderTree?: () => void
    onSetFolderTreeCollapsed?: (collapsed: boolean) => void
}

interface WebSyncTriggerOptions {
    forceRebuildIndex?: boolean
}

// 这些键由系统流程维护，只读展示，避免用户误改破坏内部状态。
const RESERVED_METADATA_KEYS = new Set([
    'content_kind',
    'table_rows_ready',
    'table_row_count',
    'table_rows_updated_at',
    'qa_rows_ready',
    'qa_row_count',
    'qa_rows_updated_at',
    'source_mode',
    'source_file_type',
    'qa_template_version',
    'virtual_file',
    'has_manual_edits',
    'edited_waiting_reparse',
    'pending_reparse_row_count',
    'last_rebuild_from_rows_at',
])

/**
 * 将元数据值安全转成字符串，避免对象被 Input 渲染成 [object Object]。
 */
function stringifyMetadataValue(value: unknown): string {
    if (value === null || value === undefined) {
        return ''
    }
    if (typeof value === 'string') {
        return value
    }
    if (typeof value === 'number' || typeof value === 'boolean') {
        return String(value)
    }
    try {
        return JSON.stringify(value)
    } catch {
        return String(value)
    }
}

/**
 * 系统保留键和复杂对象值统一走只读展示；只有用户自定义的简单键值对允许编辑。
 */
function normalizeMetadataFields(metadata?: Record<string, unknown>): MetadataField[] {
    if (!metadata) {
        return []
    }

    return Object.entries(metadata).map(([key, value]) => {
        const isScalarValue =
            value === null ||
            value === undefined ||
            typeof value === 'string' ||
            typeof value === 'number' ||
            typeof value === 'boolean'

        return {
            key,
            value: stringifyMetadataValue(value),
            readonly: RESERVED_METADATA_KEYS.has(key) || !isScalarValue,
        }
    })
}

/**
 * 将后端文档数据转换为前端 FileItem 格式
 */
function convertToFileItem(doc: KnowledgeBaseDocument): FileItem {
    // 格式化文件大小
    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 B'
        const k = 1024
        const sizes = ['B', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
    }

    // 格式化时间
    const formatTime = (dateStr: string | null): string => {
        if (!dateStr) return '-'
        const date = new Date(dateStr)
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
        }).replace(/\//g, '/').replace(',', '')
    }

    // 格式化持续时间
    const formatDuration = (ms: number | null): string => {
        if (!ms) return '0s'
        const seconds = Math.floor(ms / 1000)
        const minutes = Math.floor(seconds / 60)
        const remainingSeconds = seconds % 60
        const milliseconds = ms % 1000

        if (minutes > 0) {
            return `${minutes}m ${remainingSeconds}.${milliseconds.toString().padStart(3, '0')}s`
        }
        return `${remainingSeconds}.${milliseconds.toString().padStart(3, '0')}s`
    }

    // 映射解析状态：后端 pending/queued/processing/completed/failed/cancelled/cancelling/synced_chunking -> 前端状态
    const statusMap: Record<string, 'Pending' | 'Queued' | 'Processing' | 'Completed' | 'Failed' | 'Cancelled' | 'Cancelling' | 'SyncedChunking'> = {
        pending: 'Pending',
        queued: 'Queued',
        processing: 'Processing',
        completed: 'Completed',
        failed: 'Failed',
        cancelled: 'Cancelled',      // 已取消（仅普通文件）
        cancelling: 'Cancelling',    // 取消中（仅普通文件）
        synced_chunking: 'SyncedChunking', // 网页已同步、分块建索引中（仅 web 类型）
    }

    // 解析文件夹路径
    const parseFolderPath = (folder: KnowledgeBaseDocument['folder']): {
        name: string;
        path: string;
        level: number;
        pathArray?: Array<{ id: string; name: string; level: number }>;
    } | undefined => {
        if (!folder) return undefined

        // 直接使用后端提供的 full_name_path
        // 格式是 "/研发部/项目A"，这是完整的可读路径
        const displayPath = folder.full_name_path || folder.name

        return {
            name: folder.name,  // 文件夹名称（单个名称）
            path: displayPath,  // 完整路径（用于显示）
            level: folder.level,
            pathArray: folder.path_array,  // 路径数组（包含每一级的 ID 和名称）
        }
    }

    const folderInfo = parseFolderPath(doc.folder)
    const kbDocMetadata = doc.metadata || {}
    const documentMetadata = doc.document.metadata || {}
    const isManualQAVirtualDataset =
        kbDocMetadata?.content_kind === 'qa_dataset' &&
        Boolean(documentMetadata?.virtual_file) &&
        doc.document.source_type === 'manual' &&
        doc.document.asset_kind === 'virtual'

    return {
        id: doc.id,
        name: doc.display_name || doc.document.name,  // 优先使用 display_name，否则使用 document.name
        type: (doc.document.file_type || 'UNKNOWN') as 'PDF' | 'Markdown' | 'TXT' | 'DOCX' | 'XLSX' | 'PPTX',
        size: formatFileSize(doc.document.file_size),
        chunks: doc.chunk_count || 0,  // 确保默认为 0
        status: statusMap[doc.parse_status] || 'Pending',
        uploadTime: formatTime(doc.created_at),
        startTime: formatTime(doc.parse_started_at),
        duration: formatDuration(doc.parse_duration_milliseconds),
        enabled: doc.is_enabled,
        tags: doc.tags?.map(tag => tag.id) || [], // 🟢 使用后端返回的标签ID数组
        creator: doc.created_by_name || 'unknown',
        parsingLogs: doc.parsing_logs || [],
        progress: doc.parse_progress || 0,  // 🔧 直接使用后端返回的 parse_progress 字段
        parseError: doc.last_error || doc.parse_error || undefined,
        runtimeModels: doc.runtime_models || undefined,
        runtimeUpdatedAt: doc.runtime_updated_at || undefined,
        markdown_document_id: doc.markdown_document_id || null,  // 🟢 新增：Markdown 文档 ID
        folderId: doc.folder_id,
        folderName: folderInfo?.name,  // 文件夹名称（单个）
        folderPath: folderInfo?.path,  // 完整路径（如 "/研发部/项目A"）
        folderLevel: folderInfo?.level || 0,
        folderPathArray: folderInfo?.pathArray,  // 路径数组
        sourceType: doc.document.source_type,
        assetKind: doc.document.asset_kind,
        isVirtualFile: Boolean(documentMetadata?.virtual_file),
        contentKind: kbDocMetadata?.content_kind,
        canDownloadSourceFile: !isManualQAVirtualDataset,
        metadata: doc.metadata || undefined,  // 使用知识库文档的业务元数据
        intelligenceConfig: doc.intelligence_config || undefined,
        chunkConfig: doc.parse_config as ChunkConfig | undefined,
    }
}

export function FileBrowser({ kbId, kbType, selectedFolderId, autoOpenUploadDialog, onTableSchemaInitialized, onFolderChange, isFolderTreeCollapsed, onToggleFolderTree, onSetFolderTreeCollapsed }: FileBrowserProps) {
    const isWebKnowledgeBase = kbType === 'web'
    // 视图模式
    const [viewMode, setViewMode] = useState<'files' | 'chunks'>('files')
    const [chunkPreviewFile, setChunkPreviewFile] = useState<FileItem | null>(null)

    // 记必进入切片预览前的文件树状态，用于返回时恢复
    const folderTreeStateBeforeChunks = useRef<boolean | null>(null)

    // 递归查看子文件夹
    const [includeSubfolders, setIncludeSubfolders] = useState(true)

    // 使用 useCallback 包装回调函数，避免无限循环
    const handleIncludeSubfoldersChange = useCallback((checked: boolean) => {
        setIncludeSubfolders(checked)
    }, [])

    // 分页状态 - 必须在 useQuery 之前定义
    const [currentPage, setCurrentPage] = useState(1)
    const [pageSize, setPageSize] = useState(10)

    // 过滤状态 - 必须在 useQuery 之前定义
    const [searchQuery, setSearchQuery] = useState('')
    const [searchInput, setSearchInput] = useState('') // 搜索输入框的值
    const [statusFilter, setStatusFilter] = useState<string>('all')

    // 选择状态
    const [selectedFileIds, setSelectedFileIds] = useState<Set<string>>(new Set())
    const [selectedFile, setSelectedFile] = useState<FileItem | null>(null)

    // 排序状态
    type SortField = 'name' | 'uploadTime' | 'chunks' | 'size' | 'type' | 'status' | 'enabled' | 'folder'
    type SortOrder = 'asc' | 'desc' | null
    const [sortField, setSortField] = useState<SortField | null>(null)
    const [sortOrder, setSortOrder] = useState<SortOrder>(null)

    // 列显示配置状态
    const [columnConfig, setColumnConfig] = useState<ColumnConfig[]>(DEFAULT_COLUMNS)

    // 标签过滤状态
    const [selectedTagIds, setSelectedTagIds] = useState<Set<string>>(new Set())
    const [tempSelectedTagIds, setTempSelectedTagIds] = useState<Set<string>>(new Set()) // 临时选择的标签
    const [tagSearchQuery, setTagSearchQuery] = useState('') // 标签搜索
    const [isTagPopoverOpen, setIsTagPopoverOpen] = useState(false)

    // 文件夹路径（面包屑）
    const { data: folderPath = [], isLoading: isLoadingFolderPath } = useQuery({
        queryKey: ['folder-path', selectedFolderId],
        queryFn: () => fetchFolderPath(selectedFolderId!),
        enabled: !!selectedFolderId,
        staleTime: 0, // 立即标记为过期
    })

    const queryClient = useQueryClient()

    // 文件数据 - 使用真实 API
    const { data: documentsData, isLoading: isLoadingDocuments, refetch: refetchDocuments } = useQuery({
        queryKey: ['kb-documents', kbId, selectedFolderId, includeSubfolders, currentPage, pageSize, searchQuery, statusFilter],
        queryFn: () => fetchKnowledgeBaseDocuments(kbId, {
            folder_id: selectedFolderId,
            include_subfolders: includeSubfolders,
            page: currentPage,
            page_size: pageSize,
            search: searchQuery || undefined,
            parse_status: statusFilter !== 'all' ? statusFilter.toLowerCase() : undefined,
        }),
        enabled: !!kbId,
        staleTime: 0,
        refetchOnMount: true,
        // 如果有正在处理的文件，则开启轮询（每3秒一次）
        // 有正在处理/排队/取消中的文件时，自动轮询刷新状态
        refetchInterval: (query) => {
            const hasActiveTask = query.state.data?.data.some(
                (doc: any) => ['processing', 'queued', 'cancelling'].includes(doc.parse_status)
            )
            return hasActiveTask ? 3000 : false
        },
    })

    const clearChunkPreviewCache = useCallback((kbDocId: string) => {
        // 主动清理重型预览缓存，避免频繁切换文件时内存持续堆积。
        queryClient.removeQueries({ queryKey: ['chunks', kbDocId] })
        queryClient.removeQueries({ queryKey: ['chunks', 'stats', kbDocId] })
        queryClient.removeQueries({ queryKey: ['source-content', kbDocId] })
        queryClient.removeQueries({ queryKey: ['markdown-preview', kbDocId] })
    }, [queryClient])

    // 标签库 - 与文件夹树一致，从 API 拉取并持久化新建/编辑
    // 获取文档可选标签（用于标签选择）
    const { data: docTags = [] } = useDocumentAvailableTags(kbId, { limit: 200 })

    // 主标签库定义
    const tagDefinitions: TagDefinition[] = useMemo(() => {
        if (!docTags || !Array.isArray(docTags)) return []
        return docTags.map((tag: Tag) => ({
            id: tag.id,
            name: tag.name,
            description: tag.description,
            color: tag.color || 'blue',
            synonyms: tag.aliases ?? [],
        }))
    }, [docTags])

    // 标签库管理（tagDefinitions 由上方 useQuery + useMemo 提供；新建/编辑通过 createTag/updateTag 持久化）
    // 按 id 解析出的标签（文档带的是 tag_id，若不在 tagDefinitions 里则单独拉取，参考文件夹树用完整标签数据展示）
    const [resolvedTagsById, setResolvedTagsById] = useState<Record<string, TagDefinition>>({})

    // 合并主标签库和缓存的标签定义
    const allTagDefinitions: TagDefinition[] = useMemo(() => {
        const mainTags = new Map(tagDefinitions.map(tag => [tag.id, tag]))
        const cachedTags = new Map(Object.entries(resolvedTagsById).map(([id, tag]) => [id, tag]))

        // 合并，主标签库优先
        const merged = new Map([...cachedTags, ...mainTags])
        return Array.from(merged.values())
    }, [tagDefinitions, resolvedTagsById])

    // 🔧 修复：切换目录或过滤条件时，重置分页到第 1 页并清空选中状态
    // 避免切换文件夹后页码越界导致空数据，以及用户误操作看不见的文件
    useEffect(() => {
        setCurrentPage(1)
        setSelectedFileIds(new Set())
    }, [selectedFolderId, includeSubfolders, searchQuery, statusFilter])

    // 转换后端数据为前端格式
    const files: FileItem[] = useMemo(() => {
        return documentsData?.data.map(convertToFileItem) || []
    }, [documentsData?.data])

    // 缓存所有标签定义到 resolvedTagsById，避免重复查询
    useEffect(() => {
        if (!documentsData?.data) return

        const newTags: Record<string, TagDefinition> = {}
        documentsData.data.forEach(doc => {
            doc.tags?.forEach(tag => {
                if (!tagDefinitions.some(t => t.id === tag.id) && !newTags[tag.id]) {
                    newTags[tag.id] = {
                        id: tag.id,
                        name: tag.name,
                        description: tag.description,
                        color: tag.color || 'blue',
                        synonyms: tag.aliases || [],
                        allowedTargetTypes: tag.allowed_target_types || ['kb_doc'],
                    }
                }
            })
        })

        if (Object.keys(newTags).length > 0) {
            setResolvedTagsById(prev => ({ ...prev, ...newTags }))
        }
    }, [documentsData?.data, tagDefinitions])

    const totalFiles = documentsData?.total || 0

    // 🟢 移除旧的异步加载标签逻辑，现在直接使用后端返回的标签数据
    // 合并标签数据到文件列表（现在标签数据已经在 convertToFileItem 中处理）
    const filesWithTags: FileItem[] = files

    // 对话框状态
    const [showDetailSheet, setShowDetailSheet] = useState(false)
    const [showRenameDialog, setShowRenameDialog] = useState(false)
    const [showParseDialog, setShowParseDialog] = useState(false)
    const [showChunkConfigDialog, setShowChunkConfigDialog] = useState(false)
    const [showBatchParseDialog, setShowBatchParseDialog] = useState(false)
    const [showBatchConfigDialog, setShowBatchConfigDialog] = useState(false)
    const [showMetadataDialog, setShowMetadataDialog] = useState(false)
    const [showBatchMetadataDialog, setShowBatchMetadataDialog] = useState(false)
    const [showBatchTagDialog, setShowBatchTagDialog] = useState(false)
    const [showTagDetailDialog, setShowTagDetailDialog] = useState(false)
    const [showUploadDialog, setShowUploadDialog] = useState(false)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
    const [showBatchDeleteConfirm, setShowBatchDeleteConfirm] = useState(false)
    const [showCancelParseConfirm, setShowCancelParseConfirm] = useState(false)
    const [fileToCancelParse, setFileToCancelParse] = useState<FileItem | null>(null)
    const [forceBatchWebSyncRebuild, setForceBatchWebSyncRebuild] = useState(false)

    // 加载状态
    const [isSavingMetadata, setIsSavingMetadata] = useState(false)  // 新增：保存元数据加载状态
    const [isSavingBatchTags, setIsSavingBatchTags] = useState(false)  // 新增：批量保存标签加载状态
    const [isSavingBatchMetadata, setIsSavingBatchMetadata] = useState(false)  // 新增：批量保存元数据加载状态

    useEffect(() => {
        if (autoOpenUploadDialog) {
            setShowUploadDialog(true)
        }
    }, [autoOpenUploadDialog])

    // 表单状态
    const [fileToProcess, setFileToProcess] = useState<FileItem | null>(null)
    const [fileToConfig, setFileToConfig] = useState<FileItem | null>(null)
    const [fileToEditMetadata, setFileToEditMetadata] = useState<FileItem | null>(null)
    const [fileToDelete, setFileToDelete] = useState<FileItem | null>(null)
    const [chunkConfig, setChunkConfig] = useState<ChunkConfig>({
        chunkSize: 512,
        chunkOverlap: 50,
        separators: '\\n\\n,\\n,。,！,？',
        chunkMethod: 'recursive',
    })

    // 元数据和标签编辑状态
    const [editingTags, setEditingTags] = useState<string[]>([])
    const [newTag, setNewTag] = useState('')
    const [editingMetadata, setEditingMetadata] = useState<MetadataField[]>([])
    const [docContextEnabled, setDocContextEnabled] = useState(false)
    const [docContextContent, setDocContextContent] = useState('')
    const [newMetadataKey, setNewMetadataKey] = useState('')
    const [newMetadataValue, setNewMetadataValue] = useState('')

    const [editingTagDetail, setEditingTagDetail] = useState<TagDefinition | null>(null)
    const [tagDetailForm, setTagDetailForm] = useState({
        name: '',
        description: '',
        synonyms: [] as string[],
        color: 'blue',
        allowedTargetTypes: ['kb_doc'] as ('kb_doc' | 'kb' | 'folder')[],
    })
    const [newSynonym, setNewSynonym] = useState('')

    // 是否为 UUID（editingTags 中可能是 tag id 或未保存的标签名，与文件夹树一致）
    const isTagId = (s: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s)

    // 解析 tagId 或 tagName → TagDefinition：优先查找 allTagDefinitions，然后查找 resolvedTagsById
    const getTagDefinition = useMemo(() => {
        return (tagIdOrName: string): TagDefinition | undefined => {
            if (isTagId(tagIdOrName)) {
                // 从合并的标签定义中查找
                const tag = allTagDefinitions.find((t) => t.id === tagIdOrName)
                if (tag) return tag

                // 都没找到，返回undefined
                return undefined
            }
            // 按名称查找，只在合并的标签定义中查找
            return allTagDefinitions.find((t) => t.name === tagIdOrName) ?? { id: tagIdOrName, name: tagIdOrName, color: 'blue', synonyms: [] }
        }
    }, [allTagDefinitions])

    // 打开元数据弹窗时：仅对 UUID 且不在 tagDefinitions 的 id 拉取单条标签并缓存
    useEffect(() => {
        if (!showMetadataDialog || editingTags.length === 0) return
        const missingIds = editingTags.filter(
            (id) => isTagId(id) && !tagDefinitions.some((t) => t.id === id) && !resolvedTagsById[id]
        )
        if (missingIds.length === 0) return
        let cancelled = false
        missingIds.forEach((id) => {
            fetchTag(id)
                .then((tag) => {
                    if (cancelled) return
                    const def: TagDefinition = {
                        id: tag.id,
                        name: tag.name,
                        description: tag.description,
                        color: tag.color || 'blue',
                        synonyms: tag.aliases ?? [],
                        allowedTargetTypes: tag.allowed_target_types || ['kb_doc'],
                    }
                    setResolvedTagsById((prev) => ({ ...prev, [id]: def }))
                })
                .catch(() => { /* 忽略单条拉取失败，界面仍显示 id */ })
        })
        return () => { cancelled = true }
    }, [showMetadataDialog, editingTags, tagDefinitions, resolvedTagsById])

    // 创建标签（详细设置里新建 / 快速添加新名称时调用，持久化到 tags API）
    const { mutate: handleCreateTag, isPending: isCreatingTag } = useMutation({
        mutationFn: createTag,
        onSuccess: async (tag) => {
            // 立即更新本地缓存
            const def: TagDefinition = {
                id: tag.id,
                name: tag.name,
                description: tag.description,
                color: tag.color || 'blue',
                synonyms: tag.aliases ?? [],
                allowedTargetTypes: tag.allowed_target_types || ['kb_doc'],
            }
            setResolvedTagsById((prev) => ({ ...prev, [tag.id]: def }))

            // 强制刷新所有相关的查询缓存
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ['tags', 'list', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'available', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'document-available', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'folder-available', kbId] }),
                queryClient.invalidateQueries({
                    queryKey: ['kb-documents', kbId],
                    exact: false  // 匹配所有以此开头的查询键
                })
            ])

            // 强制重新获取文档数据，确保新标签立即显示
            await refetchDocuments()

            toast.success('标签创建成功')
            setShowTagDetailDialog(false)
            setEditingTagDetail(null)
            setTagDetailForm({ name: '', description: '', synonyms: [], color: 'blue', allowedTargetTypes: ['kb_doc'] })
            setNewSynonym('')
            setNewTag('')
            // 新建后自动加到当前文件的编辑标签列表（快速添加或详细设置保存都会走这里）
            setEditingTags((prev) => (prev.includes(tag.id) ? prev : [...prev, tag.id]))
        },
        onError: (err: any) => {
            toast.error(err?.response?.data?.detail ?? '创建标签失败')
        },
    })

    // 更新标签（编辑标签和元数据 → 详细设置 → 编辑标签，持久化到 tags API）
    const { mutate: handleUpdateTag, isPending: isUpdatingTag } = useMutation({
        mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateTag>[1] }) => updateTag(id, data),
        onSuccess: async (updatedTag) => {
            // 立即回写到 resolvedTagsById，使「编辑标签和元数据」里的标签颜色等变更即时生效
            if (updatedTag?.id) {
                const def: TagDefinition = {
                    id: updatedTag.id,
                    name: updatedTag.name,
                    description: updatedTag.description,
                    color: updatedTag.color || 'blue',
                    synonyms: updatedTag.aliases ?? [],
                    allowedTargetTypes: updatedTag.allowed_target_types || ['kb_doc'],
                }
                setResolvedTagsById((prev) => ({ ...prev, [updatedTag.id]: def }))
            }

            // 强制刷新所有相关的查询缓存
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ['tags', 'list', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'available', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'document-available', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'folder-available', kbId] }),
                queryClient.invalidateQueries({
                    queryKey: ['kb-documents', kbId],
                    exact: false  // 匹配所有以此开头的查询键
                })
            ])

            // 强制重新获取文档数据，确保标签颜色立即更新
            await refetchDocuments()

            toast.success('标签更新成功')
            setShowTagDetailDialog(false)
            setEditingTagDetail(null)
            setTagDetailForm({ name: '', description: '', synonyms: [], color: 'blue', allowedTargetTypes: ['kb_doc'] })
            setNewSynonym('')
        },
        onError: (err: any) => {
            toast.error(err?.response?.data?.detail ?? '更新标签失败')
        },
    })

    // 排序处理函数
    const handleSort = (field: SortField) => {
        if (sortField === field) {
            // 同一字段：null -> asc -> desc -> null
            if (sortOrder === null) {
                setSortOrder('asc')
            } else if (sortOrder === 'asc') {
                setSortOrder('desc')
            } else {
                setSortField(null)
                setSortOrder(null)
            }
        } else {
            // 不同字段：重置为 asc
            setSortField(field)
            setSortOrder('asc')
        }
    }

    // 计算分页数据
    // 注意：现在分页、搜索、状态过滤都在服务端处理
    // 这里只需要处理客户端的标签过滤和排序
    let filteredFiles = filesWithTags.filter((file) => {
        // 标签过滤（多选 - 文件必须包含所有选中的标签）
        if (selectedTagIds.size > 0) {
            const hasAllTags = Array.from(selectedTagIds).every((tagId) => file.tags.includes(tagId))
            if (!hasAllTags) {
                return false
            }
        }
        return true
    })

    // 应用排序
    if (sortField && sortOrder) {
        filteredFiles = [...filteredFiles].sort((a, b) => {
            let compareResult = 0

            switch (sortField) {
                case 'name':
                    compareResult = a.name.localeCompare(b.name, 'zh-CN')
                    break
                case 'uploadTime':
                    compareResult = new Date(a.uploadTime).getTime() - new Date(b.uploadTime).getTime()
                    break
                case 'chunks':
                    compareResult = a.chunks - b.chunks
                    break
                case 'size':
                    // 解析大小字符串（如 "8.4 MB"）
                    const parseSize = (sizeStr: string): number => {
                        const match = sizeStr.match(/^([\d.]+)\s*(KB|MB|GB)$/i)
                        if (!match) return 0
                        const value = parseFloat(match[1])
                        const unit = match[2].toUpperCase()
                        const multipliers: Record<string, number> = { KB: 1, MB: 1024, GB: 1024 * 1024 }
                        return value * (multipliers[unit] || 1)
                    }
                    compareResult = parseSize(a.size) - parseSize(b.size)
                    break
                case 'type':
                    compareResult = a.type.localeCompare(b.type)
                    break
                case 'status':
                    // 状态排序优先级：Completed > Processing > Queued > Pending > Failed
                    const statusOrder: Record<string, number> = {
                        Completed: 1,
                        Processing: 2,
                        Queued: 3,
                        Pending: 4,
                        Failed: 5,
                    }
                    compareResult = (statusOrder[a.status] || 99) - (statusOrder[b.status] || 99)
                    break
                case 'enabled':
                    // 启用状态：true > false
                    compareResult = (a.enabled ? 1 : 0) - (b.enabled ? 1 : 0)
                    break
                case 'folder':
                    // 文件夹排序
                    const aFolder = a.folderName || ''
                    const bFolder = b.folderName || ''
                    compareResult = aFolder.localeCompare(bFolder, 'zh-CN')
                    break
            }

            return sortOrder === 'asc' ? compareResult : -compareResult
        })
    }

    const totalPages = Math.ceil(totalFiles / pageSize)
    const startIndex = (currentPage - 1) * pageSize
    const endIndex = Math.min(startIndex + pageSize, totalFiles)
    const currentPageFiles = filteredFiles

    // 标签选择处理
    const handleTagToggle = (tagId: string) => {
        const newSelected = new Set(tempSelectedTagIds)
        if (newSelected.has(tagId)) {
            newSelected.delete(tagId)
        } else {
            newSelected.add(tagId)
        }
        setTempSelectedTagIds(newSelected)
    }

    const handleClearTags = () => {
        setTempSelectedTagIds(new Set())
    }

    const handleConfirmTags = () => {
        setSelectedTagIds(new Set(tempSelectedTagIds))
        setIsTagPopoverOpen(false)
        setTagSearchQuery('')
    }

    const handleCancelTags = () => {
        setTempSelectedTagIds(new Set(selectedTagIds))
        setIsTagPopoverOpen(false)
        setTagSearchQuery('')
    }

    // 搜索处理
    const handleSearch = () => {
        setSearchQuery(searchInput)
    }

    const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            handleSearch()
        }
    }

    // 过滤标签列表（用于标签搜索）
    const filteredTagDefinitions = allTagDefinitions.filter((tag) => {
        if (!tagSearchQuery) return true
        const query = tagSearchQuery.toLowerCase()
        return (
            tag.name.toLowerCase().includes(query) ||
            tag.description?.toLowerCase().includes(query) ||
            (tag.synonyms ?? []).some((s) => s.toLowerCase().includes(query))
        )
    })

    // ==================== 选择操作 ====================
    const handleSelectAll = (checked: boolean) => {
        if (checked) {
            const newSelected = new Set(selectedFileIds)
            currentPageFiles.forEach((file) => newSelected.add(file.id))
            setSelectedFileIds(newSelected)
        } else {
            const newSelected = new Set(selectedFileIds)
            currentPageFiles.forEach((file) => newSelected.delete(file.id))
            setSelectedFileIds(newSelected)
        }
    }

    const handleSelectFile = (fileId: string, checked: boolean) => {
        const newSelected = new Set(selectedFileIds)
        if (checked) {
            newSelected.add(fileId)
        } else {
            newSelected.delete(fileId)
        }
        setSelectedFileIds(newSelected)
    }

    const getSelectedFiles = () => {
        return filesWithTags.filter((file) => selectedFileIds.has(file.id))
    }

    // ==================== 文件操作 ====================
    const handleToggleEnabled = async (fileId: string) => {
        try {
            const file = filesWithTags.find(f => f.id === fileId)
            if (!file) return

            const newEnabledState = !file.enabled

            const { toggleDocumentsEnabled } = await import('@/lib/api/knowledge-base')
            await toggleDocumentsEnabled(fileId, newEnabledState)  // 单个ID，自动转为数组

            toast.success(`文档已${newEnabledState ? '启用' : '禁用'}`)

            // 刷新数据
            refetchDocuments()
        } catch (error: any) {
            console.error('切换文档启用状态失败:', error)
            toast.error(error.response?.data?.detail || '操作失败，请重试')
        }
    }

    const handleRename = (file: FileItem) => {
        setSelectedFile(file)
        setShowRenameDialog(true)
    }

    const handleRenameConfirm = async (newName: string) => {
        if (!selectedFile) return

        try {
            await renameDocument(selectedFile.id, newName)
            toast.success('重命名成功')
            setShowRenameDialog(false)
            setSelectedFile(null)
            // 刷新列表
            refetchDocuments()
        } catch (error: any) {
            console.error('重命名失败:', error)
            toast.error(error.response?.data?.detail || '重命名失败')
        }
    }

    const handleDownload = async (file: FileItem) => {
        setDownloadProgressMap((prev) => ({ ...prev, [file.id]: 0 }))
        const actionLabel = file.contentKind === 'qa_dataset' ? '源文件下载' : '下载'
        try {
            const { downloadDocument } = await import('@/lib/api/document')
            await downloadDocument(file.id, undefined, ({ percent }) => {
                setDownloadProgressMap((prev) => ({
                    ...prev,
                    [file.id]: typeof percent === 'number' ? percent : null,
                }))
            })
            toast.success(`${actionLabel}完成: ${file.name}`, {
                position: 'bottom-right'  // 右下角显示
            })
        } catch (error: any) {
            console.error('下载文件失败:', error)
            toast.error(error.message || `${actionLabel}失败`, {
                position: 'bottom-right'  // 右下角显示
            })
        } finally {
            setDownloadProgressMap((prev) => {
                const next = { ...prev }
                delete next[file.id]
                return next
            })
        }
    }

    const handleCancelParse = (file: FileItem) => {
        setFileToCancelParse(file)
        setShowCancelParseConfirm(true)
    }

    const handleCancelParseConfirm = async () => {
        if (!fileToCancelParse) return

        const fileId = fileToCancelParse.id
        const previousParseStatus = fileToCancelParse.status.toLowerCase()

        // 关闭确认框
        setShowCancelParseConfirm(false)

        // 1. 立即标记为加载中
        setParsingFileIds(prev => new Set(prev).add(fileId))

        // 2. 乐观更新：立即更新所有匹配的查询缓存
        queryClient.setQueriesData(
            { queryKey: ['kb-documents', kbId], exact: false },
            (old: any) => {
                if (!old?.data) return old
                return {
                    ...old,
                    data: old.data.map((doc: KnowledgeBaseDocument) =>
                        doc.id === fileId
                            ? { ...doc, parse_status: 'cancelling', parse_error: '取消中...' }
                            : doc
                    )
                }
            }
        )

        try {
            const result = await cancelParseDocuments(fileId)
            toast.success(result.message || '已取消解析任务')

            // 延迟刷新
            setTimeout(() => {
                refetchDocuments()
            }, 500)
        } catch (error: any) {
            console.error('取消解析失败:', error)

            // 失败时回滚状态
            queryClient.setQueriesData(
                { queryKey: ['kb-documents', kbId], exact: false },
                (old: any) => {
                    if (!old?.data) return old
                    return {
                        ...old,
                        data: old.data.map((doc: KnowledgeBaseDocument) =>
                            doc.id === fileId
                                ? { ...doc, parse_status: previousParseStatus, parse_error: null }
                                : doc
                        )
                    }
                }
            )

            toast.error(error.response?.data?.detail || '取消失败')
        } finally {
            // 移除加载标记
            setParsingFileIds(prev => {
                const next = new Set(prev)
                next.delete(fileId)
                return next
            })
            setFileToCancelParse(null)
        }
    }

    const handleDelete = (file: FileItem) => {
        setFileToDelete(file)
        setShowDeleteConfirm(true)
    }

    const handleDeleteConfirm = async () => {
        if (!fileToDelete) return

        try {
            const { detachDocumentsFromKB } = await import('@/lib/api/knowledge-base')
            await detachDocumentsFromKB(kbId, fileToDelete.id)

            toast.success('文档已从知识库中移除')

            // 关闭对话框（onOpenChange 会自动清空 fileToDelete）
            setShowDeleteConfirm(false)

            // 刷新数据
            refetchDocuments()
        } catch (error: any) {
            console.error('移除文档失败:', error)
            toast.error(error.response?.data?.detail || '移除失败，请重试')
        }
    }

    const handleViewDetail = (file: FileItem) => {
        setSelectedFile(file)
        setShowDetailSheet(true)
    }

    // 🔧 正在解析的文件ID集合（用于禁用按钮）
    const [parsingFileIds, setParsingFileIds] = useState<Set<string>>(new Set())
    // 下载进度（0-100），null 表示可见但总大小未知（仅显示“下载中”）
    const [downloadProgressMap, setDownloadProgressMap] = useState<Record<string, number | null>>({})

    const triggerWebSyncForFiles = async (
        files: FileItem[],
        options?: WebSyncTriggerOptions,
    ) => {
        if (files.length === 0) return
        const forceRebuildIndex = Boolean(options?.forceRebuildIndex)

        const fileIds = files.map(file => file.id)
        setParsingFileIds(prev => {
            const next = new Set(prev)
            fileIds.forEach(id => next.add(id))
            return next
        })

        // 先乐观更新为排队中，后续以服务端状态为准。
        queryClient.setQueriesData(
            { queryKey: ['kb-documents', kbId], exact: false },
            (old: any) => {
                if (!old?.data) return old
                return {
                    ...old,
                    data: old.data.map((doc: KnowledgeBaseDocument) =>
                        fileIds.includes(doc.id)
                            ? { ...doc, parse_status: 'queued', parse_error: null }
                            : doc
                    )
                }
            }
        )

        const results = await Promise.allSettled(
            fileIds.map(kbDocId => triggerWebSyncNowByKbDoc({
                kb_doc_id: kbDocId,
                force_rebuild_index: forceRebuildIndex,
            }))
        )
        const successCount = results.filter(item => item.status === 'fulfilled').length
        const failedCount = results.length - successCount

        if (successCount > 0 && failedCount === 0) {
            toast.success(
                successCount === 1
                    ? (forceRebuildIndex ? '已触发网页同步，并将在本次同步后始终重建索引' : '已触发网页同步')
                    : (forceRebuildIndex
                        ? `已触发 ${successCount} 个网页同步任务，并将在本次同步后始终重建索引`
                        : `已触发 ${successCount} 个网页同步任务`)
            )
        } else if (successCount > 0) {
            toast.warning(`成功 ${successCount} 个，失败 ${failedCount} 个`)
        } else {
            toast.error('触发网页同步失败，请重试')
        }

        setParsingFileIds(prev => {
            const next = new Set(prev)
            fileIds.forEach(id => next.delete(id))
            return next
        })
        refetchDocuments()
    }

    const handleParse = async (file: FileItem, options?: WebSyncTriggerOptions) => {
        if (isWebKnowledgeBase) {
            await triggerWebSyncForFiles([file], options)
            return
        }
        setFileToProcess(file)
        setShowParseDialog(true)
    }

    const handleParseConfirm = async () => {
        if (!fileToProcess) return

        const fileId = fileToProcess.id

        // 1. 立即关闭对话框并标记为加载中（禁用按钮）
        setShowParseDialog(false)
        setParsingFileIds(prev => new Set(prev).add(fileId))

        // 2. 乐观更新：立即更新所有匹配的查询缓存为 "Queued"
        queryClient.setQueriesData(
            { queryKey: ['kb-documents', kbId], exact: false },
            (old: any) => {
                if (!old?.data) return old
                return {
                    ...old,
                    data: old.data.map((doc: KnowledgeBaseDocument) =>
                        doc.id === fileId
                            ? { ...doc, parse_status: 'queued', parse_error: null }
                            : doc
                    )
                }
            }
        )

        try {
            const result = await reparseDocuments(fileId)

            // 显示成功消息
            if (result.success) {
                toast.success(result.message || '已提交解析任务')
            } else {
                toast.warning(result.message || '部分任务被跳过')
            }

            // 清理文件引用
            setFileToProcess(null)

            // 延迟刷新（给后端一点时间）
            setTimeout(() => {
                refetchDocuments()
            }, 500)
        } catch (error: any) {
            console.error('启动解析失败:', error)

            // 失败时回滚状态
            queryClient.setQueriesData(
                { queryKey: ['kb-documents', kbId], exact: false },
                (old: any) => {
                    if (!old?.data) return old
                    return {
                        ...old,
                        data: old.data.map((doc: KnowledgeBaseDocument) =>
                            doc.id === fileId
                                ? { ...doc, parse_status: fileToProcess.status.toLowerCase() }
                                : doc
                        )
                    }
                }
            )

            toast.error(error.response?.data?.detail || '启动解析失败')
        } finally {
            // 移除加载标记
            setParsingFileIds(prev => {
                const next = new Set(prev)
                next.delete(fileId)
                return next
            })
        }
    }

    const handleChunkConfig = (file: FileItem) => {
        setFileToConfig(file)
        if (file.chunkConfig) {
            setChunkConfig(file.chunkConfig)
        } else {
            setChunkConfig({
                chunkSize: 512,
                chunkOverlap: 50,
                separators: '\\n\\n,\\n,。,！,？',
                chunkMethod: 'recursive',
            })
        }
        setShowChunkConfigDialog(true)
    }

    const handleChunkConfigSave = () => {
        if (fileToConfig) {
            // TODO: Call API to save chunk config
            console.log('Save chunk config for file:', fileToConfig.id, chunkConfig)
            setShowChunkConfigDialog(false)
            setFileToConfig(null)
            // After API call succeeds, refetch the data
            refetchDocuments()
        }
    }

    const handleEditMetadata = async (file: FileItem) => {
        setFileToEditMetadata(file)
        setEditingMetadata(normalizeMetadataFields(file.metadata))
        const persistentContext = (file.intelligenceConfig?.persistent_context || {}) as Record<string, any>
        setDocContextEnabled(Boolean(persistentContext.enabled))
        setDocContextContent(String(persistentContext.content || ''))
        setNewTag('')
        setNewMetadataKey('')
        setNewMetadataValue('')
        setShowMetadataDialog(true)

        try {
            // 获取完整的标签信息（包含 id, name, color）
            const { tags } = await getKbDocTags(file.id)

            // 直接使用标签ID，但同时缓存标签定义
            setEditingTags(tags.map((t) => t.id))

            // 缓存标签定义，确保界面能正确显示标签名称
            tags.forEach(tag => {
                setResolvedTagsById(prev => ({
                    ...prev,
                    [tag.id]: {
                        id: tag.id,
                        name: tag.name,
                        color: tag.color || 'blue',
                        synonyms: []
                    }
                }))
            })
        } catch {
            // 如果获取失败，使用文件对象中的标签ID（可能为空）
            setEditingTags(file.tags?.length ? [...file.tags] : [])
        }
    }

    // ==================== 标签和元数据操作（与文件夹树一致：快速添加不调后端，保存时再处理） ====================
    const handleAddTag = () => {
        if (!newTag.trim()) {
            toast.error('请输入标签名称')
            return
        }
        const tagName = newTag.trim()
        const existingTag = allTagDefinitions.find((t) => t.name.toLowerCase() === tagName.toLowerCase())

        if (existingTag) {
            if (!editingTags.includes(existingTag.id)) {
                setEditingTags([...editingTags, existingTag.id])
            }
            toast.success('已添加标签')
        } else {
            // 新标签：仅加入本地列表，不调用后端，保存时再 createTag + setKbDocTags
            if (!editingTags.includes(tagName)) {
                setEditingTags([...editingTags, tagName])
            }
            toast.success('已添加新标签')
        }
        setNewTag('')
    }

    /** 从可选标签列表点击添加（按 id），与文件夹树一致 */
    const handleAddTagById = (tagId: string) => {
        if (!editingTags.includes(tagId)) {
            setEditingTags([...editingTags, tagId])
        }
        toast.success('已添加标签')
    }

    const handleEditTagDetail = async (tagIdOrName?: string) => {
        if (tagIdOrName) {
            if (isTagId(tagIdOrName)) {
                let tag = getTagDefinition(tagIdOrName)
                if (!tag || !tag.id) {
                    try {
                        const t = await fetchTag(tagIdOrName)
                        tag = {
                            id: t.id,
                            name: t.name,
                            description: t.description,
                            color: t.color || 'blue',
                            synonyms: t.aliases ?? [],
                            allowedTargetTypes: t.allowed_target_types || ['kb_doc'],
                        }
                        setResolvedTagsById((prev) => ({ ...prev, [tagIdOrName]: tag! }))
                    } catch {
                        toast.error('获取标签详情失败')
                        return
                    }
                }
                if (tag?.id) {
                    setEditingTagDetail(tag)
                    setTagDetailForm({
                        name: tag.name,
                        description: tag.description || '',
                        synonyms: [...(tag.synonyms ?? [])],
                        color: tag.color || 'blue',
                        allowedTargetTypes: tag.allowedTargetTypes?.length ? tag.allowedTargetTypes : ['kb_doc'],
                    })
                }
            } else {
                // 未保存的标签名：仅预填名称，保存时再创建
                setEditingTagDetail(null)
                setTagDetailForm({
                    name: tagIdOrName,
                    description: '',
                    synonyms: [],
                    color: 'blue',
                    allowedTargetTypes: ['kb_doc'],
                })
            }
        } else {
            setEditingTagDetail(null)
            setTagDetailForm({
                name: newTag.trim() || '',
                description: '',
                synonyms: [],
                color: 'blue',
                allowedTargetTypes: ['kb_doc'],
            })
        }
        setNewSynonym('')
        setShowTagDetailDialog(true)
    }

    const handleSaveTagDetail = () => {
        const name = tagDetailForm.name.trim()
        if (!name) return

        if (editingTagDetail) {
            handleUpdateTag({
                id: editingTagDetail.id,
                data: {
                    name,
                    description: tagDetailForm.description.trim() || undefined,
                    aliases: tagDetailForm.synonyms.length > 0 ? tagDetailForm.synonyms : undefined,
                    color: tagDetailForm.color,
                    allowed_target_types: tagDetailForm.allowedTargetTypes,
                },
            })
        } else {
            handleCreateTag({
                name,
                description: tagDetailForm.description.trim() || undefined,
                aliases: tagDetailForm.synonyms.length > 0 ? tagDetailForm.synonyms : undefined,
                color: tagDetailForm.color,
                allowed_target_types: tagDetailForm.allowedTargetTypes,
                kb_id: kbId,
            })
        }
    }

    // 计算标签保存的加载状态
    const isTagSaving = isCreatingTag || isUpdatingTag

    const handleAddSynonym = () => {
        if (newSynonym.trim() && !tagDetailForm.synonyms.includes(newSynonym.trim())) {
            setTagDetailForm({
                ...tagDetailForm,
                synonyms: [...tagDetailForm.synonyms, newSynonym.trim()],
            })
            setNewSynonym('')
        }
    }

    const handleRemoveSynonym = (synonym: string) => {
        setTagDetailForm({
            ...tagDetailForm,
            synonyms: tagDetailForm.synonyms.filter((s) => s !== synonym),
        })
    }

    const handleRemoveTag = (tagId: string) => {
        setEditingTags(editingTags.filter((t) => t !== tagId))
    }

    const handleAddMetadata = () => {
        if (newMetadataKey.trim() && newMetadataValue.trim()) {
            const exists = editingMetadata.find((m) => m.key === newMetadataKey.trim())
            if (!exists) {
                setEditingMetadata([
                    ...editingMetadata,
                    { key: newMetadataKey.trim(), value: newMetadataValue.trim(), readonly: false },
                ])
                setNewMetadataKey('')
                setNewMetadataValue('')
            }
        }
    }

    const handleUpdateMetadata = (index: number, key: string, value: string) => {
        const updated = [...editingMetadata]
        if (updated[index]?.readonly) {
            return
        }
        updated[index] = { ...updated[index], key, value }
        setEditingMetadata(updated)
    }

    const handleRemoveMetadata = (index: number) => {
        if (editingMetadata[index]?.readonly) {
            return
        }
        setEditingMetadata(editingMetadata.filter((_, i) => i !== index))
    }

    const handleSaveMetadata = async () => {
        if (!fileToEditMetadata) return
        const kbDocId = fileToEditMetadata.id // knowledge_base_documents.id，resource_tags.target_id=kb_doc

        setIsSavingMetadata(true)  // 开始保存，设置加载状态

        try {
            // 将 editingTags（id 或未保存的标签名）解析为 tag ids，保存时再 createTag + setKbDocTags
            const tagIds: string[] = []
            const createdTagsMap: Record<string, string> = {} // 临时标签名 -> 真实标签ID 的映射

            for (const entry of editingTags) {
                if (isTagId(entry)) {
                    tagIds.push(entry)
                } else {
                    const name = entry.trim()
                    if (!name) continue
                    const { exists, tag } = await checkTagDuplicate(kbId, name)
                    if (exists && tag) {
                        let resolvedTag = tag
                        if (!(tag.allowed_target_types || []).includes('kb_doc')) {
                            resolvedTag = await updateTag(tag.id, {
                                allowed_target_types: Array.from(new Set([...(tag.allowed_target_types || []), 'kb_doc'])),
                            })
                        }
                        tagIds.push(resolvedTag.id)
                        createdTagsMap[name] = resolvedTag.id
                    } else {
                        const created = await createTag({ name, kb_id: kbId, allowed_target_types: ['kb_doc'] })
                        tagIds.push(created.id)
                        createdTagsMap[name] = created.id
                    }
                }
            }

            // 准备元数据
            const metadataRecord: Record<string, string> = {}
            for (const { key, value, readonly } of editingMetadata) {
                const normalizedKey = key.trim()
                if (!normalizedKey || readonly || RESERVED_METADATA_KEYS.has(normalizedKey)) {
                    continue
                }
                metadataRecord[normalizedKey] = value
            }

            // 统一调用新接口保存（元数据 + 标签）
            const intelligenceConfig = {
                ...(fileToEditMetadata.intelligenceConfig || {}),
                persistent_context: {
                    enabled: docContextEnabled,
                    content: docContextEnabled ? docContextContent.trim() : '',
                },
            }
            await updateDocumentTagsAndMetadata(kbDocId, {
                metadata: metadataRecord,
                tag_ids: tagIds,
                intelligence_config: intelligenceConfig,
                merge_metadata: false  // 单个文档编辑：全量覆盖模式
            })

            // 更新 editingTags，将临时标签名替换为真实的标签ID
            const updatedEditingTags = editingTags.map(entry => {
                if (!isTagId(entry) && createdTagsMap[entry.trim()]) {
                    return createdTagsMap[entry.trim()]
                }
                return entry
            })
            setEditingTags(updatedEditingTags)

            // 立即更新本地缓存中的标签定义
            for (const tagId of Object.values(createdTagsMap)) {
                const createdTag = await fetchTag(tagId).catch(() => null)
                if (createdTag) {
                    const def: TagDefinition = {
                        id: createdTag.id,
                        name: createdTag.name,
                        description: createdTag.description,
                        color: createdTag.color || 'blue',
                        synonyms: createdTag.aliases ?? [],
                        allowedTargetTypes: createdTag.allowed_target_types || ['kb_doc'],
                    }
                    setResolvedTagsById((prev) => ({ ...prev, [createdTag.id]: def }))
                }
            }

            // 强制刷新所有相关的查询缓存
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ['tags', 'list', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'available', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'document-available', kbId] }),
                queryClient.invalidateQueries({ queryKey: ['tags', 'folder-available', kbId] }),
                queryClient.invalidateQueries({
                    queryKey: ['kb-documents', kbId],
                    exact: false  // 匹配所有以此开头的查询键
                })
            ])

            // 强制重新获取文档数据，确保标签更新后界面同步
            await refetchDocuments()

            toast.success('保存成功')
            setShowMetadataDialog(false)
            setFileToEditMetadata(null)
            setDocContextEnabled(false)
            setDocContextContent('')
        } catch (err: any) {
            toast.error(err?.response?.data?.detail ?? '保存失败')
        } finally {
            setIsSavingMetadata(false)  // 保存完成，恢复状态
        }
    }

    // ==================== 批量操作 ====================
    const handleBatchDelete = () => {
        const selectedFiles = getSelectedFiles()
        if (selectedFiles.length === 0) return

        setShowBatchDeleteConfirm(true)
    }

    const handleBatchDeleteConfirm = async () => {
        try {
            const { detachDocumentsFromKB } = await import('@/lib/api/knowledge-base')
            const result = await detachDocumentsFromKB(kbId, Array.from(selectedFileIds))

            toast.success(result.message || `已移除 ${result.data.detached_count} 个文档`)

            // 关闭对话框（onOpenChange 会自动清空 selectedFileIds）
            setShowBatchDeleteConfirm(false)

            // 刷新数据
            refetchDocuments()
        } catch (error: any) {
            console.error('批量移除文档失败:', error)
            toast.error(error.response?.data?.detail || '移除失败，请重试')
        }
    }

    const handleBatchToggleEnabled = async (enabled: boolean) => {
        const selectedFiles = getSelectedFiles()
        if (selectedFiles.length === 0) return

        try {
            const { toggleDocumentsEnabled } = await import('@/lib/api/knowledge-base')
            const result = await toggleDocumentsEnabled(Array.from(selectedFileIds), enabled)

            toast.success(result.message || `已${enabled ? '启用' : '禁用'} ${result.data.updated_count} 个文档`)

            // 不清空选择，保持选中状态，方便用户继续操作
            // setSelectedFileIds(new Set())  // ❌ 移除这行

            // 刷新数据
            refetchDocuments()
        } catch (error: any) {
            console.error('批量切换文档启用状态失败:', error)
            toast.error(error.response?.data?.detail || '操作失败，请重试')
        }
    }

    const handleBatchParse = () => {
        const selectedFiles = getSelectedFiles()
        if (selectedFiles.length === 0) return
        if (isWebKnowledgeBase) {
            setShowBatchParseDialog(true)
            return
        }

        setShowBatchParseDialog(true)
    }

    const handleBatchParseConfirm = async () => {
        const ids = Array.from(selectedFileIds)
        if (ids.length === 0) return

        if (isWebKnowledgeBase) {
            const selectedFiles = getSelectedFiles()
            await triggerWebSyncForFiles(selectedFiles, { forceRebuildIndex: forceBatchWebSyncRebuild })
            setShowBatchParseDialog(false)
            setForceBatchWebSyncRebuild(false)
            return
        }

        try {
            await reparseDocuments(ids)
            toast.success(`已启动 ${ids.length} 个文件的解析任务`)
            setShowBatchParseDialog(false)
            // 刷新列表
            refetchDocuments()
        } catch (error: any) {
            console.error('批量启动解析失败:', error)
            toast.error(error.response?.data?.detail || '批量启动解析失败')
        }
    }

    const handleBatchConfig = () => {
        const selectedFiles = getSelectedFiles()
        if (selectedFiles.length === 0) return

        setChunkConfig({
            chunkSize: 512,
            chunkOverlap: 50,
            separators: '\\n\\n,\\n,。,！,？',
            chunkMethod: 'recursive',
        })
        setShowBatchConfigDialog(true)
    }

    const handleBatchConfigSave = () => {
        // TODO: Call API to batch save chunk config
        console.log('Batch save chunk config:', Array.from(selectedFileIds), chunkConfig)
        setShowBatchConfigDialog(false)
        // 保持选中状态，方便用户继续操作（如启动解析）
        // setSelectedFileIds(new Set())  // ❌ 移除
        // After API call succeeds, refetch the data
        refetchDocuments()
    }

    const handleBatchSaveTags = async () => {
        setIsSavingBatchTags(true)  // 开始保存，设置加载状态

        try {
            const tagIds: string[] = []
            const createdTagsMap: Record<string, string> = {} // 临时标签名 -> 真实标签ID 的映射

            for (const entry of editingTags) {
                if (isTagId(entry)) {
                    tagIds.push(entry)
                } else {
                    const name = entry.trim()
                    if (!name) continue
                    const { exists, tag } = await checkTagDuplicate(kbId, name)
                    if (exists && tag) {
                        let resolvedTag = tag
                        if (!(tag.allowed_target_types || []).includes('kb_doc')) {
                            resolvedTag = await updateTag(tag.id, {
                                allowed_target_types: Array.from(new Set([...(tag.allowed_target_types || []), 'kb_doc'])),
                            })
                        }
                        tagIds.push(resolvedTag.id)
                        createdTagsMap[name] = resolvedTag.id
                    } else {
                        const created = await createTag({ name, kb_id: kbId, allowed_target_types: ['kb_doc'] })
                        tagIds.push(created.id)
                        createdTagsMap[name] = created.id
                    }
                }
            }

            // 对每个选中的文件：获取现有标签 -> 合并新标签 -> 更新
            const updatedTagsMap: Record<string, string[]> = {}
            for (const kbDocId of selectedFileIds) {
                const { tags: current } = await getKbDocTags(kbDocId)
                const currentIds = new Set(current.map((t) => t.id))
                const merged = [...currentIds]
                tagIds.forEach((id) => {
                    if (!currentIds.has(id)) {
                        merged.push(id)
                        currentIds.add(id)
                    }
                })

                // 只更新标签
                await updateDocumentTags(kbDocId, merged)
                updatedTagsMap[kbDocId] = merged
            }

            // 更新 editingTags，将临时标签名替换为真实的标签ID
            const updatedEditingTags = editingTags.map(entry => {
                if (!isTagId(entry) && createdTagsMap[entry.trim()]) {
                    return createdTagsMap[entry.trim()]
                }
                return entry
            })
            setEditingTags(updatedEditingTags)

            toast.success(`已为 ${selectedFileIds.size} 个文件添加标签`)
            setShowBatchTagDialog(false)

            // 刷新文档列表和标签缓存
            refetchDocuments()
            await queryClient.invalidateQueries({ queryKey: ['tags', 'list', kbId] })
            await queryClient.invalidateQueries({ queryKey: ['tags', 'available', kbId] })

            // 强制刷新文档查询缓存，确保标签更新后界面同步
            await queryClient.invalidateQueries({
                queryKey: ['kb-documents', kbId],
                exact: false  // 匹配所有以此开头的查询键
            })
        } catch (err: any) {
            toast.error(err?.response?.data?.detail ?? '批量添加标签失败')
        } finally {
            setIsSavingBatchTags(false)  // 保存完成，恢复状态
        }
    }

    const handleBatchSaveMetadata = async () => {
        setIsSavingBatchMetadata(true)  // 开始保存，设置加载状态

        try {
            const metadataRecord: Record<string, string> = {}
            for (const { key, value, readonly } of editingMetadata) {
                const normalizedKey = key.trim()
                if (!normalizedKey || readonly || RESERVED_METADATA_KEYS.has(normalizedKey)) {
                    continue
                }
                metadataRecord[normalizedKey] = value
            }

            // 如果没有设置任何元数据，直接返回
            if (Object.keys(metadataRecord).length === 0) return

            for (const kbDocId of selectedFileIds) {
                // 批量操作：合并模式（保留现有元数据，添加新的）
                await updateDocumentMetadata(kbDocId, metadataRecord, true)  // merge_metadata = true
            }

            toast.success(`已为 ${selectedFileIds.size} 个文件设置元数据`)
            setShowBatchMetadataDialog(false)

            // 刷新文档列表，确保元数据更新后界面同步
            refetchDocuments()

            // 强制刷新文档查询缓存
            await queryClient.invalidateQueries({
                queryKey: ['kb-documents', kbId],
                exact: false  // 匹配所有以此开头的查询键
            })
        } catch (err: any) {
            toast.error(err?.response?.data?.detail ?? '批量设置元数据失败')
        } finally {
            setIsSavingBatchMetadata(false)  // 保存完成，恢复状态
        }
    }

    // ==================== 分页操作 ====================
    const handlePageChange = (page: number) => {
        setCurrentPage(page)
    }

    const handlePageSizeChange = (newPageSize: number) => {
        setPageSize(newPageSize)
        setCurrentPage(1)
    }

    // 忽略未使用参数的警告
    void kbId

    // 面包屑导航点击处理
    const handleBreadcrumbClick = (folderId: string | null) => {
        onFolderChange?.(folderId)
    }

    // 是否显示文件夹列
    const shouldShowFolderColumn =
        includeSubfolders || // 开启了递归查看
        !selectedFolderId || // 在根目录
        !!searchQuery || // 使用了搜索
        selectedTagIds.size > 0 || // 使用了标签过滤
        statusFilter !== 'all' // 使用了状态过滤


    // ==================== 渲染 ====================
    
    // 渲染主视图内容
    const renderMainContent = () => {
        if (viewMode === 'chunks' && chunkPreviewFile) {
            return (
                <ChunkPreview
                    fileName={chunkPreviewFile.name}
                    kbDocId={chunkPreviewFile.id}
                    kbType={kbType}
                    kbDoc={chunkPreviewFile}  // 传递完整的 kbDoc 对象
                    onBack={() => {
                        clearChunkPreviewCache(chunkPreviewFile.id)
                        setViewMode('files')
                        setChunkPreviewFile(null)
                        // 恢复进入切片预览前的文件树状态
                        if (folderTreeStateBeforeChunks.current !== null && onSetFolderTreeCollapsed) {
                            onSetFolderTreeCollapsed(folderTreeStateBeforeChunks.current)
                            folderTreeStateBeforeChunks.current = null
                        }
                    }}
                    onReparse={() => handleParse(chunkPreviewFile)}
                    isFolderTreeCollapsed={isFolderTreeCollapsed}
                    onToggleFolderTree={onToggleFolderTree}
                />
            )
        }

        return (
            <div className='flex flex-col flex-1 h-full overflow-hidden'>
                {/* 文件列表 Header */}
            <div className='bg-card border-b px-6 py-4 space-y-3'>
                {/* 第一行：面包屑导航和路径设置 - 始终显示 */}
                <div className='flex items-center justify-between gap-4 pb-1'>
                    <div className='flex items-center gap-2 overflow-hidden px-1'>
                        {isLoadingFolderPath ? (
                            // 加载中：显示骨架屏
                            <nav className='flex items-center gap-1.5 text-sm' aria-label='加载中'>
                                <div className='flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-accent/50 animate-pulse'>
                                    <div className='h-4 w-4 bg-muted-foreground/20 rounded' />
                                    <div className='h-4 w-20 bg-muted-foreground/20 rounded' />
                                </div>
                            </nav>
                        ) : selectedFolderId && folderPath.length > 0 ? (
                            // 有文件夹路径：显示面包屑
                            <FolderBreadcrumb folderPath={folderPath} onNavigate={handleBreadcrumbClick} />
                        ) : (
                            // 根目录：显示根目录按钮
                            <nav className='flex items-center gap-1.5 text-sm' aria-label='文件夹路径'>
                                <button
                                    onClick={() => handleBreadcrumbClick(null)}
                                    className='flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-accent text-foreground font-semibold cursor-default shadow-sm'
                                    disabled
                                    aria-current='page'
                                >
                                    <FolderIcon className='h-4 w-4 text-blue-600 dark:text-blue-400' />
                                    <span className='font-medium'>根目录</span>
                                </button>
                            </nav>
                        )}
                    </div>

                    {/* 递归查看开关 */}
                    <div className='flex items-center gap-2.5 shrink-0 bg-blue-50/50 px-3 py-1.5 rounded-full border border-blue-100/50 shadow-sm'>
                        <Switch
                            id='include-subfolders'
                            checked={includeSubfolders}
                            onCheckedChange={handleIncludeSubfoldersChange}
                        />
                        <Label
                            htmlFor='include-subfolders'
                            className='cursor-pointer text-xs font-semibold text-slate-700 select-none whitespace-nowrap'
                        >
                            包含子文件夹
                        </Label>
                    </div>
                </div>

                {/* 第二行：面板控制和主要操作 */}
                <div className='flex justify-between items-center'>
                    <div className='flex items-center gap-2'>
                        <h1 className='text-xl font-bold whitespace-nowrap'>文件列表</h1>
                        <Badge variant='outline' className='ml-1 text-muted-foreground border-none font-normal bg-slate-100'>
                            {totalFiles}
                        </Badge>
                    </div>

                    <div className='flex items-center gap-3'>
                        {selectedFileIds.size > 0 && (
                            <Badge variant='secondary' className='ml-2'>
                                已选择: {selectedFileIds.size}
                            </Badge>
                        )}
                        {(searchQuery || statusFilter !== 'all' || selectedTagIds.size > 0) && (
                            <Button
                                variant='ghost'
                                size='sm'
                                className='h-7 text-xs'
                                onClick={() => {
                                    setSearchQuery('')
                                    setSearchInput('')
                                    setStatusFilter('all')
                                    setSelectedTagIds(new Set())
                                    setTempSelectedTagIds(new Set())
                                }}
                            >
                                清除过滤
                            </Button>
                        )}
                        {/* 显示已选择的标签 */}
                        {selectedTagIds.size > 0 && (
                            <div className='flex items-center gap-1 ml-2'>
                                {Array.from(selectedTagIds).map((tagId) => {
                                    const tag = allTagDefinitions.find((t) => t.id === tagId)
                                    if (!tag) return null
                                    return (
                                        <Badge
                                            key={tagId}
                                            variant='secondary'
                                            className='gap-1 pr-1 cursor-pointer hover:bg-secondary/80'
                                            onClick={() => handleTagToggle(tagId)}
                                        >
                                            {tag.name}
                                            <X className='h-3 w-3' />
                                        </Badge>
                                    )
                                })}
                            </div>
                        )}
                    </div>
                    <div className='flex items-center gap-3'>
                        {/* 搜索框 */}
                        <div className='flex items-center gap-2'>
                            <div className='relative w-64'>
                                <Search className='absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground' />
                                <Input
                                    placeholder='搜索文件...'
                                    className='pl-9 h-9'
                                    value={searchInput}
                                    onChange={(e) => setSearchInput(e.target.value)}
                                    onKeyDown={handleSearchKeyDown}
                                />
                            </div>
                            <Button
                                size='sm'
                                className='h-9 bg-blue-600 hover:bg-blue-700 text-white'
                                onClick={handleSearch}
                            >
                                搜索
                            </Button>
                        </div>

                        {/* 状态过滤 */}
                        <Select value={statusFilter} onValueChange={setStatusFilter}>
                            <SelectTrigger className='w-32 h-9'>
                                <SelectValue placeholder='状态' />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value='all'>全部状态</SelectItem>
                                <SelectItem value='completed'>已完成</SelectItem>
                                <SelectItem value='processing'>处理中</SelectItem>
                                <SelectItem value='pending'>待处理</SelectItem>
                                <SelectItem value='failed'>失败</SelectItem>
                            </SelectContent>
                        </Select>

                        {/* 标签过滤（多选） */}
                        <Popover open={isTagPopoverOpen} onOpenChange={setIsTagPopoverOpen}>
                            <PopoverTrigger asChild>
                                <Button
                                    variant='outline'
                                    className='h-9 gap-2 min-w-32'
                                    onClick={() => {
                                        setTempSelectedTagIds(new Set(selectedTagIds))
                                        setIsTagPopoverOpen(true)
                                    }}
                                >
                                    <Filter className='h-4 w-4' />
                                    标签
                                    {selectedTagIds.size > 0 && (
                                        <Badge variant='secondary' className='ml-1 h-5 px-1.5 text-xs'>
                                            {selectedTagIds.size}
                                        </Badge>
                                    )}
                                </Button>
                            </PopoverTrigger>
                            <PopoverContent className='w-80 p-0' align='start'>
                                {/* 顶部栏 */}
                                <div className='flex items-center justify-between px-3 py-2 border-b'>
                                    <span className='text-sm font-medium'>选择标签</span>
                                    {tempSelectedTagIds.size > 0 && (
                                        <Button
                                            variant='ghost'
                                            size='sm'
                                            className='h-6 px-2 text-xs'
                                            onClick={handleClearTags}
                                        >
                                            清除
                                        </Button>
                                    )}
                                </div>

                                {/* 标签搜索框 */}
                                <div className='px-3 py-2 border-b'>
                                    <div className='relative'>
                                        <Search className='absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground' />
                                        <Input
                                            placeholder='搜索标签...'
                                            className='h-8 pl-8 text-sm'
                                            value={tagSearchQuery}
                                            onChange={(e) => setTagSearchQuery(e.target.value)}
                                        />
                                    </div>
                                </div>

                                {/* 标签列表 */}
                                <ScrollArea className='max-h-64'>
                                    <div className='p-2 space-y-1'>
                                        {filteredTagDefinitions.length === 0 ? (
                                            <div className='px-2 py-4 text-center text-sm text-muted-foreground'>
                                                {tagSearchQuery ? '未找到匹配的标签' : '暂无标签'}
                                            </div>
                                        ) : (
                                            filteredTagDefinitions.map((tag) => (
                                                <div
                                                    key={tag.id}
                                                    className='flex items-center gap-2 px-2 py-2 rounded-md hover:bg-accent cursor-pointer'
                                                    onClick={() => handleTagToggle(tag.id)}
                                                >
                                                    <Checkbox
                                                        checked={tempSelectedTagIds.has(tag.id)}
                                                        onCheckedChange={() => handleTagToggle(tag.id)}
                                                        onClick={(e) => e.stopPropagation()}
                                                    />
                                                    <div className='flex-1 min-w-0'>
                                                        <div className='text-sm font-medium truncate'>{tag.name}</div>
                                                        {tag.description && (
                                                            <div className='text-xs text-muted-foreground truncate'>
                                                                {tag.description}
                                                            </div>
                                                        )}
                                                    </div>
                                                    {tempSelectedTagIds.has(tag.id) && (
                                                        <Check className='h-4 w-4 text-primary' />
                                                    )}
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </ScrollArea>

                                {/* 底部按钮 */}
                                <div className='flex items-center justify-end gap-2 px-3 py-2 border-t bg-muted/30'>
                                    <Button variant='ghost' size='sm' className='h-8' onClick={handleCancelTags}>
                                        取消
                                    </Button>
                                    <Button size='sm' className='h-8' onClick={handleConfirmTags}>
                                        确定 {tempSelectedTagIds.size > 0 && `(${tempSelectedTagIds.size})`}
                                    </Button>
                                </div>
                            </PopoverContent>
                        </Popover>

                        {/* 列显示设置 */}
                        <Popover>
                            <PopoverTrigger asChild>
                                <Button
                                    variant='outline'
                                    size='icon'
                                    className='h-9 w-9'
                                    title='列显示设置'
                                >
                                    <img src='/icons/icon_show_column_setting.svg' alt='' className='h-4 w-4' />
                                </Button>
                            </PopoverTrigger>
                            <PopoverContent className='w-56' align='end'>
                                <div className='space-y-3'>
                                    <div className='font-semibold text-sm'>显示列</div>
                                    <div className='space-y-2'>
                                        {columnConfig.map((column) => (
                                            <div key={column.id} className='flex items-center space-x-2'>
                                                <Checkbox
                                                    id={`column-${column.id}`}
                                                    checked={column.visible}
                                                    onCheckedChange={() => {
                                                        const newConfig = columnConfig.map(col =>
                                                            col.id === column.id ? { ...col, visible: !col.visible } : col
                                                        )
                                                        setColumnConfig(newConfig)
                                                    }}
                                                    disabled={column.id === 'name'} // 名称列始终显示
                                                />
                                                <Label
                                                    htmlFor={`column-${column.id}`}
                                                    className='text-sm font-normal cursor-pointer flex-1'
                                                >
                                                    {column.label}
                                                </Label>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </PopoverContent>
                        </Popover>

                        <Button
                            className='gap-2 h-9 bg-blue-600 hover:bg-blue-700 text-white'
                            onClick={() => setShowUploadDialog(true)}
                            disabled={isWebKnowledgeBase}
                            title={isWebKnowledgeBase ? '网页同步类型知识库不支持上传文件' : undefined}
                        >
                            <Upload className='h-4 w-4' /> 上传文件
                        </Button>
                    </div>
                </div>

                {/* 批量操作栏 */}
                <BatchActionsBar
                    selectedCount={selectedFileIds.size}
                    onBatchParse={handleBatchParse}
                    onBatchConfig={handleBatchConfig}
                    onBatchTag={() => {
                        setEditingTags([])
                        setNewTag('')
                        setShowBatchTagDialog(true)
                    }}
                    onBatchMetadata={() => {
                        setEditingMetadata([])
                        setNewMetadataKey('')
                        setNewMetadataValue('')
                        setShowBatchMetadataDialog(true)
                    }}
                    onBatchEnable={() => handleBatchToggleEnabled(true)}
                    onBatchDisable={() => handleBatchToggleEnabled(false)}
                    onBatchDelete={handleBatchDelete}
                    onCancelSelection={() => setSelectedFileIds(new Set())}
                />
            </div>

            {/* 文件列表 */}
            <div className='flex-1 overflow-auto p-6'>
                {isLoadingDocuments ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-center space-y-2">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                            <p className="text-sm text-muted-foreground">加载中...</p>
                        </div>
                    </div>
                ) : (
                    <>
                        <FileTable
                            files={currentPageFiles}
                            selectedFileIds={selectedFileIds}
                            tagDefinitions={allTagDefinitions}
                            sortField={sortField}
                            sortOrder={sortOrder}
                            shouldShowFolderColumn={shouldShowFolderColumn}
                            columnConfig={columnConfig}
                            parsingFileIds={parsingFileIds}
                            downloadProgressMap={downloadProgressMap}
                            onColumnConfigChange={setColumnConfig}
                            onSort={handleSort}
                            onSelectAll={handleSelectAll}
                            onSelectFile={handleSelectFile}
                            onToggleEnabled={handleToggleEnabled}
                            onViewDetail={handleViewDetail}
                            onEditMetadata={handleEditMetadata}
                            onEditTagDetail={handleEditTagDetail}
                            onViewChunks={(file) => {
                                // 保存当前文件树状态，然后自动折叠
                                folderTreeStateBeforeChunks.current = isFolderTreeCollapsed ?? false
                                if (!isFolderTreeCollapsed && onSetFolderTreeCollapsed) {
                                    onSetFolderTreeCollapsed(true)
                                }
                                setChunkPreviewFile(file)
                                setViewMode('chunks')
                            }}
                            onParse={handleParse}
                            onChunkConfig={handleChunkConfig}
                            onRename={handleRename}
                            onDownload={handleDownload}
                            onDelete={handleDelete}
                            onCancelParse={handleCancelParse}
                            onFolderClick={handleBreadcrumbClick}
                            onRefresh={refetchDocuments}  // 🔧 新增：传递刷新回调
                            kbType={kbType}
                        />

                        {/* 分页 */}
                        <Pagination
                            currentPage={currentPage}
                            totalPages={totalPages}
                            pageSize={pageSize}
                            totalItems={totalFiles}
                            startIndex={startIndex}
                            endIndex={endIndex}
                            onPageChange={handlePageChange}
                            onPageSizeChange={handlePageSizeChange}
                        />
                    </>
                )}
            </div>
        </div>
        )
    }

    return (
        <>
            {/* 主内容区域 */}
            {renderMainContent()}

            {/* 文件详情侧边栏 - 全局渲染 */}
            <FileDetailSheet
                open={showDetailSheet}
                onOpenChange={setShowDetailSheet}
                file={selectedFile}
                tagDefinitions={allTagDefinitions}
                kbType={kbType}
            />

            {/* 对话框 - 全局渲染，确保在切片预览模式下也能显示 */}
            <RenameDialog
                open={showRenameDialog}
                onOpenChange={setShowRenameDialog}
                fileName={selectedFile?.name || ''}
                onConfirm={handleRenameConfirm}
            />

            <ParseDialog
                open={showParseDialog}
                onOpenChange={setShowParseDialog}
                file={fileToProcess}
                onConfirm={handleParseConfirm}
            />

            <ChunkConfigDialog
                open={showChunkConfigDialog}
                onOpenChange={setShowChunkConfigDialog}
                fileName={fileToConfig?.name}
                config={chunkConfig}
                onConfigChange={setChunkConfig}
                onSave={handleChunkConfigSave}
            />

            <BatchParseDialog
                open={showBatchParseDialog}
                onOpenChange={(open) => {
                    setShowBatchParseDialog(open)
                    if (!open) {
                        setForceBatchWebSyncRebuild(false)
                    }
                }}
                selectedCount={selectedFileIds.size}
                isWebKnowledgeBase={isWebKnowledgeBase}
                forceWebSyncRebuild={forceBatchWebSyncRebuild}
                onForceWebSyncRebuildChange={setForceBatchWebSyncRebuild}
                onConfirm={handleBatchParseConfirm}
            />

            <ChunkConfigDialog
                open={showBatchConfigDialog}
                onOpenChange={setShowBatchConfigDialog}
                config={chunkConfig}
                onConfigChange={setChunkConfig}
                onSave={handleBatchConfigSave}
            />

            <TagDetailSheet
                open={showTagDetailDialog}
                onOpenChange={setShowTagDetailDialog}
                editingTag={editingTagDetail}
                tagForm={tagDetailForm}
                defaultTargetType='kb_doc'
                onTagFormChange={setTagDetailForm}
                newSynonym={newSynonym}
                onNewSynonymChange={setNewSynonym}
                onAddSynonym={handleAddSynonym}
                onRemoveSynonym={handleRemoveSynonym}
                onSaveTagDefinition={handleSaveTagDetail}
                isLoading={isTagSaving}
            />

            <MetadataDialog
                open={showMetadataDialog}
                onOpenChange={(open) => {
                    if (!open) setResolvedTagsById({})
                    if (!open) {
                        setFileToEditMetadata(null)
                        setDocContextEnabled(false)
                        setDocContextContent('')
                    }
                    setShowMetadataDialog(open)
                }}
                fileName={fileToEditMetadata?.name || ''}
                editingTags={editingTags}
                editingMetadata={editingMetadata}
                tagDefinitions={allTagDefinitions}
                getTagDefinition={getTagDefinition}
                newTag={newTag}
                newMetadataKey={newMetadataKey}
                newMetadataValue={newMetadataValue}
                onNewTagChange={setNewTag}
                onNewMetadataKeyChange={setNewMetadataKey}
                onNewMetadataValueChange={setNewMetadataValue}
                onAddTag={handleAddTag}
                onAddTagById={handleAddTagById}
                onRemoveTag={handleRemoveTag}
                onEditTagDetail={handleEditTagDetail}
                onAddMetadata={handleAddMetadata}
                onUpdateMetadata={handleUpdateMetadata}
                onRemoveMetadata={handleRemoveMetadata}
                docContextEnabled={docContextEnabled}
                docContextContent={docContextContent}
                onDocContextEnabledChange={setDocContextEnabled}
                onDocContextContentChange={setDocContextContent}
                onSave={handleSaveMetadata}
                isLoading={isSavingMetadata}  // 传递保存加载状态
            />

            <BatchTagDialog
                open={showBatchTagDialog}
                onOpenChange={(open: boolean) => {
                    if (!open) setResolvedTagsById({})
                    setShowBatchTagDialog(open)
                }}
                selectedCount={selectedFileIds.size}
                editingTags={editingTags}
                tagDefinitions={allTagDefinitions}
                getTagDefinition={getTagDefinition}
                newTag={newTag}
                onNewTagChange={setNewTag}
                onAddTag={handleAddTag}
                onAddTagById={handleAddTagById}
                onRemoveTag={handleRemoveTag}
                onEditTagDetail={handleEditTagDetail}
                docContextEnabled={docContextEnabled}
                docContextContent={docContextContent}
                onDocContextEnabledChange={setDocContextEnabled}
                onDocContextContentChange={setDocContextContent}
                onSave={handleBatchSaveTags}
                isLoading={isSavingBatchTags}  // 传递批量保存标签加载状态
            />

            <BatchMetadataDialog
                open={showBatchMetadataDialog}
                onOpenChange={setShowBatchMetadataDialog}
                selectedCount={selectedFileIds.size}
                editingMetadata={editingMetadata}
                newMetadataKey={newMetadataKey}
                newMetadataValue={newMetadataValue}
                onNewMetadataKeyChange={setNewMetadataKey}
                onNewMetadataValueChange={setNewMetadataValue}
                onAddMetadata={handleAddMetadata}
                onUpdateMetadata={handleUpdateMetadata}
                onRemoveMetadata={handleRemoveMetadata}
                docContextEnabled={docContextEnabled}
                docContextContent={docContextContent}
                onDocContextEnabledChange={setDocContextEnabled}
                onDocContextContentChange={setDocContextContent}
                onSave={handleBatchSaveMetadata}
                isLoading={isSavingBatchMetadata}  // 传递批量保存元数据加载状态
            />

            {/* 文件上传对话框 */}
            <FileUploadDialog
                open={showUploadDialog}
                onOpenChange={setShowUploadDialog}
                kbId={kbId}
                kbType={kbType}
                currentFolderName={
                    selectedFolderId && folderPath.length > 0
                        ? folderPath.map(f => f.name).join(' > ')
                        : '/'
                }
                currentFolderId={selectedFolderId}
                isLoadingFolder={isLoadingFolderPath}
                onUploadSuccess={refetchDocuments}
                onTableSchemaInitialized={onTableSchemaInitialized}
            />

            {/* 取消解析确认对话框 */}
            <ConfirmDialog
                open={showCancelParseConfirm}
                onOpenChange={(open) => {
                    setShowCancelParseConfirm(open)
                    if (!open) {
                        setFileToCancelParse(null)
                    }
                }}
                title="取消解析"
                desc={
                    <div className="space-y-3">
                        <p className="text-base">确定要取消以下文档的解析任务吗？</p>
                        {fileToCancelParse && (
                            <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg">
                                <p className="font-semibold text-blue-900 break-all">{fileToCancelParse.name}</p>
                                {(fileToCancelParse.progress ?? 0) > 0 && (
                                    <p className="text-sm text-blue-700 mt-1">
                                        当前进度: {fileToCancelParse.progress}%
                                    </p>
                                )}
                            </div>
                        )}
                        <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg">
                            <p className="text-sm text-amber-900 font-medium">
                                ⚠️ 取消后已解析的进度将丢失，如需重新解析需要从头开始。
                            </p>
                        </div>
                    </div>
                }
                confirmText="确认取消"
                cancelBtnText="继续解析"
                destructive
                handleConfirm={handleCancelParseConfirm}
            />

            {/* 单个删除确认对话框 */}
            <ConfirmDialog
                open={showDeleteConfirm}
                onOpenChange={(open) => {
                    setShowDeleteConfirm(open)
                    // 对话框关闭时清空数据，避免闪现
                    if (!open) {
                        setFileToDelete(null)
                    }
                }}
                title="移除文档"
                desc={
                    <div className="space-y-3">
                        <p className="text-base">确定要从知识库中移除以下文档吗？</p>
                        {fileToDelete && (
                            <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg">
                                <p className="font-semibold text-blue-900 break-all">{fileToDelete.name}</p>
                            </div>
                        )}
                        <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg">
                            <p className="text-sm text-amber-900 font-medium">
                                ⚠️ 注意：这只会移除知识库关联，不会删除物理文件。
                            </p>
                        </div>
                    </div>
                }
                confirmText="确认移除"
                cancelBtnText="取消"
                destructive
                handleConfirm={handleDeleteConfirm}
            />

            {/* 批量删除确认对话框 */}
            <ConfirmDialog
                open={showBatchDeleteConfirm}
                onOpenChange={(open) => {
                    setShowBatchDeleteConfirm(open)
                    // 对话框关闭时清空选择，避免闪现
                    if (!open) {
                        setSelectedFileIds(new Set())
                    }
                }}
                title="批量移除文档"
                desc={
                    <div className="space-y-3">
                        <p className="text-base">
                            确定要从知识库中移除 <span className="font-bold text-destructive">{selectedFileIds.size}</span> 个文档吗？
                        </p>
                        {(() => {
                            const selectedFiles = getSelectedFiles()
                            const displayFiles = selectedFiles.slice(0, 5)
                            const remainingCount = selectedFiles.length - 5

                            return (
                                <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg space-y-1.5 max-h-48 overflow-y-auto">
                                    {displayFiles.map(file => (
                                        <div key={file.id} className="flex items-start gap-2">
                                            <span className="text-blue-600 mt-0.5">•</span>
                                            <span className="font-medium text-blue-900 break-all flex-1">{file.name}</span>
                                        </div>
                                    ))}
                                    {remainingCount > 0 && (
                                        <div className="flex items-center gap-2 pt-1 border-t border-blue-200">
                                            <span className="text-blue-700 text-sm font-medium">
                                                ... 还有 {remainingCount} 个文件
                                            </span>
                                        </div>
                                    )}
                                </div>
                            )
                        })()}
                        <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg">
                            <p className="text-sm text-amber-900 font-medium">
                                ⚠️ 注意：这只会移除知识库关联，不会删除物理文件。
                            </p>
                        </div>
                    </div>
                }
                confirmText={`确认移除 ${selectedFileIds.size} 个文档`}
                cancelBtnText="取消"
                destructive
                handleConfirm={handleBatchDeleteConfirm}
            />
        </>
    )
}
