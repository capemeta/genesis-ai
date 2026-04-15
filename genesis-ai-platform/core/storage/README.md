# 存储驱动系统

本项目支持多种存储驱动，可通过配置灵活切换。

## 支持的存储驱动

### 1. 本地文件系统（local）

适用于开发环境和小规模部署。

**配置示例**：
```env
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=./storage-data
```

**路径说明**：
- **相对路径**：相对于项目根目录（main.py 所在目录）
  - 示例：`./storage-data`, `storage-data`, `./data/files`
  - 推荐用于开发环境
- **绝对路径**：直接使用指定的路径
  - Linux: `/var/lib/genesis-ai/storage`
  - Windows: `C:/data/genesis-ai/storage`
  - 推荐用于生产环境

**优点**：
- 简单易用，无需额外服务
- 适合开发和测试
- 文件直接可访问

**缺点**：
- 不支持分布式部署
- 无法跨服务器共享文件
- 缺少高级功能（CDN、预签名 URL 等）

### 2. S3 兼容存储（s3）

支持 AWS S3、SeaweedFS、MinIO 等 S3 兼容的对象存储。

**配置示例**：
```env
STORAGE_DRIVER=s3
SEAWEEDFS_ENDPOINT=http://localhost:8333
SEAWEEDFS_ACCESS_KEY=your-access-key
SEAWEEDFS_SECRET_KEY=your-secret-key
SEAWEEDFS_BUCKET=genesis-ai-files
SEAWEEDFS_REGION=us-east-1
```

**优点**：
- 支持分布式部署
- 高可用、高扩展性
- 支持预签名 URL
- 支持 CDN 加速

**缺点**：
- 需要额外的存储服务
- 配置相对复杂

## 使用方法

### 基本使用

```python
from core.storage import get_storage_driver

# 获取存储驱动（自动根据配置选择）
storage = get_storage_driver()

# 上传文件
await storage.upload(
    file=file_object,
    key="tenant-id/documents/2024/01/file.pdf",
    content_type="application/pdf",
    metadata={"tenant_id": "xxx"}
)

# 下载文件
await storage.download(
    key="tenant-id/documents/2024/01/file.pdf",
    destination=Path("/tmp/file.pdf")
)

# 获取文件内容
content = await storage.get_content("tenant-id/documents/2024/01/file.pdf")

# 检查文件是否存在
exists = await storage.exists("tenant-id/documents/2024/01/file.pdf")

# 删除文件
await storage.delete("tenant-id/documents/2024/01/file.pdf")

# 获取访问 URL
url = await storage.get_url("tenant-id/documents/2024/01/file.pdf", expires_in=3600)
```

### 指定驱动类型

```python
from core.storage import get_storage_driver

# 强制使用本地存储
local_storage = get_storage_driver("local")

# 强制使用 S3 存储
s3_storage = get_storage_driver("s3")
```

### 直接使用特定驱动

```python
from core.storage.local_driver import get_local_driver
from core.storage.s3_driver import get_s3_driver

# 本地存储
local = get_local_driver("./storage")

# S3 存储
s3 = get_s3_driver()
```

## 文件路径规范

所有存储驱动使用统一的路径规范（参考 `path_utils.py`）：

```
{tenant_id}/
  ├── documents/          # 文档
  │   └── {year}/{month}/
  │       └── {document_id}.{ext}
  ├── avatars/            # 头像
  │   └── {user_id}.{ext}
  ├── exports/            # 导出文件
  │   └── {year}/{month}/
  │       └── {uuid}.{ext}
  ├── chunks/             # 文档分块
  │   └── doc-{document_id}/
  │       └── {uuid}.json
  └── temp/               # 临时文件
      └── {year}/{month}/
          └── {uuid}.{ext}
```

## 最佳实践

### 开发环境

```env
# 使用本地存储，相对路径
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=./storage-data
```

### 生产环境

