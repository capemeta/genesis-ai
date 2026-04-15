/**
 * 角色表格组件
 */
import { useMemo } from 'react'
import { Edit, Trash2, Shield, Users } from 'lucide-react'
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
import type { RoleListItem } from '@/lib/api/role'
import { formatDate } from '@/lib/utils'
import { SUPER_ADMIN_ROLE } from '@/lib/auth/auth-const'

interface RoleTableProps {
  data: RoleListItem[]
  total: number
  isLoading: boolean
  pagination: PaginationState
  onPaginationChange: (pagination: PaginationState) => void
  onEdit: (role: RoleListItem) => void
  onDelete: (role: RoleListItem) => void
  onAssignPermissions: (role: RoleListItem) => void
  onAssignUsers: (role: RoleListItem) => void
}

export function RoleTable({
  data,
  total,
  isLoading,
  pagination,
  onPaginationChange,
  onEdit,
  onDelete,
  onAssignPermissions,
  onAssignUsers,
}: RoleTableProps) {
  // 定义表格列
  const columns = useMemo<ColumnDef<RoleListItem>[]>(
    () => [
      {
        accessorKey: 'name',
        header: '角色名称',
      },
      {
        accessorKey: 'code',
        header: '角色编码',
        cell: ({ row }) => (
          <div className='font-mono text-sm'>{row.getValue('code')}</div>
        ),
      },
      {
        accessorKey: 'status',
        header: '状态',
        cell: ({ row }) => {
          const status = row.getValue('status') as string
          return status === '0' ? (
            <Badge variant='default'>正常</Badge>
          ) : (
            <Badge variant='secondary'>停用</Badge>
          )
        },
      },
      {
        accessorKey: 'sort_order',
        header: '排序',
      },
      {
        accessorKey: 'description',
        header: '描述',
        cell: ({ row }) => row.getValue('description') || '-',
      },
      {
        accessorKey: 'created_at',
        header: '创建时间',
        cell: ({ row }) => formatDate(row.getValue('created_at')),
      },
      {
        id: 'actions',
        header: () => <div className='text-right'>操作</div>,
        cell: ({ row }) => {
          const role = row.original
          // super_admin 不显示任何操作
          if (role.code === SUPER_ADMIN_ROLE) {
            return null
          }
          return (
            <div className='flex justify-end gap-2'>
              <PermissionButton
                permission='settings:roles:edit'
                variant='ghost'
                size='icon'
                onClick={() => onEdit(role)}
                title='编辑'
              >
                <Edit className='h-4 w-4' />
              </PermissionButton>
              <PermissionButton
                permission='settings:roles:edit'
                variant='ghost'
                size='icon'
                onClick={() => onAssignPermissions(role)}
                title='授权'
              >
                <Shield className='h-4 w-4' />
              </PermissionButton>
              <PermissionButton
                permission='settings:roles:edit'
                variant='ghost'
                size='icon'
                onClick={() => onAssignUsers(role)}
                title='分配用户'
              >
                <Users className='h-4 w-4' />
              </PermissionButton>
              <PermissionButton
                permission='settings:roles:delete'
                variant='ghost'
                size='icon'
                onClick={() => onDelete(role)}
                title='删除'
              >
                <Trash2 className='h-4 w-4' />
              </PermissionButton>
            </div>
          )
        },
      },
    ],
    [onEdit, onDelete, onAssignPermissions, onAssignUsers]
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
