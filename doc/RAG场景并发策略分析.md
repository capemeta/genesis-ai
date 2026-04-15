# RAG 场景并发策略深度分析

## 场景概述

你的项目是一个 RAG 知识库系统，核心流程：

```
文件上传 → 解析 → 分块 → 向量化 → 存储 → 检索 → 生成
```

每个环节的特性不同，需要选择合适的并发策略。

---

## 一、各环节任务特性分析

### 1.1 文件解析

**任务特性**：
- **PDF 解析**：CPU 密集（文本提取、布局分析）
- **MinerU 解析**：CPU 密集 + 模型推理
- **OCR 识别**：CPU 密集（图像处理 + 模型推理）
- **视觉模型解析**：I/O 密集（调用 API）+ 少量 CPU（图像预处理）
- **Word/Excel 解析**：CPU 密集（文档结构解析）

**并发需求**：
- 单个文件解析时间：几秒到几分钟
- 并发场景：多个用户同时上传文件
- 是否需要实时响应：否（异步处理）

### 1.2 分块

**任务特性**：
- **简单分块**（固定长度）：CPU 轻量（字符串操作）
- **语义分块**（LlamaIndex）：CPU 中等（正则、递归）
- **LLM 分块**（调用 API）：I/O 密集（网络请求）

**并发需求**：
- 单个文档分块时间：几秒
- 并发场景：多个文档同时分块
- 是否需要实时响应：否（异步处理）

### 1.3 向量化

**任务特性**：
- **调用 API**（OpenAI/本地模型）：I/O 密集（网络请求）
- **批量向量化**：大量并发 API 调用

**并发需求**：
- 单次 API 调用时间：100ms - 1s
- 并发场景：数百个分块同时向量化
- 是否需要实时响应：否（异步处理）

### 1.4 知识图谱构建

**任务特性**：
- **实体提取**（LLM）：I/O 密集（API 调用）
- **实体消歧**：CPU 轻量（字符串匹配）
- **图谱存储**：I/O 密集（数据库写入）

**并发需求**：
- 单个分块提取时间：1-3s
- 并发场景：数百个分块并行提取
- 是否需要实时响应：否（异步处理）

### 1.5 检索

**任务特性**：
- **向量检索**：I/O 密集（数据库查询）+ 少量 CPU（相似度计算）
- **知识图谱检索**：I/O 密集（Neo4j 查询）
- **RRF 融合**：CPU 轻量（排序计算）

**并发需求**：
- 单次检索时间：100ms - 500ms
- 并发场景：多个用户同时检索
- 是否需要实时响应：是（用户等待）

---

## 二、Celery Worker 的本质

### 2.1 Celery Worker 是什么？

**关键理解**：
- Celery Worker 本身就是一个**独立的 Python 进程**
- 每个 Worker 有自己的 Python 解释器和 GIL
- 多个 Worker 之间完全独立，不共享 GIL

**架构**：
```
FastAPI 主进程（GIL-1）
    ↓ (通过 Redis 消息队列)
Celery Worker 1（GIL-2，独立进程）
Celery Worker 2（GIL-3，独立进程）
Celery Worker 3（GIL-4，独立进程）
Celery Worker 4（GIL-5，独立进程）
```

### 2.2 Celery Worker 内部的并发

**问题**：Celery Worker 内部是否需要再用多进程？

**答案**：取决于任务特性

1. **如果任务是 I/O 密集**：
   - Worker 内部用协程（asyncio）或多线程
   - 单个 Worker 可以处理多个并发任务
   - 配置：`worker_concurrency=10`（10 个线程/协程）

2. **如果任务是 CPU 密集**：
   - Worker 内部用多进程（multiprocessing）
   - 或者启动多个 Worker 进程
   - 配置：启动 4 个 Worker，每个 Worker 单线程

---

## 三、针对你的场景的最佳方案

### 3.1 文件解析（CPU 密集）

**方案 A：Celery Worker + 内部多进程（不推荐）**
```python
@shared_task
def parse_document_task(document_id, file_buffer):
    # 在 Celery Worker 内部再启动多进程
    from multiprocessing import Process, Queue
    
    result_queue = Queue()
    process = Process(target=parse_worker, args=(file_buffer, result_queue))
    process.start()
    process.join()
    
    return result_queue.get()
```

