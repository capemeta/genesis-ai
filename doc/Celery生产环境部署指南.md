# Celery 生产环境部署指南

## 概述

本文档说明 Celery 在不同环境下的配置方案，包括 Windows 开发环境和 Linux 生产环境。

## 核心概念

### Worker Pool 类型

Celery 支持多种 Worker Pool 实现，通过 `-P` 参数指定：

| Pool 类型 | 适用场景 | 并发模型 | Windows 支持 | Linux 支持 |
|-----------|----------|----------|--------------|------------|
| `solo` | 开发调试 | 单线程，无并发 | ✅ | ✅ |
| `eventlet` | I/O 密集型（文档解析、网络请求） | 协程（绿色线程） | ✅ | ✅ |
| `gevent` | I/O 密集型 | 协程（绿色线程） | ✅ | ✅ |
| `prefork` | CPU 密集型 | 多进程 | ❌ | ✅ |
| `threads` | 混合型 | 多线程 | ✅ | ✅ |

### 并发数（-c 参数）

- **solo**: 固定为 1，无法修改
- **eventlet/gevent**: 建议 10-50（协程开销小）
- **prefork**: 建议 CPU 核心数 * 2
- **threads**: 建议 CPU 核心数 * 4

## Windows 环境配置

### 开发环境（推荐）

```powershell
# 单线程，易调试，适合开发阶段
celery -A tasks.celery_tasks worker -l info -P solo
```

**优点**：
- 简单稳定，易于调试
- 不会出现并发问题
- 日志输出清晰
- 无需额外依赖

**缺点**：
- 无并发能力，任务排队执行
- 不适合多用户场景

### 生产环境（需要安装 eventlet）

**安装依赖**：
```powershell
# 安装 eventlet
uv pip install eventlet

# 或安装 gevent
uv pip install gevent
```

**启动命令**：
```powershell
# 使用 eventlet 协程池，5 个并发
celery -A tasks.celery_tasks worker -l info -P eventlet -c 5

# 或使用 gevent（类似 eventlet）
celery -A tasks.celery_tasks worker -l info -P gevent -c 5
```

**优点**：
- 支持并发，适合 I/O 密集型任务（文档解析、网络请求）
- 内存占用低（协程比线程轻量）
- Windows 原生支持

**缺点**：
- 不适合 CPU 密集型任务（如大规模计算）
- 需要安装额外依赖

**注意**：如果未安装 eventlet/gevent，启动时会报错 `ModuleNotFoundError: No module named 'eventlet'`。开发环境建议使用 `-P solo`。

### 高并发场景

```powershell
# 多个 Worker 进程，每个进程 5 个协程
# 窗口 1
celery -A tasks.celery_tasks worker -l info -P eventlet -c 5 -n worker1@%h

# 窗口 2
celery -A tasks.celery_tasks worker -l info -P eventlet -c 5 -n worker2@%h

# 窗口 3
celery -A tasks.celery_tasks worker -l info -P eventlet -c 5 -n worker3@%h
```

**说明**：
- `-n worker1@%h`：指定 Worker 名称（`%h` 是主机名）
- 总并发数 = Worker 数量 × 每个 Worker 的并发数（3 × 5 = 15）

## Linux 环境配置

### 生产环境（推荐）

```bash
# 使用 prefork 多进程池（最稳定）
celery -A tasks.celery_tasks worker -l info -P prefork -c 4

# 或使用 eventlet（更高并发）
celery -A tasks.celery_tasks worker -l info -P eventlet -c 20
```

**prefork 优点**：
- 进程隔离，一个任务崩溃不影响其他任务
- 适合 CPU 密集型任务
- Celery 默认推荐

**eventlet 优点**：
- 更高并发数（协程开销小）
- 适合 I/O 密集型任务
- 内存占用低

### 使用 Systemd 管理（推荐）

