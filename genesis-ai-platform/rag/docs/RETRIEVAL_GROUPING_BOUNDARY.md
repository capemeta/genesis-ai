# 检索分组边界说明

本文档用于明确 `parent_id`、`content_group_id`、`hierarchical_retrieval_mode`、`group_by_content_group` 四者的职责边界，避免把“层级召回”和“业务聚合”混为一谈。

## 1. `parent_id` 的职责：层级关系

`parent_id` 只表达 Chunk 之间的结构树关系。

典型用途：

1. 叶子块命中后，找到所属父块
2. 对层级分块做 `recursive` / `auto_merge`
3. 在最终展示或喂给模型时补充父块上下文

它解决的问题是：

- 这个叶子块属于哪个父块
- 多个叶子块是否属于同一个父块

它**不负责**表达“这些块是不是同一个业务对象”。

## 2. `content_group_id` 的职责：业务归属关系

`content_group_id` 用于把多个检索单元归并到同一个业务对象。

典型用途：

1. QA 知识库中，把同一条 QA 记录下的 `question`、`answer`、`answer_fragment` 视为同一个业务单元
2. 表格知识库中，把同一行的 `row`、`row_group`、`row_fragment` 视为同一条业务记录
3. 通用知识库中的 Excel 行分块，把同一行的完整行块与行片段视为同一业务行

它解决的问题是：

- 这些命中是不是同一条业务记录
- 是否要把同一业务对象下的多个命中折叠成一条结果

它**不负责**：

- 从叶子块回溯父块
- 决定是否补父上下文
- 决定是否自动父块合并

## 3. `hierarchical_retrieval_mode` 的职责：层级召回策略

`hierarchical_retrieval_mode` 只决定“命中叶子块后，结果按什么层级返回”。

当前策略：

1. `leaf_only`
   仅返回命中的最小检索单元，不补父上下文，也不做父级合并
2. `recursive`
   命中叶子块后，保留叶子命中点，同时补父上下文
3. `auto_merge`
   当多个叶子块集中命中同一父块时，结果收敛为父块结果

注意：

- 对表格、QA、Excel 行等“独立元素拆分”的场景，最终返回结果必须是完整父块 / 完整行
- 这属于层级召回和完整单元回收职责，不属于 `group_by_content_group`

## 4. `group_by_content_group` 的职责：业务聚合开关

`group_by_content_group` 只决定“多个已经命中的候选结果，是否按业务单元继续折叠”。

推荐理解方式：

1. 先由 `hierarchical_retrieval_mode` 决定结果应该落在叶子块还是父块
2. 再由 `group_by_content_group` 决定这些结果是否按业务对象继续合并

因此它的职责是：

- `true`：同一 `content_group_id` 下的多个候选结果继续合并成一条业务结果
- `false`：只按层级召回后的自然结果单元排序，不再跨结果做业务聚合

## 5. 四者关系总结

1. `parent_id`
   负责结构层级
2. `hierarchical_retrieval_mode`
   负责层级召回策略
3. `content_group_id`
   负责业务归属标识
4. `group_by_content_group`
   负责是否按业务对象继续折叠结果

## 6. 为什么父子分块并不能替代 `group_by_content_group`

如果目标只是“从叶子块找到父块”，确实只需要 `parent_id`。

但如果目标是“把同一 QA / 同一表格行 / 同一 Excel 行下的多个命中收敛为一条业务结果”，就需要 `content_group_id`。

也就是说：

1. 做父子召回，不需要 `group_by_content_group`
2. 做业务聚合，才需要 `group_by_content_group`

## 7. 当前实现约束

1. `group_by_content_group` 不参与父子关系判断
2. `group_by_content_group` 不替代 `hierarchical_retrieval_mode`
3. 对 QA / 表格 / Excel 行碎片，即使关闭 `group_by_content_group`，最终结果仍必须回收到完整父块 / 完整行
4. `neighbor_window_size` 只负责叶子块邻域补充，不负责业务聚合
