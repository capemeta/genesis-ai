# RAG 分块流程最佳实践

## 核心原则：根据任务类型选择同步/异步

### 任务分类

| 任务类型 | 特征 | 推荐方式 | Worker 配置 | 并发能力 |
|---------|------|---------|------------|----------|
| **解析任务** | CPU 密集（文件解析） | ✅ 同步 | `prefork --concurrency=4` | 4 个进程 |
| **分块任务** | CPU 密集（文本处理） | ✅ 同步 | `prefork --concurrency=2` | 2 个进程 |
| **增强任务** | I/O 密集（LLM API） | ✅ 异步 | `gevent --concurrency=50` | 50 个协程 |
| **训练任务** | I/O 密集（Embedding API） | ✅ 异步 | `gevent --concurrency=100` | 100 个协程 |

## 一、CPU 密集型任务（同步实现）

### 适用场景
- 文件解析（PDF/Word/Excel）
- 文本分块（正则、递归切分）
- 数据处理（计算密集）

### 实现方式

```python
# ✅ 正确：同步实现
@celery_app.task
def parse_document_task(document_id, file_buffer):
    """CPU 密集任务，同步执行"""
    # 直接同步执行，简单直接
    text = parse_pdf(file_buffer)
    return text

@celery_app.task
def chunk_document_task(document_id, text):
    """CPU 密集任务，同步执行"""
    chunker = MarkdownChunker()
    chunks = chunker.chunk(text)
    return chunks
```

### 部署配置

```bash
# CPU 密集任务使用 prefork 模式（多进程）
celery -A tasks worker \
  -Q parse,chunk \
  --pool=prefork \
  --concurrency=4 \
  -n cpu_worker@%h
```

### 为什么不用异步？

- ❌ CPU 密集任务用异步**没有性能提升**（受 GIL 限制）
- ❌ 反而增加 event loop 开销
- ✅ 并发通过多个 Worker 进程实现（已经绕过 GIL）

## 二、I/O 密集型任务（异步实现）

### 适用场景
- LLM API 调用（关键词、问题、摘要提取）
- Embedding API 调用（向量化）
- 数据库查询（大量并发查询）
- 网络请求（HTTP API 调用）

### 实现方式

```python
# ✅ 正确：异步实现
@celery_app.task
def enhance_chunks_task(document_id, segment_ids):
    """I/O 密集任务，异步执行"""
    # 使用 asyncio.run 在同步任务中运行异步代码
    return asyncio.run(_enhance_chunks_async(document_id, segment_ids))

async def _enhance_chunks_async(document_id, segment_ids):
    """异步实现"""
    # 加载数据
    chunks = await load_chunks_async(segment_ids)
    
    # 并发调用 LLM API（关键优化点！）
    tasks = [enhancer.enhance(chunk) for chunk in chunks]
    enhanced_chunks = await asyncio.gather(*tasks)
    
    # 保存结果
    await save_chunks_async(segment_ids, enhanced_chunks)
    
    return {"enhanced_count": len(enhanced_chunks)}
```

### 部署配置

```bash
# I/O 密集任务使用 gevent 模式（协程）
celery -A tasks worker \
  -Q enhance,train \
  --pool=gevent \
  --concurrency=100 \
  -n io_worker@%h
```

### 性能对比

**场景：处理 100 个分块，每个分块调用 LLM API（耗时 2 秒）**

| 方式 | 并发能力 | 总耗时 | 性能提升 |
|------|---------|--------|---------|
| 同步 + prefork (4进程) | 4 个任务 | 100 / 4 * 2 = 50 秒 | 基准 |
| **异步 + gevent (50协程)** | **50 个任务** | **100 / 50 * 2 = 4 秒** | **12.5倍** |
| **异步 + gevent (100协程)** | **100 个任务** | **100 / 100 * 2 = 2 秒** | **25倍** |

## 三、完整部署示例

### 开发环境（单机）

```bash
# 启动所有队列（单个 Worker 处理所有队列）
celery -A tasks worker \
  -Q parse,chunk,enhance,train \
  --pool=prefork \
  --concurrency=4 \
  -n dev_worker@%h \
  --loglevel=info
```

### 生产环境（多 Worker）

```bash
# 1. CPU 密集 Worker（解析 + 分块）
celery -A tasks worker \
  -Q parse,chunk \
  --pool=prefork \
  --concurrency=4 \
  -n cpu_worker@%h \
  --max-tasks-per-child=10 \
  --time-limit=600 \
  --soft-time-limit=540 &

# 2. I/O 密集 Worker（增强）
celery -A tasks worker \
  -Q enhance \
  --pool=gevent \
  --concurrency=50 \
  -n enhance_worker@%h \
  --time-limit=600 \
  --soft-time-limit=540 &

# 3. I/O 密集 Worker（训练）
celery -A tasks worker \
  -Q train \
  --pool=gevent \
  --concurrency=100 \
  -n train_worker@%h \
  --time-limit=600 \
  --soft-time-limit=540 &

# 4. Celery Beat（定时任务）
celery -A tasks beat --loglevel=info &

# 5. Flower（监控）
celery -A tasks flower --port=5555 &
```

### Docker Compose 部署

