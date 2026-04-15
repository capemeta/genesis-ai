import { useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

interface VariantBatchDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  initialTerms: string[]
  loading: boolean
  onSubmit: (terms: string[], duplicateCount: number) => void
}

function normalizeLines(raw: string): string[] {
  const lines = raw
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
  return Array.from(new Set(lines))
}

export function VariantBatchDialog({
  open,
  onOpenChange,
  title,
  initialTerms,
  loading,
  onSubmit,
}: VariantBatchDialogProps) {
  const [rawValue, setRawValue] = useState('')

  const normalized = useMemo(() => normalizeLines(rawValue), [rawValue])
  const nonEmptyLineCount = useMemo(
    () => rawValue.split('\n').map((item) => item.trim()).filter(Boolean).length,
    [rawValue]
  )
  const duplicateCount = Math.max(0, nonEmptyLineCount - normalized.length)

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setRawValue(initialTerms.join('\n'))
    }
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className='sm:max-w-xl'>
        <DialogHeader>
          <DialogTitle>批量维护口语词</DialogTitle>
          <DialogDescription>目标标准词：{title}。每行一个口语词，保存后将按替换模式同步。</DialogDescription>
        </DialogHeader>
        <div className='space-y-3 py-2'>
          <div className='space-y-2'>
            <Label htmlFor='variant-lines'>口语词列表</Label>
            <Textarea
              id='variant-lines'
              rows={12}
              value={rawValue}
              onChange={(event) => setRawValue(event.target.value)}
              placeholder={'例如：\nAI 大模型\nLLM\n大模型系统'}
            />
          </div>
          <p className='text-xs text-muted-foreground'>去重后共 {normalized.length} 条口语词。</p>
          {duplicateCount > 0 ? (
            <p className='text-xs text-amber-600'>检测到 {duplicateCount} 条重复输入，保存时会自动去重。</p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant='outline' onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            onClick={() => onSubmit(normalized, duplicateCount)}
            disabled={loading}
          >
            {loading && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
            保存并替换
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
