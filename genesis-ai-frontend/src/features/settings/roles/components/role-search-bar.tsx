/**
 * 角色搜索栏组件
 */
import { useState } from 'react'
import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface RoleSearchBarProps {
  onSearch: (params: any) => void
}

export function RoleSearchBar({ onSearch }: RoleSearchBarProps) {
  const [search, setSearch] = useState('')

  const handleSearch = () => {
    onSearch({ search })
  }

  const handleReset = () => {
    setSearch('')
    onSearch({ search: '' })
  }

  return (
    <div className='flex items-center gap-4'>
      <Input
        placeholder='请输入角色编码、名称'
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        className='max-w-sm'
      />
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
