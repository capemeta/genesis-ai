import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Node } from 'reactflow'
import { NodeData } from '../../types'

interface KnowledgeConfigFormProps {
  node: Node<NodeData>
}

export const KnowledgeConfigForm = ({ node }: KnowledgeConfigFormProps) => {
  void node
  return (
    <div className='space-y-4'>
      <div className='space-y-2'>
        <Label className='text-xs font-medium'>知识库</Label>
        <Select defaultValue='kb1'>
          <SelectTrigger className='h-9'>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='kb1'>Knowledge Base v2</SelectItem>
            <SelectItem value='kb2'>Product Documentation</SelectItem>
            <SelectItem value='kb3'>Support FAQs</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className='space-y-2'>
        <Label className='text-xs font-medium'>Top K (返回结果数)</Label>
        <Input type='number' defaultValue='5' min='1' max='20' className='h-9' />
      </div>

      <div className='space-y-2'>
        <Label className='text-xs font-medium'>相似度阈值</Label>
        <div className='flex items-center gap-2'>
          <input
            type='range'
            min='0'
            max='1'
            step='0.05'
            defaultValue='0.7'
            className='flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary'
          />
          <span className='text-xs font-medium w-12 text-right'>0.70</span>
        </div>
      </div>
    </div>
  )
}
