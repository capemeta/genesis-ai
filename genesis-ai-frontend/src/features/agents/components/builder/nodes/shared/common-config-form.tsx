import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Node } from 'reactflow'
import { NodeData } from '../../types'

interface CommonConfigFormProps {
  node: Node<NodeData>
}

export const CommonConfigForm = ({ node }: CommonConfigFormProps) => {
  return (
    <div className='space-y-4 mb-6'>
      <div className='space-y-2'>
        <Label className='text-xs font-medium'>节点名称</Label>
        <Input 
          defaultValue={node.data.title} 
          className='h-9'
        />
      </div>
      <div className='space-y-2'>
        <Label className='text-xs font-medium'>描述</Label>
        <Textarea 
          defaultValue={node.data.description}
          className='min-h-[60px] text-xs resize-none'
        />
      </div>
    </div>
  )
}
