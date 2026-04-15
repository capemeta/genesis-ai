/**
 * 验证码输入组件
 */
import { useState, useEffect, useRef } from 'react'
import { RefreshCw } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { getCaptcha } from '@/lib/api/auth'
import { toast } from 'sonner'

interface CaptchaInputProps {
  value?: string
  onChange?: (value: string) => void
  onTokenChange?: (token: string) => void
  disabled?: boolean
  refreshKey?: number
}

export function CaptchaInput({
  value,
  onChange,
  onTokenChange,
  disabled,
  refreshKey = 0
}: CaptchaInputProps) {
  const [captchaImageUrl, setCaptchaImageUrl] = useState<string>('')
  const [captchaToken, setCaptchaToken] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  
  // 🔥 使用 ref 防止 React 18 StrictMode 导致的重复调用
  const isLoadingRef = useRef(false)

  // 加载验证码
  const loadCaptcha = async () => {
    // 🔥 如果正在加载，直接返回（防止重复请求）
    if (isLoadingRef.current) {
      console.log('[CaptchaInput] Already loading, skipping...')
      return
    }
    
    isLoadingRef.current = true
    setIsLoading(true)
    
    try {
      const data = await getCaptcha()
      setCaptchaImageUrl(data.image_url)
      setCaptchaToken(data.token)
      onTokenChange?.(data.token)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to load captcha')
    } finally {
      setIsLoading(false)
      // 🔥 延迟重置 loading 状态，避免快速连续调用
      setTimeout(() => {
        isLoadingRef.current = false
      }, 100)
    }
  }

  // 初始加载
  useEffect(() => {
    loadCaptcha()
  }, [refreshKey])

  return (
    <div className='flex gap-2 items-stretch'>
      {/* 验证码输入框 */}
      <Input
        type='text'
        placeholder='请输入验证码'
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        disabled={disabled}
        maxLength={6}
        className='flex-1 h-10'
      />
      
      {/* 验证码图片（可点击刷新） */}
      {captchaImageUrl && (
        <div
          className='relative h-10 w-32 flex-shrink-0 cursor-pointer rounded border bg-muted overflow-hidden hover:opacity-80 transition-opacity'
          onClick={loadCaptcha}
          title='Click to refresh captcha'
        >
          {isLoading && (
            <div className='absolute inset-0 flex items-center justify-center bg-background/50'>
              <RefreshCw className='h-4 w-4 animate-spin' />
            </div>
          )}
          <img
            src={captchaImageUrl}
            alt='Captcha'
            className='h-full w-full object-cover'
            key={captchaToken} // 强制重新加载图片
          />
        </div>
      )}
    </div>
  )
}
