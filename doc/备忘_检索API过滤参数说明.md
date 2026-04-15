# 检索 API 过滤参数备忘

## 入口

检索测试接口和聊天知识库绑定最终都会把过滤配置传给混合检索服务。核心结构：

```json
{
  "query": "南康地区在哪里修理笔记本",
  "config": {
    "auto_filter_mode": "hybrid",
    "enable_llm_filter_expression": true,
    "metadata_fields": []
  },
  "filters": {
    "folder_ids": [],
    "tag_ids": [],
    "metadata": {},
    "search_unit_metadata": {},
    "filter_expression": {}
  }
}
```

## 简单过滤

这里的“简单过滤”指显式传入的直接条件，不包含自动标签候选、自动元数据候选，也不包含表达式树。

`filters.kb_doc_ids`：限定知识库文档 ID，多个值是 OR，和其他过滤项整体是 AND。

`filters.document_ids`：限定原始文档 ID，多个值是 OR。

`filters.folder_ids`：限定文件夹 ID，多个值是 OR。`include_descendant_folders=true` 时包含子目录。

`filters.folder_tag_ids`：先解析出匹配这些标签的文件夹，再按文件夹过滤。多个标签目前按“匹配任一标签的文件夹”进入候选集合。

`filters.tag_ids`：文档标签硬过滤。多个标签目前要求文档同时具备这些标签。

`filters.metadata` / `filters.document_metadata`：文档级元数据精确匹配。多个 key 是 AND；单个 key 当前是精确值匹配。

`filters.search_unit_metadata`：分块/QA/表格行级元数据过滤。普通召回后端按 JSONB 包含关系过滤；表格和 QA 会优先走业务表解析 content_group 范围。

`filters.only_tagged`：只返回有文档标签的文档。

## 统一过滤表达式

`filters.filter_expression` 是统一过滤表达式入口。

它既可以写目录 / 标签条件，也可以写文档元数据 / 分块元数据条件，还可以混合写。

`filters.filter_expression` 用于复杂硬过滤，支持括号、跨字段 OR、NOT、`not_in`。表达式不是 SQL 字符串，而是受控 JSON 树。

逻辑节点：

```json
{
  "op": "and",
  "items": []
}
```

支持 `and`、`or`、`not`。`items` 可以嵌套，表示括号。

叶子节点：

```json
{
  "field": "metadata",
  "path": ["region"],
  "op": "in",
  "values": ["南康", "赣州"]
}
```

支持字段：

`kb_doc` / `kb_doc_id`：知识库文档 ID。

`document` / `document_id`：原始文档 ID。

`folder` / `folder_id`：文件夹 ID。

`folder_tag` / `folder_tag_id`：文件夹标签 ID，后端会先解析为文件夹 ID。

`tag` / `doc_tag` / `tag_id`：文档标签 ID。

`metadata` / `document_metadata`：文档元数据，必须带 `path`。

`search_unit_metadata`：分块/搜索单元元数据，必须带 `path`。

支持操作符：

`eq`：等于第一个值。

`ne`：不等于第一个值，缺失值默认通过。

`in`：在多个值中。

`not_in`：不在多个值中，缺失值默认通过；该操作符已真正落到 SQL 的 `NOT IN`。

`exists`：路径或字段存在。

`not_exists`：路径或字段不存在。

示例：南康地区，且排除某个文档标签：

```json
{
  "op": "and",
  "items": [
    {
      "field": "metadata",
      "path": ["region"],
      "op": "in",
      "values": ["南康"]
    },
    {
      "field": "tag",
      "op": "not_in",
      "values": ["文档标签ID"]
    }
  ]
}
```

示例：文档地区是南康，或者分块分类是维修：

```json
{
  "op": "or",
  "items": [
    {
      "field": "metadata",
      "path": ["region"],
      "op": "eq",
      "values": ["南康"]
    },
    {
      "field": "search_unit_metadata",
      "path": ["qa_fields", "category"],
      "op": "eq",
      "values": ["维修"]
    }
  ]
}
```

## 自动标签、自动元数据与 LLM 统一过滤表达式

`config.metadata_fields`：声明 LLM/规则可识别的元数据字段。字段里可以配置 `key`、`name`、`aliases`、`options`、`target`、`metadata_path`、`match_mode`。

