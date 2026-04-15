# 聊天模块与 API 会话设计方案

## 1. 文档目标

本文用于给 Genesis AI 平台的聊天功能提供一版正式设计建议，覆盖以下问题：

- 聊天会话如何支持多知识库选择
- 检索召回参数如何设计，哪些应该做成会话配置，哪些应该做成单轮执行快照
- API 调用是否需要存储聊天记录
- 如果既有 UI 聊天，又有 API 聊天，如何统一设计且避免互相污染
- 如何兼顾后续的可观测性、调试、评估、审计与扩展

本文是设计稿，不直接替代当前 `docker/postgresql/init-schema.sql`，而是用于指导后续统一重构。

当前项目处于开发阶段，本文采用“按最佳实践重新设计”的原则，不考虑兼容现有 `init-schema.sql` 中的聊天相关表；后续可直接删除旧的聊天相关表并按新模型重建。

> 重要修正
>
> 本文最终正式采用两层聊天模型：
>
> - `chat_spaces`：聊天空间 / 聊天集合 / 聊天入口容器
> - `chat_sessions`：某个聊天空间下的具体会话实例
>
> 因此，文档中前面少量把 `chat_sessions` 直接当作顶层聊天容器的分析性表述，仅作为中间推导过程参考；正式落地时应以本文后部“V2 正式定稿模型”为准。

---

## 2. 对现状的判断

当前库中已经存在最基础的聊天结构：

- `conversations`
- `messages`

现有设计的优点：

- 已有会话与消息的基础抽象
- 已有 `knowledge_bases.retrieval_config`，说明知识库默认检索参数这一层已经存在
- 前端原型已经明确表现出“会话绑定 Agent、多知识库、右侧参数面板”的产品方向

现有设计的不足：

- `conversations.kb_id` 只能绑定单知识库，不符合当前原型的多知识库勾选模式
- `conversations.config` 过于笼统，缺乏结构化字段，不利于筛选、统计和审计
- `messages.references` 与 `messages.agent_steps` 都堆在 JSONB 中，后续做引用明细、召回分析、链路调试时会很吃力
- 没有区分“用户可见的会话数据”和“系统执行过程数据”
- 没有明确区分 `UI` 聊天与 `API` 聊天
- 没有明确支持“持久化会话”和“无状态临时调用”两种 API 模式

结论：

聊天模块不应继续停留在 `会话 + 消息` 的单层模型，而应该升级为：

- 空间层：用户看到的聊天集合、聊天入口、默认配置容器
- 会话层：某个聊天空间下可连续追问的具体会话实例
- 执行层：每一轮真实推理与检索执行快照

---

## 3. 设计原则

### 3.1 会话层与执行层分离

会话层解决的是：

- 用户看到哪些会话
- 会话标题、归档、置顶、来源渠道
- 会话默认使用哪些知识库和哪些参数

执行层解决的是：

- 某一轮问答实际用了哪些知识库
- 实际用了什么模型、什么召回参数、什么重排参数
- 召回了哪些 chunk，最终引用了哪些 chunk
- 耗时、token、失败原因、调试轨迹

### 3.2 默认配置与运行快照分离

不能只存一份 `config JSONB`。

必须区分：

- 默认配置：会话或 Agent 层面的长期配置
- 运行快照：某次请求实际生效的参数

否则后期会出现无法回答“这次为什么这么回答”的问题。

### 3.3 UI 与 API 统一能力，但允许不同持久化策略

UI 聊天与 API 聊天应该复用同一套核心聊天服务和同一套检索/生成链路。

但在数据保留层面必须允许差异：

- UI 默认持久化
- API 可持久化，也可无状态调用

### 3.4 高价值数据结构化，低频扩展字段 JSONB

以下高频字段应独立成列：

- 渠道
- 会话状态
- 默认模型
- 默认 Agent
- 最后消息时间
- 是否持久化
- 执行状态
- token 和耗时

以下低频扩展字段可保留 JSONB：

- 额外展示配置
- 前端布局偏好
- 调试元信息
- 厂商兼容字段

### 3.5 不存储完整思维链

不要把模型完整 CoT 作为数据库正式字段持久化。

可以存：

- 安全的执行摘要
- 工具调用轨迹
- 检索过程摘要
- 错误上下文

不建议存：

- 完整内部推理过程
- 未脱敏的中间提示词拼接结果

---

## 3.6 实施口径说明

为了避免歧义，本文明确区分“分析过程”与“正式实施口径”。

### A. 仅作为分析参考的内容

下列章节包含方案推导、开源对比、单层模型讨论和终局扩展设想，允许与最终实现口径不完全一致：

- 第 4 节到第 29 节

这些章节的价值在于：

- 解释为什么要这样设计
- 记录方案演进过程
- 讨论未来可能扩展到的能力

但它们**不是后续直接开发的权威实现定义**。

### B. 后续开发必须遵循的正式口径

后续数据库、后端接口、前端联调，统一以以下内容为准：

1. 第 30 节：`V2 正式定稿模型`
2. 第 31 节：`设计复审：字段收敛、性能与是否过度设计`
3. 第 32 节：`首批落地版表结构建议`
4. 第 33 节：`首批落地版字段建议`
5. 第 34 节：`首批落地版的合理性判断`
6. `docker/postgresql/init-schema.sql` 中已经落地的新聊天相关表结构

如果文档分析段落与已落地 SQL 存在冲突：

- 以 `docker/postgresql/init-schema.sql` 为准
- 后续应先修正文档，再继续开发

### C. 当前最终实施表范围

当前已经在 SQL 中落地、后续开发应直接围绕它们展开的表为：

- `retrieval_profiles`
- `workflows`
- `chat_spaces`
- `chat_space_capability_bindings`
- `chat_sessions`
- `chat_session_stats`
- `chat_messages`
- `chat_message_citations`
- `chat_turns`
- `chat_turn_retrievals`
- `chat_turn_tool_calls`
- `chat_turn_workflow_runs`

### D. 当前未落地、仅保留为未来扩展讨论的对象

以下概念可以继续保留在文档中做架构讨论，但**当前不作为开发实现对象**：

- `assistants`
- `agents`
- `assistant_capability_bindings`
- `agent_capability_bindings`
- `chat_turn_agent_runs`
- `chat_space_stats`
- `chat_feedback`

也就是说：

- 当前正式实现以“知识库聊天 + 工作流兼容”主线为准
- Agent 平台相关设计暂不进入首批开发范围

---

## 4. 推荐领域模型

推荐将聊天模块拆为以下核心对象。

### 4.1 `chat_sessions`

用途：用户可见的聊天会话主表。

建议字段：

- `id`
- `tenant_id`
- `owner_id`
- `title`
- `summary`
- `channel`
- `session_type`
- `status`
- `visibility`
- `persistence_mode`
- `default_agent_id`
- `default_model_id`
- `default_system_prompt_id` 或 `default_system_prompt`
- `default_config`
- `last_message_at`
- `message_count`
- `created_by_id`
- `updated_by_id`
- `created_at`
- `updated_at`

建议枚举：

- `channel`: `ui | api | system`
- `session_type`: `rag | llm_only | agent`
- `status`: `active | archived | deleted`
- `visibility`: `user_visible | backend_only`
- `persistence_mode`: `persistent | ephemeral`

关键说明：

- `channel` 用于区分界面创建、API 创建、系统任务生成
- `visibility` 用于控制 API 会话是否展示在前端会话列表
- `persistence_mode` 用于控制该会话是否长期保留
- `default_config` 存会话级默认参数，不是单轮真实执行参数

### 4.2 `chat_session_knowledge_bases`

用途：聊天会话与知识库的多对多关联表。

建议字段：

- `id`
- `tenant_id`
- `session_id`
- `knowledge_base_id`
- `is_enabled`
- `binding_role`
- `sort_order`
- `binding_config`
- `created_at`
- `updated_at`

关键说明：

- 一个会话可以绑定多个知识库
- 某个知识库可临时禁用，但不需要从会话中移除
- `binding_config` 可用于表达某个知识库自己的局部覆盖参数
- `binding_role` 可预留给后续“主知识库 / 辅助知识库 / 背景知识库”等语义

### 4.3 `chat_messages`

用途：消息主表，只负责存储消息本身。

建议字段：

- `id`
- `tenant_id`
- `session_id`
- `turn_id`
- `parent_message_id`
- `role`
- `message_type`
- `content`
- `content_blocks`
- `status`
- `is_visible`
- `source_channel`
- `user_id`
- `created_at`
- `updated_at`

建议枚举：

- `role`: `system | user | assistant | tool`
- `message_type`: `text | file | event | tool_result`
- `status`: `pending | streaming | completed | failed`
- `source_channel`: `ui | api | system`

关键说明：

- 推荐使用 UUID，不建议继续用 `BIGSERIAL`
- `turn_id` 让消息和某一轮执行一一对应
- `content_blocks` 用于支持富文本、引用卡片、附件块、表格块、工具结果块
- 对纯文本内容，`content` 足够；对复杂消息，渲染优先读 `content_blocks`

### 4.4 `chat_message_citations`

用途：存助手消息最终引用了哪些来源。

建议字段：

- `id`
- `tenant_id`
- `message_id`
- `session_id`
- `turn_id`
- `citation_index`
- `kb_id`
- `kb_doc_id`
- `chunk_id`
- `source_anchor`
- `page_number`
- `snippet`
- `score`
- `metadata`

关键说明：

- 不建议只把引用放在 `messages.references` JSONB 中
- 结构化后，前端可以更容易做“引用定位、引用过滤、引用分析”
- 也更方便后续做“回答引用覆盖率”和“召回命中率”的评估

### 4.5 `chat_turns`

用途：一轮问答一次执行记录，是聊天执行层的核心表。

建议字段：

- `id`
- `tenant_id`
- `session_id`
- `user_message_id`
- `assistant_message_id`
- `request_id`
- `channel`
- `execution_mode`
- `status`
- `agent_id`
- `model_id`
- `effective_config`
- `effective_kb_ids`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `latency_ms`
- `started_at`
- `completed_at`
- `error_code`
- `error_message`
- `debug_summary`
- `created_at`
- `updated_at`

建议枚举：

- `execution_mode`: `sync | async | stream`
- `status`: `queued | running | completed | failed | cancelled`

关键说明：

- `effective_config` 是本轮真实生效参数快照
- `effective_kb_ids` 是本轮真实参与召回的知识库集合
- 即使会话默认绑定了 5 个知识库，本轮也可能只实际用了其中 2 个

### 4.6 `chat_turn_retrievals`

用途：记录一轮问答的召回明细。

建议字段：

- `id`
- `tenant_id`
- `turn_id`
- `session_id`
- `kb_id`
- `kb_doc_id`
- `chunk_id`
- `retrieval_stage`
- `raw_score`
- `rerank_score`
- `selected_for_context`
- `selected_for_citation`
- `rank_index`
- `metadata`
- `created_at`

关键说明：

- `retrieval_stage` 可表示 `vector / keyword / hybrid / rerank / final_context`
- 后续做召回调优时，这张表非常重要
- 这张表和原有 `query_logs` 职责有重叠，建议未来逐步收敛，以 `chat_turn_retrievals` 为主

### 4.7 `chat_feedback`

用途：对回答做点赞、点踩、纠错、补充反馈。

建议字段：

