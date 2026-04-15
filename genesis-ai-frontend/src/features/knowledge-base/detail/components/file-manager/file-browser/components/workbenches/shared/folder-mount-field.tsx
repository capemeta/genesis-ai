import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { fetchFolderPath, fetchFolderTree } from '@/lib/api/folder'
import type { FolderTreeNode } from '@/lib/api/folder.types'

interface FolderMountFieldProps {
  kbId: string
  value: string | null
  onChange: (folderId: string | null) => void
  label?: string
  description?: string
}

interface FolderOption {
  id: string
  label: string
}

function flattenFolderOptions(nodes: FolderTreeNode[], depth = 0): FolderOption[] {
  return nodes.flatMap((node) => {
    const prefix = depth > 0 ? `${'··'.repeat(depth)} ` : ''
    return [
      { id: node.id, label: `${prefix}${node.name}` },
      ...flattenFolderOptions(node.children || [], depth + 1),
    ]
  })
}

export function FolderMountField({
  kbId,
  value,
  onChange,
  label = '挂载目录',
  description,
}: FolderMountFieldProps) {
  const { data: folderTree = [], isLoading: isLoadingFolders } = useQuery({
    queryKey: ['folders', 'tree', kbId],
    queryFn: () => fetchFolderTree(kbId),
    enabled: !!kbId,
    staleTime: 30_000,
  })

  const { data: folderPath = [] } = useQuery({
    queryKey: ['folder-path', value],
    queryFn: () => fetchFolderPath(value!),
    enabled: !!value,
    staleTime: 30_000,
  })

  // 统一拍平成下拉选项，便于在弹窗里快速选择挂载目录。
  const folderOptions = useMemo(() => flattenFolderOptions(folderTree), [folderTree])
  const currentPathLabel = value && folderPath.length > 0
    ? folderPath.map(folder => folder.name).join(' / ')
    : '根目录'

  return (
    <div className='space-y-2'>
      <Label>{label}</Label>
      <div className='rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600'>
        当前挂载位置：{currentPathLabel}
      </div>
      <Select
        value={value || '__root__'}
        onValueChange={nextValue => onChange(nextValue === '__root__' ? null : nextValue)}
      >
        <SelectTrigger className='bg-white'>
          <SelectValue placeholder={isLoadingFolders ? '正在加载目录...' : '请选择挂载目录'} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value='__root__'>根目录</SelectItem>
          {folderOptions.map(option => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {description ? <p className='text-xs text-slate-500'>{description}</p> : null}
    </div>
  )
}
