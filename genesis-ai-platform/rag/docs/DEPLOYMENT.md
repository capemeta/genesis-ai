# Celery Worker 部署指南

## 核心原则

**不要在 Celery Worker 内部再创建多进程！**

Celery Worker 本身就是独立进程，通过配置 Worker 的并发模式和数量来实现并行处理。

## Worker 配置策略

### 1. 解析队列（CPU 密集）

```bash
# 使用 prefork 模式 + 低并发
celery -A tasks worker \
  -Q parse \
  --pool=prefork \
  --concurrency=4 \
  -n parse@%h \
  --max-tasks-per-child=10 \
  --time-limit=600 \
  --soft-time-limit=540

# 说明：
# - prefork: 多进程池，每个进程独立，不受 GIL 限制
# - concurrency=4: 4 个子进程并发处理
# - max-tasks-per-child=10: 每个进程处理 10 个任务后重启（防止内存泄漏）
# - time-limit: 硬超时 10 分钟
# - soft-time-limit: 软超时 9 分钟（先尝试优雅退出）
```

### 2. 分块队列（CPU 轻量）

```bash
# 使用 prefork 模式 + 中等并发
celery -A tasks worker \
  -Q chunk \
  --pool=prefork \
  --concurrency=2 \
  -n chunk@%h \
  --max-tasks-per-child=20 \
  --time-limit=300 \
  --soft-time-limit=270
```

### 3. 训练队列（I/O 密集）

```bash
# 使用 gevent 模式 + 高并发
celery -A tasks worker \
  -Q train \
  --pool=gevent \
  --concurrency=100 \
  -n train@%h \
  --time-limit=600 \
  --soft-time-limit=540

# 说明：
# - gevent: 协程池，适合 I/O 密集任务（API 调用）
# - concurrency=100: 100 个协程并发
# - 向量化、LLM 调用等都是 I/O 密集，适合高并发
```

### 4. 增强队列（I/O 密集 + LLM）

```bash
# 使用 gevent 模式 + 中等并发
celery -A tasks worker \
  -Q enhance \
  --pool=gevent \
  --concurrency=50 \
  -n enhance@%h \
  --time-limit=600 \
  --soft-time-limit=540
```

## 并发模式对比

| 模式 | 适用场景 | GIL 影响 | 并发能力 | 内存开销 |
|------|----------|----------|----------|----------|
| **prefork** | CPU 密集（解析、分块） | ✅ 无影响（多进程） | 中（4-8） | 高 |
| **solo** | 极端 CPU 密集 | ✅ 无影响（单进程单任务） | 低（1） | 低 |
| **gevent** | I/O 密集（API 调用） | ⚠️ 有影响（单进程） | 高（100+） | 低 |
| **eventlet** | I/O 密集（备选） | ⚠️ 有影响（单进程） | 高（100+） | 低 |

## 完整部署示例

### 开发环境（单机）

```bash
# 启动所有队列（单个 Worker 处理所有队列）
celery -A tasks worker \
  -Q parse,chunk,enhance,train \
  --pool=prefork \
  --concurrency=4 \
  -n worker@%h \
  --loglevel=info
```

### 生产环境（多 Worker）

```bash
# 1. 解析 Worker（CPU 密集）
celery -A tasks worker -Q parse --pool=prefork --concurrency=4 -n parse@%h &

# 2. 分块 Worker（CPU 轻量）
celery -A tasks worker -Q chunk --pool=prefork --concurrency=2 -n chunk@%h &

# 3. 增强 Worker（I/O 密集）
celery -A tasks worker -Q enhance --pool=gevent --concurrency=50 -n enhance@%h &

# 4. 训练 Worker（I/O 密集）
celery -A tasks worker -Q train --pool=gevent --concurrency=100 -n train@%h &

# 5. 启动 Celery Beat（定时任务）
celery -A tasks beat --loglevel=info &

# 6. 启动 Flower（监控）
celery -A tasks flower --port=5555 &
```

### Docker Compose 部署

