# QA 与 kb_qa_rows 设计方案

> **文档定位**：阐述 QA 在「载体层 / 主事实层 / 检索层」中的分工；下文 **§17～§19** 与当前 `genesis-ai-platform` 实现、`docker/postgresql/init-schema.sql` **对齐**，便于评审与迭代。  
> **统一内容表**：当前阶段 QA **不**使用通用 `kb_content_items`，而走专表 `kb_qa_rows`；其他内容类型后续独立评估。

## 1. 目标

结合当前项目现状，明确以下设计目标：

- `documents + knowledge_base_documents` 继续表达「文件 / 数据集载体」
- `chunks` 只作为检索投影层，不再承担内容主存储职责
- QA 使用 QA 专表 `kb_qa_rows`（已实现），不落到通用内容表
- QA 手工录入通过「虚拟文件」进入系统，不要求用户上传物理原件
- 当前阶段不考虑历史兼容，优先采用对 QA 最清晰、最好维护的设计

本方案优先保证：

- 语义清晰
- 前后端模型直观
- QA 运营能力易扩展
- 分块与检索链路稳定

## 2. 当前现状与问题

当前系统主链路为：

- `documents`：物理文档资产 / 逻辑文件载体
- `knowledge_base_documents`：知识库中的文档挂载与处理实例
- `chunks`：检索切片

这条链路适合「文件 → 解析 → 分块 → 检索」的传统文档模式，但对 QA 会出现几个问题。

### 2.1 如果一条 QA 对应一条 document，数量会失控

不管是手工录入还是导入 1000 条 FAQ，如果每条 QA 都生成一条 `documents + knowledge_base_documents`，会带来：

- 记录数量膨胀
- UI 列表层级混乱
- 文件载体和问答记录概念混杂

### 2.2 如果只用 chunks 存 QA，会混淆「内容主事实」和「检索投影」

`chunks` 的职责应该是：

- 向量化
- 全文检索
- 召回排序
- LLM 上下文拼装

不应承担：

- QA 主存储
- QA 主编辑入口
- QA 版本语义

### 2.3 通用内容表对 QA 不够自然

如果继续使用通用 `kb_content_items`，虽然平台统一，但对 QA 会出现明显问题：

- 字段过于通用，语义绕
- `item_type / content_structured / metadata_info` 这一层壳太厚
- 后端接口和前端页面其实都只服务 QA，却始终在操作「通用内容项」
- 后续做 QA 去重、审核、别名管理、人工修改痕迹时，会越来越像在通用表里硬塞 QA 语义

所以当前阶段更合理的方向是：

- QA 用专表
- 其他内容类型后续再按各自语义决定是否使用通用表或独立表

## 3. 设计结论

QA 采用「三层模型」：

1. 载体层：`documents + knowledge_base_documents`
2. QA 主事实层：`kb_qa_rows`
3. 检索层：`chunks + embeddings`

职责划分如下。

### 3.1 载体层

继续复用：

- `documents`
- `knowledge_base_documents`

表示一个「QA 数据集载体」，例如：

- 上传的 Excel / CSV 文件
- 手工创建的 QA 虚拟文件（逻辑名多为 `.json`，见 §8）

### 3.2 QA 主事实层

QA 专表：

- `kb_qa_rows`

它表示某个 QA 数据集中的一条问答记录，是 **QA 的内容主事实表**（编辑、导出、重建 chunks 均以行为准）。

### 3.3 检索层

继续复用：

- `chunks`
- `embeddings`

这里只存为检索优化后的投影，不作为 QA 主存储。

## 4. 为什么选 kb_qa_rows，而不是 kb_content_items

当前阶段推荐：

- QA 使用 `kb_qa_rows`
- 不再让 QA 落到通用 `kb_content_items`

原因：

### 4.1 QA 是强结构化记录，不是「泛内容项」

QA 的字段天然稳定（与库表一致）：

- `question` / `answer`
- `similar_questions`（相似问题/别名，JSONB 数组）
- `category` / `tags`
- `source_row` / `source_sheet_name` / `source_row_id`

这类数据非常适合独立表，不需要额外套一层 `content_structured`。

### 4.2 QA 的后续能力会明显偏业务运营