- `id`
- `tenant_id`
- `session_id`
- `message_id`
- `turn_id`
- `user_id`
- `feedback_type`
- `feedback_text`
- `created_at`

建议枚举：

- `feedback_type`: `upvote | downvote | correction | report`

---

## 5. 参数设计建议

### 5.1 参数分层

推荐采用四层覆盖模型：

1. 租户默认参数
2. Agent 预设参数
3. 会话默认参数
4. 单轮请求覆盖参数

优先级从后向前覆盖。

最终执行参数必须写入 `chat_turns.effective_config`。

### 5.2 参数分类

不建议继续把所有参数混成一个“右侧滑块区域”。

推荐拆为以下几类。

#### A. 生成参数

- `temperature`
- `top_p`
- `max_output_tokens`
- `presence_penalty`
- `frequency_penalty`
- `reasoning_effort`

说明：

- `Reasoning Mode` 不建议只做布尔值
- 更推荐 `reasoning_effort = low | medium | high`

#### B. 检索参数

- `retrieval_enabled`
- `recall_top_k`
- `score_threshold`
- `retrieval_strategy`
- `enable_hybrid_search`
- `enable_rerank`
- `rerank_model_id`
- `rerank_top_k`
- `final_context_k`

说明：

- 前端“Search Depth (K)”命名过于模糊
- 应该拆成召回阶段、重排阶段、最终上下文阶段三个层次

#### C. 上下文构建参数

- `max_context_tokens`
- `context_merge_strategy`
- `citation_mode`
- `deduplicate_chunks`
- `chunk_grouping_strategy`

#### D. Agent 参数

- `agent_id`
- `tool_choice_mode`
- `allow_web_search`
- `allow_function_call`
- `tool_timeout_ms`

---

## 6. API 调用是否要存储聊天记录

结论：不要只有一种模式，最佳实践是同时支持“无状态模式”和“会话模式”。

### 6.1 UI 聊天

推荐策略：默认持久化。

原因：

- 用户天然希望在界面中看到聊天历史
- 需要支持继续追问、归档、搜索、会话管理

### 6.2 API 聊天

推荐策略：支持两种模式。

#### 模式 A：无状态调用

特征：

- 不要求预先创建会话
- 可直接提交消息并获得结果
- 默认不保存消息正文到聊天会话表
- 只记录调用日志、模型日志、检索摘要、耗时与 token

适用场景：

- 外部系统临时调用
- 对隐私要求高的场景
- 对话历史由调用方自行维护

#### 模式 B：有状态调用

特征：

- 显式传 `session_id`
- 或传 `auto_create_session=true`
- 或传 `persist=true`
- 平台会持久化会话和消息，可在 UI 中展示

适用场景：

- API 与平台 UI 混合使用
- 希望在平台内回看 API 对话
- 需要统一审计与历史复盘

### 6.3 推荐 API 参数

建议 API 层支持以下控制字段：

- `session_id`
- `persist`
- `auto_create_session`
- `visibility`
- `channel`

建议语义：

- `session_id`：指定已有会话
- `persist=true`：落库为正式会话消息
- `auto_create_session=true`：若未传 `session_id`，则自动建会话
- `visibility=user_visible | backend_only`：决定是否进入前端列表
- `channel=api`：标识来源为 API

### 6.4 推荐默认行为

推荐默认值：

- UI：`persist=true`，`visibility=user_visible`
- API：`persist=false`，仅写调用日志

推荐原因：

- 这样更符合企业产品的隐私预期
- 避免 API 调用大量污染聊天列表
- 后续如果客户有“必须留痕”的要求，可以通过租户策略开启默认持久化

---

## 7. UI 与 API 共存时的展示策略

如果希望“在界面中看到 API 产生的聊天记录”，建议不要单纯通过表名区分，而是通过元数据控制。

### 7.1 必须具备的区分字段

在 `chat_sessions` 中至少应有：

- `channel`
- `visibility`
- `persistence_mode`

### 7.2 前端列表展示规则

前端“我的对话”列表默认查询：

- `status != deleted`
- `visibility = user_visible`
- 当前用户有权限查看

必要时可提供筛选项：

- 全部
- 界面创建
- API 创建
- 系统生成

### 7.3 推荐体验

如果 API 创建的会话允许在前端显示，建议列表卡片上有来源标记：

- `UI`
- `API`
- `SYSTEM`

这样用户不会混淆来源。

---

## 8. 与当前前端原型的映射建议

当前原型方向总体正确，但建议做以下调整。

### 8.1 右侧配置面板建议保留

保留内容：

- Agent 选择
- 绑定知识库
- 生成参数
- 检索参数

### 8.2 建议下沉到高级设置的项目

以下内容不建议默认直接暴露给普通用户：

- `score_threshold`
- `rerank_top_k`
- `max_context_tokens`
- `retrieval_strategy`
- `chunk_grouping_strategy`

更好的方式：

- 默认展示“预设模式”
- 高级用户展开“高级参数”

### 8.3 参数预设建议

建议提供参数预设：

- `精确`
- `平衡`
- `深度分析`
- `开放发散`

这样普通用户不必理解所有检索细节。

### 8.4 “Re-index Sources” 不建议放在会话抽屉

原因：

- 重建索引是知识库运维动作，不是聊天会话动作
- 它会造成权限边界和用户心智混乱

建议位置：

- 知识库详情页
- 知识库管理页
- 文档解析任务页

---

## 9. 与现有库表的关系与迁移建议

### 9.1 `conversations`

当前问题：

- 只有 `kb_id`
- 只能表达单知识库
- `config` 语义过大

建议：

- 未来迁移为 `chat_sessions`
- 保留 `config`，但重命名为 `default_config`
- 删除单 `kb_id` 绑定方式，改为关联表

### 9.2 `messages`

当前问题：

- `references` 与 `agent_steps` 结构化不足
- 不利于引用分析与执行审计

建议：

- 未来迁移为 `chat_messages`
- 新增 `turn_id`
- 引用拆到 `chat_message_citations`
- 调试轨迹拆到 `chat_turns` 或专门的执行日志表

### 9.3 `query_logs`

当前问题：

- 适合做粗粒度分析
- 不足以支撑聊天场景下的细粒度召回可观测性

建议：

- 保留作为历史兼容或全局统计表
- 聊天链路逐步迁移到 `chat_turns + chat_turn_retrievals`

### 9.4 `model_invocation_logs`

当前定位正确，应继续保留。

建议：

- 聊天执行成功后，把 `chat_turns.request_id` 与 `model_invocation_logs.request_id` 关联
- 用于串起模型调用、聊天执行、检索明细三类数据

---

## 10. 推荐 API 设计

### 10.1 会话接口

建议接口：

- `POST /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions/{session_id}`
- `PATCH /api/v1/chat/sessions/{session_id}`
- `POST /api/v1/chat/sessions/{session_id}/archive`
- `DELETE /api/v1/chat/sessions/{session_id}`

创建会话请求建议：

- `title`
- `session_type`
- `agent_id`
- `knowledge_base_ids`
- `default_config`
- `visibility`

### 10.2 发消息接口

建议接口：

- `POST /api/v1/chat/sessions/{session_id}/messages`

请求建议：

- `message`
- `attachments`
- `override_config`
- `knowledge_base_overrides`
- `stream`

### 10.3 无状态聊天接口

建议接口：

- `POST /api/v1/chat/completions`

请求建议：

- `messages`
- `knowledge_base_ids`
- `agent_id`
- `config`
- `persist`
- `session_id`
- `auto_create_session`
- `visibility`
- `stream`

### 10.4 响应中应返回的信息

建议返回：

- `session_id`
- `turn_id`
- `assistant_message_id`
- `content`
- `citations`
- `usage`
- `debug_summary`

---

## 11. 推荐索引与性能建议

### 11.1 `chat_sessions`

建议索引：

- `(tenant_id, owner_id, status, updated_at desc)`
- `(tenant_id, channel, visibility, updated_at desc)`
- `(tenant_id, last_message_at desc)`

### 11.2 `chat_messages`

建议索引：

- `(session_id, created_at)`
- `(tenant_id, session_id, created_at)`
- `(turn_id)`

### 11.3 `chat_turns`

建议索引：

- `(session_id, created_at desc)`
- `(tenant_id, request_id)`
- `(tenant_id, status, created_at desc)`

### 11.4 `chat_turn_retrievals`

建议索引：

- `(turn_id, rank_index)`
- `(tenant_id, kb_id, created_at desc)`
- `(chunk_id)`

---

## 12. 权限与审计建议

聊天模块要纳入现有权限体系，至少建议以下权限点：

- `chat:session:create`
- `chat:session:read`
- `chat:session:update`
- `chat:session:delete`
- `chat:message:create`
- `chat:message:read`
- `chat:config:update`
- `chat:api:invoke`
- `chat:api:view_backend_only`

审计重点：

- 谁创建了会话
- 谁修改了会话配置
- 谁将 API 会话暴露为前端可见
- 谁查看了非本人会话

---

## 13. 第一阶段落地建议

如果按低风险、可逐步上线的方式推进，建议分三期。

### 第一期：打通基础聊天闭环

目标：

- 会话列表
- 会话详情
- 多知识库绑定
- 基础参数配置
- 消息持久化

最低需要表：

- `chat_sessions`
- `chat_session_knowledge_bases`
- `chat_messages`

### 第二期：打通执行快照与引用

目标：

- 每轮执行参数快照
- 引用明细
- token、耗时、错误
- 检索过程可观测

新增表：

- `chat_turns`
- `chat_message_citations`
- `chat_turn_retrievals`

### 第三期：打通 API 会话与统一观测

目标：

- API 无状态与有状态模式
- UI/API 会话统一接入
- 前端可选择查看 API 会话
- 与模型调用日志打通

---

## 14. 最终建议结论

### 14.1 是否要存 API 聊天记录

最佳实践不是“全存”或“全不存”，而是：

- UI 默认存
- API 默认不存正文，只存日志
- API 支持显式持久化为正式会话

### 14.2 是否要让 API 先创建会话

最佳实践不是强制，而是：

- 支持先创建会话
- 也支持在首次调用时自动创建会话
- 还支持完全无状态调用

### 14.3 当前数据库设计最大的结构性改动点

最重要的三点：

- 单 `kb_id` 改为会话与知识库多对多
- 聊天会话数据与执行过程数据分层
- API 调用引入 `channel + visibility + persistence_mode`

### 14.4 当前原型最大的产品层优化点

最重要的三点：

- 参数面板需要从“少量滑块”升级为“预设 + 高级参数”
- `Search Depth (K)` 要拆成更明确的检索阶段参数
- `Re-index Sources` 应迁出聊天会话页面

---

## 15. 后续实施建议

下一步建议基于本文继续产出两份落地稿：

1. 聊天模块数据库迁移方案
2. 聊天模块接口定义与前端字段映射方案

建议顺序：

1. 先定领域模型与表结构
2. 再定 API 契约
3. 最后让前端页面字段与后端实体一一对齐

这样后续改动最少，整体也最稳。

---

## 16. Assistant、Agent、Workflow、Tool、MCP、Skill 的统一设计

这一部分用于回答一个更关键的问题：

- 聊天是否只是挂知识库
- 智能体应该怎么和聊天整合
- 工作流是否也应该有自己的会话
- Tool、MCP、Skill 应该挂在聊天上，还是挂在 Agent 上

结论先行：

