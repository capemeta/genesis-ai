import { useState, useRef, useEffect } from 'react'
import {
    Check,
    Loader2,
    AlertCircle,
    Clock,
    MoreVertical,
    Eye,
    Edit2,
    Download,
    Trash2,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    Folder,
    X,
    ChevronsUp,
    ChevronsDown,
    Copy,
} from 'lucide-react'
import { toast } from 'sonner'
import { withAppAssetPath } from '@/lib/app-base'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
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
import { cn } from '@/lib/utils'
import {
    CURRENT_ROOT_PATH_DISPLAY,
    PATH_SEPARATOR,
    PATH_TRUNCATE_CONFIG,
    PATH_MAX_WIDTH,
} from './folder-path-config'
import { getFileTypeIconUrl, NO_FILE_ICON_URL } from '../../shared/file-type-icon'
import type { FileItem, TagDefinition } from '../types'

// 列配置类型
export interface ColumnConfig {
    id: string
    label: string
    visible: boolean
    sortable: boolean
}

// 默认列配置
export const DEFAULT_COLUMNS: ColumnConfig[] = [
    { id: 'name', label: '名称', visible: true, sortable: true },
    { id: 'type', label: '文件类型', visible: false, sortable: true }, // 默认隐藏
    { id: 'size', label: '文件大小', visible: false, sortable: true }, // 默认隐藏
    { id: 'status', label: '状态', visible: true, sortable: true },
    { id: 'enabled', label: '启用', visible: true, sortable: true },
    { id: 'folder', label: '文件夹路径', visible: true, sortable: true }, // 默认隐藏
    { id: 'tags', label: '标签', visible: true, sortable: false },
    { id: 'uploadTime', label: '上传时间', visible: false, sortable: true }, // 默认隐藏
    { id: 'chunks', label: '切片数', visible: true, sortable: true }, // 默认隐藏
]

// 文件夹路径显示组件
interface FolderPathCellProps {
    file: FileItem
    onFolderClick: (folderId: string | null) => void
}

function FolderPathCell({ file, onFolderClick }: FolderPathCellProps) {
    // 根目录显示
    if (!file.folderPath) {
        const { icon: Icon, text, className } = CURRENT_ROOT_PATH_DISPLAY
        return (
            <div className={cn('flex items-center gap-1.5 text-sm', className)}>
                {Icon && <Icon className='h-3.5 w-3.5' />}
                <span>{text}</span>
            </div>
        )
    }

    // 如果有 path_array，使用它来渲染可点击的面包屑
    if (file.folderPathArray && file.folderPathArray.length > 0) {
        const shouldTruncate = file.folderPathArray.length > PATH_TRUNCATE_CONFIG.maxLevels
        const displayItems = shouldTruncate
            ? file.folderPathArray.slice(-PATH_TRUNCATE_CONFIG.showLastLevels)
            : file.folderPathArray

        return (
            <div className='flex items-center gap-1 text-sm flex-wrap'>
                <Folder className='h-3.5 w-3.5 text-blue-600 dark:text-blue-400 shrink-0' />
                {shouldTruncate && (
                    <>
                        <span className='text-muted-foreground'>{PATH_TRUNCATE_CONFIG.truncateSymbol}</span>
                        <span className='text-muted-foreground'>{PATH_SEPARATOR}</span>
                    </>
                )}
                {displayItems.map((item, index) => (
                    <div key={item.id} className='flex items-center gap-1'>
                        {index > 0 && <span className='text-muted-foreground'>{PATH_SEPARATOR}</span>}
                        <button
                            className='hover:text-primary hover:underline transition-colors'
                            onClick={(e) => {
                                e.stopPropagation()
                                onFolderClick(item.id)
                            }}
                            title={`跳转到 ${item.name}`}
                        >
                            {item.name}
                        </button>
                    </div>
                ))}
            </div>
        )
    }

    // 后备方案：使用字符串路径（不可点击每一级）
    const pathParts = file.folderPath.split('/').filter(Boolean)
    const shouldTruncate = pathParts.length > PATH_TRUNCATE_CONFIG.maxLevels

    // 智能截断
    const displayPath = shouldTruncate
        ? `${PATH_TRUNCATE_CONFIG.truncateSymbol}${PATH_SEPARATOR}${pathParts.slice(-PATH_TRUNCATE_CONFIG.showLastLevels).join(PATH_SEPARATOR)}`
        : pathParts.join(PATH_SEPARATOR)

    return (
        <TooltipProvider>
            <Tooltip>
                <TooltipTrigger asChild>
                    <button
                        className='flex items-center gap-1.5 text-sm hover:text-primary transition-colors text-left group'
                        onClick={(e) => {
                            e.stopPropagation()
                            onFolderClick(file.folderId || null)
                        }}
                    >
                        <Folder className='h-3.5 w-3.5 text-blue-600 dark:text-blue-400 shrink-0' />
                        <span className='truncate group-hover:underline' style={{ maxWidth: `${PATH_MAX_WIDTH}px` }}>
                            {displayPath}
                        </span>
                    </button>
                </TooltipTrigger>
                <TooltipContent side='top' className='max-w-sm'>
                    <div className='flex items-center gap-1.5'>
                        <Folder className='h-3.5 w-3.5 text-blue-600 dark:text-blue-400' />
                        <span className='text-xs'>{pathParts.join(PATH_SEPARATOR)}</span>
                    </div>
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    )
}

