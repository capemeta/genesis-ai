/**
 * 标签颜色工具函数 - 统一的标签颜色样式
 */

/**
 * 根据颜色名称获取可选标签的 Tailwind CSS 类名（outline 样式）
 */
export function getTagOutlineColorClass(color?: string): string {
  switch (color) {
    case 'blue':
      return 'border-blue-300 text-blue-700 dark:border-blue-300 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-950/50'
    case 'green':
      return 'border-green-300 text-green-700 dark:border-green-300 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-950/50'
    case 'purple':
      return 'border-purple-300 text-purple-700 dark:border-purple-300 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-950/50'
    case 'red':
      return 'border-red-300 text-red-700 dark:border-red-300 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-950/50'
    case 'yellow':
      return 'border-yellow-300 text-yellow-700 dark:border-yellow-300 dark:text-yellow-300 hover:bg-yellow-100 dark:hover:bg-yellow-950/50'
    case 'gray':
      return 'border-gray-300 text-gray-700 dark:border-gray-300 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
    default:
      // 默认蓝色
      return 'border-blue-300 text-blue-700 dark:border-blue-300 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-950/50'
  }
}

/**
 * 根据颜色名称获取已选标签的 Tailwind CSS 类名（filled 样式）
 */
export function getTagFilledColorClass(color?: string): string {
  switch (color) {
    case 'blue':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200 border border-blue-300'
    case 'green':
      return 'bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200 border border-green-300'
    case 'purple':
      return 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200 border border-purple-300'
    case 'red':
      return 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200 border border-red-300'
    case 'yellow':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-200 border border-yellow-300'
    case 'gray':
      return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200 border border-gray-300'
    default:
      // 默认蓝色
      return 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200 border border-blue-300'
  }
}