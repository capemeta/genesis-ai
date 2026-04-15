# Celery 任务状态流转与僵尸清理机制

## 任务状态流转

### 1. 正常流程

```
用户上传文档
    ↓
API 创建 KnowledgeBaseDocument 记录
    ↓
parse_status = "queued"  ← 任务提交到 Celery 队列
task_id = <celery_task_id>
    ↓
Celery Worker 获取任务
    ↓
尝试获取分布式锁 (Redis)
    ↓
获取锁成功
    ↓
parse_status = "processing"  ← 任务开始执行
parse_started_at = 当前时间
updated_at = 当前时间
    ↓
执行解析逻辑
    ↓
parse_status = "completed"  ← 任务完成
parse_ended_at = 当前时间
chunk_count = N
    ↓
释放分布式锁
```

### 2. 并发冲突流程

```
任务 A 和任务 B 同时解析同一文档
    ↓
任务 A 获取锁成功
    ↓
任务 B 尝试获取锁失败
    ↓
任务 B 抛出 ValueError("文档正在被其他任务解析")
    ↓
任务 B 不重试，直接返回 {"status": "skipped"}
```

### 3. 任务失败流程

```
任务执行过程中发生异常
    ↓
捕获异常，回滚事务
    ↓
parse_status = "failed"
parse_error = 异常信息
parse_ended_at = 当前时间
    ↓
释放分布式锁
    ↓
如果重试次数 < 3，触发重试（指数退避）
如果重试次数 >= 3，标记为最终失败
```

### 4. 任务超时流程

```
任务执行超过 10 分钟（软超时）
    ↓
抛出 SoftTimeLimitExceeded 异常
    ↓
parse_status = "failed"
parse_error = "解析超时（超过 10 分钟）"
    ↓
释放分布式锁
    ↓
不重试（超时任务不应该重试）
```

### 5. Worker 崩溃流程

```
任务正在执行
    ↓
Worker 进程崩溃（kill -9, 断电等）
    ↓
分布式锁在 12 分钟后自动释放
parse_status 仍然是 "processing"
parse_started_at 是崩溃前的时间
    ↓
僵尸清理任务运行（每 10 分钟）
    ↓
检测到僵尸任务（见下文）
    ↓
parse_status = "failed"
parse_error = "任务超时（超过 30 分钟未完成），可能由于 Worker 崩溃"
```

## 僵尸清理机制

### 僵尸任务的判定条件（必须同时满足）

1. **状态检查**：`parse_status = "processing"`
2. **时间检查**：`parse_started_at` 超过 30 分钟前
3. **锁检查**：没有持有分布式锁（`parsing:lock:{kb_doc_id}` 不存在）
4. **开始时间检查**：`parse_started_at IS NOT NULL`（任务已经开始执行）

### 为什么需要这四个条件？

#### 条件 1：状态检查
- 只清理 `processing` 状态的任务
- `queued` 状态的任务在队列中等待，不清理
- `completed` 和 `failed` 状态的任务已经结束，不清理

#### 条件 2：时间检查
- 使用 `parse_started_at` 而不是 `updated_at`
- `parse_started_at` 反映任务真正开始执行的时间
- 避免误杀刚开始执行的任务

#### 条件 3：锁检查
- 检查 Redis 中是否存在 `parsing:lock:{kb_doc_id}`
- 如果锁存在，说明任务正在执行，不清理
- 如果锁不存在，说明任务已经不在执行（可能崩溃）

#### 条件 4：开始时间检查
- 如果 `parse_started_at IS NULL`，说明任务还在队列中等待
- 任务在队列中等待 30 分钟是正常的（高负载场景）
- 只清理已经开始执行但长时间未完成的任务

### 清理流程

```python
# 每 10 分钟运行一次
@celery_app.task(name="cleanup_zombie_tasks_task")
def cleanup_zombie_tasks_task():
    # 1. 查询候选任务
    candidates = select(KnowledgeBaseDocument).where(
        parse_status = "processing",
        updated_at < 30 分钟前
    )
    
    # 2. 逐个检查
    for task in candidates:
        # 检查锁
        if redis.exists(f"parsing:lock:{task.id}"):
            continue  # 跳过，任务正在执行
        
        # 检查开始时间
        if task.parse_started_at is None:
            continue  # 跳过，任务在队列中等待
        
        # 检查超时
        age = now - task.parse_started_at
        if age < 30 分钟:
            continue  # 跳过，任务刚开始执行
        
        # 确认为僵尸，标记为失败
        task.parse_status = "failed"
        task.parse_error = "任务超时（超过 30 分钟未完成）"
```

## 场景分析

### 场景 1：任务在队列中等待 1 小时

```
状态：parse_status = "queued"
结果：不会被清理（状态不是 processing）
```

### 场景 2：任务正在执行（5 分钟）

```
状态：parse_status = "processing"
锁：存在
parse_started_at：5 分钟前
结果：不会被清理（持有锁）
```

### 场景 3：任务正在执行（35 分钟）

```
状态：parse_status = "processing"
锁：存在
parse_started_at：35 分钟前
结果：不会被清理（持有锁，说明任务仍在执行）
```