后续很容易做这些能力：

- 问题去重
- 别名管理
- 单条启停
- 单条审核
- 人工修改痕迹
- 导入来源定位

这些都更适合专表。

### 4.3 通用性不是当前第一优先级

当前处于开发阶段，不需要为了「未来也许统一」而牺牲 QA 的清晰度。

更合适的策略是：

- QA 先走最合理的专表方案
- 网页、音视频、Notion 等后续按各自形态判断
- 真正需要统一时，再从更高层抽象

## 5. kb_qa_rows 表设计（与 init-schema 一致）

### 5.1 表职责

`kb_qa_rows` 表示某个 QA 数据集中的一条问答记录，是 QA 的内容主事实表。

### 5.2 字段（权威：`docker/postgresql/init-schema.sql`）

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| tenant_id | UUID | 租户 ID |
| kb_id | UUID | 所属知识库 |
| document_id | UUID | 所属载体 document |
| kb_doc_id | UUID | 所属知识库挂载实例 |
| source_row_id | VARCHAR(255) | 稳定来源记录 ID，可为空 |
| position | INTEGER | 在当前数据集中的稳定顺序 |
| question | TEXT | 标准问题 |
| answer | TEXT | 标准答案 |
| similar_questions | JSONB | 相似问题数组（导入列名 `similar_questions`） |
| category | VARCHAR(255) | 分类 |
| tags | JSONB | 标签数组 |
| source_mode | VARCHAR(32) | `manual` / `imported` |
| source_row | INTEGER | 来源行号 |
| source_sheet_name | VARCHAR(255) | Excel 工作表名 |
| has_manual_edits | BOOLEAN | 是否发生过人工修改（导入行上） |
| is_enabled | BOOLEAN | 是否启用参与检索 |
| content_hash | VARCHAR(64) | 内容哈希 |
| version_no | INTEGER | 版本号 |
| created_by_id / created_by_name | UUID / VARCHAR | 创建人 |
| updated_by_id / updated_by_name | UUID / VARCHAR | 修改人 |
| created_at / updated_at | TIMESTAMPTZ | 时间戳 |

> 历史文档若出现 `question_aliases` 列名，属旧稿；**库表与代码均以 `similar_questions` 为准**。

### 5.3 关键索引（已实现）

- `tenant_id`、`kb_id`、`kb_doc_id`
- `(kb_doc_id, is_enabled)`、`(kb_doc_id, position)`
- `source_row_id`、`content_hash`

说明：

- `kb_doc_id` 是最核心的查询入口，用于数据集详情页与重建
- `similar_questions` / `tags` 的 JSONB GIN 索引一期未启用；待出现稳定过滤需求再补

## 6. 三层关系定义

### 6.1 documents

表示「QA 数据集载体」。

例如：

- `售后FAQ.xlsx`
- `帮助中心FAQ.csv`
- `手工问答集-售后服务.json`（虚拟载体，见 §8）

### 6.2 knowledge_base_documents

表示该载体在某个知识库中的挂载和处理实例。

负责：

- 解析状态、分块配置、启停
- 运行时状态（如 `runtime_stage`）
- 标签、摘要等数据集级信息
- `display_name`：列表展示名（建议与「含扩展名的载体名」策略一致，避免与上传文件名脱节）

### 6.3 kb_qa_rows

表示载体里的具体问答记录（主事实）。

### 6.4 chunks

表示为检索优化生成的投影切片。

例如（与 `QAChunker` 一致）：

- 短答案：常对应 1 个可检索叶子块 `chunk_role=qa_row`
- 长答案：1 个父块 + N 个答案子块 `qa_answer_fragment` 等（见 §11）

## 7. QA 的数据语义

QA 不再直接依附于 `chunks`，而是：

- 载体：文件或虚拟文件
- 主事实：`kb_qa_rows`
- 检索投影：QA chunks

### 7.1 kb_qa_rows 的语义

每条记录就是一条完整问答：

- `question` / `answer`
- `similar_questions`：问题别名数组（模板列名同左）
- `category` / `tags`
- `source_row` / `source_sheet_name`：来源定位

### 7.2 不再需要 content_structured 壳

因为 QA 专表字段已经足够稳定，后端与前端可直接面向行模型，无需 `item_type='qa'` 的通用壳。

