# 文件上传功能实现说明

## 📋 功能概述

实现了完整的文件上传功能，支持：
- ✅ 文件上传到 SeaweedFS（S3 兼容存储）
- ✅ 物理去重（基于 SHA256 哈希）
- ✅ 秒传支持（相同文件直接复用）
- ✅ 重复文件检测（同一文件夹内）
- ✅ 批量上传（并发控制）
- ✅ 上传进度跟踪
- ✅ 智能提示（统一提示成功/重复/失败数量）

## 🎯 设计方案

### 1. 物理存储策略

**物理去重 + 逻辑多份**：
- **物理层面**：同一租户内，相同 `content_hash` 的文件只在 SeaweedFS 中存储一份
- **逻辑层面**：`documents` 表记录一份物理文件，`knowledge_base_documents` 表记录多份逻辑关联

**优势**：
- 节省存储空间（物理去重）
- 支持秒传（检测到相同 hash 直接复用）
- 支持同一文件在多个知识库中使用
- 支持同一文件在同一知识库的不同文件夹中使用

### 2. 数据库表设计

#### documents 表（物理文件表）
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    owner_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20),
    storage_driver VARCHAR(20) DEFAULT 'local',
    bucket_name VARCHAR(100),
    file_key VARCHAR(512) NOT NULL,          -- SeaweedFS 存储路径
    file_size BIGINT,
    mime_type VARCHAR(100),
    content_hash VARCHAR(64),                -- 🔑 SHA256 哈希，用于去重
    ...
);

CREATE INDEX idx_docs_tenant_hash ON documents(tenant_id, content_hash);
```

#### knowledge_base_documents 表（逻辑关联表）
```sql
CREATE TABLE knowledge_base_documents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    kb_id UUID NOT NULL,
    document_id UUID NOT NULL,               -- 关联物理文档
    folder_id UUID,                          -- 所在文件夹
    status VARCHAR(50) DEFAULT 'pending',    -- 解析状态
    chunks_count INTEGER DEFAULT 0,
    ...
);
```

### 3. 文件上传流程

```
┌─────────────────────────────────────────────────────────────┐
│                     文件上传流程                              │
└─────────────────────────────────────────────────────────────┘

1. 前端上传文件
   ↓
2. 后端计算文件 SHA256 Hash
   ↓
3. 检查是否重复（同一文件夹内）
   ├─ 存在 → 返回成功 + 标记 is_duplicate=true（静默成功）
   └─ 不存在 → 继续
   ↓
4. 检查物理文件是否存在（同租户内）
   ├─ 存在 → 秒传（跳到步骤 6）
   └─ 不存在 → 继续上传
   ↓
5. 上传文件到 SeaweedFS
   ├─ 生成唯一的 file_key（tenant_id/documents/year/month/uuid.ext）
   ├─ 上传到 S3
   └─ 创建 Document 记录
   ↓
6. 创建 knowledge_base_documents 关联
   ├─ 关联 kb_id、document_id、folder_id
   ├─ 设置 status = 'pending'
   └─ 返回关联 ID
   ↓
7. 触发异步解析任务（TODO）
   ├─ 解析文档内容
   ├─ 分块（chunks）
   ├─ 生成向量（embeddings）
   └─ 更新 status = 'success'
```

### 4. 重复文件处理策略

**采用"智能合并"方案**：
- 后端统一返回成功（HTTP 200）+ 标记 `is_duplicate`
- 前端批量上传时统一提示（"成功 X 个，跳过 Y 个"）
- 前端单文件上传时明确提示（"文件已存在"）

**示例**：
```typescript
// 批量上传完成后
if (successCount - duplicateCount > 0) {
  toast.success(`成功上传 ${successCount - duplicateCount} 个文件`)
}
if (duplicateCount > 0) {
  toast.info(`跳过 ${duplicateCount} 个重复文件`)
}
```

## 📁 文件结构

### 后端

```
genesis-ai-platform/
├── core/
│   └── storage/
│       ├── __init__.py
│       ├── base.py              # 存储驱动抽象基类
│       └── s3_driver.py         # S3 存储驱动（SeaweedFS）
├── api/
│   └── v1/
│       └── documents.py         # 文档上传 API
├── models/
│   ├── document.py              # Document 模型
│   └── knowledge_base_document.py  # KnowledgeBaseDocument 模型
├── schemas/
│   └── document.py              # 文档 Schema（添加 DocumentUploadResponse）
└── test_upload.py               # 上传测试脚本
```

### 前端

```
genesis-ai-frontend/
└── src/
    ├── lib/
    │   └── api/
    │       └── document.ts      # 文档上传 API 客户端
    └── features/
        └── knowledge-base/
            └── detail/
                └── components/
                    └── file-manager/
                        └── file-browser/
                            ├── hooks/
                            │   └── use-file-upload.ts  # 上传 Hook（已更新）
                            └── dialogs/
                                └── file-upload-dialog.tsx  # 上传对话框（已更新）
```

## 🔧 配置说明

### 1. 后端配置（.env）

```env
# 存储配置
STORAGE_DRIVER=s3  # 使用 S3（SeaweedFS）

# SeaweedFS S3 配置
SEAWEEDFS_ENDPOINT=http://171.35.42.139:8304
SEAWEEDFS_ACCESS_KEY=GAI_AK_G6PMXBGGLZ6M
SEAWEEDFS_SECRET_KEY=be5pC1LI5cohK26PMvmNzcBxTBaf85iMN4sdXABS
SEAWEEDFS_BUCKET=genesis-ai-files
SEAWEEDFS_REGION=us-east-1
```

### 2. SeaweedFS 配置

确保 SeaweedFS 已启动并配置了 S3 权限：

```bash
# 启动 SeaweedFS
cd docker/seaweedfs
docker-compose up -d

