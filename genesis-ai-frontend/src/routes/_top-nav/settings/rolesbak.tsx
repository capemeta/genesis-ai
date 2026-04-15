import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { Search, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export const Route = createFileRoute('/_top-nav/settings/rolesbak')({
  component: RolesAndPermissions,
})

function RolesAndPermissions() {
  const [selectedRole, setSelectedRole] = useState('super-admin')

  const roles = [
    {
      id: 'super-admin',
      name: 'Super Admin',
      badge: 'DEFAULT',
      description: 'Full system access and control.',
    },
    {
      id: 'workspace-manager',
      name: 'Workspace Manager',
      description: 'Manage users, agents, and data.',
    },
    {
      id: 'member',
      name: 'Member',
      description: 'Standard workspace access.',
    },
    {
      id: 'read-only',
      name: 'Read-only',
      description: 'Viewing rights only.',
    },
  ]

  const permissions = {
    knowledgeBase: [
      {
        title: 'Documents & Files',
        description: 'Access and manage uploaded source files.',
        permissions: { view: true, create: true, edit: true, delete: true },
      },
      {
        title: 'Vector Store Config',
        description: 'Modify indexing and embedding settings.',
        permissions: { view: true, create: true, edit: true, delete: true },
      },
    ],
    agents: [
      {
        title: 'Agent Marketplace',
        description: 'Access and install predefined agent templates.',
        permissions: { view: true, create: true, edit: true, delete: true },
      },
      {
        title: 'Custom Agent Builder',
        description: 'Define prompt templates and model parameters.',
        permissions: { view: true, create: true, edit: true, delete: true },
      },
    ],
    usersTeams: [
      {
        title: 'User Invitations',
        description: 'Invite new team members.',
        permissions: { view: true, create: false, edit: false, delete: false },
      },
      {
        title: 'Role Assignment',
        description: 'Assign roles to users.',
        permissions: { view: true, create: false, edit: false, delete: false },
      },
    ],
  }

  return (
    <div>
      {/* Header */}
      <div className='mb-6'>
        <div className='flex items-center justify-between mb-4'>
          <div>
            <h1 className='text-3xl font-bold tracking-tight mb-2'>
              Roles & Permissions
            </h1>
            <p className='text-muted-foreground'>
              Define user access levels and granular functional permissions with
              organizational boundaries.
            </p>
          </div>
          <Button>
            <Plus className='mr-2 h-4 w-4' />
            Add New Role
          </Button>
        </div>
      </div>

      <div className='grid gap-6 lg:grid-cols-3'>
        {/* Left: Roles List */}
        <div>
          <div className='mb-4'>
            <div className='relative mb-4'>
              <Search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
              <Input
                type='search'
                placeholder='Search roles...'
                className='pl-9'
              />
            </div>
          </div>

          <div className='space-y-2'>
            {roles.map((role) => (
              <button
                key={role.id}
                onClick={() => setSelectedRole(role.id)}
                className={`w-full text-left p-4 rounded-lg border transition-colors ${
                  selectedRole === role.id
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:bg-muted/50'
                }`}
              >
                <div className='flex items-center justify-between mb-1'>
                  <span className='font-medium'>{role.name}</span>
                  {role.badge && (
                    <Badge variant='secondary' className='text-xs'>
                      {role.badge}
                    </Badge>
                  )}
                </div>
                <p className='text-sm text-muted-foreground'>{role.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Right: Permissions Configuration */}
        <div className='lg:col-span-2'>
          <Card>
            <CardHeader>
              <div className='flex items-center justify-between'>
                <div>
                  <CardTitle>Super Admin Configuration</CardTitle>
                  <CardDescription>
                    Set functional permissions and data visibility scope.
                  </CardDescription>
                </div>
                <div className='flex gap-2'>
                  <Button variant='outline'>Discard Changes</Button>
                  <Button>Save Permissions</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className='space-y-6'>
              {/* Organization Scope */}
              <div>
                <div className='flex items-center justify-between mb-4'>
                  <div>
                    <h3 className='font-semibold mb-1'>Organization Scope</h3>
                    <p className='text-sm text-muted-foreground'>
                      SCOPE STRATEGY: All Departments
                    </p>
                  </div>
                  <Select defaultValue='all'>
                    <SelectTrigger className='w-[200px]'>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='all'>All Departments</SelectItem>
                      <SelectItem value='specific'>Specific Departments</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Knowledge Base Permissions */}
              <div>
                <h3 className='font-semibold mb-4 flex items-center gap-2'>
                  <span className='text-blue-500'>📚</span>
                  Knowledge Base
                </h3>
                <div className='space-y-4'>
                  <div className='grid grid-cols-5 gap-4 pb-2 border-b text-sm font-medium text-muted-foreground'>
                    <div className='col-span-1'>Permission</div>
                    <div>View</div>
                    <div>Create</div>
                    <div>Edit</div>
                    <div>Delete</div>
                  </div>
                  {permissions.knowledgeBase.map((item, index) => (
                    <div key={index} className='grid grid-cols-5 gap-4 items-center'>
                      <div className='col-span-1'>
                        <div className='font-medium text-sm'>{item.title}</div>
                        <div className='text-xs text-muted-foreground'>
                          {item.description}
                        </div>
                      </div>
                      <Checkbox checked={item.permissions.view} />
                      <Checkbox checked={item.permissions.create} />
                      <Checkbox checked={item.permissions.edit} />
                      <Checkbox checked={item.permissions.delete} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Agents Permissions */}
              <div>
                <h3 className='font-semibold mb-4 flex items-center gap-2'>
                  <span className='text-blue-500'>🤖</span>
                  Agents
                </h3>
                <div className='space-y-4'>
                  <div className='grid grid-cols-5 gap-4 pb-2 border-b text-sm font-medium text-muted-foreground'>
                    <div className='col-span-1'>Permission</div>
                    <div>View</div>
                    <div>Create</div>
                    <div>Edit</div>
                    <div>Delete</div>
                  </div>
                  {permissions.agents.map((item, index) => (
                    <div key={index} className='grid grid-cols-5 gap-4 items-center'>
                      <div className='col-span-1'>
                        <div className='font-medium text-sm'>{item.title}</div>
                        <div className='text-xs text-muted-foreground'>
                          {item.description}
                        </div>
                      </div>
                      <Checkbox checked={item.permissions.view} />
                      <Checkbox checked={item.permissions.create} />
                      <Checkbox checked={item.permissions.edit} />
                      <Checkbox checked={item.permissions.delete} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Users & Teams Permissions */}
              <div>
                <h3 className='font-semibold mb-4 flex items-center gap-2'>
                  <span className='text-blue-500'>👥</span>
                  Users & Teams
                </h3>
                <div className='space-y-4'>
                  <div className='grid grid-cols-5 gap-4 pb-2 border-b text-sm font-medium text-muted-foreground'>
                    <div className='col-span-1'>Permission</div>
                    <div>View</div>
                    <div>Create</div>
                    <div>Edit</div>
                    <div>Delete</div>
                  </div>
                  {permissions.usersTeams.map((item, index) => (
                    <div key={index} className='grid grid-cols-5 gap-4 items-center'>
                      <div className='col-span-1'>
                        <div className='font-medium text-sm'>{item.title}</div>
                        <div className='text-xs text-muted-foreground'>
                          {item.description}
                        </div>
                      </div>
                      <Checkbox checked={item.permissions.view} />
                      <Checkbox checked={item.permissions.create} />
                      <Checkbox checked={item.permissions.edit} />
                      <Checkbox checked={item.permissions.delete} />
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
