import { type Node, type Edge } from 'reactflow'
import { type NodeData, type ComponentItem } from '../types'

export const INITIAL_NODES: Node<NodeData>[] = [
  {
    id: '1',
    type: 'custom',
    position: { x: 150, y: 250 },
    data: {
      title: '用户查询',
      description: '接收用户输入的问题',
      nodeType: 'start',
      color: 'purple',
      iconName: 'MessageSquare',
    },
  },
  {
    id: '2',
    type: 'custom',
    position: { x: 550, y: 250 },
    data: {
      title: '知识库检索',
      description: 'Knowledge Base v2 • Top K: 5',
      nodeType: 'knowledge',
      color: 'amber',
      iconName: 'BookOpen',
    },
  },
  {
    id: '3',
    type: 'custom',
    position: { x: 950, y: 250 },
    data: {
      title: 'AI 推理引擎',
      description: 'GPT-4o • Temperature: 0.7',
      nodeType: 'llm',
      color: 'blue',
      iconName: 'Brain',
    },
  },
  {
    id: '4',
    type: 'custom',
    position: { x: 1350, y: 250 },
    data: {
      title: '最终响应',
      description: '返回生成的答案给用户',
      nodeType: 'output',
      color: 'green',
      iconName: 'Send',
    },
  },
]

export const INITIAL_EDGES: Edge[] = [
  {
    id: 'e1-2',
    source: '1',
    target: '2',
    animated: false,
    style: { strokeWidth: 2.5, stroke: '#3b82f6' },
  },
  {
    id: 'e2-3',
    source: '2',
    target: '3',
    animated: false,
    style: { strokeWidth: 2.5, stroke: '#3b82f6' },
  },
  {
    id: 'e3-4',
    source: '3',
    target: '4',
    animated: true,
    style: { strokeWidth: 2.5, stroke: '#3b82f6' },
  },
]

export const COMPONENT_PALETTE: { category: string; items: ComponentItem[] }[] = [
  {
    category: '输入触发器',
    items: [
      { iconName: 'MessageSquare', label: '用户查询', color: 'purple', type: 'start', description: '接收用户输入' },
      { iconName: 'Webhook', label: 'Webhook', color: 'purple', type: 'start', description: 'API 触发器' },
    ],
  },
  {
    category: '知识库',
    items: [
      { iconName: 'BookOpen', label: '知识库检索', color: 'amber', type: 'knowledge', description: '从知识库查询相关内容' },
      { iconName: 'FileSearch', label: '文档检索', color: 'amber', type: 'knowledge', description: '搜索文档内容' },
    ],
  },
  {
    category: 'AI & 逻辑',
    items: [
      { iconName: 'Brain', label: 'LLM 节点', color: 'blue', type: 'llm', description: '调用大语言模型' },
      { iconName: 'GitBranch', label: '条件分支', color: 'blue', type: 'condition', description: '根据条件分流' },
      { iconName: 'Wrench', label: '工具调用', color: 'blue', type: 'tool', description: '执行外部工具' },
    ],
  },
  {
    category: '输出',
    items: [
      { iconName: 'Send', label: '文本响应', color: 'green', type: 'output', description: '返回文本结果' },
    ],
  },
]
