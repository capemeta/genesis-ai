/**
 * Web 同步工作台常量定义
 */

/**
 * 网页同步状态中文标签映射
 */
export const WEB_PAGE_SYNC_STATUS_LABELS: Record<string, string> = {
  // idle 统一文案为"待同步"，与文件列表中 parse_status=pending 的展示一致
  idle: '待同步',
  queued: '排队中',
  syncing: '同步中',
  success: '同步成功',
  partial_success: '部分成功',
  failed: '同步失败',
}

/**
 * 网页同步状态对应的 Badge 样式类名
 * 与文件列表状态色系保持一致
 */
export const WEB_PAGE_SYNC_STATUS_CLASSES: Record<string, string> = {
  // idle = 待同步，用橙色传递"有事要做"的提示感
  idle: 'bg-orange-50 text-orange-600 border-none shadow-none hover:bg-orange-50',
  queued: 'bg-yellow-100 text-yellow-700 border-none shadow-none hover:bg-yellow-100',
  syncing: 'bg-blue-50 text-blue-700 border-none shadow-none hover:bg-blue-50',
  success: 'bg-green-100 text-green-700 border-none shadow-none hover:bg-green-100',
  partial_success: 'bg-orange-100 text-orange-700 border-none shadow-none hover:bg-orange-100',
  failed: 'bg-red-100 text-red-700 border-none shadow-none hover:bg-red-100',
}

/**
 * 同步记录运行状态中文标签映射
 */
export const RUN_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  success: '成功',
  failed: '失败',
}

/**
 * 抓取模式中文标签映射
 */
export const FETCH_MODE_LABELS: Record<string, string> = {
  auto: '自动回退',
  static: '仅静态',
  browser: '浏览器',
}

/**
 * 默认分块配置
 */
export const DEFAULT_CHUNKING_CONFIG = {
  max_embed_tokens: 512,
}

/**
 * 默认抓取超时时间（秒）
 */
export const DEFAULT_TIMEOUT_SECONDS = 20