- 不建议把聊天、Agent、Workflow 设计成三套彼此分裂的系统
- 也不建议把 Agent 简单等价为一个工具
- 最佳实践是：统一会话模型、统一能力绑定模型、统一执行快照模型

### 16.1 推荐的产品抽象顺序

建议从产品视角到执行视角分三层理解：

1. 用户入口层：Assistant
2. 推理决策层：Agent
3. 流程编排层：Workflow

对应含义：

- `Assistant` 是用户真正看到和选择的聊天对象
- `Agent` 是具备自主决策、可调用多种能力的执行体
- `Workflow` 是可编排、可复用、可观测的流程

因此，推荐的产品设计不是“让用户直接面对底层 Agent 组件”，而是：

- 用户创建或进入一个 `Assistant`
- `Assistant` 后面可以是普通 LLM 模式，也可以是 Agent 模式
- 当任务复杂时，由 Agent 决定是否调用 Workflow

这比“聊天直接挂 Agent、Workflow、工具、知识库的一堆配置”更符合大多数产品的认知路径。

### 16.2 对几个核心概念的推荐定义

#### A. Assistant

建议定义为：

- 一个面向聊天交互的能力入口
- 对用户暴露名称、头像、描述、默认风格
- 维护默认模型、默认系统提示词、默认知识库、默认工具集
- 可以配置其底层执行模式为 `llm` 或 `agent`

适用场景：

- 财务助手
- 法务助手
- 研发助手
- 客服助手
- 报告生成助手

#### B. Agent

建议定义为：

- 一个面向推理和动作决策的执行实体
- 能决定本轮是否检索知识库、是否调用工具、是否调用 MCP、是否转给 Workflow
- 能管理自己的策略和能力使用顺序

关键判断：

- Agent 不是一个普通工具
- Agent 更像“会规划的执行器”
- 它可以被 Assistant 使用，也可以在内部调用其他能力

#### C. Workflow

建议定义为：

- 一个显式编排的流程定义
- 更强调确定性步骤、节点关系、输入输出和可观测性
- 可作为 Agent 的子能力，也可以直接作为一个聊天入口

典型场景：

- 合同审查流程
- 报告生成流程
- 多系统数据处理流程
- 多阶段审批或分析流程

#### D. Tool

建议定义为：

- 单一能力单元
- 输入明确、输出明确
- 不承担复杂会话管理和多轮决策

例如：

- 汇率查询
- 数据库查询
- 文件解析
- 发邮件
- 调用企业内部 API

#### E. MCP

建议定义为：

- 一类外部能力接入协议或能力容器
- 可通过 Server 暴露工具、资源、提示词模板等
- 在平台内部应归入“能力来源”或“工具提供者”

因此，不建议把 MCP 单独当成一种和 Tool 平级的终端执行对象，而更建议把它看作：

- Tool 的来源
- Resource 的来源
- Prompt/Skill 的来源

#### F. Skill

建议定义为：

- 一组特定任务的执行策略、约束和知识模板
- 更偏“方法论资产”而非直接执行器
- 可以作用于 Assistant，也可以作用于 Agent

例如：

- “财报分析技能”
- “合同审查技能”
- “结构化摘要技能”

Skill 更像“能力配方”或“任务模板”，不是底层的 RPC 工具。

### 16.3 行业里更通用的关系模型

推荐关系如下：

- `Assistant` 绑定：
  - 默认模型
  - 默认知识库
  - 默认工具
  - 默认搜索
  - 默认 MCP 来源
  - 默认 Skills
  - 可选默认 Workflow
  - 可选底层 Agent

- `Agent` 绑定：
  - 可用工具集
  - 可用 MCP Server
  - 可用 Workflow
  - 推理策略
  - 检索策略

- `Workflow` 绑定：
  - 节点
  - 节点间连线
  - 每个节点可能调用模型、工具、检索或子流程

所以更推荐的系统心智模型是：

- 用户主要和 `Assistant` 交互
- `Assistant` 在内部决定是否走简单聊天模式还是 Agent 模式
- `Agent` 负责复杂决策
- `Workflow` 负责复杂流程编排

### 16.4 为什么不建议“把 Agent 仅仅当成一个工具”

如果把 Agent 当成工具，会有几个问题：

- 工具的输入输出通常是单步、确定性的
- Agent 往往需要看上下文、做决策、迭代调用多个能力
- Agent 经常需要自己的执行日志、状态和中间过程

所以从工程和产品角度，Agent 更合适被设计为：

- 一种执行模式
- 或一种高级入口能力

而不是普通的工具记录。

### 16.5 为什么 Workflow 也不应单独搞一套会话模型

很多系统会走到一个坑里：

- 聊天有一套会话
- 工作流又单独有一套会话
- Agent 再有一套运行日志

最后三套数据割裂。

更好的做法是：

- 统一用 `chat_sessions` 承载所有“用户可连续交互”的入口
- 通过 `entrypoint_type` 和 `entrypoint_id` 区分入口是谁

推荐字段：

- `entrypoint_type`: `assistant | agent | workflow`
- `entrypoint_id`

这样：

- 普通助手会话：`entrypoint_type=assistant`
- 直接面向某个 Agent 的会话：`entrypoint_type=agent`
- 直接面向某个 Workflow 的会话：`entrypoint_type=workflow`

统一后，前端、权限、审计、搜索、归档、分享都可以复用同一套机制。

---

## 17. 工作流与聊天共存时的推荐模式

### 17.1 `workflow_as_tool`

含义：

- Workflow 被 Assistant 或 Agent 当成一个能力节点调用
- 用户主视角仍然是聊天
- 工作流执行是某个 `turn` 内的子过程

这种模式下：

- 仍属于原聊天会话
- Workflow 运行记录写到执行层
- 用户看到的是“本轮调用了某个流程”

适用于：

- 聊天中触发“生成报告”
- 聊天中触发“批量审查文档”
- 聊天中触发“跨系统同步”

### 17.2 `workflow_as_entrypoint`

含义：

- Workflow 本身是一个对外可聊天的入口
- 用户其实是在和一个“流程型助手”对话

这种模式下：

- 依然使用统一 `chat_session`
- 只是 `entrypoint_type=workflow`
- 后台每一轮根据当前上下文驱动流程推进

适用于：

- 合同审查助手
- 报销审核助手
- 报告撰写助手
- 引导式数据采集助手

### 17.3 推荐结论

不要单独为 Workflow 新建另一套“工作流会话”主模型。

最佳实践是：

- 统一会话模型
- 区分入口类型
- 执行轨迹中记录 Workflow 的运行实例

---

## 18. 检索、知识图谱、搜索与工具的配置挂载建议

### 18.1 不建议把所有能力字段直接挂到聊天会话主表

如果直接在 `chat_sessions` 上新增大量字段，例如：

- `kb_ids`
- `tool_ids`
- `workflow_ids`
- `mcp_server_ids`
- `enable_graph`
- `enable_search`
- `rewrite_query`

短期快，长期会非常难维护。

更好的方式是：

- 会话主表只保留核心元数据
- 能力挂载通过关联表完成
- 运行时再形成快照

### 18.2 推荐能力绑定模型

建议新增统一能力绑定表，例如：

- `assistant_capabilities`
- `agent_capabilities`
- `chat_session_capabilities`

公共字段建议：

- `id`
- `tenant_id`
- `owner_type`
- `owner_id`
- `capability_type`
- `capability_id`
- `is_enabled`
- `priority`
- `config`
- `created_at`
- `updated_at`

建议枚举：

- `owner_type`: `assistant | agent | session`
- `capability_type`: `knowledge_base | tool | search_provider | mcp_server | workflow | skill`

关键好处：

- 能统一表达各种挂载关系
- 能按优先级排序
- 能保存局部覆盖配置
- 能适应以后继续新增能力类型

### 18.3 检索配置的最佳挂载位置

检索配置通常需要分三层：

#### A. 知识库默认配置

放在 `knowledge_bases.retrieval_config`

用于表达这个知识库的默认检索特征，例如：

- 默认 `top_k`
- 默认相似度阈值
- 默认是否启用 rerank
- 默认是否启用图谱扩展

#### B. Assistant / Agent / Session 默认配置

用于表达当前入口默认的检索偏好，例如：

- 是否启用多轮改写
- 多知识库权重分配
- 是否允许网络搜索参与混合召回
- 是否允许图谱扩展

#### C. Turn 级真实执行配置

最终生效参数必须写入 `chat_turns.effective_config`

包括：

- 是否执行多轮对话改写
- 改写后的 query
- 使用了哪些知识源
- 每个知识源的权重
- 相似度阈值
- 图谱开关
- rerank 开关
- 最终上下文条数

### 18.4 你提到的几个配置，推荐归位如下

#### 多轮对话改写

建议：

- 默认策略配置挂在 `Assistant / Agent / Session`
- 实际是否触发、改写结果挂在 `Turn`

#### 相似度

建议：

- 默认阈值可挂知识库或 Session
- 实际阈值和召回结果必须落到 `Turn`

#### 权重

建议：

- 多知识库权重属于 Session 或 Assistant 默认配置
- 本轮动态调整后的权重写入 `effective_config`

#### 知识图谱开关

建议：

- 不应直接写死在知识库主表单字段里
- 应作为一种可选检索能力配置
- 最终是否启用写入 Turn 快照

#### 搜索能力

建议：

- 搜索应视为一种能力源
- 可以是 `search_provider`
- 可以参与混合检索，而不是与知识库平级散落在各处

---

## 19. 推荐新增的领域实体

为了更完整地支持未来能力扩展，建议在领域模型上增加以下实体。

### 19.1 `assistants`

建议用途：

- 作为用户入口对象
- 承担对外展示与默认配置组合

建议字段：

- `id`
- `tenant_id`
- `name`
- `description`
- `avatar_url`
- `execution_mode`
- `default_agent_id`
- `default_model_id`
- `system_prompt`
- `default_config`
- `status`
- `visibility`
- `created_at`
- `updated_at`

建议枚举：

- `execution_mode`: `llm | agent | workflow_router`

### 19.2 `agents`

建议用途：

- 存储智能体策略、约束与能力组合

建议字段：

- `id`
- `tenant_id`
- `name`
- `description`
- `planning_mode`
- `policy_config`
- `default_model_id`
- `default_config`
- `status`
- `created_at`
- `updated_at`

### 19.3 `workflows`

建议用途：

- 存储工作流定义

建议字段：

- `id`
- `tenant_id`
- `name`
- `description`
- `workflow_type`
- `definition`
- `input_schema`
- `output_schema`
- `status`
- `created_at`
- `updated_at`

### 19.4 `tools`

建议用途：

- 存储平台内注册工具

建议字段：

- `id`
- `tenant_id`
- `name`
- `description`
- `tool_type`
- `provider_type`
- `input_schema`
- `output_schema`
- `auth_config`
- `status`
- `created_at`
- `updated_at`

### 19.5 `mcp_servers`

建议用途：

- 存储 MCP 服务接入配置

建议字段：

- `id`
- `tenant_id`
- `name`
- `description`
- `server_url`
- `transport_type`
- `auth_config`
- `capability_manifest`
- `status`
- `created_at`
- `updated_at`

### 19.6 `skills`

建议用途：

- 存储技能模板、约束、执行指令集

建议字段：

