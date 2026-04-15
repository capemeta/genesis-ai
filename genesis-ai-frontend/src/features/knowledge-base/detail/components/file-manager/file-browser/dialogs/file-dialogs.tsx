/**
 * 完整的内容管理对话框集合
 * 包含所有 8 个对话框组件
 */
import React from 'react'
import { Plus, X, HelpCircle } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { getTagOutlineColorClass, getTagFilledColorClass } from '../../shared/tag-color-utils'
import type { FileItem, ChunkConfig, MetadataField } from '../types'
import type { TagDefinition } from '../../shared/tag-types'
import { TagDetailSheet } from '../../shared/tag-detail-sheet'

// ==================== 1. 重命名对话框 ====================
interface RenameDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    fileName: string
    onConfirm: (newName: string) => void
}

function RenameDialog({ open, onOpenChange, fileName, onConfirm }: RenameDialogProps) {
    const [value, setValue] = React.useState(fileName)

    React.useEffect(() => {
        setValue(fileName)
    }, [fileName])

    const handleConfirm = () => {
        if (value.trim()) {
            onConfirm(value.trim())
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>重命名文件</DialogTitle>
                    <DialogDescription>请输入新的文件名</DialogDescription>
                </DialogHeader>
                <div className='space-y-4 py-4'>
                    <div className='space-y-2'>
                        <Label htmlFor='filename'>文件名</Label>
                        <Input
                            id='filename'
                            value={value}
                            onChange={(e) => setValue(e.target.value)}
                            placeholder='输入文件名'
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    handleConfirm()
                                }
                            }}
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant='outline' onClick={() => onOpenChange(false)}>
                        取消
                    </Button>
                    <Button onClick={handleConfirm} disabled={!value.trim()}>
                        确认
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// ==================== 2. 解析对话框 ====================
interface ParseDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    file: FileItem | null
    onConfirm: () => void
}

function ParseDialog({
    open,
    onOpenChange,
    file,
    onConfirm,
}: ParseDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className='sm:max-w-[450px]'>
                <DialogHeader className='pb-4 border-b'>
                    <DialogTitle className='text-xl font-semibold'>重新解析文件</DialogTitle>
                    <DialogDescription className="sr-only">
                        重新解析文件对话框
                    </DialogDescription>
                </DialogHeader>
                <div className='space-y-4 pt-4'>
                    <p className="text-sm text-muted-foreground">
                        此操作将根据当前配置重新分块文件内容，确定继续吗？
                    </p>

                    {/* 提示清空已有切片 */}
                    {file && file.chunks > 0 && (
                        <div className='p-4 rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900/50'>
                            <div className='flex items-center gap-2 text-amber-800 dark:text-amber-200 mb-1'>
                                <HelpCircle className='h-4 w-4' />
                                <p className='text-sm font-semibold'>将清空现有分块</p>
                            </div>
                            <p className='text-xs text-amber-700/90 dark:text-amber-300/70 ml-6'>
                                当前有 <span className="font-bold">{file.chunks}</span> 个分块，重新解析会<span className="font-bold underline">删除并重建</span>。
                            </p>
                        </div>
                    )}
                </div>
                <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t">
                    <Button variant='outline' onClick={() => onOpenChange(false)}>
                        取消
                    </Button>
                    <Button onClick={onConfirm} className='bg-blue-600 hover:bg-blue-700'>
                        确认重新解析
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// ==================== 3. 分块配置对话框 ====================
interface ChunkConfigDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    fileName?: string
    config: ChunkConfig
    onConfigChange: (config: ChunkConfig) => void
    onSave: () => void
}

