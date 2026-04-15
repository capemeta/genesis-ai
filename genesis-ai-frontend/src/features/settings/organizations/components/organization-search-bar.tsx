/**
 * 组织搜索栏组件
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

interface OrganizationSearchBarProps {
  onSearch: (params: { name?: string; status?: string }) => void
}

export function OrganizationSearchBar({ onSearch }: OrganizationSearchBarProps) {
  const [name, setName] = useState('')
  const [status, setStatus] = useState<string>('all')

  const handleSearch = () => {
    onSearch({
      name: name || undefined,
      status: status === 'all' ? undefined : status,
    })
  }

  const handleReset = () => {
    setName('')
    setStatus('all')
    onSearch({})
  }

  return (
    <div className="flex items-center gap-3">
      {/* 部门名称输入框 */}
      <Input
        placeholder="部门名称"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        className="w-48"
      />

      {/* 状态下拉框 */}
      <Select value={status} onValueChange={setStatus}>
        <SelectTrigger className="w-32">
          <SelectValue placeholder="状态" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部</SelectItem>
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