- `id`
- `tenant_id`
- `name`
- `description`
- `skill_type`
- `instruction_template`
- `input_schema`
- `status`
- `created_at`
- `updated_at`

---

## 20. 推荐执行链路

未来聊天链路建议统一为下面的模式：

1. 用户进入一个 `Assistant / Agent / Workflow` 入口
2. 创建或进入统一 `chat_session`
3. 用户发送消息，生成 `chat_message`
4. 系统创建一条 `chat_turn`
5. 根据入口类型和默认配置，装配本轮能力上下文
6. 判断本轮是：
   - 纯 LLM
   - RAG
   - Agent 决策
   - Workflow 驱动
7. 执行过程中记录：
   - query rewrite
   - retrieval
   - rerank
   - tool call
   - workflow run
   - model invocation
8. 生成助手消息与引用
9. 将真实执行结果写回 `chat_turn`

这样无论未来增加：

- Web Search
- MCP
- Skills
- 多 Agent 编排
- Workflow 编排

都不用推翻会话主模型。

---

## 21. 这一部分的最终结论

### 21.1 智能体应该直接挂在聊天中吗

推荐答案：

- 面向用户可以“挂载”或“选择”智能体
- 但内部不要把 Agent 仅仅当成聊天页面的一组附加字段
- 更应该把 Agent 看成聊天入口背后的执行模式或执行实体

### 21.2 工作流要不要有会话

推荐答案：

- 需要支持会话语义
- 但不应单独搞另一套主会话模型
- 应复用统一 `chat_session`

### 21.3 行业更通用的做法是什么

更通用、更稳的做法是：

- 用 `Assistant` 做用户入口
- 用 `Agent` 做复杂执行
- 用 `Workflow` 做流程编排
- 用统一会话模型承载所有连续交互
- 用统一能力绑定模型管理 KB、Tool、Search、MCP、Skill、Workflow
- 用统一执行快照模型记录每一轮真实发生了什么

### 21.4 对本项目的直接建议

本项目后续设计建议优先级如下：

1. 先引入 `assistants`
2. 再定义 `agents`
3. 再补 `workflows`
4. 用统一能力绑定表承载多种能力
5. 保证 `chat_session / chat_turn` 不因能力增长而反复改表

这样未来从“知识库聊天”升级到“智能体平台”时，架构是连续演进的，而不是推倒重来。

---

## 22. 关于“智能体平台”和 Dify 式工作流编排的关系

这一部分用于回答一个容易混淆的问题：

- 智能体平台和 Dify 这类拖拽编排平台是不是同一个东西
- 如果后续已经要做工作流编排，是不是就不需要再考虑智能体平台

先给结论：

- 它们不是完全相同的东西
- 但边界会重叠，而且在产品演进上经常逐步靠近
- 对本项目而言，当前更应该优先建设的是：
  - 知识库平台
  - 聊天入口
  - 工作流编排能力
- 智能体平台可以作为后续在“复杂决策、自主规划、多 Agent 协作”方向上的增强层

### 22.1 三者的核心差异

#### A. 知识库平台

核心目标是：

- 管理知识资产
- 管理文档解析、分块、索引、检索
- 为聊天、搜索、工作流、Agent 提供知识能力

其本质是“知识底座”。

关注重点通常是：

- 知识库管理
- 文档处理链路
- 检索效果
- 引用与溯源
- 权限和共享

#### B. 工作流编排平台

核心目标是：

- 把一个任务拆成若干节点和连线
- 明确输入、输出和执行顺序
- 让流程可视化、可调试、可复用

其本质是“流程编排底座”。

关注重点通常是：

- 节点定义
- 节点连线
- 条件分支
- 变量传递
- 运行日志
- 重试和可观测性

典型代表就是 Dify、Coze 里那种：

- LLM 节点
- 检索节点
- HTTP 节点
- 代码节点
- 工具节点
- 条件判断节点

#### C. 智能体平台

核心目标是：

- 让系统具备一定的自主决策能力
- 能根据任务目标动态选择工具、知识源、子流程
- 在不完全预先写死路径的情况下完成复杂任务

其本质是“动态决策与自主执行底座”。

关注重点通常是：

- 任务规划
- 工具选择
- 多步执行
- 自我反思或纠错
- 记忆
- 多 Agent 协作

### 22.2 Dify 式编排和 Agent 的真正区别

最核心的区别在于：执行路径是否主要由人预先编排。

#### 工作流编排

特点：

- 流程路径大部分是人定义好的
- 节点和节点之间的关系较稳定
- 即使有条件分支，也通常仍在预设边界内
- 重点是可控、可视化、好调试

一句话理解：

- 人告诉系统“按这个流程做”

#### 智能体

特点：

- 路径不是完全预先写死
- 系统需要自己判断下一步该做什么
- 可能动态决定：
  - 要不要检索
  - 检索哪个知识库
  - 要不要调用工具
  - 要不要调用 MCP
  - 要不要转子工作流
  - 失败后是否换一种策略

一句话理解：

- 人告诉系统“帮我完成目标”，系统自己规划过程

### 22.3 为什么会让人觉得“工作流平台也能做智能体”

因为现代工作流平台已经越来越强，确实能覆盖一部分 Agent 场景。

比如在工作流里加上：

- LLM 决策节点
- 条件分支
- 工具节点
- 循环节点
- 记忆节点

那么它看起来已经很像一个智能体了。

所以现实里常见两种情况：

#### 情况 A：工作流平台中内嵌 Agent 能力

即：

- 工作流是骨架
- 某些节点内部用 Agent 决策

这种方式优点是：

- 可观测性好
- 流程边界清晰
- 更适合企业场景

#### 情况 B：智能体平台中把 Workflow 当成工具

即：

- Agent 是主控制器
- 复杂稳定步骤交给 Workflow 执行

这种方式优点是：

- 自主性更强
- 更适合开放任务

因此，两者不是互斥关系，而是可以互相嵌套。

### 22.4 对你当前项目，应该怎么判断优先级

结合你当前的真实情况：

- 现在主要是知识库
- 后续明确会有类似 Dify 的拖拽编排
- “智能体平台”还只是潜在方向，尚未清晰

那么更合适的产品路线是：

#### 第一阶段：知识库平台

重点建设：

- 知识库管理
- 解析与检索配置
- 聊天问答
- 引用与溯源
- API 能力

#### 第二阶段：工作流编排平台

重点建设：

- 节点化编排
- 模型节点
- 检索节点
- 工具节点
- MCP 节点
- 条件与循环
- 工作流运行记录

这一阶段已经可以覆盖大量“企业智能体”诉求。

#### 第三阶段：智能体能力增强

当后续你真的出现以下需求时，再正式抽象“智能体平台”会更合适：

- 任务目标输入，不想预先画完整流程
- 需要自主规划
- 需要多 Agent 分工协作
- 需要长期记忆
- 需要复杂任务反思与重试

也就是说：

- 不是现在就必须单独重建一个“智能体平台”
- 但当前架构要为它预留空间

### 22.5 行业更通用的演进路径

很多产品的实际演进顺序通常不是：

- 先做一个纯 Agent 平台

而是：

1. 先做知识库问答
2. 再做助手配置
3. 再做工作流编排
4. 再在工作流中引入更强的动态决策节点
5. 最后才逐步形成真正的智能体平台

这条路径更符合企业产品落地，因为：

- 知识库问答最容易形成价值闭环
- 工作流编排比完全自主 Agent 更可控
- 企业更容易接受可解释、可观测、可审批的流程

### 22.6 对本项目最务实的架构建议

对当前项目，推荐采用下面的统一设计思路。

#### 产品层

主对外概念先以以下为主：

- 知识库
- 助手
- 工作流

先不要急着把“智能体平台”作为一级产品模块做重。

#### 引擎层

内部执行模式预留三种：

- `retrieval_chat`
- `workflow`
- `agent`

这样：

- 当前主流场景走 `retrieval_chat`
- 后续拖拽编排走 `workflow`
- 未来复杂自主执行走 `agent`

#### 数据层

统一保留：

- `entrypoint_type`
- `execution_mode`
- `chat_turns`
- `workflow_runs`
- `tool_calls`

这样以后从知识库聊天扩展到工作流聊天、Agent 聊天时，不需要重建会话主模型。

### 22.7 一个更容易落地的理解方式

可以把三者理解为：

- 知识库平台：提供“知道什么”
- 工作流平台：提供“按什么流程做”
- 智能体平台：提供“自己决定怎么做”

这三者不是替代关系，而是能力层次不同。

### 22.8 对“是不是同一个东西”的最终回答

严格来说，不是同一个东西。

但从系统建设顺序和产品演进上看：

- 工作流平台常常是智能体平台的前置阶段
- 智能体平台也常常复用工作流平台的执行能力

所以对本项目最合理的判断是：

- 现在先把“知识库平台 + 聊天 + 工作流编排”打扎实
- 数据模型和执行模型为 `agent` 预留扩展点
- 等真正出现“自主规划、多 Agent 协作、开放任务执行”需求时，再把智能体平台独立强化

这会比现在就把“智能体平台”做成一个过重的一级模块更稳。

---

## 23. 聊天与未来能力兼容的正式表结构设计草案

本节给出一版面向正式落地的推荐表结构。

设计目标：

- 当前优先满足知识库聊天
- 原生支持多知识库、多轮改写、检索参数配置
- 兼容未来的工作流聊天、Agent 聊天、工具调用、MCP、Skills
- 避免未来因能力增加而推翻会话主模型
- 保持关键链路结构化，避免全部堆进 JSONB

### 23.1 设计总原则

正式表结构建议遵循以下原则：

1. `Session` 只表达“连续交互容器”，不表达具体执行细节
2. `Turn` 表达“一轮请求的真实执行快照”
3. `Capability Binding` 统一承载知识库、工具、Workflow、MCP、Skill 等挂载关系
4. `Workflow / Agent / Tool` 运行日志与消息流解耦
5. 关键查询字段结构化，低频扩展字段使用 JSONB
6. UI 与 API 共用一套会话模型，通过渠道和可见性区分

---

## 24. 推荐核心表

### 24.1 `chat_sessions`

用途：