```yaml
version: '3.8'

services:
  # 解析 Worker
  celery-parse:
    build: .
    command: celery -A tasks worker -Q parse --pool=prefork --concurrency=4 -n parse@%h
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
    deploy:
      replicas: 2  # 2 个实例
      resources:
        limits:
          cpus: '2.0'
          memory: 4G

  # 分块 Worker
  celery-chunk:
    build: .
    command: celery -A tasks worker -Q chunk --pool=prefork --concurrency=2 -n chunk@%h
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 2G

  # 增强 Worker
  celery-enhance:
    build: .
    command: celery -A tasks worker -Q enhance --pool=gevent --concurrency=50 -n enhance@%h
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '0.5'
          memory: 1G

  # 训练 Worker
  celery-train:
    build: .
    command: celery -A tasks worker -Q train --pool=gevent --concurrency=100 -n train@%h
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 1G

  # Celery Beat
  celery-beat:
    build: .
    command: celery -A tasks beat --loglevel=info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis

  # Flower 监控
  celery-flower:
    build: .
    command: celery -A tasks flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

## 任务路由配置

```python
# tasks/celery_tasks.py

celery_app.conf.update(
    # 任务路由：不同任务发送到不同队列
    task_routes={
        'rag.ingestion.tasks.parse_document_task_new': {'queue': 'parse'},
        'rag.ingestion.tasks.chunk_document_task_new': {'queue': 'chunk'},
        'rag.ingestion.tasks.enhance_chunks_task_new': {'queue': 'enhance'},
        'rag.ingestion.tasks.train_document_task_new': {'queue': 'train'},
        'rag.ingestion.tasks.vectorize_segments_task_new': {'queue': 'train'},
    },
    
    # Worker 配置
    worker_prefetch_multiplier=1,  # 每次只预取 1 个任务（避免任务堆积）
    worker_max_tasks_per_child=50,  # 每个子进程处理 50 个任务后重启
    
    # 任务超时
    task_soft_time_limit=540,  # 9 分钟软超时
    task_time_limit=600,  # 10 分钟硬超时
    
    # 任务确认
    task_acks_late=True,  # 任务完成后才确认（防止任务丢失）
    task_reject_on_worker_lost=True,  # Worker 崩溃时重新入队
    
    # 结果后端
    result_expires=3600,  # 结果保留 1 小时
)
```

## 监控与调优

### 1. 使用 Flower 监控

访问 `http://localhost:5555` 查看：
- 实时任务执行状态
- Worker 状态和负载
- 队列长度
- 任务耗时统计

### 2. 性能调优

```bash
# 查看队列长度
celery -A tasks inspect active_queues

# 查看 Worker 状态
celery -A tasks inspect stats

# 查看正在执行的任务
celery -A tasks inspect active

# 查看已注册的任务
celery -A tasks inspect registered
```

### 3. 日志配置

```python
# core/config/settings.py

CELERY_WORKER_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
CELERY_WORKER_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'
```

## 常见问题

### Q1: 为什么不在 Celery Worker 内部再创建多进程？

**A**: Celery Worker 本身就是独立进程，通过配置 `--pool=prefork --concurrency=N` 已经实现了多进程并发。再嵌套多进程会：
- 增加管理复杂度
- 增加资源开销
- 难以监控和调试
- 可能导致进程泄漏

### Q2: CPU 密集任务应该用什么模式？

**A**: 使用 `prefork` 模式，每个子进程独立，不受 GIL 限制：
```bash
celery -A tasks worker -Q parse --pool=prefork --concurrency=4
```

### Q3: I/O 密集任务应该用什么模式？

**A**: 使用 `gevent` 或 `eventlet` 模式，协程并发：
```bash
celery -A tasks worker -Q train --pool=gevent --concurrency=100
```

### Q4: 如何防止内存泄漏？

**A**: 配置 `--max-tasks-per-child`，定期重启子进程：
```bash
celery -A tasks worker --max-tasks-per-child=50
```

### Q5: 如何处理长时间运行的任务？

**A**: 配置合理的超时时间：
```bash
celery -A tasks worker --time-limit=600 --soft-time-limit=540
```

## 总结

1. **不要在 Celery Worker 内部再创建多进程**
2. **通过配置 Worker 的并发模式和数量实现并行**
3. **CPU 密集用 prefork，I/O 密集用 gevent**
4. **不同类型任务使用不同队列和 Worker**
5. **使用 Flower 监控和调优**
