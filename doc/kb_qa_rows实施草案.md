# kb_qa_rows 实施草案

## 1. 文档目的

在 [QA与统一内容表设计方案.md](d:/workspace/python/genesis-ai/doc/QA与统一内容表设计方案.md) 的基础上，给出 `kb_qa_rows` 方案的实施落地规格，便于继续推进代码迁移与收尾。

本草案聚焦：

- `kb_qa_rows` 的 DDL 与索引
- SQLAlchemy Model / Schema 的最终落点
- QA 专用接口与服务边界
- `QAParser -> kb_qa_rows -> QAChunker -> chunks` 的任务链
- 导入型 QA 与手工型 QA 的统一维护规则


## 2. 当前实施结论

QA 不再使用通用 `kb_content_items`。

当前正式方向：

1. `documents`
   表示 QA 数据集载体

2. `knowledge_base_documents`
   表示 QA 数据集在知识库中的挂载实例

3. `kb_qa_rows`
   表示数据集中的每一条问答记录，是 QA 主事实层

4. `chunks`
   表示 QA 检索投影层


## 3. 数据关系

推荐关系：

- 1 个 `document`
  - 对应 1..N 个 `knowledge_base_documents`
- 1 个 `knowledge_base_document`
  - 对应 0..N 个 `kb_qa_rows`
- 1 个 `kb_qa_row`
  - 对应 0..N 个 `chunks`


## 4. 表结构落地

权威 DDL 已同步到：

- [init-schema.sql](d:/workspace/python/genesis-ai/docker/postgresql/init-schema.sql)
- [数据库设计.md](d:/workspace/python/genesis-ai/doc/数据库设计.md)

当前 `kb_qa_rows` 的核心字段为：

- `id`
- `tenant_id`
- `kb_id`
- `document_id`
- `kb_doc_id`
- `source_row_id`
- `position`
- `question`
- `answer`
- `question_aliases`
- `category`
- `tags`
- `source_mode`
- `source_row`
- `source_sheet_name`
- `has_manual_edits`
- `is_enabled`
- `content_hash`
- `version_no`
- 审计字段

当前最小必要索引为：

- `tenant_id`
- `kb_id`
- `kb_doc_id`
- `(kb_doc_id, is_enabled)`
- `(kb_doc_id, position)`
- `source_row_id`
- `content_hash`


## 5. Model / Schema 落点

当前推荐与已实施方向：

- Model：
  - [kb_qa_row.py](d:/workspace/python/genesis-ai/genesis-ai-platform/models/kb_qa_row.py)

- Schema：
  - [kb_qa_row.py](d:/workspace/python/genesis-ai/genesis-ai-platform/schemas/kb_qa_row.py)

说明：

- QA 专用请求体继续单独保留
- 不再复用通用 `kb_content_item` schema
- 前端接口响应目前暂时仍兼容旧的 `content_structured` 形状，便于页面平滑过渡


## 6. QA 数据集服务落点

当前 QA 服务应直接围绕 `kb_qa_rows` 工作：

- 列表：按 `kb_doc_id` 查询 `kb_qa_rows`
- 新增：插入单条 `kb_qa_rows`
- 更新：修改 `question / answer / aliases / tags / category`
- 删除：删除对应 `kb_qa_rows`
- 启停：更新 `is_enabled`
- 排序：更新 `position`

推荐服务文件：

- [qa_dataset_service.py](d:/workspace/python/genesis-ai/genesis-ai-platform/services/qa_dataset_service.py)

行为原则：

- 导入型 QA 和手工型 QA 都允许编辑
- 编辑主入口始终是 `kb_qa_rows`
- 编辑后先将数据集置为待重建，再统一从 `kb_qa_rows` 重建 `chunks`


## 7. Parser / Chunker / Task 链路

当前推荐链路：

### 7.1 文件导入型 QA

1. 上传 `.csv/.xlsx`
2. 在“关联到知识库”阶段立即调用 `QAParser`，并将结果落到 `kb_qa_rows`
3. `parse_task` 优先从 `kb_qa_rows` 构建 QA metadata，而不是重新解析原始文件
4. `chunk_task` 从 `kb_qa_rows` 读取数据
5. `QAChunker` 生成 QA chunks
6. `train_task` 写入 embeddings

### 7.2 手工维护型 QA

1. 创建虚拟文件载体
2. 前端新增 / 编辑问答
3. 服务层直接更新 `kb_qa_rows`
4. 将数据集标记为待重建，并清理旧 chunks
5. 用户触发重建时，再统一从 `kb_qa_rows` 出发生成 chunks
6. 更新 embeddings

当前关键文件：

- [qa_parser.py](d:/workspace/python/genesis-ai/genesis-ai-platform/rag/ingestion/parsers/qa/qa_parser.py)
- [parse_task.py](d:/workspace/python/genesis-ai/genesis-ai-platform/rag/ingestion/tasks/parse_task.py)
- [chunk_task.py](d:/workspace/python/genesis-ai/genesis-ai-platform/rag/ingestion/tasks/chunk_task.py)
- [qa_chunker.py](d:/workspace/python/genesis-ai/genesis-ai-platform/rag/ingestion/chunkers/qa/qa_chunker.py)


## 8. Chunk 协议映射

`kb_qa_rows -> chunks` 时，建议使用：

- `metadata_info.node_id`
- `metadata_info.parent_id`
- `metadata_info.child_ids`
- `metadata_info.depth`
- `metadata_info.is_leaf`
- `metadata_info.should_vectorize`
- `metadata_info.qa_row_id`
- `metadata_info.chunk_role`
- `metadata_info.question`
- `metadata_info.question_aliases`
- `metadata_info.tags`
- `metadata_info.category`

说明：

- 不再使用 `content_item_id`
- 统一使用 `qa_row_id`
- QA 的主关联键已经从“通用内容项”切换为“QA 行”
- 长答案按“父块 `qa_row` + 子块 `qa_answer_fragment`”输出，父子层级协议与表格型知识库保持一致


## 9. 前端接口兼容策略

当前前端 QA 管理页已经大量依赖：

- `content_structured.question`
- `content_structured.answer`
- `content_structured.question_aliases`
- `content_structured.tags`
- `content_structured.category`

因此当前阶段建议：

- 后端内部已切到 `kb_qa_rows`
- 对外接口响应先继续兼容旧形状
- 等迁移稳定后，再决定是否把前端类型改成更直接的 QA 行结构

这是“存储层先收敛，接口层后收敛”的策略。


## 10. 当前遗留与下一步

这份草案仍有参考价值，因为代码迁移还在继续，但旧的 `kb_content_items` 草案已经不再适合作为权威文档。

当前下一步建议：

1. 继续收敛 `qa_dataset_service` 中围绕 `kb_qa_rows` 的维护能力
2. 完成 QA 前端 API 类型从“通用内容项语义”向“QA 行语义”收敛
3. 继续补 `kb_qa_rows` / `QAChunker` / 任务链的专用测试
4. 最后再决定是否继续保留任何 `kb_content_items` 概念


## 11. 结论

当前阶段：

- 旧的 `kb_content_items实施草案.md` 不再适合作为参考
- 应由 `kb_qa_rows实施草案.md` 取代
- 这份文档保留，是为了服务当前仍在进行中的代码迁移

等 `kb_qa_rows` 迁移彻底完成后，如果文档内容已经完全被代码和主设计文档覆盖，再考虑进一步精简。
