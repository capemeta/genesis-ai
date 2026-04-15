import { NodeProps, Position } from 'reactflow'
import { BaseNode } from './shared/base-node'
import { CustomHandle } from './shared/custom-handle'
import { NodeData } from '../types'

export const CustomNode = ({ data, selected }: NodeProps<NodeData>) => {
  return (
    <BaseNode data={data} selected={selected}>
      <CustomHandle type='target' position={Position.Left} />
      <CustomHandle type='source' position={Position.Right} />
    </BaseNode>
  )
}

export const nodeTypes = {
  custom: CustomNode,
}
