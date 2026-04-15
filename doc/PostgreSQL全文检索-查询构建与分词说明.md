# PostgreSQL 全文检索（FTS）查询构建与「分词」说明

本文说明本项目中 **构建 PostgreSQL FTS 查询** 的完整链路：哪些步骤在 **应用层（Python）** 用规则完成，哪些步骤由 **PostgreSQL** 在 **`simple` 文本搜索配置** 下内部处理。可与源码对照阅读：

- `genesis-ai-platform/rag/lexical/analysis/` — 后端无关的全文检索分析器、索引文本构建、PG 查询载荷适配
- `genesis-ai-platform/rag/lexical/text_utils.py` — 兼容旧调用入口，内部转发到 `rag.lexical.analysis`
- `genesis-ai-platform/rag/retrieval/backends/pg_fts.py` — `plainto_tsquery` / `to_tsquery` 与评分 SQL

---

## 1. 两个层次：不要混成「一种分词」

| 层次 | 位置 | 作用 |
|------|------|------|
| **A. 应用层（Python）** | `rag.lexical.analysis` / `text_utils.build_pg_fts_query_payload` 等 | 对查询做 **规范化**，结合 **知识库检索词表、同义词、专业术语、停用词**，抽取 **高置信词项** 与低权重 **CJK fallback bigram**，拼成传给 PG 的 **字符串**（`strict_query_text`、`loose_query_text`、`fallback_query_text`、结构化补分用的 `phrase_pattern` 等）。 |
| **B. 数据库层（PostgreSQL）** | `plainto_tsquery('simple', …)`、`to_tsquery('simple', …)` | 对 Python **已传入的字符串** 按 **`simple` 配置** 做 **词法解析**，生成 `tsquery`，再与列上的 `tsvector`（`@@`）匹配；同时参与 **`ts_rank_cd` 打分**。 |

结论：

- **中文/混合查询里「先拆成哪些片段」**：主要由 **Python 应用层分析器** 完成。当前默认实现已切换为 **`JiebaLexicalAnalyzer`**，规则型 analyzer 作为基础能力与 fallback 思路保留，用于弥补 **`simple` 对中文极弱** 的问题。
- **这些字符串如何变成可执行的 `tsquery`、如何与索引向量匹配**：由 **PostgreSQL 内部**（`simple`）完成。

两者是 **串联关系**：Python 产出「检索串」→ PG 再解析并执行 FTS。

---

## 2. 应用层（Python）：具体做了什么

实现入口：`build_pg_fts_query_payload(query, priority_terms=…, priority_phrases=…, synonym_terms=…, glossary_terms=…, retrieval_stopwords=…)`。

### 2.1 规范化：`normalize_lexical_text`

- 去空白、部分标点归一、转小写等，得到 **`normalized`**（整句级别的规范化文本）。

### 2.2 ASCII 词：`extract_ascii_terms`

- 用正则 `[A-Za-z0-9][A-Za-z0-9_./:-]*` 等规则抓取 **英文、数字、混合术语**；
- 长度等过滤后得到 **`ascii_terms`**。
- 这是 **明确的代码规则分词**，不依赖 PostgreSQL。

### 2.3 中文相关：`JiebaLexicalAnalyzer` / `fallback_ngram`

- 当前默认中文分词器是 **应用层 `jieba`**，依赖通过 `uv add jieba` 引入；
- `priority_terms`、`glossary_terms`、`synonym_terms` 会作为自定义词加入当前 tokenizer，使 **知识库检索词表、专业术语、查询命中的同义词扩展** 能影响分词；`priority_phrases` 只用于完整短语补分，不注册成进程级 jieba 自定义词，避免用户整句压住 `剪映` 这类子词；`synonym_terms` 只在查询命中同义词后用于 query expansion，不默认写入索引侧词典；
- analyzer 从 `genesis-ai-platform/rag/lexical/resources/stopwords/` 加载两份默认停用词：`doc_stopwords.txt` 用于索引侧，`query_stopwords.txt` 用于查询侧；知识库配置里的 `retrieval_stopwords` 会在对应默认词表基础上追加；
- 查询侧与索引侧停用词可以不同：索引侧应更保守，避免长期索引资产误删有效词；查询侧可以更积极地过滤问句引导词、语气词、低价值泛词，但是否过滤 `如何`、`怎么` 这类词以 `query_stopwords.txt` 和知识库配置为准；
- 查询诊断会输出 `stopword_hits`，表示本次查询文本中实际命中的停用词；`ignored_terms` 表示真实被过滤的词项，不再把因为单字停用词重叠而被压制的 fallback bigram（例如 `何使`、`的素`）当作停用词命中展示；`stopwords` 只保留词表预览，`stopword_count` 表示本次合并后的停用词总数；
- analyzer 会限制动态自定义词数量、单个词长度、查询/索引 token 数量和 fallback 数量，避免大词表或长文本导致 `tsquery` / `tsvector` 膨胀；
- `extract_cjk_fallback_terms` 仍保留为低权重兜底：对 CJK 连续块做二字滑动窗口（bigram），但查询侧当 jieba 已经产出足够词项时，默认不再把 `何上`、`传剪`、`映空` 这类噪声放进主查询；
- 索引侧仍可保留部分 fallback_ngram 以增强召回，查询侧通过低权重 `fallback_query_text` 控制其影响。

