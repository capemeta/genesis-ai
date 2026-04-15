# 分块流程架构设计文档

## 一、架构概览

基于 FastGPT 和 RAGFlow 的设计理念，构建了一个模块化、可扩展的文档处理流程架构。

### 核心设计原则

1. **模块化**：解析器、分块器、增强器完全解耦
2. **可扩展**：通过工厂模式轻松添加新策略
3. **异步优先**：使用 asyncio + Celery 实现异步处理
4. **并发控制**：多层 Semaphore 精细化控制资源
5. **性能优化**：LLM 缓存、批量处理、asyncio.to_thread

## 二、完整流程

```
┌─────────────┐
│  文件上传    │
└──────┬──────┘
       │
       ↓
┌─────────────────────────────────────────┐
│  解析队列 (parse_document_task)          │
│  - 自动选择策略 (auto/basic/mineru/...)  │
│  - 多进程解析 (避免 GIL)                 │
│  - 保存原始文本                          │
└──────┬──────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────┐
│  分块队列 (chunk_document_task)          │
│  - 选择分块策略                          │
│  - 执行分块                              │
│  - 保存分块结果                          │
└──────┬──────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────┐
│  增强队列 (enhance_chunks_task)          │
│  - 关键词提取 (LLM + 缓存)               │
│  - 问题提取 (LLM + 缓存)                 │
│  - 摘要生成 (LLM + 缓存)                 │
└──────┬──────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────┐
│  训练队列 (train_document_task)          │
│  - 向量化 (批量 API 调用)                │
│  - 知识图谱构建 (可选)                   │
└──────┬──────────────────────────────────┘
       │
       ↓
┌─────────────┐
│  完成        │
└─────────────┘
```

## 三、模块设计

### 3.1 解析器模块 (parsers/)

**职责**：将各种格式的文件转换为纯文本

**支持策略**：
- `BasicParser`: 基础解析（PyPDF2/python-docx/openpyxl）
- `MinerUParser`: 高质量 PDF 解析（保留结构）
- `VisionParser`: 视觉大模型解析（复杂布局）
- `OCRParser`: OCR 解析（扫描件）

**关键特性**：
- 自动策略选择（`auto_select_strategy`）
- 使用 `asyncio.to_thread` 避免阻塞
- 工厂模式支持扩展

**示例**：
```python
# 自动选择策略
strategy = ParserFactory.auto_select_strategy(file_buffer, ".pdf")

# 创建解析器
parser = ParserFactory.create_parser(strategy)

# 解析
text, metadata = await parser.parse(file_buffer, ".pdf")
```

### 3.2 分块器模块 (chunkers/)

**职责**：将长文本切分为合适大小的分块

**支持策略**：
- `FixedSizeChunker`: 固定长度分块（简单快速）
- `SemanticChunker`: 语义分块（保持语义完整性）
- `MarkdownChunker`: Markdown 结构分块（保留层级）
- `RecursiveChunker`: 递归分块（灵活适应）

**关键特性**：
- 支持重叠（chunk_overlap）
- 使用 `asyncio.to_thread` 避免阻塞
- 工厂模式支持扩展

**示例**：
```python
# 创建分块器
chunker = ChunkerFactory.create_chunker(
    ChunkStrategy.FIXED_SIZE,
    chunk_size=512,
    chunk_overlap=50
)

# 分块
chunks = await chunker.chunk(text, metadata)
```

### 3.3 增强器模块 (enhancers/)

**职责**：为分块添加额外信息，提升检索效果

**支持功能**：
- `KeywordEnhancer`: 关键词提取（提升召回率）
- `QuestionEnhancer`: 问题提取（支持问答式检索）
- `SummaryEnhancer`: 摘要生成（快速预览）

**关键特性**：
- LLM 缓存装饰器（节省成本 80%+）
- 并发执行（llm_limiter 控制）
- 工厂模式支持扩展

**示例**：
```python
# 批量创建增强器
enhancers = EnhancerFactory.create_enhancers({
    "keyword": {"topn": 5},
    "question": {"topn": 3},
    "summary": {"max_length": 100}
})

# 增强分块
for enhancer in enhancers:
    chunk = await enhancer.enhance(chunk)
```

### 3.4 任务模块 (tasks/)

**职责**：Celery 异步任务，编排完整流程

**任务列表**：
- `parse_document_task`: 解析任务
- `chunk_document_task`: 分块任务
- `enhance_chunks_task`: 增强任务
- `train_document_task`: 训练任务（向量化等）

**关键特性**：
- 自动任务链（parse → chunk → enhance → train）
- 并发控制（多层 Semaphore）
- 错误重试（max_retries=3）

**示例**：
```python
# 触发解析任务（后续任务自动触发）
task = parse_document_task.delay(
    document_id="doc_123",
    file_id="file_456",
    file_extension=".pdf",
    parse_strategy="auto"
)
```

## 四、并发控制策略

### 4.1 多层 Semaphore

不同类型任务使用不同的并发限制：

```python
# limiters.py
parse_limiter = asyncio.Semaphore(4)    # 解析（CPU 密集）
chunk_limiter = asyncio.Semaphore(2)    # 分块（CPU 轻量）
embed_limiter = asyncio.Semaphore(50)   # 向量化（I/O 密集）
llm_limiter = asyncio.Semaphore(10)     # LLM 调用（I/O + 限流）
kg_limiter = asyncio.Semaphore(2)       # 知识图谱（I/O 密集）
minio_limiter = asyncio.Semaphore(20)   # MinIO 上传（I/O 密集）
```

