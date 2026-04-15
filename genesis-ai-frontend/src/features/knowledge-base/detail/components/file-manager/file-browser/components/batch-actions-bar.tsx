import { Play, Settings, Tag, FileText, Power, PowerOff, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip'

interface BatchActionsBarProps {
    selectedCount: number
    onBatchParse: () => void
    onBatchConfig: () => void
    onBatchTag: () => void
    onBatchMetadata: () => void
    onBatchEnable: () => void
    onBatchDisable: () => void
    onBatchDelete: () => void
    onCancelSelection: () => void
}

export function BatchActionsBar({
    selectedCount,
    onBatchParse,
    onBatchConfig: _onBatchConfig,
    onBatchTag,
    onBatchMetadata,
    onBatchEnable,
    onBatchDisable,
    onBatchDelete,
    onCancelSelection,
}: BatchActionsBarProps) {
    if (selectedCount === 0) return null

    return (
        <div className='flex items-center gap-2 p-3 bg-primary/5 rounded-lg border border-primary/20'>
            <span className='text-sm font-medium text-primary'>批量操作：</span>
            <Button variant='outline' size='sm' className='h-8 gap-1.5' onClick={onBatchParse}>
                <Play className='h-3.5 w-3.5' />
                解析
            </Button>
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <span className='inline-flex'>
                            <Button
                                variant='outline'
                                size='sm'
                                className='h-8 gap-1.5 cursor-not-allowed opacity-60'
                                type='button'
                                disabled
                                aria-label='解析配置（暂不支持）'
                            >
                                <Settings className='h-3.5 w-3.5' />
                                解析配置
                            </Button>
                        </span>
                    </TooltipTrigger>
                    <TooltipContent side='top'>
                        <p className='text-xs'>暂不支持</p>
                    </TooltipContent>
                </Tooltip>
            </TooltipProvider>
            <Button variant='outline' size='sm' className='h-8 gap-1.5' onClick={onBatchTag}>
                <Tag className='h-3.5 w-3.5' />
                设置标签
            </Button>
            <Button variant='outline' size='sm' className='h-8 gap-1.5' onClick={onBatchMetadata}>
                <FileText className='h-3.5 w-3.5' />
                设置元数据
            </Button>
            <Button variant='outline' size='sm' className='h-8 gap-1.5' onClick={onBatchEnable}>
                <Power className='h-3.5 w-3.5' />
                启用
            </Button>
            <Button variant='outline' size='sm' className='h-8 gap-1.5' onClick={onBatchDisable}>
                <PowerOff className='h-3.5 w-3.5' />
                禁用
            </Button>
            <Button
                variant='outline'
                size='sm'
                className='h-8 gap-1.5 text-destructive hover:text-destructive'
                onClick={onBatchDelete}
            >
                <Trash2 className='h-3.5 w-3.5' />
                删除
            </Button>
            <div className='flex-1' />
            <Button variant='ghost' size='sm' className='h-8' onClick={onCancelSelection}>
                取消选择
            </Button>
        </div>
    )
}