- 聊天会话主表
- 所有“可连续交互”的入口统一落在这里

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `owner_id UUID NOT NULL`
- `entrypoint_type VARCHAR(32) NOT NULL`
- `entrypoint_id UUID`
- `session_type VARCHAR(32) NOT NULL`
- `channel VARCHAR(32) NOT NULL`
- `visibility VARCHAR(32) NOT NULL DEFAULT 'user_visible'`
- `persistence_mode VARCHAR(32) NOT NULL DEFAULT 'persistent'`
- `title VARCHAR(255)`
- `summary TEXT`
- `status VARCHAR(32) NOT NULL DEFAULT 'active'`
- `default_assistant_id UUID`
- `default_agent_id UUID`
- `default_model_id UUID`
- `default_retrieval_profile_id UUID`
- `default_system_prompt TEXT`
- `default_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `last_message_at TIMESTAMPTZ`
- `archived_at TIMESTAMPTZ`
- `deleted_at TIMESTAMPTZ`
- `created_by_id UUID`
- `updated_by_id UUID`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `entrypoint_type`: `assistant | workflow | agent`
- `session_type`: `retrieval_chat | workflow_chat | agent_chat`
- `channel`: `ui | api | system`
- `visibility`: `user_visible | backend_only`
- `persistence_mode`: `persistent | ephemeral`
- `status`: `active | archived | deleted`

最佳实践说明：

- `entrypoint_type + entrypoint_id` 是未来兼容性的关键
- 不建议继续只用单个 `kb_id`
- `default_config` 用于会话默认配置，不用于记录每轮真实执行

推荐索引：

- `(tenant_id, owner_id, status, updated_at DESC)`
- `(tenant_id, channel, visibility, updated_at DESC)`
- `(tenant_id, last_message_at DESC)`

### 24.2 `chat_session_stats`

用途：

- 存放会话级聚合统计，避免频繁扫消息表

建议字段：

- `session_id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `message_count INT NOT NULL DEFAULT 0`
- `turn_count INT NOT NULL DEFAULT 0`
- `user_message_count INT NOT NULL DEFAULT 0`
- `assistant_message_count INT NOT NULL DEFAULT 0`
- `tool_call_count INT NOT NULL DEFAULT 0`
- `workflow_run_count INT NOT NULL DEFAULT 0`
- `total_input_tokens BIGINT NOT NULL DEFAULT 0`
- `total_output_tokens BIGINT NOT NULL DEFAULT 0`
- `total_tokens BIGINT NOT NULL DEFAULT 0`
- `last_model_id UUID`
- `last_turn_status VARCHAR(32)`
- `last_feedback_at TIMESTAMPTZ`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

最佳实践说明：

- 类似 Yuxi 的会话统计思路可直接借鉴
- 统计类字段单独表维护，比每次聚合消息更稳

### 24.3 `chat_messages`

用途：

- 存消息流
- 支持用户消息、助手消息、工具结果消息、系统事件消息

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID`
- `parent_message_id UUID`
- `replaces_message_id UUID`
- `role VARCHAR(32) NOT NULL`
- `message_type VARCHAR(32) NOT NULL DEFAULT 'text'`
- `status VARCHAR(32) NOT NULL DEFAULT 'completed'`
- `source_channel VARCHAR(32) NOT NULL`
- `content TEXT`
- `content_blocks JSONB NOT NULL DEFAULT '[]'::jsonb`
- `display_content TEXT`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `is_visible BOOLEAN NOT NULL DEFAULT TRUE`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `user_id UUID`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `role`: `system | user | assistant | tool`
- `message_type`: `text | event | tool_call | tool_result | workflow_event | file | citation_card`
- `status`: `pending | streaming | completed | failed | cancelled`
- `source_channel`: `ui | api | system`

最佳实践说明：

- 不建议继续用 `BIGSERIAL`
- UUID 更适合分布式系统、流式链路和前后端统一引用
- `content_blocks` 是对未来富文本、多模态、节点输出的必要预留
- `replaces_message_id` 用于支持中断重试、重新生成

推荐索引：

- `(session_id, created_at)`
- `(tenant_id, session_id, created_at)`
- `(turn_id)`

### 24.4 `chat_message_citations`

用途：

- 结构化存储助手消息引用

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID`
- `message_id UUID NOT NULL`
- `citation_index INT NOT NULL`
- `kb_id UUID`
- `kb_doc_id UUID`
- `chunk_id BIGINT`
- `source_anchor TEXT`
- `page_number INT`
- `snippet TEXT`
- `score DOUBLE PRECISION`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

最佳实践说明：

- 不建议只把引用塞在消息 JSON 中
- 结构化后更适合做前端引用跳转、评测和统计

推荐索引：

- `(message_id, citation_index)`
- `(turn_id)`
- `(tenant_id, kb_id, created_at DESC)`

### 24.5 `chat_turns`

用途：

- 一轮问答的真实执行快照
- 是整个聊天链路的核心表

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `request_id UUID NOT NULL`
- `channel VARCHAR(32) NOT NULL`
- `execution_mode VARCHAR(32) NOT NULL`
- `entrypoint_type VARCHAR(32) NOT NULL`
- `entrypoint_id UUID`
- `user_message_id UUID`
- `assistant_message_id UUID`
- `status VARCHAR(32) NOT NULL`
- `effective_model_id UUID`
- `effective_agent_id UUID`
- `effective_retrieval_profile_id UUID`
- `effective_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `effective_capabilities JSONB NOT NULL DEFAULT '[]'::jsonb`
- `rewrite_query TEXT`
- `final_query TEXT`
- `prompt_tokens INT`
- `completion_tokens INT`
- `total_tokens INT`
- `latency_ms INT`
- `started_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `debug_summary JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `execution_mode`: `retrieval_chat | workflow | agent`
- `status`: `queued | running | completed | failed | cancelled`

最佳实践说明：

- `effective_config` 是最关键字段之一，必须记录本轮真实生效参数
- `effective_capabilities` 可作为轻量快照，明细则落到子表
- `request_id` 应与模型调用日志、工具调用日志、工作流运行日志统一串联

推荐索引：

- `(session_id, created_at DESC)`
- `(tenant_id, request_id)`
- `(tenant_id, status, created_at DESC)`

---

## 25. 推荐能力绑定表

### 25.1 `chat_capability_bindings`

用途：

- 为 Session 统一挂载知识库、工具、搜索、MCP、Workflow、Skill

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `capability_type VARCHAR(32) NOT NULL`
- `capability_id UUID NOT NULL`
- `binding_role VARCHAR(32) NOT NULL DEFAULT 'default'`
- `is_enabled BOOLEAN NOT NULL DEFAULT TRUE`
- `priority INT NOT NULL DEFAULT 100`
- `config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `capability_type`: `knowledge_base | tool | search_provider | mcp_server | workflow | skill`
- `binding_role`: `default | primary | secondary | optional`

最佳实践说明：

- 未来能力增长时，不改 `chat_sessions` 主表
- 局部覆盖配置放在 `config`
- `priority` 用于多能力排序和默认选择

推荐索引：

- `(session_id, capability_type, priority)`
- `(tenant_id, capability_type, capability_id)`

### 25.2 `assistant_capability_bindings`

用途：

- 为 Assistant 绑定默认能力

说明：

- 字段结构与 `chat_capability_bindings` 基本一致
- 区别仅在 `owner_id` 指向 `assistant_id`

最佳实践说明：

- Assistant 是对外入口时，能力默认应先挂在 Assistant 上
- Session 仅在运行中做局部覆盖和动态增减

### 25.3 `agent_capability_bindings`

用途：

- 为 Agent 绑定可用能力集

最佳实践说明：

- Agent 的能力绑定更强调“允许使用哪些能力”
- Session 的能力绑定更强调“当前会话实际启用了哪些能力”

---

## 26. 推荐执行明细表

### 26.1 `chat_turn_retrievals`

用途：

- 存一轮问答的召回明细

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID NOT NULL`
- `retrieval_source_type VARCHAR(32) NOT NULL`
- `retrieval_source_id UUID`
- `kb_id UUID`
- `kb_doc_id UUID`
- `chunk_id BIGINT`
- `retrieval_stage VARCHAR(32) NOT NULL`
- `raw_score DOUBLE PRECISION`
- `rerank_score DOUBLE PRECISION`
- `final_score DOUBLE PRECISION`
- `rank_index INT`
- `selected_for_context BOOLEAN NOT NULL DEFAULT FALSE`
- `selected_for_citation BOOLEAN NOT NULL DEFAULT FALSE`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `retrieval_source_type`: `knowledge_base | web_search | graph | workflow_memory`
- `retrieval_stage`: `rewrite | recall | rerank | final_context`

最佳实践说明：

- 支持未来知识库、网络搜索、图谱、工作流记忆等统一纳入召回
- 能支撑检索分析、评测和可观测性

### 26.2 `chat_turn_tool_calls`

用途：

- 存一轮问答中所有工具调用明细

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID NOT NULL`
- `message_id UUID`
- `tool_type VARCHAR(32) NOT NULL`
- `tool_id UUID`
- `tool_name VARCHAR(255) NOT NULL`
- `provider_type VARCHAR(32)`
- `provider_ref_id UUID`
- `call_index INT NOT NULL DEFAULT 1`
- `status VARCHAR(32) NOT NULL`
- `input_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `output_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `latency_ms INT`
- `started_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `tool_type`: `builtin | external_api | mcp_tool | workflow_tool | skill_tool`
- `status`: `pending | running | completed | failed | cancelled`

最佳实践说明：

- 借鉴 Yuxi 将 ToolCall 与消息拆表
- 未来 MCP、Workflow 作为工具调用时也可复用

### 26.3 `chat_turn_workflow_runs`

用途：

- 记录某一轮中触发的 Workflow 执行

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID NOT NULL`
- `workflow_id UUID NOT NULL`
- `workflow_version_id UUID`
- `trigger_source VARCHAR(32) NOT NULL`
- `run_status VARCHAR(32) NOT NULL`
- `input_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `output_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `run_summary JSONB NOT NULL DEFAULT '{}'::jsonb`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `started_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `trigger_source`: `session_entrypoint | agent_decision | tool_call`
- `run_status`: `queued | running | completed | failed | cancelled`

最佳实践说明：

- 借鉴 Coze 的 `run_record` 思路
- Workflow 运行日志不应只写进消息 JSON

### 26.4 `chat_turn_agent_runs`

用途：

- 为未来 Agent 规划、多 Agent 协作预留运行层

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID NOT NULL`
- `agent_id UUID NOT NULL`
- `parent_agent_run_id UUID`
- `run_role VARCHAR(32) NOT NULL DEFAULT 'primary'`
- `status VARCHAR(32) NOT NULL`
- `planning_summary JSONB NOT NULL DEFAULT '{}'::jsonb`
- `memory_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `started_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `run_role`: `primary | delegated | collaborator`
- `status`: `queued | running | completed | failed | cancelled`

最佳实践说明：

- 当前未必立即启用
- 但建议现在就把接口位置和表位预留清楚

---

## 27. 推荐入口与能力定义表

### 27.1 `assistants`

用途：

- 面向用户的主入口对象

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `description TEXT`
- `avatar_url VARCHAR(512)`
- `execution_mode VARCHAR(32) NOT NULL DEFAULT 'retrieval_chat'`
- `default_agent_id UUID`
- `default_model_id UUID`
- `default_retrieval_profile_id UUID`
- `system_prompt TEXT`
- `default_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `status VARCHAR(32) NOT NULL DEFAULT 'active'`
- `visibility VARCHAR(32) NOT NULL DEFAULT 'private'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `execution_mode`: `retrieval_chat | workflow | agent`
- `visibility`: `private | tenant_public`
- `status`: `active | disabled | archived`

最佳实践说明：

- 当前阶段优先以 Assistant 为用户入口
- 工作流和 Agent 可先作为内部执行模式，不一定急于成为一级 UI 概念

### 27.2 `retrieval_profiles`

用途：

- 抽象检索配置模板，供 Assistant、Session、Workflow 节点复用

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `description TEXT`
- `profile_scope VARCHAR(32) NOT NULL`
- `config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `status VARCHAR(32) NOT NULL DEFAULT 'active'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `profile_scope`: `assistant_default | session_default | workflow_node | evaluation`
- `status`: `active | archived`

最佳实践说明：

- 比把检索参数散落在 KB / Session / Assistant 各处更清晰
- 与 RAGFlow 独立 `search` 实体思路一致

### 27.3 `workflows`

用途：

