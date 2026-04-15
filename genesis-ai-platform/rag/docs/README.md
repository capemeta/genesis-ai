# RAG 模块架构

基于 FastGPT 和 RAGFlow 架构设计的模块化 RAG 系统。

## 架构概览

```
文件上传 → 解析 → 分块 → 增强 → 向量化 → 检索 → 生成
         ↓      ↓     ↓      ↓        ↓       ↓
      ingestion/  embeddings/  retrieval/  generation/
```

## 目录结构

```
rag/
├── __init__.py              # RAG 模块入口
├── schema.py                # 通用数据结构
├── enums.py                 # 枚举定义
├── model_configs.json       # 模型配置
│
├── ingestion/               # 数据接入层
│   ├── parsers/             # 文档解析器
│   ├── chunkers/            # 文档分块器
│   ├── enhancers/           # 内容增强器
│   └── tasks/               # Celery 任务
│
├── embeddings/              # 向量化层（待实现）
│   └── providers/           # 向量化提供商
│
├── retrieval/               # 检索层（待实现）
│
├── generation/              # 生成层（待实现）
│
├── pipeline/                # 流程编排（待实现）
│
├── utils/                   # 工具函数
│   ├── llm_cache.py         # LLM 缓存
│   ├── model_utils.py       # 模型工具
│   ├── token_utils.py       # Token 计数
│   └── limiters.py          # 并发控制
│
└── docs/                    # 文档
    ├── README.md            # 本文件
    ├── ARCHITECTURE.md      # 架构设计
    ├── BEST_PRACTICES.md    # 最佳实践
    └── DEPLOYMENT.md        # 部署指南
```

## 核心特性

### 1. 数据接入层 (ingestion/)

- **多策略解析**：支持 Basic/MinerU/Vision/OCR/Docling/TCADP 六种解析策略
- **多策略分块**：支持固定长度/语义/Markdown/递归分块
- **自动增强**：关键词/问题/摘要/元数据自动提取
- **异步任务**：Celery 任务队列，完全异步

### 2. 向量化层 (embeddings/)

待实现，将支持：
- OpenAI Embeddings
- HuggingFace Embeddings
- 本地模型
- 自定义向量化提供商

### 3. 检索层 (retrieval/)

待实现，将支持：
- 向量检索
- 全文检索
- 混合检索（RRF 融合）
- 重排序

### 4. 生成层 (generation/)

待实现，将支持：
- Prompt 构建
- 上下文构建
- LLM 调用
- 流式输出

## 使用示例

### 1. 解析文档

```python
from rag import ParserFactory
from rag.enums import ParseStrategy

# 自动选择解析策略
strategy = ParserFactory.auto_select_strategy(file_buffer, ".pdf")

# 创建解析器
parser = ParserFactory.create_parser(strategy)

# 解析文档
text, metadata = await parser.parse(file_buffer, ".pdf")
```

### 2. 分块文档

```python
from rag import ChunkerFactory
from rag.enums import ChunkStrategy

# 创建分块器
chunker = ChunkerFactory.create_chunker(
    ChunkStrategy.FIXED_SIZE,
    chunk_size=512,
    chunk_overlap=50
)

# 分块
chunks = await chunker.chunk(text, metadata)
```

### 3. 增强分块

```python
from rag import EnhancerFactory

# 创建增强器
enhancers = EnhancerFactory.create_enhancers({
    "keyword": {"topn": 5},
    "question": {"topn": 3},
    "summary": {"max_length": 100}
})

# 增强分块
for chunk in chunks:
    for enhancer in enhancers:
        chunk = await enhancer.enhance(chunk)
```

### 4. 完整流程（Celery 任务）

```python
from rag.ingestion.tasks.parse_task import parse_document_task

# 触发解析任务
task = parse_document_task.delay(
    document_id="doc_123",
    file_id="file_456",
    file_extension=".pdf",
    parse_strategy="auto"
)

# 后续任务自动触发：
# parse → chunk → enhance → train
```

## 扩展指南

### 添加自定义解析器

```python
from rag.ingestion.parsers import BaseParser, ParserFactory
from rag.enums import ParseStrategy

class CustomParser(BaseParser):
    async def parse(self, file_buffer, file_extension):
        # 实现解析逻辑
        return text, metadata
    
    def supports(self, file_extension):
        return file_extension == ".custom"

# 注册解析器
ParserFactory.register_parser(ParseStrategy.CUSTOM, CustomParser)
```

### 添加自定义分块器

```python
from rag.ingestion.chunkers import BaseChunker, ChunkerFactory
from rag.enums import ChunkStrategy

class CustomChunker(BaseChunker):
    async def chunk(self, text, metadata):
        # 实现分块逻辑
        return chunks

# 注册分块器
ChunkerFactory.register_chunker(ChunkStrategy.CUSTOM, CustomChunker)
```

### 添加自定义增强器

```python
from rag.ingestion.enhancers import BaseEnhancer, EnhancerFactory

class CustomEnhancer(BaseEnhancer):
    async def enhance(self, chunk):
        # 实现增强逻辑
        return chunk

# 注册增强器
EnhancerFactory.register_enhancer("custom", CustomEnhancer)
```

## 迁移说明

**重要**：目录结构已重构，import 路径已更新：

### 旧路径 → 新路径

```python
# 解析器
from rag.ingestion.parsers import ParserFactory
# ↓
from rag.ingestion.parsers import ParserFactory

# 分块器
from rag.ingestion.chunkers import ChunkerFactory
# ↓
from rag.ingestion.chunkers import ChunkerFactory

# 增强器
from rag.ingestion.enhancers import EnhancerFactory
# ↓
from rag.ingestion.enhancers import EnhancerFactory

# 任务
from rag.ingestion.tasks.parse_task import parse_document_task
# ↓
from rag.ingestion.tasks.parse_task import parse_document_task

# 工具函数
from rag.ingestion.utils.token_utils import count_tokens
# ↓
from rag.utils.token_utils import count_tokens

# 枚举
from rag.ingestion.enums import ParseStrategy
# ↓
from rag.enums import ParseStrategy
```

### 兼容性

所有功能保持完全一致，只是目录结构更清晰：
- `rag.ingestion` → `rag.ingestion`（数据接入）
- `rag.ingestion.utils` → `rag.utils`（通用工具）
- `rag.ingestion.enums` → `rag.enums`（枚举定义）

## 相关文档

- [架构设计](./ARCHITECTURE.md) - 详细的架构设计文档
- [最佳实践](./BEST_PRACTICES.md) - 开发最佳实践
- [部署指南](./DEPLOYMENT.md) - 生产环境部署
- [PostgreSQL FTS 查询与分词](../../../doc/PostgreSQL全文检索-查询构建与分词说明.md) - Python 规则与 `simple` 内部分词的分工、strict/loose/ILIKE（见 [RAG 内索引](./LEXICAL_FTS_TOKENIZATION.md)）
- [分块流程研究](../../../doc/分块流程研究.md) - 分块策略研究
- [FastGPT 调用链](../../../doc/fastgpt/FastGPT-分块与解析调用链.md) - FastGPT 参考
- [RAGFlow 分块流程](../../../doc/ragflow/分块解析流程文档.md) - RAGFlow 参考
