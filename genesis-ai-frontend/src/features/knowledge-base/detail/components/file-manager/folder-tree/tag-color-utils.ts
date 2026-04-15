/**
 * 标签颜色工具函数
 */

/**
 * 根据颜色名称获取对应的 Tailwind CSS 类名
 */
export function getTagColorClass(color?: string): string {
  switch (color) {
    case 'blue':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
    case 'green':
      return 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300'
    case 'purple':
      return 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300'
    case 'red':
      return 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300'
    case 'yellow':
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300'
    case 'gray':
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
    default:
      // 默认蓝色
      return 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
  }
}
