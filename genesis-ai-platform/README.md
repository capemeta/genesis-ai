# Genesis AI Platform - 后端

企业级 RAG 知识库系统后端服务

## 🎯 项目简介

启元 AI 平台是一个企业级 RAG（检索增强生成）知识库系统，提供数据接入、向量检索、智能问答等核心能力。

**当前开发阶段**：第一阶段 - RAG 知识库核心功能

## 🚀 快速开始

### 前置要求

- **Python**: 3.12+
- **包管理**: uv
- **Docker**: 用于运行 PostgreSQL 和 Redis

### 1. 启动数据库

```powershell
# 进入 docker 目录
cd ..\docker

# 启动 PostgreSQL 和 Redis
docker-compose -f dev\docker-compose.yml up -d postgres redis

# 检查服务状态
docker-compose -f dev\docker-compose.yml ps
```

### 2. 配置环境变量

```powershell
# 回到后端目录
cd ..\genesis-ai-platform

# 复制环境变量模板
copy .env.example .env

# 编辑 .env（可选，默认配置已经可用）
# 主要检查 DATABASE_URL 和 REDIS_URL 是否正确
```

### 3. 安装依赖

```powershell
# 使用 uv 安装依赖
uv sync
```

### 4. 启动应用

```powershell
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 启动 FastAPI 应用（开发模式，热重载）
python main.py

# 或使用 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8200
```

### 5. 访问 API 文档

- **Swagger UI**: http://localhost:8200/docs
- **ReDoc**: http://localhost:8200/redoc

### 6. 测试认证功能

```powershell
# 运行测试脚本
python scripts\test_auth.py
```

### 7. 启动 Session 清理任务（可选，待启动）

**说明**：清理孤儿 refresh session，防止 Redis 内存泄漏。详见 `SESSION_CLEANUP.md`

**⚠️ 注意**：代码已实现，但需要手动启动 Celery 服务。

```powershell
# 启动 Celery Worker（后台任务处理）
uv run celery -A tasks.celery_tasks worker --loglevel=info

# 启动 Celery Beat（定时任务调度器）
# 新开一个终端窗口
uv run celery -A tasks.celery_tasks beat --loglevel=info
```

**清理策略**（已实现）：
- ✅ 每小时清理一次孤儿 refresh session
- ✅ 每天凌晨 3 点清理已过期的撤销 token
- ✅ 前端监听标签页关闭，主动清理 session（sessionStorage 模式）

**手动触发清理**（已实现）：
```powershell
# 运行清理脚本
uv run python -m tasks.cleanup_sessions

# 或通过管理员 API
curl -X POST http://localhost:8200/api/v1/admin/cleanup/sessions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**何时需要启动**：
- ✅ 如果用户都勾选"记住我"（使用 localStorage），孤儿 session 很少，可以不启动
- ⚠️ 如果用户大量使用 sessionStorage（不勾选"记住我"），建议启动清理任务
- 📊 可以通过管理员 API 查看统计信息：`GET /api/v1/admin/stats/sessions`

**已实现的功能**：
- ✅ 孤儿 session 自动清理（`tasks/cleanup_sessions.py`）
- ✅ Celery 定时任务配置（`tasks/celery_tasks.py`）
- ✅ 管理员 API（`api/v1/admin.py`）
- ✅ 前端标签页关闭监听（`genesis-ai-frontend/src/App.tsx`）
- ✅ 详细文档（`SESSION_CLEANUP.md`）

## 📦 技术栈

- **Python**: 3.12+
- **Web 框架**: FastAPI
- **ORM**: SQLAlchemy 2.0 (异步)
- **认证**: fastapi-users + PyJWT + passlib[bcrypt]
- **数据库**: PostgreSQL 16+ (含 pgvector 扩展)
- **缓存**: Redis
- **任务队列**: Celery
- **LLM 管理**: LiteLLM
- **RAG 框架**: LlamaIndex, LangChain
- **包管理**: uv

## 📁 项目结构

```
genesis-ai-platform/
├── core/                   # 核心基础设施
│   ├── config/            # 配置管理
│   ├── database/          # 数据库连接
│   ├── security/          # 安全工具（认证、加密）
│   ├── crud_factory.py    # 🌟 CRUD 工厂（自动化 CRUD）
│   ├── base_service.py    # 通用 Service 基类
│   ├── base_router.py     # 通用 Router 工厂
│   ├── response.py        # REST API 响应格式处理
│   └── exceptions.py      # 异常定义
│
├── models/                 # 数据模型（SQLAlchemy）
│   ├── base.py            # 基础模型（审计字段、租户隔离）
│   ├── user.py            # 用户模型
│   └── tenant.py          # 租户模型
│
├── schemas/                # Pydantic Schema（请求/响应）
│   ├── user.py            # 用户 Schema
│   ├── auth.py            # 认证 Schema
│   └── common.py          # 通用 Schema（分页、响应）
│
├── api/                    # API 路由
│   ├── crud_registry.py   # 🌟 CRUD 注册中心
│   └── v1/
│       ├── auth.py        # 认证接口
│       ├── users.py       # 用户管理
│       └── deps.py        # 依赖注入
│
├── repositories/           # 数据访问层
│   ├── base.py            # 基础 Repository
│   └── user_repo.py       # 用户 Repository
│
├── services/               # 业务逻辑层
│   └── user_service.py    # 用户服务
│
├── middleware/             # 中间件
│   └── auth_middleware.py # 认证中间件
│
├── tasks/                  # Celery 异步任务
├── rag/                    # RAG 核心功能
│   ├── loaders/           # 文档加载器
│   ├── chunking/          # 文档分块
│   ├── embeddings/        # 向量化
│   └── retrieval/         # 检索引擎
│
├── utils/                  # 工具函数
├── scripts/                # 运维脚本
│   ├── test_auth.py       # 认证测试脚本
│   └── create_initial_data.py  # 初始化数据
│
├── tests/                  # 测试
├── migrations/             # 数据库迁移（Alembic）
│
├── main.py                 # 应用入口
├── pyproject.toml          # 项目配置
├── .env.example            # 环境变量模板
│
└── 文档/
    ├── CRUD_QUICK_START.md         # 🌟 CRUD 系统使用指南
    ├── 新表快速接入指南.md          # 新表接入流程
    ├── 审计字段使用指南.md          # 审计字段规范
    ├── 权限控制使用指南.md          # 权限系统使用
    └── 自定义查询与连表-使用指南.md  # 复杂查询指南
