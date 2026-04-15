# Genesis AI - Docker 部署指南

本目录包含 Genesis AI 平台的 Docker 配置文件，支持开发和生产环境。

## 📁 目录结构

```
docker/
├── dev/                          # 开发环境配置
│   ├── .env                      # 开发环境变量
│   ├── deploy.sh                 # 开发环境一键部署脚本
│   ├── docker-compose.yml        # 开发环境 Docker Compose
│   ├── init-database.sh          # 开发数据库初始化脚本
│   └── postgresql.conf           # 开发环境 PostgreSQL 配置
├── prod/                         # 生产环境配置
│   ├── .env                      # 生产环境变量
│   ├── deploy.sh                 # 生产环境一键部署脚本
│   ├── docker-compose.yml        # 生产环境 Docker Compose
│   ├── init-database.sql         # 生产数据库初始化脚本
│   └── postgresql.conf           # 生产环境 PostgreSQL 配置
├── init-schema.sql               # 公共表结构 + 默认主数据初始化脚本（通用）
├── .env.example                  # 环境变量示例
├── README.md                     # 本文档
```

**说明：**
- `dev/` 和 `prod/` 文件夹包含各自环境的完整配置
- `init-schema.sql` 基于真实数据库快照生成，包含公共表结构和默认主数据，两个环境共用
- `docker-entrypoint-initdb.d` 下的初始化脚本只会在 PostgreSQL 数据目录为空时执行一次
- `dev/` 和 `prod/` 使用宿主机目录持久化数据；`docker-compose.full.yml` 和 `docker-compose.storage.yml` 使用 Docker named volume

## 初始化生命周期

### 首次启动

- 当 PostgreSQL 数据目录为空时，容器会自动执行 `/docker-entrypoint-initdb.d/` 下的初始化脚本
- 开发环境会自动执行 `dev/init-database.sh`
- 生产环境会自动执行 `prod/init-database.sql`
- 初始化脚本会在建库、建应用用户、安装扩展后自动导入 `init-schema.sql`
- `init-schema.sql` 会导入业务表结构和默认主数据，包括默认租户、用户、角色、权限、菜单及其关联

### 首次导入业务结构

- 现已纳入首次初始化自动执行，无需再手动执行 `../init-schema.sql`
- 如需重新导入，必须删除数据目录或数据卷后重新初始化

### 后续重启

- 只要数据目录或数据卷已存在，后续执行 `docker compose up -d` 或 `docker-compose up -d` 都不会再次自动初始化
- 正常重启只会直接加载现有数据，不会清空库，也不会重新导入 `init-schema.sql`

### 强制重建

- 强制重建必须显式执行单独脚本
- 开发环境：`dev/reset-db.ps1`
- 生产环境：`prod/reset-db.sh`
- 强制重建会删除已有 PostgreSQL 数据目录，然后重新触发首次初始化流程并自动导入 `init-schema.sql`

## 🚀 快速开始

### Windows 开发环境（WSL Docker）

1. **启动开发环境**
```bash
cd docker/dev
docker-compose up -d
```

2. **初始化数据库（首次运行）**
```bash
# 仅当 ../pgdata-dev 为空时，容器首次启动会自动执行 init-database.sh
# 并自动导入 ../init-schema.sql
```

3. **查看日志**
```bash
docker-compose logs -f
```

4. **停止服务（保留数据）**
```bash
docker-compose down
```

5. **强制重建数据库（危险操作）**
```powershell
cd docker/postgresql/dev
.\reset-db.ps1
```

### 生产环境

1. **配置环境变量**
```bash
cd docker/prod
# ⚠️ 编辑 .env 和 init-database.sql，修改密码等敏感信息
```

2. **启动生产环境**
```bash
# ⚠️ 重要：先修改 init-database.sql 中的应用用户密码！
docker-compose up -d
```

3. **初始化数据库（首次运行）**
```bash
# 仅当 ../pgdata-prod 为空时，容器首次启动会自动执行 init-database.sql
# 并自动导入 ../init-schema.sql
```

4. **强制重建数据库（危险操作）**
```bash
cd docker/postgresql/prod
sh ./reset-db.sh
```

## ⚙️ 配置对比

