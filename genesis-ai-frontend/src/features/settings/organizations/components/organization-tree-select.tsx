/**
 * 组织树形下拉选择器
 * 用于选择上级部门
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
import type { OrganizationTreeNode } from '@/lib/api/organization'

interface OrganizationTreeSelectProps {
  value?: string | null
  onChange: (value: string | null) => void
  treeData: OrganizationTreeNode[]
  disabled?: boolean
  excludeIds?: string[]  // 排除的节点ID（编辑时排除自己和子部门）
}

export function OrganizationTreeSelect({
  value,
  onChange,
  treeData,
  disabled = false,
  excludeIds = [],
}: OrganizationTreeSelectProps) {
  const [open, setOpen] = useState(false)

  // 扁平化树形数据（用于搜索和显示）
  const flattenedData = useMemo(() => {
    const result: Array<{
      id: string
      name: string
      level: number
      disabled: boolean
    }> = []

    const flatten = (nodes: OrganizationTreeNode[], level = 0) => {
      nodes.forEach((node) => {
        result.push({
          id: node.id,
          name: node.name,
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

  // 根据ID查找名称
  const getNameById = (id: string | null) => {
    if (!id) return '无上级部门（根部门）'
    const item = flattenedData.find((item) => item.id === id)
    return item ? item.name : '未知部门'
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
            {/* <Building2 className="h-4 w-4 text-muted-foreground" /> */}
            <span className="truncate">{getNameById(value || null)}</span>
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <Command>
          <CommandInput placeholder="搜索部门..." />
          <CommandList
            className="max-h-[300px] overflow-y-auto overscroll-contain [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-thumb]:rounded-full"
            style={{
              overflowY: 'auto',
              WebkitOverflowScrolling: 'touch',
              pointerEvents: 'auto',
              touchAction: 'auto',
            } as React.CSSProperties}
            onWheel={(e) => {
              e.stopPropagation()
            }}
          >
            <CommandEmpty>未找到部门</CommandEmpty>
            <CommandGroup>
              {/* 根部门选项 */}
              <CommandItem
                value="__root__"
                onSelect={() => {
                  onChange(null)
                  setOpen(false)
                }}
              >
                <Check
                  className={cn(
                    'mr-2 h-4 w-4',
                    value === null ? 'opacity-100' : 'opacity-0'
                  )}
                />
                {/* <Building2 className="mr-2 h-4 w-4 text-muted-foreground" /> */}
                无上级部门（根部门）
              </CommandItem>

              {/* 树形列表 */}
              {flattenedData.map((item) => (
                <CommandItem
                  key={item.id}
                  value={`${item.name}-${item.id}`}
                  onSelect={() => {
                    if (!item.disabled) {
                      onChange(item.id)
                      setOpen(false)
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
                  {/* <Building2 className="mr-2 h-4 w-4 text-muted-foreground" /> */}
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