```env
# 使用 S3 存储
STORAGE_DRIVER=s3
SEAWEEDFS_ENDPOINT=https://s3.example.com
SEAWEEDFS_ACCESS_KEY=prod-access-key
SEAWEEDFS_SECRET_KEY=prod-secret-key
SEAWEEDFS_BUCKET=genesis-ai-files
```

或使用本地存储（单机部署）：

```env
# 使用本地存储，绝对路径
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=/var/lib/genesis-ai/storage
```

### 文件下载

推荐通过后端 API 代理下载，而不是直接暴露存储路径：

```python
# ✅ 推荐：通过 API 代理
@router.post("/documents/download")
async def download_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user)
):
    # 1. 权限检查
    # 2. 从存储获取文件
    # 3. 返回文件流
    storage = get_storage_driver()
    content = await storage.get_content(document.file_key)
    return Response(content=content, media_type=document.mime_type)

# ❌ 不推荐：直接返回存储路径
# 安全风险：暴露内部路径，无法进行权限控制
```

## 迁移指南

### 从 S3 迁移到本地存储

1. 修改配置：
```env
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=/var/lib/genesis-ai/storage
```

2. 迁移文件：
```bash
# 使用 s3cmd 或 aws cli 下载所有文件
aws s3 sync s3://genesis-ai-files /var/lib/genesis-ai/storage
```

3. 更新数据库：
```sql
UPDATE documents SET storage_driver = 'local' WHERE storage_driver = 's3';
```

### 从本地存储迁移到 S3

1. 上传文件到 S3：
```bash
aws s3 sync /var/lib/genesis-ai/storage s3://genesis-ai-files
```

2. 修改配置：
```env
STORAGE_DRIVER=s3
SEAWEEDFS_ENDPOINT=https://s3.example.com
# ... 其他 S3 配置
```

3. 更新数据库：
```sql
UPDATE documents SET storage_driver = 's3' WHERE storage_driver = 'local';
```

## 测试

运行测试脚本验证存储驱动：

```bash
# 测试本地存储
cd genesis-ai-platform
uv run python test_local_storage.py

# 测试 S3 存储（需要先配置 S3）
# 修改 .env 中的 STORAGE_DRIVER=s3
uv run python -m pytest tests/test_storage.py
```

## 故障排查

### 本地存储

**问题：权限不足**
```
PermissionError: [Errno 13] Permission denied: '/var/lib/genesis-ai/storage'
```

解决方法：
```bash
# 确保目录存在且有写权限
sudo mkdir -p /var/lib/genesis-ai/storage
sudo chown -R $USER:$USER /var/lib/genesis-ai/storage
```

**问题：磁盘空间不足**
```
OSError: [Errno 28] No space left on device
```

解决方法：
- 清理临时文件
- 扩展磁盘空间
- 迁移到 S3 存储

### S3 存储

**问题：连接失败**
```
ClientError: Unable to connect to endpoint
```

解决方法：
- 检查 SEAWEEDFS_ENDPOINT 配置
- 确保网络连通性
- 检查防火墙设置

**问题：认证失败**
```
ClientError: The AWS Access Key Id you provided does not exist
```

解决方法：
- 检查 ACCESS_KEY 和 SECRET_KEY
- 确保凭证有效且未过期

## 扩展开发

### 添加新的存储驱动

1. 创建驱动类（继承 `StorageDriver`）：

```python
# core/storage/custom_driver.py
from core.storage.base import StorageDriver

class CustomStorageDriver(StorageDriver):
    async def upload(self, file, key, content_type=None, metadata=None):
        # 实现上传逻辑
        pass
    
    async def download(self, key, destination):
        # 实现下载逻辑
        pass
    
    # ... 实现其他方法
```

2. 在工厂方法中注册：

```python
# core/storage/__init__.py
def get_storage_driver(driver_type=None):
    # ...
    elif driver == "custom":
        return get_custom_driver()
```

3. 更新配置：

```python
# core/config/settings.py
STORAGE_DRIVER: str = "local"  # local, s3, custom
```
