# SeaweedFS Docker 部署

SeaweedFS 是一个简单且高度可扩展的分布式文件系统，支持 S3 API。

## 架构组件

### 开发环境（单节点）
使用 `weed server` 命令一次性启动所有组件：
- **Master**: 集群管理和元数据服务
- **Volume**: 数据存储服务
- **Filer**: 文件系统接口和元数据管理
- **S3**: S3 兼容 API 服务

### 生产环境（多节点）
使用 `docker-compose.prod.yml` 部署高可用集群：
- 3 个 Master 节点（高可用）
- 3 个 Volume 节点（数据冗余）
- 1 个 Filer 节点
- 1 个 S3 服务

## 性能与资源占用

### 内存占用

SeaweedFS 非常轻量，单节点开发环境：

- **空闲状态**：约 50-80 MB
- **轻度使用**：约 100-150 MB
- **中度使用**：约 200-300 MB
- **配置限制**：最大 512 MB（开发环境足够）

对比其他对象存储：
- MinIO：约 200-500 MB（空闲）
- Ceph：约 1-2 GB（最小配置）
- SeaweedFS：约 50-150 MB ✅

### CPU 占用

- **空闲**：< 1%
- **上传/下载**：5-15%（取决于文件大小）
- **配置限制**：最大 1 个 CPU 核心

### 磁盘占用

- **程序本身**：约 50 MB（Docker 镜像）
- **元数据**：每 1000 个文件约 1-2 MB
- **数据文件**：实际文件大小（支持压缩）

### 资源限制配置

在 `docker-compose.yml` 中已配置资源限制：

```yaml
deploy:
  resources:
    limits:
      memory: 512M      # 最大 512MB（可根据需要调整）
      cpus: '1.0'       # 最大 1 核心
    reservations:
      memory: 128M      # 预留 128MB
      cpus: '0.25'      # 预留 0.25 核心
```

如果你的机器资源紧张，可以进一步降低：

```yaml
limits:
  memory: 256M      # 最小可用配置
  cpus: '0.5'
```

## 快速开始

### 1. 启动服务

```powershell
cd docker\seaweedfs

# PowerShell
.\start.ps1

# 或 CMD
start.bat

# 或 Linux/macOS
chmod +x start.sh stop.sh
./start.sh
```

服务启动后，访问：
- **Master UI**: http://localhost:8301
- **Volume UI**: http://localhost:8302/ui/index.html
- **Filer UI**: http://localhost:8303
- **S3 API**: http://localhost:8304

### 2. 修改 S3 访问密钥（生产环境必须）

**重要**：默认密钥仅供开发测试，生产环境必须修改！

编辑 `config/s3.json`：
```json
{
  "identities": [
    {
      "name": "admin",
      "credentials": [
        {
          "accessKey": "your_custom_admin_key",      // 修改这里
          "secretKey": "your_custom_admin_secret"    // 修改这里
        }
      ],
      "actions": ["Admin", "Read", "Write"]
    },
    {
      "name": "readwrite",
      "credentials": [
        {
          "accessKey": "your_custom_app_key",        // 修改这里
          "secretKey": "your_custom_app_secret"      // 修改这里
        }
      ],
      "actions": ["Read", "Write"]
    }
  ]
}
```

重启服务使配置生效：
```powershell
docker compose restart
```

### 3. 配置应用程序

在 `genesis-ai-platform/.env` 中添加：

```env
# SeaweedFS S3 配置
SEAWEEDFS_ENDPOINT=http://localhost:8304
SEAWEEDFS_ACCESS_KEY=GAI_AK_G6PMXBGGLZ6M        # 与 s3.json 中的 readwrite 用户一致
SEAWEEDFS_SECRET_KEY=be5pC1LI5cohK26PMvmNzcBxTBaf85iMN4sdXABS     # 与 s3.json 中的 readwrite 用户一致
SEAWEEDFS_BUCKET=genesis-ai-files
SEAWEEDFS_REGION=us-east-1
```