interface FileTableProps {
    files: FileItem[]
    selectedFileIds: Set<string>
    tagDefinitions: TagDefinition[]
    sortField: 'name' | 'uploadTime' | 'chunks' | 'size' | 'type' | 'status' | 'enabled' | 'folder' | null
    sortOrder: 'asc' | 'desc' | null
    shouldShowFolderColumn: boolean
    columnConfig?: ColumnConfig[]
    parsingFileIds: Set<string>
    downloadProgressMap: Record<string, number | null>
    onSort: (field: 'name' | 'uploadTime' | 'chunks' | 'size' | 'type' | 'status' | 'enabled' | 'folder') => void
    onSelectAll: (checked: boolean) => void
    onSelectFile: (fileId: string, checked: boolean) => void
    onToggleEnabled: (fileId: string) => void
    onViewDetail: (file: FileItem) => void
    onEditMetadata: (file: FileItem) => void
    onEditTagDetail: (tagId: string) => void
    onViewChunks: (file: FileItem) => void
    onParse: (file: FileItem, options?: { forceRebuildIndex?: boolean }) => void
    onChunkConfig: (file: FileItem) => void
    onRename: (file: FileItem) => void
    onDownload: (file: FileItem) => void
    onDelete: (file: FileItem) => void
    onCancelParse: (file: FileItem) => void
    onFolderClick: (folderId: string | null) => void
    onColumnConfigChange?: (config: ColumnConfig[]) => void
    onRefresh?: () => void  // 🔧 新增：刷新数据的回调
    kbType?: string
}

