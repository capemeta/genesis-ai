import { Check, Loader2, AlertCircle, Clock, Calendar, Timer, User, ArrowDown, Cpu } from 'lucide-react'
import { Sheet, SheetContent, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { getFileTypeIconUrl } from '../../shared/file-type-icon'
import { useRef } from 'react'

import type { FileItem, TagDefinition } from '../types'
import { Progress } from '@/components/ui/progress'

interface FileDetailSheetProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    file: FileItem | null
    tagDefinitions: TagDefinition[]
    // 知识库类型，用于状态文案差异化展示
    kbType?: string
}

export function FileDetailSheet({ open, onOpenChange, file, tagDefinitions, kbType }: FileDetailSheetProps) {
    const isWebKnowledgeBase = kbType === 'web'
    const logContainerRef = useRef<HTMLDivElement>(null)
    const runtimeModels = Object.entries(file?.runtimeModels || {})
    
    const getTagDefinition = (tagId: string) => {
        return tagDefinitions.find((t) => t.id === tagId)
    }

    const scrollToBottom = () => {
        if (logContainerRef.current) {
            logContainerRef.current.scrollTo({
                top: logContainerRef.current.scrollHeight,
                behavior: 'smooth'
            })
        }
    }

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className='w-[600px] sm:max-w-[600px] overflow-y-auto p-0'>
                {/* 无障碍标题（视觉上隐藏） */}
                <SheetTitle className="sr-only">文件详情</SheetTitle>
                <SheetDescription className="sr-only">查看文件的详细信息和处理状态</SheetDescription>
                
                {/* Header 区域 */}
                <div className='sticky top-0 z-10 bg-background border-b px-6 py-4'>
                    <div className='flex items-start justify-between'>
                        <div>
                            <h2 className='text-lg font-semibold'>文件详情</h2>
                            <p className='text-sm text-muted-foreground mt-1'>查看文件的详细信息和处理状态</p>
                        </div>
                    </div>
                </div>

                {/* 内容区域 */}
                {file && (
                    <div className='px-6 py-6 space-y-6'>
                        {/* 文件名 */}
                        <div className='pb-4 border-b'>
                            <p className='text-xs text-muted-foreground mb-2'>文件名</p>
                            <div className='flex items-center gap-2'>
                                <img
                                    src={getFileTypeIconUrl(file.name, undefined, file.type)}
                                    alt=''
                                    className='h-8 w-8 shrink-0 object-contain'
                                />
                                <p className='text-base font-semibold break-all leading-relaxed'>{file.name}</p>
                            </div>
                        </div>

                        {/* 基本信息 */}
                        <div className='space-y-4'>
                            <h3 className='text-sm font-semibold text-foreground'>基本信息</h3>

                            <div className='grid grid-cols-2 gap-x-6 gap-y-4'>
                                <div>
                                    <p className='text-xs text-muted-foreground mb-1.5'>文件类型</p>
                                    <p className='text-sm font-medium'>{file.type}</p>
                                </div>
                                <div>
                                    <p className='text-xs text-muted-foreground mb-1.5'>文件大小</p>
                                    <p className='text-sm font-medium'>{file.size}</p>
                                </div>
                                <div>
                                    <p className='text-xs text-muted-foreground mb-1.5'>分块数</p>
                                    <p className='text-sm font-medium'>{file.chunks}</p>
                                </div>
                                <div>
                                    <p className='text-xs text-muted-foreground mb-1.5'>状态</p>
                                    <Badge
                                        className={cn(
                                            'gap-1 border-none shadow-none',
                                            file.status === 'Completed' && 'bg-green-100 text-green-700',
                                            file.status === 'Processing' && 'bg-blue-100 text-blue-700',
                                            file.status === 'Queued' && 'bg-yellow-100 text-yellow-700',
                                            file.status === 'Failed' && 'bg-red-100 text-red-700',
                                            // Pending 在 web 类型下为"待同步"，橙色传递待办感；普通文件下灰色
                                            file.status === 'Pending' && (isWebKnowledgeBase ? 'bg-orange-50 text-orange-600' : 'bg-slate-100 text-slate-700'),
                                            file.status === 'Cancelled' && 'bg-gray-100 text-gray-700',
                                            file.status === 'Cancelling' && 'bg-orange-100 text-orange-700',
                                            // web 専属中间态：已同步内容，正在建索引
                                            file.status === 'SyncedChunking' && 'bg-cyan-50 text-cyan-700'
                                        )}
                                    >
                                        {file.status === 'Completed' && <Check className='h-3 w-3' />}
                                        {file.status === 'Processing' && <Loader2 className='h-3 w-3 animate-spin' />}
                                        {file.status === 'Queued' && <Clock className='h-3 w-3' />}
                                        {file.status === 'Failed' && <AlertCircle className='h-3 w-3' />}
                                        {file.status === 'Pending' && <Clock className='h-3 w-3' />}
                                        {file.status === 'Cancelled' && <AlertCircle className='h-3 w-3' />}
                                        {file.status === 'Cancelling' && <Loader2 className='h-3 w-3 animate-spin' />}
                                        {file.status === 'SyncedChunking' && <Loader2 className='h-3 w-3 animate-spin' />}
                                        {
                                            file.status === 'Completed' ? (isWebKnowledgeBase ? '同步完成' : '已解析') :
                                            file.status === 'Processing' ? (isWebKnowledgeBase ? '同步中' : '正在解析') :
                                            file.status === 'Queued' ? '排队中' :
                                            file.status === 'Failed' ? (isWebKnowledgeBase ? '同步失败' : '解析失败') :
                                            file.status === 'Pending' ? (isWebKnowledgeBase ? '待同步' : '等待启动') :
                                            file.status === 'Cancelled' ? '已取消' :
                                            file.status === 'Cancelling' ? '取消中' :
                                            file.status === 'SyncedChunking' ? '已同步，建索引中' :
                                            '等待启动'
                                        }
                                    </Badge>
                                </div>
                            </div>
                        </div>

                        {/* 时间信息 */}
                        <div className='space-y-4 pt-4 border-t'>
                            <h3 className='text-sm font-semibold text-foreground'>时间信息</h3>

                            <div className='grid grid-cols-2 gap-x-6 gap-y-4'>
                                <div>
                                    <p className='text-xs text-muted-foreground mb-1.5'>上传时间</p>
                                    <div className='flex items-center gap-1.5'>
                                        <Calendar className='h-3.5 w-3.5 text-muted-foreground' />
                                        <p className='text-sm font-medium'>{file.uploadTime}</p>
                                    </div>
                                </div>
                                {file.startTime && (
                                    <div>
                                        <p className='text-xs text-muted-foreground mb-1.5'>开始解析</p>
                                        <div className='flex items-center gap-1.5'>
                                            <Clock className='h-3.5 w-3.5 text-muted-foreground' />
                                            <p className='text-sm font-medium'>{file.startTime}</p>
                                        </div>
                                    </div>
                                )}
                                {file.duration && (
                                    <div>
                                        <p className='text-xs text-muted-foreground mb-1.5'>处理时长</p>
                                        <div className='flex items-center gap-1.5'>
                                            <Timer className='h-3.5 w-3.5 text-muted-foreground' />
                                            <p className='text-sm font-medium'>{file.duration}</p>
                                        </div>
                                    </div>
                                )}
                                <div>
                                    <p className='text-xs text-muted-foreground mb-1.5'>创建者</p>
                                    <div className='flex items-center gap-1.5'>
                                        <User className='h-3.5 w-3.5 text-muted-foreground' />
                                        <p className='text-sm font-medium'>{file.creator || 'Unknown'}</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* 标签 */}
                        {file.tags.length > 0 && (
                            <div className='space-y-3 pt-4 border-t'>
                                <h3 className='text-sm font-semibold text-foreground'>标签</h3>
                                <div className='flex flex-wrap gap-2'>
                                    {file.tags.map((tagId) => {
                                        const tagDef = getTagDefinition(tagId)
                                        return (
                                            <Badge
                                                key={tagId}
                                                variant='secondary'
                                                className={cn(
                                                    'text-xs',
                                                    tagDef?.color === 'blue' && 'bg-blue-100 text-blue-700',
                                                    tagDef?.color === 'green' && 'bg-green-100 text-green-700',
                                                    tagDef?.color === 'purple' && 'bg-purple-100 text-purple-700',
                                                    tagDef?.color === 'red' && 'bg-red-100 text-red-700',
                                                    tagDef?.color === 'yellow' && 'bg-yellow-100 text-yellow-700',
                                                    tagDef?.color === 'gray' && 'bg-gray-100 text-gray-700'
                                                )}
                                                title={tagDef?.description}
                                            >
                                                {tagDef?.name || tagId}
                                            </Badge>
                                        )
                                    })}
                                </div>
                            </div>
                        )}

                        {/* 运行时模型快照 */}
                        {runtimeModels.length > 0 && (
                            <div className='space-y-4 pt-4 border-t'>
                                <div className='flex items-center gap-2'>
                                    <Cpu className='h-4 w-4 text-muted-foreground' />
                                    <h3 className='text-sm font-semibold text-foreground'>本次运行模型快照</h3>
                                </div>
                                <p className='text-xs leading-relaxed text-muted-foreground'>
                                    展示这份文档最近一次实际处理时使用的模型，不受当前知识库最新配置实时覆盖。
                                </p>
                                <div className='space-y-3'>
                                    {runtimeModels.map(([capability, modelInfo]) => (
                                        <div key={capability} className='rounded-lg border bg-muted/20 p-3 space-y-1.5'>
                                            <div className='flex items-center justify-between gap-3'>
                                                <span className='text-xs font-semibold uppercase tracking-wide text-muted-foreground'>
                                                    {capability === 'embedding' ? '嵌入模型' : capability === 'chat' ? '理解与增强模型' : capability}
                                                </span>
                                                {modelInfo.provider_code && (
                                                    <Badge variant='secondary' className='text-[11px]'>
                                                        {modelInfo.provider_code}
                                                    </Badge>
                                                )}
                                            </div>
                                            <p className='text-sm font-medium text-foreground'>
                                                {modelInfo.display_name || modelInfo.raw_model_name || '未记录模型名称'}
                                            </p>
                                            {modelInfo.raw_model_name && modelInfo.display_name !== modelInfo.raw_model_name && (
                                                <p className='text-xs text-muted-foreground break-all'>
                                                    原始模型名: {modelInfo.raw_model_name}
                                                </p>
                                            )}
                                            {modelInfo.tenant_model_id && (
                                                <p className='text-xs text-muted-foreground break-all'>
                                                    租户模型ID: {modelInfo.tenant_model_id}
                                                </p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                                {file.runtimeUpdatedAt && (
                                    <p className='text-xs text-muted-foreground'>
                                        快照更新时间: {new Date(file.runtimeUpdatedAt).toLocaleString('zh-CN', { hour12: false })}
                                    </p>
                                )}
                            </div>
                        )}

                        {/* 日志 / 同步错误区块 */}
                        {((file.parsingLogs && file.parsingLogs.length > 0) || file.parseError) && (
                            <div className='space-y-4 pt-4 border-t'>
                                <div className="flex items-center justify-between">
                                    <h3 className='text-sm font-semibold text-foreground'>
                                        {isWebKnowledgeBase ? '同步日志' : '解析日志'}
                                    </h3>
                                    <div className="flex items-center gap-2">
                                        {file.status === 'Processing' && (
                                            <span className="text-xs text-blue-600 font-medium">进度: {file.progress}%</span>
                                        )}
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-7 px-2 text-xs gap-1"
                                            onClick={scrollToBottom}
                                            title="跳转到底部"
                                        >
                                            <ArrowDown className="h-3 w-3" />
                                            跳到底部
                                        </Button>
                                    </div>
                                </div>

                                {file.status === 'Processing' && (
                                    <div className="space-y-1.5">
                                        <Progress value={file.progress} className="h-1.5" />
                                    </div>
                                )}

                                <div 
                                    ref={logContainerRef}
                                    className='bg-muted/30 rounded-lg p-4 space-y-2 font-mono text-xs max-h-80 overflow-y-auto scrollbar-thin'
                                >
                                    {isWebKnowledgeBase && file.parseError ? (
                                        <div className="p-2 bg-red-50 text-red-700 rounded border border-red-100">
                                            <div className="font-bold flex items-center gap-1 mb-1 text-[11px]">
                                                <AlertCircle className="h-3 w-3" />
                                                同步错误
                                            </div>
                                            {file.parseError}
                                        </div>
                                    ) : (
                                        <>
                                            {file.parsingLogs?.flatMap((attempt) => 
                                                attempt.logs?.map((log, index) => (
                                                    <div key={`${attempt.attempt}-${index}`} className='flex gap-2 leading-relaxed'>
                                                        <span className="text-muted-foreground shrink-0">[{log.time?.split('T')[1]?.split('.')[0] || 'N/A'}]</span>
                                                        <span className={cn(
                                                            "shrink-0 font-bold uppercase",
                                                            log.status === 'error' ? "text-red-500" :
                                                                log.status === 'processing' ? "text-blue-500" : "text-green-600"
                                                        )}>{log.step}:</span>
                                                        <span className='text-foreground/80 break-all'>{log.message}</span>
                                                    </div>
                                                )) || []
                                            )}
                                            {file.parseError && (
                                                <div className="mt-2 p-2 bg-red-50 text-red-700 rounded border border-red-100">
                                                    <div className="font-bold flex items-center gap-1 mb-1 text-[11px]">
                                                        <AlertCircle className="h-3 w-3" />
                                                        最终错误
                                                    </div>
                                                    {file.parseError}
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </SheetContent>
        </Sheet>
    )
}
