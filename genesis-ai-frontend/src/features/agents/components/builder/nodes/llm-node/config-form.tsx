import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Search } from 'lucide-react'
import { Node } from 'reactflow'
import { NodeData } from '../../types'

interface LLMConfigFormProps {
  node: Node<NodeData>
}

export const LLMConfigForm = ({ node }: LLMConfigFormProps) => {
  void node
  return (
    <div className='space-y-4'>
      <div className='space-y-2'>
        <Label className='text-xs font-medium'>模型提供商</Label>
        <Select defaultValue='gpt4o'>
          <SelectTrigger className='h-9'>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='gpt4o'>OpenAI GPT-4o</SelectItem>
            <SelectItem value='claude'>Anthropic Claude 3.5 Sonnet</SelectItem>
            <SelectItem value='mistral'>Mistral Large</SelectItem>
            <SelectItem value='llama'>Llama 3 70B</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className='space-y-3'>
        <Label className='text-xs font-medium'>模型参数</Label>
        <div className='space-y-3'>
          <div className='space-y-2'>
            <div className='flex justify-between text-xs'>
              <span className='text-muted-foreground'>Temperature</span>
              <span className='font-medium'>0.7</span>
            </div>
            <input
              type='range'
              min='0'
              max='1'
              step='0.1'
              defaultValue='0.7'
              className='w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary'
            />
          </div>
          <div className='space-y-2'>
            <div className='flex justify-between text-xs'>
              <span className='text-muted-foreground'>Max Tokens</span>
              <span className='font-medium'>2048</span>
            </div>
            <input
              type='range'
              min='100'
              max='4000'
              step='100'
              defaultValue='2048'
              className='w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary'
            />
          </div>
        </div>
      </div>

      <div className='space-y-2'>
        <Label className='text-xs font-medium'>System Prompt</Label>
        <Textarea
          defaultValue={`You are a helpful and knowledgeable customer support agent.

Context: {{context}}
User Query: {{user_query}}

Provide concise and professional answers.`}
          className='min-h-[120px] font-mono text-xs resize-none'
        />
        <div className='flex gap-1 flex-wrap'>
          <Badge variant='secondary' className='text-[10px] font-mono'>
            {'{{context}}'}
          </Badge>
          <Badge variant='secondary' className='text-[10px] font-mono'>
            {'{{user_query}}'}
          </Badge>
        </div>
      </div>

      <div>
        <div className='flex items-center justify-between mb-2'>
          <Label className='text-xs font-medium'>可用工具</Label>
          <Button variant='link' size='sm' className='h-auto p-0 text-xs'>
            添加工具
          </Button>
        </div>
        <div className='space-y-2'>
          <div className='flex items-center justify-between p-2 rounded-lg bg-muted/50 border'>
            <div className='flex items-center gap-2 text-xs'>
              <Search className='h-3 w-3' />
              <span>web_search</span>
            </div>
            <Switch defaultChecked />
          </div>
        </div>
      </div>
    </div>
  )
}