- 存工作流定义

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `description TEXT`
- `workflow_type VARCHAR(32) NOT NULL DEFAULT 'chat_flow'`
- `definition JSONB NOT NULL DEFAULT '{}'::jsonb`
- `input_schema JSONB NOT NULL DEFAULT '{}'::jsonb`
- `output_schema JSONB NOT NULL DEFAULT '{}'::jsonb`
- `status VARCHAR(32) NOT NULL DEFAULT 'draft'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `workflow_type`: `chat_flow | task_flow | tool_flow`
- `status`: `draft | active | archived`

### 27.4 `agents`

用途：

- 未来智能体策略与执行模型定义

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `description TEXT`
- `planning_mode VARCHAR(32) NOT NULL DEFAULT 'react'`
- `default_model_id UUID`
- `policy_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `memory_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `default_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `status VARCHAR(32) NOT NULL DEFAULT 'draft'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

最佳实践说明：

- 即使当前阶段不重点建设 Agent 平台，也应预留实体
- 但 UI 上可先弱化，不必和 Workflow 并列做重

---

## 28. 参数归属最佳实践

### 28.1 参数归属优先级

推荐优先级如下：

1. 租户默认
2. Knowledge Base 默认
3. Retrieval Profile 默认
4. Assistant 默认
5. Session 默认
6. Turn 覆盖

最终结果统一写入：

- `chat_turns.effective_config`

### 28.2 你当前最需要结构化的检索参数

建议在 `retrieval_profiles.config` 与 `chat_turns.effective_config` 中统一表达：

- `query_rewrite_enabled`
- `rewrite_strategy`
- `recall_top_k`
- `rerank_top_k`
- `final_context_k`
- `similarity_threshold`
- `keyword_threshold`
- `vector_weight`
- `keyword_weight`
- `enable_hybrid_search`
- `enable_rerank`
- `rerank_model_id`
- `enable_knowledge_graph`
- `graph_hops`
- `enable_web_search`
- `enable_related_search`
- `source_weights`
- `empty_response_strategy`

最佳实践说明：

- 不建议把这些都做成单独列
- 也不建议只放在 Session 主表
- 最适合的是“配置模板 + 执行快照”双层模式

---

## 29. 最佳实践下的最终推荐

如果只给一版最核心、最稳的推荐，那么是：

### 当前阶段必须落地

- `chat_sessions`
- `chat_session_stats`
- `chat_messages`
- `chat_message_citations`
- `chat_turns`
- `chat_capability_bindings`
- `chat_turn_retrievals`
- `chat_turn_tool_calls`
- `chat_turn_workflow_runs`
- `assistants`
- `retrieval_profiles`
- `workflows`

### 当前阶段可以先弱化但应预留

- `agents`
- `agent_capability_bindings`
- `chat_turn_agent_runs`

### 不建议的做法

- 把未来所有能力字段硬塞进 `conversations`
- 继续用单 `kb_id` 表达聊天知识源
- 把工具调用、工作流运行、引用都只存进消息 JSONB
- 让 API、UI、Workflow 各做一套独立会话模型

### 最符合你当前项目阶段的路径

1. 先把知识库聊天和检索配置打稳
2. 用统一会话模型承载当前聊天
3. 用 Workflow 表和运行表承接未来 Dify 式编排
4. Agent 相关先预留，不急于做重
5. 等出现真正的自主规划、多 Agent 协作需求时，再把 Agent 层强化

这样是当前阶段最符合最佳实践、同时也最贴合你项目节奏的一条路线。

---

## 30. V2 正式定稿模型

本节是本文最终采用的正式模型，用于覆盖前文分析过程中出现的单层 `chat_sessions` 讨论。

正式定稿采用四层结构：

- `chat_spaces`
- `chat_sessions`
- `chat_messages`
- `chat_turns`

关系如下：

- 一个 `chat_space` 下有多个 `chat_sessions`
- 一个 `chat_session` 下有多条 `chat_messages`
- 一个 `chat_session` 下有多次 `chat_turns`
- 一次 `chat_turn` 可关联多条引用、检索记录、工具调用、工作流运行

### 30.1 为什么必须是两层而不是一层

结合当前原型：

- 聊天首页卡片页更像“聊天集合 / 聊天入口 / 聊天工作台”
- 进入卡片后，左侧 Recent Chats 才是具体会话列表
- 当前中间打开的是某条具体会话

所以最符合产品心智的结构是：

- 首页卡片 = `chat_spaces`
- 进入后的左侧会话列表 = `chat_sessions`
- 会话中的消息 = `chat_messages`

这与 RAGFlow 的 `Dialog -> Conversation` 两层模型更接近，也更符合你当前原型。

### 30.2 `chat_spaces`：聊天空间主表

这是正式的一层主容器。

用途：

- 对应聊天首页卡片
- 对应一个长期存在的聊天入口
- 挂载默认知识库、默认能力、默认入口对象、默认参数

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `owner_id UUID NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `description TEXT`
- `status VARCHAR(32) NOT NULL DEFAULT 'active'`
- `entrypoint_type VARCHAR(32) NOT NULL`
- `entrypoint_id UUID`
- `channel_scope VARCHAR(32) NOT NULL DEFAULT 'ui'`
- `default_model_id UUID`
- `default_retrieval_profile_id UUID`
- `default_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `space_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb`
- `last_session_at TIMESTAMPTZ`
- `created_by_id UUID`
- `updated_by_id UUID`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `entrypoint_type`: `assistant | workflow | agent`
- `status`: `active | archived | deleted`
- `channel_scope`: `ui | api | mixed`

最佳实践说明：

- `chat_spaces` 才是聊天模块首页的核心对象
- 它更像“聊天入口定义 + 默认能力容器”
- 未来可直接承接知识库空间、工作流空间、Agent 空间

### 30.3 `chat_space_capability_bindings`

用途：

- 给 `chat_spaces` 挂默认能力

建议支持：

- `knowledge_base`
- `tool`
- `search_provider`
- `mcp_server`
- `workflow`
- `skill`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `chat_space_id UUID NOT NULL`
- `capability_type VARCHAR(32) NOT NULL`
- `capability_id UUID NOT NULL`
- `binding_role VARCHAR(32) NOT NULL DEFAULT 'default'`
- `is_enabled BOOLEAN NOT NULL DEFAULT TRUE`
- `priority INT NOT NULL DEFAULT 100`
- `config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### 30.4 `chat_sessions`：具体会话实例表

这才是真正的聊天 session。

用途：

- 对应进入某个聊天空间后的左侧会话列表
- 对应用户当前正在进行的一次具体会话
- 负责保存该次会话自己的历史与局部覆盖参数

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `chat_space_id UUID NOT NULL`
- `owner_id UUID NOT NULL`
- `title VARCHAR(255)`
- `summary TEXT`
- `status VARCHAR(32) NOT NULL DEFAULT 'active'`
- `channel VARCHAR(32) NOT NULL`
- `visibility VARCHAR(32) NOT NULL DEFAULT 'user_visible'`
- `persistence_mode VARCHAR(32) NOT NULL DEFAULT 'persistent'`
- `config_override JSONB NOT NULL DEFAULT '{}'::jsonb`
- `session_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb`
- `last_message_at TIMESTAMPTZ`
- `archived_at TIMESTAMPTZ`
- `deleted_at TIMESTAMPTZ`
- `created_by_id UUID`
- `updated_by_id UUID`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议枚举：

- `status`: `active | archived | deleted`
- `channel`: `ui | api | system`
- `visibility`: `user_visible | backend_only`
- `persistence_mode`: `persistent | ephemeral`

最佳实践说明：

- `chat_sessions` 不再作为首页卡片主表
- 它是 `chat_space` 下的具体实例
- UI 与 API 的历史隔离、是否可展示，也应该放在这一层控制

### 30.5 `chat_session_stats`

用途：

- 存放具体会话级别统计

建议字段：

- `session_id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `message_count INT NOT NULL DEFAULT 0`
- `turn_count INT NOT NULL DEFAULT 0`
- `user_message_count INT NOT NULL DEFAULT 0`
- `assistant_message_count INT NOT NULL DEFAULT 0`
- `tool_call_count INT NOT NULL DEFAULT 0`
- `workflow_run_count INT NOT NULL DEFAULT 0`
- `total_input_tokens BIGINT NOT NULL DEFAULT 0`
- `total_output_tokens BIGINT NOT NULL DEFAULT 0`
- `total_tokens BIGINT NOT NULL DEFAULT 0`
- `last_model_id UUID`
- `last_turn_status VARCHAR(32)`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### 30.6 `chat_messages`

正式作用不变，但必须明确其归属是：

- 属于 `chat_session`
- 而不是直接属于首页聊天卡片容器

建议字段保持：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID`
- `parent_message_id UUID`
- `replaces_message_id UUID`
- `role VARCHAR(32) NOT NULL`
- `message_type VARCHAR(32) NOT NULL DEFAULT 'text'`
- `status VARCHAR(32) NOT NULL DEFAULT 'completed'`
- `source_channel VARCHAR(32) NOT NULL`
- `content TEXT`
- `content_blocks JSONB NOT NULL DEFAULT '[]'::jsonb`
- `display_content TEXT`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `is_visible BOOLEAN NOT NULL DEFAULT TRUE`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `user_id UUID`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### 30.7 `chat_turns`

正式作用也不变，但归属同样应明确为：

- 属于具体 `chat_session`
- 执行参数从 `chat_space` 默认值和 `chat_session` 覆盖值中合并得出

