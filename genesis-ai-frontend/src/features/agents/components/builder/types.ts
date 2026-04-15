import { Node, Edge } from 'reactflow'

export interface NodeData {
  title: string
  description?: string
  nodeType: 'start' | 'knowledge' | 'llm' | 'output' | 'condition' | 'tool'
  color: string
  iconName: string
  config?: any
}

export type ComponentItem = {
  iconName: string
  label: string
  color: string
  type: string
  description: string
}

export interface BuilderHistory {
  nodes: Node[]
  edges: Edge[]
}
