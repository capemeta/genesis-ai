# SeaweedFS 身份与访问管理 (IAM) 指南

本指南详细介绍了如何在 SeaweedFS 中管理访问密钥（Access Key/Secret Key）以及如何为不同业务分配权限。

## 1. 核心管理方式：静态配置文件 (`s3.json`)

目前 SeaweedFS 最稳定、最推荐的方式是通过 `s3.json` 配置文件来定义用户身份（Identities）。

### 1.1 配置文件位置
在 Docker 部署中，该文件通常位于宿主机的 `docker/seaweedfs/config/s3.json`，并挂载到容器的 `/etc/seaweedfs/s3.json`。

### 1.2 配置项详解

```json
{
  "identities": [
    {
      "name": "biz_user_system",
      "credentials": [
        {
          "accessKey": "SYS_AK_123456",
          "secretKey": "SYS_SK_abcdef"
        }
      ],
      "actions": ["Read", "Write", "List"],
      "buckets": ["user-avatars", "public-assets"]
    }
  ]
}
```

*   **`name`**: 身份名称，仅用于管理标识。
*   **`credentials`**: 包含一对或多对 AccessKey 和 SecretKey。
*   **`actions`**: 权限列表。常用值：
    *   `Read`: 下载对象。
    *   `Write`: 上传、删除、创建桶。
    *   `List`: 查看桶列表及内容。
    *   `Admin`: 系统管理权限。
    *   `Tagging`: 修改对象标签。
*   **`buckets` (重要)**: 
    *   **权限隔离的核心**。如果指定了桶名列表，该 Key **只能**看到和操作这些桶。
    *   访问列表外的桶会直接返回 `403 Forbidden`。
    *   如果不写此字段，默认拥有访问所有桶的权限。

---

## 2. API 控制支持程度

### 2.1 现状分析
SeaweedFS 的 S3 兼容层主要集中在 **数据平面 (Data Plane)**，而非 **控制平面 (Control Plane)**。

| 功能分类 | 支持程度 | 说明 |
| :--- | :--- | :--- |
| **数据操作 API** | **完全支持** | CreateBucket, PutObject, GetObject, DeleteObject, HeadObject 等。 |
| **预签名 URL** | **完全支持** | 可生成带过期时间的临时访问连接，这是动态权限的首选方案。 |
| **IAM 管理 API** | **部分/不支持** | 不支持 AWS 风格的 `CreateUser`, `PutUserPolicy` 等 IAM API。 |

### 2.2 为什么不支持 IAM API？
SeaweedFS 的设计哲学是轻量级和高性能。为了保持元数据服务的简洁，它没有像 AWS 那样维护复杂的在线身份数据库。身份验证目前高度依赖于启动时加载的静态 JSON 配置。

---

## 3. 动态业务场景的推荐架构

如果你正在开发一个需要“动态分配权限”的系统（例如：为每个新租户自动分配存储空间），建议采用 **“中心化存储服务 (Proxy/Service Pattern)”**。

### 核心设计思想：
1.  **不直接下发 Key**：不要把真实的 SeaweedFS Key 给到具体的业务前端或第三方。
2.  **后端统一持有 Master Key**：由你的后端服务（如 `genesis-ai-platform`）持有具备 `Admin` 权限的 Key。
3.  **使用预签名 URL (Presigned URL)**：
    *   业务方需要上传/下载时，请求你的后端接口。
    *   后端接口校验业务权限。
    *   后端利用 `boto3` 生成一个限时（如 5 分钟）的 URL 返回给业务方。
    *   业务方拿到 URL 直接与 SeaweedFS 通信。

### 架构图示：
```text
[ 业务线 A ] <----(1) 请求下载 ----> [ 存储微服务 ]
                                       |
                                    (2) 权限校验 & 生成签名
                                       |
[ 业务线 A ] <----(3) 拿着签名URL --+--> [ SeaweedFS S3 ]
                   直接下载/上传数据
```

---

## 4. 如何使用特定的访问密钥

当你为不同业务配置了不同的 Key 后，以下是具体的调用方式。

### 4.1 在 Python (boto3) 中使用

每个业务线在自己的代码中使用分配到的 `AccessKey` 和 `SecretKey`。

```python
import boto3

# 业务 A 的配置
s3_biz_a = boto3.client(
    's3',
    endpoint_url='http://localhost:8304',
    aws_access_key_id='SYS_AK_123456',     # 使用该业务特有的 Key
    aws_secret_access_key='SYS_SK_abcdef', # 使用该业务特有的 Secret
    region_name='us-east-1'
)

# 尝试操作授权内的桶（成功）
s3_biz_a.list_objects(Bucket='user-avatars')

# 尝试操作授权外的桶（即使桶存在，也会报错 403 Access Denied）
try:
    s3_biz_a.list_objects(Bucket='financial-records')
except Exception as e:
    print(f"操作被拒绝: {e}")
```

### 4.2 在 AWS CLI 中使用

你可以配置多个 Profile，或者直接在命令中指定环境变量。

```bash
# 方式一：使用环境变量
export AWS_ACCESS_KEY_ID=SYS_AK_123456
export AWS_SECRET_ACCESS_KEY=SYS_SK_abcdef

aws --endpoint-url http://localhost:8304 s3 ls s3://user-avatars

# 方式二：配置 Profile
aws configure --profile biz_a
# 输入 SYS_AK_123456 ...

aws --profile biz_a --endpoint-url http://localhost:8304 s3 ls
```

### 4.3 在 `genesis-ai-platform` (.env) 中切换

如果你的应用本身就是一个多租户系统，你可以在不同环境的 `.env` 中指定不同的 Key：

```env
# 不同环境或不同业务实例使用不同的 Key
SEAWEEDFS_ACCESS_KEY=SYS_AK_123456
SEAWEEDFS_SECRET_KEY=SYS_SK_abcdef
SEAWEEDFS_BUCKET=user-avatars
```

---

## 5. 总结

*   **小型/固定业务**：直接修改 `s3.json`，通过 `buckets` 字段手工分配权限。
*   **大型/动态业务**：通过后端服务封装，利用 **预签名 URL** 实现逻辑上的动态权限控制。
*   **生效方式**：修改 `s3.json` 后需执行 `docker compose restart` 重启服务。
