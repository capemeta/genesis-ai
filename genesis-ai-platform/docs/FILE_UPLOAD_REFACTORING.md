# 文件上传功能重构说明

## 重构原因

根据 `doc/数据库设计.md` 的设计理念，原有的文件上传 API 设计存在问题：

**错误设计**：
- 将文件上传和知识库关联放在同一个 API 中
- `documents` 表和 `knowledge_base_documents` 表的职责混淆

**正确设计**：
- `documents` 表：纯物理资产管理，记录文件在存储系统中的真实存在，与知识库无关
- `knowledge_base_documents` 表：RAG 业务核心，实现"一份物理文件挂载到多个知识库"

## 新设计方案

### 两阶段上传流程

#### 第一阶段：纯文件上传（与知识库无关）
**API**: `POST /api/v1/documents/upload`

**功能**：
1. 验证文件类型和大小
2. 计算文件 Hash (SHA256)
3. 检查物理文件是否存在（秒传）
4. 上传到 SeaweedFS（如果需要）
5. 创建 `documents` 记录

**返回**：
```json
{
  "success": true,
  "message": "文件上传成功",
  "data": {
    "id": "document_id",
    "name": "文件名.pdf",
    "file_size": 1024000,
    "file_type": "PDF",
    "content_hash": "sha256_hash",
    "is_duplicate": false
  }
}
```

#### 第二阶段：关联到知识库（用户确认时）
**API**: `POST /api/v1/documents/knowledge-bases/{kb_id}/documents/attach`

**功能**：
1. 验证知识库是否存在
2. 验证文档是否存在
3. 检查是否已关联（去重）
4. 批量创建 `knowledge_base_documents` 记录
5. 触发异步解析任务

**请求**：
```json
{
  "document_ids": ["doc_id_1", "doc_id_2"],
  "folder_id": "folder_id_or_null"
}
```

**返回**：
```json
{
  "success": true,
  "message": "关联完成：成功 2 个，跳过 0 个，失败 0 个",
  "data": {
    "success_count": 2,
    "duplicate_count": 0,
    "failed_count": 0,
    "details": [
      {
        "document_id": "doc_id_1",
        "name": "文件1.pdf",
        "status": "success",
        "kb_doc_id": "kb_doc_id_1",
        "message": "关联成功"
      }
    ]
  }
}
```

## 前端实现

### API 客户端 (`src/lib/api/document.ts`)

```typescript
// 第一阶段：上传文件
export async function uploadDocument(
  file: File,
  onProgress?: (progress: number) => void
): Promise<{ success: boolean; message: string; data: DocumentUploadResponse }>

// 第二阶段：关联到知识库
export async function attachDocumentsToKB(
  kbId: string,
  documentIds: string[],
  folderId?: string | null
): Promise<{ success: boolean; message: string; data: AttachDocumentsResponse }>
```

### Hook (`use-file-upload.ts`)

```typescript
export function useFileUpload() {
  // 第一阶段：上传队列
  const processUploadQueue = async () => { ... }
  
  // 第二阶段：关联到知识库
  const attachToKnowledgeBase = async (options: UploadOptions) => { ... }
  
  return {
    uploadFiles,
    addFiles,
    processUploadQueue,
    attachToKnowledgeBase,
    isUploading,
    isAllUploaded,
    isAttaching,
    ...
  }
}
```

### 上传对话框 (`file-upload-dialog.tsx`)

**用户体验**：
1. 用户选择文件 → 自动开始上传（第一阶段）
2. 显示上传进度
3. 上传完成后，用户点击"保存" → 关联到知识库（第二阶段）
4. 显示关联结果

## 核心优势

### 1. 符合数据库设计理念
- `documents` 表：纯物理资产，与业务解耦
- `knowledge_base_documents` 表：业务关联，支持一份文件挂载到多个知识库

### 2. 支持秒传
- 同一租户内，相同 `content_hash` 的文件只存储一份
- 第一阶段检测到重复文件，直接返回已有 `document_id`

### 3. 支持批量关联
- 第二阶段可以批量关联多个文档到知识库
- 支持去重检测（同一文件夹内）

### 4. 灵活的业务逻辑
- 用户可以先上传文件，稍后再决定关联到哪个知识库
- 同一文件可以关联到多个知识库（不同的 `folder_id`）

## 数据库表结构

### documents 表（物理资产）
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    owner_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20),
    storage_driver VARCHAR(20) DEFAULT 'local',
    bucket_name VARCHAR(100),
    file_key VARCHAR(512) NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    source_type VARCHAR(50) DEFAULT 'file',
    source_url TEXT,
    content_hash VARCHAR(64),  -- SHA256，用于去重
    metadata JSONB DEFAULT '{}'::jsonb,
    created_by_id UUID,
    created_by_name VARCHAR(255),
    updated_by_id UUID,
    updated_by_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_docs_tenant_hash ON documents(tenant_id, content_hash);
```

### knowledge_base_documents 表（业务关联）
```sql
CREATE TABLE knowledge_base_documents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    kb_id UUID NOT NULL,
    document_id UUID NOT NULL,
    folder_id UUID,
    status VARCHAR(50) DEFAULT 'pending',
    chunks_count INTEGER DEFAULT 0,
    summary TEXT,
    parse_config JSONB,
    parsing_logs JSONB DEFAULT '[]'::jsonb,
    parse_started_at TIMESTAMPTZ,
    parse_ended_at TIMESTAMPTZ,
    parse_duration_milliseconds BIGINT,
    is_enabled BOOLEAN DEFAULT true,
    created_by_id UUID,
    created_by_name VARCHAR(255),
    updated_by_id UUID,
    updated_by_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_kbd_rel ON knowledge_base_documents(kb_id, document_id);
CREATE INDEX idx_kbd_status ON knowledge_base_documents(status);
```

## 文件清单

### 后端
- `genesis-ai-platform/api/v1/documents.py` - 重构后的 API
  - `POST /documents/upload` - 纯文件上传
  - `POST /documents/knowledge-bases/{kb_id}/documents/attach` - 关联到知识库

### 前端
- `genesis-ai-frontend/src/lib/api/document.ts` - API 客户端
- `genesis-ai-frontend/src/features/knowledge-base/detail/components/file-manager/file-browser/hooks/use-file-upload.ts` - 上传 Hook
- `genesis-ai-frontend/src/features/knowledge-base/detail/components/file-manager/file-browser/dialogs/file-upload-dialog.tsx` - 上传对话框

## 测试建议

### 场景 1：正常上传
1. 选择文件 → 自动上传 → 点击"保存" → 关联成功

### 场景 2：秒传
1. 上传文件 A → 成功
2. 再次上传相同文件 A → 秒传（is_duplicate: true）
3. 点击"保存" → 关联成功

### 场景 3：重复关联
1. 上传文件 A → 关联到文件夹 F1 → 成功
2. 再次上传文件 A → 关联到文件夹 F1 → 提示"文件已存在于当前位置"

### 场景 4：多知识库挂载
1. 上传文件 A → 关联到知识库 KB1 → 成功
2. 上传文件 A → 关联到知识库 KB2 → 成功（同一物理文件，两个业务关联）

## 后续优化

1. **异步解析任务**：在 `attach` API 中触发 Celery 任务
2. **进度追踪**：通过 WebSocket 实时推送解析进度
3. **批量操作**：支持批量删除、批量移动等
4. **权限控制**：基于 `resource_permissions` 表实现细粒度权限