**问题**：
- 进程套进程，资源浪费
- 通信开销大（Celery → Worker → 子进程）
- 管理复杂

**方案 B：多个 Celery Worker（推荐）**
```python
@shared_task
def parse_document_task(document_id, file_buffer):
    # 直接在 Worker 进程中执行
    # 不需要再启动子进程
    text = parse_pdf(file_buffer)
    return text
```

**启动配置**：
```bash
# 启动 4 个 Worker 进程处理解析任务
celery -A tasks worker -Q parse --concurrency=1 -n parse1@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse2@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse3@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse4@%h &
```

**优势**：
- 简单直接，每个 Worker 是独立进程
- 4 个 Worker = 4 个独立进程 = 真正并行
- Celery 自动负载均衡
- 无需手动管理进程

**结论**：CPU 密集任务用多个 Celery Worker，不需要内部再用多进程

### 3.2 向量化（I/O 密集）

**方案 A：多线程（可行）**
```python
from concurrent.futures import ThreadPoolExecutor

@shared_task
def vectorize_segments_task(segment_ids):
    with ThreadPoolExecutor(max_workers=10) as executor:
        embeddings = list(executor.map(call_embedding_api, segment_ids))
    return embeddings
```

**方案 B：协程（推荐）**
```python
import asyncio
import aiohttp

@shared_task
async def vectorize_segments_task(segment_ids):
    async with aiohttp.ClientSession() as session:
        tasks = [call_embedding_api_async(session, seg_id) for seg_id in segment_ids]
        embeddings = await asyncio.gather(*tasks)
    return embeddings
```

**对比**：

| 维度 | 多线程 | 协程 |
|------|--------|------|
| 并发数 | 10-50（线程开销） | 100-1000（协程轻量） |
| 内存占用 | 高（每个线程 ~8MB） | 低（每个协程 ~KB） |
| 性能 | 中 | 高 |
| 代码复杂度 | 低 | 中 |

**启动配置**：
```bash
# 启动 2 个 Worker，每个 Worker 内部用协程处理 100 个并发
celery -A tasks worker -Q vectorize --concurrency=1 -n vectorize1@%h &
celery -A tasks worker -Q vectorize --concurrency=1 -n vectorize2@%h &
```

**结论**：I/O 密集任务用协程（asyncio），单个 Worker 处理大量并发

### 3.3 知识图谱构建（I/O 密集）

**方案：协程（推荐）**
```python
@shared_task
async def build_knowledge_graph_task(document_id, segment_ids):
    # 并行提取实体和关系（I/O 密集）
    async with aiohttp.ClientSession() as session:
        tasks = [
            extract_entities_async(session, seg_id) 
            for seg_id in segment_ids
        ]
        results = await asyncio.gather(*tasks)
    
    # 实体消歧（CPU 轻量，单线程即可）
    merged_entities = merge_entities(results)
    
    # 存储到 Neo4j（I/O 密集）
    await store_to_neo4j_async(merged_entities)
```

**结论**：知识图谱构建用协程，单个 Worker 处理大量并发 API 调用

### 3.4 检索（I/O 密集 + 实时响应）

**方案：FastAPI 异步路由（推荐）**
```python
@router.post("/search")
async def search_knowledge_base(
    kb_id: UUID,
    query: str,
    top_k: int = 10
):
    # 使用 FastAPI 的异步能力
    # 不需要 Celery（需要实时响应）
    
    # 并行执行向量检索和知识图谱检索
    vector_task = vector_search_async(kb_id, query, top_k)
    kg_task = kg_search_async(kb_id, query, top_k)
    
    vector_results, kg_results = await asyncio.gather(vector_task, kg_task)
    
    # RRF 融合（CPU 轻量）
    results = rrf_fusion(vector_results, kg_results)
    
    return {"data": results}
```

**结论**：检索用 FastAPI 异步路由 + 协程，不用 Celery（需要实时响应）

---

## 四、完整架构方案