### 4.2 使用方式

```python
async def _parse_document_async(...):
    async with parse_limiter:  # 并发控制
        # 解析逻辑
        pass
```

## 五、性能优化

### 5.1 LLM 缓存

**问题**：重复调用 LLM 成本高、速度慢

**解决方案**：Redis 缓存装饰器

```python
from rag.utils import llm_cache

@llm_cache(cache_ttl=3600)
async def extract_keywords(text: str, topn: int = 5):
    prompt = f"从以下文本中提取 {topn} 个关键词：\n{text}"
    result = await call_llm_api(prompt)
    return result.strip().split(",")
```

**效果**：
- 成本降低 80%+
- 速度提升 10-100x（缓存命中时）

### 5.2 asyncio.to_thread

**问题**：同步库（PyPDF2、LlamaIndex）阻塞事件循环

**解决方案**：在线程池中执行同步操作

```python
# 使用 asyncio.to_thread 避免阻塞
text = await asyncio.to_thread(
    parse_pdf,  # 同步函数
    file_buffer
)
```

### 5.3 批量处理

**问题**：逐个调用 API 效率低

**解决方案**：批量调用

```python
# 批量向量化
texts = [chunk["text"] for chunk in chunks]
embeddings = await batch_embed(texts, batch_size=100)
```

**效果**：
- API 调用次数减少 100x
- 吞吐量提升 2-3x

## 六、状态管理

### 6.1 文档状态

```python
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"           # 已上传
    PARSING = "parsing"             # 解析中
    PARSE_FAILED = "parse_failed"   # 解析失败
    CHUNKING = "chunking"           # 分块中
    CHUNK_FAILED = "chunk_failed"   # 分块失败
    TRAINING = "training"           # 训练中
    TRAIN_FAILED = "train_failed"   # 训练失败
    BUILDING_KG = "building_kg"     # 构建知识图谱中
    KG_FAILED = "kg_failed"         # 知识图谱失败
    COMPLETED = "completed"         # 完成
```

### 6.2 状态流转

```
UPLOADED → PARSING → CHUNKING → TRAINING → COMPLETED
    ↓          ↓          ↓           ↓
PARSE_FAILED CHUNK_FAILED TRAIN_FAILED
```

## 七、扩展指南

### 7.1 添加自定义解析器

```python
from rag.ingestion.parsers import BaseParser, ParserFactory

class CustomParser(BaseParser):
    async def parse(self, file_buffer, file_extension):
        # 实现解析逻辑
        return text, metadata
    
    def supports(self, file_extension):
        return file_extension == ".custom"

# 注册
ParserFactory.register_parser("custom", CustomParser)
```

### 7.2 添加自定义分块器

```python
from rag.ingestion.chunkers import BaseChunker, ChunkerFactory

class CustomChunker(BaseChunker):
    async def chunk(self, text, metadata):
        # 实现分块逻辑
        return chunks

# 注册
ChunkerFactory.register_chunker("custom", CustomChunker)
```

### 7.3 添加自定义增强器

```python
from rag.ingestion.enhancers import BaseEnhancer, EnhancerFactory

class CustomEnhancer(BaseEnhancer):
    async def enhance(self, chunk):
        # 实现增强逻辑
        return chunk

# 注册
EnhancerFactory.register_enhancer("custom", CustomEnhancer)
```

## 八、TODO 清单

### 高优先级（必须实现）

- [ ] **LLM 缓存**：集成 Redis 缓存（节省成本 80%+）
- [ ] **具体解析器**：实现 PyPDF2/MinerU/OCR 解析逻辑
- [ ] **LlamaIndex 集成**：集成 LlamaIndex 分块器
- [ ] **批量向量化**：实现批量 embedding API 调用
- [ ] **数据库集成**：实现分块保存和加载

### 中优先级（推荐实现）

- [ ] **知识图谱**：实现实体提取和关系提取
- [ ] **混合检索**：实现向量 + 图谱混合检索
- [ ] **任务监控**：集成 Celery Flower
- [ ] **错误处理**：完善错误重试和告警

### 低优先级（可选实现）

- [ ] **RAPTOR**：层次聚类摘要
- [ ] **TOC 生成**：自动生成文档目录
- [ ] **单元测试**：添加完整测试覆盖
- [ ] **性能测试**：压力测试和性能调优

## 九、技术栈

- **语言**: Python 3.12.x
- **异步**: asyncio + Celery
- **任务队列**: Redis + Celery
- **解析**: PyPDF2, python-docx, MinerU, PaddleOCR
- **分块**: LlamaIndex, LangChain
- **LLM**: LiteLLM
- **向量**: pgvector
- **图数据库**: Neo4j（可选）

## 十、参考文档

- [分块流程研究](../../../doc/分块流程研究.md) - 完整设计文档
- [FastGPT 调用链](../../../doc/fastgpt/FastGPT-分块与解析调用链.md)
- [RAGFlow 分块流程](../../../doc/ragflow/分块解析流程文档.md)
- [Python GIL 与并发](../../../doc/Python-GIL-与-并发策略说明.md)
- [RAG 并发策略](../../../doc/RAG场景并发策略分析.md)
