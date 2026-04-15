import { Loader2 } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import type { GlossaryItem } from './api'

export interface GlossaryEditorValue {
  term: string
  definition: string
  examples: string
  is_active: boolean
  is_global_scope: boolean
}

interface GlossaryEditorDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  value: GlossaryEditorValue
  onChange: (value: GlossaryEditorValue) => void
  onSubmit: () => void
  loading: boolean
  editingItem?: GlossaryItem | null
}

export function GlossaryEditorDialog({
  open,
  onOpenChange,
  value,
  onChange,
  onSubmit,
  loading,
  editingItem,
}: GlossaryEditorDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-2xl'>
        <DialogHeader>
          <DialogTitle>{editingItem ? '编辑术语' : '新建术语'}</DialogTitle>
          <DialogDescription>术语名称会进入检索分词词典，并用于生成阶段上下文增强；它不参与同义词翻译。</DialogDescription>
        </DialogHeader>
        <div className='grid gap-4 py-2'>
          <div className='space-y-2'>
            <Label htmlFor='glossary-term'>术语名称</Label>
            <Input
              id='glossary-term'
              value={value.term}
              onChange={(event) => onChange({ ...value, term: event.target.value })}
              placeholder='例如：大语言模型'
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='glossary-definition'>术语定义</Label>
            <Textarea
              id='glossary-definition'
              rows={5}
              value={value.definition}
              onChange={(event) => onChange({ ...value, definition: event.target.value })}
              placeholder='描述该术语在当前业务中的准确含义'
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='glossary-examples'>示例（可选）</Label>
            <Textarea
              id='glossary-examples'
              rows={3}
              value={value.examples}
              onChange={(event) => onChange({ ...value, examples: event.target.value })}
              placeholder='可填写场景示例，帮助模型更稳定使用术语'
            />
          </div>
          <div className='flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/20 px-4 py-3'>
            <div className='space-y-1'>
              <p className='text-sm font-medium'>作用域</p>
              <p className='text-xs text-muted-foreground'>关闭为当前知识库，开启为租户公共规则</p>
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
              <p className='text-xs text-muted-foreground'>停用后不会进入检索分词词典，也不会参与术语增强注入</p>
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
          <Button onClick={onSubmit} disabled={loading}>
            {loading && <Loader2 className='mr-2 h-4 w-4 animate-spin' />}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
