# 当前检索实现梳理与评估

## 文档目的

本文梳理当前 `genesis-ai-platform` 的检索实现，回答下面几个问题：

1. 当前检索链路到底是怎么跑的
2. 离线索引和在线查询分别做了什么
3. QA / 表格 / 通用文档三类知识库在检索上有什么差异
4. 现状是否需要优化
5. 当前实现里有哪些漏洞、隐患、非最佳实践点

---

## 相关核心文件

- `rag/retrieval/hybrid.py`
- `rag/retrieval/types.py`
- `rag/retrieval/service.py`
- `rag/retrieval/router.py`
- `rag/retrieval/backends/pg_vector.py`
- `rag/retrieval/backends/pg_fts.py`
- `rag/query_analysis/service.py`
- `rag/query_analysis/types.py`
- `rag/search_units.py`
- `rag/vectorization/service.py`
- `rag/lexical/service.py`
- `rag/ingestion/tasks/chunk_task.py`
- `rag/ingestion/tasks/train_task.py`

---

## 一、先说总体结论

当前实现不是“纯向量检索”，而是一个**分层的混合检索**：

1. 先把 `chunk` 派生为 `search_unit`
2. 再分别建立：
   - 向量索引 `pg_chunk_search_unit_vectors`
   - 全文索引 `pg_chunk_search_unit_lexical_indexes`
3. 查询时先做：
   - 查询分析
   - 硬过滤解析
   - 向量召回
   - 全文召回
4. 再把两路结果按 `content_group_id / chunk_id` 融合
5. 最后补文档信息、父块上下文、摘要片段，并做一个启发式 rerank

它的方向是对的，已经不是“简单 embedding 搜索”了。

但是当前实现仍然存在几个明显问题：

1. 有些配置字段已经暴露，但实际上没有真正生效
2. 一些逻辑是“启发式占位”，还不算最终最佳实践
3. 部分召回分支是 Python 侧临时实现，规模大了会出性能问题
4. 中文全文检索方案偏弱
5. 若知识库继续变大，过滤、摘要召回、查询 embedding 这几块都需要继续优化

结论：**需要优化，而且是值得尽快优化的。**

---

## 二、离线索引构建链路

### 2.1 chunk 不是最终检索单元

当前系统不是直接拿 `chunks` 去检索，而是先把 `chunk` 转成 `chunk_search_units`。

原因是一个 `chunk` 可以派生出多个不同语义用途的检索投影，例如：

- `default`
- `summary`
- `question`
- `answer`
- `keyword`
- `row`
- `row_group`
- `row_fragment`
- `page_body`
- `doc_summary`

这部分逻辑在 `rag/search_units.py`。

### 2.2 search_unit 的生成逻辑

`build_search_units_for_chunks()` 的核心思路：

1. 普通知识库：
   - 每个 chunk 生成一个默认检索投影
   - 再根据增强结果追加 `summary / question / keyword` 等投影
2. QA 知识库：
   - 重点生成 `question` 和可选 `answer`
   - `question` 侧会把纯问题文本单独放进 `vector_text`
3. 表格知识库：
   - 行级检索投影是 `row`
   - 同一业务行还会派生 `row_group`
   - `row_group` 当前默认只走全文，不走向量
4. 文档级摘要：
   - `kb_doc.summary` 会派生 `doc_summary` 投影
   - 当前默认 `should_vectorize = False`

### 2.3 离线训练阶段做什么

在 `rag/ingestion/tasks/train_task.py` 里，增强后会执行：

1. 删除旧 search_unit / 旧 lexical index / 旧 vector index
2. 基于最新 chunk 重建 `chunk_search_units`
3. 基于 search_unit 构建全文索引
4. 基于 search_unit 构建向量索引

### 2.4 全文索引如何构建

`rag/lexical/service.py`：

1. 读取 search_unit
2. 优先取 `metadata.lexical_text`，否则取 `search_text`
3. 生成标准化全文文本
4. 写入 `pg_chunk_search_unit_lexical_indexes`
5. `search_vector` 使用 `to_tsvector('simple', :search_text)`

### 2.5 向量索引如何构建

`rag/vectorization/service.py`：

