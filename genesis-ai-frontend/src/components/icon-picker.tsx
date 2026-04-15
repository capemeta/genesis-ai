/**
 * 图标选择器组件
 * 支持从 Lucide 图标库中选择图标
 */
import { useState, useMemo } from 'react'
import { Check, ChevronsUpDown, Search, X } from 'lucide-react'
import * as LucideIcons from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

interface IconPickerProps {
  value?: string | null
  onChange: (value: string | null) => void
  disabled?: boolean
}

// Lucide 图标列表（精选 300+ 个常用图标）
const LUCIDE_ICONS = [
  // 基础图标
  'Home', 'User', 'Users', 'Settings', 'Search', 'Menu', 'X', 'Check',
  'ChevronRight', 'ChevronLeft', 'ChevronDown', 'ChevronUp',
  'ChevronsRight', 'ChevronsLeft', 'ChevronsDown', 'ChevronsUp',
  'Plus', 'Minus', 'Edit', 'Edit2', 'Edit3', 'Trash', 'Trash2',
  'Save', 'Download', 'Upload', 'RefreshCw', 'RefreshCcw',
  
  // 文件和文件夹
  'File', 'FileText', 'FileEdit', 'FilePlus', 'FileMinus', 'FileCheck',
  'FileX', 'FileSearch', 'FileArchive', 'FileCode', 'FileJson',
  'Folder', 'FolderOpen', 'FolderPlus', 'FolderMinus', 'FolderCheck',
  'FolderX', 'FolderSearch', 'FolderArchive', 'FolderCode',
  
  // 媒体
  'Image', 'Video', 'Music', 'Film', 'Camera', 'Mic', 'MicOff',
  'Volume', 'Volume1', 'Volume2', 'VolumeX', 'Play', 'Pause',
  'Square', 'Circle', 'StopCircle', 'PlayCircle', 'SkipBack', 'SkipForward',
  'FastForward', 'Rewind', 'Repeat', 'Repeat1', 'Shuffle',
  
  // 通讯
  'Mail', 'MailOpen', 'MailCheck', 'MailX', 'MailPlus', 'MailMinus',
  'Phone', 'PhoneCall', 'PhoneIncoming', 'PhoneOutgoing', 'PhoneMissed',
  'PhoneOff', 'PhoneForwarded', 'MessageSquare', 'MessageCircle',
  'Send', 'SendHorizontal', 'Inbox', 'AtSign',
  
  // 通知和提醒
  'Bell', 'BellOff', 'BellRing', 'BellDot', 'Calendar', 'CalendarDays',
  'CalendarCheck', 'CalendarX', 'CalendarPlus', 'CalendarMinus',
  'Clock', 'Clock1', 'Clock2', 'Clock3', 'Clock4', 'Clock5',
  'Timer', 'TimerOff', 'TimerReset', 'Alarm', 'AlarmClock',
  
  // 位置和导航
  'MapPin', 'Map', 'Navigation', 'Navigation2', 'Compass', 'Globe',
  'Globe2', 'Link', 'Link2', 'ExternalLink', 'Anchor',
  
  // 安全和隐私
  'Eye', 'EyeOff', 'Lock', 'LockOpen', 'Unlock', 'Key',
  'Shield', 'ShieldCheck', 'ShieldAlert', 'ShieldX', 'ShieldOff',
  'Fingerprint', 'Scan', 'ScanFace', 'ScanLine',
  
  // 社交和互动
  'Star', 'StarOff', 'StarHalf', 'Heart', 'HeartOff', 'HeartCrack',
  'ThumbsUp', 'ThumbsDown', 'Flag', 'FlagOff', 'Bookmark',
  'BookmarkPlus', 'BookmarkMinus', 'BookmarkCheck', 'BookmarkX',
  'Share', 'Share2', 'Award', 'Trophy', 'Medal', 'Gift',
  
  // 状态和反馈
  'AlertCircle', 'AlertTriangle', 'AlertOctagon', 'Info',
  'HelpCircle', 'CheckCircle', 'CheckCircle2', 'XCircle',
  'XOctagon', 'Ban', 'Slash', 'Loader', 'Loader2',
  
  // 箭头
  'ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown',
  'ArrowUpRight', 'ArrowUpLeft', 'ArrowDownRight', 'ArrowDownLeft',
  'ArrowBigRight', 'ArrowBigLeft', 'ArrowBigUp', 'ArrowBigDown',
  'MoveRight', 'MoveLeft', 'MoveUp', 'MoveDown',
  'CornerRightUp', 'CornerRightDown', 'CornerLeftUp', 'CornerLeftDown',
  
  // 编辑和操作
  'Copy', 'Clipboard', 'ClipboardCheck', 'ClipboardCopy', 'ClipboardList',
  'ClipboardPaste', 'ClipboardX', 'Scissors', 'Printer', 'Stamp',
  'Eraser', 'PenTool', 'Pencil', 'PencilLine', 'Highlighter',
  
  // 趋势和图表
  'Zap', 'ZapOff', 'TrendingUp', 'TrendingDown', 'Activity',
  'BarChart', 'BarChart2', 'BarChart3', 'BarChart4',
  'PieChart', 'LineChart', 'AreaChart', 'Gauge',
  
  // 商业和金融
  'Package', 'Package2', 'PackageCheck', 'PackageX', 'PackagePlus',
  'ShoppingCart', 'ShoppingBag', 'CreditCard', 'Wallet',
  'DollarSign', 'Euro', 'Pound', 'Banknote', 'Receipt',
  'Tag', 'Tags', 'Ticket', 'BadgePercent', 'BadgeDollarSign',
  
  // 技术和开发
  'Database', 'Server', 'HardDrive', 'Cpu', 'MemoryStick',
  'Cloud', 'CloudOff', 'CloudUpload', 'CloudDownload', 'CloudRain',
  'Wifi', 'WifiOff', 'Bluetooth', 'BluetoothOff', 'BluetoothConnected',
  'Radio', 'Signal', 'SignalHigh', 'SignalMedium', 'SignalLow', 'SignalZero',
  'Rss', 'Cast', 'Airplay', 'Monitor', 'MonitorSpeaker',
  'Smartphone', 'Tablet', 'Laptop', 'Watch', 'Tv',
  
  // 布局和界面
  'Grid', 'Grid2x2', 'Grid3x3', 'List', 'ListOrdered',
  'Layers', 'Layout', 'LayoutGrid', 'LayoutList', 'LayoutDashboard',
  'Sidebar', 'SidebarOpen', 'SidebarClose', 'PanelLeft', 'PanelRight',
  'PanelTop', 'PanelBottom', 'Columns', 'Rows', 'Table',
  'Maximize', 'Maximize2', 'Minimize', 'Minimize2',
  'ZoomIn', 'ZoomOut', 'Expand', 'Shrink', 'Fullscreen',
  'RotateCw', 'RotateCcw', 'Rotate3d', 'FlipHorizontal', 'FlipVertical',
  
  // 过滤和排序
  'Filter', 'FilterX', 'SortAsc', 'SortDesc', 'ArrowUpDown',
  'ArrowUpNarrowWide', 'ArrowDownNarrowWide', 'ArrowUpWideNarrow', 'ArrowDownWideNarrow',
  
  // 更多操作
  'MoreVertical', 'MoreHorizontal', 'Grip', 'GripVertical', 'GripHorizontal',
  'Move', 'MoveVertical', 'MoveHorizontal', 'MoveDiagonal', 'MoveDiagonal2',
  
  // 书籍和学习
  'BookOpen', 'Book', 'BookMarked', 'BookCopy', 'BookText',
  'Library', 'GraduationCap', 'School', 'Backpack',
  
  // 代码和开发
  'Code', 'Code2', 'CodeSquare', 'Terminal', 'TerminalSquare',
  'GitBranch', 'GitCommit', 'GitMerge', 'GitPullRequest', 'GitFork',
  'Github', 'Gitlab', 'Bug', 'Wrench', 'Hammer',
  'Settings2', 'Sliders', 'SlidersHorizontal', 'Cog', 'Tool',
  
  // 工作和办公
  'Briefcase', 'Building', 'Building2', 'Factory', 'Warehouse',
  'Store', 'Home', 'Hotel', 'Landmark', 'Church',
  'Target', 'Crosshair', 'Focus', 'Scan', 'QrCode',
  
  // 天气
  'Sun', 'Moon', 'Cloud', 'CloudRain', 'CloudSnow', 'CloudDrizzle',
  'CloudLightning', 'CloudFog', 'Wind', 'Snowflake', 'Droplet', 'Droplets',
  
  // 交通
  'Car', 'Bus', 'Truck', 'Bike', 'Plane', 'Ship', 'Train',
  'Rocket', 'Fuel', 'ParkingCircle', 'TrafficCone',
  
  // 健康和医疗
  'Heart', 'HeartPulse', 'Activity', 'Pill', 'Syringe',
  'Stethoscope', 'Thermometer', 'Bandage', 'Cross',
  
  // 食物和饮料
  'Coffee', 'Beer', 'Wine', 'Pizza', 'Cake', 'Apple',
  'Banana', 'Cherry', 'Grape', 'IceCream', 'Soup',
  
  // 表情和手势
  'Smile', 'Frown', 'Meh', 'Laugh', 'Angry', 'ThumbsUp', 'ThumbsDown',
  'Hand', 'HandMetal', 'Handshake',
  
  // 其他常用
  'Box', 'Archive', 'Inbox', 'Trash', 'Trash2',
  'Power', 'PowerOff', 'Plug', 'Plug2', 'Battery',
  'BatteryCharging', 'BatteryFull', 'BatteryLow', 'BatteryMedium',
  'Lightbulb', 'LightbulbOff', 'Flame', 'Sparkles', 'Zap',
]