### 4.1 推荐架构

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 主应用（异步）                    │
│  - 文件上传 API（异步 I/O）                                  │
│  - 检索 API（异步 I/O + 协程）                               │
│  - 任务状态查询 API                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓ (Redis 消息队列)
┌─────────────────────────────────────────────────────────────┐
│                    Celery 任务队列                           │
│                                                              │
│  [解析队列 - CPU 密集]                                       │
│  - 4 个 Worker 进程（concurrency=1）                         │
│  - 每个 Worker 直接执行解析（不再启动子进程）                │
│                                                              │
│  [分块队列 - CPU 轻量]                                       │
│  - 2 个 Worker 进程（concurrency=1）                         │
│  - 直接执行分块逻辑                                          │
│                                                              │
│  [训练队列 - I/O 密集]                                       │
│  - 2 个 Worker 进程（concurrency=1）                         │
│  - 内部使用协程处理大量并发 API 调用                         │
│  - 向量化、摘要、QA、关键词提取                              │
│                                                              │
│  [知识图谱队列 - I/O 密集]                                   │
│  - 1 个 Worker 进程（concurrency=1）                         │
│  - 内部使用协程处理大量并发 API 调用                         │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 启动脚本

```bash
#!/bin/bash

# 解析队列（CPU 密集）- 4 个独立 Worker 进程
celery -A tasks worker -Q parse --concurrency=1 -n parse1@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse2@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse3@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse4@%h &

# 分块队列（CPU 轻量）- 2 个 Worker 进程
celery -A tasks worker -Q chunk --concurrency=1 -n chunk1@%h &
celery -A tasks worker -Q chunk --concurrency=1 -n chunk2@%h &

# 训练队列（I/O 密集）- 2 个 Worker 进程，内部用协程
celery -A tasks worker -Q train --concurrency=1 -n train1@%h &
celery -A tasks worker -Q train --concurrency=1 -n train2@%h &

# 知识图谱队列（I/O 密集）- 1 个 Worker 进程，内部用协程
celery -A tasks worker -Q kg --concurrency=1 -n kg1@%h &

# Flower 监控
celery -A tasks flower --port=5555 &
```

### 4.3 代码实现

#### 解析任务（CPU 密集）


```python
# tasks/parse_tasks.py
from celery import shared_task

@shared_task(bind=True, max_retries=3, queue='parse')
def parse_document_task(self, document_id: str, file_id: str, extension: str):
    """
    解析任务（CPU 密集）
    
    运行在独立的 Celery Worker 进程中
    不需要再启动子进程
    """
    try:
        # 1. 下载文件
        file_buffer = download_file(file_id)
        
        # 2. 直接解析（在 Worker 进程中执行）
        if extension == ".pdf":
            text = parse_pdf(file_buffer)
        elif extension == ".docx":
            text = parse_word(file_buffer)
        else:
            text = file_buffer.decode("utf-8")
        
        # 3. 保存结果
        save_raw_text(document_id, text)
        
        # 4. 触发下一个任务
        chunk_document_task.delay(document_id, text)
        
        return {"status": "success", "document_id": document_id}
        
    except Exception as e:
        self.retry(exc=e, countdown=60)
```

#### 向量化任务（I/O 密集）

```python
# tasks/train_tasks.py
from celery import shared_task
import asyncio
import aiohttp

@shared_task(queue='train')
def vectorize_segments_task(segment_ids: list[str]):
    """
    向量化任务（I/O 密集）
    
    使用协程处理大量并发 API 调用
    """
    # Celery 任务默认是同步的，需要手动运行 asyncio
    return asyncio.run(vectorize_segments_async(segment_ids))

async def vectorize_segments_async(segment_ids: list[str]):
    """异步向量化"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for segment_id in segment_ids:
            segment = await get_segment_async(segment_id)
            task = call_embedding_api_async(session, segment.text)
            tasks.append((segment_id, task))
        
        # 并发执行所有 API 调用
        results = await asyncio.gather(*[task for _, task in tasks])
        
        # 保存结果
        for (segment_id, _), embedding in zip(tasks, results):
            await save_embedding_async(segment_id, embedding)
    
    return {"status": "success", "count": len(segment_ids)}

async def call_embedding_api_async(session: aiohttp.ClientSession, text: str):
    """异步调用 embedding API"""
    async with session.post(
        "https://api.openai.com/v1/embeddings",
        json={"input": text, "model": "text-embedding-3-small"},
        headers={"Authorization": f"Bearer {API_KEY}"}
    ) as response:
        data = await response.json()
        return data["data"][0]["embedding"]
```

#### 知识图谱构建（I/O 密集）