```ini
# /etc/systemd/system/celery-worker.service
[Unit]
Description=Celery Worker
After=network.target redis.target postgresql.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/opt/genesis-ai-platform
Environment="PATH=/opt/genesis-ai-platform/.venv/bin"
ExecStart=/opt/genesis-ai-platform/.venv/bin/celery -A tasks.celery_tasks worker \
    -l info \
    -P eventlet \
    -c 10 \
    --pidfile=/var/run/celery/worker.pid \
    --logfile=/var/log/celery/worker.log \
    --detach

ExecStop=/opt/genesis-ai-platform/.venv/bin/celery -A tasks.celery_tasks control shutdown
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**启动服务**：
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-worker
sudo systemctl start celery-worker
sudo systemctl status celery-worker
```

## 参数详解

### 基础参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `-A` | 指定 Celery 应用 | `-A tasks.celery_tasks` |
| `-l` | 日志级别 | `-l info`（debug/info/warning/error） |
| `-P` | Worker Pool 类型 | `-P eventlet` |
| `-c` | 并发数 | `-c 5` |
| `-n` | Worker 名称 | `-n worker1@%h` |
| `-Q` | 监听的队列 | `-Q default,parsing,embedding` |

### 高级参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `--max-tasks-per-child` | 每个 Worker 子进程最多执行多少任务后重启（防止内存泄漏） | `1000` |
| `--max-memory-per-child` | 每个 Worker 子进程最大内存（KB），超过后重启 | `500000`（500MB） |
| `--time-limit` | 任务硬超时（秒），超过后强制 Kill | `3600`（1 小时） |
| `--soft-time-limit` | 任务软超时（秒），超过后抛出异常 | `3000`（50 分钟） |
| `--prefetch-multiplier` | 预取任务数量倍数 | `1`（低延迟）或 `4`（高吞吐） |

### 示例：完整生产配置

```bash
celery -A tasks.celery_tasks worker \
    -l info \
    -P eventlet \
    -c 10 \
    -n worker@%h \
    --max-tasks-per-child=1000 \
    --max-memory-per-child=500000 \
    --time-limit=3600 \
    --soft-time-limit=3000 \
    --prefetch-multiplier=1
```

## 队列设计

### 按任务类型分队列

```python
# tasks/celery_tasks.py
app.conf.task_routes = {
    'parse_document_task': {'queue': 'parsing'},      # 文档解析队列
    'generate_embeddings_task': {'queue': 'embedding'}, # 向量生成队列
    'cleanup_zombie_tasks': {'queue': 'maintenance'},  # 维护任务队列
}
```

### 启动多个 Worker 监听不同队列

```powershell
# Worker 1：专门处理文档解析（高优先级）
celery -A tasks.celery_tasks worker -l info -P eventlet -c 3 -Q parsing -n parsing-worker@%h

# Worker 2：专门处理向量生成（中优先级）
celery -A tasks.celery_tasks worker -l info -P eventlet -c 5 -Q embedding -n embedding-worker@%h

# Worker 3：处理维护任务（低优先级）
celery -A tasks.celery_tasks worker -l info -P solo -Q maintenance -n maintenance-worker@%h
```

**优点**：
- 高优先级任务不会被低优先级任务阻塞
- 可以针对不同任务类型优化并发数
- 便于监控和调试

## 监控

### Flower（Web 监控界面）

```powershell
# 启动 Flower
celery -A tasks.celery_tasks flower --port=5555

# 访问
http://localhost:5555
```

**功能**：
- 实时查看任务队列长度
- 查看 Worker 状态和负载
- 查看任务执行历史和耗时
- 手动重试失败任务
- 查看任务参数和结果

### 命令行监控

```powershell
# 查看活跃任务
celery -A tasks.celery_tasks inspect active

# 查看已注册任务
celery -A tasks.celery_tasks inspect registered

# 查看 Worker 状态
celery -A tasks.celery_tasks inspect stats

# 查看队列长度
celery -A tasks.celery_tasks inspect reserved
```