function ChunkConfigDialog({
    open,
    onOpenChange,
    fileName,
    config,
    onConfigChange,
    onSave,
}: ChunkConfigDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className='sm:max-w-[600px]'>
                <DialogHeader>
                    <DialogTitle className='text-xl'>解析配置</DialogTitle>
                    {fileName && <DialogDescription>为文件 "{fileName}" 设置独立的解析参数</DialogDescription>}
                </DialogHeader>
                <div className='space-y-6 py-4'>
                    {/* 分块方法 */}
                    <div className='space-y-2'>
                        <Label htmlFor='chunk-method'>分块方法</Label>
                        <Select
                            value={config.chunkMethod}
                            onValueChange={(value: 'fixed' | 'semantic' | 'recursive') =>
                                onConfigChange({ ...config, chunkMethod: value })
                            }
                        >
                            <SelectTrigger id='chunk-method'>
                                <SelectValue placeholder='选择分块方法' />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value='fixed'>固定大小分块</SelectItem>
                                <SelectItem value='semantic'>语义分块</SelectItem>
                                <SelectItem value='recursive'>递归分块（推荐）</SelectItem>
                            </SelectContent>
                        </Select>
                        <p className='text-xs text-muted-foreground'>
                            {config.chunkMethod === 'fixed' && '按固定字符数切分，简单快速'}
                            {config.chunkMethod === 'semantic' && '基于语义边界切分，保持内容完整性'}
                            {config.chunkMethod === 'recursive' && '递归尝试多种分隔符，平衡大小和语义'}
                        </p>
                    </div>

                    {/* 分块大小 */}
                    <div className='space-y-3'>
                        <div className='flex items-center justify-between'>
                            <Label htmlFor='chunk-size'>分块大小（字符数）</Label>
                            <span className='text-sm font-medium text-primary'>{config.chunkSize}</span>
                        </div>
                        <Slider
                            id='chunk-size'
                            min={128}
                            max={2048}
                            step={64}
                            value={[config.chunkSize]}
                            onValueChange={(value) => onConfigChange({ ...config, chunkSize: value[0] })}
                            className='w-full'
                        />
                        <div className='flex justify-between text-xs text-muted-foreground'>
                            <span>128</span>
                            <span>1024</span>
                            <span>2048</span>
                        </div>
                        <p className='text-xs text-muted-foreground'>
                            推荐值：512-1024。较小的块适合精确检索，较大的块保留更多上下文
                        </p>
                    </div>

                    {/* 重叠大小 */}
                    <div className='space-y-3'>
                        <div className='flex items-center justify-between'>
                            <Label htmlFor='chunk-overlap'>重叠大小（字符数）</Label>
                            <span className='text-sm font-medium text-primary'>{config.chunkOverlap}</span>
                        </div>
                        <Slider
                            id='chunk-overlap'
                            min={0}
                            max={512}
                            step={10}
                            value={[config.chunkOverlap]}
                            onValueChange={(value) => onConfigChange({ ...config, chunkOverlap: value[0] })}
                            className='w-full'
                        />
                        <div className='flex justify-between text-xs text-muted-foreground'>
                            <span>0</span>
                            <span>256</span>
                            <span>512</span>
                        </div>
                        <p className='text-xs text-muted-foreground'>
                            推荐值：分块大小的 10-20%。重叠可以避免重要信息被切断
                        </p>
                    </div>

                    {/* 分隔符 */}
                    <div className='space-y-2'>
                        <Label htmlFor='separators'>分隔符（逗号分隔）</Label>
                        <Textarea
                            id='separators'
                            value={config.separators}
                            onChange={(e) => onConfigChange({ ...config, separators: e.target.value })}
                            placeholder='\\n\\n,\\n,。,！,？'
                            rows={3}
                            className='font-mono text-sm'
                        />
                        <p className='text-xs text-muted-foreground'>
                            按优先级排列的分隔符，用于递归分块。常用：段落分隔符（\n\n）、换行符（\n）、句号等
                        </p>
                    </div>

                    {/* 配置预览 */}
                    <div className='rounded-lg border bg-muted/30 p-4 space-y-2'>
                        <p className='text-sm font-medium'>配置预览</p>
                        <div className='grid grid-cols-2 gap-2 text-xs'>
                            <div>
                                <span className='text-muted-foreground'>方法：</span>
                                <span className='font-medium ml-1'>
                                    {config.chunkMethod === 'fixed' && '固定大小'}
                                    {config.chunkMethod === 'semantic' && '语义分块'}
                                    {config.chunkMethod === 'recursive' && '递归分块'}
                                </span>
                            </div>
                            <div>
                                <span className='text-muted-foreground'>大小：</span>
                                <span className='font-medium ml-1'>{config.chunkSize}</span>
                            </div>
                            <div>
                                <span className='text-muted-foreground'>重叠：</span>
                                <span className='font-medium ml-1'>{config.chunkOverlap}</span>
                            </div>
                            <div>
                                <span className='text-muted-foreground'>重叠率：</span>
                                <span className='font-medium ml-1'>
                                    {((config.chunkOverlap / config.chunkSize) * 100).toFixed(1)}%
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
                <DialogFooter>
                    <Button variant='outline' onClick={() => onOpenChange(false)}>
                        取消
                    </Button>
                    <Button onClick={onSave}>保存配置</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// ==================== 4. 批量解析对话框 ====================
interface BatchParseDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    selectedCount: number
    isWebKnowledgeBase?: boolean
    forceWebSyncRebuild?: boolean
    onForceWebSyncRebuildChange?: (checked: boolean) => void
    onConfirm: () => void
}