**注意**：
- ❌ SeaweedFS 不支持通过环境变量配置 S3 权限
- ✅ S3 权限必须在 `config/s3.json` 中配置
- ✅ 应用程序通过环境变量连接 SeaweedFS
- ✅ 应用程序应使用 `readwrite` 用户（最小权限原则）

### 4. 测试 S3 API

使用 AWS CLI 测试（需要先安装 AWS CLI）：

```powershell
# 配置 AWS CLI
aws configure set aws_access_key_id GAI_AK_G6PMXBGGLZ6M
aws configure set aws_secret_access_key be5pC1LI5cohK26PMvmNzcBxTBaf85iMN4sdXABS
aws configure set default.region us-east-1

# 创建 bucket
aws --endpoint-url http://localhost:8304 s3 mb s3://test-bucket

# 上传文件
aws --endpoint-url http://localhost:8304 s3 cp test.txt s3://test-bucket/

# 列出文件
aws --endpoint-url http://localhost:8304 s3 ls s3://test-bucket/

# 下载文件
aws --endpoint-url http://localhost:8304 s3 cp s3://test-bucket/test.txt downloaded.txt
```

或使用 Python boto3：

```python
import boto3

# 创建 S3 客户端
s3 = boto3.client(
    's3',
    endpoint_url='http://localhost:8304',
    aws_access_key_id='GAI_AK_G6PMXBGGLZ6M',
    aws_secret_access_key='be5pC1LI5cohK26PMvmNzcBxTBaf85iMN4sdXABS',
    region_name='us-east-1'
)

# 创建 bucket
s3.create_bucket(Bucket='test-bucket')

# 上传文件
s3.upload_file('test.txt', 'test-bucket', 'test.txt')

# 列出文件
response = s3.list_objects_v2(Bucket='test-bucket')
for obj in response.get('Contents', []):
    print(obj['Key'])

# 下载文件
s3.download_file('test-bucket', 'test.txt', 'downloaded.txt')
```

## 配置说明

### 开发环境 vs 生产环境

**开发环境** (`docker-compose.yml`):
- 单节点部署，所有组件在一个容器中
- 无副本策略（节省资源）
- 适合本地开发和测试

**生产环境** (`docker-compose.prod.yml`):
- 多节点部署，高可用
- 副本策略：`010`（同数据中心不同机架）
- 3 个 Master 节点 + 3 个 Volume 节点

### 副本策略（生产环境）

- `000`: 无副本（默认，适合开发环境）
- `001`: 1个副本在同一机架
- `010`: 1个副本在同一数据中心的不同机架
- `100`: 1个副本在不同数据中心

生产环境建议使用 `010` 或 `100`。

### Filer 元数据存储

**开发环境**：默认使用内置的 LevelDB（存储在 `./data` 目录）

**生产环境**：建议使用 PostgreSQL 或 Redis
1. 编辑 `config/filer.toml`
2. 启用 `[postgres]` 或 `[redis2]` 配置
3. 禁用 `[leveldb2]`

### S3 权限配置详解

SeaweedFS 的 S3 API 通过 `config/s3.json` 文件管理访问控制。

#### 配置文件结构

```json
{
  "identities": [
    {
      "name": "admin",              // 用户身份名称（仅用于标识）
      "credentials": [              // 访问凭证列表（可以有多个）
        {
          "accessKey": "admin_access_key",    // S3 Access Key（类似用户名）
          "secretKey": "admin_secret_key"     // S3 Secret Key（类似密码）
        }
      ],
      "actions": [                  // 权限列表
        "Admin",                    // 管理权限（可以管理其他用户）
        "Read",                     // 读权限（下载、列出文件）
        "Write"                     // 写权限（上传、删除文件）
      ]
    }
  ]
}
```

#### 权限说明