```

## 🎯 核心特性

### 1. CRUD 工厂（极速开发）

**只需 1 行代码，即可拥有完整的 CRUD 功能！**

```python
# api/crud_registry.py
from core.crud_factory import crud_factory
from models.knowledge_base import KnowledgeBase

def register_all_crud():
    # 只需这一行！
    crud_factory.register(
        model=KnowledgeBase,
        prefix="/knowledge-bases",
        tags=["knowledge-bases"]
    )
```

**自动获得**：
- ✅ 5 个标准 CRUD 路由（列表、获取、创建、更新、删除）
- ✅ 统一响应格式（包含 code、message、data 三字段，列表响应的 data 字段包含分页信息）
- ✅ 租户隔离、权限检查、审计字段、软删除
- ✅ 分页、过滤、排序
- ✅ 自动生成 Schema、Service、Router

**详细指南**：查看 `CRUD_QUICK_START.md`

### 2. 企业级权限系统

- **RBAC**: 基于角色的访问控制
- **URAC**: 通用资源访问控制
- **多租户隔离**: 物理/逻辑层面的数据隔离
- **细粒度授权**: 支持用户、角色、组织三级授权

### 3. 审计与追溯

所有核心表包含完整审计字段：
- `owner_id` - 资源所有者
- `created_by_id`, `created_by_name` - 创建人
- `updated_by_id`, `updated_by_name` - 更新人
- `created_at`, `updated_at` - 时间戳
- `deleted_at` - 软删除支持

### 4. REST API 响应规范

所有 API 遵循统一的 REST 响应格式：
- 列表接口返回 `{"data": [...], "total": 100}`
- 单个资源返回 `{"data": {...}}`
- 统一的错误响应格式

## 🔌 API 端点

### 认证相关

- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/jwt/login` - 用户登录
- `POST /api/v1/auth/jwt/logout` - 用户登出
- `POST /api/v1/auth/forgot-password` - 忘记密码
- `POST /api/v1/auth/reset-password` - 重置密码
- `POST /api/v1/auth/request-verify-token` - 请求验证令牌
- `POST /api/v1/auth/verify` - 验证邮箱

### 用户管理

- `GET /api/v1/users/me` - 获取当前用户信息
- `PATCH /api/v1/users/me` - 更新当前用户信息
- `GET /api/v1/users/{id}` - 获取用户信息（管理员）
- `PATCH /api/v1/users/{id}` - 更新用户信息（管理员）
- `DELETE /api/v1/users/{id}` - 删除用户（管理员）

### 健康检查

- `GET /api/v1/health` - 基础健康检查
- `GET /api/v1/health/db` - 数据库健康检查

## 🛠️ 开发指南

### 添加新表（推荐使用 CRUD 工厂）

**完整流程**：查看 `新表快速接入指南.md`

**快速步骤**：

1. **创建数据库表**（在 `docker/dev/init-database.sql` 中）
2. **创建 SQLAlchemy 模型**（在 `models/` 中）
3. **注册到 CRUD 工厂**（在 `api/crud_registry.py` 中）

