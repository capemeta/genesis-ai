import { useLayout } from '@/context/layout-provider'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from '@/components/ui/sidebar'
// import { AppTitle } from './app-title'
import { sidebarData } from './data/sidebar-data'
import { NavUser } from './nav-user'
import { TeamSwitcher } from './team-switcher'
import { DynamicSidebarMenu } from './dynamic-sidebar-menu'

export function AppSidebar() {
  const { collapsible, variant } = useLayout()
  return (
    <Sidebar collapsible={collapsible} variant={variant}>
      <SidebarHeader>
        <TeamSwitcher teams={sidebarData.teams} />

        {/* Replace <TeamSwitch /> with the following <AppTitle />
         /* if you want to use the normal app title instead of TeamSwitch dropdown */}
        {/* <AppTitle /> */}
      </SidebarHeader>
      <SidebarContent>
        {/* 🔥 动态菜单权限系统 - 根据用户权限动态渲染菜单 */}
        <DynamicSidebarMenu />
        
        {/* 🔥 静态菜单（可选）- 如果需要保留静态菜单，取消注释 */}
        {/* {sidebarData.navGroups.map((props) => (
          <NavGroup key={props.title} {...props} />
        ))} */}
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={sidebarData.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
