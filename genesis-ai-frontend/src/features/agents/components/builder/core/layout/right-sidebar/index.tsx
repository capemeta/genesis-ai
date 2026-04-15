import {
  Settings,
  Copy,
  Trash2,
  X,
  Save,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Node } from 'reactflow'
import { NodeData } from '../../../types'
import { CommonConfigForm } from '../../../nodes/shared/common-config-form'
import { LLMConfigForm } from '../../../nodes/llm-node/config-form'
import { KnowledgeConfigForm } from '../../../nodes/knowledge-node/config-form'

interface RightSidebarProps {
  selectedNode: Node<NodeData> | undefined
  setSelectedNodeId: (id: string | null) => void
  duplicateSelectedNode: () => void
  deleteSelectedNodes: () => void
}

export const RightSidebar = ({
  selectedNode,
  setSelectedNodeId,
  duplicateSelectedNode,
  deleteSelectedNodes,
}: RightSidebarProps) => {
  if (!selectedNode) return null

  const renderConfigForm = () => {
    switch (selectedNode.data.nodeType) {
      case 'llm':
        return <LLMConfigForm node={selectedNode} />
      case 'knowledge':
        return <KnowledgeConfigForm node={selectedNode} />
      default:
        return null
    }
  }

  return (
    <aside className='w-80 border-l bg-card flex flex-col shadow-xl animate-in slide-in-from-right duration-200'>
      <div className='p-4 border-b flex items-center justify-between bg-muted/20'>
        <div className='flex items-center gap-2'>
          <div className='h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center'>
            <Settings className='h-4 w-4 text-primary' />
          </div>
          <div>
            <h2 className='font-semibold text-sm'>{selectedNode.data.title}</h2>
            <p className='text-[10px] text-muted-foreground uppercase tracking-tight'>
              {selectedNode.data.nodeType}
            </p>
          </div>
        </div>
        <div className='flex items-center gap-1'>
          <Button
            variant='ghost'
            size='icon'
            className='h-8 w-8 text-muted-foreground hover:text-foreground'
            onClick={duplicateSelectedNode}
            title='复制 (Ctrl+D)'
          >
            <Copy className='h-4 w-4' />
          </Button>
          <Button
            variant='ghost'
            size='icon'
            className='h-8 w-8 text-muted-foreground hover:text-destructive'
            onClick={deleteSelectedNodes}
            title='删除 (Del)'
          >
            <Trash2 className='h-4 w-4' />
          </Button>
          <Separator orientation='vertical' className='h-4 mx-1' />
          <Button
            variant='ghost'
            size='icon'
            className='h-8 w-8'
            onClick={() => setSelectedNodeId(null)}
          >
            <X className='h-4 w-4' />
          </Button>
        </div>
      </div>

      <ScrollArea className='flex-1 p-4'>
        <CommonConfigForm node={selectedNode} />
        <Separator className='my-4' />
        {renderConfigForm()}
      </ScrollArea>

      <div className='p-4 border-t bg-muted/30'>
        <div className='flex gap-2'>
          <Button 
            variant='outline' 
            className='flex-1 h-9'
            onClick={() => setSelectedNodeId(null)}
          >
            取消
          </Button>
          <Button className='flex-1 h-9 gap-1.5'>
            <Save className='h-3.5 w-3.5' />
            保存配置
          </Button>
        </div>
      </div>
    </aside>
  )
}