# 检查状态
curl http://localhost:8304
```

## 🚀 使用方法

### 1. 启动服务

```bash
# 启动后端
cd genesis-ai-platform
uv run uvicorn main:app --reload

# 启动前端
cd genesis-ai-frontend
pnpm dev
```

### 2. 测试上传

#### 方式一：使用测试脚本

```bash
cd genesis-ai-platform

# 修改 test_upload.py 中的配置
# - KB_ID: 替换为实际的知识库ID
# - USERNAME/PASSWORD: 替换为实际的登录凭证

# 运行测试
uv run python test_upload.py
```

#### 方式二：使用前端界面

1. 登录系统
2. 进入知识库详情页
3. 点击"上传文件"按钮
4. 选择文件并上传

### 3. 验证功能

**测试场景**：
1. ✅ 上传新文件 → 正常上传
2. ✅ 上传相同文件 → 检测到重复，返回成功 + 标记
3. ✅ 修改文件后上传 → 正常上传（Hash 不同）
4. ✅ 批量上传 → 统一提示成功/重复数量

## 📊 API 接口

### POST /api/v1/knowledge-bases/{kb_id}/documents/upload

**请求**：
```
Content-Type: multipart/form-data

file: File (required)
folder_id: string (optional)
```

**响应**：
```json
{
  "success": true,
  "message": "文件上传成功",
  "data": {
    "id": "uuid",
    "document_id": "uuid",
    "name": "test.pdf",
    "file_size": 1024,
    "file_type": "PDF",
    "status": "pending",
    "is_duplicate": false,
    "is_instant_upload": false
  }
}
```

**字段说明**：
- `is_duplicate`: 是否为重复文件（同一文件夹内已存在）
- `is_instant_upload`: 是否为秒传（物理文件已存在，直接复用）

## 🔍 去重逻辑

### 1. 租户级别去重

```python
# 检查同租户内是否存在相同文件
existing_doc = await session.execute(
    select(Document).where(
        Document.tenant_id == tenant_id,
        Document.content_hash == file_hash
    )
)
```

### 2. 文件夹级别去重

```python
# 检查同一文件夹内是否已经关联了该文档
existing_relation = await session.execute(
    select(KnowledgeBaseDocument)
    .join(Document)
    .where(
        KnowledgeBaseDocument.kb_id == kb_id,
        KnowledgeBaseDocument.folder_id == folder_id,
        Document.content_hash == content_hash
    )
)
```

## 🎨 前端体验

### 批量上传提示

```typescript
// 上传完成后统一提示
if (successCount - duplicateCount > 0) {
  toast.success(`成功上传 ${successCount - duplicateCount} 个文件`)
}
if (duplicateCount > 0) {
  toast.info(`跳过 ${duplicateCount} 个重复文件`)
}
if (errorCount > 0) {
  toast.error(`${errorCount} 个文件上传失败`)
}
```

### 上传进度

- 显示每个文件的上传进度
- 支持取消上传
- 支持重试失败的文件
- 支持清空列表

## 🔐 安全性

1. **文件类型验证**：只允许特定类型的文件
2. **文件大小限制**：最大 100MB
3. **租户隔离**：不同租户的文件完全隔离
4. **权限检查**：验证用户是否有权限上传到该知识库
5. **Hash 验证**：使用 SHA256 确保文件完整性
6. **中文文件名支持**：使用 URL 编码处理 S3 metadata 中的中文字符

## 📝 TODO

- [ ] 实现异步文档解析任务（Celery）
- [ ] 添加文件预览功能
- [ ] 支持更多文件类型
- [ ] 添加文件下载功能
- [ ] 实现文件删除（物理删除 vs 逻辑删除）
- [ ] 添加上传统计和监控

## 🐛 已修复的问题

### 1. S3 metadata 不支持非 ASCII 字符

**问题描述**：
```
Parameter validation failed:
Non ascii characters found in S3 metadata for key "original_filename", 
value: "98 主机防火墙策略.xls".  
S3 metadata can only contain ASCII characters.
```

**原因**：S3 的 metadata 只支持 ASCII 字符，中文文件名会导致上传失败。

**解决方案**：
```python
# 使用 URL 编码处理中文文件名
import urllib.parse
encoded_filename = urllib.parse.quote(file.filename)

await s3_driver.upload(
    file=file.file,
    key=file_key,
    content_type=file.content_type,
    metadata={
        "original_filename": encoded_filename,  # URL 编码后的文件名
        "tenant_id": str(current_user.tenant_id),
        "uploaded_by": str(current_user.id)
    }
)
```

**代码位置**：`api/v1/documents.py` 第 177-179 行

### 2. folder_id 参数处理

**问题描述**：前端可能传递 `undefined` 或字符串 `"null"`，导致后端处理异常。

**解决方案**：
```typescript
// 前端严格检查并只在有效值时添加到 FormData
if (folderId && folderId !== 'null' && folderId !== 'undefined') {
  formData.append('folder_id', folderId)
}
```

**代码位置**：`src/lib/api/document.ts` 第 33-36 行

## 📚 相关文档

- [SeaweedFS 配置说明](../docker/seaweedfs/README.md)
- [数据库设计](../doc/数据库设计.md)
- [增删改查指南](../doc/增删改查指南.md)