1. 读取 search_unit
2. 若 `should_vectorize = False`，跳过
3. 优先取 `metadata.vector_text`，否则取 `search_text`
4. 调用模型平台做 embedding
5. 写入 `pg_chunk_search_unit_vectors`

这说明当前系统的真实检索入口是 `search_unit`，不是直接对 `chunk.content` 做统一检索。

---

## 三、在线查询链路

在线查询主入口在 `rag/retrieval/hybrid.py` 的 `HybridRetrievalService.search()`。

完整顺序如下。

### 3.1 参数归一化

先把前端或聊天侧传来的配置统一转成 `HybridSearchConfig`：

- `top_k`
- `vector_top_k`
- `keyword_top_k`
- `rerank_top_n`
- `vector_weight`
- `final_score_threshold`
- `enable_doc_summary_retrieval`
- `enable_parent_context`
- `group_by_content_group`
- `use_knowledge_graph`

当前默认值体现了一个思路：

1. 先宽召回
2. 再融合
3. 再裁剪到最终 `top_k`

### 3.2 合并知识库级 query_analysis 配置

系统会把 `kb.retrieval_config.query_analysis` 合进当前请求配置，主要包括：

- 同义词改写
- 自动过滤模式
- metadata 字段定义
- retrieval lexicon
- stopwords
- LLM 候选过滤参数

同时会从 `persistent_context` 里补 `enable_doc_summary_retrieval`。

### 3.3 查询分析

`QueryAnalysisService.analyze()` 目前会做这些事：

1. 标准化原始 query
2. 可选同义词改写
3. 套用知识库级检索词表
4. 可选规则型自动过滤
5. 可选 LLM 候选过滤提取
6. 查询术语解释（glossary）
7. 生成 lexical query
8. 生成 priority lexical hints

最后得到：

- `raw_query`
- `rewritten_query`
- `lexical_query`
- `retrieval_filters`
- `priority_lexical_terms`
- `priority_lexical_phrases`

这里的设计是合理的：**向量 query 和全文 query 已经不是同一个原始字符串，而是 query analysis 处理后的两个版本。**

### 3.4 过滤条件前置解析

系统把过滤分成两层：

1. 文档层硬过滤
2. 检索层软召回

`_resolve_candidate_filters()` 的核心逻辑：

1. 先按：
   - kb_doc_ids
   - document_ids
   - folder_ids
   - tag_ids
   - latest_days
   - document_metadata
2. 在文档层得到候选 `kb_doc_ids / document_ids`
3. 如果是表格或 QA，再进一步在主事实表里把过滤解析成 `content_group_ids`

也就是说，表格和 QA 没有完全依赖冗余 metadata 过滤，而是回到主事实表再做一遍过滤映射。

这点是当前实现里一个比较好的设计。

### 3.5 查询向量化

`_embed_query()` 会：

1. 解析当前知识库实际生效的 embedding 模型
2. 调模型平台生成 query embedding
3. 校验向量维度是否与 pgvector 表兼容

注意：这里是**每次查询都实时做 embedding**。

### 3.6 scope 选择

系统不是把所有 search_unit 一锅端召回，而是按知识库类型限制 scope。

#### 通用文档默认向量 scope

- `default`
- `summary`
- `question`
- `answer`
- `row`
- `page_body`

#### 通用文档默认全文 scope

- `default`
- `summary`
- `doc_summary`
- `question`
- `keyword`
- `answer`
- `row`
- `row_fragment`
- `page_body`

#### QA 知识库

- 向量：`question` 或 `question + answer`
- 全文：`question`，可选 `answer`，可选 `keyword`

#### 表格知识库

- 向量：只查 `row`
- 全文：查 `row / row_group / row_fragment / keyword`

### 3.7 向量召回

`PGVectorSearchBackend.search()`：

1. 只在 `pg_chunk_search_unit_vectors` 里查
2. 关联 `chunk_search_units / chunks / knowledge_base_documents`
3. 默认只查：
   - `display_enabled = true`
   - `is_leaf = true`
4. 按向量距离排序

这说明当前向量召回默认是**叶子块召回**，父块主要用于后续补上下文。

### 3.8 全文召回

`PGFTSSearchBackend.search()`：

1. 构造 strict / loose tsquery
2. 再叠加 `ILIKE` 的优先短语 / 优先词命中加分
3. 同样默认只查叶子块
4. 按 score 倒排