## 8. QA 的载体模型（含实现判别字段）

### 8.1 文件导入型 QA

支持：

- `.xlsx`、`.csv`（`QAParser` 固定模板，首 sheet）

进入系统后（服务层 `import_dataset_file`）：

1. 创建 `documents`（`source_type=upload`，`asset_kind=physical`，原始字节上传至 `file_key`）
2. 创建 `knowledge_base_documents`（`custom_metadata` 含 `content_kind=qa_dataset`、`source_mode=imported`、`virtual_file=false` 等）
3. 解析并写入 `kb_qa_rows`
4. 排队解析流水线，生成 / 更新 `chunks`

此时：

- 对象存储中的文件 = **导入时刻的用户文件快照**
- `kb_qa_rows` = **可编辑的主事实**（见 §9、§17）

### 8.2 手工录入型 QA（虚拟文件）

交互概要：

1. 用户在 QA 知识库中「新建问答集」
2. 系统创建虚拟载体：`documents` 上 `carrier_type=generated_snapshot`、`asset_kind=virtual`、`source_type=manual`，`metadata_info.virtual_file=true`
3. `documents.name` 经规范化后以 **`.json` 结尾**（逻辑文件名）
4. 问答内容写入 `kb_qa_rows`
5. 调用 `_sync_manual_dataset_file`：将当前所有行序列化为 **JSON 快照** 写入同一 `file_key`（便于与「按文件解析」流水线对齐）
6. 排队解析 / 重建生成 `chunks`

### 8.3 documents 表：实现侧判别约定（摘要）

| 维度 | 导入型 | 手工虚拟型 |
| --- | --- | --- |
| `source_type` | `upload` | `manual` |
| `asset_kind` | `physical` | `virtual` |
| `carrier_type` | `file`（常见） | `generated_snapshot` |
| `metadata_info` | `virtual_file: false`，`content_kind: qa_dataset` | `virtual_file: true`，`content_kind: qa_dataset` |

具体以 `QADatasetService.create_virtual_dataset` / `import_dataset_file` 为准。

### 8.4 knowledge_base_documents.custom_metadata 常见键

- `content_kind`: `qa_dataset`
- `virtual_file`: 是否虚拟载体
- `source_mode`: `manual` / `imported`
- `has_manual_edits`：是否发生过人工修改（数据集级）
- `edited_waiting_reparse` / `pending_reparse_row_count`：待重建状态（编辑后清理 chunks 并标记，用户触发「重建」后恢复）

## 9. 编辑策略（与实现一致）

编辑边界必须清晰，否则会出现「原文件、QA 主事实、chunk 到底编辑哪一层」的混乱。

### 9.1 默认只编辑 kb_qa_rows，不直接改 chunks

`chunks` 是索引投影，默认不作为主编辑入口。

编辑后：

- 删除该数据集已有 `chunks`（或等价清理）
- 将 `knowledge_base_documents` 置为「待重建」
- 用户触发「重建问答集」后，由 `kb_qa_rows` 重新生成 `chunks` 并触发向量化链路

### 9.2 手工录入型：允许全量维护

允许新增 / 修改 / 删除 / 启停 / 排序等；每次变更后会 **同步更新存储中的 JSON 快照**（§17）。

### 9.3 文件导入型：导入即初始化，可继续编辑

策略：

- 导入后生成 `kb_qa_rows`，后续编辑只改行表
- 导入后在存储中的 **原始 xlsx/csv 不会被覆盖**；编辑仅在 DB 与后续导出 / 重建中体现（§17）
- `_sync_manual_dataset_file` 对导入型走「仅打标记」分支：`documents.metadata_info.has_manual_edits`、`kb_doc.custom_metadata.has_manual_edits` 等

### 9.4 QA 类型默认不开放 chunk 编辑

即使系统保留 chunk 编辑能力，也建议 QA 默认关闭；若开放调试能力，必须提示「仅影响检索投影」。

## 10. 前端展示最佳实践

不要在同一层把「文件载体」和「单条 QA」混在一个列表中展示。

### 10.1 第一层：载体列表

对应 `knowledge_base_documents`（及关联 `documents`），展示数据集名称：

