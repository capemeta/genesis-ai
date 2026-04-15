/**
 * 文件夹路径显示配置
 * 可以在这里切换不同的根路径显示方案
 */
import { Home, Folder } from 'lucide-react'

// 根路径显示方案
export const ROOT_PATH_DISPLAY_OPTIONS = {
    // 方案 1：Home 图标 + 根目录（推荐）
    homeIcon: {
        icon: Home,
        text: '根目录',
        className: 'text-muted-foreground',
    },
    
    // 方案 2：文件夹图标 + 根目录（与左侧文件夹树图标颜色一致）
    folderIcon: {
        icon: Folder,
        text: '根目录',
        className: 'text-blue-600 dark:text-blue-400',
    },
    
    // 方案 3：斜杠（Unix 风格）
    slash: {
        icon: null,
        text: '/',
        className: 'text-muted-foreground font-mono',
    },
    
    // 方案 4：中文描述
    chinese: {
        icon: null,
        text: '（根目录）',
        className: 'text-muted-foreground',
    },
    
    // 方案 5：空白占位符
    placeholder: {
        icon: null,
        text: '—',
        className: 'text-muted-foreground',
    },
    
    // 方案 6：点点点
    dots: {
        icon: null,
        text: '···',
        className: 'text-muted-foreground',
    },
} as const

// 当前使用的方案（可以在这里切换）
export const CURRENT_ROOT_PATH_DISPLAY = ROOT_PATH_DISPLAY_OPTIONS.homeIcon

// 路径分隔符配置
export const PATH_SEPARATOR = ' › ' // 可选：' / ', ' > ', ' → ', ' ▸ '

// 路径截断配置
export const PATH_TRUNCATE_CONFIG = {
    maxLevels: 3, // 超过多少级开始截断
    showLastLevels: 2, // 截断后显示最后几级
    truncateSymbol: '...', // 截断符号，可选：'…', '···', '...'
}

// 路径显示最大宽度（像素）
export const PATH_MAX_WIDTH = 200
