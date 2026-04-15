/**
 * 权限树形下拉选择器
 * 用于选择上级权限
 */
import { useState, useMemo } from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'
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
import type { PermissionListItem } from '@/lib/api/permission'

interface PermissionTreeNode extends PermissionListItem {
  children?: PermissionTreeNode[]
}

interface PermissionTreeSelectProps {
  value?: string | null
  onChange: (value: string | null) => void
  treeData: PermissionTreeNode[]
  disabled?: boolean
  placeholder?: string
  excludeIds?: string[]  // 排除的节点ID（编辑时排除自己和子权限）
}

export function PermissionTreeSelect({
  value,
  onChange,
  treeData,
  disabled = false,
  excludeIds = [],
}: PermissionTreeSelectProps) {
  const [open, setOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // 扁平化树形数据（用于搜索和显示）
  const flattenedData = useMemo(() => {
    const result: Array<{
      id: string
      name: string
      type: 'menu' | 'function' | 'directory'
      level: number
      disabled: boolean
    }> = []

    const flatten = (nodes: PermissionTreeNode[], level = 0) => {
      nodes.forEach((node) => {
        result.push({
          id: node.id,
          name: node.name,
          type: node.type,
          level,
          disabled: excludeIds.includes(node.id),
        })
        if (node.children && node.children.length > 0) {
          flatten(node.children, level + 1)
        }
      })
    }

    flatten(treeData)
    return result
  }, [treeData, excludeIds])

  // 根据搜索关键词过滤数据
  const filteredData = useMemo(() => {
    if (!searchQuery.trim()) {
      return flattenedData
    }

    const query = searchQuery.toLowerCase().trim()
    return flattenedData.filter((item) =>
      item.name.toLowerCase().includes(query)
    )
  }, [flattenedData, searchQuery])

  // 根据ID查找名称
  const getNameById = (id: string | null) => {
    if (!id) return '无（顶级权限）'
    const item = flattenedData.find((item) => item.id === id)
    return item ? item.name : '未知权限'
  }

  // 生成缩进
  const getIndent = (level: number) => {
    return '　'.repeat(level)  // 使用全角空格
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
          // 禁用 cmdk 的键盘导航，避免拦截滚轮事件
          loop={false}
        >
          <CommandInput 
            placeholder="搜索权限..." 
            value={searchQuery}
            onValueChange={setSearchQuery}
          />
          <CommandList 
            className="max-h-[300px] overflow-y-auto overscroll-contain [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-thumb]:rounded-full"
            style={{ 
              // 只在需要时显示滚动条
              overflowY: 'auto',
              WebkitOverflowScrolling: 'touch',
              // 确保可以接收滚轮事件
              pointerEvents: 'auto',
              // 禁用 touch-action 限制
              touchAction: 'auto'
            } as React.CSSProperties}
            onWheel={(e) => {
              // 阻止事件冒泡到 Command 组件
              e.stopPropagation()
            }}
          >
            <CommandEmpty>未找到权限</CommandEmpty>
            <CommandGroup>
              {/* 顶级权限选项 */}
              {!searchQuery && (
                <CommandItem
                  value="__root__"
                  onSelect={() => {
                    onChange(null)
                    setOpen(false)
                    setSearchQuery('')
                  }}
                >
                  <Check
                    className={cn(
                      'mr-2 h-4 w-4',
                      value === null ? 'opacity-100' : 'opacity-0'
                    )}
                  />
                  无（顶级权限）
                </CommandItem>
              )}

              {/* 树形列表 */}
              {filteredData.map((item) => (
                <CommandItem
                  key={item.id}
                  value={`${item.name}-${item.id}`}
                  onSelect={() => {
                    if (!item.disabled) {
                      onChange(item.id)
                      setOpen(false)
                      setSearchQuery('')
                    }
                  }}
                  disabled={item.disabled}
                  className={cn(item.disabled && 'opacity-50 cursor-not-allowed')}
                >
                  <Check
                    className={cn(
                      'mr-2 h-4 w-4',
                      value === item.id ? 'opacity-100' : 'opacity-0'
                    )}
                  />
                  <span>
                    {getIndent(item.level)}
                    {item.name}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