`config.extra_metadata_fields`：在知识库默认字段之外追加字段。

`config.override_metadata_fields`：完全覆盖知识库默认字段和请求里的 `metadata_fields`，优先级最高。

优先级：`override_metadata_fields` > `metadata_fields` 或知识库默认字段 > `extra_metadata_fields` 追加。

`config.auto_filter_mode`：

`disabled`：不做自动标签/元数据识别。

`rule`：只做规则候选。标签只加权，自动文档元数据按 match 模式过滤。

`llm_candidate`：让 LLM 在一次调用里同时尝试输出候选与建议表达式。目录/标签候选默认不直接升级为硬过滤；但通过校验的元数据候选会转成 `auto_filter_signals`，并在检索阶段形成自动元数据过滤。通过校验的 LLM 统一过滤表达式会作为追加硬过滤并入最终条件；如果 API 已有显式表达式，则以 `AND` 方式继续收紧。

`hybrid`：规则 + LLM。推荐理解为“规则先抽取，LLM做补充 / 纠偏 / 表达式化”。API 显式过滤始终锁定；LLM 可以纠偏同目标规则候选，但不能覆盖 API 显式过滤。LLM 统一过滤表达式会以 `AND` 方式并入最终条件。

`config.enable_llm_filter_expression`：是否允许 LLM 输出受控统一过滤表达式。默认开启。表达式会重新归一化并校验：只能引用提示词里给出的目录、标签、元数据字段；有枚举值时只允许枚举内的值。LLM 不会输出 SQL，后端也不会执行自由文本条件。

注意：API / 前端显式传入的 `locked_filters` 不会传给 LLM。LLM 只看到 query、候选池以及 hybrid 下的规则候选；显式过滤冲突校验与最终合并全部在后端完成。

## 覆盖关系

API 显式传入的 `filters.filter_expression` 优先级最高。LLM 自动统一过滤表达式不会覆盖它，只会在其基础上继续 `AND` 收紧。

简单过滤和表达式会一起生效，整体相当于 AND。比如同时传了 `folder_ids` 和 `filter_expression`，结果必须同时满足目录范围和表达式。

自动元数据过滤不参与评分，只负责过滤范围。自动标签不作为硬过滤，主要进入标签加权诊断。注意：LLM 元数据候选先要满足 `LLM 最小置信度` 并通过后端校验，才会转成自动元数据过滤信号。

## 诊断

检索测试结果和聊天调试会展示：

`explicit_filters`：API/界面显式传入的过滤。

`query_analysis.resolved_filters`：查询分析后最终合并的过滤，包括 LLM 统一过滤表达式是否落地。

`pipeline.filters.debug_summary.requested_filter_expression`：本轮请求表达式摘要。

`llm_debug.filter_expression`：LLM 输出并通过校验的统一过滤表达式。

`llm_debug.filter_expression_applied`：是否实际落地。

`llm_debug.filter_expression_merge_mode`：表达式并入方式。当前可能为：

- `llm_only`：本轮只有 LLM 表达式
- `and_append`：API 显式表达式已存在，LLM 表达式通过 `AND` 追加收紧

## 术语建议

为了避免混淆，推荐统一使用下面这组名称：

- 标签过滤：`tag_ids`、`folder_tag_ids`
- 元数据过滤：`metadata` / `document_metadata`、`search_unit_metadata`
- 统一过滤表达式：`filter_expression`
- 自动标签候选：规则或 LLM 从 query 中识别到的标签相关信号
- 自动元数据候选：规则或 LLM 从 query 中识别到的元数据相关信号
- LLM 统一过滤表达式：LLM 输出并经后端校验的 `filter_expression`

## 兼容旧参数

`config.metadata_filter` 目前仍保留在接口结构中，主要用于兼容旧测试配置。

它表达的是一些历史范围选项，例如时间窗或“仅带标签文档”，概念上不属于当前这套“元数据过滤 / 标签过滤 / 统一过滤表达式”主体系。

新能力设计、前端主入口和排查诊断，建议都围绕：

- 简单过滤
- 自动标签 / 自动元数据
- 统一过滤表达式

来理解，不再把 `metadata_filter` 当成主能力入口。