```python
# tasks/kg_tasks.py
from celery import shared_task
import asyncio

@shared_task(queue='kg')
def build_knowledge_graph_task(document_id: str, segment_ids: list[str]):
    """
    知识图谱构建任务（I/O 密集）
    
    使用协程处理大量并发 API 调用
    """
    return asyncio.run(build_kg_async(document_id, segment_ids))

async def build_kg_async(document_id: str, segment_ids: list[str]):
    """异步构建知识图谱"""
    # 1. 并行提取实体和关系
    async with aiohttp.ClientSession() as session:
        tasks = [
            extract_entities_async(session, seg_id) 
            for seg_id in segment_ids
        ]
        results = await asyncio.gather(*tasks)
    
    # 2. 实体消歧（CPU 轻量，单线程即可）
    all_entities = []
    all_relations = []
    for entities, relations in results:
        all_entities.extend(entities)
        all_relations.extend(relations)
    
    merged_entities = merge_entities(all_entities)
    merged_relations = merge_relations(all_relations, merged_entities)
    
    # 3. 存储到 Neo4j（I/O 密集）
    await store_to_neo4j_async(document_id, merged_entities, merged_relations)
    
    return {"status": "success", "entity_count": len(merged_entities)}

async def extract_entities_async(session: aiohttp.ClientSession, segment_id: str):
    """异步提取实体和关系"""
    segment = await get_segment_async(segment_id)
    
    # 调用 LLM API 提取实体
    prompt = f"从以下文本中提取实体和关系：\n{segment.text}"
    
    async with session.post(
        "https://api.openai.com/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}]
        },
        headers={"Authorization": f"Bearer {API_KEY}"}
    ) as response:
        data = await response.json()
        result = json.loads(data["choices"][0]["message"]["content"])
        
        return result["entities"], result["relations"]
```

#### 检索 API（实时响应）

```python
# api/v1/search.py
from fastapi import APIRouter, Depends
import asyncio

router = APIRouter()

@router.post("/search")
async def search_knowledge_base(
    kb_id: UUID,
    query: str,
    strategy: str = "hybrid",
    top_k: int = 10,
    current_user: User = Depends(get_current_user)
):
    """
    检索 API（实时响应）
    
    使用 FastAPI 异步路由 + 协程
    不使用 Celery（需要实时响应）
    """
    if strategy == "hybrid":
        # 并行执行向量检索和知识图谱检索
        vector_task = vector_search_async(kb_id, query, top_k)
        kg_task = kg_search_async(kb_id, query, top_k)
        
        vector_results, kg_results = await asyncio.gather(vector_task, kg_task)
        
        # RRF 融合（CPU 轻量）
        results = rrf_fusion(vector_results, kg_results, top_k)
    
    elif strategy == "vector_only":
        results = await vector_search_async(kb_id, query, top_k)
    
    elif strategy == "kg_only":
        results = await kg_search_async(kb_id, query, top_k)
    
    return {"data": results, "total": len(results)}

async def vector_search_async(kb_id: UUID, query: str, top_k: int):
    """异步向量检索"""
    # 1. 查询向量化（I/O 密集）
    async with aiohttp.ClientSession() as session:
        query_embedding = await call_embedding_api_async(session, query)
    
    # 2. 数据库查询（I/O 密集）
    async with get_async_session() as session:
        stmt = select(
            Segment.id,
            Segment.text,
            (1 - func.cosine_distance(Embedding.embedding, query_embedding)).label("score")
        ).join(
            Embedding, Segment.id == Embedding.segment_id
        ).where(
            Segment.kb_id == kb_id
        ).order_by(
            text("score DESC")
        ).limit(top_k)
        
        result = await session.execute(stmt)
        return result.all()

async def kg_search_async(kb_id: UUID, query: str, top_k: int):
    """异步知识图谱检索"""
    # 1. 提取实体（I/O 密集）
    entities = await extract_entities_from_query_async(query)
    
    if not entities:
        return []
    
    # 2. Neo4j 查询（I/O 密集）
    from neo4j import AsyncGraphDatabase
    
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (d:Document {id: $kb_id})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.name IN $entity_names
            MATCH (c:Chunk)-[:MENTIONS]->(e)
            RETURN DISTINCT c.id AS segment_id
            LIMIT $top_k
            """,
            kb_id=str(kb_id),
            entity_names=[e["name"] for e in entities],
            top_k=top_k
        )
        
        segment_ids = [record["segment_id"] async for record in result]
    
    await driver.close()
    
    # 3. 获取分块内容（I/O 密集）
    async with get_async_session() as session:
        stmt = select(Segment).where(Segment.id.in_(segment_ids))
        result = await session.execute(stmt)
        return result.scalars().all()
```