示例：

```text
原问句：如何上传剪映空间
当前 jieba 主词项：如何 / 上传 / 剪映 / 空间
配置专业词后：如何 / 上传 / 剪映空间 / 空间 / 剪映
查询侧 fallback_query_text：默认为空（jieba 词项足够时不再平权 OR bigram）
```

### 2.4 `strict_terms` / `loose_terms` 与查询串

- **`strict_terms`**：在 **`normalized` 整句** 基础上，再并入 **jieba 高置信词项、优先词、查询命中的同义词扩展词、专业术语、ASCII 词** 等（**不包含** 低置信 `fallback_ngram`）。  
  - 拼成 **`strict_query_text`**：多个 term 用 **空格** 连接，供 **`plainto_tsquery('simple', strict_query_text)`** 使用。

- **`loose_terms`**：高置信词项集合，主要包括 **整句短语、jieba 词项、优先短语、优先词、查询命中的同义词扩展词、专业术语、ASCII 词** 等，去重后拼成 **`loose_query_text`**，供 **`to_tsquery('simple', loose_query_text)`** 使用。
  - 若某个高置信词项本身含空格，payload 适配器会把它转换成 `to_tsquery` 可消费的操作数，例如 `open ai 上传` 会进入 `loose_query_text` 为 `open & ai & 上传`，避免 `to_tsquery` 语法错误。

- **`fallback_terms`**：低置信 CJK fallback bigram，例如 `上传`、`剪映`、`空间`，也可能包含 `传剪`、`映空` 这类跨词边界噪声。  
  - 拼成 **`fallback_query_text`**，单独供 **`to_tsquery('simple', fallback_query_text)`** 使用。  
  - 它仍可参与召回，但评分权重低于 strict / loose；当前查询侧若 jieba 已产出足够词项，`fallback_query_text` 通常为空，避免把 bigram 噪声与业务词平权 OR。

### 2.5 优先词与短语（查询分析产物）

- `priority_terms` / `priority_phrases` / `synonym_terms` / `glossary_terms` 经规范化后进入应用层分析器，成为 **高置信词项**，同时生成若干 **`%…%` 形式的 ILIKE 模式**。这些模式只用于 SQL 里的 **结构化补分**，不再作为 `WHERE` 召回分支，避免把 PG FTS 退化成 `%xxx%` 扫描。

### 2.6 索引侧扩展：`build_lexical_index_text`

- 对 **索引入库文本** 同样做规范化，并把 **jieba 词项、知识库命中的检索词条/专业术语、ASCII 词、低权重 fallback_ngram** 拼进一段更适合 **`to_tsvector('simple', …)`** 的字符串，使 **索引与查询在策略上对齐**（具体入库逻辑见 lexical 流水线，此处不展开）。同义词不默认写入索引侧词典，而是在查询命中后做限量扩展。

### 2.7 调试输出：`build_pg_fts_query_payload` 的 `debug` 字段

- 包含 `ascii_terms`、`cjk_terms`、`strict_terms`、`loose_terms`、`fallback_terms`、`ignored_terms` 等，便于 API/前端展示「应用层拆出了什么」；**与** `query_analysis` 里的 **`priority_lexical_*`（查询分析优先词）** 含义不同，后者是另一条业务链路。

---

## 3. 数据库层（PostgreSQL）：具体做了什么

实现见：`PGFTSSearchBackend.search`（`pg_fts.py`）。

### 3.1 三个 FTS 分支（均使用 `simple`）

