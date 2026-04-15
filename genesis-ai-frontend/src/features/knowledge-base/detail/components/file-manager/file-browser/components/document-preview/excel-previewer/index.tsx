/**
 * Excel 文件预览器
 *
 * 使用 SheetJS (xlsx) 在客户端解析 .xlsx / .xls / .csv 文件，
 * 渲染为带多 Sheet Tab 切换的只读表格视图。
 *
 * 特性：
 * - 多 Sheet Tab 切换
 * - 固定表头（第一行），滚动内容区
 * - 超宽表格横向滚动
 * - 显示行号 / 列数 / 数据行数
 * - 空单元格用灰色占位，合并单元格保留宽度
 */
import { useState, useEffect, useMemo } from 'react'
import * as XLSX from 'xlsx'
import { Loader2, AlertCircle, TableProperties } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface SheetData {
  name: string
  headers: string[]
  rows: string[][]
  rowCount: number
  colCount: number
}

interface ExcelPreviewerProps {
  blob: Blob
  fileName?: string
  className?: string
}

/**
 * 将 CSV 原始字节解码为字符串（解决国内常见 GBK/GB18030 与 UTF-8 混用导致的乱码）
 *
 * 顺序：UTF-8 / UTF-16 BOM → UTF-8（fatal）→ GB18030（Chromium/Edge 等支持）→ UTF-8 宽松兜底
 */
function decodeCsvBytes(bytes: Uint8Array): string {
  if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    return new TextDecoder('utf-8').decode(bytes.subarray(3))
  }
  if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) {
    return new TextDecoder('utf-16le').decode(bytes.subarray(2))
  }
  if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
    return new TextDecoder('utf-16be').decode(bytes.subarray(2))
  }
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    try {
      return new TextDecoder('gb18030').decode(bytes)
    } catch {
      return new TextDecoder('utf-8', { fatal: false }).decode(bytes)
    }
  }
}

/** 将 SheetJS worksheet 转换为结构化的 SheetData */
function parseSheet(ws: XLSX.WorkSheet, sheetName: string): SheetData {
  const range = XLSX.utils.decode_range(ws['!ref'] || 'A1')
  const rowCount = range.e.r - range.s.r + 1
  const colCount = range.e.c - range.s.c + 1

  // 转成二维字符串数组（含表头行）
  const rawRows: string[][] = XLSX.utils.sheet_to_json<string[]>(ws, {
    header: 1,
    defval: '',
    raw: false,
  })

  const headers = (rawRows[0] ?? []).map((v) => String(v ?? ''))
  const rows = rawRows.slice(1).map((row) => {
    // 补齐列数（保证每行列数与表头对齐）
    const padded = [...row]
    while (padded.length < headers.length) padded.push('')
    return padded.map((v) => String(v ?? ''))
  })

  return { name: sheetName, headers, rows, rowCount, colCount }
}