| 权限 | 说明 | 允许的操作 |
|------|------|-----------|
| **Admin** | 管理员权限 | 所有操作 + 管理其他用户 |
| **Read** | 读权限 | `GET`、`HEAD`、`LIST` 操作（下载、查看、列出） |
| **Write** | 写权限 | `PUT`、`POST`、`DELETE` 操作（上传、删除） |

#### 预配置的三个用户

**1. admin（管理员）**
```json
{
  "name": "admin",
  "credentials": [
    {
      "accessKey": "<YOUR_ADMIN_ACCESS_KEY>",
      "secretKey": "<YOUR_ADMIN_SECRET_KEY>"
    }
  ],
  "actions": ["Admin", "Read", "Write"]
}
```
- **用途**：系统管理员，拥有所有权限
- **权限**：可以创建/删除 bucket，上传/下载/删除文件，管理其他用户
- **使用场景**：后台管理、系统维护

**2. readwrite（读写用户）**
```json
{
  "name": "readwrite",
  "credentials": [
    {
      "accessKey": "<YOUR_READWRITE_ACCESS_KEY>",
      "secretKey": "<YOUR_READWRITE_SECRET_KEY>"
    }
  ],
  "actions": ["Read", "Write"]
}
```
- **用途**：应用程序使用的账号
- **权限**：可以上传、下载、删除文件，但不能管理用户
- **使用场景**：应用程序文件存储（推荐）

**3. readonly（只读用户）**
```json
{
  "name": "readonly",
  "credentials": [
    {
      "accessKey": "<YOUR_READONLY_ACCESS_KEY>",
      "secretKey": "<YOUR_READONLY_SECRET_KEY>"
    }
  ],
  "actions": ["Read"]
}
```
- **用途**：只读访问
- **权限**：只能下载和查看文件，不能上传或删除
- **使用场景**：公开下载、数据分析、备份恢复

#### 如何修改密钥

**重要**：生产环境必须修改默认密钥！

1. 编辑 `config/s3.json`：
```json
{
  "identities": [
    {
      "name": "admin",
      "credentials": [
        {
          "accessKey": "your_custom_access_key",      // 修改这里
          "secretKey": "your_custom_secret_key_123"   // 修改这里
        }
      ],
      "actions": ["Admin", "Read", "Write"]
    }
  ]
}
```

2. 重启服务使配置生效：
```powershell
docker compose restart
```

3. 更新应用程序配置（在 `genesis-ai-platform/.env` 中）：
```env
SEAWEEDFS_ACCESS_KEY=your_custom_app_key
SEAWEEDFS_SECRET_KEY=your_custom_app_secret
```

#### 添加新用户

如果需要为不同的应用或团队创建独立账号：

```json
{
  "identities": [
    {
      "name": "admin",
      "credentials": [
        {
          "accessKey": "<YOUR_ADMIN_ACCESS_KEY>",
          "secretKey": "<YOUR_ADMIN_SECRET_KEY>"
        }
      ],
      "actions": ["Admin", "Read", "Write"]
    },
    {
      "name": "app1",                    // 新增：应用1
      "credentials": [
        {
          "accessKey": "app1_key",
          "secretKey": "app1_secret"
        }
      ],
      "actions": ["Read", "Write"]
    },
    {
      "name": "app2",                    // 新增：应用2
      "credentials": [
        {
          "accessKey": "app2_key",
          "secretKey": "app2_secret"
        }
      ],
      "actions": ["Read"]               // 只读权限
    }
  ]
}
```

#### 一个用户多个密钥

一个用户可以有多个访问密钥（用于密钥轮换）：

```json
{
  "name": "admin",
  "credentials": [
    {
      "accessKey": "admin_key_old",      // 旧密钥（即将废弃）
      "secretKey": "admin_secret_old"
    },
    {
      "accessKey": "admin_key_new",      // 新密钥
      "secretKey": "admin_secret_new"
    }
  ],
  "actions": ["Admin", "Read", "Write"]
}
```