从载荷中取出 **`strict_query_text`**、**`loose_query_text`** 等，在 SQL 内：

```text
strict_query    = plainto_tsquery('simple', strict_query_text)    -- 若为空则为 NULL
loose_query     = to_tsquery('simple', loose_query_text)          -- 若为空则为 NULL
fallback_query  = to_tsquery('simple', fallback_query_text)       -- 若为空则为 NULL
```

- **`plainto_tsquery`**：将输入当作 **类自然语言字符串** 解析为 `tsquery`。
- **`to_tsquery`**：输入需符合 **tsquery 语法**（此处 `loose_query_text` / `fallback_query_text` 已用 `|` 连接多个操作数）；**每个操作数** 仍由 **`simple` 配置** 做词法处理。

### 3.2 打分（`ts_rank_cd`）权重（实现以代码为准）

在现有实现中，**向量相关部分**大致为：

- **`strict_query` 命中**：`ts_rank_cd(..., strict_query) * 0.72`
- **`loose_query` 命中**：`ts_rank_cd(..., loose_query) * 0.28`
- **`fallback_query` 命中**：`ts_rank_cd(..., fallback_query) * 0.08`

即 **strict、loose、fallback 同时参与加权**；fallback 主要承载 CJK bigram 兜底召回，权重明显低于 strict / loose（若某一侧为 NULL 则该侧为 0）。

SQL 内部还会叠加完整短语、优先词、优先短语等结构化补分，因此 PG FTS 的 **raw score** 是一个加和分，可能超过 1，例如 `1.50`。这个 raw score 只用于 SQL 内部排序和诊断，不直接作为前端“全文相关性”展示。

返回到检索融合层前，当前会做单调归一化：

```text
lexical_score = raw_score / (raw_score + 0.8)
```

例如：

```text
raw 0.17 -> lexical_score 0.1753
raw 1.50 -> lexical_score 0.6522
raw 3.00 -> lexical_score 0.7895
```

这样既避免前端展示超过 1 的“相关性分”，又保留 raw score 的强弱顺序。诊断字段中保留 `lexical_raw_score`、`lexical_score` 与 `lexical_score_normalization`，方便后续调权。

### 3.3 命中条件（WHERE）

文档是否进入结果集，当前只看 FTS 条件，满足其一即可：

- `lex.search_vector @@ strict_query`
- **或** `lex.search_vector @@ loose_query`
- **或** `lex.search_vector @@ fallback_query`

因此：**strict、loose、fallback 不是二选一**；**CJK fallback bigram 主要进入 `fallback_query_text`**，通过 **低权重 fallback 分支** 与索引交互；**loose 分支**更侧重业务词表、同义词、专业术语和优先短语等高置信词项。各类 **ILIKE**（整句 `phrase_pattern`、优先词/短语模式等）只对已经被 FTS 召回的候选做补分，不参与召回。

### 3.4 PostgreSQL「内部分词」指什么

此处 **不是** 指中文分词插件，而是：

- 使用配置名 **`simple`** 的 **默认词法规则**：如何识别 token、哪些字符属于「词」等；
- **`plainto_tsquery` / `to_tsquery`** 对 **已给定字符串** 的解析结果。

对 **拉丁字母与数字**，`simple` 行为相对直观；对 **中文**，单靠 PG 往往不够，因此项目在 **Python 层先用 jieba 与词表拆出高置信词项**，必要时再补低权重 fallback_ngram，然后交给 **`to_tsquery('simple', …)`**。

---

## 4. 索引侧与查询侧的对齐关系

### 4.1 与典型全文引擎（如 Qdrant / Milvus）的类比

在 Qdrant / Milvus 等系统中，常见约定是：**索引写入与检索查询使用同一套分词/分析器（analyzer）**，使「入库词项」与「查询词项」处于同一语义空间。

在本项目中，对应关系可概括为：

| 环节 | 角色 |
|------|------|
| **应用层（Python）** | 索引入库与查询构造 **共用** `rag.lexical.analysis` 中的 **`JiebaLexicalAnalyzer`、`normalize_lexical_text`、ASCII 抽取、fallback_ngram 抽取**（与查询载荷同源）。 |
| **PostgreSQL** | 索引列与查询 **共用** 文本搜索配置 **`simple`**：`to_tsvector('simple', …)` 建向量，`plainto_tsquery` / `to_tsquery('simple', …)` 建查询。 |