```python
# 1. 创建模型
# models/tag.py
from models.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID

class Tag(Base):
    __tablename__ = "tags"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    # ... 其他字段

# 2. 注册到 CRUD 工厂（1 行代码）
# api/crud_registry.py
crud_factory.register(model=Tag, prefix="/tags", tags=["tags"])

# 完成！自动生成所有 CRUD 接口
```

### 数据库迁移

```powershell
# 生成迁移文件
uv run alembic revision --autogenerate -m "描述"

# 执行迁移
uv run alembic upgrade head

# 回滚迁移
uv run alembic downgrade -1
```

### 运行测试

```powershell
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests\test_auth.py

# 带覆盖率报告
uv run pytest --cov=. --cov-report=html
```

## ⚙️ 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DATABASE_URL | PostgreSQL 连接字符串 | `postgresql+asyncpg://genesis:genesis@localhost:5432/genesis_ai` |
| REDIS_URL | Redis 连接字符串 | `redis://localhost:6379/0` |
| SECRET_KEY | JWT 密钥（生产环境必须修改） | - |
| ACCESS_TOKEN_EXPIRE_MINUTES | Token 过期时间（分钟） | 30 (30分钟) |
| SEAWEEDFS_ENDPOINT | SeaweedFS 端点 | `http://localhost:8304` |
| SEAWEEDFS_ACCESS_KEY | SeaweedFS 访问密钥 | - |
| SEAWEEDFS_SECRET_KEY | SeaweedFS 密钥 | - |

完整配置请参考 `.env.example`

## 📝 注意事项

### 1. 租户问题

当前系统需要租户 ID 才能注册用户。首次使用需要先创建租户：

```sql
-- 连接到数据库
docker exec -it genesis-ai-db-dev psql -U genesis -d genesis_ai

-- 创建租户
INSERT INTO tenants (id, owner_id, name, description)
VALUES (
    '123e4567-e89b-12d3-a456-426614174000',
    '123e4567-e89b-12d3-a456-426614174000',
    '默认租户',
    '系统默认租户'
);
```

或使用初始化脚本：

```powershell
python scripts\create_initial_data.py
```

### 2. 数据库表自动创建

应用启动时会自动创建所有数据库表（开发环境）。生产环境建议使用 Alembic 迁移。

### 3. 超级管理员

第一个用户可以手动设置为超级管理员：

```sql
UPDATE users 
SET is_superuser = true 
WHERE email = 'admin@example.com';
```

## 🔧 常见问题

### Q: 数据库连接失败？

**A**: 检查以下几点：
1. PostgreSQL 容器是否正常运行：`docker ps`
2. 数据库连接字符串是否正确：检查 `.env` 中的 `DATABASE_URL`
3. 数据库是否已创建：`docker exec -it genesis-ai-db-dev psql -U postgres -l`

### Q: 注册时提示租户不存在？

**A**: 需要先创建租户，参考上面的"租户问题"部分。

### Q: Token 无效？

**A**: 检查：
1. Token 是否正确复制（不要包含多余空格）
2. Token 是否已过期（默认 24 小时）
3. SECRET_KEY 是否在重启后发生变化

### Q: 如何快速添加新表？

**A**: 使用 CRUD 工厂，只需 1 行代码！详见 `CRUD_QUICK_START.md`

## 📚 相关文档

### 项目文档（根目录 `doc/`）
- `数据库设计.md` - 数据库设计规范
- `权限系统深度解析.md` - 权限系统详解
- `文件夹与标签系统深度设计.md` - 文件夹与标签设计
- `大模型-自研RAG框架.md` - RAG 框架设计
- `认证系统详细说明.md` - 认证系统详解

### 开发指南（当前目录）
- `CRUD_QUICK_START.md` - CRUD 系统使用指南
- `新表快速接入指南.md` - 新表接入流程
- `审计字段使用指南.md` - 审计字段规范
- `权限控制使用指南.md` - 权限系统使用
- `SESSION_CLEANUP.md` - Session 清理机制说明

### Kiro Steering（`.kiro/steering/`）
- `project-overview.md` - 项目概览
- `backend-standards.md` - 后端开发规范
- `windows-development.md` - Windows 开发环境指南

## 🗺️ 开发路线图

### ✅ 已完成

- [x] 认证系统（注册、登录、JWT）
- [x] 用户管理
- [x] 租户隔离
- [x] CRUD 工厂（自动化 CRUD）
- [x] 审计字段系统
- [x] REST API 响应规范

### 🔄 进行中

- [ ] 知识库管理
- [ ] 文件夹管理（ltree）
- [ ] 标签系统
- [ ] 资源权限管理（URAC）

### 📋 计划中

- [ ] 文档上传与解析
- [ ] 文档分块与向量化
- [ ] 混合检索（向量 + 全文 + RRF）
- [ ] RAG 问答生成（流式输出）
- [ ] 对话历史
- [ ] 智能体编排

## 📄 许可证

MIT