当前全文分数不是单一 `ts_rank_cd`，而是：

1. strict tsquery 分
2. loose tsquery 分
3. priority phrase 命中分
4. priority term 命中分
5. phrase pattern 命中分

因此它实际上是“PostgreSQL FTS + 词面命中加权”的混合全文召回。

### 3.9 doc_summary 辅助召回

如果开启 `enable_doc_summary_retrieval`，且当前 lexical 结果里没有 `doc_summary`，会执行 `_search_doc_summary_hits()`：

1. 直接扫 `KnowledgeBaseDocument.summary`
2. 用 Python 计算 bigram overlap + term overlap
3. 生成伪 `SearchHit`

但需要注意：`doc_summary` 并不是完全没进入正式索引。

当前真实情况是：

1. `kb_doc.summary` 已经会先派生为 `doc_summary` search_unit
2. 该 search_unit 会进入正式 lexical index
3. 这里的 `_search_doc_summary_hits()` 是在“正式 lexical 没命中 doc_summary”时的在线补召回

所以它是一个**正式全文索引之上的补充召回分支**，而不是唯一实现。

### 3.10 双路结果融合

`_fuse_hits()` 是当前排序核心。

处理逻辑：

1. 向量命中和全文命中统一走 `_apply()`
2. 先做单路阈值过滤：
   - 向量低于 `vector_similarity_threshold` 的丢掉
   - 全文低于 `keyword_relevance_threshold` 的丢掉
3. 再按 group_key 聚合：
   - `doc_summary` 用 `doc_summary:{kb_doc_id}`
   - 否则默认用 `content_group_id`
   - 如果没有 `content_group_id`，用 `chunk_id`
4. 对每个 group 记录：
   - `vector_score`
   - `keyword_score`
   - `matched_scopes`
   - `matched_backend_types`
5. 再算融合分

融合分公式大体是：

1. `weighted = vector_score * vector_weight + keyword_score * lexical_weight`
2. 再乘 `scope_weight`
3. 再加：
   - coverage bonus
   - backend bonus
   - repeated hit bonus
   - query intent bonus
   - metadata bonus

其中比较特别的点：

#### QA lexical 命中会再校正

`_normalize_qa_lexical_hit_score()` 会对 `question` scope 做结构化归一化，提升“完全同问”的 lexical 分数。

#### 意图加权

`_compute_query_intent_bonus()` 会基于 query 特征，对 QA / 表格场景给额外加分。

#### metadata 加权

`_compute_metadata_bonus()` 会看：

- QA 的 category / tags / question_text
- 表格的 sheet_name / field_names / filter_fields / table_context_text

如果 query 词面和这些元数据重合，会再加一点分。

### 3.11 结果补全

`_hydrate_results()` 负责把 `GroupedHit` 补成前端真正可用的结果项。

它会补：

1. `Chunk`
2. 父 chunk
3. `KnowledgeBaseDocument`
4. `Document`
5. tags

然后生成：

- `title`
- `snippet`
- `score`
- `vector_score`
- `keyword_score`
- `matched_scopes`
- `matched_backends`
- `page_numbers`
- `parent_chunk_id`
- `content_group_id`

### 3.12 snippet 生成

`_build_result_snippet()` 逻辑：

1. 表格结果会加工作表、定位、字段、表格上下文
2. QA 答案碎片会尽量补“问题 + 完整答案”
3. 普通层级 chunk 在开启 `enable_parent_context` 时会补父块摘要

这说明当前系统结果展示不是“原样返回命中 chunk”，而是做过上下文包装。

### 3.13 最后 rerank

`_apply_rerank_if_needed()` 当前不是调用真实 rerank 模型，而是：

1. 取 snippet 或 question_text
2. 算 query 与该文本的 bigram overlap
3. 用启发式方式把融合分和 overlap 再混一次

所以它是**启发式 rerank 占位实现**，不是模型级 rerank。

---

## 四、不同知识库类型的检索差异

## 4.1 通用文档

特点：

- 默认 `default + summary + keyword + question` 等多投影混合
- 向量和全文都参与
- 层级 chunk 命中后通过父块补上下文

## 4.2 QA 知识库

特点：