因此：**并非「只有查询做预处理、入库仍是原始正文直接进 PG」**；入库前已对文本做 **与查询侧同源的启发式扩展**，再交由 `simple` 生成 `tsvector`。

### 4.2 索引入库路径（实现摘要）

全文索引写入见 `genesis-ai-platform/rag/lexical/service.py`（`SearchUnitLexicalIndexService`）：

1. 从检索投影取源文（如 `lexical_text` / `search_text`）。
2. **`normalized_text = build_lexical_index_text(lexical_source_text)`** — 与查询侧使用同一模块内的索引专用拼接函数。
3. 持久化 **`search_text`**，并计算 **`search_vector = to_tsvector('simple', search_text)`**。

即：**存储进 `pg_chunk_search_unit_lexical_indexes` 的已是扩展后的检索串**，不是未经 `build_lexical_index_text` 的裸文本。

### 4.3 「同源规则」与「不同拼接形态」

- **同源**：索引使用的 `build_lexical_index_text` 与查询使用的 `build_pg_fts_query_payload`，底层依赖 **同一套** `JiebaLexicalAnalyzer`、规范化、ASCII 抽取与 fallback_ngram 逻辑，目标是在不引入 PG 中文插件的前提下，使 **文档侧与查询侧词项空间尽量一致**。

- **非同形**：二者 **输出字符串的拼接方式不同** — 索引侧将 **规范化整句 + jieba 词项 + 词表命中项 + fallback_ngram** 以 **空格** 拼成 **单段** 供 `to_tsvector`；查询侧则构造 **strict / loose / fallback** 等 **多条 `tsquery` 串**（含 `|` OR 等）。随后均由 **`simple`** 解析，**不是**「索引与查询逐字节同一条字符串」，而是 **同一族规则下的不同组装**。

结论表述建议：**索引前已按与查询同源的 Python 规则扩展文本；再在 PG 内用与查询相同的 `simple` 配置生成向量/查询。** 若需与 Qdrant / Milvus「完全同一 analyzer 输出形态」严格对齐，当前实现属于 **策略一致、字符串形态不完全相同** 的折中。

---

## 5. 引入外部中文分词器时的原则性说明

若引入 **jieba、HanLP** 等应用层分词器，或 **PostgreSQL 中文分词扩展**（如 zhparser 等），需保证 **索引构建与检索查询使用同一套分词结果或同一 PG `text search configuration`**，否则将出现词表不对齐、召回异常等问题。常见做法包括：

1. **应用层分词**：文档入库前与用户查询均经 **同一分词器** → 将 token 序列用约定分隔符拼为字符串 → 再调用 **`to_tsvector` / `plainto_tsquery` / `to_tsquery`**（配置可为 `simple` 或与新词典配套的自定义配置，以实际扩展文档为准）。
2. **仅在 PostgreSQL 内分词**：索引列使用 **`to_tsvector('某中文配置', 原文)`**，查询使用 **`plainto_tsquery('同一配置', 查询串)`**，由扩展保证索引与查询对称。
3. **外接专用搜索引擎**：索引与查询均在该引擎内完成，与本地的 `pg_chunk_search_unit_lexical_indexes` 解耦，需单独约定数据同步与一致性。

**存储前是否「先分词」**：在方案（1）（2）中，**在生成 `tsvector` 之前** 要么在应用层完成分词并拼串，要么在 PG 内由配置完成分词；**本质上索引向量始终对应「已按选定规则处理后的文本」**，与引入分词器之前「先经 Python 扩展再 `to_tsvector`」的结构一致，只是分词器从启发式规则换为专业中文分词。

### 5.1 PG 内扩展 vs 应用层分词器

这里的“PG 内扩展”和“应用层分词器”不是同一个东西，核心差异是 **分词发生在哪里、词项结果绑定哪个检索后端**。

#### 5.1.1 PG 内扩展是什么

PG 内扩展是把中文分词能力安装进 PostgreSQL 的全文检索体系里，例如：

- `zhparser`
- `pg_jieba`

典型使用方式是：

```sql
-- 示例：创建中文分词配置，实际语法以所选扩展文档为准
CREATE EXTENSION zhparser;
CREATE TEXT SEARCH CONFIGURATION zhcfg (PARSER = zhparser);

-- 索引侧：由 PG 扩展把原文解析成 tsvector
UPDATE pg_chunk_search_unit_lexical_indexes
SET search_vector = to_tsvector('zhcfg', search_text);

-- 查询侧：由同一配置把用户查询解析成 tsquery
SELECT plainto_tsquery('zhcfg', '如何上传剪映空间');
```

