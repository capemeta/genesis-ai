/**
 * 用户搜索栏组件
 */
import { useState } from 'react'
import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { OrganizationTreeNode } from '@/lib/api/organization'
import { OrganizationTreeSelect } from './organization-tree-select'

interface UserSearchBarProps {
  onSearch: (params: { search?: string; status?: string; organization_id?: string }) => void
  organizationTree: OrganizationTreeNode[]
}

export function UserSearchBar({ onSearch, organizationTree }: UserSearchBarProps) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [organizationId, setOrganizationId] = useState<string | null>(null)

  const handleSearch = () => {
    onSearch({
      search,
      status: status === 'all' ? '' : status,
      organization_id: organizationId || '',
    })
  }

  const handleReset = () => {
    setSearch('')
    setStatus('all')
    setOrganizationId(null)
    onSearch({ search: '', status: '', organization_id: '' })
  }

  return (
    <div className='flex flex-col gap-4 lg:flex-row lg:items-center'>
      <Input
        placeholder='搜索用户名、昵称、邮箱或手机号'
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        className='w-full lg:max-w-sm'
      />
      <Select value={status} onValueChange={setStatus}>
        <SelectTrigger className='w-[180px]'>
          <SelectValue placeholder='状态' />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value='all'>全部</SelectItem>
          <SelectItem value='active'>正常</SelectItem>
          <SelectItem value='disabled'>禁用</SelectItem>
          <SelectItem value='locked'>锁定</SelectItem>
        </SelectContent>
      </Select>
      <div className='w-full lg:w-[260px]'>
        <OrganizationTreeSelect
          value={organizationId}
          onChange={setOrganizationId}
          treeData={organizationTree}
          placeholder='筛选所属部门'
        />
      </div>
      <Button onClick={handleSearch}>
        <Search className='mr-2 h-4 w-4' />
        搜索
      </Button>
      <Button variant='outline' onClick={handleReset}>
        重置
      </Button>
    </div>
  )
}
