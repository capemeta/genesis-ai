# SeaweedFS 路径设计说明

## 设计原则

### 1. 租户隔离
所有路径以 `tenant_id` 开头，确保多租户数据物理隔离。

### 2. 资源分类
按业务类型分目录：
- `documents/` - 知识库文档
- `avatars/` - 用户头像
- `exports/` - 导出文件
- `chunks/` - 文档分块
- `temp/` - 临时文件

### 3. 时间分区
使用 `year/month` 分区，避免单目录文件过多：
- 便于按时间清理
- 提高列表性能
- 支持按时间统计

### 4. 唯一标识
使用 UUID 避免文件名冲突：
- 防止并发上传冲突
- 避免热点分区
- 支持秒传（基于 content_hash）

### 5. 路径深度控制
- 最大深度：6 层
- 推荐深度：4-5 层
- 避免超过 7 层（影响性能）

## 路径结构

```
genesis-ai-files/                    # Bucket
  └── {tenant_id}/                   # 租户隔离（第1层）
      ├── documents/                 # 文档类型（第2层）
      │   ├── kb-{kb_id}/           # 知识库分组（第3层）
      │   │   └── {year}/{month}/   # 时间分区（第4-5层）
      │   │       └── {uuid}{ext}   # 文件（第6层）
      │   └── temp/                 # 临时文档（第3层）
      │       └── {year}/{month}/   # 时间分区（第4-5层）
      │           └── {uuid}{ext}   # 文件（第6层）
      ├── avatars/                  # 头像（第2层）
      │   └── {user_id}{ext}       # 文件（第3层，直接覆盖）
      ├── exports/                  # 导出文件（第2层）
      │   └── {year}/{month}/      # 时间分区（第3-4层）
      │       └── {uuid}{ext}      # 文件（第5层）
      ├── chunks/                   # 文档分块（第2层）
      │   └── doc-{document_id}/   # 文档分组（第3层）
      │       └── {uuid}.json      # 分块文件（第4层）
      └── temp/                     # 临时文件（第2层）
          └── {year}/{month}/      # 时间分区（第3-4层）
              └── {uuid}{ext}      # 文件（第5层）
```

## 路径示例

### 1. 知识库文档

**未关联知识库（临时）**：
```
550e8400-e29b-41d4-a716-446655440000/documents/temp/2024/01/a1b2c3d4-e5f6-7890-abcd-ef1234567890.pdf
```

**已关联知识库**：
```
550e8400-e29b-41d4-a716-446655440000/documents/kb-660e8400-e29b-41d4-a716-446655440001/2024/01/a1b2c3d4-e5f6-7890-abcd-ef1234567890.pdf
```

**优点**：
- 按知识库分组，便于批量操作
- 时间分区，便于统计和清理
- UUID 文件名，避免冲突

### 2. 用户头像

```
550e8400-e29b-41d4-a716-446655440000/avatars/770e8400-e29b-41d4-a716-446655440002.jpg
```

**优点**：
- 简单直接，路径固定
- 自动覆盖旧头像，节省存储
- 便于 CDN 缓存（添加版本参数 `?v=timestamp`）

**注意**：
- 前端请求时添加时间戳参数避免缓存：`/avatars/user-id.jpg?v=1704067200`
- 或使用 ETag 机制

### 3. 导出文件

```
550e8400-e29b-41d4-a716-446655440000/exports/2024/01/export-a1b2c3d4-e5f6-7890-abcd-ef1234567890.zip
```

**优点**：
- 按时间分区，便于清理过期导出
- UUID 文件名，避免冲突

### 4. 文档分块

```
550e8400-e29b-41d4-a716-446655440000/chunks/doc-880e8400-e29b-41d4-a716-446655440003/chunk-a1b2c3d4.json
```

**优点**：
- 按文档分组，便于批量操作
- 删除文档时可以一次性删除所有分块
- 不使用时间分区，避免路径过深

### 5. 临时文件

```
550e8400-e29b-41d4-a716-446655440000/temp/2024/01/temp-a1b2c3d4-e5f6-7890-abcd-ef1234567890.tmp
```

**优点**：
- 时间分区，便于按时间清理
- 独立目录，不影响业务文件

## 使用场景

### 场景 1：文档上传流程

```python
from core.storage.path_utils import generate_storage_path

# 1. 用户上传文档（未关联知识库）
file_key = generate_storage_path(
    tenant_id=tenant_id,
    filename="report.pdf",
    resource_type="documents",
    kb_id=None  # 临时文档
)
# 结果: tenant-uuid/documents/temp/2024/01/uuid.pdf

# 2. 用户将文档添加到知识库
new_file_key = generate_storage_path(
    tenant_id=tenant_id,
    filename="report.pdf",
    resource_type="documents",
    kb_id=kb_id  # 指定知识库
)
# 结果: tenant-uuid/documents/kb-kb-uuid/2024/01/uuid.pdf

# 3. 使用 S3 API 移动文件
await s3_driver.copy(old_key=file_key, new_key=new_file_key)
await s3_driver.delete(file_key)
```

### 场景 2：批量操作

```python
from core.storage.path_utils import get_kb_document_prefix

# 列出知识库的所有文档
prefix = get_kb_document_prefix(tenant_id, kb_id)
# 结果: tenant-uuid/documents/kb-kb-uuid/

objects = await s3_driver.list_objects(prefix=prefix)

# 删除知识库的所有文档
for obj in objects:
    await s3_driver.delete(obj['Key'])
```

### 场景 3：清理临时文件