- 建议 `display_name` 与 `documents.name` 在「是否含扩展名」上策略一致，避免列表与下载名不一致。

### 10.2 第二层：问答列表

对应 `kb_qa_rows`：问题、答案摘要、标签、分类、启停、来源行号、更新时间等。

## 11. chunks 在新模型下的角色

`chunks` 继续复用，职责收敛为检索与上下文构建。

对 QA（`QAChunker`）：

- 短答案：生成可向量化的叶子块
- 长答案：父块 + 答案片段子块；父块可标记不参与检索（`exclude_from_retrieval`）

**库表列名**：PostgreSQL 中为 **`chunks.metadata`（JSONB）**，不是 `metadata_info`。Chunker 产出的内存结构里使用 `metadata` 键，持久化时写入该列。

建议在 `chunks.metadata` 中承载 QA 投影信息（示例，以实际落库为准）：

- `qa_row_id`、`chunk_role`（如 `qa_row` / `qa_answer_fragment`）
- `similar_questions`、`source_mode`
- 以及与统一 chunk 协议一致的 `source_anchors`、`page_numbers` 等（无页码时为空数组）

`content_blocks` 承载结构化预览与上下文组装所需块列表。

## 12. QA 检索策略建议

（策略方向保持不变。）

- `question` 主召回；`similar_questions` 辅助
- `answer` 参与召回；长答案拆子块
- `tags` / `category` 偏过滤与重排

## 13. 解析与重建流程（与 parse_task 对齐）

### 13.1 文件导入型

1. 上传并创建 `documents` + `knowledge_base_documents`
2. 服务层已将行写入 `kb_qa_rows`
3. `parse_task` 在 QA 知识库下可选用 **`qa_rows` 策略**（从 `kb_qa_rows` 组装元数据），避免重复依赖原始文件解析出行数据
4. `chunk_task` / `QAChunker` 基于行数据生成 `chunks`
5. 向量化与检索索引

### 13.2 手工录入型

1. 创建虚拟载体与行数据
2. 同步 JSON 快照至存储
3. 编辑行 → 清理 chunks、标记待重建
4. 「重建问答集」→ 从最新 `kb_qa_rows` 生成 `chunks`（`rebuild_dataset`）

### 13.3 内容变更后的索引更新

主事实先改、投影后重建；与 §9 一致。

## 14. QA 导入模板规范（与 QAParser 一致）

第一期导入入口：

- `.xlsx`、`.csv`
- **不开放**用户上传 `.json` 作为批量导入格式（与「虚拟载体文件名 `.json`」区分：后者是系统内部逻辑名，不是导入模板）

固定表头，不做动态字段映射：

| 列名 | 必填 | 说明 |
| --- | --- | --- |
| question | 是 | 标准问题 |
| answer | 是 | 标准答案 |
| similar_questions | 否 | 多个别名使用 `||` 分隔 |
| category | 否 | 单值 |
| tags | 否 | 多个标签可用 `,` / `，` / `;` / `；` 分隔 |
| enabled | 否 | 默认启用；支持 `true/false`、`1/0`、`yes/no`、`是/否`、`启用/禁用` 等 |

约束：

- Excel 第一阶段只读第一个 sheet
- CSV 推荐 UTF-8 或 UTF-8-SIG
- `question` / `answer` 为空的行视为无效

模板示例：

```csv
question,answer,similar_questions,category,tags,enabled
如何重置密码？,进入个人中心的安全设置页面重置密码。,忘记密码怎么办||密码重置入口在哪||怎么修改登录密码,账号管理,账号,true
如何开具发票？,在订单详情页申请开票即可。,怎么申请发票||发票在哪里开,发票,发票,true
```

## 15. 后续与其他类型的关系

- QA：`kb_qa_rows` 专表
- 网页 / 音视频 / 第三方同步：各自评估专表或同步模型

统一的是 **载体 + 主事实 + 检索投影** 的分层思想，而非「一张通用内容表包一切」。

## 16. 最终建议（摘要）

- 载体层：`documents + knowledge_base_documents`
- 主事实：`kb_qa_rows`
- 投影：`chunks + embeddings`
- 导入与手工均可编辑行表；导入原件保留为审计快照，**当前实现不随编辑回写存储文件**（§17）
- UI：载体列表与问答列表分层展示