function BatchParseDialog({
    open,
    onOpenChange,
    selectedCount,
    isWebKnowledgeBase = false,
    forceWebSyncRebuild = false,
    onForceWebSyncRebuildChange,
    onConfirm,
}: BatchParseDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className='sm:max-w-[450px]'>
                <DialogHeader>
                    <DialogTitle className='text-xl'>{isWebKnowledgeBase ? '批量同步网页' : '批量解析文件'}</DialogTitle>
                    <DialogDescription>
                        {isWebKnowledgeBase
                            ? <>将对选中的 <span className="font-semibold text-blue-600 dark:text-blue-400">{selectedCount}</span> 个网页执行同步操作。</>
                            : <>将对选中的 <span className="font-semibold text-blue-600 dark:text-blue-400">{selectedCount}</span> 个文件执行解析操作。系统将对所有选中的文件应用解析流程。</>
                        }
                    </DialogDescription>
                </DialogHeader>
                <div className='space-y-6 py-4'>

                    {/* 提示清空已有切片 */}
                    <div className='p-4 rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900/50'>
                        <div className='flex items-center gap-2 text-amber-800 dark:text-amber-200 mb-1'>
                            <HelpCircle className='h-4 w-4' />
                            <p className='text-sm font-semibold'>{isWebKnowledgeBase ? '同步后可能重建现有切片' : '现有分块将被清空'}</p>
                        </div>
                        <p className='text-xs text-amber-700/90 dark:text-amber-300/70 ml-6'>
                            {isWebKnowledgeBase
                                ? <>默认仅在网页内容发生变化时才重建索引。若下方勾选“始终重建索引”，系统会<span className="font-bold underline">删除并重建这些网页现有的分块</span>。</>
                                : <>解析将<span className="font-bold underline">删除这些文件现有的所有分块</span>。如果文件之前未解析，则不受影响。</>
                            }
                        </p>
                    </div>
                    {isWebKnowledgeBase && (
                        <div className='rounded-lg border border-slate-200 bg-slate-50 p-4'>
                            <div className='flex items-start gap-3'>
                                <Checkbox
                                    id='batch-force-web-sync-rebuild'
                                    checked={forceWebSyncRebuild}
                                    onCheckedChange={(checked) => onForceWebSyncRebuildChange?.(Boolean(checked))}
                                />
                                <div className='space-y-1'>
                                    <label htmlFor='batch-force-web-sync-rebuild' className='text-sm font-semibold cursor-pointer'>
                                        始终重建索引
                                    </label>
                                    <p className='text-xs text-muted-foreground'>
                                        勾选后，本次手动同步即使网页内容未变化，也会继续执行 parse -&gt; chunk -&gt; enhance -&gt; train。
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
                <DialogFooter className="gap-2 sm:gap-0">
                    <Button variant='outline' onClick={() => onOpenChange(false)}>
                        取消
                    </Button>
                    <Button onClick={onConfirm} className='bg-blue-600 hover:bg-blue-700'>
                        {isWebKnowledgeBase ? '确定批量同步' : '确定批量解析'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// ==================== 6. 元数据和标签编辑对话框 ====================
interface MetadataDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    fileName: string
    editingTags: string[]
    editingMetadata: MetadataField[]
    tagDefinitions: TagDefinition[]
    /** 按 tagId 解析为完整标签（含名称、颜色），未传则用 tagDefinitions.find；用于文档带 tag_id 时显示名称 */
    getTagDefinition?: (tagId: string) => TagDefinition | undefined
    newTag: string
    newMetadataKey: string
    newMetadataValue: string
    onNewTagChange: (value: string) => void
    onNewMetadataKeyChange: (value: string) => void
    onNewMetadataValueChange: (value: string) => void
    onAddTag: () => void
    /** 从可选标签列表点击添加（按 id），与文件夹树一致 */
    onAddTagById?: (tagId: string) => void
    onRemoveTag: (tagId: string) => void
    onEditTagDetail: (tagId?: string) => void
    onAddMetadata: () => void
    onUpdateMetadata: (index: number, key: string, value: string) => void
    onRemoveMetadata: (index: number) => void
    docContextEnabled: boolean
    docContextContent: string
    onDocContextEnabledChange: (enabled: boolean) => void
    onDocContextContentChange: (value: string) => void
    onSave: () => void
    isLoading?: boolean  // 新增：保存加载状态
}

function MetadataDialog({
    open,
    onOpenChange,
    fileName,
    editingTags,
    editingMetadata,
    tagDefinitions,
    getTagDefinition: getTagDefinitionProp,
    newTag,
    newMetadataKey,
    newMetadataValue,
    onNewTagChange,
    onNewMetadataKeyChange,
    onNewMetadataValueChange,
    onAddTag,
    onAddTagById,
    onRemoveTag,
    onEditTagDetail,
    onAddMetadata,
    onUpdateMetadata,
    onRemoveMetadata,
    docContextEnabled,
    docContextContent,
    onDocContextEnabledChange,
    onDocContextContentChange,
    onSave,
    isLoading = false,  // 新增：默认为 false
}: MetadataDialogProps) {
    const getTagDefinition = getTagDefinitionProp ?? ((tagId: string) => tagDefinitions.find((t) => t.id === tagId))
    const editableMetadata = editingMetadata.filter((field) => !field.readonly)
    const readonlyMetadata = editingMetadata.filter((field) => field.readonly)

    return (
        <TooltipProvider>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className='sm:max-w-[750px] max-h-[85vh] overflow-y-auto'>
                    <DialogHeader className="space-y-3">
                        <DialogTitle className='text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent'>
                            编辑标签和元数据
                        </DialogTitle>
                        <DialogDescription className="text-sm text-muted-foreground">
                            正在编辑文件：<span className="font-medium text-foreground">"{fileName}"</span>
                        </DialogDescription>
                    </DialogHeader>
                    <div className='space-y-8 py-6'>
                        {/* 标签编辑 */}
                        <div className='space-y-4'>
                            <div className='flex items-center gap-3'>
                                <Label className='text-lg font-bold text-gray-800 dark:text-gray-200'>标签</Label>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <HelpCircle className='h-4 w-4 text-muted-foreground hover:text-blue-500 cursor-help transition-colors' />
                                    </TooltipTrigger>
                                    <TooltipContent side="right" className="max-w-xs">
                                        <p className="text-sm">标签用于快速分类和筛选文档，支持颜色标记和语义描述</p>
                                    </TooltipContent>
                                </Tooltip>
                                <div className="flex-1"></div>
                                <Button
                                    variant='outline'
                                    size='sm'
                                    className='h-8 gap-2 hover:bg-blue-50 hover:border-blue-300 dark:hover:bg-blue-950/30'
                                    onClick={() => onEditTagDetail()}
                                >
                                    <Plus className='h-3.5 w-3.5' />
                                    详细设置
                                </Button>
                            </div>

                            <div className='flex gap-3'>
                                <Input
                                    placeholder='输入标签名称（快速添加）'
                                    value={newTag}
                                    onChange={(e) => onNewTagChange(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault()
                                            onAddTag()
                                        }
                                    }}
                                    className="flex-1 h-10 border-2 focus:border-blue-400 transition-colors"
                                />
                                <Button
                                    onClick={onAddTag}
                                    size='icon'
                                    className='h-10 w-10 bg-blue-600 hover:bg-blue-700 shadow-md'
                                    title='快速添加'
                                >
                                    <Plus className='h-4 w-4' />
                                </Button>
                            </div>

                            {newTag.trim() && (
                                <div className='px-3 py-2 rounded-md bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800'>
                                    <p className='text-sm'>
                                        {tagDefinitions.some((t) => t.name.toLowerCase() === newTag.trim().toLowerCase()) ? (
                                            <span className='text-blue-700 dark:text-blue-300 font-medium'>
                                                ✓ 标签已存在，点击 + 直接添加
                                            </span>
                                        ) : (
                                            <span className='text-blue-600 dark:text-blue-400'>
                                                + 将创建新标签 "{newTag.trim()}"
                                            </span>
                                        )}
                                    </p>
                                </div>
                            )}

                            {tagDefinitions.length > 0 && onAddTagById && (
                                <div className='space-y-2'>
                                    <p className='text-sm font-medium text-gray-600 dark:text-gray-400'>可选标签：</p>
                                    <div className='flex flex-wrap gap-2 max-h-[120px] overflow-y-auto p-3 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30'>
                                        {tagDefinitions
                                            .filter((t) => !editingTags.includes(t.id))
                                            .slice(0, 15)
                                            .map((tag) => (
                                                <Badge
                                                    key={tag.id}
                                                    variant='outline'
                                                    className={cn(
                                                        'cursor-pointer hover:scale-105 text-sm py-1 px-3 h-8 transition-all duration-200 gap-2 shadow-sm hover:shadow-md',
                                                        getTagOutlineColorClass(tag.color)
                                                    )}
                                                    onClick={() => onAddTagById(tag.id)}
                                                >
                                                    <Plus className='h-3.5 w-3.5 opacity-60' />
                                                    {tag.name}
                                                </Badge>
                                            ))}
                                        {tagDefinitions.filter((t) => !editingTags.includes(t.id)).length > 15 && (
                                            <span className='text-xs text-muted-foreground self-center'>还有更多...</span>
                                        )}
                                    </div>
                                </div>
                            )}

                            {editingTags.length > 0 && (
                                <div className='space-y-2'>
                                    <p className='text-sm font-medium text-gray-600 dark:text-gray-400'>已选标签：</p>
                                    <div className='flex flex-wrap gap-2 p-4 rounded-lg border-2 border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20'>
                                        {editingTags.map((tagId) => {
                                            const tagDef = getTagDefinition(tagId)
                                            return (
                                                <Badge
                                                    key={tagId}
                                                    variant='secondary'
                                                    className={cn(
                                                        'gap-2 pr-2 text-sm py-1.5 px-3 group cursor-pointer hover:scale-105 transition-all duration-200 shadow-sm hover:shadow-md',
                                                        getTagFilledColorClass(tagDef?.color)
                                                    )}
                                                    onClick={() => onEditTagDetail(tagId)}
                                                    title={tagDef ? '点击编辑标签详情' : '点击为此标签添加详细信息'}
                                                >
                                                    {tagDef?.name || tagId}
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            onRemoveTag(tagId)
                                                        }}
                                                        className='ml-1 hover:bg-red-500/20 rounded-full p-1 transition-colors group-hover:bg-red-500/30'
                                                        title='移除标签'
                                                    >
                                                        <X className='h-3.5 w-3.5' />
                                                    </button>
                                                </Badge>
                                            )
                                        })}
                                    </div>
                                </div>
                            )}

                            {editingTags.length === 0 && (
                                <div className='text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg'>
                                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                                        <Plus className="h-6 w-6 text-gray-400" />
                                    </div>
                                    <p className='text-sm'>暂无标签，请添加标签进行分类</p>
                                </div>
                            )}
                        </div>

                        {/* 元数据编辑 */}
                        <div className='space-y-4'>
                            <div className='flex items-center gap-3'>
                                <Label className='text-lg font-bold text-gray-800 dark:text-gray-200'>自定义元数据</Label>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <HelpCircle className='h-4 w-4 text-muted-foreground hover:text-purple-500 cursor-help transition-colors' />
                                    </TooltipTrigger>
                                    <TooltipContent side="right" className="max-w-xs">
                                        <div className="space-y-1 text-sm">
                                            <p>• 元数据可以添加任意键值对，如作者、部门、项目等</p>
                                            <p>• 这些信息会在检索时作为过滤条件使用</p>
                                            <p>• 元数据也会被包含在向量化过程中，提升检索准确度</p>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </div>

                            <div className='flex gap-3'>
                                <Input
                                    placeholder='键（如：author）'
                                    value={newMetadataKey}
                                    onChange={(e) => onNewMetadataKeyChange(e.target.value)}
                                    className='flex-1 h-10 border-2 focus:border-purple-400 transition-colors'
                                />
                                <Input
                                    placeholder='值（如：张三）'
                                    value={newMetadataValue}
                                    onChange={(e) => onNewMetadataValueChange(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault()
                                            onAddMetadata()
                                        }
                                    }}
                                    className='flex-1 h-10 border-2 focus:border-purple-400 transition-colors'
                                />
                                <Button
                                    onClick={onAddMetadata}
                                    size='icon'
                                    className='h-10 w-10 bg-purple-600 hover:bg-purple-700 shadow-md'
                                >
                                    <Plus className='h-4 w-4' />
                                </Button>
                            </div>

                            {editableMetadata.length > 0 && (
                                <div className='space-y-3 p-4 rounded-lg border-2 border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/20'>
                                    {editingMetadata.map((field, index) => {
                                        if (field.readonly) {
                                            return null
                                        }
                                        return (
                                            <div key={index} className='flex gap-3 items-center p-3 bg-white dark:bg-gray-900 rounded-md border shadow-sm'>
                                                <Input
                                                    value={field.key}
                                                    onChange={(e) => onUpdateMetadata(index, e.target.value, field.value)}
                                                    placeholder='键'
                                                    className='flex-1 border-purple-200 focus:border-purple-400'
                                                />
                                                <div className="text-gray-400 font-bold">:</div>
                                                <Input
                                                    value={field.value}
                                                    onChange={(e) => onUpdateMetadata(index, field.key, e.target.value)}
                                                    placeholder='值'
                                                    className='flex-1 border-purple-200 focus:border-purple-400'
                                                />
                                                <Button
                                                    onClick={() => onRemoveMetadata(index)}
                                                    size='icon'
                                                    variant='ghost'
                                                    className='text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30 h-9 w-9'
                                                >
                                                    <X className='h-4 w-4' />
                                                </Button>
                                            </div>
                                        )
                                    })}
                                </div>
                            )}

                            {editableMetadata.length === 0 && (
                                <div className='text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg'>
                                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                                        <Plus className="h-6 w-6 text-gray-400" />
                                    </div>
                                    <p className='text-sm'>暂无自定义元数据，请添加键值对</p>
                                </div>
                            )}

                            {readonlyMetadata.length > 0 && (
                                <div className='space-y-3'>
                                    <div className='flex items-center justify-between'>
                                        <Label className='text-base font-semibold text-gray-700 dark:text-gray-300'>系统元数据</Label>
                                        <span className='text-xs text-muted-foreground'>系统生成，仅展示</span>
                                    </div>
                                    <div className='space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950/20'>
                                        {readonlyMetadata.map((field) => (
                                            <div key={`readonly-${field.key}`} className='grid grid-cols-[180px_1fr] gap-3 items-start rounded-md border bg-white p-3 dark:bg-gray-900'>
                                                <Input value={field.key} readOnly disabled className='bg-slate-100 dark:bg-slate-800' />
                                                <Input value={field.value} readOnly disabled className='bg-slate-100 dark:bg-slate-800' />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className='space-y-4'>
                            <div className='flex items-center gap-3'>
                                <Label className='text-lg font-bold text-gray-800 dark:text-gray-200'>文档补充说明</Label>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <HelpCircle className='h-4 w-4 text-muted-foreground hover:text-emerald-500 cursor-help transition-colors' />
                                    </TooltipTrigger>
                                    <TooltipContent side="right" className="max-w-xs">
                                        <p className="text-sm">给这篇文档补一段长期说明。只有命中这篇文档时，回答才会优先参考它。</p>
                                    </TooltipContent>
                                </Tooltip>
                                <div className='flex-1' />
                                <div className='flex items-center gap-2'>
                                    <span className='text-sm text-muted-foreground'>启用</span>
                                    <Checkbox
                                        checked={docContextEnabled}
                                        onCheckedChange={(checked) => onDocContextEnabledChange(Boolean(checked))}
                                    />
                                </div>
                            </div>

                            <div className='rounded-lg border-2 border-emerald-200 bg-emerald-50/60 p-4 dark:border-emerald-900 dark:bg-emerald-950/20'>
                                <Textarea
                                    value={docContextContent}
                                    onChange={(event) => onDocContextContentChange(event.target.value)}
                                    placeholder='例如：本文件默认适用于中国区 2025 版政策，金额单位按人民币理解。'
                                    rows={5}
                                    disabled={!docContextEnabled}
                                    className='border-emerald-200 bg-white/90 focus:border-emerald-400 disabled:opacity-70 dark:border-emerald-900 dark:bg-slate-950/40'
                                />
                                <p className='mt-2 text-xs text-muted-foreground'>
                                    适合填写适用范围、版本前提、默认口径。没有填写时，系统才会按知识库开关决定是否回退使用文档摘要。
                                </p>
                            </div>
                        </div>
                    </div>
                    <DialogFooter className="gap-3 pt-6 border-t">
                        <Button
                            variant='outline'
                            onClick={() => onOpenChange(false)}
                            className="px-6"
                            disabled={isLoading}  // 保存时禁用取消按钮
                        >
                            取消
                        </Button>
                        <Button
                            onClick={onSave}
                            className="px-6 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                            disabled={isLoading}  // 保存时禁用按钮
                        >
                            {isLoading ? (
                                <>
                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                    保存中...
                                </>
                            ) : (
                                '保存更改'
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </TooltipProvider>
    )
}

// ==================== 7. 批量标签编辑对话框 ====================
function BatchTagDialog({
    open,
    onOpenChange,
    selectedCount,
    editingTags,
    tagDefinitions,
    getTagDefinition: getTagDefinitionProp,
    newTag,
    onNewTagChange,
    onAddTag,
    onAddTagById,
    onRemoveTag,
    onEditTagDetail,
    onSave,
    isLoading = false,  // 新增：默认为 false
}: Omit<MetadataDialogProps, 'fileName' | 'editingMetadata' | 'onAddMetadata' | 'onUpdateMetadata' | 'onRemoveMetadata' | 'newMetadataKey' | 'newMetadataValue' | 'onNewMetadataKeyChange' | 'onNewMetadataValueChange'> & { selectedCount: number }) {
    const getTagDefinition = getTagDefinitionProp ?? ((tagId: string) => tagDefinitions.find((t) => t.id === tagId))

    return (
        <TooltipProvider>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className='sm:max-w-[750px] max-h-[85vh] overflow-y-auto'>
                    <DialogHeader className="space-y-3">
                        <DialogTitle className='text-2xl font-bold bg-gradient-to-r from-blue-600 to-green-600 bg-clip-text text-transparent'>
                            批量设置标签
                        </DialogTitle>
                        <DialogDescription className="text-sm text-muted-foreground">
                            为选中的 <span className="font-medium text-foreground">{selectedCount}</span> 个文件添加标签（将追加到现有标签中）
                        </DialogDescription>
                    </DialogHeader>
                    <div className='space-y-8 py-6'>
                        {/* 标签编辑 */}
                        <div className='space-y-4'>
                            <div className='flex items-center gap-3'>
                                <Label className='text-lg font-bold text-gray-800 dark:text-gray-200'>添加标签</Label>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <HelpCircle className='h-4 w-4 text-muted-foreground hover:text-blue-500 cursor-help transition-colors' />
                                    </TooltipTrigger>
                                    <TooltipContent side="right" className="max-w-xs">
                                        <p className="text-sm">标签用于快速分类和筛选文档，支持颜色标记和语义描述</p>
                                    </TooltipContent>
                                </Tooltip>
                                <div className="flex-1"></div>
                                <Button
                                    variant='outline'
                                    size='sm'
                                    className='h-8 gap-2 hover:bg-blue-50 hover:border-blue-300 dark:hover:bg-blue-950/30'
                                    onClick={() => onEditTagDetail()}
                                >
                                    <Plus className='h-3.5 w-3.5' />
                                    详细设置
                                </Button>
                            </div>

                            <div className='flex gap-3'>
                                <Input
                                    placeholder='输入标签名称（快速添加）'
                                    value={newTag}
                                    onChange={(e) => onNewTagChange(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault()
                                            onAddTag()
                                        }
                                    }}
                                    className="flex-1 h-10 border-2 focus:border-blue-400 transition-colors"
                                />
                                <Button
                                    onClick={onAddTag}
                                    size='icon'
                                    className='h-10 w-10 bg-blue-600 hover:bg-blue-700 shadow-md'
                                    title='快速添加'
                                >
                                    <Plus className='h-4 w-4' />
                                </Button>
                            </div>

                            {newTag.trim() && (
                                <div className='px-3 py-2 rounded-md bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800'>
                                    <p className='text-sm'>
                                        {tagDefinitions.some((t) => t.name.toLowerCase() === newTag.trim().toLowerCase()) ? (
                                            <span className='text-blue-700 dark:text-blue-300 font-medium'>
                                                ✓ 标签已存在，点击 + 直接添加
                                            </span>
                                        ) : (
                                            <span className='text-blue-600 dark:text-blue-400'>
                                                + 将创建新标签 "{newTag.trim()}"
                                            </span>
                                        )}
                                    </p>
                                </div>
                            )}

                            {tagDefinitions.length > 0 && onAddTagById && (
                                <div className='space-y-2'>
                                    <p className='text-sm font-medium text-gray-600 dark:text-gray-400'>可选标签：</p>
                                    <div className='flex flex-wrap gap-2 max-h-[120px] overflow-y-auto p-3 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30'>
                                        {tagDefinitions
                                            .filter((t) => !editingTags.includes(t.id))
                                            .slice(0, 15)
                                            .map((tag) => (
                                                <Badge
                                                    key={tag.id}
                                                    variant='outline'
                                                    className={cn(
                                                        'cursor-pointer hover:scale-105 text-sm py-1 px-3 h-8 transition-all duration-200 gap-2 shadow-sm hover:shadow-md',
                                                        getTagOutlineColorClass(tag.color)
                                                    )}
                                                    onClick={() => onAddTagById(tag.id)}
                                                >
                                                    <Plus className='h-3.5 w-3.5 opacity-60' />
                                                    {tag.name}
                                                </Badge>
                                            ))}
                                        {tagDefinitions.filter((t) => !editingTags.includes(t.id)).length > 15 && (
                                            <span className='text-xs text-muted-foreground self-center'>还有更多...</span>
                                        )}
                                    </div>
                                </div>
                            )}

                            {editingTags.length > 0 && (
                                <div className='space-y-2'>
                                    <p className='text-sm font-medium text-gray-600 dark:text-gray-400'>已选标签：</p>
                                    <div className='flex flex-wrap gap-2 p-4 rounded-lg border-2 border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20'>
                                        {editingTags.map((tagId) => {
                                            const tagDef = getTagDefinition(tagId)
                                            return (
                                                <Badge
                                                    key={tagId}
                                                    variant='secondary'
                                                    className={cn(
                                                        'gap-2 pr-2 text-sm py-1.5 px-3 group cursor-pointer hover:scale-105 transition-all duration-200 shadow-sm hover:shadow-md',
                                                        getTagFilledColorClass(tagDef?.color)
                                                    )}
                                                    onClick={() => onEditTagDetail(tagId)}
                                                    title={tagDef ? '点击编辑标签详情' : '点击为此标签添加详细信息'}
                                                >
                                                    {tagDef?.name || tagId}
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            onRemoveTag(tagId)
                                                        }}
                                                        className='ml-1 hover:bg-red-500/20 rounded-full p-1 transition-colors group-hover:bg-red-500/30'
                                                        title='移除标签'
                                                    >
                                                        <X className='h-3.5 w-3.5' />
                                                    </button>
                                                </Badge>
                                            )
                                        })}
                                    </div>
                                </div>
                            )}

                            {editingTags.length === 0 && (
                                <div className='text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg'>
                                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                                        <Plus className="h-6 w-6 text-gray-400" />
                                    </div>
                                    <p className='text-sm'>暂无标签，请添加标签进行分类</p>
                                </div>
                            )}
                        </div>
                    </div>
                    <DialogFooter className="gap-3 pt-6 border-t">
                        <Button
                            variant='outline'
                            onClick={() => onOpenChange(false)}
                            className="px-6"
                            disabled={isLoading}  // 保存时禁用取消按钮
                        >
                            取消
                        </Button>
                        <Button
                            onClick={onSave}
                            disabled={editingTags.length === 0 || isLoading}
                            className="px-6 bg-gradient-to-r from-blue-600 to-green-600 hover:from-blue-700 hover:to-green-700 shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isLoading ? (
                                <>
                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                    保存中...
                                </>
                            ) : (
                                `应用标签 (${editingTags.length})`
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </TooltipProvider>
    )
}

// ==================== 8. 批量元数据编辑对话框 ====================
function BatchMetadataDialog({
    open,
    onOpenChange,
    selectedCount,
    editingMetadata,
    newMetadataKey,
    newMetadataValue,
    onNewMetadataKeyChange,
    onNewMetadataValueChange,
    onAddMetadata,
    onUpdateMetadata,
    onRemoveMetadata,
    onSave,
    isLoading = false,  // 新增：默认为 false
}: Omit<MetadataDialogProps, 'fileName' | 'editingTags' | 'tagDefinitions' | 'getTagDefinition' | 'newTag' | 'onNewTagChange' | 'onAddTag' | 'onAddTagById' | 'onRemoveTag' | 'onEditTagDetail'> & { selectedCount: number }) {
    const editableMetadata = editingMetadata.filter((field) => !field.readonly)

    return (
        <TooltipProvider>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className='sm:max-w-[750px] max-h-[85vh] overflow-y-auto'>
                    <DialogHeader className="space-y-3">
                        <DialogTitle className='text-2xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent'>
                            批量设置元数据
                        </DialogTitle>
                        <div className="space-y-2">
                            <DialogDescription className="text-sm text-muted-foreground">
                                为选中的 <span className="font-medium text-foreground">{selectedCount}</span> 个文件设置元数据
                            </DialogDescription>
                            <div className='flex items-center gap-2 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/30 px-3 py-2 rounded-md border border-amber-200 dark:border-amber-800'>
                                <span className='text-sm'>⚠</span>
                                <span className='text-xs'>
                                    此处设置的元数据将合并到所有文档，如果 Key 已存在将覆盖原值，未设置的 Key 保持不变
                                </span>
                            </div>
                        </div>
                    </DialogHeader>
                    <div className='space-y-8 py-6'>
                        {/* 元数据编辑 */}
                        <div className='space-y-4'>
                            <div className='flex items-center gap-3'>
                                <Label className='text-lg font-bold text-gray-800 dark:text-gray-200'>添加元数据</Label>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <HelpCircle className='h-4 w-4 text-muted-foreground hover:text-purple-500 cursor-help transition-colors' />
                                    </TooltipTrigger>
                                    <TooltipContent side="right" className="max-w-xs">
                                        <div className="space-y-1 text-sm">
                                            <p>• 元数据可以添加任意键值对，如作者、部门、项目等</p>
                                            <p>• 这些信息会在检索时作为过滤条件使用</p>
                                            <p>• 元数据也会被包含在向量化过程中，提升检索准确度</p>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </div>

                            <div className='flex gap-3'>
                                <Input
                                    placeholder='键（如：department）'
                                    value={newMetadataKey}
                                    onChange={(e) => onNewMetadataKeyChange(e.target.value)}
                                    className='flex-1 h-10 border-2 focus:border-purple-400 transition-colors'
                                />
                                <Input
                                    placeholder='值（如：技术部）'
                                    value={newMetadataValue}
                                    onChange={(e) => onNewMetadataValueChange(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault()
                                            onAddMetadata()
                                        }
                                    }}
                                    className='flex-1 h-10 border-2 focus:border-purple-400 transition-colors'
                                />
                                <Button
                                    onClick={onAddMetadata}
                                    size='icon'
                                    className='h-10 w-10 bg-purple-600 hover:bg-purple-700 shadow-md'
                                >
                                    <Plus className='h-4 w-4' />
                                </Button>
                            </div>

                            {editableMetadata.length > 0 && (
                                <div className='space-y-3 p-4 rounded-lg border-2 border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/20'>
                                    {editingMetadata.map((field, index) => {
                                        if (field.readonly) {
                                            return null
                                        }
                                        return (
                                            <div key={index} className='flex gap-3 items-center p-3 bg-white dark:bg-gray-900 rounded-md border shadow-sm'>
                                                <Input
                                                    value={field.key}
                                                    onChange={(e) => onUpdateMetadata(index, e.target.value, field.value)}
                                                    placeholder='键'
                                                    className='flex-1 border-purple-200 focus:border-purple-400'
                                                />
                                                <div className="text-gray-400 font-bold">:</div>
                                                <Input
                                                    value={field.value}
                                                    onChange={(e) => onUpdateMetadata(index, field.key, e.target.value)}
                                                    placeholder='值'
                                                    className='flex-1 border-purple-200 focus:border-purple-400'
                                                />
                                                <Button
                                                    onClick={() => onRemoveMetadata(index)}
                                                    size='icon'
                                                    variant='ghost'
                                                    className='text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30 h-9 w-9'
                                                >
                                                    <X className='h-4 w-4' />
                                                </Button>
                                            </div>
                                        )
                                    })}
                                </div>
                            )}

                            {editableMetadata.length === 0 && (
                                <div className='text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg'>
                                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                                        <Plus className="h-6 w-6 text-gray-400" />
                                    </div>
                                    <p className='text-sm'>暂无元数据，请添加键值对</p>
                                </div>
                            )}
                        </div>
                    </div>
                    <DialogFooter className="gap-3 pt-6 border-t">
                        <Button
                            variant='outline'
                            onClick={() => onOpenChange(false)}
                            className="px-6"
                            disabled={isLoading}  // 保存时禁用取消按钮
                        >
                            取消
                        </Button>
                        <Button
                            onClick={onSave}
                            disabled={editableMetadata.length === 0 || isLoading}
                            className="px-6 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isLoading ? (
                                <>
                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                    保存中...
                                </>
                            ) : (
                                `应用元数据 (${editableMetadata.length})`
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </TooltipProvider>
    )
}

// 导出所有对话框（TagDetailSheet 为共享标签编辑侧边栏，由 file-browser 挂载）
export {
    RenameDialog,
    ParseDialog,
    ChunkConfigDialog,
    BatchParseDialog,
    TagDetailSheet,
    MetadataDialog,
    BatchTagDialog,
    BatchMetadataDialog,
}