// 获取所有图标名称（去重）
const getAllIconNames = (): string[] => {
  // 去重并排序
  const uniqueIcons = Array.from(new Set(LUCIDE_ICONS))
  return uniqueIcons.sort()
}

export function IconPicker({ value, onChange, disabled = false }: IconPickerProps) {
  const [open, setOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  
  const allIcons = useMemo(() => getAllIconNames(), [])
  
  // 根据搜索关键词过滤图标
  const filteredIcons = useMemo(() => {
    if (!searchQuery.trim()) {
      return allIcons
    }
    
    const query = searchQuery.toLowerCase().trim()
    return allIcons.filter((name) => name.toLowerCase().includes(query))
  }, [allIcons, searchQuery])
  
  // 渲染图标
  const renderIcon = (iconName: string) => {
    try {
      const IconComponent = (LucideIcons as any)[iconName]
      if (!IconComponent) return null
      return <IconComponent className="h-4 w-4" />
    } catch (error) {
      return null
    }
  }
  
  // 清除选择
  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange(null)
  }
  
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
        >
          <span className="flex items-center gap-2">
            {value ? (
              <>
                {renderIcon(value)}
                <span className="truncate">{value}</span>
              </>
            ) : (
              <span className="text-muted-foreground">选择图标...</span>
            )}
          </span>
          <div className="flex items-center gap-1">
            {value && !disabled && (
              <X
                className="h-4 w-4 shrink-0 opacity-50 hover:opacity-100"
                onClick={handleClear}
              />
            )}
            <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
          </div>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <div className="flex flex-col">
          {/* 搜索框 */}
          <div className="flex items-center border-b px-3 py-2">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <Input
              placeholder="搜索图标..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 border-0 p-0 focus-visible:ring-0 focus-visible:ring-offset-0"
            />
          </div>
          
          {/* 图标列表 */}
          <div 
            className="h-[300px] overflow-y-auto overscroll-contain [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-thumb]:rounded-full"
            style={{ 
              // 强制启用原生滚动
              overflowY: 'scroll',
              WebkitOverflowScrolling: 'touch',
              // 确保可以接收滚轮事件
              pointerEvents: 'auto',
              // 禁用 touch-action 限制
              touchAction: 'auto'
            } as React.CSSProperties}
            onWheel={(e) => {
              // 阻止事件冒泡
              e.stopPropagation()
            }}
          >
            {filteredIcons.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                未找到图标
              </div>
            ) : (
              <div className="grid grid-cols-6 gap-2 p-2">
                {filteredIcons.map((iconName) => (
                  <button
                    key={iconName}
                    type="button"
                    onClick={() => {
                      onChange(iconName)
                      setOpen(false)
                      setSearchQuery('')
                    }}
                    className={cn(
                      'flex flex-col items-center justify-center gap-1 rounded-md p-2 hover:bg-accent hover:text-accent-foreground',
                      value === iconName && 'bg-accent text-accent-foreground'
                    )}
                    title={iconName}
                  >
                    <div className="relative">
                      {renderIcon(iconName)}
                      {value === iconName && (
                        <Check className="absolute -right-1 -top-1 h-3 w-3 text-primary" />
                      )}
                    </div>
                    <span className="text-[10px] truncate w-full text-center">
                      {iconName}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