### 场景 4：Worker 崩溃（35 分钟前）

```
状态：parse_status = "processing"
锁：不存在（12 分钟后自动释放）
parse_started_at：35 分钟前
结果：会被清理（僵尸任务）
```

### 场景 5：任务刚获得锁（1 分钟前）

```
状态：parse_status = "processing"
锁：存在
parse_started_at：1 分钟前
结果：不会被清理（刚开始执行）
```

### 场景 6：任务在队列中等待（35 分钟）

```
状态：parse_status = "processing"  ← 注意：这是错误的，应该是 "queued"
锁：不存在
parse_started_at：NULL
结果：不会被清理（parse_started_at 是 NULL）
```

**注意**：场景 6 在当前实现中不会发生，因为任务提交时状态是 `queued`，只有获得锁后才会变为 `processing`。

## 分布式锁设计

### 锁的生命周期

```
任务开始执行
    ↓
获取锁：redis.lock("parsing:lock:{kb_doc_id}", timeout=720)
    ↓
锁超时时间：12 分钟（比任务超时 10 分钟多 2 分钟）
    ↓
任务完成或失败
    ↓
释放锁：lock.release()
    ↓
如果任务崩溃，锁在 12 分钟后自动释放
```

### 为什么锁超时是 12 分钟？

- 任务软超时：10 分钟
- 任务硬超时：11 分钟
- 锁超时：12 分钟

**原因**：
1. 如果任务正常执行，会在 10 分钟内完成并释放锁
2. 如果任务超时，会在 10-11 分钟被强制终止
3. 锁在 12 分钟后自动释放，确保不会永久占用
4. 僵尸清理在 30 分钟后运行，此时锁早已释放

## 时间参数配置

| 参数 | 值 | 说明 |
|------|------|------|
| 任务软超时 | 10 分钟 | 抛出异常，可以优雅处理 |
| 任务硬超时 | 11 分钟 | 强制 Kill 进程 |
| 分布式锁超时 | 12 分钟 | 自动释放锁 |
| 僵尸清理超时 | 30 分钟 | 清理长时间未完成的任务 |
| 僵尸清理频率 | 10 分钟 | 定时任务执行频率 |

**设计原则**：
- 锁超时 > 任务硬超时（避免任务还在执行时锁被释放）
- 僵尸清理超时 > 锁超时（确保锁已经释放）
- 僵尸清理频率 < 僵尸清理超时（避免频繁清理）

## 监控指标

### 推荐监控的指标

1. **任务状态分布**
   - queued 数量
   - processing 数量
   - completed 数量
   - failed 数量

2. **任务执行时间**
   - 平均执行时间
   - P50, P95, P99 执行时间
   - 超时任务数量

3. **僵尸清理统计**
   - 清理的僵尸任务数量
   - 跳过的任务数量（持有锁）
   - 等待的任务数量（在队列中）

4. **队列长度**
   - 待处理任务数量
   - 队列等待时间

5. **Worker 状态**
   - 活跃 Worker 数量
   - Worker 负载
   - Worker 崩溃次数

## 故障排查

### 问题 1：任务一直处于 queued 状态

**可能原因**：
- Worker 未启动
- Worker 数量不足
- 队列阻塞

**排查步骤**：
1. 检查 Worker 是否运行：`celery -A tasks.celery_tasks inspect active`
2. 检查队列长度：`celery -A tasks.celery_tasks inspect reserved`
3. 检查 Worker 日志

### 问题 2：任务一直处于 processing 状态

**可能原因**：
- Worker 崩溃
- 任务卡住（死锁、无限循环）
- 网络中断

**排查步骤**：
1. 检查分布式锁：`redis-cli GET parsing:lock:{kb_doc_id}`
2. 检查 Worker 日志
3. 等待僵尸清理任务运行（最多 30 分钟）

### 问题 3：任务被误判为僵尸

**可能原因**：
- 僵尸清理超时时间设置过短
- 任务执行时间过长

**解决方案**：
1. 增加僵尸清理超时时间（默认 30 分钟）
2. 增加任务超时时间（默认 10 分钟）
3. 检查任务是否真的需要这么长时间

### 问题 4：大量任务超时

**可能原因**：
- 文件过大
- 解析算法效率低
- Worker 资源不足

**解决方案**：
1. 增加任务超时时间
2. 优化解析算法
3. 增加 Worker 数量
4. 使用更强大的服务器

## 最佳实践

1. **合理设置超时时间**
   - 根据实际文件大小和解析速度调整
   - 软超时应该略小于硬超时
   - 锁超时应该略大于硬超时

2. **监控任务状态**
   - 使用 Flower 监控任务队列
   - 设置告警（任务失败率、队列长度）
   - 定期检查僵尸清理日志

3. **优化任务执行**
   - 避免在任务中执行耗时操作
   - 使用流式处理大文件
   - 合理拆分任务

4. **容错设计**
   - 任务应该是幂等的
   - 使用分布式锁防止并发
   - 合理设置重试策略

5. **资源管理**
   - 正确关闭数据库连接
   - 正确关闭 Redis 连接
   - 避免内存泄漏
