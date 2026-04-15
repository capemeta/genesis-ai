/**
 * 权限搜索栏组件
 */
import { useState } from 'react'
import { Search, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface PermissionSearchBarProps {
  onSearch: (params: {
    search?: string
    type?: string
    status?: string
  }) => void
}

export function PermissionSearchBar({ onSearch }: PermissionSearchBarProps) {
  const [search, setSearch] = useState('')
  const [type, setType] = useState<string>('all')
  const [status, setStatus] = useState<string>('all')

  const handleSearch = () => {
    onSearch({
      search: search || undefined,
      type: type === 'all' ? undefined : type,
      status: status === 'all' ? undefined : status,
    })
  }

  const handleReset = () => {
    setSearch('')
    setType('all')
    setStatus('all')
    onSearch({})
  }

  return (
    <div className="flex items-center gap-3">
      {/* 搜索输入框 */}
      <Input
        placeholder="搜索权限名称、代码..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        className="w-64"
      />

      {/* 类型下拉框 */}
      <Select value={type} onValueChange={setType}>
        <SelectTrigger className="w-32">
          <SelectValue placeholder="类型" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部类型</SelectItem>
          <SelectItem value="directory">目录</SelectItem>
          <SelectItem value="menu">菜单</SelectItem>
          <SelectItem value="function">功能</SelectItem>
        </SelectContent>
      </Select>

      {/* 状态下拉框 */}
      <Select value={status} onValueChange={setStatus}>
        <SelectTrigger className="w-32">
          <SelectValue placeholder="状态" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部状态</SelectItem>
          <SelectItem value="0">正常</SelectItem>
          <SelectItem value="1">停用</SelectItem>
        </SelectContent>
      </Select>

      {/* 搜索按钮 */}
      <Button onClick={handleSearch} size="default">
        <Search className="mr-2 h-4 w-4" />
        搜索
      </Button>

      {/* 重置按钮 */}
      <Button onClick={handleReset} variant="outline" size="default">
        <RotateCcw className="mr-2 h-4 w-4" />
        重置
      </Button>
    </div>
  )
}
