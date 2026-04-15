import { useEffect, useRef } from 'react'
import { useRouterState } from '@tanstack/react-router'
import LoadingBar, { type LoadingBarRef } from 'react-top-loading-bar'

export function NavigationProgress() {
  const ref = useRef<LoadingBarRef>(null)
  const routerState = useRouterState()

  useEffect(() => {
    // 路由导航进度
    if (routerState.status === 'pending') {
      ref.current?.continuousStart()
    } 
    // 路由导航完成
    else {
      ref.current?.complete()
    }
  }, [routerState.status])

  return (
    <LoadingBar
      color='hsl(var(--primary))'
      ref={ref}
      shadow={true}
      height={3}
      transitionTime={200}
    />
  )
}
