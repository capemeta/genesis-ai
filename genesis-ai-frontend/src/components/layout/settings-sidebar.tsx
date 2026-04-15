import { useState, useMemo } from 'react'
import { Link, useRouterState } from '@tanstack/react-router'
import * as LucideIcons from 'lucide-react'
import {
  UserCog,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { usePermissionStore } from '@/stores/permission-store'
import type { MenuItem } from '@/stores/permission-store'

// 固定的个人设置菜单（不参与动态加载）
const personalSettingsMenu = {
  title: '个人设置',
  items: [
    { title: '个人资料', path: '/settings/profile', icon: UserCog },
  ],
}

// 获取菜单图标组件（支持动态 Lucide 图标）
const getMenuIcon = (iconName?: string) => {
  // 如果没有图标名称，返回 null，不显示图标
  if (!iconName) {
    return null
  }

  try {
    // 动态从 Lucide Icons 中获取
    // @ts-ignore - 动态访问 Lucide 图标
    const Icon = LucideIcons[iconName]

    if (Icon) {
      return Icon
    }

    // 图标不存在，返回 null
    return null
  } catch (error) {
    // 加载失败，返回 null
    return null
  }
}

export function SettingsSidebar() {
  const router = useRouterState()
  const currentPath = router.location.pathname
  const [isCollapsed, setIsCollapsed] = useState(false)
  const { getChildMenus, menus, isLoaded } = usePermissionStore()

  // 动态加载 /settings 的子菜单
  const dynamicMenus = useMemo(() => {
    if (!isLoaded || menus.length === 0) {
      console.log('[SettingsSidebar] Menus not loaded yet')
      return []
    }

    const settingsChildren = getChildMenus('/settings')
    console.log('[SettingsSidebar] Settings children menus:', settingsChildren)

    // 将菜单按类型分组：directory 作为分组标题，menu 作为菜单项
    const groups: Array<{ title: string; items: MenuItem[] }> = []

    settingsChildren.forEach(child => {
      // 跳过控制台菜单（/settings 首页）
      if (child.path === '/settings' || child.code === 'menu:settings:dashboard') {
        return
      }

      // 判断是否为 directory 类型：通过 type 字段判断
      if (child.type === 'directory') {
        // directory 类型：作为分组标题，其子菜单作为菜单项
        groups.push({
          title: child.name,
          items: child.children || []
        })
        console.log('[SettingsSidebar] Added directory group:', child.name, 'with', child.children?.length || 0, 'items')
      }
      // 独立的 menu 类型直接忽略，不做特殊处理
    })

    console.log('[SettingsSidebar] Dynamic menu groups:', groups)
    return groups
  }, [menus, isLoaded, getChildMenus])

  // 渲染菜单项（支持折叠和非折叠两种模式）
  const renderMenuItem = (item: MenuItem, isCollapsed: boolean) => {
    // 如果是 directory 类型，不渲染为菜单项（已经作为分组标题处理）
    if (item.type === 'directory') {
      return null
    }
    if (!item.path) {
      return null
    }

    const isActive = item.path === '/settings'
      ? currentPath === '/settings'
      : currentPath.startsWith(item.path) && item.path !== '/settings'

    const IconComponent = getMenuIcon(item.icon)

    if (isCollapsed) {
      return (
        <TooltipProvider key={item.id}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to={item.path}
                className={cn(
                  'flex items-center justify-center rounded-lg p-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                {IconComponent && <IconComponent className='h-5 w-5' />}
              </Link>
            </TooltipTrigger>
            <TooltipContent side='right'>
              {item.name}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )
    }

    return (
      <Link
        key={item.id}
        to={item.path}
        className={cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
          isActive
            ? 'bg-primary text-primary-foreground'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        )}
      >
        {IconComponent && <IconComponent className='h-4 w-4' />}
        <span>{item.name}</span>
      </Link>
    )
  }

  // 渲染固定个人设置菜单
  const renderPersonalSettings = () => {
    const { items } = personalSettingsMenu

    return (
      <div>
        {!isCollapsed && (
          <h3 className='mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider'>
            {personalSettingsMenu.title}
          </h3>
        )}
        <div className='space-y-1'>
          {items.map((item) => {
            const isActive = currentPath.startsWith(item.path)
            const Icon = item.icon

            if (isCollapsed) {
              return (
                <TooltipProvider key={item.path}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link
                        to={item.path}
                        className={cn(
                          'flex items-center justify-center rounded-lg p-2 text-sm transition-colors',
                          isActive
                            ? 'bg-primary text-primary-foreground'
                            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                        )}
                      >
                        <Icon className='h-5 w-5' />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent side='right'>
                      {item.title}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )
            }

            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                <Icon className='h-4 w-4' />
                <span>{item.title}</span>
              </Link>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <aside className={cn(
      'border-r bg-muted/10 h-[calc(100vh-4rem)] transition-all duration-300 ease-in-out flex flex-col',
      isCollapsed ? 'w-16' : 'w-64'
    )}>
      {/* 顶部标题和折叠按钮 - 固定不滚动 */}
      <div className={cn('p-6 pb-4 flex-shrink-0', isCollapsed && 'p-3 pb-2')}>
        <div className={cn('flex', isCollapsed ? 'justify-center' : 'justify-between items-start')}>
          {!isCollapsed && (
            <div>
              <h2 className='text-lg font-semibold mb-1'>管理设置</h2>
              <p className='text-sm text-muted-foreground'>平台配置管理</p>
            </div>
          )}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant='ghost'
                  size='icon'
                  onClick={() => setIsCollapsed(!isCollapsed)}
                  className={cn('h-8 w-8', !isCollapsed && 'mt-1')}
                >
                  {isCollapsed ? (
                    <PanelLeftOpen className='h-4 w-4' />
                  ) : (
                    <PanelLeftClose className='h-4 w-4' />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side='right'>
                {isCollapsed ? '展开侧边栏' : '收起侧边栏'}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      {/* 滚动内容区域 */}
      <div className={cn('flex-1 overflow-y-auto overflow-x-hidden px-6', isCollapsed && 'px-3')}>
        <nav className='space-y-6 pb-6'>
          {/* 固定个人设置菜单 */}
          {renderPersonalSettings()}

          {/* 动态加载的管理菜单 */}
          {dynamicMenus.length > 0 && (
            <>
              {!isCollapsed && <div className='my-4 border-t border-border' />}
              {dynamicMenus.map((group) => (
                <div key={group.title}>
                  {!isCollapsed && (
                    <h3 className='mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider'>
                      {group.title}
                    </h3>
                  )}
                  <div className='space-y-1'>
                    {group.items.map((item) => renderMenuItem(item, isCollapsed))}
                  </div>
                </div>
              ))}
            </>
          )}

        </nav>
      </div>

      {/* 底部退出按钮 - 固定不滚动 */}
      {/* 注释原因：顶部导航栏头像下拉菜单中已有退出登录功能，无需重复 */}
      {/* {!isCollapsed && (
        <div className='px-6 py-4 border-t flex-shrink-0'>
          <button
            onClick={handleLogout}
            className='flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full'
          >
            <svg
              xmlns='http://www.w3.org/2000/svg'
              viewBox='0 0 24 24'
              fill='none'
              stroke='currentColor'
              strokeWidth='2'
              strokeLinecap='round'
              strokeLinejoin='round'
              className='h-4 w-4'
            >
              <path d='M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4' />
              <polyline points='16 17 21 12 16 7' />
              <line x1='21' x2='9' y1='12' y2='12' />
            </svg>
            <span>退出登录</span>
          </button>
        </div>
      )} */}
    </aside>
  )
}