也就是说，PG 内扩展的核心是：**索引侧和查询侧都在 PostgreSQL 内部用同一个中文 text search configuration 生成 `tsvector / tsquery`**。

优点：

- 对长期使用 PostgreSQL FTS 的系统很顺，SQL 侧调用自然。
- 分词、索引、查询都在 PG 内完成，索引与查询容易保持同一配置。
- 不需要应用层自己拼 token 串。

缺点：

- 绑定 PostgreSQL 的 `tsvector / tsquery` 体系。
- 未来迁移到 Qdrant / Milvus 时，PG 扩展本身不能复用，需要重新配置目标引擎 analyzer 或重新做应用层分词。
- 需要额外数据库扩展安装、镜像构建、运维和版本兼容治理。

#### 5.1.2 应用层分词器是什么

应用层分词器是在 Python 服务里先完成中文分词，再把 token 结果交给检索后端。例如：

```text
原文：如何上传剪映空间
应用层分词：如何 / 上传 / 剪映空间
索引文本：如何 上传 剪映空间
查询文本：如何 上传 剪映空间
```

可选工具包括：

- `jieba`
- `HanLP`
- `pkuseg`

典型使用方式是：

```python
# 伪代码：索引侧和查询侧都走同一个 analyzer
tokens = analyzer.tokenize("如何上传剪映空间", kb_terms=["剪映空间"], stopwords=["如何"])
search_text = " ".join(tokens)

# PG 阶段可以继续交给 simple
to_tsvector("simple", search_text)

# 未来 Qdrant / Milvus 阶段也可以复用 tokens 或 query expansion 结果
```

优点：

- 跨 PG / Qdrant / Milvus 更容易复用。
- 更容易接入 **知识库级检索词表、专业术语、同义词、停用词、业务短语优先级**。
- 分词与 query analysis、rerank、QA/table scope 等 RAG 逻辑更容易统一调试。

缺点：

- 应用层要自己维护 analyzer、用户词典、停用词、索引重建规则。
- 如果后端原生 analyzer 很强，应用层全量预分词可能与后端 analyzer 重叠，需要明确取舍。

#### 5.1.3 是否配合使用

一般不建议 **PG 内扩展 + 应用层分词器** 同时承担主分词职责。两边都分词会带来：

- 索引侧和查询侧词项不一致。
- 调试链路变复杂，难以判断召回来自哪一层。
- 词典、停用词需要两处维护。

更推荐二选一：

| 场景 | 推荐 |
|------|------|
| 长期坚持 PostgreSQL FTS 作为主全文检索 | 可评估 PG 内 `zhparser / pg_jieba` |
| 未来会迁移 Qdrant / Milvus | 优先应用层 analyzer，后续接目标引擎原生 analyzer |
| 希望 Qdrant / Milvus 之间行为更一致 | 应用层 analyzer 更有优势 |
| 希望完全利用 Milvus 原生中文 analyzer / BM25 | 应用层保留 query expansion 与词表治理，底层分词交给 Milvus analyzer |

本项目结论：**不建议当前引入 PG 内中文分词扩展；中文分词质量提升优先落在统一应用层 analyzer，当前默认实现已接入 jieba。**

#### 5.1.4 性能判断：应用层分词是否会慢于 PG 内扩展

应用层分词不会天然导致查询性能明显不如 PG 内扩展。真正影响查询性能的通常是：

- 分词后 token 数量是否失控
- `tsquery` 的 OR 项是否过多
- `tsvector` 规模与 GIN 索引质量
- 候选集大小
- `ts_rank_cd` 打分和后续 rerank 成本

用户查询通常较短，例如：

```text
如何上传剪映空间
```

应用层 `jieba` 对这类 query 的分词开销通常很小；PG 内扩展同样也需要分词，只是分词发生在数据库内部：

```sql
plainto_tsquery('zhcfg', '如何上传剪映空间')
```

因此，差异不是“PG 内扩展不分词、应用层分词要额外分词”，而是 **分词发生在 DB 内还是 Python 服务内**。

只要索引侧仍然写入 `search_vector`，并且使用 GIN 索引：

```sql
to_tsvector('simple', '如何 上传 剪映空间')
```