```python
from core.storage.path_utils import get_temp_files_prefix
from datetime import datetime, timedelta

# 清理 7 天前的临时文件
cutoff_date = datetime.utcnow() - timedelta(days=7)
year = cutoff_date.strftime("%Y")
month = cutoff_date.strftime("%m")

prefix = get_temp_files_prefix(tenant_id, year, month)
# 结果: tenant-uuid/temp/2024/01/

objects = await s3_driver.list_objects(prefix=prefix)
for obj in objects:
    if obj['LastModified'] < cutoff_date:
        await s3_driver.delete(obj['Key'])
```

### 场景 4：头像上传

```python
from core.storage.path_utils import generate_storage_path, get_user_avatar_path

# 方式 1：使用 generate_storage_path
file_key = generate_storage_path(
    tenant_id=tenant_id,
    filename="avatar.jpg",
    resource_type="avatars",
    user_id=user_id
)
# 结果: tenant-uuid/avatars/user-uuid.jpg

# 方式 2：使用 get_user_avatar_path（推荐）
file_key = get_user_avatar_path(tenant_id, user_id, ext=".jpg")
# 结果: tenant-uuid/avatars/user-uuid.jpg

# 上传头像（自动覆盖旧头像）
await s3_driver.upload(file, file_key)

# 前端访问（添加版本参数避免缓存）
avatar_url = f"{cdn_url}/{file_key}?v={int(time.time())}"
```

## S3/SeaweedFS 最佳实践

### 1. 使用前缀而非真实目录

S3 是对象存储，没有真实的目录结构。路径中的 `/` 只是对象键的一部分。

```python
# ✅ 正确：使用前缀过滤
prefix = "tenant-uuid/documents/kb-kb-uuid/"
objects = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

# ❌ 错误：尝试列出"目录"
# S3 没有目录的概念
```

### 2. 避免热点分区

使用 UUID 而非递增 ID，避免所有请求集中在同一个分区。

```python
# ✅ 好：UUID 分散请求
file_key = f"{tenant_id}/documents/{uuid4()}.pdf"

# ❌ 差：递增 ID 导致热点
file_key = f"{tenant_id}/documents/{auto_increment_id}.pdf"
```

### 3. 合理使用分区键

使用 `tenant_id` 和 `year/month` 作为分区键：

```python
# ✅ 好：多层分区
file_key = f"{tenant_id}/documents/kb-{kb_id}/2024/01/{uuid}.pdf"

# ❌ 差：单层分区，文件过多
file_key = f"{tenant_id}/documents/{uuid}.pdf"
```

### 4. 支持批量操作

通过前缀实现批量操作：

```python
# 删除知识库的所有文档
prefix = f"{tenant_id}/documents/kb-{kb_id}/"
objects = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
for obj in objects['Contents']:
    s3_client.delete_object(Bucket=bucket, Key=obj['Key'])
```

### 5. 路径深度控制

避免路径过深影响性能：

```python
# ✅ 好：6 层深度
tenant/documents/kb-uuid/2024/01/file.pdf

# ❌ 差：9 层深度（过深）
tenant/documents/kb-uuid/2024/01/15/12/30/file.pdf
```

## 迁移策略

如果需要从旧路径迁移到新路径：

### 1. 双写策略

```python
# 同时写入新旧路径
await s3_driver.upload(file, old_path)
await s3_driver.upload(file, new_path)

# 读取时优先读新路径
try:
    return await s3_driver.download(new_path)
except NotFound:
    return await s3_driver.download(old_path)
```

### 2. 后台迁移

```python
# Celery 任务：批量迁移
@celery_app.task
def migrate_files(tenant_id: str):
    old_prefix = f"{tenant_id}/documents/"
    objects = s3_client.list_objects_v2(Bucket=bucket, Prefix=old_prefix)
    
    for obj in objects['Contents']:
        old_key = obj['Key']
        # 生成新路径
        new_key = generate_new_path(old_key)
        # 复制到新路径
        s3_client.copy_object(
            Bucket=bucket,
            CopySource={'Bucket': bucket, 'Key': old_key},
            Key=new_key
        )
        # 删除旧路径（可选，建议保留一段时间）
        # s3_client.delete_object(Bucket=bucket, Key=old_key)
```

## 监控与维护

### 1. 存储空间统计

```python
# 统计知识库占用空间
prefix = get_kb_document_prefix(tenant_id, kb_id)
objects = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
total_size = sum(obj['Size'] for obj in objects['Contents'])
```

### 2. 定期清理

```python
# 清理 30 天前的临时文件
from datetime import datetime, timedelta

cutoff_date = datetime.utcnow() - timedelta(days=30)
prefix = get_temp_files_prefix(tenant_id)
objects = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

for obj in objects['Contents']:
    if obj['LastModified'] < cutoff_date:
        s3_client.delete_object(Bucket=bucket, Key=obj['Key'])
```

### 3. 审计日志

```python
# 记录文件操作
logger.info(f"File uploaded: {file_key}, user: {user_id}, size: {file_size}")
logger.info(f"File deleted: {file_key}, user: {user_id}")
```

## 总结

这套路径设计遵循 S3/SeaweedFS 最佳实践：

✅ **租户隔离**：所有路径以 tenant_id 开头
✅ **资源分类**：按业务类型分目录
✅ **时间分区**：使用 year/month 分区
✅ **唯一标识**：使用 UUID 避免冲突
✅ **路径深度**：控制在 3-6 层
✅ **批量操作**：支持通过前缀批量操作
✅ **可维护性**：便于清理、统计、审计

这套设计可以支撑大规模文件存储，同时保持良好的性能和可维护性。