建议字段保持：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `request_id UUID NOT NULL`
- `execution_mode VARCHAR(32) NOT NULL`
- `status VARCHAR(32) NOT NULL`
- `user_message_id UUID`
- `assistant_message_id UUID`
- `effective_model_id UUID`
- `effective_agent_id UUID`
- `effective_retrieval_profile_id UUID`
- `effective_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `rewrite_query TEXT`
- `final_query TEXT`
- `prompt_tokens INT`
- `completion_tokens INT`
- `total_tokens INT`
- `latency_ms INT`
- `started_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `debug_summary JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### 30.8 配置继承链

正式推荐的配置继承关系：

1. 租户默认
2. Knowledge Base 默认
3. Retrieval Profile 默认
4. `chat_space.default_config`
5. `chat_session.config_override`
6. 当前请求 override
7. 写入 `chat_turns.effective_config`

这样能同时兼容：

- 聊天空间默认配置
- 某次具体会话中的局部调整
- 单轮即时调参

### 30.9 这套模型下，首页与详情页的表映射

#### 聊天首页卡片页

主查：

- `chat_spaces`

补充：

- `chat_space` 的聚合统计
- 最近一次 `chat_session`

#### 进入某个聊天空间后的左侧会话列表

主查：

- `chat_sessions`

过滤条件：

- `chat_space_id = 当前 space`

#### 当前聊天详情页

主查：

- `chat_sessions`
- `chat_messages`
- `chat_turns`

右侧参数面板默认来源：

- `chat_space.default_config`

若当前会话有特殊覆盖，则叠加：

- `chat_session.config_override`

### 30.10 最终推荐落地顺序

正式落地建议按下面顺序进行：

1. 先建 `chat_spaces`
2. 再建 `chat_sessions`
3. 再建 `chat_messages`
4. 再建 `chat_turns`
5. 再补 `chat_space_capability_bindings`
6. 再补检索、工具、工作流等执行明细表

### 30.11 本文最终采用的命名

正式采用：

- `chat_spaces`：聊天首页卡片层
- `chat_sessions`：某个聊天空间下的具体会话层
- `chat_messages`：消息层
- `chat_turns`：执行层

不再采用：

- 直接把首页卡片层命名为 `chat_sessions`
- 使用 `default_assistant_id` 作为顶层会话主语义字段

顶层入口统一使用：

- `chat_spaces.entrypoint_type`
- `chat_spaces.entrypoint_id`

这就是本文最终定稿口径。

---

## 31. 设计复审：字段收敛、性能与是否过度设计

本节用于对前文方案做二次收敛，重点回答：

- 当前表设计是否合理
- 是否存在过度设计
- 哪些字段应补充
- 哪些字段应删除或延后
- 是否考虑了性能与后续维护成本

结论先行：

- 整体分层方向是合理的
- `chat_spaces -> chat_sessions -> chat_messages / chat_turns` 是当前最适合你的结构
- 但前文部分字段与子表拆分偏“平台终局形态”，需要收敛到“当前可落地 + 未来可扩展”
- 最佳实践不是“把未来所有能力一次性建全”，而是“先把主干设计对，再为未来留稳定扩展点”

### 31.1 哪些地方是正确且应保留的

以下设计建议继续保留，不建议再回退：

#### A. 两层模型

- `chat_spaces`
- `chat_sessions`

这是当前原型最自然的抽象，不是过度设计。

原因：

- 首页卡片和内部具体会话确实是两个层级
- 这能天然承接“聊天入口”和“具体历史会话”的区别
- 这比把所有东西都塞进单层 `chat_sessions` 更符合产品心智

#### B. 执行层单独拆分

- `chat_turns`

这也不是过度设计。

原因：

- 只用消息表无法承接检索快照、工具调用、工作流运行、token、耗时
- 后续只要你有检索调优、问题排查、调用审计，这层都是必需的

#### C. 引用单独结构化

- `chat_message_citations`

这是高价值设计，不建议回退到纯 JSON。

原因：

- 引用是 RAG 产品最关键的业务资产之一
- 前端引用跳转、质量评估、来源分析都依赖结构化落库

### 31.2 哪些地方偏重，需要收敛

前文为了覆盖未来场景，确实有几处偏重，这里建议明确收敛。

#### A. 不建议现在就落太多“并行绑定表”

前文提到了：

- `chat_space_capability_bindings`
- `assistant_capability_bindings`
- `agent_capability_bindings`

从终局架构看没问题，但当前阶段不建议三套都上。

当前最佳实践建议：

- 先只落 `chat_space_capability_bindings`
- `assistant` 若短期只是入口类型，不急于单独建绑定表
- `agent_capability_bindings` 暂时只保留设计，不立即建表

原因：

- 当前主战场是知识库聊天与未来工作流
- 现在同时建三套绑定表会抬高理解成本和维护成本
- 真正需要时再把能力绑定向 Assistant / Agent 扩展，更稳

#### B. 不建议现在就落所有 Agent 运行子表

前文提到了：

- `chat_turn_agent_runs`

这个方向是对的，但当前阶段建议：

- 仅保留设计，不立即落表

原因：

- 你当前并没有明确的多 Agent 协作与自主规划业务
- 过早落表容易形成“为了未来而未来”
- 当前先用 `chat_turns.execution_mode='agent'` + `debug_summary` 预留即可

#### C. `space_snapshot` / `session_snapshot` 建议收敛

前文提到：

- `space_snapshot`
- `session_snapshot`

这两个字段不建议都作为正式主字段强制落地。

更稳的建议：

- `chat_spaces` 保留 `default_config`
- `chat_sessions` 保留 `config_override`
- 只有在明确需要展示快照时，再引入一个统一的 `display_snapshot` 或 `metadata`

原因：

- “snapshot” 语义很宽，后续容易变成杂物箱
- 过多 snapshot 字段会让数据来源不清晰
- 最佳实践是：默认配置、覆盖配置、执行快照三层分明，少做额外快照

#### D. `entrypoint_id` 允许为空，但不要扩散太多冗余字段

当前建议保留：

- `entrypoint_type`
- `entrypoint_id`

但不建议再额外加：

- `default_assistant_id`
- `default_workflow_id`
- `default_agent_id`

原因：

- 冗余字段会让入口语义变乱
- 当前只保留统一入口表达最清晰

### 31.3 哪些字段建议补充

在当前正式设计里，我认为有几类字段值得补充。

#### A. 排序与显示字段

建议在 `chat_spaces` 和 `chat_sessions` 中补充：

- `display_order INT NOT NULL DEFAULT 100`
- `is_pinned BOOLEAN NOT NULL DEFAULT FALSE`

原因：

- 聊天产品通常需要置顶和排序
- 靠 `updated_at` 一种排序不够

#### B. 会话标题生成状态

建议在 `chat_sessions` 中补充：

- `title_source VARCHAR(32) NOT NULL DEFAULT 'manual'`

建议枚举：

- `manual | auto | fallback`

原因：

- 聊天标题经常是自动生成的
- 后续有助于区分用户手改标题和系统生成标题

#### C. 幂等与外部请求标识

建议在 `chat_sessions` 和 `chat_turns` 视需要补充：

- `external_ref_id VARCHAR(128)`
- `idempotency_key VARCHAR(128)`

原因：

- API 场景下很常见
- 对重试、防重复提交很有帮助

当前建议：

- `chat_turns` 优先保留 `request_id`
- `chat_sessions.external_ref_id` 可选，不是第一批必需

#### D. 会话关闭时间

建议在 `chat_sessions` 增加：

- `closed_at TIMESTAMPTZ`

原因：

- 对归档、完成态、统计分析更清晰

### 31.4 哪些字段不建议一开始就单列化

最佳实践不是把所有想象中的参数都做列。

以下内容建议继续放在 JSONB 配置中，不必单列：

- 多轮改写策略细节
- 检索权重组合
- Knowledge Graph 细粒度参数
- Web Search 细粒度参数
- MCP 调用细节
- Workflow 节点局部参数

原因：

- 这些参数变化快
- 很多还未稳定
- 现在单列化只会导致后续频繁迁移

所以更合适的是：

- 稳定查询字段单列
- 快速演进参数进 `default_config / config_override / effective_config`

### 31.5 性能是否考虑充分

整体上，这套方案性能是可控的，但要注意几个关键点。

#### A. 列表页不要实时扫消息表

首页卡片页和左侧会话列表，不能每次实时统计：

- 消息数
- token
- 最后一条消息

最佳实践：

- 维护 `chat_session_stats`
- 如未来首页卡片也有复杂统计，可再补 `chat_space_stats`

当前建议：

- 第一阶段只建 `chat_session_stats`
- `chat_space` 页面的聚合可以先通过最近 session 或轻量聚合实现
- 不急着再建 `chat_space_stats`

#### B. 消息表要控制热路径索引

`chat_messages` 最核心查询一般只有两类：

- 按 `session_id + created_at` 拉会话消息流
- 按 `turn_id` 反查本轮消息

所以不建议一开始加太多复合索引。

当前推荐保留：

- `(session_id, created_at)`
- `(turn_id)`

够了。

#### C. Turn 表是审计核心，但不宜无限膨胀

`chat_turns` 里建议保留：

- 核心执行状态
- token
- latency
- `effective_config`
- `debug_summary`

不建议：

- 把所有检索明细、所有工具明细都继续塞回 `chat_turns`

原因：

- 审计表要稳定
- 细粒度明细应进子表

#### D. 引用表不会成为主要瓶颈

`chat_message_citations` 通常单条消息引用数有限。

所以：

- 结构化拆分收益远大于性能损失
- 关键是索引别过多

当前推荐保留：

- `(message_id, citation_index)`
- `(turn_id)`

#### E. JSONB 使用是合理的，但要克制

当前设计里 JSONB 主要集中在：

- `default_config`
- `config_override`
- `effective_config`
- `debug_summary`
- 若干 `metadata`

这是合理的。

但最佳实践要求：

- 不把关键查询条件藏进 JSONB
- 不把业务主语义只写进 JSONB

### 31.6 是否过度设计

如果按“当前立刻上线实现”看，前文终局版确实偏重。

如果按“开发阶段重新建模，后续不想推倒重来”看，方向又是合理的。

所以更准确的判断是：

- 架构方向不过度
- 但首批落库范围需要收敛

### 31.7 当前阶段最推荐的首批建表范围

从最佳实践和项目节奏综合考虑，第一批最推荐落的只有这些：

- `chat_spaces`
- `chat_space_capability_bindings`
- `chat_sessions`
- `chat_session_stats`
- `chat_messages`
- `chat_message_citations`
- `chat_turns`
- `chat_turn_retrievals`
- `chat_turn_tool_calls`
- `chat_turn_workflow_runs`
- `retrieval_profiles`
- `workflows`

这一批已经足够覆盖：

- 知识库聊天
- 多知识库绑定
- API 会话
- 工具调用
- MCP 工具接入
- 工作流聊天
- 后续 Dify 式编排

但又没有把 Agent 平台一次性做满。

### 31.8 当前阶段不建议首批落库的内容

以下建议先不建表，只保留设计：

- `agents`
- `agent_capability_bindings`
- `chat_turn_agent_runs`
- `chat_space_stats`

原因：

- 当前业务优先级还不够高
- 现在建容易造成概念负担
- 真有场景时再补，会更稳

### 31.9 最终复审结论

最终建议可以收敛成一句话：

当前正式设计应采用“两层聊天模型 + 执行分层 + 统一能力挂载”的主干架构；
首批落地范围要控制在知识库聊天和未来工作流兼容所必需的表上；
Agent 相关只预留扩展位，不宜在当前阶段过度落库。

这才是更符合你当前项目节奏的最佳实践。

---

## 32. 首批落地版表结构建议

本节是面向当前开发阶段的“第一批真正建议落地”的版本。

目标不是覆盖所有未来可能，而是满足下面几件最重要的事：

- 支持首页聊天空间
- 支持空间下多会话
- 支持多知识库挂载
- 支持会话消息与执行快照
- 支持检索引用、工具调用、工作流运行
- 为未来 Dify 式编排预留稳定扩展点

### 32.1 首批推荐落地的表

当前最推荐落地的只有以下 10 张表：

1. `chat_spaces`
2. `chat_space_capability_bindings`
3. `chat_sessions`
4. `chat_session_stats`
5. `chat_messages`
6. `chat_message_citations`
7. `chat_turns`
8. `chat_turn_retrievals`
9. `chat_turn_tool_calls`
10. `chat_turn_workflow_runs`

补充两个基础能力表：

11. `retrieval_profiles`
12. `workflows`

如果要再进一步收敛，甚至可以把第 9、10 张表延后，但不建议把前 8 张再删减。

### 32.2 首批不建议落地的表

以下表当前阶段建议只保留设计，不立即建：

- `agents`
- `agent_capability_bindings`
- `chat_turn_agent_runs`
- `assistant_capability_bindings`
- `chat_space_stats`

原因：

- 当前业务主轴还不是 Agent 平台
- 这些表的语义后续大概率还会调整
- 先落会增加复杂度，不利于快速稳定迭代

---

## 33. 首批落地版字段建议

本节给出首批版本更收敛的字段集。

### 33.1 `chat_spaces`

这是首页卡片层主表。

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `owner_id UUID NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `description TEXT`
- `status VARCHAR(32) NOT NULL DEFAULT 'active'`
- `entrypoint_type VARCHAR(32) NOT NULL`
- `entrypoint_id UUID`
- `default_model_id UUID`
- `default_retrieval_profile_id UUID`
- `default_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `is_pinned BOOLEAN NOT NULL DEFAULT FALSE`
- `display_order INT NOT NULL DEFAULT 100`
- `last_session_at TIMESTAMPTZ`
- `created_by_id UUID`
- `updated_by_id UUID`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议说明：

- `name`：首页卡片标题
- `description`：首页卡片描述
- `entrypoint_type`：`assistant | workflow | agent`
- `entrypoint_id`：指向具体入口对象，当前可以主要用于 Assistant 或 Workflow
- `default_config`：空间级默认参数容器

当前不建议加的字段：

- `space_snapshot`
- `default_assistant_id`
- `channel_scope`

原因：

- 要么语义重复，要么当前使用价值不高

推荐索引：

- `(tenant_id, owner_id, status, updated_at DESC)`
- `(tenant_id, is_pinned DESC, display_order ASC, updated_at DESC)`

### 33.2 `chat_space_capability_bindings`

这是空间级能力挂载表。

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `chat_space_id UUID NOT NULL`
- `capability_type VARCHAR(32) NOT NULL`
- `capability_id UUID NOT NULL`
- `binding_role VARCHAR(32) NOT NULL DEFAULT 'default'`
- `is_enabled BOOLEAN NOT NULL DEFAULT TRUE`
- `priority INT NOT NULL DEFAULT 100`
- `config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议支持的 `capability_type`：

