/**
 * 切片预览组件 - Badge 组件
 */
import type { Chunk } from '@/lib/api/chunks'
import { Badge } from '@/components/ui/badge'
import {
  isExcelSheetRootChunk,
  isExcelRowParentChunk,
  getExcelSheetName,
} from '../lib/excel'

/**
 * Excel Sheet 根块徽章
 */
export function ExcelSheetRootBadge({ chunk }: { chunk?: Chunk | null }) {
  if (!isExcelSheetRootChunk(chunk)) return null

  return (
    <>
      <Badge
        variant='outline'
        className='h-5 shrink-0 border-cyan-200 bg-cyan-50 px-1.5 text-[10px] font-medium text-cyan-700 dark:border-cyan-800 dark:bg-cyan-950/30 dark:text-cyan-300'
      >
        Sheet: {getExcelSheetName(chunk) || '未命名'}
      </Badge>
      <Badge
        variant='outline'
        className='h-5 shrink-0 border-slate-200 bg-slate-50 px-1.5 text-[10px] text-slate-600 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300'
      >
        仅结构，不检索
      </Badge>
    </>
  )
}

/**
 * Excel 行父块徽章
 */
export function ExcelRowParentBadge({ chunk }: { chunk?: Chunk | null }) {
  if (!isExcelRowParentChunk(chunk)) return null

  return (
    <>
      <Badge
        variant='outline'
        className='h-5 shrink-0 border-slate-300 bg-slate-100 px-1.5 text-[10px] font-medium text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
      >
        行父块
      </Badge>
      <Badge
        variant='outline'
        className='h-5 shrink-0 border-slate-200 bg-slate-50 px-1.5 text-[10px] text-slate-500 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-400'
      >
        仅结构，不检索
      </Badge>
    </>
  )
}
