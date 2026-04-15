# 文件浏览器组件说明

## FolderBreadcrumb 面包屑导航

### 功能特性

1. **完整路径显示**：显示从根目录到当前文件夹的完整路径
2. **可点击导航**：点击任意父级文件夹快速跳转
3. **视觉反馈**：
   - 当前文件夹高亮显示（背景色 + 加粗）
   - 悬停效果（hover 状态）
   - 图标动画（根目录图标 hover 时放大）
4. **响应式设计**：
   - 长路径自动横向滚动
   - 文件夹名称过长时截断显示
   - 支持 tooltip 显示完整名称和描述
5. **无障碍支持**：
   - 语义化 HTML（nav, aria-label, aria-current）
   - 键盘导航支持

### 使用示例

```tsx
import { FolderBreadcrumb } from './components/folder-breadcrumb'

<FolderBreadcrumb
  folderPath={folderPath}
  onNavigate={(folderId) => {
    // folderId 为 null 表示返回根目录
    setSelectedFolderId(folderId)
  }}
/>
```

### 样式说明

- **根目录按钮**：灰色文字 + 文件夹图标，hover 时图标放大
- **路径分隔符**：使用 ChevronRight 图标，半透明
- **中间文件夹**：灰色文字，hover 时背景高亮
- **当前文件夹**：背景高亮 + 加粗 + 阴影，不可点击
- **滚动条**：细滚动条，自动隐藏

### 设计参考

参考了以下产品的面包屑设计：
- VS Code 文件浏览器
- Notion 页面导航
- GitHub 文件路径
- macOS Finder 路径栏

### API 依赖

需要后端提供 `fetchFolderPath` API：

```typescript
// 输入：文件夹 ID
// 输出：从根目录到当前文件夹的路径数组
export async function fetchFolderPath(folderId: string): Promise<Folder[]>
```

实现逻辑：从当前文件夹向上追溯 `parent_id`，直到根目录。
