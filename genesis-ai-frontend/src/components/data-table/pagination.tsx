import {
  ChevronLeftIcon,
  ChevronRightIcon,
  DoubleArrowLeftIcon,
  DoubleArrowRightIcon,
} from '@radix-ui/react-icons'
import { type Table } from '@tanstack/react-table'
import { cn, getPageNumbers } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type DataTablePaginationProps<TData> = {
  table: Table<TData>
  className?: string
  totalRecords?: number // 总记录数（可选）
}

export function DataTablePagination<TData>({
  table,
  className,
  totalRecords,
}: DataTablePaginationProps<TData>) {
  const currentPage = table.getState().pagination.pageIndex + 1
  const totalPages = table.getPageCount()
  const pageNumbers = getPageNumbers(currentPage, totalPages)
  
  // 如果没有传入 totalRecords，则使用表格的行数
  const recordCount = totalRecords ?? table.getRowCount()

  return (
    <div
      className={cn(
        'flex items-center justify-between overflow-clip px-2',
        '@max-2xl/content:flex-col-reverse @max-2xl/content:gap-4',
        className
      )}
      style={{ overflowClipMargin: 1 }}
    >
      <div className='flex w-full items-center justify-between'>
        <div className='flex items-center text-sm font-medium text-muted-foreground'>
          共 {recordCount} 条记录
        </div>
        <div className='flex items-center gap-2'>
          <p className='hidden text-sm font-medium sm:block'>每页行数</p>
          <Select
            value={`${table.getState().pagination.pageSize}`}
            onValueChange={(value) => {
              // 改变每页行数时，重置到第一页
              // 直接调用 onPaginationChange 而不是 setPageSize/setPageIndex
              // 这样可以确保两个状态同时更新
              const newPageSize = Number(value)
              const newPagination = {
                pageIndex: 0,
                pageSize: newPageSize,
              }
              // 获取 onPaginationChange 回调并调用它
              const onPaginationChange = (table as any).options.onPaginationChange
              if (onPaginationChange) {
                onPaginationChange(newPagination)
              }
            }}
          >
            <SelectTrigger className='h-8 w-[70px]'>
              <SelectValue placeholder={table.getState().pagination.pageSize} />
            </SelectTrigger>
            <SelectContent side='top'>
              {[10, 20, 30, 40, 50].map((pageSize) => (
                <SelectItem key={pageSize} value={`${pageSize}`}>
                  {pageSize}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className='flex items-center sm:space-x-6 lg:space-x-8'>
        <div className='flex w-[100px] items-center justify-center text-sm font-medium @max-3xl/content:hidden'>
          第 {currentPage} 页，共 {totalPages} 页
        </div>
        <div className='flex items-center space-x-2'>
          <Button
            variant='outline'
            className='size-8 p-0 @max-md/content:hidden'
            onClick={() => table.setPageIndex(0)}
            disabled={!table.getCanPreviousPage()}
          >
            <span className='sr-only'>跳转到第一页</span>
            <DoubleArrowLeftIcon className='h-4 w-4' />
          </Button>
          <Button
            variant='outline'
            className='size-8 p-0'
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            <span className='sr-only'>上一页</span>
            <ChevronLeftIcon className='h-4 w-4' />
          </Button>

          {/* 页码按钮 */}
          {pageNumbers.map((pageNumber, index) => (
            <div key={`${pageNumber}-${index}`} className='flex items-center'>
              {pageNumber === '...' ? (
                <span className='px-1 text-sm text-muted-foreground'>...</span>
              ) : (
                <Button
                  variant={currentPage === pageNumber ? 'default' : 'outline'}
                  className='h-8 min-w-8 px-2'
                  onClick={() => table.setPageIndex((pageNumber as number) - 1)}
                >
                  <span className='sr-only'>跳转到第 {pageNumber} 页</span>
                  {pageNumber}
                </Button>
              )}
            </div>
          ))}

          <Button
            variant='outline'
            className='size-8 p-0'
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            <span className='sr-only'>下一页</span>
            <ChevronRightIcon className='h-4 w-4' />
          </Button>
          <Button
            variant='outline'
            className='size-8 p-0 @max-md/content:hidden'
            onClick={() => table.setPageIndex(table.getPageCount() - 1)}
            disabled={!table.getCanNextPage()}
          >
            <span className='sr-only'>跳转到最后一页</span>
            <DoubleArrowRightIcon className='h-4 w-4' />
          </Button>
        </div>
      </div>
    </div>
  )
}