查询侧仍然可以走 PG FTS 索引：

```sql
search_vector @@ to_tsquery('simple', '上传 | 剪映空间')
```

也就是说，应用层分词后并不是退化成全表 `ILIKE` 扫描；它仍然可以走 `tsvector + GIN`。

如果应用层分词做得好，例如：

```text
如何 / 上传 / 剪映空间
```

相比当前 fallback bigram：

```text
如何 / 何上 / 上传 / 传剪 / 剪映 / 映空 / 空间
```

反而会减少无效 OR 项和候选噪声，查询性能与排序质量都可能更好。

需要避免的是 **query expansion 失控**，例如把用户问题、业务词、同义词、专业术语、bigram 全量无限 OR。实现时应遵循：

- query token 数量设上限
- 同义词 expansion 只在 query 命中后触发，并设上限；同义词组不默认进入索引侧词典
- 专业术语只加入实际命中的项
- fallback bigram 低权重、限量、可被停用词过滤
- 索引侧与查询侧必须使用同一 analyzer 规则
- 标签、文件夹路径等 metadata 信号不应写入每个 chunk 的正文分词词典；它们更适合走硬过滤、软加权或单独的文档级 metadata 检索投影

本项目判断：

```text
查询性能：应用层 jieba + PG simple GIN 索引，不会天然不如 PG 内扩展
查询质量：应用层 jieba 明显优于当前 bigram 补丁
迁移能力：应用层 jieba 明显优于 PG 内扩展
工程复杂度：jieba 中等，PG 内扩展中等偏高且绑定 PG
```

因此，当前更推荐：

```text
应用层 JiebaLexicalAnalyzer
  - 控制 token 数量
  - 词表 / 术语进入 jieba 自定义词
  - 停用词过滤
  - 同义词限量 expansion
  - fallback bigram 低权重、限量
  - 索引侧和查询侧统一
  - PG 阶段继续走 tsvector + GIN
```

### 5.2 中文分词器选型结论

本项目当前明确会从 PostgreSQL 本地全文检索逐步迁移到 **Qdrant / Milvus**，并且未来 Qdrant / Milvus 会同时承担 **向量检索与全文检索**。因此，中文分词能力的最佳落点不是 PostgreSQL 内扩展，而是：

```text
当前：PG simple FTS + 应用层 JiebaLexicalAnalyzer 降噪
中期：按效果评估 HanLP 等更强中文 NLP 能力
最终：Qdrant / Milvus 原生全文检索能力 + 应用层词表 / 同义词 / query expansion
```

推荐优先级：

| 方案 | 推荐度 | 说明 |
|------|--------|------|
| **应用层 jieba** | **当前已采用** | 纯 Python、接入成本低、支持用户词典，适合把 **知识库检索词表、专业术语、产品名、缩写** 加入分词；未来迁移 Qdrant / Milvus 时仍可复用应用层 analyzer 与 query expansion 逻辑。 |
| **应用层 HanLP** | 第二阶段评估 | 分词、NER 等能力更强，但模型与部署更重；适合后续需要更强实体识别、术语抽取、自动词表治理时再引入。 |
| **应用层 pkuseg** | 特定领域评估 | 支持领域模型与用户词典，可在医疗、金融等固定领域做效果对比；不作为第一版默认实现。 |
| **PG 内 zhparser / pg_jieba** | 当前不推荐 | 能改善 PG FTS 中文分词，但绑定 PostgreSQL 的 `tsvector / tsquery` 体系，迁移 Qdrant / Milvus 时不可直接复用。若长期坚持 PG FTS 才值得投入。 |

当前实现方向：

```text
get_default_lexical_analyzer()
  -> JiebaLexicalAnalyzer

JiebaLexicalAnalyzer:
  - jieba 精确模式 + 搜索模式组合
  - 知识库检索词表 -> jieba 自定义词，并统一作为优先短语处理
  - 专业术语 glossary -> jieba 自定义词（索引侧只加入当前文本实际命中的词项）
  - 默认停用词 + 知识库停用词 -> analyzer 过滤
  - 同义词 -> 命中 query 后限量 expansion，不默认写入索引词典
  - 标签 / 文件夹路径 / 文档级标签 -> 过滤或 metadata 投影，不进入每个 chunk 的正文分词
  - fallback bigram -> 仅作为低权重兜底，不进入主召回词项
```

例如：