- `question` 是核心检索投影
- 可选把 `answer` 也纳入向量和全文
- 完全同问有额外 lexical 结构化加分
- category / tags 也能参与过滤和 metadata bonus

## 4.3 表格知识库

特点：

- 向量主查 `row`
- 全文补查 `row_group / row_fragment / keyword`
- 过滤优先回主事实表 `KBTableRow`
- snippet 和 metadata 都会显式补“字段、维度、指标、工作表、行定位”

当前表格检索是这套实现里最有业务定制感的一部分。

---

## 五、当前实现的优点

## 5.1 已经形成了“离线索引 + 在线融合”的完整链路

这比“直接查 chunk 表 + 临时 embedding”成熟很多。

## 5.2 search_unit 设计是对的

一个 chunk 派生多种检索投影，是当前架构里最关键的正确方向。

## 5.3 过滤层和召回层做了拆层

表格 / QA 都尽量通过主事实表解析过滤条件，而不是完全依赖冗余 metadata。

## 5.4 已经开始做类型化检索

QA、表格、网页、通用文档并不是完全同一套策略。

## 5.5 结果 hydration 做得比普通 RAG 更完整

父块上下文、工作表上下文、QA 完整答案上下文，这些都说明当前系统不只是“召回几个向量最近块”。

---

## 六、明确需要优化的点

下面按优先级分。

## P0：功能/设计漏洞

### 6.1 `group_by_content_group` 配置当前基本未生效

问题：

- 配置里有 `group_by_content_group`
- 但 `_fuse_hits()` 实际始终按 `content_group_id or chunk_id` 聚合
- 没有看到按该配置切换聚合策略的逻辑

影响：

- 前端以为自己能控制“按业务组聚合 / 按 chunk 聚合”
- 实际当前不能

结论：

- 这是一个明确的实现漏洞

### 6.2 `use_knowledge_graph` 当前只是预留，不是真正参与检索

问题：

- 配置里支持 `use_knowledge_graph`
- 但当前只在 `extension_branch_context` 里做保留说明
- 没有真正执行 KG 召回或融合

影响：

- 参数语义和真实行为不一致

结论：

- 如果前端已经暴露该参数，应视为“名义支持，实际未实现”

### 6.3 `rerank_model` 不是模型 rerank

问题：

- 从名字看像真正的 rerank model
- 实际只是启发式 bigram overlap 重排

影响：

- 会误导调用方
- 配置语义不真实

结论：

- 要么改名为 `heuristic_rerank`
- 要么接入真实 rerank

---

## P1：性能与规模风险

### 6.4 `doc_summary` 当前是“正式全文索引 + Python 补召回”的混合实现

问题：

`doc_summary` 并不是完全未索引化。

当前真实情况是：

1. `doc_summary` 已进入正式 lexical index
2. 同时又保留了 `_search_doc_summary_hits()` 作为 Python 补召回

问题主要在于：

- 正式索引与补召回逻辑并存，行为复杂
- Python 补召回会在大数据量下变慢
- 补召回评分体系和主检索链路不完全一致

影响：

- 行为解释成本更高
- 数据量大了补召回会慢
- 调参和排障会更复杂

建议：

- 保留正式 lexical index
- 重新评估 Python 补召回是否还有必要长期存在
- 如果保留，也应明确它只是兜底分支

### 6.5 查询 embedding 没有查询级缓存

问题：

- 每次检索都会实时做 query embedding
- 当前看到的是文档向量构建有缓存，query embedding 没有类似缓存层

影响：

- 高频问句重复成本高
- 对模型平台压力大

建议：

- 增加短 TTL 的 query embedding cache

### 6.6 候选过滤解析可能在大库下变重

问题：

- `_resolve_candidate_filters()` 先查文档层候选，再查表格/QA 主事实表
- 是正确方向，但在大数据量下仍可能产生较大 SQL 和较长候选列表

建议：

- 后续需要评估分页候选、半连接、物化过滤视图或更专门的检索候选表

---

## P1：检索质量风险

### 6.7 中文全文检索当前不是最佳实践

问题：

- 当前 lexical index 使用 `to_tsvector('simple', ...)`
- PostgreSQL `simple` 对中文分词能力非常弱
- 系统主要靠预处理文本、ILIKE 模式和辅助分数补救

