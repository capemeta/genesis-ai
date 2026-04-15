/**
 * 动态侧边栏菜单组件
 * 根据用户权限动态渲染菜单
 */
import { Link } from '@tanstack/react-router'
import * as LucideIcons from 'lucide-react'
import { usePermissionStore } from '@/stores/permission-store'
import type { MenuItem } from '@/stores/permission-store'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from '@/components/ui/sidebar'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronRight, Folder, FileText, AlertCircle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'

// 默认图标映射
const DEFAULT_ICONS = {
  directory: Folder,
  menu: FileText,
  function: FileText,
}

// 获取 Lucide 图标组件
function getIcon(iconName: string | null | undefined, type: string = 'menu') {
  // 如果没有指定图标，使用默认图标
  if (!iconName) {
    const DefaultIcon = DEFAULT_ICONS[type as keyof typeof DEFAULT_ICONS] || FileText
    return <DefaultIcon className="h-4 w-4" />
  }
  
  try {
    // @ts-ignore - 动态访问 Lucide 图标
    const Icon = LucideIcons[iconName]
    
    if (Icon) {
      return <Icon className="h-4 w-4" />
    }
    
    // 图标不存在，使用默认图标
    console.warn(`图标 "${iconName}" 不存在，使用默认图标`)
    const DefaultIcon = DEFAULT_ICONS[type as keyof typeof DEFAULT_ICONS] || FileText
    return <DefaultIcon className="h-4 w-4" />
  } catch (error) {
    console.error(`加载图标 "${iconName}" 失败:`, error)
    const DefaultIcon = DEFAULT_ICONS[type as keyof typeof DEFAULT_ICONS] || FileText
    return <DefaultIcon className="h-4 w-4" />
  }
}

// 渲染菜单项
function renderMenuItem(item: MenuItem) {
  const icon = getIcon(item.icon, item.type)
  
  // 如果是目录（directory），渲染为可折叠菜单
  if (item.type === 'directory' && item.children && item.children.length > 0) {
    return (
      <Collapsible key={item.id} asChild defaultOpen className='group/collapsible'>
        <SidebarMenuItem>
          <CollapsibleTrigger asChild>
            <SidebarMenuButton tooltip={item.name}>
              {icon}
              <span>{item.name}</span>
              <ChevronRight className='ml-auto h-4 w-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90' />
            </SidebarMenuButton>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <SidebarMenuSub>
              {item.children.map((child) => renderSubMenuItem(child))}
            </SidebarMenuSub>
          </CollapsibleContent>
        </SidebarMenuItem>
      </Collapsible>
    )
  }
  
  // 如果是菜单（menu）且有路径，渲染为链接
  if (item.type === 'menu' && item.path) {
    return (
      <SidebarMenuItem key={item.id}>
        <SidebarMenuButton asChild tooltip={item.name}>
          <Link to={item.path}>
            {icon}
            <span>{item.name}</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    )
  }
  
  // 其他情况不渲染
  return null
}

// 渲染子菜单项
function renderSubMenuItem(item: MenuItem) {
  const icon = getIcon(item.icon, item.type)
  
  // 如果是目录，继续递归渲染
  if (item.type === 'directory' && item.children && item.children.length > 0) {
    return (
      <Collapsible key={item.id} asChild defaultOpen className='group/collapsible'>
        <SidebarMenuSubItem>
          <CollapsibleTrigger asChild>
            <SidebarMenuSubButton>
              {icon}
              <span>{item.name}</span>
              <ChevronRight className='ml-auto h-4 w-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90' />
            </SidebarMenuSubButton>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <SidebarMenuSub>
              {item.children.map((child) => renderSubMenuItem(child))}
            </SidebarMenuSub>
          </CollapsibleContent>
        </SidebarMenuSubItem>
      </Collapsible>
    )
  }
  
  // 如果是菜单且有路径，渲染为链接
  if (item.type === 'menu' && item.path) {
    return (
      <SidebarMenuSubItem key={item.id}>
        <SidebarMenuSubButton asChild>
          <Link to={item.path}>
            {icon}
            <span>{item.name}</span>
          </Link>
        </SidebarMenuSubButton>
      </SidebarMenuSubItem>
    )
  }
  
  return null
}

export function DynamicSidebarMenu() {
  const { menus, isLoaded, loading: isLoading, error } = usePermissionStore()
  
  // 加载中状态
  if (isLoading) {
    return (
      <SidebarGroup>
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="flex items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-solid border-current border-r-transparent" />
              <span>加载菜单中...</span>
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>
    )
  }
  
  // 错误状态
  if (error) {
    return (
      <SidebarGroup>
        <Alert variant="destructive" className="mx-2">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="text-xs">
            {error}
          </AlertDescription>
        </Alert>
      </SidebarGroup>
    )
  }
  
  // 未加载或无菜单
  if (!isLoaded || menus.length === 0) {
    return null
  }
  
  // 按模块分组菜单
  const groupedMenus = menus.reduce((acc, menu) => {
    const module = menu.module || 'default'
    if (!acc[module]) {
      acc[module] = []
    }
    acc[module].push(menu)
    return acc
  }, {} as Record<string, MenuItem[]>)
  
  return (
    <>
      {Object.entries(groupedMenus).map(([module, items]) => (
        <SidebarGroup key={module}>
          {module !== 'default' && (
            <SidebarGroupLabel>{module}</SidebarGroupLabel>
          )}
          <SidebarMenu>
            {items.map((item) => renderMenuItem(item))}
          </SidebarMenu>
        </SidebarGroup>
      ))}
    </>
  )
}