这样可以在不中断服务的情况下更换密钥：
1. 添加新密钥
2. 更新应用程序使用新密钥
3. 删除旧密钥

#### 安全建议

1. **生产环境必须修改默认密钥**
2. **使用强密码**：至少 20 个字符，包含大小写字母、数字、特殊字符
3. **最小权限原则**：应用程序使用 `readwrite` 账号，不要使用 `admin`
4. **定期轮换密钥**：建议每 3-6 个月更换一次
5. **不要在代码中硬编码密钥**：使用环境变量或密钥管理服务
6. **启用 HTTPS**：生产环境使用反向代理（Nginx/Caddy）启用 HTTPS

#### Web 控制台管理

**重要说明**：SeaweedFS 原生不提供权限管理的 Web 控制台。权限配置需要通过编辑 `config/s3.json` 文件完成。

**可用的 Web UI**：

1. **Master UI** (http://localhost:8301)
   - 查看集群状态
   - 查看 Volume 分布
   - 查看存储统计
   - ❌ 不能管理权限

2. **Filer UI** (http://localhost:8303)
   - 浏览文件和目录
   - 上传/下载文件（需要认证）
   - ❌ 不能管理权限

3. **Volume UI** (http://localhost:8302/ui/index.html)
   - 查看 Volume 状态
   - 查看文件分布
   - ❌ 不能管理权限

**权限管理方式**：

目前只能通过以下方式管理权限：

1. **手动编辑配置文件**（推荐）
   ```powershell
   # 编辑 s3.json
   notepad config\s3.json
   
   # 重启服务使配置生效
   docker-compose restart
   ```

2. **使用版本控制**
   - 将 `config/s3.json` 纳入 Git 管理
   - 通过 Pull Request 审核权限变更
   - 保留权限变更历史

3. **自动化脚本**
   - 编写脚本生成 `s3.json`
   - 从数据库或配置中心读取权限配置
   - 自动重启服务

**第三方管理工具**：

如果需要 Web 控制台，可以考虑以下方案：

1. **MinIO Console**（不兼容，仅供参考）
   - MinIO 提供了完善的 Web 控制台
   - 但不能用于管理 SeaweedFS

2. **自建管理后台**
   - 在你的应用中集成权限管理功能
   - 通过 API 修改 `s3.json` 并重启服务
   - 示例代码见下方

3. **使用 Portainer**（管理 Docker）
   - 可以通过 Portainer 编辑配置文件
   - 访问：http://localhost:9000
   - 但仍需手动编辑 JSON

**自建管理后台示例**：

如果你想在 `genesis-ai-platform` 中集成 S3 权限管理：

```python
# genesis-ai-platform/services/seaweedfs_admin.py
import json
import subprocess
from pathlib import Path
from typing import List, Dict

class SeaweedFSAdmin:
    """SeaweedFS S3 权限管理服务"""
    
    def __init__(self, config_path: str = "../docker/seaweedfs/config/s3.json"):
        self.config_path = Path(config_path)
    
    def load_config(self) -> Dict:
        """加载 S3 配置"""
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def save_config(self, config: Dict):
        """保存 S3 配置"""
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def list_users(self) -> List[Dict]:
        """列出所有用户"""
        config = self.load_config()
        return config.get('identities', [])
    
    def add_user(self, name: str, access_key: str, secret_key: str, 
                 actions: List[str] = ["Read", "Write"]):
        """添加新用户"""
        config = self.load_config()
        
        # 检查用户是否已存在
        for identity in config['identities']:
            if identity['name'] == name:
                raise ValueError(f"用户 {name} 已存在")
        
        # 添加新用户
        config['identities'].append({
            "name": name,
            "credentials": [{
                "accessKey": access_key,
                "secretKey": secret_key
            }],
            "actions": actions
        })
        
        self.save_config(config)
        self.restart_service()
    
    def update_user(self, name: str, access_key: str = None, 
                   secret_key: str = None, actions: List[str] = None):
        """更新用户"""
        config = self.load_config()
        
        for identity in config['identities']:
            if identity['name'] == name:
                if access_key and secret_key:
                    identity['credentials'][0]['accessKey'] = access_key
                    identity['credentials'][0]['secretKey'] = secret_key
                if actions:
                    identity['actions'] = actions
                
                self.save_config(config)
                self.restart_service()
                return
        
        raise ValueError(f"用户 {name} 不存在")
    
    def delete_user(self, name: str):
        """删除用户"""
        config = self.load_config()
        
        config['identities'] = [
            identity for identity in config['identities']
            if identity['name'] != name
        ]
        
        self.save_config(config)
        self.restart_service()
    
    def restart_service(self):
        """重启 SeaweedFS 服务"""
        # 方式1：使用 docker-compose
        subprocess.run([
            "docker-compose",
            "-f", "../docker/seaweedfs/docker-compose.yml",
            "restart"
        ])
        
        # 方式2：使用 Docker API（推荐）
        # import docker
        # client = docker.from_env()
        # container = client.containers.get('seaweedfs')
        # container.restart()

# 使用示例
admin = SeaweedFSAdmin()

# 列出所有用户
users = admin.list_users()
for user in users:
    print(f"用户: {user['name']}, 权限: {user['actions']}")

# 添加新用户
admin.add_user(
    name="app1",
    access_key="app1_key_123",
    secret_key="app1_secret_456",
    actions=["Read", "Write"]
)

# 更新用户权限
admin.update_user(name="app1", actions=["Read"])

# 删除用户
admin.delete_user(name="app1")
```

然后在 FastAPI 中创建管理接口：

```python
# genesis-ai-platform/api/v1/seaweedfs_admin.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from services.seaweedfs_admin import SeaweedFSAdmin
from core.security.auth import get_current_user

router = APIRouter(prefix="/admin/seaweedfs", tags=["seaweedfs-admin"])

class UserCreate(BaseModel):
    name: str
    access_key: str
    secret_key: str
    actions: List[str] = ["Read", "Write"]

class UserUpdate(BaseModel):
    access_key: str | None = None
    secret_key: str | None = None
    actions: List[str] | None = None

@router.get("/users")
async def list_users(current_user = Depends(get_current_user)):
    """列出所有 S3 用户（需要管理员权限）"""
    if "admin" not in current_user.permissions:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    admin = SeaweedFSAdmin()
    return {"data": admin.list_users()}

@router.post("/users")
async def create_user(user: UserCreate, current_user = Depends(get_current_user)):
    """创建 S3 用户"""
    if "admin" not in current_user.permissions:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    admin = SeaweedFSAdmin()
    try:
        admin.add_user(user.name, user.access_key, user.secret_key, user.actions)
        return {"message": f"用户 {user.name} 创建成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/users/{name}")
async def update_user(name: str, user: UserUpdate, current_user = Depends(get_current_user)):
    """更新 S3 用户"""
    if "admin" not in current_user.permissions:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    admin = SeaweedFSAdmin()
    try:
        admin.update_user(name, user.access_key, user.secret_key, user.actions)
        return {"message": f"用户 {name} 更新成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/users/{name}")
async def delete_user(name: str, current_user = Depends(get_current_user)):
    """删除 S3 用户"""
    if "admin" not in current_user.permissions:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    admin = SeaweedFSAdmin()
    try:
        admin.delete_user(name)
        return {"message": f"用户 {name} 删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

这样你就可以在自己的管理后台中管理 SeaweedFS 的 S3 权限了！

**总结**：

| 方式 | 优点 | 缺点 |
|------|------|------|
| 手动编辑配置文件 | 简单直接 | 需要重启服务，无审计日志 |
| 版本控制（Git） | 有变更历史，可审核 | 需要手动操作 |
| 自建管理后台 | Web 界面，集成到应用 | 需要开发 |
| 第三方工具 | 功能完善 | 可能不兼容 |

**推荐方案**：
- **开发环境**：手动编辑配置文件
- **生产环境**：自建管理后台 + Git 版本控制

#### 使用示例

**Python (boto3)**
```python
import boto3

# 使用 readwrite 账号
s3 = boto3.client(
    's3',
    endpoint_url='http://localhost:8304',
    aws_access_key_id='<YOUR_READWRITE_ACCESS_KEY>',      # 从 s3.json 中获取
    aws_secret_access_key='<YOUR_READWRITE_SECRET_KEY>',  # 从 s3.json 中获取
    region_name='us-east-1'
)

# 上传文件
s3.upload_file('local.txt', 'my-bucket', 'remote.txt')
```

**AWS CLI**
```powershell
# 配置凭证
aws configure set aws_access_key_id <YOUR_READWRITE_ACCESS_KEY>
aws configure set aws_secret_access_key <YOUR_READWRITE_SECRET_KEY>

# 使用 S3 API
aws --endpoint-url http://localhost:8304 s3 ls
aws --endpoint-url http://localhost:8304 s3 cp file.txt s3://my-bucket/
```

**环境变量方式**
```powershell
# PowerShell
$env:AWS_ACCESS_KEY_ID = "<YOUR_READWRITE_ACCESS_KEY>"
$env:AWS_SECRET_ACCESS_KEY = "<YOUR_READWRITE_SECRET_KEY>"
$env:AWS_ENDPOINT_URL = "http://localhost:8304"

# 然后直接使用 AWS CLI（无需 --endpoint-url）
aws s3 ls
```

## 数据持久化

### 开发环境
数据存储在 `./data` 目录（单节点，所有数据在一起）

### 生产环境
数据分散存储：
```
data/
├── master1/     # Master 1 元数据
├── master2/     # Master 2 元数据
├── master3/     # Master 3 元数据
├── volume1/     # Volume 1 数据
├── volume2/     # Volume 2 数据
├── volume3/     # Volume 3 数据
├── filer/       # Filer 元数据
└── s3/          # S3 审计日志
```

**备份建议**：
- 定期备份 Master 元数据目录
- 定期备份 Filer 元数据目录
- Volume 数据通过副本策略保护

## 常用命令

### 启动/停止服务

```powershell
# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 重启服务
docker compose restart

# 停止并删除数据卷（危险！）
docker compose down -v
```

### 查看日志

```powershell
# 查看所有服务日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f master
docker compose logs -f volume1
docker compose logs -f filer
docker compose logs -f s3
```

### 切换到生产环境

```powershell
# 使用生产环境配置启动
docker compose -f docker-compose.prod.yml up -d

# 停止生产环境
docker compose -f docker-compose.prod.yml down
```

### 健康检查

```powershell
# 检查集群状态
curl http://localhost:8301/cluster/status

# 检查 Volume 状态
curl http://localhost:8301/dir/status

# 检查 Filer 状态
curl http://localhost:8303/
```

## 性能优化

### 1. 内存优化

如果内存紧张，可以调整资源限制：

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 256M  # 降低到 256MB
```

### 2. 磁盘优化

- 使用 SSD 存储以提升性能
- 定期清理过期数据
- 启用文件压缩（自动）

### 3. Volume 配置

```bash
# 调整 volume 大小限制（默认 1024MB）
-master.volumeSizeLimitMB=512  # 降低到 512MB 节省内存
```

### 4. 生产环境优化

- 使用 PostgreSQL 或 Redis 作为 Filer 元数据存储
- 启用缓存以提升读取性能
- 使用 host 网络模式
- 配置防火墙规则

## 监控

SeaweedFS 提供 Prometheus 指标：

- Master: http://localhost:8301/metrics
- Volume: http://localhost:8302/metrics
- Filer: http://localhost:8303/metrics

可以使用 Prometheus + Grafana 进行监控。

## 故障排查

### Master 无法启动

```powershell
# 查看日志
docker compose logs master

# 检查端口占用
netstat -ano | findstr :8301

# 清理数据重新启动（危险！）
# Remove-Item -Recurse -Force .\data\master
docker compose up -d master
```

### Volume 无法连接 Master

```powershell
# 检查网络连接
docker compose exec volume1 ping master

# 检查 Master 状态
curl http://localhost:8301/cluster/status
```

### S3 API 认证失败

1. 检查 `config/s3.json` 中的密钥配置
2. 确保 Filer 服务正常运行
3. 查看 S3 服务日志

## 生产环境建议

1. **高可用**：部署 3 个 Master 节点（使用 `-peers` 参数）
2. **数据冗余**：设置副本策略为 `010` 或 `100`
3. **监控**：集成 Prometheus + Grafana
4. **备份**：定期备份 Master 和 Filer 元数据
5. **安全**：
   - 修改默认 S3 密钥
   - 使用 HTTPS（配置反向代理）
   - 限制网络访问（防火墙规则）

## 防火墙与安全配置

### 1. 开放宿主机端口

如果你需要从外部访问 SeaweedFS，请在防火墙中开启以下 **宿主机端口**：

| 端口 | 服务类型 | 说明 | 推荐开启状态 |
| :--- | :--- | :--- | :--- |
| **8304** | **S3 API** | **最重要端口**。应用程序、boto3、AWS CLI 连接 S3 必用。 | **必须开启** |
| **8301** | **Master UI** | 查看集群整体状态、Volume 分布情况。 | 建议开启 |
| **8303** | **Filer UI** | 浏览、管理、上传下载文件。 | 建议开启 |
| **8302** | **Volume UI** | 查看具体存储节点的状态。 | 可选（开发调试用） |

**Linux (firewalld) 开启命令：**
```bash
# 批量开启 TCP 端口
firewall-cmd --permanent --add-port=8301-8304/tcp
# 重新加载生效
firewall-cmd --reload
```

### 2. 关于 gRPC 端口

SeaweedFS 内部组件通信（如 Filer 连接 Master）使用的是 gRPC，通常是 **HTTP 端口 + 10000**。
- **单机部署**：所有通信在 Docker 网络内部完成，**无需**在外部防火墙开启。
- **集群部署**：跨机器部署时，机器之间需要互通 19333, 18080 等端口。

### 3. 安全建议

> [!CAUTION]
> ### 🚨 极其重要：安全性警告
> SeaweedFS 的 **Master UI (8301)** 和 **Filer UI (8303)** 默认情况下 **没有任何验证机制**。
> *   **风险**：任何人只要能访问 8303 端口，就可以直接通过浏览器查看、下载甚至删除你的所有文件。
> *   **对策**：
>     1.  **严禁暴露**：永远不要在外部网络（公网）上开放 8301、8302、8303 端口。
>     2.  **防火墙策略**：仅开放 8304 (S3) 端口给外界，S3 协议自带认证机制。
>     3.  **身份认证**：如果必须外网访问 UI，请务必使用 Nginx/Caddy 等反向代理并添加 **Basic Auth** (用户名密码)。
>     4.  **最小权限**：应用程序仅使用经由 S3 认证的 8304 端口。

- **权限管理 API**：有关如何管理多业务 Key 及桶级隔离，请参考 [IAM 指南 (IAM_GUIDE.md)](./IAM_GUIDE.md)。
- **最小权限**：应用程序请务必使用 `s3.json` 中配置的 `readwrite` 角色密钥，不要直接使用 `admin` 密钥。

### 4. 详细加固方案

#### 方案 A：防火墙硬隔离（最简单、最快）

**原则**：只暴露 S3 业务端口，封禁管理端口。

```bash
# 仅开放 S3 业务端口 (8304) 给外部应用
firewall-cmd --permanent --add-port=8304/tcp

# 确保管理端口 (8301, 8303) 不在开放列表中，或者仅限特定管理员 IP 访问
# firewall-cmd --permanent --remove-port=8301/tcp
# firewall-cmd --permanent --remove-port=8303/tcp

firewall-cmd --reload
```

#### 方案 B：Nginx 反向代理 + Basic Auth

如果你确定需要通过互联网访问 Filer UI 或 Master UI，请务必在前面加一层带密码保护的反代。

1. **生成密码文件**：
```bash
# 生成名为 admin 的用户，你需要输入两次密码
htpasswd -c /etc/nginx/.seaweed_htpasswd admin
```

2. **Nginx 配置示例**：
```nginx
server {
    listen 80;
    server_name seaweed-admin.yourdomain.com; # 你的管理域名

    location / {
        auth_basic "SeaweedFS Admin Storage";
        auth_basic_user_file /etc/nginx/.seaweed_htpasswd;
        
        proxy_pass http://127.0.0.1:8303; # 指向 Filer UI
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 方案 C：SSH 隧道（最安全的临时访问方式）

在不开放防火墙端口的情况下，通过 SSH 安全地将远程服务器端口映射到本地。

**在你的本地机器执行**：
```bash
# 将远程服务器的 8303 端口映射到本地的 8303
ssh -L 8303:localhost:8303 root@your-server-ip
```
执行后，你只需要在本地浏览器访问 `http://localhost:8303`，流量就会通过加密的 SSH 通道传送到服务器。

---

## 参考文档

- [SeaweedFS 官方文档](https://github.com/seaweedfs/seaweedfs/wiki)
- [S3 API 兼容性](https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API)
- [生产环境部署](https://github.com/seaweedfs/seaweedfs/wiki/Production-Setup)

## 集成到项目

在 `genesis-ai-platform/.env` 中添加 SeaweedFS 配置：

```env
# SeaweedFS S3 配置
SEAWEEDFS_ENDPOINT=http://localhost:8304
SEAWEEDFS_ACCESS_KEY=GAI_AK_G6PMXBGGLZ6M       # 与 s3.json 中的 readwrite 用户一致
SEAWEEDFS_SECRET_KEY=be5pC1LI5cohK26PMvmNzcBxTBaf85iMN4sdXABS
SEAWEEDFS_BUCKET=genesis-ai-files
SEAWEEDFS_REGION=us-east-1
```

**注意**：
- 应用程序应该使用 `readwrite` 用户，而不是 `admin` 用户（最小权限原则）
- 如果修改了 `config/s3.json` 中的密钥，这里也要同步修改

在 Python 代码中使用：

```python
import boto3
from core.config import settings

# 创建 S3 客户端
s3_client = boto3.client(
    's3',
    endpoint_url=settings.SEAWEEDFS_ENDPOINT,
    aws_access_key_id=settings.SEAWEEDFS_ACCESS_KEY,
    aws_secret_access_key=settings.SEAWEEDFS_SECRET_KEY,
    region_name=settings.SEAWEEDFS_REGION
)

# 上传文件
def upload_file(file_path: str, key: str):
    s3_client.upload_file(
        file_path, 
        settings.SEAWEEDFS_BUCKET, 
        key
    )

# 下载文件
def download_file(key: str, file_path: str):
    s3_client.download_file(
        settings.SEAWEEDFS_BUCKET, 
        key, 
        file_path
    )

# 生成预签名 URL（用于前端直接下载）
def generate_presigned_url(key: str, expiration: int = 3600):
    return s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings.SEAWEEDFS_BUCKET, 
            'Key': key
        },
        ExpiresIn=expiration
    )
```