---

## 17. 对象存储与「文件真源」——当前实现行为（重要）

本节描述 **`QADatasetService._sync_manual_dataset_file`** 与相关路径的**实际行为**，用于产品与研发对齐预期。

### 17.1 手工虚拟数据集

- **会**在每次增删改、启停、排序等操作后，将当前全部 `kb_qa_rows` 序列化为 UTF-8 JSON，**上传覆盖** `documents.file_key` 指向的对象。
- **主事实仍以 `kb_qa_rows` 为准**；存储 JSON 更多用于「载体上仍有可下载/可解析的文件对象」与流水线对齐。
- `rebuild_dataset` **不会**再次调用上述同步函数；通常编辑路径已先同步，若未来存在「仅重建、不经过编辑」的脚本入口，需自行评估快照是否仍一致。

### 17.2 Excel / CSV 导入数据集

- **首次导入**：用户文件字节上传至 `file_key`，与 `documents` 记录一致。
- **后续编辑**：仍会调用 `_sync_manual_dataset_file`，但实现上进入 **「仅更新元数据」** 分支：设置 `has_manual_edits` 等，**不会对存储中的 xlsx/csv 做 upload 覆盖**。
- 因此：**对象存储中的导入文件 = 导入时刻快照**；**当前业务数据 = `kb_qa_rows`**。

### 17.3 导出 CSV（`export_dataset_csv`）

- **明确基于最新 `kb_qa_rows` 生成**，不读取存储中的原始导入文件。
- 导出文件名来自 `knowledge_base_documents.display_name` 或 `documents.name`；HTTP `Content-Disposition` 需符合 ASCII/latin-1 规范（实现上已用 RFC 5987 `filename*` 承载中文）。

---

## 18. 导出 / 下载 / 「原文件」产品语义（建议）

| 能力 | 建议语义（与现实现一致部分已标注） |
| --- | --- |
| 导出 CSV | 反映 **当前行表**（已实现） |
| 下载载体文件 | 若走 `documents` 存储：导入型可能为 **导入快照**，与行表可能不一致（§17.2） |

**建议在 UI 文案上区分**：「导出当前数据」vs「下载最初上传文件（仅作留档）」——是否需要后者由产品决定（见 §20）。

---

## 19. 实现对照清单（便于代码阅读）

| 主题 | 主要位置 |
| --- | --- |
| QA 行 CRUD、导入、导出、存储同步 | `services/qa_dataset_service.py` |
| 模板解析 | `rag/ingestion/parsers/qa/qa_parser.py` |
| QA 分块 | `rag/ingestion/chunkers/qa/qa_chunker.py` |
| 解析任务中 QA 策略（含 qa_rows） | `rag/ingestion/tasks/parse_task.py` |
| 表结构 | `docker/postgresql/init-schema.sql` → `kb_qa_rows` |

---

## 20. 待你确认的设计取舍（非最佳实践或产品决策）

以下项 **无唯一标准答案**，请按产品目标拍板；确认后可将结论回写本节。

1. **导入型「存储文件与行表双轨」**  
   不覆盖存储可节省写放大、保留审计原件；但任何「下载即当前数据」的预期会落空。是否接受「导出 = 真源，原文件 = 快照」？是否需要「同步回写 xlsx/csv」的可选能力？

2. **手工虚拟集的 JSON 快照**  
   与 `kb_qa_rows` 存在冗余。是否长期保留「必须有一份物理 JSON」的约束，还是未来改为解析任务 **只读行表**、虚拟载体可不落文件（需改流水线）？

3. **`rebuild_dataset` 与快照**  
   当前重建不强制刷新 JSON。是否在重建成功后再调用一次同步，保证存储快照与 chunks 同一「版本」语义？

4. **跨模块复用 `_build_content_disposition`**  
   导出接口从 `api.v1.documents` 引用私有函数属小技术债；是否抽到 `core` 公共工具？

---

*文档版本说明：本次更新对齐库表字段名 `similar_questions`、`chunks.metadata`、导入/虚拟载体存储策略及导出语义，并拆分「设计原则」与「实现行为」便于评审。*
