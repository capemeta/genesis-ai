import { useState, useCallback, useRef } from 'react'
import {
  Node,
  Edge,
  Connection,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  OnNodesDelete,
  OnEdgesDelete,
} from 'reactflow'
import { toast } from 'sonner'
import { INITIAL_NODES, INITIAL_EDGES } from '../../constants'
import { NodeData, ComponentItem, BuilderHistory } from '../../types'

export function useBuilderLogic() {
  const [nodes, setNodes, onNodesChange] = useNodesState(INITIAL_NODES)
  const [edges, setEdges, onEdgesChange] = useEdgesState(INITIAL_EDGES)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [history, setHistory] = useState<BuilderHistory[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  
  const { screenToFlowPosition, getNodes, getEdges, getViewport } = useReactFlow()
  const nodeIdCounter = useRef(5)

  // 保存历史记录
  const saveToHistory = useCallback(() => {
    const newHistory = history.slice(0, historyIndex + 1)
    newHistory.push({ nodes: getNodes(), edges: getEdges() })
    setHistory(newHistory)
    setHistoryIndex(newHistory.length - 1)
  }, [history, historyIndex, getNodes, getEdges])

  // 撤销
  const undo = useCallback(() => {
    if (historyIndex > 0) {
      const prevState = history[historyIndex - 1]
      setNodes(prevState.nodes)
      setEdges(prevState.edges)
      setHistoryIndex(historyIndex - 1)
      toast.success('已撤销')
    }
  }, [historyIndex, history, setNodes, setEdges])

  // 重做
  const redo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const nextState = history[historyIndex + 1]
      setNodes(nextState.nodes)
      setEdges(nextState.edges)
      setHistoryIndex(historyIndex + 1)
      toast.success('已重做')
    }
  }, [historyIndex, history, setNodes, setEdges])

  // 连接节点
  const onConnect = useCallback(
    (params: Connection) => {
      const newEdge = { 
        ...params, 
        animated: false, 
        style: { strokeWidth: 2.5, stroke: '#3b82f6' } 
      }
      setEdges((eds) => addEdge(newEdge, eds))
      saveToHistory()
      toast.success('节点已连接')
    },
    [setEdges, saveToHistory]
  )

  // 点击节点
  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNodeId(node.id)
  }, [])

  // 监听选中变化
  const onSelectionChange = useCallback((params: { nodes: Node[]; edges: Edge[] }) => {
    if (params.nodes.length === 1) {
      setSelectedNodeId(params.nodes[0].id)
    } else if (params.nodes.length === 0) {
      setSelectedNodeId(null)
    }
  }, [])

  // 点击画布空白处
  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null)
  }, [])

  // 添加节点到画布中心
  const addNodeToCenter = useCallback(
    (item: ComponentItem) => {
      const { x, y, zoom } = getViewport()
      const centerX = (window.innerWidth / 2 - x) / zoom
      const centerY = (window.innerHeight / 2 - y) / zoom
      
      const newNode: Node<NodeData> = {
        id: `node-${nodeIdCounter.current++}`,
        type: 'custom',
        position: {
          x: centerX - 140,
          y: centerY - 80,
        },
        data: {
          title: item.label,
          description: item.description,
          nodeType: item.type as any,
          color: item.color,
          iconName: item.iconName,
        },
      }

      setNodes((nds) => [...nds, newNode])
      setSelectedNodeId(newNode.id)
      saveToHistory()
      toast.success(`已添加 ${item.label}`)
    },
    [setNodes, saveToHistory, getViewport]
  )

  // 拖拽到画布
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const data = event.dataTransfer.getData('application/reactflow')
      if (data) {
        const item: ComponentItem = JSON.parse(data)
        const position = screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        })

        const newNode: Node<NodeData> = {
          id: `node-${nodeIdCounter.current++}`,
          type: 'custom',
          position,
          data: {
            title: item.label,
            description: item.description,
            nodeType: item.type as any,
            color: item.color,
            iconName: item.iconName,
          },
        }

        setNodes((nds) => [...nds, newNode])
        saveToHistory()
        toast.success(`已添加 ${item.label}`)
      }
    },
    [screenToFlowPosition, setNodes, saveToHistory]
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  // 删除选中的节点
  const deleteSelectedNodes = useCallback(() => {
    setNodes((nds) => {
      const selectedNodes = nds.filter(node => node.selected || node.id === selectedNodeId)
      if (selectedNodes.length === 0) return nds
      
      const selectedIds = selectedNodes.map(n => n.id)
      setEdges((eds) => eds.filter(edge => !selectedIds.includes(edge.source) && !selectedIds.includes(edge.target)))
      setSelectedNodeId(null)
      saveToHistory()
      toast.success('已删除节点')
      return nds.filter(node => !selectedIds.includes(node.id))
    })
  }, [selectedNodeId, setNodes, setEdges, saveToHistory])

  // 复制选中的节点
  const duplicateSelectedNode = useCallback(() => {
    if (selectedNodeId) {
      const nodeToCopy = getNodes().find(node => node.id === selectedNodeId)
      if (nodeToCopy) {
        const newNode: Node<NodeData> = {
          ...nodeToCopy,
          id: `node-${nodeIdCounter.current++}`,
          position: {
            x: nodeToCopy.position.x + 50,
            y: nodeToCopy.position.y + 50,
          },
          selected: false,
        }
        setNodes((nds) => [...nds, newNode])
        saveToHistory()
        toast.success('已复制节点')
      }
    }
  }, [selectedNodeId, getNodes, setNodes, saveToHistory])

  const onNodesDelete: OnNodesDelete = useCallback(() => {
    saveToHistory()
  }, [saveToHistory])

  const onEdgesDelete: OnEdgesDelete = useCallback(() => {
    saveToHistory()
  }, [saveToHistory])

  return {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onNodeClick,
    onSelectionChange,
    onPaneClick,
    onDrop,
    onDragOver,
    onNodesDelete,
    onEdgesDelete,
    selectedNodeId,
    setSelectedNodeId,
    searchTerm,
    setSearchTerm,
    undo,
    redo,
    historyIndex,
    historyLength: history.length,
    addNodeToCenter,
    deleteSelectedNodes,
    duplicateSelectedNode,
    selectedNode: nodes.find((n) => n.id === selectedNodeId)
  }
}