export function ExcelPreviewer({ blob, fileName, className }: ExcelPreviewerProps) {
  const [sheets, setSheets] = useState<SheetData[]>([])
  const [activeSheet, setActiveSheet] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)

    blob
      .arrayBuffer()
      .then((buf) => {
        if (cancelled) return
        const ext = fileName?.split('.').pop()?.toLowerCase() ?? ''
        const isCsv = ext === 'csv'
        const wb = isCsv
          ? XLSX.read(decodeCsvBytes(new Uint8Array(buf)), {
              type: 'string',
              cellDates: true,
              dense: false,
            })
          : XLSX.read(buf, { type: 'array', cellDates: true, dense: false })
        const parsed = wb.SheetNames.map((name) =>
          parseSheet(wb.Sheets[name], name)
        )
        setSheets(parsed)
        setActiveSheet(0)
      })
      .catch((e: Error) => {
        if (cancelled) return
        setError(e.message || '解析 Excel 文件失败')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [blob, fileName])

  const current = useMemo(() => sheets[activeSheet], [sheets, activeSheet])

  if (isLoading) {
    return (
      <div className={cn('flex h-full items-center justify-center', className)}>
        <div className='flex flex-col items-center gap-3'>
          <Loader2 className='h-8 w-8 animate-spin text-primary/50' />
          <p className='text-xs text-muted-foreground animate-pulse'>正在解析 Excel 文件…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn('flex h-full flex-col items-center justify-center gap-3 p-8', className)}>
        <AlertCircle className='h-10 w-10 text-destructive/50' />
        <p className='text-sm text-muted-foreground'>解析失败</p>
        <p className='text-[10px] text-muted-foreground/60 break-all text-center max-w-[240px]'>
          {error}
        </p>
      </div>
    )
  }

  if (!current) {
    return (
      <div className={cn('flex h-full items-center justify-center', className)}>
        <p className='text-xs text-muted-foreground'>文件为空</p>
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col h-full overflow-hidden bg-white dark:bg-slate-950', className)}>
      {/* Sheet Tab 栏 */}
      <div className='shrink-0 flex items-center gap-1 px-3 py-1.5 border-b bg-slate-50 dark:bg-slate-900 overflow-x-auto scrollbar-thin'>
        <TableProperties className='h-3.5 w-3.5 text-emerald-500 shrink-0 mr-1' />
        {sheets.map((sheet, idx) => (
          <button
            key={sheet.name}
            onClick={() => setActiveSheet(idx)}
            className={cn(
              'shrink-0 rounded-md px-2.5 py-0.5 text-xs font-medium transition-all',
              idx === activeSheet
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 shadow-sm'
                : 'text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700 dark:text-slate-400'
            )}
          >
            {sheet.name}
          </button>
        ))}
        {/* 当前 Sheet 统计 */}
        <div className='ml-auto shrink-0 flex items-center gap-1.5 pl-2'>
          <Badge variant='outline' className='text-[9px] py-0 px-1.5 h-4 bg-white dark:bg-slate-900'>
            {current.rowCount} 行
          </Badge>
          <Badge variant='outline' className='text-[9px] py-0 px-1.5 h-4 bg-white dark:bg-slate-900'>
            {current.colCount} 列
          </Badge>
        </div>
      </div>

      {/* 表格区域 */}
      <div className='flex-1 overflow-auto'>
        <table className='min-w-full text-xs border-collapse'>
          {/* 固定表头 */}
          <thead className='sticky top-0 z-10'>
            <tr className='bg-slate-100 dark:bg-slate-800'>
              {/* 行号占位列 */}
              <th className='w-8 min-w-8 border border-slate-200 dark:border-slate-700 px-1 py-1 text-center text-[10px] text-slate-400 font-normal select-none bg-slate-50 dark:bg-slate-900'>
                #
              </th>
              {current.headers.map((h, ci) => (
                <th
                  key={ci}
                  className='border border-slate-200 dark:border-slate-700 px-2 py-1 text-left font-semibold text-slate-700 dark:text-slate-200 whitespace-nowrap max-w-[200px] truncate'
                  title={h}
                >
                  {h || <span className='text-slate-300 dark:text-slate-600 italic'>{_colLetter(ci)}</span>}
                </th>
              ))}
            </tr>
          </thead>

          {/* 数据行 */}
          <tbody>
            {current.rows.length === 0 ? (
              <tr>
                <td
                  colSpan={current.headers.length + 1}
                  className='py-8 text-center text-xs text-muted-foreground'
                >
                  此工作表无数据行
                </td>
              </tr>
            ) : (
              current.rows.map((row, ri) => (
                <tr
                  key={ri}
                  className={cn(
                    'transition-colors',
                    ri % 2 === 0
                      ? 'bg-white dark:bg-slate-950'
                      : 'bg-slate-50/60 dark:bg-slate-900/60',
                    'hover:bg-blue-50/40 dark:hover:bg-blue-950/20'
                  )}
                >
                  {/* 行号 */}
                  <td className='w-8 border border-slate-200 dark:border-slate-700 px-1 py-0.5 text-center text-[10px] text-slate-400 select-none bg-slate-50/80 dark:bg-slate-900/80'>
                    {ri + 2}
                  </td>
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className='border border-slate-200 dark:border-slate-700 px-2 py-0.5 text-slate-700 dark:text-slate-300 whitespace-nowrap max-w-[240px] truncate'
                      title={cell}
                    >
                      {cell === '' ? (
                        <span className='text-slate-300 dark:text-slate-700'>—</span>
                      ) : (
                        cell
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** 将列索引转换为 Excel 列字母（0→A, 1→B, 26→AA …） */
function _colLetter(idx: number): string {
  let result = ''
  let n = idx + 1
  while (n > 0) {
    const rem = (n - 1) % 26
    result = String.fromCharCode(65 + rem) + result
    n = Math.floor((n - 1) / 26)
  }
  return result
}
