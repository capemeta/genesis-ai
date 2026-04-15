import { Outlet } from '@tanstack/react-router'
import { TechSupportFooter } from '@/components/layout/tech-support-footer'
import { TopNavbar } from './top-navbar'
import { SearchProvider } from '@/context/search-provider'

type TopNavLayoutProps = {
  children?: React.ReactNode
}

export function TopNavLayout({ children }: TopNavLayoutProps) {
  return (
    <SearchProvider>
      {/* 固定一屏高度：顶栏 + 主内容 + 页脚，避免整页出现外层滚动条；主内容区内部再各自滚动 */}
      <div className='relative flex h-svh max-h-svh min-h-0 flex-col overflow-hidden'>
        <div className='shrink-0'>
          <TopNavbar />
        </div>
        <main className='flex min-h-0 flex-1 flex-col overflow-y-auto'>
          {children ?? <Outlet />}
        </main>
        <TechSupportFooter className='shrink-0' />
      </div>
    </SearchProvider>
  )
}
