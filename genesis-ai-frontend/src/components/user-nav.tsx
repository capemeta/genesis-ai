/**
 * 用户导航菜单
 * 显示用户信息和登出按钮
 */
import { useNavigate } from '@tanstack/react-router'
import { LogOut, User } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { useLogout } from '@/lib/auth/logout-handler'
import { getFileUrl } from '@/lib/utils'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function UserNav() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { handleLogout } = useLogout()

  if (!user) {
    return (
      <Button
        variant='ghost'
        size='sm'
        onClick={() => navigate({ to: '/login' })}
      >
        Sign In
      </Button>
    )
  }

  // 获取用户名首字母作为头像
  const initials = user.nickname
    ? user.nickname.substring(0, 2).toUpperCase()
    : user.username.substring(0, 2).toUpperCase()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant='ghost' className='relative h-9 w-9 rounded-full'>
          <Avatar className='h-9 w-9'>
            <AvatarImage src={getFileUrl(user.avatar_url)} alt={user.username} />
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className='w-56' align='end' forceMount>
        <DropdownMenuLabel className='font-normal'>
          <div className='flex flex-col space-y-1'>
            <p className='text-sm font-medium leading-none'>
              {user.nickname || user.username}
            </p>
            <p className='text-xs leading-none text-muted-foreground'>
              {user.email}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem
            onClick={() => navigate({ to: '/settings/profile' })}
          >
            <User className='mr-2 h-4 w-4' />
            <span>Profile</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout}>
          <LogOut className='mr-2 h-4 w-4' />
          <span>Log out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
