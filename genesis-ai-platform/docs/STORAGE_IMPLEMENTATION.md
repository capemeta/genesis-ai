# 存储驱动实现说明

## 概述

本项目现已支持两种存储驱动：
1. **本地文件系统（local）** - 新增
2. **S3 兼容存储（s3）** - 已有

## 新增功能

### 1. 本地存储驱动（LocalStorageDriver）

**文件位置**：`core/storage/local_driver.py`

**核心特性**：
- ✅ 支持相对路径和绝对路径
- ✅ 自动创建目录结构
- ✅ 自动清理空目录
- ✅ 完整的异步 API
- ✅ 与 S3 驱动相同的接口

**路径处理**：
- **相对路径**：相对于项目根目录（main.py 所在目录）
  - 示例：`./storage`, `storage`, `./data/files`
  - 推荐用于开发环境
- **绝对路径**：直接使用指定的路径
  - Linux: `/var/lib/genesis-ai/storage`
  - Windows: `C:/data/genesis-ai/storage`
  - 推荐用于生产环境

### 2. 存储驱动工厂（get_storage_driver）

**文件位置**：`core/storage/__init__.py`

**功能**：根据配置自动选择合适的存储驱动

```python
from core.storage import get_storage_driver

# 自动根据配置选择驱动
storage = get_storage_driver()

# 或指定驱动类型
local_storage = get_storage_driver("local")
s3_storage = get_storage_driver("s3")
```

### 3. 统一的存储接口

所有存储驱动实现相同的接口（`StorageDriver`）：

```python
# 上传文件
await storage.upload(file, key, content_type, metadata)

# 下载文件
await storage.download(key, destination)

# 获取文件内容
content = await storage.get_content(key)

# 检查文件是否存在
exists = await storage.exists(key)

# 删除文件
await storage.delete(key)

# 获取访问 URL
url = await storage.get_url(key, expires_in)
```

## 配置说明

### 环境变量配置

**使用本地存储**：
```env
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=./storage-data
```

**使用 S3 存储**：
```env
STORAGE_DRIVER=s3
SEAWEEDFS_ENDPOINT=http://localhost:8333
SEAWEEDFS_ACCESS_KEY=your-access-key
SEAWEEDFS_SECRET_KEY=your-secret-key
SEAWEEDFS_BUCKET=genesis-ai-files
```

### 最佳实践

**开发环境**：
```env
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=./storage-data
```

**生产环境（单机）**：
```env
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=/var/lib/genesis-ai/storage
```

**生产环境（分布式）**：
```env
STORAGE_DRIVER=s3
# ... S3 配置
```

## 代码更新

### 1. 文档上传/下载 API

**文件**：`api/v1/documents.py`

**更新内容**：
- 使用 `get_storage_driver()` 替代 `get_s3_driver()`
- 根据配置自动选择存储驱动
- 支持本地存储和 S3 存储

**关键代码**：
```python
from core.storage import get_storage_driver

# 上传
storage_driver = get_storage_driver()
await storage_driver.upload(file=file.file, key=file_key, ...)

# 下载
storage_driver = get_storage_driver()
file_content = await storage_driver.get_content(document.file_key)
```

### 2. RAG 解析服务

**文件**：
- `rag/service/parsing_service.py`
- `rag/chunking/tasks/parse_task.py`

**更新内容**：
- 使用 `get_storage_driver()` 替代 `get_s3_driver()`
- 支持从本地存储或 S3 加载文件

### 3. Document 模型

**文件**：`models/document.py`

**更新内容**：
- `storage_driver` 字段现在根据配置自动设置
- 支持 `local` 和 `s3` 两种值

## 文件下载功能保证

### 1. 本地存储下载

**实现方式**：
- 直接读取本地文件内容
- 通过 `get_content()` 方法返回字节流
- 后端 API 代理下载（推荐）

**代码示例**：
```python
# 获取文件内容
storage_driver = get_storage_driver()
file_content = await storage_driver.get_content(document.file_key)

# 返回文件流
return Response(
    content=file_content,
    media_type=document.mime_type,
    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
)
```

### 2. S3 存储下载

**实现方式**：
- 通过 S3 API 获取文件内容
- 支持预签名 URL（可选）
- 后端 API 代理下载（推荐）

### 3. 中文文件名支持

**实现**：
- 使用 RFC 6266 标准
- 同时提供 `filename` 和 `filename*` 参数
- 支持所有现代浏览器

**代码示例**：
```python
def _build_content_disposition(filename: str) -> str:
    import urllib.parse
    encoded_filename = urllib.parse.quote(filename, safe='')
    
    try:
        ascii_filename = filename.encode('ascii').decode('ascii')
    except UnicodeEncodeError:
        name_parts = filename.rsplit('.', 1)
        ascii_filename = f"download.{name_parts[1]}" if len(name_parts) == 2 else "download"
    
    return f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
```

## 测试

### 运行测试

```bash
# 测试本地存储
cd genesis-ai-platform
uv run python test_local_storage.py
```

### 测试结果

```
============================================================
本地存储驱动测试
============================================================

1. 初始化驱动（相对路径）
   存储根目录: D:\workspace\python\genesis-ai\genesis-ai-platform\test_storage

2. 测试文件上传
   上传成功: test/xxx/test.txt

3. 测试文件存在检查
   文件存在: True

4. 测试获取文件内容
   内容匹配: True

5. 测试下载文件
   下载内容匹配: True

6. 测试获取 URL
   文件 URL: D:\workspace\...\test.txt

7. 测试删除文件
   删除后文件存在: False

8. 测试绝对路径初始化
   存储根目录: D:\workspace\...\test_storage_abs

9. 清理测试目录
   清理完成

============================================================
✅ 所有测试通过！
============================================================
```

## 迁移指南

### 从 S3 切换到本地存储

1. 修改 `.env` 配置：
```env
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=./storage
```

2. 下载 S3 中的文件到本地：
```bash
aws s3 sync s3://genesis-ai-files ./storage
```

3. 更新数据库（可选）：
```sql
UPDATE documents SET storage_driver = 'local' WHERE storage_driver = 's3';
```

### 从本地存储切换到 S3

1. 上传本地文件到 S3：
```bash
aws s3 sync ./storage s3://genesis-ai-files
```

2. 修改 `.env` 配置：
```env
STORAGE_DRIVER=s3
SEAWEEDFS_ENDPOINT=http://localhost:8333
# ... 其他 S3 配置
```

3. 更新数据库（可选）：
```sql
UPDATE documents SET storage_driver = 's3' WHERE storage_driver = 'local';
```

## 相关文档

- **详细文档**：`core/storage/README.md`
- **测试脚本**：`test_local_storage.py`
- **配置示例**：`.env.example`

## 注意事项

1. **生产环境建议**：
   - 单机部署：使用本地存储 + 绝对路径
   - 分布式部署：使用 S3 存储

2. **备份策略**：
   - 本地存储：定期备份存储目录
   - S3 存储：启用版本控制和跨区域复制

3. **权限管理**：
   - 本地存储：确保应用有读写权限
   - S3 存储：配置正确的 IAM 策略

4. **性能考虑**：
   - 本地存储：受限于磁盘 I/O
   - S3 存储：受限于网络带宽

5. **文件下载**：
   - 推荐通过后端 API 代理下载
   - 支持权限控制和审计
   - 支持中文文件名
