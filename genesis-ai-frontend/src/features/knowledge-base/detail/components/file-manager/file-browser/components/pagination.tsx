import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface PaginationProps {
    currentPage: number
    totalPages: number
    pageSize: number
    totalItems: number
    startIndex: number
    endIndex: number
    onPageChange: (page: number) => void
    onPageSizeChange: (pageSize: number) => void
}

export function Pagination({
    currentPage,
    totalPages,
    pageSize,
    totalItems,
    startIndex,
    endIndex,
    onPageChange,
    onPageSizeChange,
}: PaginationProps) {
    const needPageNav = totalPages > 1
    const displayEnd = totalItems === 0 ? 0 : Math.min(endIndex, totalItems)
    const displayStart = totalItems === 0 ? 0 : startIndex + 1

    return (
        <div className='flex items-center justify-between px-2 py-4'>
            <div className='flex items-center gap-2 text-sm text-muted-foreground'>
                <span>
                    {totalItems === 0
                        ? '共 0 条'
                        : `显示 ${displayStart} - ${displayEnd} 条，共 ${totalItems} 条`}
                </span>
            </div>
            <div className='flex items-center gap-2'>
                <div className='flex items-center gap-1'>
                    <span className='text-sm text-muted-foreground mr-2'>每页</span>
                    <Select
                        value={pageSize.toString()}
                        onValueChange={(value) => {
                            onPageSizeChange(Number(value))
                        }}
                    >
                        <SelectTrigger className='h-8 w-[70px]'>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value='10'>10</SelectItem>
                            <SelectItem value='20'>20</SelectItem>
                            <SelectItem value='30'>30</SelectItem>
                            <SelectItem value='50'>50</SelectItem>
                            <SelectItem value='100'>100</SelectItem>
                        </SelectContent>
                    </Select>
                    <span className='text-sm text-muted-foreground ml-2'>条</span>
                </div>
                {needPageNav && (
                    <div className='flex items-center gap-1'>
                        <Button
                            variant='outline'
                            size='icon'
                            className='h-8 w-8'
                            onClick={() => onPageChange(1)}
                            disabled={currentPage === 1}
                        >
                            <ChevronsLeft className='h-4 w-4' />
                        </Button>
                        <Button
                            variant='outline'
                            size='icon'
                            className='h-8 w-8'
                            onClick={() => onPageChange(currentPage - 1)}
                            disabled={currentPage === 1}
                        >
                            <ChevronLeft className='h-4 w-4' />
                        </Button>
                        <div className='flex items-center gap-1 px-3'>
                            <span className='text-sm'>
                                第 {currentPage} / {totalPages} 页
                            </span>
                        </div>
                        <Button
                            variant='outline'
                            size='icon'
                            className='h-8 w-8'
                            onClick={() => onPageChange(currentPage + 1)}
                            disabled={currentPage === totalPages}
                        >
                            <ChevronRight className='h-4 w-4' />
                        </Button>
                        <Button
                            variant='outline'
                            size='icon'
                            className='h-8 w-8'
                            onClick={() => onPageChange(totalPages)}
                            disabled={currentPage === totalPages}
                        >
                            <ChevronsRight className='h-4 w-4' />
                        </Button>
                    </div>
                )}
            </div>
        </div>
    )
}
