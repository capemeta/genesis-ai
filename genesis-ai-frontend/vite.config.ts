import path from 'path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react-swc'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

function normalizeBasePath(pathValue?: string): string {
  const trimmed = (pathValue || '/').trim()
  if (!trimmed || trimmed === '/') {
    return '/'
  }

  const withLeadingSlash = trimmed.startsWith('/') ? trimmed : `/${trimmed}`
  return `${withLeadingSlash.replace(/\/+$/, '')}/`
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 开发态同样读取前端 .env，确保 `/genesis-ai` 这类子路径在 `vite dev` 下也生效。
  const env = loadEnv(mode, __dirname, '')
  const appBasePath = normalizeBasePath(env.ROOT_PATH || process.env.ROOT_PATH)

  return {
    // 子路径部署时，需要让静态资源也带上统一上下文前缀。
    base: appBasePath,
    // 将预构建缓存放在项目根目录，避免落在 node_modules 下被 Windows 杀毒/同步工具频繁锁定导致偶发 500
    cacheDir: path.resolve(__dirname, '.vite'),
    plugins: [
      tanstackRouter({
        target: 'react',
        autoCodeSplitting: true,
        routesDirectory: './src/routes', // 扫描路由文件的起始目录
        generatedRouteTree: './src/routeTree.gen.ts', // 生成的路由树文件存放位置
      }),
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '127.0.0.1', // 显式绑定回环地址，避免 localhost 被代理或 DNS 规则影响
      // 开发态禁用浏览器缓存，避免偶发 ERR_CACHE_READ_FAILURE 导致动态模块加载失败
      headers: {
        'Cache-Control': 'no-store, max-age=0',
        Pragma: 'no-cache',
        Expires: '0',
      },
      // port: 5173,       // 可选：自定义端口（默认 5173）
      // open: true,       // 可选：启动时自动打开浏览器
    },
  }
})
