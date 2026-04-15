/**
 * 组织树形下拉选择器
 * 用于选择用户所属部门
 */
import { useState, useMemo, useCallback } from 'react'
import { Check, ChevronsUpDown, ChevronRight, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import type { OrganizationTreeNode } from '@/lib/api/organization'

interface OrganizationTreeSelectProps {
  value?: string | null
  onChange: (value: string | null) => void
  treeData: OrganizationTreeNode[]
  disabled?: boolean
  placeholder?: string
}

interface TreeNodeWithMeta extends OrganizationTreeNode {
  level: number
  parentId?: string
}

export function OrganizationTreeSelect({
  value,
  onChange,
  treeData,
  disabled = false,
  placeholder = '请选择部门',
}: OrganizationTreeSelectProps) {
  const [open, setOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())

  // 构建扁平化数据和父子关系映射
  const { flattenedData, childrenMap, nameMap, parentMap } = useMemo(() => {
    const flat: TreeNodeWithMeta[] = []
    const children = new Map<string, string[]>()
    const names = new Map<string, string>()
    const parents = new Map<string, string>()

    const flatten = (nodes: OrganizationTreeNode[], level = 0, parentId?: string) => {
      nodes.forEach((node) => {
        const nodeWithMeta: TreeNodeWithMeta = {
          ...node,
          level,
          parentId,
        }
        flat.push(nodeWithMeta)
        names.set(node.id, node.name)
        
        if (parentId) {
          parents.set(node.id, parentId)
          if (!children.has(parentId)) {
            children.set(parentId, [])
          }
          children.get(parentId)!.push(node.id)
        }

        if (node.children && node.children.length > 0) {
          flatten(node.children, level + 1, node.id)
        }
      })
    }

    flatten(treeData)
    return { flattenedData: flat, childrenMap: children, nameMap: names, parentMap: parents }
  }, [treeData])

  // 获取节点的所有父节点ID（递归）
  const getAllParentIds = useCallback((nodeId: string): Set<string> => {
    const result = new Set<string>()
    let current = nodeId
    
    while (parentMap.has(current)) {
      const parent = parentMap.get(current)!
      result.add(parent)
      current = parent
    }
    
    return result
  }, [parentMap])

  // 根据搜索关键词过滤数据
  const filteredData = useMemo(() => {
    if (!searchQuery.trim()) {
      return flattenedData
    }

    const query = searchQuery.toLowerCase().trim()
    const matchedIds = new Set<string>()
    const parentIdsToShow = new Set<string>()

    // 找到所有匹配的节点
    flattenedData.forEach((item) => {
      if (item.name.toLowerCase().includes(query)) {
        matchedIds.add(item.id)
        // 添加所有父节点
        getAllParentIds(item.id).forEach((parentId) => {
          parentIdsToShow.add(parentId)
        })
      }
    })

    // 自动展开搜索结果的所有父节点
    setExpandedNodes((prev) => {
      const newExpanded = new Set(prev)
      parentIdsToShow.forEach((id) => newExpanded.add(id))
      return newExpanded
    })

    // 返回匹配的节点和它们的父节点
    return flattenedData.filter((item) => matchedIds.has(item.id) || parentIdsToShow.has(item.id))
  }, [flattenedData, searchQuery, getAllParentIds])

  // 根据ID查找名称
  const getNameById = (id: string | null) => {
    if (!id) return placeholder
    return nameMap.get(id) || placeholder
  }

  // 生成缩进
  const getIndent = (level: number) => {
    return '　'.repeat(level)  // 使用全角空格
  }

  // 切换节点展开状态
  const toggleNodeExpand = (nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const newExpanded = new Set(expandedNodes)
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId)
    } else {
      newExpanded.add(nodeId)
    }
    setExpandedNodes(newExpanded)
  }

  // 判断节点是否应该显示
  const shouldShowNode = useCallback((node: TreeNodeWithMeta): boolean => {
    // 如果是根节点，总是显示
    if (!node.parentId) {
      return true
    }

    // 如果父节点展开了，显示
    if (expandedNodes.has(node.parentId)) {
      return true
    }

    return false
  }, [expandedNodes])

  // 判断节点是否有子节点
  const hasChildren = (nodeId: string): boolean => {
    return (childrenMap.get(nodeId) || []).length > 0
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
        >
          <span className="flex items-center gap-2">
            <span className="truncate">{getNameById(value || null)}</span>
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <Command 
          shouldFilter={false}
          loop={false}
        >
          <CommandInput 
            placeholder="搜索部门..." 
            value={searchQuery}
            onValueChange={setSearchQuery}
          />
          <CommandList 
            className="max-h-[300px] overflow-y-auto overscroll-contain [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-thumb]:rounded-full"
            style={{ 
              overflowY: 'auto',
              WebkitOverflowScrolling: 'touch',
              pointerEvents: 'auto',
              touchAction: 'auto'
            } as React.CSSProperties}
            onWheel={(e) => {
              e.stopPropagation()
            }}
          >
            <CommandEmpty>未找到部门</CommandEmpty>
            <CommandGroup>
              {filteredData.map((item) => {
                // 如果节点不应该显示，跳过
                if (!shouldShowNode(item)) {
                  return null
                }

                const nodeHasChildren = hasChildren(item.id)

                return (
                  <CommandItem
                    key={item.id}
                    value={`${item.name}-${item.id}`}
                    onSelect={() => {
                      onChange(item.id)
                      setOpen(false)
                      setSearchQuery('')
                    }}
                    className="flex items-center gap-1"
                  >
                    <Check
                      className={cn(
                        'mr-2 h-4 w-4',
                        value === item.id ? 'opacity-100' : 'opacity-0'
                      )}
                    />
                    <span>
                      {getIndent(item.level)}
                      {nodeHasChildren && (
                        <button
                          type="button"
                          onClick={(e) => toggleNodeExpand(item.id, e)}
                          className="inline-flex items-center justify-center w-4 h-4 mr-1 hover:bg-gray-100 rounded"
                        >
                          {expandedNodes.has(item.id) ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronRight className="h-3 w-3" />
                          )}
                        </button>
                      )}
                      {!nodeHasChildren && <span className="inline-block w-4" />}
                      {item.name}
                    </span>
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