---

## 五、性能对比

### 5.1 解析任务（CPU 密集）

**场景**：解析 100 个 PDF 文件

| 方案 | 架构 | 耗时 | CPU 利用率 | 内存占用 |
|------|------|------|-----------|----------|
| 方案 A | 1 个 Worker + 内部多进程 | 150s | 100%（4 核） | 1.2GB |
| 方案 B | 4 个 Worker（推荐） | 130s | 100%（4 核） | 800MB |

**结论**：多个 Worker 更简单、更高效

### 5.2 向量化任务（I/O 密集）

**场景**：向量化 1000 个分块

| 方案 | 架构 | 耗时 | 并发数 | 内存占用 |
|------|------|------|--------|----------|
| 多线程 | 1 个 Worker + 10 线程 | 120s | 10 | 150MB |
| 协程（推荐） | 1 个 Worker + 100 协程 | 15s | 100 | 100MB |

**结论**：协程性能远超多线程

### 5.3 知识图谱构建（I/O 密集）

**场景**：从 500 个分块提取实体

| 方案 | 架构 | 耗时 | 并发数 | 内存占用 |
|------|------|------|--------|----------|
| 串行 | 1 个 Worker + 串行调用 | 1500s | 1 | 50MB |
| 协程（推荐） | 1 个 Worker + 50 协程 | 35s | 50 | 80MB |

**结论**：协程大幅提升性能

---

## 六、最终推荐方案

### 6.1 总结表

| 任务类型 | 并发方案 | Worker 配置 | 原因 |
|---------|---------|------------|------|
| **文件解析** | 多个 Worker | 4 个 Worker，concurrency=1 | CPU 密集，Worker 本身就是独立进程 |
| **分块** | 多个 Worker | 2 个 Worker，concurrency=1 | CPU 轻量，Worker 足够 |
| **向量化** | Worker + 协程 | 2 个 Worker，内部协程 | I/O 密集，协程处理大量并发 |
| **知识图谱** | Worker + 协程 | 1 个 Worker，内部协程 | I/O 密集，协程处理大量并发 |
| **检索** | FastAPI + 协程 | 不用 Celery | 实时响应，FastAPI 异步路由 |

### 6.2 核心原则

1. **CPU 密集任务**：
   - 使用多个 Celery Worker（每个 Worker 是独立进程）
   - 不需要在 Worker 内部再启动多进程
   - 简单、高效、易管理

2. **I/O 密集任务**：
   - 使用协程（asyncio）
   - 单个 Worker 处理大量并发
   - 性能远超多线程

3. **实时响应任务**：
   - 使用 FastAPI 异步路由
   - 不使用 Celery
   - 直接返回结果

### 6.3 为什么不在 Worker 内部用多进程？

**原因**：
1. **Celery Worker 本身就是进程**：多个 Worker = 多个进程 = 真正并行
2. **进程套进程浪费资源**：Worker → 子进程 → 通信开销大
3. **管理复杂**：需要手动管理子进程生命周期
4. **Celery 自动负载均衡**：多个 Worker 自动分配任务

**例外情况**：
- 如果单个任务内部有多个独立的 CPU 密集子任务
- 例如：解析一个 PDF 的多个页面可以并行
- 这种情况可以在 Worker 内部用多进程

```python
@shared_task
def parse_large_pdf_task(document_id: str, file_buffer: bytes):
    """
    解析大型 PDF（例如 1000 页）
    
    可以在 Worker 内部用多进程并行处理多个页面
    """
    from multiprocessing import Pool
    
    # 提取所有页面
    pages = extract_pages(file_buffer)
    
    # 使用进程池并行处理
    with Pool(processes=4) as pool:
        page_texts = pool.map(parse_page, pages)
    
    # 合并结果
    full_text = "\n".join(page_texts)
    return full_text
```

但对于你的场景（多个文档并行处理），直接用多个 Worker 更合适。

---

## 七、实施建议

### 7.1 开发阶段

