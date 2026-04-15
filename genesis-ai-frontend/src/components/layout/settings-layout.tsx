import { Outlet } from '@tanstack/react-router'
import { SettingsSidebar } from './settings-sidebar'

export function SettingsLayout() {
  return (
    <div className='fixed inset-x-0 top-16 bottom-0 flex overflow-hidden'>
      <SettingsSidebar />
      <main className='flex-1 overflow-y-auto p-8'>
        <Outlet />
      </main>
    </div>
  )
}