- `knowledge_base`
- `tool`
- `search_provider`
- `mcp_server`
- `workflow`
- `skill`

当前最主要的用途：

- 给聊天空间挂知识库
- 给聊天空间挂工具/MCP
- 给工作流型空间挂可用流程

推荐索引：

- `(chat_space_id, capability_type, priority)`
- `(tenant_id, capability_type, capability_id)`

### 33.3 `chat_sessions`

这是空间下的具体聊天会话。

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `chat_space_id UUID NOT NULL`
- `owner_id UUID NOT NULL`
- `title VARCHAR(255)`
- `title_source VARCHAR(32) NOT NULL DEFAULT 'manual'`
- `summary TEXT`
- `status VARCHAR(32) NOT NULL DEFAULT 'active'`
- `channel VARCHAR(32) NOT NULL DEFAULT 'ui'`
- `visibility VARCHAR(32) NOT NULL DEFAULT 'user_visible'`
- `persistence_mode VARCHAR(32) NOT NULL DEFAULT 'persistent'`
- `config_override JSONB NOT NULL DEFAULT '{}'::jsonb`
- `is_pinned BOOLEAN NOT NULL DEFAULT FALSE`
- `display_order INT NOT NULL DEFAULT 100`
- `last_message_at TIMESTAMPTZ`
- `closed_at TIMESTAMPTZ`
- `archived_at TIMESTAMPTZ`
- `deleted_at TIMESTAMPTZ`
- `created_by_id UUID`
- `updated_by_id UUID`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议说明：

- `title`：左侧会话标题
- `title_source`：`manual | auto | fallback`
- `config_override`：该会话对空间默认配置的覆盖项

推荐索引：

- `(chat_space_id, status, updated_at DESC)`
- `(tenant_id, owner_id, status, updated_at DESC)`
- `(tenant_id, channel, visibility, updated_at DESC)`

### 33.4 `chat_session_stats`

建议字段：

- `session_id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `message_count INT NOT NULL DEFAULT 0`
- `turn_count INT NOT NULL DEFAULT 0`
- `user_message_count INT NOT NULL DEFAULT 0`
- `assistant_message_count INT NOT NULL DEFAULT 0`
- `tool_call_count INT NOT NULL DEFAULT 0`
- `workflow_run_count INT NOT NULL DEFAULT 0`
- `total_input_tokens BIGINT NOT NULL DEFAULT 0`
- `total_output_tokens BIGINT NOT NULL DEFAULT 0`
- `total_tokens BIGINT NOT NULL DEFAULT 0`
- `last_model_id UUID`
- `last_turn_status VARCHAR(32)`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议说明：

- 列表页和左侧会话列表不要实时扫消息表
- 这个表是性能稳定的重要前提

### 33.5 `chat_messages`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID`
- `parent_message_id UUID`
- `replaces_message_id UUID`
- `role VARCHAR(32) NOT NULL`
- `message_type VARCHAR(32) NOT NULL DEFAULT 'text'`
- `status VARCHAR(32) NOT NULL DEFAULT 'completed'`
- `source_channel VARCHAR(32) NOT NULL`
- `content TEXT`
- `content_blocks JSONB NOT NULL DEFAULT '[]'::jsonb`
- `display_content TEXT`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `is_visible BOOLEAN NOT NULL DEFAULT TRUE`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `user_id UUID`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议说明：

- `content` 是主文本
- `content_blocks` 为未来富文本、多段结果、工具结果块做预留
- 当前阶段完全可以先以文本为主，复杂块按需开启

推荐索引：

- `(session_id, created_at)`
- `(turn_id)`

### 33.6 `chat_message_citations`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID`
- `message_id UUID NOT NULL`
- `citation_index INT NOT NULL`
- `kb_id UUID`
- `kb_doc_id UUID`
- `chunk_id BIGINT`
- `source_anchor TEXT`
- `page_number INT`
- `snippet TEXT`
- `score DOUBLE PRECISION`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

推荐索引：

- `(message_id, citation_index)`
- `(turn_id)`

### 33.7 `chat_turns`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `request_id UUID NOT NULL`
- `execution_mode VARCHAR(32) NOT NULL`
- `status VARCHAR(32) NOT NULL`
- `user_message_id UUID`
- `assistant_message_id UUID`
- `effective_model_id UUID`
- `effective_retrieval_profile_id UUID`
- `effective_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `rewrite_query TEXT`
- `final_query TEXT`
- `prompt_tokens INT`
- `completion_tokens INT`
- `total_tokens INT`
- `latency_ms INT`
- `started_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `debug_summary JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议说明：

- `execution_mode` 当前建议只用：
  - `retrieval_chat`
  - `workflow`
  - `agent`
- `effective_config` 是运行快照核心字段

推荐索引：

- `(session_id, created_at DESC)`
- `(tenant_id, request_id)`
- `(tenant_id, status, created_at DESC)`

### 33.8 `chat_turn_retrievals`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID NOT NULL`
- `retrieval_source_type VARCHAR(32) NOT NULL`
- `retrieval_source_id UUID`
- `kb_id UUID`
- `kb_doc_id UUID`
- `chunk_id BIGINT`
- `retrieval_stage VARCHAR(32) NOT NULL`
- `raw_score DOUBLE PRECISION`
- `rerank_score DOUBLE PRECISION`
- `final_score DOUBLE PRECISION`
- `rank_index INT`
- `selected_for_context BOOLEAN NOT NULL DEFAULT FALSE`
- `selected_for_citation BOOLEAN NOT NULL DEFAULT FALSE`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

当前主要服务于：

- 召回调试
- 引用复盘
- 检索评测

### 33.9 `chat_turn_tool_calls`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID NOT NULL`
- `message_id UUID`
- `tool_type VARCHAR(32) NOT NULL`
- `tool_id UUID`
- `tool_name VARCHAR(255) NOT NULL`
- `provider_type VARCHAR(32)`
- `provider_ref_id UUID`
- `call_index INT NOT NULL DEFAULT 1`
- `status VARCHAR(32) NOT NULL`
- `input_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `output_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `latency_ms INT`
- `started_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

当前最重要的价值：

- 为 MCP / Tool / 搜索工具 / Workflow 工具调用保留统一日志模型

### 33.10 `chat_turn_workflow_runs`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `session_id UUID NOT NULL`
- `turn_id UUID NOT NULL`
- `workflow_id UUID NOT NULL`
- `trigger_source VARCHAR(32) NOT NULL`
- `run_status VARCHAR(32) NOT NULL`
- `input_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `output_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `run_summary JSONB NOT NULL DEFAULT '{}'::jsonb`
- `error_code VARCHAR(128)`
- `error_message TEXT`
- `started_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

当前最重要的价值：

- 为未来 Dify 式编排保留统一运行痕迹

### 33.11 `retrieval_profiles`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `description TEXT`
- `status VARCHAR(32) NOT NULL DEFAULT 'active'`
- `config JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

建议说明：

- 检索配置模板建议尽量独立
- 不要让检索参数完全散落在 KB / space / session 中

### 33.12 `workflows`

建议字段：

- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `description TEXT`
- `workflow_type VARCHAR(32) NOT NULL DEFAULT 'chat_flow'`
- `definition JSONB NOT NULL DEFAULT '{}'::jsonb`
- `input_schema JSONB NOT NULL DEFAULT '{}'::jsonb`
- `output_schema JSONB NOT NULL DEFAULT '{}'::jsonb`
- `status VARCHAR(32) NOT NULL DEFAULT 'draft'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

---

## 34. 首批落地版的合理性判断

### 34.1 是否合理

这版表结构是合理的。

因为它解决了当前最核心的业务问题：

- 首页卡片与内部会话分层
- 多知识库能力挂载
- 消息流持久化
- 检索引用可追踪
- 工作流和工具调用可观测

同时又没有把未来所有 Agent 能力一次性做重。

### 34.2 是否最佳实践

从当前项目阶段看，这版更接近最佳实践。

原因：

- 主体结构清晰
- 配置分层清晰
- 查询路径明确
- 对未来编排能力有扩展位
- 没有为了“可能会有的智能体平台”而把当前模型复杂化

### 34.3 是否过度设计

这版相较前文终局版，已经明显收敛。

仍然保留的“面向未来预留”只有：

- `entrypoint_type`
- `chat_space_capability_bindings`
- `chat_turn_tool_calls`
- `chat_turn_workflow_runs`

我认为这些不属于过度设计，而是必要的扩展基础。

### 34.4 是否考虑性能

是考虑过的，主要体现在：

- 首页和左侧列表依赖 `chat_session_stats`
- 不依赖实时扫消息表统计
- 消息表只保留少量高价值索引
- 运行明细拆分到子表，避免 `chat_turns` 单表膨胀
- 快速变化参数保留 JSONB，不频繁迁移表结构

### 34.5 当前仍要注意的风险

虽然这版已经收敛，但仍有几个注意点：

- `content_blocks` 虽然必要，但第一阶段不要过度使用
- `metadata` / `debug_summary` 要严格约束内容，不要变成垃圾桶
- `chat_space_capability_bindings` 要避免后续堆太多弱语义能力类型
- `retrieval_profiles.config` 需要尽早约定统一字段规范

---

## 35. 当前版本的最终建议

如果现在就进入数据库设计与实现阶段，建议以本节首批落地版为准：

- 不再按旧 `init-schema.sql` 的 `conversations/messages` 思路修修补补
- 直接切到 `chat_spaces -> chat_sessions -> chat_messages/chat_turns` 两层主模型
- 首批只实现当前真正需要的 10 到 12 张核心表
- Agent 相关延后
- 将来如果要做真正智能体平台，再基于当前模型平滑扩展

这就是我现在认为最符合你项目现阶段、也最符合最佳实践的一版方案。