影响：

- 中文长句、近义表达、短语边界处理不够稳
- FTS 召回质量上限受限

建议：

- 若继续走 PostgreSQL，考虑接入更适合中文的分词方案
- 或引入专门全文检索后端

### 6.8 阈值与权重高度启发式

问题：

- `vector_weight`
- `scope_weight`
- `coverage_bonus`
- `backend_bonus`
- `query_intent_bonus`
- `metadata_bonus`

这些值目前多数是经验值，不是离线评估校准结果。

影响：

- 在不同知识库类型、不同规模、不同领域下，可能会漂

建议：

- 做离线评测集
- 按知识库类型独立调参

### 6.9 `row_group` 只走全文，不走向量

问题：

- 当前表格 `row_group` 被设计成全文辅路
- 这会降低“整行上下文语义”在向量侧的参与度

是否一定是问题：

- 不一定
- 这是为了避免噪声扩大

建议：

- 先保留现状
- 但应该通过评测确认：表格问答是否需要为 `row_group` 引入低权重向量召回

---

## P2：架构一致性问题

### 6.10 检索后端选择目前只支持全局配置

问题：

- `get_active_search_backends()` 只读全局 `.env`
- 还不支持知识库级覆盖

影响：

- 无法按知识库类型或租户差异化选择后端

建议：

- 后续抽成租户级 / KB 级检索后端策略

### 6.11 过滤口径有“双通道”维护成本

问题：

- 一部分过滤在主事实表
- 一部分还保留在 search_unit metadata

虽然当前这样做是为了兼顾性能和灵活性，但长期看有口径漂移风险。

建议：

- 明确哪些字段只允许主事实表过滤
- 哪些字段允许 metadata 过滤
- 避免两套语义长期并存

---

## 七、哪些地方已经不是最佳实践

严格说，下面这些点已经不能算最佳实践：

1. `rerank_model` 名不副实
2. `use_knowledge_graph` 名义存在但未真正参与检索
3. `group_by_content_group` 配置暴露但未实际控制分组
4. `doc_summary` 当前是“正式索引 + Python 补召回”双路径并存，复杂度偏高
5. 中文全文检索使用 PostgreSQL `simple`
6. 大量排序参数依赖手工启发式，缺少评测闭环

---

## 八、我对当前方案的判断

我的判断是：

### 8.1 当前方案能用，而且整体方向是对的

不是推倒重来的状态。

### 8.2 当前方案还不能算“最终版检索架构”

尤其是：

- 配置语义一致性
- 中文全文质量
- 文档摘要召回
- rerank 真实性
- 大库性能

这几块还差一步。

### 8.3 现在最值得优先做的不是大重构，而是收口

建议优先顺序：

1. 修复名义参数与真实行为不一致的问题
2. 收口 `doc_summary` 的双路径实现
3. 给 query embedding 增加缓存
4. 为中文全文检索补更合适的方案
5. 基于评测集重调融合权重

---

## 九、建议的下一步改造优先级

## 第一优先级

1. 修复 `group_by_content_group` 未生效
2. 明确 `use_knowledge_graph` 当前是否对外暴露
3. 明确 `rerank_model` 是占位还是接真实模型

## 第二优先级

1. 收口 `doc_summary` 的正式索引与补召回双路径
2. 增加 query embedding cache
3. 为全文检索增加中文能力

## 第三优先级

1. 建离线评测集
2. 校准 `vector_weight / scope_weight / threshold`
3. 评估表格 `row_group` 是否需要低权重向量召回

---

## 十、最终结论

当前检索实现已经具备以下能力：

1. search_unit 多投影建模
2. 向量 + 全文双路召回
3. QA / 表格 / 通用文档差异化处理
4. 过滤前置解析
5. 父块上下文补全
6. 结果融合与解释信息输出

但当前还存在几个必须正视的问题：

1. 部分参数只是“看起来支持”，实际上没真正生效
2. doc_summary 和 rerank 仍有明显占位实现色彩
3. 中文 lexical 方案仍偏弱
4. 后续规模扩大后，性能和调参体系都要继续完善

所以结论不是“这套检索不行”，而是：

**这套检索已经有可继续演进的基础，但现在非常值得做一轮收口和增强。**
