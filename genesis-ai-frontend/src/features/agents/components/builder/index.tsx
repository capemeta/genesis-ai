import { useCallback, type KeyboardEvent } from 'react'
import { ReactFlowProvider } from 'reactflow'
import 'reactflow/dist/style.css'
import { useBuilderLogic } from './core/hooks/use-builder-logic'
import { Toolbar } from './core/layout/toolbar'
import { LeftSidebar } from './core/layout/left-sidebar'
import { Canvas } from './core/layout/canvas'
import { RightSidebar } from './core/layout/right-sidebar'
import './builder.css'

export function AgentBuilder() {
  const logic = useBuilderLogic()
  const { 
    undo, 
    redo, 
    historyIndex, 
    historyLength, 
    searchTerm, 
    setSearchTerm, 
    addNodeToCenter,
    deleteSelectedNodes,
    duplicateSelectedNode,
    selectedNode,
    setSelectedNodeId
  } = logic

  // 键盘快捷键
  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Delete 删除
      if (event.key === 'Delete' || event.key === 'Backspace') {
        deleteSelectedNodes()
      }
      // Ctrl+Z 撤销
      if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
        event.preventDefault()
        undo()
      }
      // Ctrl+Y 或 Ctrl+Shift+Z 重做
      if (
        ((event.ctrlKey || event.metaKey) && event.key === 'y') ||
        ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key === 'z')
      ) {
        event.preventDefault()
        redo()
      }
      // Ctrl+D 复制
      if ((event.ctrlKey || event.metaKey) && event.key === 'd') {
        event.preventDefault()
        duplicateSelectedNode()
      }
    },
    [deleteSelectedNodes, undo, redo, duplicateSelectedNode]
  )

  return (
    <div 
      className='flex h-[calc(100vh-4rem)] flex-col bg-background'
      onKeyDown={onKeyDown as any}
      tabIndex={0}
    >
      <Toolbar 
        undo={undo} 
        redo={redo} 
        historyIndex={historyIndex} 
        historyLength={historyLength} 
      />
      
      <div className='flex flex-1 overflow-hidden'>
        <LeftSidebar 
          searchTerm={searchTerm} 
          setSearchTerm={setSearchTerm} 
          addNodeToCenter={addNodeToCenter} 
        />
        
        <Canvas {...logic} />
        
        {selectedNode && (
          <RightSidebar 
            selectedNode={selectedNode}
            setSelectedNodeId={setSelectedNodeId}
            duplicateSelectedNode={duplicateSelectedNode}
            deleteSelectedNodes={deleteSelectedNodes}
          />
        )}
      </div>
    </div>
  )
}

// 导出包装了 Provider 的组件
export default function AgentBuilderPage() {
  return (
    <ReactFlowProvider>
      <AgentBuilder />
    </ReactFlowProvider>
  )
}