export function FileTable({
    files,
    selectedFileIds,
    tagDefinitions,
    sortField,
    sortOrder,
    shouldShowFolderColumn,
    columnConfig = DEFAULT_COLUMNS,
    parsingFileIds,
    downloadProgressMap,
    onSort,
    onSelectAll,
    onSelectFile,
    onToggleEnabled,
    onViewDetail,
    onEditMetadata,
    onEditTagDetail,
    onViewChunks,
    onParse,
    onChunkConfig: _onChunkConfig,
    onRename,
    onDownload,
    onDelete,
    onCancelParse,
    onFolderClick,
    onRefresh,  // 🔧 新增：接收刷新回调
    kbType,
}: FileTableProps) {
    const isWebKnowledgeBase = kbType === 'web'
    const isAllSelected = files.length > 0 && files.every((file) => selectedFileIds.has(file.id))
    const isSomeSelected = files.some((file) => selectedFileIds.has(file.id)) && !isAllSelected

    // 状态日志对话框状态
    const [logDialogOpen, setLogDialogOpen] = useState(false)
    const [selectedLogFile, setSelectedLogFile] = useState<FileItem | null>(null)
    const [selectedAttemptIndex, setSelectedAttemptIndex] = useState<number>(-1) // 🔧 修复：-1 表示默认选中最新的尝试

    // 重新解析/同步确认弹窗状态
    const [reparseConfirmFile, setReparseConfirmFile] = useState<FileItem | null>(null)
    const [forceWebSyncRebuild, setForceWebSyncRebuild] = useState(false)
    
    // 日志容器引用
    const logContainerRef = useRef<HTMLDivElement>(null)

    // 🔧 实时刷新功能：处理中或取消中时自动轮询
    const isFileInActiveState = selectedLogFile && ['Processing', 'Cancelling', 'Queued'].includes(selectedLogFile.status)
    useEffect(() => {
        // 只有在对话框打开且文档处于活跃状态时才启动定时刷新
        if (!logDialogOpen || !isFileInActiveState) {
            return
        }

        // 每 2 秒刷新一次数据
        const intervalId = setInterval(() => {
            if (onRefresh) {
                onRefresh()
            }
        }, 2000)

        return () => clearInterval(intervalId)
    }, [logDialogOpen, isFileInActiveState, onRefresh])

    // 🔧 新增：当文件数据更新时，同步更新 selectedLogFile
    useEffect(() => {
        if (selectedLogFile && logDialogOpen) {
            const updatedFile = files.find(f => f.id === selectedLogFile.id)
            if (updatedFile) {
                setSelectedLogFile(updatedFile)
            }
        }
    }, [files, selectedLogFile, logDialogOpen])

    // 滚动到顶部
    const scrollToTop = () => {
        if (logContainerRef.current) {
            logContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' })
        }
    }

    // 滚动到底部
    const scrollToBottom = () => {
        if (logContainerRef.current) {
            logContainerRef.current.scrollTo({ top: logContainerRef.current.scrollHeight, behavior: 'smooth' })
        }
    }

    const getTagDefinition = (tagId: string) => {
        return tagDefinitions.find((t) => t.id === tagId)
    }

    const isColumnVisible = (columnId: string) => {
        const column = columnConfig.find(col => col.id === columnId)
        return column?.visible ?? true
    }

    // 计算可见列数（用于 colspan）
    const visibleColumnsCount = columnConfig.filter(col => col.visible).length + 2 // +2 for checkbox and actions

    // 排序图标组件
    const SortIcon = ({
        field,
    }: {
        field: 'name' | 'uploadTime' | 'chunks' | 'size' | 'type' | 'status' | 'enabled' | 'folder'
    }) => {
        if (sortField !== field) {
            return <ArrowUpDown className='h-3.5 w-3.5 text-muted-foreground/50' />
        }
        if (sortOrder === 'asc') {
            return <ArrowUp className='h-3.5 w-3.5 text-primary' />
        }
        if (sortOrder === 'desc') {
            return <ArrowDown className='h-3.5 w-3.5 text-primary' />
        }
        return <ArrowUpDown className='h-3.5 w-3.5 text-muted-foreground/50' />
    }

    // 可排序表头组件
    const SortableHeader = ({
        field,
        children,
        className,
    }: {
        field: 'name' | 'uploadTime' | 'chunks' | 'size' | 'type' | 'status' | 'enabled' | 'folder'
        children: React.ReactNode
        className?: string
    }) => (
        <th
            className={cn(
                'px-6 py-3 cursor-pointer select-none hover:bg-muted/70 transition-colors group',
                className
            )}
            onClick={() => onSort(field)}
        >
            <div className='flex items-center gap-2'>
                {children}
                <SortIcon field={field} />
            </div>
        </th>
    )

    return (
        <div className='bg-card rounded-xl shadow-sm border overflow-hidden'>
            <div className='overflow-x-auto'>
                <table className='w-full text-left text-sm whitespace-nowrap'>
                    <thead className='bg-muted/50 border-b text-muted-foreground font-semibold'>
                        <tr>
                            <th className='px-6 py-3 w-10 sticky left-0 bg-muted/50 z-10'>
                                <Checkbox
                                    checked={isAllSelected}
                                    onCheckedChange={(checked) => onSelectAll(checked === true)}
                                    aria-label='全选当前页'
                                    className={cn(isSomeSelected && 'data-[state=checked]:bg-primary/50')}
                                />
                            </th>
                            {isColumnVisible('name') && <SortableHeader field='name'>名称</SortableHeader>}
                            {isColumnVisible('type') && <SortableHeader field='type'>文件类型</SortableHeader>}
                            {isColumnVisible('size') && <SortableHeader field='size'>文件大小</SortableHeader>}
                            {isColumnVisible('status') && <SortableHeader field='status'>状态</SortableHeader>}
                            {isColumnVisible('enabled') && (
                                <SortableHeader field='enabled' className='text-center'>
                                    启用
                                </SortableHeader>
                            )}
                            {isColumnVisible('folder') && shouldShowFolderColumn && (
                                <SortableHeader field='folder'>文件夹路径</SortableHeader>
                            )}
                            {isColumnVisible('tags') && <th className='px-6 py-3'>标签</th>}
                            {isColumnVisible('uploadTime') && <SortableHeader field='uploadTime'>上传时间</SortableHeader>}
                            {isColumnVisible('chunks') && (
                                <SortableHeader field='chunks' className='text-right'>
                                    切片数
                                </SortableHeader>
                            )}
                            <th className='px-6 py-3 text-center sticky right-0 bg-muted/50 z-10 shadow-[-4px_0_8px_-2px_rgba(0,0,0,0.1)]'>
                                操作
                            </th>
                        </tr>
                    </thead>
                    <tbody className='divide-y'>
                        {files.length === 0 ? (
                            <tr>
                                <td
                                    colSpan={visibleColumnsCount}
                                    className='px-6 py-16 text-center text-muted-foreground'
                                >
                                    <div className='flex flex-col items-center gap-2'>
                                        <img
                                            src={NO_FILE_ICON_URL}
                                            alt=''
                                            className='h-12 w-12 opacity-30 object-contain'
                                        />
                                        <p className='text-sm'>暂无文件</p>
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            files.map((file) => (
                                <tr key={file.id} className='hover:bg-muted/30 transition-colors group'>
                                    <td className='px-6 py-4 sticky left-0 bg-card group-hover:bg-muted/30 z-10'>
                                        <Checkbox
                                            checked={selectedFileIds.has(file.id)}
                                            onCheckedChange={(checked) => onSelectFile(file.id, checked === true)}
                                            aria-label={`选择 ${file.name}`}
                                        />
                                    </td>
                                    {isColumnVisible('name') && (
                                        <td className='px-6 py-4 font-medium'>
                                            <div className='flex items-center gap-2 group/name'>
                                                <img
                                                    src={getFileTypeIconUrl(file.name, undefined, file.type)}
                                                    alt=''
                                                    className='h-6 w-6 shrink-0 object-contain'
                                                />
                                                <span
                                                    title={file.name}
                                                    className='max-w-xs truncate cursor-pointer hover:text-primary transition-colors'
                                                    onClick={() => onViewChunks(file)}
                                                >
                                                    {file.name}
                                                </span>
                                                <TooltipProvider>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button
                                                                variant='ghost'
                                                                size='icon'
                                                                className='h-6 w-6 opacity-0 group-hover/name:opacity-100 transition-opacity'
                                                                onClick={(e) => {
                                                                    e.stopPropagation()
                                                                    navigator.clipboard.writeText(file.name)
                                                                    toast.success('文件名已复制到剪贴板')
                                                                }}
                                                            >
                                                                <Copy className='h-3.5 w-3.5' />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent side='top'>
                                                            <p className='text-xs'>复制文件名</p>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>
                                            </div>
                                        </td>
                                    )}
                                    {isColumnVisible('type') && (
                                        <td className='px-6 py-4 text-muted-foreground'>
                                            {file.type}
                                        </td>
                                    )}
                                    {isColumnVisible('size') && (
                                        <td className='px-6 py-4 text-muted-foreground'>
                                            {file.size}
                                        </td>
                                    )}
                                    {isColumnVisible('status') && (
                                        <td className='px-6 py-4'>
                                            <div className="flex items-center gap-2">
                                                <Badge
                                                    className={cn(
                                                        'gap-1 border-none shadow-none',
                                                        file.status === 'Completed' && 'bg-green-100 text-green-700 hover:bg-green-100',
                                                        file.status === 'Processing' && 'bg-blue-50 text-blue-700 hover:bg-blue-50',
                                                        file.status === 'Queued' && 'bg-yellow-100 text-yellow-700 hover:bg-yellow-100',
                                                        file.status === 'Failed' && 'bg-red-100 text-red-700 hover:bg-red-100',
                                                        // Pending 在 web 类型下为"待同步"，用橙色传递待办感；普通文件下为"等待启动"，保持灰色
                                                        file.status === 'Pending' && (isWebKnowledgeBase ? 'bg-orange-50 text-orange-600 hover:bg-orange-50' : 'bg-slate-100 text-slate-700 hover:bg-slate-100'),
                                                        file.status === 'Cancelled' && 'bg-gray-100 text-gray-700 hover:bg-gray-100',
                                                        file.status === 'Cancelling' && 'bg-orange-100 text-orange-700 hover:bg-orange-100',
                                                        // web 専属中间态：已同步内容，正在建索引
                                                        file.status === 'SyncedChunking' && 'bg-cyan-50 text-cyan-700 hover:bg-cyan-50'
                                                    )}
                                                >
                                                    {file.status === 'Completed' && <Check className='h-3 w-3' />}
                                                    {file.status === 'Processing' && <Loader2 className='h-3 w-3 animate-spin' />}
                                                    {file.status === 'Queued' && <Clock className='h-3 w-3' />}
                                                    {file.status === 'Failed' && <AlertCircle className='h-3 w-3' />}
                                                    {file.status === 'Pending' && <Clock className='h-3 w-3' />}
                                                    {file.status === 'Cancelled' && <X className='h-3 w-3' />}
                                                    {file.status === 'Cancelling' && <Loader2 className='h-3 w-3 animate-spin' />}
                                                    {file.status === 'SyncedChunking' && <Loader2 className='h-3 w-3 animate-spin' />}
                                                    <div className="flex flex-col">
                                                        <span>{
                                                            file.status === 'Completed' ? (isWebKnowledgeBase ? '同步完成' : '已解析') :
                                                            file.status === 'Processing' ? (isWebKnowledgeBase ? '同步中' : `正在解析 ${file.progress}%`) :
                                                            file.status === 'Queued' ? '排队中' :
                                                            file.status === 'Failed' ? (isWebKnowledgeBase ? '同步失败' : '解析失败') :
                                                            file.status === 'Pending' ? (isWebKnowledgeBase ? '待同步' : '等待启动') :
                                                            file.status === 'Cancelled' ? '已取消' :
                                                            file.status === 'Cancelling' ? '取消中' :
                                                            file.status === 'SyncedChunking' ? '已同步，建索引中' :
                                                            '等待启动'
                                                        }</span>
                                                    </div>
                                                </Badge>
                                                {/* 日志图标按钞：web 类型显示同步错误，普通文件显示解析日志 */}
                                                {((file.parsingLogs && file.parsingLogs.length > 0) || file.parseError) && (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 rounded-full hover:bg-muted"
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            setSelectedLogFile(file)
                                                            setLogDialogOpen(true)
                                                        }}
                                                        title={isWebKnowledgeBase ? '查看同步错误' : '查看解析日志'}
                                                    >
                                                        <img 
                                                            src={withAppAssetPath('icons/icon_doc_file_parse_log.svg')} 
                                                            alt="日志" 
                                                            className="h-4 w-4"
                                                        />
                                                    </Button>
                                                )}
                                            </div>
                                        </td>
                                    )}
                                    {isColumnVisible('enabled') && (
                                        <td className='px-6 py-4'>
                                            <div className='flex justify-center'>
                                                <Switch checked={file.enabled} onCheckedChange={() => onToggleEnabled(file.id)} />
                                            </div>
                                        </td>
                                    )}
                                    {/* 文件夹列（条件显示）- 显示完整路径 */}
                                    {isColumnVisible('folder') && shouldShowFolderColumn && (
                                        <td className='px-6 py-4'>
                                            <FolderPathCell file={file} onFolderClick={onFolderClick} />
                                        </td>
                                    )}
                                    {isColumnVisible('tags') && (
                                        <td className='px-6 py-4'>
                                        <div className='flex flex-wrap gap-1'>
                                            {file.tags.slice(0, 2).map((tagId) => {
                                                const tagDef = getTagDefinition(tagId)
                                                return (
                                                    <Badge
                                                        key={tagId}
                                                        variant='secondary'
                                                        className={cn(
                                                            'text-xs cursor-pointer hover:opacity-80 transition-opacity',
                                                            tagDef?.color === 'blue' &&
                                                            'bg-blue-100 text-blue-700 hover:bg-blue-100',
                                                            tagDef?.color === 'green' &&
                                                            'bg-green-100 text-green-700 hover:bg-green-100',
                                                            tagDef?.color === 'purple' &&
                                                            'bg-purple-100 text-purple-700 hover:bg-purple-100',
                                                            tagDef?.color === 'red' &&
                                                            'bg-red-100 text-red-700 hover:bg-red-100',
                                                            tagDef?.color === 'yellow' &&
                                                            'bg-yellow-100 text-yellow-700 hover:bg-yellow-100',
                                                            tagDef?.color === 'gray' &&
                                                            'bg-gray-100 text-gray-700 hover:bg-gray-100'
                                                        )}
                                                        title={tagDef?.description}
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            onEditTagDetail(tagId)
                                                        }}
                                                    >
                                                        {tagDef?.name || tagId}
                                                    </Badge>
                                                )
                                            })}
                                            {file.tags.length > 2 && (
                                                <TooltipProvider>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Badge variant='outline' className='text-xs cursor-help'>
                                                                +{file.tags.length - 2}
                                                            </Badge>
                                                        </TooltipTrigger>
                                                        <TooltipContent
                                                            side='top'
                                                            className='max-w-xs bg-card border shadow-lg'
                                                        >
                                                            <div className='space-y-1'>
                                                                <p className='text-xs font-semibold mb-2 text-foreground'>
                                                                    所有标签：
                                                                </p>
                                                                <div className='flex flex-wrap gap-1'>
                                                                    {file.tags.map((tagId) => {
                                                                        const tagDef = getTagDefinition(tagId)
                                                                        return (
                                                                            <Badge
                                                                                key={tagId}
                                                                                variant='secondary'
                                                                                className={cn(
                                                                                    'text-xs cursor-pointer hover:opacity-80',
                                                                                    tagDef?.color === 'blue' &&
                                                                                    'bg-blue-100 text-blue-700',
                                                                                    tagDef?.color === 'green' &&
                                                                                    'bg-green-100 text-green-700',
                                                                                    tagDef?.color === 'purple' &&
                                                                                    'bg-purple-100 text-purple-700',
                                                                                    tagDef?.color === 'red' &&
                                                                                    'bg-red-100 text-red-700',
                                                                                    tagDef?.color === 'yellow' &&
                                                                                    'bg-yellow-100 text-yellow-700',
                                                                                    tagDef?.color === 'gray' &&
                                                                                    'bg-gray-100 text-gray-700'
                                                                                )}
                                                                                onClick={() => onEditTagDetail(tagId)}
                                                                            >
                                                                                {tagDef?.name || tagId}
                                                                            </Badge>
                                                                        )
                                                                    })}
                                                                </div>
                                                            </div>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>
                                            )}
                                            {file.tags.length === 0 && (
                                                <span className='text-xs text-muted-foreground'>-</span>
                                            )}
                                        </div>
                                    </td>
                                    )}
                                    {isColumnVisible('uploadTime') && (
                                        <td className='px-6 py-4 text-muted-foreground'>
                                            <div className='flex items-center gap-1.5'>
                                                <Clock className='h-3.5 w-3.5' />
                                                {file.uploadTime}
                                            </div>
                                        </td>
                                    )}
                                    {isColumnVisible('chunks') && (
                                        <td className='px-6 py-4 text-right'>
                                            {file.chunks > 0 ? (
                                                <button
                                                    className='text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:underline transition-colors font-medium cursor-pointer'
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        onViewChunks(file)
                                                    }}
                                                    title='查看切片'
                                                >
                                                    {file.chunks}
                                                </button>
                                            ) : (
                                                <span className='text-muted-foreground'>0</span>
                                            )}
                                        </td>
                                    )}
                                    <td className='px-6 py-4 sticky right-0 bg-card group-hover:bg-muted/30 z-10 shadow-[-4px_0_8px_-2px_rgba(0,0,0,0.1)]'>
                                        <div className='flex items-center justify-center gap-1'>
                                           
                                            {/* 启动/重新解析按钮 */}
                                            <Button
                                                variant='ghost'
                                                size='icon'
                                                className='h-8 w-8'
                                                onClick={() => {
                                                    if (file.status === 'Processing') {
                                                        onCancelParse(file)
                                                    } else if (file.status === 'Pending') {
                                                        // 首次启动无需确认
                                                        onParse(file)
                                                    } else {
                                                        // Completed / Failed 等重新解析/同步场景，弹窗确认
                                                        setReparseConfirmFile(file)
                                                    }
                                                }}
                                                title={
                                                    parsingFileIds.has(file.id)
                                                        ? '处理中...'
                                                        : file.status === 'Processing'
                                                            ? (isWebKnowledgeBase ? '取消同步' : '取消解析')
                                                            : file.status === 'Pending'
                                                                ? (isWebKnowledgeBase ? '启动同步' : '启动解析')
                                                                : (isWebKnowledgeBase ? '重新同步' : '重新解析')
                                                }
                                                disabled={parsingFileIds.has(file.id)}
                                            >
                                                {parsingFileIds.has(file.id) ? (
                                                    <Loader2 className='h-4 w-4 animate-spin' />
                                                ) : file.status === 'Processing' ? (
                                                    <X className='h-4 w-4' />
                                                ) : file.status === 'Pending' ? (
                                                    <img src={withAppAssetPath('icons/icon_start_chunkking.svg')} alt='' className='h-4 w-4' />
                                                ) : (
                                                    <img src={withAppAssetPath('icons/icon_restart_chunkking.svg')} alt='' className='h-4 w-4' />
                                                )}
                                            </Button>
                                            {/* Web 类型不展示“解析配置”，避免与“同步网页”语义冲突；当前行内解析配置入口暂不可用 */}
                                            {!isWebKnowledgeBase && (
                                                <TooltipProvider>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <span className='inline-flex'>
                                                                <Button
                                                                    variant='ghost'
                                                                    size='icon'
                                                                    className='h-8 w-8 cursor-not-allowed opacity-60'
                                                                    type='button'
                                                                    disabled
                                                                    aria-label='解析配置（暂不支持）'
                                                                >
                                                                    <img src={withAppAssetPath('icons/icon_chunkking_setting.svg')} alt='' className='h-4 w-4' />
                                                                </Button>
                                                            </span>
                                                        </TooltipTrigger>
                                                        <TooltipContent side='top'>
                                                            <p className='text-xs'>暂不支持</p>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>
                                            )}
                                             {/* 标签与元数据按钮 */}
                                            <Button
                                                variant='ghost'
                                                size='icon'
                                                className='h-8 w-8'
                                                onClick={() => onEditMetadata(file)}
                                                title='编辑标签与元数据'
                                            >
                                                <img src={withAppAssetPath('icons/icon_tags.svg')} alt='' className='h-4 w-4' />
                                            </Button>
                                            {/* 更多操作 */}
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant='ghost' size='icon' className='h-8 w-8'>
                                                        <MoreVertical className='h-4 w-4' />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align='end'>
                                                    <DropdownMenuItem onClick={() => onViewDetail(file)}>
                                                        <Eye className='h-4 w-4' />
                                                        查看详情
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem onClick={() => onRename(file)}>
                                                        <Edit2 className='h-4 w-4' />
                                                        重命名
                                                    </DropdownMenuItem>
                                                    {file.canDownloadSourceFile !== false && (
                                                        <DropdownMenuItem
                                                            onClick={() => onDownload(file)}
                                                            disabled={Object.prototype.hasOwnProperty.call(downloadProgressMap, file.id)}
                                                        >
                                                            <Download className='h-4 w-4' />
                                                            {Object.prototype.hasOwnProperty.call(downloadProgressMap, file.id)
                                                                ? `${file.contentKind === 'qa_dataset' ? '下载源文件中' : '下载中'} ${typeof downloadProgressMap[file.id] === 'number' ? `${downloadProgressMap[file.id]}%` : ''}`
                                                                : file.contentKind === 'qa_dataset' ? '下载源文件' : '下载'}
                                                        </DropdownMenuItem>
                                                    )}
                                                    <DropdownMenuSeparator />
                                                    <DropdownMenuItem variant='destructive' onClick={() => onDelete(file)}>
                                                        <Trash2 className='h-4 w-4' />
                                                        删除
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                            {Object.prototype.hasOwnProperty.call(downloadProgressMap, file.id) && (
                                                <Badge variant='outline' className='h-6 text-[10px] px-2 bg-blue-50 text-blue-700 border-blue-200'>
                                                    <Loader2 className='h-3 w-3 mr-1 animate-spin' />
                                                    {typeof downloadProgressMap[file.id] === 'number'
                                                        ? `${file.contentKind === 'qa_dataset' ? '下载源文件中' : '下载中'} ${downloadProgressMap[file.id]}%`
                                                        : file.contentKind === 'qa_dataset' ? '下载源文件中' : '下载中'}
                                                </Badge>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            )))}
                    </tbody>
                </table>
            </div>

            {/* 解析日志对话框 */}
            <Dialog open={logDialogOpen} onOpenChange={(open) => {
                setLogDialogOpen(open)
                if (!open) {
                    // 关闭时重置为最新尝试
                    setSelectedAttemptIndex(-1)
                }
            }}>
                <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <img 
                                src={withAppAssetPath('icons/icon_doc_file_parse_log.svg')} 
                                alt="日志" 
                                className="h-5 w-5"
                            />
                            解析日志
                        </DialogTitle>
                    </DialogHeader>
                    {selectedLogFile && isWebKnowledgeBase && selectedLogFile.parseError && (
                        <div className="flex-1 p-4">
                            <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-2">
                                <div className="flex items-center gap-1.5 text-sm font-semibold text-red-700">
                                    <AlertCircle className="h-4 w-4" />
                                    同步错误
                                </div>
                                <p className="whitespace-pre-wrap break-all text-sm text-red-600">{selectedLogFile.parseError}</p>
                            </div>
                        </div>
                    )}
                    {selectedLogFile && (!isWebKnowledgeBase || !selectedLogFile.parseError) && selectedLogFile.parsingLogs && selectedLogFile.parsingLogs.length > 0 && (
                        <div className="space-y-4 flex-1 overflow-hidden flex flex-col">
                            {/* 文件信息 */}
                            <div className="bg-muted/50 p-3 rounded-lg space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-muted-foreground">文件名:</span>
                                    <span className="text-sm font-semibold">{selectedLogFile.name}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-muted-foreground">当前状态:</span>
                                    <Badge 
                                        className={cn(
                                            "text-xs border-none shadow-none",
                                            selectedLogFile.status === 'Completed' && 'bg-green-100 text-green-700',
                                            selectedLogFile.status === 'Processing' && 'bg-blue-100 text-blue-700',
                                            selectedLogFile.status === 'Queued' && 'bg-yellow-100 text-yellow-700',
                                            selectedLogFile.status === 'Failed' && 'bg-red-100 text-red-700',
                                            selectedLogFile.status === 'Pending' && 'bg-slate-100 text-slate-700',
                                            selectedLogFile.status === 'Cancelled' && 'bg-gray-100 text-gray-700'
                                        )}
                                    >
                                        {selectedLogFile.status === 'Completed' ? '已解析' :
                                            selectedLogFile.status === 'Processing' ? '正在解析' :
                                                selectedLogFile.status === 'Queued' ? '排队中' :
                                                    selectedLogFile.status === 'Failed' ? '解析失败' :
                                                        selectedLogFile.status === 'Cancelled' ? '已取消' : '等待启动'}
                                    </Badge>
                                </div>
                            </div>

                            {/* 尝试历史选择器 */}
                            {selectedLogFile.parsingLogs.length > 1 && (
                                <div className="space-y-1.5 px-1">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">解析历史:</span>
                                        <span className="text-xs text-muted-foreground">(最多显示最近 3 次)</span>
                                    </div>
                                    <div className="flex gap-1 flex-wrap">
                                        {selectedLogFile.parsingLogs.map((attempt, index) => {
                                            const isLatest = index === selectedLogFile.parsingLogs!.length - 1
                                            // 🔧 修复：默认选中最新的（-1 表示最新）
                                            const isSelected = selectedAttemptIndex === -1 ? isLatest : index === selectedAttemptIndex
                                            return (
                                                <Button
                                                    key={index}
                                                    variant={isSelected ? "default" : "outline"}
                                                    size="sm"
                                                    className={cn(
                                                        "h-7 text-xs",
                                                        // 🔧 修复：选中时使用主题色，未选中时根据状态使用不同颜色
                                                        isSelected && "bg-primary text-primary-foreground hover:bg-primary/90",
                                                        !isSelected && attempt.status === 'completed' && "border-emerald-300 text-emerald-700 hover:bg-emerald-50",
                                                        !isSelected && attempt.status === 'failed' && "border-red-300 text-red-700 hover:bg-red-50",
                                                        !isSelected && attempt.status === 'cancelled' && "border-slate-300 text-slate-700 hover:bg-slate-50",
                                                        !isSelected && attempt.status === 'interrupted' && "border-amber-300 text-amber-700 hover:bg-amber-50",
                                                        !isSelected && attempt.status === 'processing' && "border-blue-300 text-blue-700 hover:bg-blue-50"
                                                    )}
                                                    onClick={() => setSelectedAttemptIndex(index)}
                                                >
                                                    第 {attempt.attempt} 次
                                                    {isLatest && " (最新)"}
                                                </Button>
                                            )
                                        })}
                                    </div>
                                </div>
                            )}

                            {(() => {
                                // 🔧 修复：默认选中最新的尝试
                                const actualIndex = selectedAttemptIndex === -1 
                                    ? selectedLogFile.parsingLogs.length - 1 
                                    : selectedAttemptIndex
                                const currentAttempt = selectedLogFile.parsingLogs[actualIndex]
                                if (!currentAttempt) return null

                                return (
                                    <>
                                        {/* 当前尝试的详细信息 */}
                                        <div className="bg-blue-50 dark:bg-blue-950/30 p-3 rounded-lg space-y-2 border border-blue-200 dark:border-blue-800">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                                                        第 {currentAttempt.attempt} 次尝试
                                                    </span>
                                                    <Badge 
                                                        className={cn(
                                                            "text-xs border-none shadow-none",
                                                            currentAttempt.status === 'completed' && 'bg-green-100 text-green-700',
                                                            currentAttempt.status === 'processing' && 'bg-blue-100 text-blue-700',
                                                            currentAttempt.status === 'failed' && 'bg-red-100 text-red-700',
                                                            currentAttempt.status === 'cancelled' && 'bg-gray-100 text-gray-700',
                                                            currentAttempt.status === 'interrupted' && 'bg-orange-100 text-orange-700'
                                                        )}
                                                    >
                                                        {currentAttempt.status === 'completed' ? '成功' :
                                                            currentAttempt.status === 'processing' ? '进行中' :
                                                                currentAttempt.status === 'failed' ? '失败' :
                                                                    currentAttempt.status === 'cancelled' ? '已取消' : '中断'}
                                                    </Badge>
                                                </div>
                                                {currentAttempt.duration_ms && (
                                                    <span className="text-xs text-muted-foreground">
                                                        耗时: {(currentAttempt.duration_ms / 1000).toFixed(2)}s
                                                    </span>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                                <span>开始: {new Date(currentAttempt.started_at).toLocaleString('zh-CN')}</span>
                                                {currentAttempt.ended_at && (
                                                    <span>结束: {new Date(currentAttempt.ended_at).toLocaleString('zh-CN')}</span>
                                                )}
                                            </div>
                                            {currentAttempt.error && (
                                                <div className="text-xs p-2 bg-red-50 text-red-700 rounded border border-red-200 mt-2">
                                                    <span className="font-semibold">错误: </span>
                                                    {currentAttempt.error}
                                                </div>
                                            )}
                                        </div>

                                        {/* 日志内容区域 */}
                                        <div className="flex-1 overflow-hidden flex flex-col relative">
                                            {/* 滚动按钮 */}
                                            <div className="absolute top-2 right-2 z-10 flex gap-1">
                                                <Button
                                                    variant="outline"
                                                    size="icon"
                                                    className="h-7 w-7 bg-background/80 backdrop-blur-sm hover:bg-background shadow-md"
                                                    onClick={scrollToTop}
                                                    title="滚动到顶部"
                                                >
                                                    <ChevronsUp className="h-4 w-4" />
                                                </Button>
                                                <Button
                                                    variant="outline"
                                                    size="icon"
                                                    className="h-7 w-7 bg-background/80 backdrop-blur-sm hover:bg-background shadow-md"
                                                    onClick={scrollToBottom}
                                                    title="滚动到底部"
                                                >
                                                    <ChevronsDown className="h-4 w-4" />
                                                </Button>
                                            </div>

                                            {/* 日志内容 */}
                                            <div 
                                                ref={logContainerRef}
                                                className="flex-1 overflow-y-auto space-y-2 border rounded-lg p-4 bg-slate-50 dark:bg-slate-900"
                                            >
                                                {currentAttempt.logs && currentAttempt.logs.length > 0 ? (
                                                    currentAttempt.logs.map((log, idx) => (
                                                        <div key={idx} className="text-sm flex gap-2 font-mono">
                                                            <span className="text-muted-foreground whitespace-nowrap text-xs">
                                                                [{log.time.split('T')[1].split('.')[0]}]
                                                            </span>
                                                            <span className={cn(
                                                                "font-semibold whitespace-nowrap",
                                                                log.status === 'error' ? "text-red-600" :
                                                                    log.status === 'processing' ? "text-blue-600" : 
                                                                        log.status === 'cancelled' ? "text-gray-600" : "text-green-600"
                                                            )}>
                                                                {log.step}:
                                                            </span>
                                                            <span className="text-foreground break-all">{log.message}</span>
                                                        </div>
                                                    ))
                                                ) : (
                                                    <div className="text-center text-muted-foreground py-8">
                                                        暂无日志
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </>
                                )
                            })()}
                        </div>
                    )}
                    {/* 非 web 或无历史日志时的错误兜底展示 */}
                    {selectedLogFile && !isWebKnowledgeBase && (!selectedLogFile.parsingLogs || selectedLogFile.parsingLogs.length === 0) && selectedLogFile.parseError && (
                        <div className="flex-1 p-4">
                            <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-2">
                                <div className="flex items-center gap-1.5 text-sm font-semibold text-red-700">
                                    <AlertCircle className="h-4 w-4" />
                                    同步错误
                                </div>
                                <p className="whitespace-pre-wrap break-all text-sm text-red-600">{selectedLogFile.parseError}</p>
                            </div>
                        </div>
                    )}
                    {/* 无 parsingLogs 也无 parseError 时的兜底提示 */}
                    {selectedLogFile && (!selectedLogFile.parsingLogs || selectedLogFile.parsingLogs.length === 0) && !selectedLogFile.parseError && (
                        <div className="flex-1 flex items-center justify-center text-muted-foreground">
                            <div className="text-center space-y-2">
                                <p>暂无解析日志</p>
                                <p className="text-xs">文档尚未开始解析</p>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>

            {/* 重新解析/同步确认弹窗 */}
            <AlertDialog
                open={Boolean(reparseConfirmFile)}
                onOpenChange={open => {
                    if (!open) {
                        setReparseConfirmFile(null)
                        setForceWebSyncRebuild(false)
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            确认{isWebKnowledgeBase ? '重新同步' : '重新解析'}？
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            {isWebKnowledgeBase
                                ? `将重新抓取「${reparseConfirmFile?.name}」的网页内容并重建切片索引，该操作会覆盖已有数据。请确认是否继续。`
                                : `将重新解析「${reparseConfirmFile?.name}」并重建切片索引，该操作会覆盖已有数据。请确认是否继续。`
                            }
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    {isWebKnowledgeBase && (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
                            <div className="flex items-start gap-3">
                                <Checkbox
                                    id="force-web-sync-rebuild"
                                    checked={forceWebSyncRebuild}
                                    onCheckedChange={(checked) => setForceWebSyncRebuild(Boolean(checked))}
                                />
                                <div className="space-y-1">
                                    <label
                                        htmlFor="force-web-sync-rebuild"
                                        className="text-sm font-medium leading-none cursor-pointer"
                                    >
                                        始终重建索引
                                    </label>
                                    <p className="text-xs text-muted-foreground">
                                        默认仅在网页内容发生变化时才进入 parse -&gt; chunk -&gt; enhance -&gt; train。
                                        勾选后，本次手动同步即使内容未变化也会完整重建索引。
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}
                    <AlertDialogFooter>
                        <AlertDialogCancel>取消</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={() => {
                                if (reparseConfirmFile) {
                                    onParse(reparseConfirmFile, { forceRebuildIndex: forceWebSyncRebuild })
                                    setReparseConfirmFile(null)
                                    setForceWebSyncRebuild(false)
                                }
                            }}
                        >
                            {isWebKnowledgeBase ? '确认同步' : '确认解析'}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