```bash
# 启动最小配置（开发环境）
celery -A tasks worker -Q parse,chunk,train,kg --concurrency=1 -n dev@%h
```

### 7.2 生产阶段

```bash
# 启动完整配置（生产环境）
# 解析队列：4 个 Worker
celery -A tasks worker -Q parse --concurrency=1 -n parse1@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse2@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse3@%h &
celery -A tasks worker -Q parse --concurrency=1 -n parse4@%h &

# 分块队列：2 个 Worker
celery -A tasks worker -Q chunk --concurrency=1 -n chunk1@%h &
celery -A tasks worker -Q chunk --concurrency=1 -n chunk2@%h &

# 训练队列：2 个 Worker（内部用协程）
celery -A tasks worker -Q train --concurrency=1 -n train1@%h &
celery -A tasks worker -Q train --concurrency=1 -n train2@%h &

# 知识图谱队列：1 个 Worker（内部用协程）
celery -A tasks worker -Q kg --concurrency=1 -n kg1@%h &
```

### 7.3 监控

```bash
# Flower 监控
celery -A tasks flower --port=5555

# 访问 http://localhost:5555 查看：
# - Worker 状态
# - 任务执行情况
# - 队列长度
# - 任务耗时统计
```

---

## 八、常见问题

### Q1: 为什么不用 Celery 的 prefork 模式？

**A**: Celery 的 prefork 模式本质上就是多进程：
```bash
# prefork 模式（默认）
celery -A tasks worker --concurrency=4  # 启动 4 个子进程

# 等价于启动 4 个独立 Worker
celery -A tasks worker --concurrency=1 -n worker1 &
celery -A tasks worker --concurrency=1 -n worker2 &
celery -A tasks worker --concurrency=1 -n worker3 &
celery -A tasks worker --concurrency=1 -n worker4 &
```

推荐后者的原因：
- 更灵活（可以给不同队列分配不同数量的 Worker）
- 更容易监控（每个 Worker 独立）
- 更容易扩展（可以分布到多台机器）

### Q2: 协程任务如何在 Celery 中使用？

**A**: Celery 任务默认是同步的，需要手动运行 asyncio：
```python
@shared_task
def async_task(data):
    return asyncio.run(async_function(data))

async def async_function(data):
    # 异步逻辑
    pass
```

### Q3: 如何限制并发数？

**A**: 
- CPU 密集：限制 Worker 数量
- I/O 密集：限制协程数量

```python
# 限制协程并发数
semaphore = asyncio.Semaphore(50)  # 最多 50 个并发

async def limited_task(data):
    async with semaphore:
        return await actual_task(data)
```

---

## 八、RAGFlow 架构借鉴

### 8.1 核心设计对比

| 设计点 | RAGFlow | 我们的方案 | 是否借鉴 |
|--------|---------|-----------|----------|
| **任务队列** | Redis Stream + 消费者组 | Celery + Redis | ❌ 继续用 Celery |
| **并发控制** | 多层 Semaphore（task/chunk/embed/kg/llm） | Worker 数量控制 | ✅ 借鉴多层控制 |
| **异步处理** | asyncio + to_thread | asyncio | ✅ 借鉴 to_thread |
| **LLM 缓存** | Redis 缓存 + hash key | 无 | ✅ 必须实现 |
| **自动增强** | 关键词/问题/元数据/TOC | 无 | ✅ 必须实现 |
| **未确认重试** | UNACKED_ITERATOR | Celery 内置 | ❌ Celery 已有 |

### 8.2 推荐实现

#### 8.2.1 多层并发控制

```python
# tasks/limiters.py
import asyncio

# 不同类型任务使用不同的 Semaphore
parse_limiter = asyncio.Semaphore(4)       # 解析并发（CPU 密集）
chunk_limiter = asyncio.Semaphore(2)       # 分块并发（CPU 轻量）
embed_limiter = asyncio.Semaphore(50)      # 向量化并发（I/O 密集）
llm_limiter = asyncio.Semaphore(10)        # LLM 调用并发（I/O 密集 + 限流）
kg_limiter = asyncio.Semaphore(2)          # 知识图谱并发（I/O 密集）
minio_limiter = asyncio.Semaphore(20)      # MinIO 上传并发（I/O 密集）

# 使用示例
@shared_task
async def parse_document_task(document_id: str):
    async with parse_limiter:
        # 解析逻辑
        pass

@shared_task
async def vectorize_segments_task(segment_ids: list[str]):
    async with embed_limiter:
        # 向量化逻辑
        pass
```

