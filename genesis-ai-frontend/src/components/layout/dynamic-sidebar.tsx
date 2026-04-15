/**
 * 动态侧边栏组件
 * 
 * 根据用户权限动态渲染菜单
 */
import { usePermissionStore } from '@/stores/permission-store'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from '@/components/ui/sidebar'
import { NavGroup } from './nav-group'
import { NavUser } from './nav-user'
import { TeamSwitcher } from './team-switcher'
import { sidebarData } from './data/sidebar-data'
import { useLayout } from '@/context/layout-provider'
import { useMemo } from 'react'
import type { NavGroup as NavGroupType } from './types'
import * as LucideIcons from 'lucide-react'

/**
 * 将后端菜单数据转换为前端导航数据格式
 */
function convertMenusToNavGroups(menus: any[]): NavGroupType[] {
  if (!menus || menus.length === 0) {
    return []
  }

  // 按模块分组
  const groupedByModule: Record<string, any[]> = {}
  
  menus.forEach((menu) => {
    const module = menu.module || 'General'
    if (!groupedByModule[module]) {
      groupedByModule[module] = []
    }
    groupedByModule[module].push(menu)
  })

  // 转换为 NavGroup 格式
  return Object.entries(groupedByModule).map(([module, items]) => ({
    title: module,
    items: items.map((item) => convertMenuItem(item)),
  }))
}

/**
 * 转换单个菜单项
 */
function convertMenuItem(menu: any): any {
  // 获取图标组件
  const IconComponent = menu.icon ? (LucideIcons as any)[menu.icon] : undefined

  const baseItem = {
    title: menu.name,
    icon: IconComponent,
  }

  // 如果有子菜单
  if (menu.children && menu.children.length > 0) {
    return {
      ...baseItem,
      items: menu.children.map((child: any) => ({
        title: child.name,
        url: child.path,
        icon: child.icon ? (LucideIcons as any)[child.icon] : undefined,
      })),
    }
  }

  // 叶子节点
  return {
    ...baseItem,
    url: menu.path,
  }
}

export function DynamicSidebar() {
  const { collapsible, variant } = useLayout()
  const { menus } = usePermissionStore()

  // 转换菜单数据
  const navGroups = useMemo(() => {
    if (menus.length === 0) {
      // 如果没有权限菜单，使用默认菜单（或显示空）
      return sidebarData.navGroups
    }
    return convertMenusToNavGroups(menus)
  }, [menus])

  return (
    <Sidebar collapsible={collapsible} variant={variant}>
      <SidebarHeader>
        <TeamSwitcher teams={sidebarData.teams} />
      </SidebarHeader>
      <SidebarContent>
        {navGroups.map((props) => (
          <NavGroup key={props.title} {...props} />
        ))}
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={sidebarData.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