```yaml
version: '3.8'

services:
  # CPU 密集 Worker
  celery-cpu:
    build: .
    command: celery -A tasks worker -Q parse,chunk --pool=prefork --concurrency=4 -n cpu@%h
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2.0'
          memory: 4G

  # I/O 密集 Worker（增强）
  celery-enhance:
    build: .
    command: celery -A tasks worker -Q enhance --pool=gevent --concurrency=50 -n enhance@%h
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '0.5'
          memory: 1G

  # I/O 密集 Worker（训练）
  celery-train:
    build: .
    command: celery -A tasks worker -Q train --pool=gevent --concurrency=100 -n train@%h
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 1G
```

## 四、代码实现模式

### 模式 1：纯同步（CPU 密集）

```python
# 分块器基类
class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, text: str) -> List[Dict]:
        """同步分块方法"""
        pass

# 实现类
class MarkdownChunker(BaseChunker):
    def chunk(self, text: str) -> List[Dict]:
        # 直接同步执行
        return self._chunk_markdown(text)

# Celery 任务
@celery_app.task
def chunk_document_task(document_id, text):
    chunker = MarkdownChunker()
    chunks = chunker.chunk(text)  # 直接调用
    return chunks
```

### 模式 2：异步（I/O 密集）

```python
# 增强器基类
class BaseEnhancer(ABC):
    @abstractmethod
    async def enhance(self, chunk: Dict) -> Dict:
        """异步增强方法"""
        pass

# 实现类
class KeywordEnhancer(BaseEnhancer):
    async def enhance(self, chunk: Dict) -> Dict:
        # 异步调用 LLM API
        keywords = await call_llm_api_async(chunk["text"])
        chunk["keywords"] = keywords
        return chunk

# Celery 任务
@celery_app.task
def enhance_chunks_task(document_id, segment_ids):
    # 使用 asyncio.run 运行异步代码
    return asyncio.run(_enhance_async(segment_ids))

async def _enhance_async(segment_ids):
    chunks = await load_chunks_async(segment_ids)
    enhancer = KeywordEnhancer()
    
    # 并发增强所有分块
    tasks = [enhancer.enhance(chunk) for chunk in chunks]
    enhanced = await asyncio.gather(*tasks)
    
    return enhanced
```

## 五、常见问题

### Q1: 为什么不在 Celery Worker 内部再创建多进程？

**A**: Celery Worker 本身就是独立进程，通过配置 `--pool=prefork --concurrency=N` 已经实现了多进程并发。再嵌套多进程会：
- 增加管理复杂度
- 增加资源开销
- 难以监控和调试

### Q2: 异步任务如何在 Celery 中运行？

**A**: 使用 `asyncio.run()` 在同步 Celery 任务中运行异步代码：

```python
@celery_app.task
def my_async_task(data):
    return asyncio.run(_my_async_impl(data))

async def _my_async_impl(data):
    # 异步实现
    result = await async_operation(data)
    return result
```

### Q3: 如何选择 Worker 并发数？

**A**: 根据任务类型和资源：

- **CPU 密集**：并发数 = CPU 核心数（如 4 核 → `--concurrency=4`）
- **I/O 密集**：并发数 = 预期并发请求数（如 `--concurrency=50` 或 `100`）

### Q4: 如何监控任务执行？

**A**: 使用 Celery Flower：

```bash
celery -A tasks flower --port=5555
```

访问 `http://localhost:5555` 查看：
- 实时任务执行状态
- Worker 状态和负载
- 队列长度
- 任务耗时统计

## 六、性能调优建议

### 1. 批量处理

```python
# ❌ 错误：逐个处理
for segment_id in segment_ids:
    embedding = await call_embedding_api(segment_id)
    await save_embedding(segment_id, embedding)

# ✅ 正确：批量处理
texts = [get_text(id) for id in segment_ids]
embeddings = await batch_embed(texts)  # 批量调用
await batch_save(segment_ids, embeddings)  # 批量保存
```

### 2. 并发控制

```python
# 使用 Redis 信号量控制全局并发
from limiters import acquire_llm_slot, release_llm_slot

async def call_llm_with_limit(text):
    if not acquire_llm_slot():
        raise Exception("LLM 槽位已满")
    
    try:
        result = await call_llm_api(text)
        return result
    finally:
        release_llm_slot()
```

### 3. LLM 缓存

```python
# 使用 Redis 缓存 LLM 结果
from utils.llm_cache import llm_cache

@llm_cache(cache_ttl=3600)
async def extract_keywords(text: str):
    # 相同文本会直接返回缓存结果
    return await call_llm_api(text)
```

## 七、总结

| 任务 | 类型 | 实现方式 | Worker 配置 | 性能 |
|------|------|---------|------------|------|
| 解析 | CPU 密集 | 同步 | `prefork --concurrency=4` | ⭐⭐⭐⭐⭐ |
| 分块 | CPU 密集 | 同步 | `prefork --concurrency=2` | ⭐⭐⭐⭐⭐ |
| 增强 | I/O 密集 | **异步** | `gevent --concurrency=50` | ⭐⭐⭐⭐⭐ |
| 训练 | I/O 密集 | **异步** | `gevent --concurrency=100` | ⭐⭐⭐⭐⭐ |

**关键要点**：
1. CPU 密集用同步 + prefork（多进程）
2. I/O 密集用异步 + gevent（协程）
3. 不要在任务内部嵌套多进程
4. 使用 `asyncio.gather` 实现并发
5. 配置合理的 Worker 并发数