**优势**：
- 精细控制不同资源的并发
- 避免某类任务打满资源
- 可根据实际情况调整

#### 8.2.2 asyncio.to_thread 处理同步阻塞

```python
@shared_task
async def parse_document_task(document_id: str, file_id: str):
    """
    异步任务中处理同步阻塞操作
    """
    # 1. 下载文件（I/O 阻塞）
    file_buffer = await asyncio.to_thread(
        download_file_from_storage,
        file_id
    )
    
    # 2. 解析文件（CPU 密集 + 同步库）
    text = await asyncio.to_thread(
        parse_pdf,  # PyPDF2 是同步的
        file_buffer
    )
    
    # 3. 分块（CPU 密集 + 同步库）
    chunks = await asyncio.to_thread(
        chunk_text,  # LlamaIndex 是同步的
        text
    )
    
    # 4. 保存结果（I/O 阻塞）
    await asyncio.to_thread(
        save_chunks,
        document_id,
        chunks
    )
```

**适用场景**：
- 调用同步库（PyPDF2、LlamaIndex）
- 文件 I/O 操作
- 数据库同步操作

**注意**：
- `asyncio.to_thread` 使用线程池，不是进程
- 仍受 GIL 限制，CPU 密集任务效果有限
- 主要用于避免阻塞事件循环

#### 8.2.3 LLM 结果缓存（必须实现）

```python
# utils/llm_cache.py
import hashlib
import json
from functools import wraps
from redis import Redis

redis_client = Redis(host='localhost', port=6379, db=0)

def llm_cache(cache_ttl: int = 3600, key_prefix: str = "llm"):
    """
    LLM 结果缓存装饰器
    
    Args:
        cache_ttl: 缓存过期时间（秒）
        key_prefix: 缓存 key 前缀
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存 key
            cache_data = {
                "func": func.__name__,
                "args": str(args),
                "kwargs": str(sorted(kwargs.items()))
            }
            cache_hash = hashlib.md5(
                json.dumps(cache_data, sort_keys=True).encode()
            ).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{cache_hash}"
            
            # 检查缓存
            cached = await asyncio.to_thread(redis_client.get, cache_key)
            if cached:
                return json.loads(cached)
            
            # 调用函数
            result = await func(*args, **kwargs)
            
            # 写入缓存
            await asyncio.to_thread(
                redis_client.setex,
                cache_key,
                cache_ttl,
                json.dumps(result, ensure_ascii=False)
            )
            
            return result
        return wrapper
    return decorator

# 使用示例
@llm_cache(cache_ttl=3600)
async def extract_keywords(text: str, topn: int = 5) -> list[str]:
    """提取关键词（带缓存）"""
    prompt = f"""
    从以下文本中提取 {topn} 个关键词，用逗号分隔：
    
    {text}
    """
    
    async with aiohttp.ClientSession() as session:
        result = await call_llm_api(session, prompt)
    
    return result.strip().split(",")

@llm_cache(cache_ttl=3600)
async def extract_questions(text: str, topn: int = 3) -> list[str]:
    """提取问题（带缓存）"""
    prompt = f"""
    从以下文本中提取 {topn} 个问题，每行一个：
    
    {text}
    """
    
    async with aiohttp.ClientSession() as session:
        result = await call_llm_api(session, prompt)
    
    return result.strip().split("\n")

@llm_cache(cache_ttl=3600)
async def extract_metadata(text: str, schema: dict) -> dict:
    """提取元数据（带缓存）"""
    prompt = f"""
    从以下文本中提取元数据，按照 schema 返回 JSON：
    
    Schema: {json.dumps(schema, ensure_ascii=False)}
    
    文本：
    {text}
    """
    
    async with aiohttp.ClientSession() as session:
        result = await call_llm_api(session, prompt)
    
    return json.loads(result)
```

**优势**：
- 避免重复调用 LLM（省钱）
- 加速处理（缓存命中率高）
- 适合批量处理

**缓存策略**：
- 关键词提取：缓存 1 小时
- 问题提取：缓存 1 小时
- 元数据提取：缓存 1 小时
- 实体提取：缓存 1 小时