| 配置项 | 开发环境 | 生产环境 |
|--------|---------|---------|
| 项目名称 | genesis-ai | genesis-ai |
| 容器名称 | genesis-ai-db-dev | genesis-ai-db-prod |
| 数据库名 | genesis_ai | genesis_ai |
| 管理员用户 | postgres | postgres |
| 管理员密码 | postgres | SDF34784XD23SJKFdj23Kjja74kjdGG3JUhyb2346 |
| 应用用户 | genesis_app | genesis_app |
| 应用用户密码 | genesis_dev_password | ⚠️ 需修改 (内置: 9J#pLw!4sM$nGfT6) |
| 数据卷 | pgdata-dev | pgdata-prod |
| 共享内存 | 256MB | 1GB |
| shared_buffers | 512MB | 2GB |
| maintenance_work_mem | 128MB | 512MB |
| work_mem | 16MB | 32MB |
| max_connections | 50 | 100 |
| 并行工作进程 | 1-2 | 2-4 |
| fsync | off (快速) | on (安全) |
| 日志级别 | 详细 (all) | 慢查询 (200ms+) |

## 🔧 常用命令

### 连接数据库
```bash
# 开发环境 - 管理员连接
docker exec -it genesis-ai-db-dev psql -U postgres -d genesis_ai

# 开发环境 - 应用用户连接
docker exec -it genesis-ai-db-dev psql -U genesis_app -d genesis_ai

# 生产环境 - 管理员连接
docker exec -it genesis-ai-db-prod psql -U postgres -d genesis_ai

# 生产环境 - 应用用户连接
docker exec -it genesis-ai-db-prod psql -U genesis_app -d genesis_ai
```

### 备份数据库
```bash
# 开发环境
docker exec genesis-ai-db-dev pg_dump -U postgres genesis_ai > backup_dev.sql

# 生产环境
docker exec genesis-ai-db-prod pg_dump -U postgres genesis_ai > backup_prod.sql
```

### 恢复数据库
```bash
# 开发环境
docker exec -i genesis-ai-db-dev psql -U postgres genesis_ai < backup_dev.sql

# 生产环境
docker exec -i genesis-ai-db-prod psql -U postgres genesis_ai < backup_prod.sql
```

### 查看资源占用
```bash
docker stats genesis-ai-db-dev
# 或
docker stats genesis-ai-db-prod
```

## 📊 性能调优建议

### 开发环境（Windows WSL）
- 适用于 4-8GB RAM 的开发机器
- 关闭了 fsync 和 synchronous_commit 以提升性能
- 减少了并行度和连接数
- 启用详细日志便于调试

### 生产环境
- 建议 8GB+ RAM
- 启用完整的数据持久化保护
- 优化了向量检索性能
- 仅记录慢查询（200ms+）

## 📦 数据持久化说明

**数据存储位置：**
- 开发环境：`docker/postgresql/pgdata-dev/` 目录
- 生产环境：`docker/postgresql/pgdata-prod/` 目录
- `docker-compose.full.yml` / `docker-compose.storage.yml`：Docker named volume `postgres_data`

**重要特性：**
- ✅ 数据映射到宿主机目录或 Docker volume，容器删除后数据**不会丢失**
- ✅ 执行 `docker-compose down` / `docker compose down` 只删除容器，数据保留
- ✅ 重新启动容器会自动加载已有数据，不会再次自动初始化
- ⚠️ 只有手动删除 `pgdata-*` 目录或显式删除 named volume 才会清空数据

**数据目录已添加到 .gitignore：**
```
pgdata-dev/
pgdata-prod/
```

### 强制重建与重置方式

**bind mount 场景（`dev/`、`prod/`）：**
- 开发环境请使用 `dev/reset-db.ps1`
- 生产环境请使用 `prod/reset-db.sh`
- 这两个脚本都会先停止容器，再删除真实数据目录，随后重启并重新导入 `init-schema.sql`

**named volume 场景（`docker-compose.full.yml`、`docker-compose.storage.yml`）：**
- PostgreSQL 数据在 `postgres_data` volume 中
- 如需强制重建，应显式删除该 volume，例如：

```bash
docker compose -f docker-compose.full.yml down -v
# 或
docker compose -f docker-compose.storage.yml down -v
```

- 删除 volume 后再次启动，才会重新触发 `/docker-entrypoint-initdb.d/` 初始化脚本

## 🔒 安全提示

⚠️ **重要**：生产环境部署前请务必：
1. 修改 `prod/.env` 中的 `POSTGRES_PASSWORD`（管理员密码）
2. 修改 `prod/init-database.sql` 中的应用用户密码（genesis_app）
3. 限制数据库端口访问（使用防火墙）
4. 定期备份数据（见上方备份命令）
5. 启用 SSL 连接（如需要）
6. 确保 `pgdata-prod` 目录有适当的访问权限
7. 使用强密码（至少 16 位，包含大小写字母、数字、特殊字符）

### 用户权限设计（最佳实践）

**双用户架构：**
```
postgres (超级用户)
├── 用途: 数据库管理、DDL 操作、数据迁移
├── 权限: 超级用户（完全控制）
├── 特点: PostgreSQL 系统默认管理员，不带业务名称
└── 使用场景: 初始化、Schema 变更、备份恢复

genesis_app (应用用户)
├── 用途: 应用程序连接
├── 权限: 受限（仅 DML 操作）
├── 特点: 业务相关命名，权限最小化
└── 使用场景: 日常业务操作
```

**配置对比：**
| 用户类型 | 用户名 | 权限级别 | 开发环境密码 | 生产环境密码 | 用途 |
|---------|--------|---------|------------|------------|------|
| 管理员 | postgres | 超级用户 | postgres | SDF34784XD23SJKFdj23Kjja74kjdGG3JUhyb2346 | 数据库管理 |
| 应用用户 | genesis_app | 受限 | genesis_dev_password | ⚠️ 需修改 (内置: 9J#pLw!4sM$nGfT6) | 应用程序连接 |

**应用程序连接配置：**
```python
# 开发环境
DATABASE_URL = "postgresql://genesis_app:genesis_dev_password@localhost:5432/genesis_ai"

# 生产环境
DATABASE_URL = "postgresql://genesis_app:9J#pLw!4sM$nGfT6@localhost:5432/genesis_ai"  # 记得修改密码！
```

**修改密码步骤：**

1. **修改管理员密码（postgres）：**
   - 编辑 `prod/.env`，修改 `POSTGRES_PASSWORD=xxx`
   - 删除数据目录：`rmdir /s /q pgdata-prod`（Windows）或 `rm -rf pgdata-prod`（Linux）
   - 重新启动容器：`docker-compose up -d`
   - 重新执行初始化脚本

2. **修改应用用户密码（genesis_app）：**
   - 编辑 `prod/init-database.sql`，修改 `PASSWORD 'xxx'` 部分
   - 重新执行初始化脚本

⚠️ **注意**：
- 管理员账号（postgres）仅用于数据库管理，不应在应用程序中使用
- 应用程序应始终使用 `genesis_app` 账号连接
- 应用用户无法执行 DDL 操作（CREATE/DROP TABLE 等），提高安全性
- 使用系统默认的 `postgres` 用户名，避免业务名称泄露
- 手动创建数据库可以精确控制编码、排序规则等参数

### 数据库编码最佳实践
本配置使用以下最佳实践设置：
- **编码**：UTF8（支持全球所有字符，包括中文、emoji 等）
- **排序规则**：en_US.UTF-8（影响 ORDER BY 和字符串比较）
- **字符分类**：en_US.UTF-8（影响大小写转换和字符类型判断）
- **连接限制**：无限制（可根据需要调整）

## 🐛 故障排查

### 容器无法启动
```bash
# 查看详细日志
docker-compose -f docker-compose.dev.yml logs

# 检查端口占用
netstat -ano | findstr :5432
```

### 内存不足
如果 Windows 机器内存较小，可以进一步降低 `dev/postgresql.conf` 中的内存配置：
- shared_buffers: 256MB
- maintenance_work_mem: 64MB
- work_mem: 8MB

### WSL Docker 性能问题
- 确保数据卷在 WSL 文件系统内（不要使用 Windows 挂载路径）
- 分配足够的 WSL 内存（.wslconfig）
- 使用 Docker Desktop 的 WSL 2 后端

### 数据库初始化失败
```bash
# 检查数据库是否已存在
docker exec -it genesis-ai-db-dev psql -U postgres -d postgres -c "\l"

# 检查扩展是否已安装
docker exec -it genesis-ai-db-dev psql -U postgres -d genesis_ai -c "\dx"

# 已有数据目录时，容器不会再次自动初始化
# 如需强制重建，请使用 reset-db 脚本，不要在正常启动链路里做删库操作
```

## ✅ 验证建议

### 验证默认启动不会重复初始化

1. 启动一次数据库并完成 `init-schema.sql` 导入
2. 再次执行 `docker compose up -d` 或 `docker-compose up -d`
3. 确认默认租户、角色、菜单、权限数据仍然存在，且没有被重新覆盖

### 验证强制重建

1. 执行对应环境的 `reset-db` 脚本
2. 确认库被重新创建
3. 确认 `init-schema.sql` 中的默认租户、用户、角色、权限、菜单及其关联已恢复

### 验证生产环境保护

1. 执行 `prod/reset-db.sh`
2. 不输入正确确认串
3. 确认脚本直接退出，且不会删除任何现有数据

## 📝 更新日志

- 2026-01-08: 重构目录结构，分离 dev/prod 配置
- 2026-01-08: 创建开发/生产环境分离配置
- 针对 Windows WSL Docker 优化开发环境配置
