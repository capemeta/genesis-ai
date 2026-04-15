# Vue 开发者的 React (Genesis AI) 上手指南

欢迎来到 **Genesis AI Platform** 前端开发！作为一个有 Vue 经验的新手，你可能会发现 React 的工作方式有些不同，但底层的 Web 开发逻辑是通用的。

这份文档旨在利用你已有的 Vue 知识，通过**概念映射**的方式，让你快速理解并上手本项目。

---

## 一、 核心概念映射 (Vue vs React)

| 概念 | Vue (Pinia/Vue Router) | React (本项目配套) | 说明 |
| :--- | :--- | :--- | :--- |
| **组件定义** | `.vue` 单文件组件 (SFC) | `.tsx` (TypeScript + JSX) | React 中没有 `<template>`，一切皆为 JS。 |
| **响应式数据** | `ref()`, `reactive()` | `useState()` (本地), `useQuery()` (异步) | React 的数据流是单向的，改变状态会触发重新渲染。 |
| **计算属性** | `computed()` | `useMemo()` | 用于缓存复杂的计算结果。 |
| **副作用/生命周期** | `onMounted`, `watch` | `useEffect()` | 一个 Hook 解决所有生命周期和数据监听。 |
| **全局状态** | Pinia | **Zustand** | 本项使用的 Zustand 比 Pinia 更轻量，逻辑非常相似。 |
| **路由** | Vue Router | **TanStack Router** | 本项目使用**文件系统路由**，由目录结构自动生成路由。 |
| **条件渲染** | `v-if` | `{condition && <Component />}` | 直接使用 JS 逻辑判断。 |
| **列表渲染** | `v-for` | `{list.map(item => ...)}` | 使用标准的数组 `.map()` 函数。 |
| **双向绑定** | `v-model` | `value` + `onChange` | React 推荐受控组件（手动更新数据）。 |

---

## 二、 目录结构：东西都放在哪？

基于 Vue 的经验，你可以这样理解 `src` 目录：

-   `src/components`: **公共组件**。类似于 Vue 的全局注册或公用组件目录。
-   `src/features`: **功能模块**（重头戏）。按照业务划分（如 `auth`, `chat`, `settings`）。每个 feature 下包含自己的 components, hooks, api 等。**这是主要的开发区域。**
-   `src/routes`: **路由配置**。这是 TanStack Router 的核心，文件夹结构即 URL 路径。
-   `src/stores`: **全局状态**。存放 Zustand store，相当于 Vue 的 `stores/`。
-   `src/hooks`: **组合式函数 (Composables)**。类似于 Vue 的 `useXXX` 函数。
-   `src/lib`: **第三方库配置**。如 `axios` 实例、工具函数 `utils.ts` 等。

---

## 三、 本项目核心技术栈

### 1. 路由：TanStack Router (文件系统路由)
你不需要手动在 `router.ts` 里写数组。
-   在 `src/routes/` 下建一个 `hello.tsx`，URL 就是 `/hello`。
-   在 `src/routes/` 下建一个 `user/$id.tsx`，URL 就是 `/user/123`（`$id` 是动态参数）。
-   **注意**：修改路由文件后，Vite 会自动更新 `src/routeTree.gen.ts`，不需要手动动它。

### 2. 状态管理：Zustand
如果你用过 Pinia，Zustand 会让你感到亲切。
```tsx
// src/stores/auth-store.ts 示例
export const useAuthStore = create((set) => ({
  user: null,
  setUser: (user) => set({ user }),
}))
```

### 3. 数据获取：TanStack Query (React Query)
Vue 中你可能在 `onMounted` 里 `axios.get`。在 React 中，我们用 `useQuery`：
```tsx
const { data, isLoading } = useQuery({
  queryKey: ['users'],
  queryFn: fetchUsers,
})
```
它能自动处理缓存、加载状态和错误。

### 4. 样式：Tailwind CSS + shadcn/ui
本项目不写 `.css` 文件（除非全局变量）。
-   使用 HTML 类名快速构筑样式：`className="flex items-center p-4"`。
-   UI 组件库：查看 `src/components/ui`，这些是基础组件（按钮、输入框、弹窗等）。

---

## 四、 快速上手：创建一个新页面

假设我们要创建一个“我的任务”页面 `/tasks`。

### 第一步：在 `src/routes` 创建路由
创建 `src/routes/_top-nav/tasks/index.tsx`:
```tsx
import { createFileRoute } from '@tanstack/react-router'
import { MyTasks } from '@/features/tasks'

export const Route = createFileRoute('/_top-nav/tasks/')({
  component: MyTasks, // 指向具体的业务组件
})
```

### 第二步：在 `src/features` 编写业务代码
创建 `src/features/tasks/index.tsx`:
```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'

export function MyTasks() {
  const [count, setCount] = useState(0) // 相当于 ref(0)

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">我的任务</h1>
      <p>当前任务数: {count}</p>
      <Button onClick={() => setCount(prev => prev + 1)}>
        增加任务
      </Button>
    </div>
  )
}
```

---

## 五、 给 Vue 开发者的 5 条“避坑”建议

1.  **忘记 `v-model`**：在 React 中，输入框通常是 `<input value={name} onChange={e => setName(e.target.value)} />`。
2.  **`key` 的重要性**：在 `map` 列表渲染时，**必须**给最外层元素加 `key`，否则 React 性能会下降且会报错。
3.  **不要直接修改状态**：不要像 Vue 那样直接 `state.count++`。必须使用 `setCount(count + 1)`，否则 React 不知道数据变了。
4.  **Hooks 的限制**：`useState`, `useEffect` 等 Hooks **只能**在组件的顶层调用，不能写在 `if` 或循环里。
5.  **单向数据流**：Props 是只读的。如果你想修改父组件的数据，父组件需要传一个回调函数（如 `onUpdate={...}`）下来。

---

## 六、 常用资源
-   [TanStack Router 文档](https://tanstack.com/router) (非常重要)
-   [shadcn/ui 组件预览](https://ui.shadcn.com/docs/components/button) (查组件怎么用)
-   [React 官方文档](https://react.dev) (遇到基础问题必看)

**祝你开发愉快！如果有任何问题，随时问我。**
