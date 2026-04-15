/**
 * 配置处理辅助函数
 */

import type { WebPageConfig } from '@/lib/api/web-sync'
import type { WebChunkingDraft } from '../types'
import { DEFAULT_CHUNKING_CONFIG, DEFAULT_TIMEOUT_SECONDS } from '../constants'

/**
 * 从后端配置中提取前端表单草稿
 */
export function getWebPageConfigDraft(config?: WebPageConfig | null): {
  timeoutSeconds: number
  contentSelector: string
  chunking: WebChunkingDraft
} {
  const chunking = config?.chunking_config || {}
  return {
    timeoutSeconds: Number(config?.timeout_seconds || DEFAULT_TIMEOUT_SECONDS),
    contentSelector: String(config?.content_selector || ''),
    chunking: {
      max_embed_tokens: Number(chunking.max_embed_tokens || DEFAULT_CHUNKING_CONFIG.max_embed_tokens),
    },
  }
}

/**
 * 构建后端配置请求载荷
 */
export function buildWebPageConfigPayload(
  timeoutSeconds: number,
  contentSelector: string,
  chunking: WebChunkingDraft
): WebPageConfig {
  const normalizedSelector = contentSelector.trim()
  return {
    timeout_seconds: Math.max(5, Number(timeoutSeconds || DEFAULT_TIMEOUT_SECONDS)),
    content_selector: normalizedSelector || undefined,
    chunking_config: {
      max_embed_tokens: Math.max(128, Number(chunking.max_embed_tokens || DEFAULT_CHUNKING_CONFIG.max_embed_tokens)),
    },
  }
}

/**
 * 获取默认分块配置草稿
 */
export function getDefaultChunkingDraft(): WebChunkingDraft {
  return { ...DEFAULT_CHUNKING_CONFIG }
}