```text
原问句：如何上传剪映空间
旧规则 fallback：如何 / 何上 / 上传 / 传剪 / 剪映 / 映空 / 空间
当前 jieba 默认：如何 / 上传 / 剪映 / 空间
加入“剪映空间”词典后：如何 / 上传 / 剪映空间 / 空间 / 剪映
```

结论：**当前已经优先在统一应用层 analyzer 中接入 jieba，而不是引入 PG 专属中文分词扩展。** 这样既能改善当前 PG FTS 阶段的中文检索效果，又不会把未来 Qdrant / Milvus 迁移成本绑定到 PostgreSQL 扩展上。

---

## 6. 与「查询分析」里优先词的区别（避免混淆）

| 概念 | 来源 | 用途 |
|------|------|------|
| **`priority_lexical_*` / `ignored_lexical_*`（query_analysis）** | 查询分析管线 | 业务上的优先词、忽略词、同义词等，影响 **`lexical_query` 字符串** 及优先词/短语补分。 |
| **`ascii_terms` / `cjk_terms` / `strict_terms` / `loose_terms` / `fallback_terms`（lexical_query_debug）** | `build_pg_fts_query_payload` 的 `debug` | **PG FTS 载荷** 在应用层的 **拆分结果**，直接对应 **`strict_query_text` / `loose_query_text` / `fallback_query_text`** 的构造材料。 |

二者可能重叠（例如分析结果会改 **`lexical_query`**），但 **语义与代码路径不同**，调试时应分开看。

---

## 7. 设计取向（为何是「Python 规则 + simple」）

- **第一阶段目标**：**不依赖** PostgreSQL 中文分词扩展，使用 **统一应用层 JiebaLexicalAnalyzer + 高置信词项 + 低权重 fallback bigram + FTS 候选上的短语补分** 提升中文检索。
- 当前不建议引入 **zhparser、pg_jieba** 等 PG 内扩展；中文分词器已优先落在统一应用层 analyzer 中，并把知识库检索词表、专业术语、停用词接进去（详见上文 **§5.1 / §5.2**）。

---

## 8. 小结表

| 问题 | 答案 |
|------|------|
| 分词是人工写代码还是 PG 自己做？ | **两者都有**：**拆分查询串、拼 strict/loose/fallback 与短语补分模式** 主要在 **Python**；**生成 `tsquery` 并与 `tsvector` 匹配** 在 **PostgreSQL（`simple`）**。 |
| CJK 连续片段和 loose 词项哪个「被用到」？ | **高置信词项进入 `loose_terms`**；**CJK fallback bigram 进入 `fallback_terms`**，再进入 **`fallback_query_text → to_tsquery`**，以低权重兜底召回。 |
| strict、loose、fallback 哪个用？ | **三个都用**：**命中**上 **OR**；**打分**上 strict / loose 权重更高，fallback 权重更低，用于降低 bigram 噪声影响。 |
| 入库前有没有做与查询同源的文本处理？ | **有**：索引用 **`build_lexical_index_text`**，与查询共用 **`text_utils`** 内规范化与词项抽取；再 **`to_tsvector('simple', …)`**。 |
| 索引串与查询串是否完全相同？ | **否**：**规则同源、拼接形态不同**（见 **§4.3**）。 |

---

## 9. 代码参考位置

| 文件 | 内容 |
|------|------|
| `genesis-ai-platform/rag/lexical/analysis/` | `LexicalAnalyzer`、`JiebaLexicalAnalyzer`、`RuleBasedLexicalAnalyzer`、`build_pg_fts_query_payload`、`build_lexical_index_text` 等统一分析器与适配器 |
| `genesis-ai-platform/rag/lexical/text_utils.py` | 兼容旧调用入口：`normalize_lexical_text`、`extract_ascii_terms`、`extract_cjk_terms`（兼容名，当前语义为 fallback_ngram）、`build_pg_fts_query_payload`、`build_lexical_index_text` |
| `genesis-ai-platform/rag/lexical/service.py` | 索引入库：`build_lexical_index_text` → `to_tsvector('simple', search_text)` |
| `genesis-ai-platform/rag/retrieval/backends/pg_fts.py` | `plainto_tsquery` / `to_tsquery`、权重、FTS `WHERE` 条件与候选补分 |
| `genesis-ai-platform/rag/retrieval/hybrid.py` | 调用 `build_pg_fts_query_payload`，并将 `lexical_query_debug` 写入 `debug` |
