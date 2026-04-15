/**
 * 验证工具函数
 */

/**
 * 验证 CSS 选择器语法
 * @returns 如果有效返回 null，否则返回错误信息
 */
export function validateCssSelectorSyntax(selector?: string | null): string | null {
  const value = String(selector || '').trim()
  if (!value) return null
  try {
    const fragment = document.createDocumentFragment()
    fragment.querySelector(value)
    return null
  } catch {
    return 'CSS 选择器语法不合法，请检查括号、引号或层级写法'
  }
}
