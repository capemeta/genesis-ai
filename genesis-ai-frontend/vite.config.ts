import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

// https://vite.dev/config/
export default defineConfig({
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
})