## 性能优化建议

### 1. 任务幂等性

确保任务可以安全重试，不会产生副作用：

```python
@shared_task(bind=True, max_retries=3)
def parse_document_task(self, kb_doc_id: str):
    # ✅ 使用分布式锁防止并发执行
    with redis_lock(f"parsing:{kb_doc_id}"):
        # ✅ 检查任务是否已完成
        if is_already_parsed(kb_doc_id):
            return "already_parsed"
        
        # 执行解析
        parse_document(kb_doc_id)
```

### 2. 任务拆分

将大任务拆分为多个小任务，提高并发度：

```python
# ❌ 不推荐：一个任务处理整个知识库
@shared_task
def parse_all_documents(kb_id: str):
    for doc_id in get_all_documents(kb_id):
        parse_document(doc_id)

# ✅ 推荐：每个文档一个任务
@shared_task
def parse_document_task(doc_id: str):
    parse_document(doc_id)

# 调用时
for doc_id in get_all_documents(kb_id):
    parse_document_task.delay(doc_id)
```

### 3. 结果后端

如果不需要任务结果，禁用结果后端以提高性能：

```python
# tasks/celery_tasks.py
app.conf.task_ignore_result = True  # 全局禁用

# 或针对特定任务
@shared_task(ignore_result=True)
def parse_document_task(doc_id: str):
    pass
```

### 4. 预取优化

```python
# 低延迟场景（任务执行时间短）
app.conf.worker_prefetch_multiplier = 4  # 每个 Worker 预取 4 倍并发数的任务

# 高延迟场景（任务执行时间长）
app.conf.worker_prefetch_multiplier = 1  # 每个 Worker 只预取 1 个任务
```

## 故障排查

### 常见问题

#### 1. 任务一直 Pending

**原因**：
- Worker 未启动
- Worker 未监听对应队列
- Redis 连接失败

**排查**：
```powershell
# 检查 Worker 是否运行
celery -A tasks.celery_tasks inspect active

# 检查 Redis 连接
redis-cli ping
```

#### 2. 任务执行失败但不重试

**原因**：
- 未配置 `max_retries`
- 异常类型不在 `autoretry_for` 中

**解决**：
```python
@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,)  # 所有异常都重试
)
def my_task(self):
    pass
```

#### 3. 内存占用过高

**原因**：
- 任务处理大文件未释放内存
- Worker 子进程未定期重启

**解决**：
```powershell
# 启动时添加参数
celery -A tasks.celery_tasks worker -l info -P eventlet -c 5 --max-tasks-per-child=100
```

#### 4. 任务超时

**原因**：
- 任务执行时间过长
- 未配置超时参数

**解决**：
```python
@shared_task(
    soft_time_limit=600,  # 10 分钟软超时
    time_limit=660        # 11 分钟硬超时
)
def my_task():
    pass
```

## 安全建议

1. **不要在任务参数中传递敏感信息**（如密码、Token）
2. **使用 Redis 密码认证**
3. **限制 Flower 访问**（使用 `--basic_auth=user:password`）
4. **定期清理过期任务结果**
5. **监控任务失败率**，及时发现异常

## 总结

| 环境 | 推荐配置 | 并发数 | 适用场景 |
|------|----------|--------|----------|
| Windows 开发 | `-P solo` | 1 | 单人开发调试 |
| Windows 生产 | `-P eventlet -c 5` | 5 | 小团队使用 |
| Linux 生产 | `-P eventlet -c 20` | 20 | 多用户高并发 |
| Linux 高负载 | `-P prefork -c 8` | 8 | CPU 密集型任务 |

**关键原则**：
- 开发环境优先稳定性（solo）
- 生产环境优先并发能力（eventlet/prefork）
- 根据任务类型选择 Pool 类型（I/O 密集用 eventlet，CPU 密集用 prefork）
- 合理配置超时和重试参数
- 使用 Flower 监控任务状态
