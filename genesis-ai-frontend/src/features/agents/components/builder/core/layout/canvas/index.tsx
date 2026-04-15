import React, { useRef } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Panel,
  BackgroundVariant,
  Node,
  Edge,
  OnNodesChange,
  OnEdgesChange,
  Connection,
  NodeMouseHandler,
  OnNodesDelete,
  OnEdgesDelete,
} from 'reactflow'
import { Brain, GripVertical } from 'lucide-react'
import { nodeTypes } from '../../../nodes'
import { Badge } from '@/components/ui/badge'

interface CanvasProps {
  nodes: Node[]
  edges: Edge[]
  onNodesChange: OnNodesChange
  onEdgesChange: OnEdgesChange
  onConnect: (connection: Connection) => void
  onNodeClick: NodeMouseHandler
  onPaneClick: () => void
  onSelectionChange: (params: { nodes: Node[]; edges: Edge[] }) => void
  onNodesDelete: OnNodesDelete
  onEdgesDelete: OnEdgesDelete
  onDrop: (event: React.DragEvent) => void
  onDragOver: (event: React.DragEvent) => void
}

export const Canvas = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
  onPaneClick,
  onSelectionChange,
  onNodesDelete,
  onEdgesDelete,
  onDrop,
  onDragOver,
}: CanvasProps) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  return (
    <section className='flex-1 relative' ref={reactFlowWrapper}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onSelectionChange={onSelectionChange}
        onNodesDelete={onNodesDelete}
        onEdgesDelete={onEdgesDelete}
        onDrop={onDrop}
        onDragOver={onDragOver}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={{
          animated: false,
          style: { strokeWidth: 2.5, stroke: '#3b82f6' },
        }}
        elevateEdgesOnSelect
        fitView
        className='bg-muted/20'
        deleteKeyCode={['Delete', 'Backspace']}
        multiSelectionKeyCode='Shift'
        selectionKeyCode='Shift'
        panOnScroll
        panOnDrag
        zoomOnDoubleClick={false}
        attributionPosition='bottom-right'
      >
        <Background 
          variant={BackgroundVariant.Dots} 
          gap={20} 
          size={1}
          className='bg-background'
        />
        
        <Controls
          showInteractive={false}
          className='!left-4 !bottom-4 !shadow-lg !border-border'
        />
        
        <MiniMap
          nodeStrokeWidth={3}
          className='!right-4 !bottom-4 !bg-card !border-2 !border-border !rounded-xl !shadow-lg'
          pannable
          zoomable
        />
        
        {/* 顶部信息面板 */}
        <Panel position='top-left' className='ml-4 mt-4'>
          <div className='flex gap-2'>
            <div className='flex items-center text-xs bg-card px-3 py-1.5 rounded-lg border shadow-sm font-semibold'>
              <div className='w-2 h-2 rounded-full bg-blue-500 mr-2' />
              节点: {nodes.length}
            </div>
            <div className='flex items-center text-xs bg-card px-3 py-1.5 rounded-lg border shadow-sm font-semibold'>
              <div className='w-2 h-2 rounded-full bg-amber-500 mr-2' />
              连接: {edges.length}
            </div>
          </div>
        </Panel>

        {/* 空状态提示 */}
        {nodes.length === 0 && (
          <Panel position='top-center' className='mt-20'>
            <div className='bg-card border-2 border-dashed rounded-xl p-8 text-center max-w-md'>
              <div className='flex justify-center mb-4'>
                <div className='h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center'>
                  <Brain className='h-8 w-8 text-primary' />
                </div>
              </div>
              <h3 className='font-semibold text-lg mb-2'>开始构建工作流</h3>
              <p className='text-sm text-muted-foreground mb-4'>
                从左侧面板选择组件，构建你的 AI Agent 工作流
              </p>
              <div className='flex flex-col gap-2 text-xs text-muted-foreground'>
                <div className='flex items-center justify-center gap-2'>
                  <GripVertical className='h-4 w-4' />
                  <span>拖拽组件到画布</span>
                </div>
                <div className='flex items-center justify-center gap-2'>
                  <Badge variant='outline' className='text-[10px] h-4 px-1.5'>2x</Badge>
                  <span>双击添加到中心</span>
                </div>
              </div>
            </div>
          </Panel>
        )}
      </ReactFlow>
    </section>
  )
}
