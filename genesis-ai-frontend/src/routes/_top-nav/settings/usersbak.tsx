import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { Search, Plus, MoreVertical } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { requirePermission } from '@/lib/auth/permission-guard'

export const Route = createFileRoute('/_top-nav/settings/usersbak')({
  beforeLoad: () => {
    // 检查用户管理菜单权限
    requirePermission('menu:settings:users')
  },
  component: UserManagement,
})

function UserManagement() {
  const [selectedUsers, setSelectedUsers] = useState<string[]>([])

  const users = [
    {
      id: '1',
      name: 'Jordan Smith',
      email: 'jordan@platform.ai',
      avatar: '',
      roles: ['Super Admin', 'Manager'],
      status: 'Active',
    },
    {
      id: '2',
      name: 'Sarah Chen',
      email: 's.chen@corp.com',
      avatar: '',
      roles: ['Manager'],
      status: 'Active',
    },
    {
      id: '3',
      name: 'Marcus Lee',
      email: 'marcus@lee.me',
      avatar: '',
      roles: ['Member', 'Read-only'],
      status: 'Offline',
    },
  ]

  const toggleUser = (userId: string) => {
    setSelectedUsers((prev) =>
      prev.includes(userId)
        ? prev.filter((id) => id !== userId)
        : [...prev, userId]
    )
  }

  return (
    <div>
      {/* Header */}
      <div className='mb-6'>
        <div className='flex items-center justify-between mb-4'>
          <div>
            <h1 className='text-3xl font-bold tracking-tight mb-2'>User Management</h1>
            <p className='text-muted-foreground'>
              Assign multiple specialized roles and manage granular platform access.
            </p>
          </div>
          <Button>
            <Plus className='mr-2 h-4 w-4' />
            Invite User
          </Button>
        </div>

        {/* Search and Filters */}
        <div className='flex items-center gap-4'>
          <div className='relative flex-1 max-w-md'>
            <Search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
            <Input
              type='search'
              placeholder='Search by name or email...'
              className='pl-9'
            />
          </div>
          <Button variant='outline'>Filter</Button>
          <Button variant='outline'>Export</Button>
        </div>
      </div>

      {/* Bulk Actions */}
      {selectedUsers.length > 0 && (
        <div className='mb-4 p-4 bg-blue-50 dark:bg-blue-950 rounded-lg flex items-center gap-4'>
          <span className='text-sm font-medium'>
            {selectedUsers.length} users selected
          </span>
          <Button size='sm' variant='outline'>
            <Plus className='mr-2 h-3 w-3' />
            Add Roles
          </Button>
          <Button size='sm' variant='outline'>
            Remove Roles
          </Button>
        </div>
      )}

      {/* Users Table */}
      <div className='border rounded-lg'>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className='w-12'>
                <Checkbox />
              </TableHead>
              <TableHead>User</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Roles</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className='w-12'>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedUsers.includes(user.id)}
                    onCheckedChange={() => toggleUser(user.id)}
                  />
                </TableCell>
                <TableCell>
                  <div className='flex items-center gap-3'>
                    <Avatar className='h-10 w-10'>
                      <AvatarImage src={user.avatar} />
                      <AvatarFallback>
                        {user.name
                          .split(' ')
                          .map((n) => n[0])
                          .join('')}
                      </AvatarFallback>
                    </Avatar>
                    <span className='font-medium'>{user.name}</span>
                  </div>
                </TableCell>
                <TableCell className='text-muted-foreground'>{user.email}</TableCell>
                <TableCell>
                  <div className='flex flex-wrap gap-1'>
                    {user.roles.map((role, index) => (
                      <Badge
                        key={index}
                        variant={role === 'Super Admin' ? 'default' : 'secondary'}
                      >
                        {role}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge
                    variant='outline'
                    className={
                      user.status === 'Active'
                        ? 'border-green-500 text-green-500'
                        : 'border-gray-400 text-gray-400'
                    }
                  >
                    {user.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant='ghost' size='icon'>
                        <MoreVertical className='h-4 w-4' />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align='end'>
                      <DropdownMenuItem>Edit User</DropdownMenuItem>
                      <DropdownMenuItem>Manage Roles</DropdownMenuItem>
                      <DropdownMenuItem>View Activity</DropdownMenuItem>
                      <DropdownMenuItem className='text-destructive'>
                        Remove User
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className='mt-4 flex items-center justify-between'>
        <p className='text-sm text-muted-foreground'>Showing 3 of 124 users</p>
        <div className='flex gap-2'>
          <Button variant='outline' size='sm'>1</Button>
          <Button variant='outline' size='sm'>2</Button>
          <Button variant='outline' size='sm'>3</Button>
        </div>
      </div>
    </div>
  )
}
