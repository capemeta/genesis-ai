import { Link, useRouterState } from '@tanstack/react-router'
import { Bell } from 'lucide-react'
import { cn, getFileUrl } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuthStore } from '@/stores/auth-store'
import { useLogout } from '@/lib/auth/logout-handler'
import { usePermissionStore } from '@/stores/permission-store'
import { getTopLevelMenus } from '@/lib/utils/menu-utils'
import { useMemo } from 'react'

// 固定首页菜单项
const homeMenuItem = { label: '首页', path: '/' }

// 备用静态菜单（当动态菜单加载失败时使用，不包含首页）
const fallbackNavItems = [
  { label: '知识库', path: '/knowledge-base' },
  { label: '文档管理', path: '/documents' },
  { label: '聊天', path: '/chat' },
  { label: '智能体', path: '/agents' },
  { label: '设置', path: '/settings' },
]

export function TopNavbar() {
  const router = useRouterState()
  const currentPath = router.location.pathname
  const { user } = useAuthStore()
  const { handleLogout } = useLogout()
  const { menus, loading, isLoaded } = usePermissionStore()

  // 动态生成顶部导航菜单
  const navItems = useMemo(() => {
    // 如果正在加载或未加载完成，首页 + 备用菜单
    if (loading || !isLoaded || menus.length === 0) {
      console.log('[TopNavbar] Using fallback menu items')
      return [homeMenuItem, ...fallbackNavItems]
    }

    // 获取顶级菜单
    const topMenus = getTopLevelMenus(menus)
    console.log('[TopNavbar] Top level menus:', topMenus)

    // 如果没有顶级菜单，首页 + 备用菜单
    if (topMenus.length === 0) {
      console.log('[TopNavbar] No top level menus found, using fallback')
      return [homeMenuItem, ...fallbackNavItems]
    }

    // 过滤掉首页菜单（如果动态菜单中有），转换为导航项格式
    const dynamicItems = topMenus
      .filter(menu => menu.path && menu.path !== '/')
      .map(menu => ({
        label: menu.name,
        path: menu.path!,
        icon: menu.icon,
      }))

    // 首页固定在第一位，后面是动态菜单
    return [homeMenuItem, ...dynamicItems]
  }, [menus, loading, isLoaded])

  // 获取用户名首字母作为头像
  const getUserInitials = () => {
    if (!user) return 'AM'
    return user.nickname
      ? user.nickname.substring(0, 2).toUpperCase()
      : user.username.substring(0, 2).toUpperCase()
  }

  const getUserDisplayName = () => {
    if (!user) return 'Alex Morgan'
    return user.nickname || user.username
  }

  const getUserRole = () => {
    if (!user) return 'Team Admin'
    return user.is_superuser ? 'Super Admin' : 'User'
  }

  return (
    <header className='sticky top-0 z-50 w-full h-16 border-b border-border/40 bg-transparent backdrop-blur-md'>
      <div className='flex h-full items-center px-6'>
        {/* Logo */}
        <Link to='/' className='flex items-center gap-2.5 font-semibold transition-opacity hover:opacity-80'>
          <div className='flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full'>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="128"
            height="128"
            viewBox="-64 -64 128 128"
            className="h-full w-full"
            role="img"
            aria-label="Genesis AI Platform logo"
          >
            <title>Genesis AI Platform</title>
            <g>
              <circle cx="0" cy="0" r="48" fill="#D8EEFF"/>
              <circle cx="0" cy="0" r="39" fill="#A8D0F8"/>
              <circle cx="0" cy="0" r="30" fill="#6AAEE8"/>
              <circle cx="0" cy="0" r="21" fill="#2E7DD8"/>
              <circle cx="0" cy="0" r="12" fill="#0A50B8"/>
              <circle cx="0" cy="0" r="4" fill="#082E80"/>
              <path d="M -34,-34 A 48,48 0 0,1 34,-34" fill="none" stroke="#EAF4FF" strokeWidth="0.7" strokeLinecap="round"/>
              <text x="0" y="8" textAnchor="middle" fontFamily="Georgia, serif" fontSize="42" fontWeight="400" fill="#FFFFFF">G</text>
            </g>
          </svg>
          </div>
          <span className='bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-lg font-bold tracking-tight text-transparent'>
            启元AI平台
          </span>
        </Link>

        {/* Navigation Links - Centered */}
        <nav className='flex flex-1 items-center justify-center'>
          <div className='flex items-center gap-1 rounded-full bg-muted/50 p-1 backdrop-blur-sm border border-border/50 shadow-sm'>
            {navItems.map((item) => {
              const isActive =
                item.path === '/'
                  ? currentPath === '/'
                  : currentPath.startsWith(item.path)

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'relative px-4 py-2 text-sm font-medium transition-all duration-200 rounded-full',
                    isActive
                      ? 'bg-background/90 text-foreground border border-primary/50 shadow-lg backdrop-blur-md'
                      : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                  )}
                >
                  {item.label}
                </Link>
              )
            })}
          </div>
        </nav>

        {/* Right Side Actions */}
        <div className='flex items-center gap-1'>
          {/* Notifications */}
          <Button
            variant='ghost'
            size='icon'
            className='relative h-9 w-9 rounded-full hover:bg-muted/50 transition-colors'
          >
            <Bell className='h-[18px] w-[18px]' />
            <span className='absolute right-2 top-2 h-2 w-2 rounded-full bg-red-500 ring-2 ring-background' />
          </Button>

          {/* Help */}
          <Button
            variant='ghost'
            size='icon'
            className='h-9 w-9 rounded-full hover:bg-muted/50 transition-colors'
          >
            <svg
              xmlns='http://www.w3.org/2000/svg'
              viewBox='0 0 24 24'
              fill='none'
              stroke='currentColor'
              strokeWidth='2'
              strokeLinecap='round'
              strokeLinejoin='round'
              className='h-[18px] w-[18px]'
            >
              <circle cx='12' cy='12' r='10' />
              <path d='M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3' />
              <path d='M12 17h.01' />
            </svg>
          </Button>

          <div className='ml-1 h-8 w-px bg-border/50' />

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant='ghost' className='relative h-9 w-9 rounded-full p-0 ml-1 hover:bg-muted/50 transition-colors'>
                <Avatar className='h-9 w-9 ring-2 ring-border/50 ring-offset-2 ring-offset-background transition-all hover:ring-primary/50'>
                  <AvatarImage src={getFileUrl(user?.avatar_url) || '/avatars/shadcn.jpg'} alt='User' />
                  <AvatarFallback className='bg-gradient-to-br from-primary/20 to-primary/10 text-primary font-semibold'>
                    {getUserInitials()}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className='w-56 backdrop-blur-xl bg-background/95 border-border/50' align='end' forceMount>
              <DropdownMenuLabel className='font-normal'>
                <div className='flex flex-col space-y-1'>
                  <p className='text-sm font-semibold leading-none'>{getUserDisplayName()}</p>
                  <p className='text-xs leading-none text-muted-foreground'>
                    {user?.email || getUserRole()}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to='/settings/profile' className='cursor-pointer'>
                  个人资料
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className='text-destructive focus:text-destructive cursor-pointer'
                onClick={handleLogout}
              >
                退出登录
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
