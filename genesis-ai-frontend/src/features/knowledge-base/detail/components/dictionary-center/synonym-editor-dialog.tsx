import { Loader2 } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

export interface SynonymEditorValue {
  professional_term: string
  variant_terms: string
  priority: number
  is_active: boolean
  is_global_scope: boolean
}

interface SynonymEditorDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  value: SynonymEditorValue
  onChange: (value: SynonymEditorValue) => void
  onSave: (value: SynonymEditorValue) => void
  loading: boolean
  isEdit: boolean
}

export function SynonymEditorDialog({
  open,
  onOpenChange,
  value,
  onChange,
  onSave,
  loading,
  isEdit,
}: SynonymEditorDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-2xl'>
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑同义词映射' : '新建同义词映射'}</DialogTitle>
          <DialogDescription>
            同义词用于在检索阶段进行语义对齐（口语变体词映射到标准术语）。
          </DialogDescription>
        </DialogHeader>

        <div className='grid gap-4 py-2'>
          <div className='space-y-2'>
            <Label htmlFor='synonym-professional-term'>标准术语 (Standard Term)</Label>
            <Input
              id='synonym-professional-term'
              value={value.professional_term}
              onChange={(event) => onChange({ ...value, professional_term: event.target.value })}
              placeholder='例如：大语言模型'
            />
          </div>

          <div className='space-y-2'>
            <Label htmlFor='synonym-variants'>口语词/变体 (Variant Terms)</Label>
            <Textarea
              id='synonym-variants'
              rows={5}
              value={value.variant_terms}
              onChange={(event) => onChange({ ...value, variant_terms: event.target.value })}
              placeholder='输入映射词，支持每行一条。&#10;LLM&#10;大模型&#10;大语言模型'
            />
            <p className='text-[10px] text-muted-foreground'>支持换行、逗号（中英文）分隔多条记录。</p>
          </div>

          <div className='space-y-2'>
            <Label htmlFor='synonym-priority'>优先级 (越小越优先)</Label>
            <Input
              id='synonym-priority'
              type='number'
              value={String(value.priority)}
              onChange={(event) => onChange({ ...value, priority: Number(event.target.value || 0) })}
            />
          </div>

          <div className='flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/20 px-4 py-3'>
            <div className='space-y-1'>
              <p className='text-sm font-medium'>作用域</p>
              <p className='text-[11px] text-muted-foreground'>关闭为当前知识库，开启为租户公共规则</p>
            </div>
            <div className='flex items-center gap-2'>
              <span className='text-xs text-muted-foreground'>本库</span>
              <Switch
                checked={value.is_global_scope}
                onCheckedChange={(checked) => onChange({ ...value, is_global_scope: checked })}
              />
              <span className='text-xs text-muted-foreground'>租户</span>
            </div>
          </div>

          <div className='flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/20 px-4 py-3'>
            <div className='space-y-1'>
              <p className='text-sm font-medium'>启用状态</p>
              <p className='text-[11px] text-muted-foreground'>停用后规则不生效</p>
            </div>
            <Switch
              checked={value.is_active}
              onCheckedChange={(checked) => onChange({ ...value, is_active: checked })}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant='outline' onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            onClick={() => onSave(value)}
            disabled={loading || !value.professional_term}
            className='bg-indigo-600 hover:bg-indigo-700 text-white'
          >
            {loading && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
            确定
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
