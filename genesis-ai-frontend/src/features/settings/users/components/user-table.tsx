/**
 * 用户表格组件
 */
import { useMemo } from 'react'
import { Edit, Trash2, Shield, Key, Eye } from 'lucide-react'
import {
  useReactTable,
  getCoreRowModel,
  type ColumnDef,
  type PaginationState,
} from '@tanstack/react-table'
import { PermissionButton } from '@/components/permission-button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DataTablePagination } from '@/components/data-table/pagination'
import type { UserListItem } from '@/lib/api/user'
import { formatDate } from '@/lib/utils'

interface UserTableProps {
  data: UserListItem[]
  total: number
  isLoading: boolean
  pagination: PaginationState
  onPaginationChange: (pagination: PaginationState) => void
  onView: (user: UserListItem) => void
  onEdit: (user: UserListItem) => void
  onDelete: (user: UserListItem) => void
  onAssignRoles: (user: UserListItem) => void
  onResetPassword: (user: UserListItem) => void
}

export function UserTable({
  data,
  total,
  isLoading,
  pagination,
  onPaginationChange,
  onView,
  onEdit,
  onDelete,
  onAssignRoles,
  onResetPassword,
}: UserTableProps) {
  // 定义表格列
  const columns = useMemo<ColumnDef<UserListItem>[]>(
    () => [
      {
        accessorKey: 'username',
        header: '用户名',
      },
      {
        accessorKey: 'nickname',
        header: '昵称',
      },
      {
        accessorKey: 'email',
        header: '邮箱',
      },
      {
        accessorKey: 'phone',
        header: '手机号',
      },
      {
        accessorKey: 'job_title',
        header: '职位',
        cell: ({ row }) => {
          const jobTitle = row.getValue('job_title') as string | undefined
          return jobTitle ? <span>{jobTitle}</span> : <span className='text-muted-foreground'>-</span>
        },
      },
      {
        accessorKey: 'organization_name',
        header: '所属部门',
        cell: ({ row }) => {
          const orgName = row.getValue('organization_name') as string | undefined
          return orgName ? <span>{orgName}</span> : <span className='text-muted-foreground'>-</span>
        },
      },
      {
        accessorKey: 'status',
        header: '状态',
        cell: ({ row }) => {
          const status = row.getValue('status') as string
          switch (status) {
            case 'active':
              return <Badge variant='default'>正常</Badge>
            case 'disabled':
              return <Badge variant='secondary'>禁用</Badge>
            case 'locked':
              return <Badge variant='destructive'>锁定</Badge>
            default:
              return <Badge variant='outline'>{status}</Badge>
          }
        },
      },
      {
        accessorKey: 'last_login_at',
        header: '最近登录',
        cell: ({ row }) => {
          const lastLoginAt = row.getValue('last_login_at') as string | undefined
          return lastLoginAt ? formatDate(lastLoginAt) : <span className='text-muted-foreground'>-</span>
        },
      },
      {
        accessorKey: 'created_at',
        header: '创建时间',
        cell: ({ row }) => formatDate(row.getValue('created_at') as string),
      },
      {
        id: 'actions',
        header: () => <div className='text-right'>操作</div>,
        cell: ({ row }) => {
          const user = row.original
          return (
            <div className='flex justify-end gap-2'>
              <PermissionButton
                permission='settings:users:query'
                variant='ghost'
                size='icon'
                onClick={() => onView(user)}
                title='查看详情'
              >
                <Eye className='h-4 w-4' />
              </PermissionButton>
              <PermissionButton
                permission='settings:users:edit'
                variant='ghost'
                size='icon'
                onClick={() => onEdit(user)}
                title='编辑'
              >
                <Edit className='h-4 w-4' />
              </PermissionButton>
              <PermissionButton
                permission='settings:users:edit'
                variant='ghost'
                size='icon'
                onClick={() => onAssignRoles(user)}
                title='分配角色'
              >
                <Shield className='h-4 w-4' />
              </PermissionButton>
              <PermissionButton
                permission='settings:users:edit'
                variant='ghost'
                size='icon'
                onClick={() => onResetPassword(user)}
                title='重置密码'
              >
                <Key className='h-4 w-4' />
              </PermissionButton>
              <PermissionButton
                permission='settings:users:delete'
                variant='ghost'
                size='icon'
                onClick={() => onDelete(user)}
                title='删除'
              >
                <Trash2 className='h-4 w-4' />
              </PermissionButton>
            </div>
          )
        },
      },
    ],
    [onView, onEdit, onDelete, onAssignRoles, onResetPassword]
  )

  // 创建表格实例（服务端分页）
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true, // 服务端分页
    pageCount: Math.ceil(total / pagination.pageSize),
    state: {
      pagination,
    },
    onPaginationChange: (updater) => {
      const newPagination = typeof updater === 'function' ? updater(pagination) : updater
      onPaginationChange(newPagination)
    },
  })

  if (isLoading) {
    return <div className='text-center py-8'>加载中...</div>
  }

  return (
    <div className='space-y-4'>
      <div className='rounded-md border'>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : typeof header.column.columnDef.header === 'function'
                        ? header.column.columnDef.header(header.getContext())
                        : header.column.columnDef.header}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className='text-center text-muted-foreground'
                >
                  暂无数据
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {typeof cell.column.columnDef.cell === 'function'
                        ? cell.column.columnDef.cell(cell.getContext())
                        : (cell.getValue() as any)}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* 分页组件 */}
      {data.length > 0 && <DataTablePagination table={table} totalRecords={total} />}
    </div>
  )
}
