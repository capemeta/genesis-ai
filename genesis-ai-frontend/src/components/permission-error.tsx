/**
 * 权限加载失败提示组件
 * 
 * 用于显示权限加载失败的友好提示，并提供重试功能
 */
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { usePermissionStore } from '@/stores/permission-store'

interface PermissionErrorProps {
  /**
   * 错误消息（可选，默认使用 store 中的错误）
   */
  message?: string
  
  /**
   * 是否显示重试按钮
   */
  showRetry?: boolean
  
  /**
   * 自定义重试回调
   */
  onRetry?: () => void
  
  /**
   * 自定义类名
   */
  className?: string
}

export function PermissionError({
  message,
  showRetry = true,
  onRetry,
  className,
}: PermissionErrorProps) {
  const { error, loadMenus } = usePermissionStore()
  
  const errorMessage = message || error || '加载权限失败'
  
  const handleRetry = () => {
    if (onRetry) {
      onRetry()
    } else {
      loadMenus()
    }
  }
  
  return (
    <Alert variant="destructive" className={className}>
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>权限加载失败</AlertTitle>
      <AlertDescription className="space-y-2">
        <p>{errorMessage}</p>
        {showRetry && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetry}
            className="mt-2"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            重试
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

/**
 * 权限加载失败的全屏提示组件
 * 
 * 用于在关键位置（如布局组件）显示全屏的错误提示
 */
export function PermissionErrorFullScreen() {
  const { error, loadMenus } = usePermissionStore()
  
  return (
    <div className="flex h-screen items-center justify-center p-4">
      <div className="max-w-md w-full space-y-4">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">权限加载失败</h2>
          <p className="text-muted-foreground mb-4">
            {error || '无法加载您的权限信息，请稍后重试'}
          </p>
        </div>
        
        <div className="space-y-2">
          <Button
            onClick={() => loadMenus()}
            className="w-full"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            重新加载
          </Button>
          
          <Button
            variant="outline"
            onClick={() => window.location.reload()}
            className="w-full"
          >
            刷新页面
          </Button>
        </div>
        
        <Alert>
          <AlertDescription className="text-sm">
            <p className="font-medium mb-1">可能的原因：</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>网络连接不稳定</li>
              <li>服务器暂时无法访问</li>
              <li>您的登录状态已过期</li>
            </ul>
          </AlertDescription>
        </Alert>
      </div>
    </div>
  )
}
