/**
 * 清理 Vite 预构建缓存目录，用于解决开发态偶发 500（缓存损坏或与依赖图不一致）。
 * 兼容历史路径 node_modules/.vite 与当前 cacheDir（项目根 .vite）。
 */
import { rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

for (const rel of ['.vite', 'node_modules/.vite']) {
  try {
    rmSync(path.join(root, rel), { recursive: true, force: true })
  } catch {
    // 忽略不存在或无权限等错误，避免阻断后续 vite 启动
  }
}