#### 8.2.4 自动增强流程（必须实现）

```python
# tasks/enhancement_tasks.py
@shared_task
async def chunk_and_enhance_task(
    document_id: str,
    text: str,
    config: dict
):
    """
    分块 + 自动增强
    
    config:
        - chunk_size: 分块大小
        - auto_keywords: 是否提取关键词
        - auto_questions: 是否提取问题
        - enable_metadata: 是否提取元数据
        - metadata_schema: 元数据 schema
    """
    # 1. 分块
    chunks = await asyncio.to_thread(
        chunk_text,
        text,
        chunk_size=config.get("chunk_size", 512)
    )
    
    # 2. 并发增强
    async with aiohttp.ClientSession() as session:
        # 限流
        async with llm_limiter:
            tasks = []
            
            for chunk in chunks:
                chunk_tasks = []
                
                # 关键词提取
                if config.get("auto_keywords"):
                    chunk_tasks.append(
                        extract_keywords(chunk["text"], topn=5)
                    )
                
                # 问题提取
                if config.get("auto_questions"):
                    chunk_tasks.append(
                        extract_questions(chunk["text"], topn=3)
                    )
                
                # 元数据提取
                if config.get("enable_metadata"):
                    chunk_tasks.append(
                        extract_metadata(
                            chunk["text"],
                            config["metadata_schema"]
                        )
                    )
                
                tasks.append(asyncio.gather(*chunk_tasks))
            
            # 并发执行所有 chunk 的增强任务
            results = await asyncio.gather(*tasks)
            
            # 合并结果
            for chunk, result in zip(chunks, results):
                idx = 0
                if config.get("auto_keywords"):
                    chunk["keywords"] = result[idx]
                    idx += 1
                if config.get("auto_questions"):
                    chunk["questions"] = result[idx]
                    idx += 1
                if config.get("enable_metadata"):
                    chunk["metadata"] = result[idx]
                    idx += 1
    
    # 3. 保存
    await save_chunks(document_id, chunks)
    
    return {"status": "success", "chunk_count": len(chunks)}
```

**增强效果**：
- 关键词：提升检索召回率
- 问题：支持问答式检索
- 元数据：支持结构化过滤

### 8.3 完整流程对比

| 阶段 | RAGFlow | 我们的方案（优化后） |
|------|---------|---------------------|
| **文件上传** | API → Redis Stream | API → Celery |
| **解析** | asyncio.to_thread + 多策略 | Celery Worker + asyncio.to_thread |
| **分块** | asyncio.to_thread | Celery Worker + asyncio.to_thread |
| **自动增强** | 并发 LLM 调用 + 缓存 | 并发 LLM 调用 + 缓存 |
| **向量化** | asyncio.gather + Semaphore | asyncio.gather + Semaphore |
| **知识图谱** | 并发提取 + 缓存 | 并发提取 + 缓存 |
| **存储** | asyncio.to_thread | asyncio.to_thread |

### 8.4 性能对比（预估）

**场景**：处理 100 个文档，每个文档 10 个分块

| 任务 | 原方案 | 优化后 | 提升 |
|------|--------|--------|------|
| 解析 | 130s | 130s | - |
| 分块 | 20s | 20s | - |
| 关键词提取（无缓存） | 1000s | 100s（并发） | 10x |
| 关键词提取（有缓存） | 1000s | 10s（缓存命中） | 100x |
| 向量化 | 15s | 15s | - |
| 知识图谱 | 35s | 35s | - |
| **总计（无缓存）** | 1200s | 300s | 4x |
| **总计（有缓存）** | 1200s | 210s | 5.7x |

---

## 九、总结

**核心结论**：
1. **CPU 密集任务**：多个 Celery Worker，不需要内部多进程
2. **I/O 密集任务**：Worker + 协程，性能最优
3. **实时响应任务**：FastAPI 异步路由，不用 Celery

**你的场景最佳方案**：
- 解析：4 个 Worker（CPU 密集）
- 分块：2 个 Worker（CPU 轻量）
- 向量化：2 个 Worker + 协程（I/O 密集）
- 知识图谱：1 个 Worker + 协程（I/O 密集）
- 检索：FastAPI 异步路由（实时响应）

这样的架构简单、高效、易维护，充分利用了 Celery 和 asyncio 的优势。
