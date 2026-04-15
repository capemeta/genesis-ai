# Markdown 分块与检索方案（当前实现）

> 文档版本: v3.0  
> 最后更新: 2026-02-24  
> 对应实现:
> - `genesis-ai-platform/rag/chunking/chunkers/markdown/parser.py`
> - `genesis-ai-platform/rag/chunking/chunkers/markdown/chunker.py`
> - `genesis-ai-platform/rag/chunking/chunkers/markdown/splitter.py`
> - `genesis-ai-platform/rag/chunking/chunkers/general/converter.py`
> - `genesis-ai-platform/services/chunk_service.py`

---

## 1. 目标与约束

### 1.1 核心目标

- 保持 Markdown 结构语义，优先避免把代码块/表格/列表等独立元素截断。
- 所有**叶子块（is_leaf=true）**满足嵌入模型 token 上限约束，且是向量化的唯一对象。
- 支持标题层级上下文在检索和 Prompt 拼接时复用。
- 拓扑结构可容纳任意深度，不限于三层。

### 1.2 铁律（当前实现）

- 所有上限判断统一按: `total_tokens = 内容token + 预算标题token`。
- 预算标题统一字段: `budget_header_text`。
- `header_path` 不降级（相邻章节合并后优先保持更具体路径）。
- **向量化以 `is_leaf=true` 为唯一判据**，不依赖 chunk_type 或绝对层级数字。

---

## 2. 拓扑角色字段体系

v3.0 起，用三个语义字段替代旧的 `level`（0/1/2）整数，支持任意深度树结构：

| 字段 | 类型 | 含义 |
|:---|:---|:---|
| `is_root` | bool | 是否是根节点（无父节点，`parent_id == null`） |
| `is_leaf` | bool | 是否是叶子节点（无子节点，`child_ids == []`）|
| `depth`   | int  | 从根算起的树深度（0=根，1=第一层子节点，2=第二层…，无上限）|

三字段组合覆盖四种拓扑角色：

| `is_root` | `is_leaf` | 语义 | `is_vectorized` |
|:---|:---|:---|:---|
| `True`  | `False` | **根块**（有子块的章节） | ❌ 不向量化 |
| `True`  | `True`  | **独立完整块**（小章节，无需拆分）| ✅ 向量化 |
| `False` | `False` | **中间块**（有父有子） | ❌ 不向量化 |
| `False` | `True`  | **叶子块**（检索单元）| ✅ 向量化 |

> ⚠️ `is_leaf` 由最终阶段 `_finalize_topology_flags()` 统一修正，以 `valid_child_ids` 是否为空为唯一判据，保证任何中间阶段（拆分、合并、建立层级）的操作都不会遗留错误状态。

---

## 3. 总体分块流程

```text
原始 Markdown
  -> Step 1: parser.parse_by_heading()
             按标题切 section + 相邻 section 迭代合并
  -> Step 2: _process_section() × N（对每个 section）
             2a. 小章节（< chunk_size * 1.5 且不超限）→ 只建章节块，不拆
             2b. 中等章节 → 章节块 + 子块（两层）
             2c. 大章节   → 章节块 + 父块 + 子块（三层）
             └── 内部流程：
                 - _build_atomic_blocks
                 - _reassemble_stage1_chunks（按 available_tokens 重组）
                 - _merge_small_chunks / _handle_last_chunk
                 - _create_parent_chunks_with_target（大章节）
                 - _split_oversized_independent_chunks（超限延迟拆分）
                 - _refresh_parent_chunks
                 - _establish_three_level_hierarchy / _establish_two_level_hierarchy
  -> Step 3: 组装 all_chunks（section + parent + child）
  -> Step 4: _finalize_topology_flags(all_chunks)
             最终修正 is_leaf / is_vectorized / 清理僵尸 child_ids
```

---

## 4. Step 1: 标题预分块与相邻合并

实现位置: `parser.py`

### 4.1 标题预分块

- 优先使用 `LlamaIndex MarkdownNodeParser`。
- 失败时回退 `_simple_parse_by_heading`（本地标题栈实现完整层级路径）。

section 关键字段:

| 字段 | 说明 |
|:---|:---|
| `text` | section 完整文本 |
| `heading` | 当前标题文字 |
| `level` | Markdown 标题层级（`#` 数量，文档结构用，非拓扑 depth）|
| `header_path` | 结构路径（用于结构定位）|
| `budget_header_text` | 预算标题（用于 token 预算）|
| `prompt_header_paths` | 标题路径列表（构造 prompt 用）|
| `prompt_header_text` | 给模型拼 Prompt 的标题文本 |
| `token_count` | section 内容 token 数 |

### 4.2 相邻 section 合并（`_merge_adjacent_sections`）

- 规则 A: 标题空壳块（只有标题或极少内容）优先并入后块。
- 规则 B: 同父级短小相邻块可合并（保守触发）。
- 合并约束: 合并后 `内容 + budget_header_text` 不得超过 `max_section_total_tokens`。
- 采用"迭代收敛"而非单轮扫描，直到本轮无合并发生。
- 合并后 `header_path` 不降级：使用后块更具体路径（优先 `sec2.header_path`）。

---

## 5. Step 2: section 内重组（`_process_section`）

### 5.1 可用预算

```python
budget_header_text = _get_budget_header_text(section)
available_tokens = embedding_model_limit - token(budget_header_text) - 10
```

### 5.2 三条策略路径

**策略 1（小章节）**：`section_tokens < chunk_size * 1.5` 且 `total_tokens <= embedding_model_limit`
- 只创建章节块，不拆分，直接返回 `[section_chunk], [], []`
- 此时 `is_root=True, is_leaf=True`（由 Step 4 终态修正）

**策略 2（中等章节）**：其余情况，不触发父块
- 章节块 + 子块，建立两层关系

**策略 3（大章节）**：`stage1_total_tokens >= chunk_size * 6`
- 章节块 + 父块 + 子块，建立三层关系

### 5.3 原子块构建

使用 `markdown-it` 将 section 切为：
- `plain`（普通文本段落）
- `protected`（代码、表格、列表、公式、HTML、引用等独立元素）

### 5.4 独立元素拆分策略（延迟）

- 阶段1 先保留"完整独立块"（不提前拆分）。
- 标记 `split_required=True`（内容超 chunk_size）或 `pending_split=True`（超嵌入上限）。
- `_split_oversized_independent_chunks` 阶段才实际拆分，拆分子块挂在完整块下。

最终层级示例：
```
大章节独立元素:  section → parent → 完整独立块 → 拆分子块
中等章节独立元素: section → 完整独立块 → 拆分子块
```

---

## 6. Step 4: 全局终态修正（`_finalize_topology_flags`）

这是 v3.0 新增的关键步骤，在所有分块和层级建立完成后执行。

**修正逻辑**（以实际 `valid_child_ids` 是否为空为唯一判据）：

```python
has_children = bool(valid_child_ids)
is_leaf = not has_children
is_vectorized = not has_children
```

**同时处理僵尸 child_ids**：过滤掉 `child_ids` 中指向不存在节点的 ID（因合并/删除导致）。

**覆盖的错误场景**：

| 场景 | 触发原因 | 修正效果 |
|:---|:---|:---|
| 小章节块 `is_leaf=False` | 策略1直接返回，从不进入 establish_hierarchy | → `is_leaf=True, is_vectorized=True` |
| 独立元素块 `is_leaf` 未同步 | 拆分后新增 child_ids，但原 is_leaf 未更新 | → `is_leaf=False, is_vectorized=False` |
| 僵尸 child_ids | 合并/删除 chunk 后，父块引用了已不存在的 node | → 清理 child_ids，重算 is_leaf |

---

## 7. 元数据规范（v3.0）

### 7.1 标题相关字段

| 字段 | 用途 |
|:---|:---|
| `header_path` | 结构路径（结构定位、过滤）|
| `budget_header_text` | token 预算标题 |
| `prompt_header_text` | Prompt 拼接标题 |
| `prompt_header_paths` | 标题路径列表（构造 prompt_header_text）|

### 7.2 拓扑与状态字段

| 字段 | 说明 |
|:---|:---|
| `node_id` | 全局唯一 UUID |
| `parent_id` | 父块 node_id（根块为 null）|
| `child_ids` | 直接子块 node_id 列表（叶子块为 []）|
| `section_id` | 所属章节块 node_id |
| `is_root` | 是否根节点 |
| `is_leaf` | 是否叶子节点（由终态修正保证准确）|
| `depth` | 从根算起的树深度（0=章节块，1=父块/一级子块，2+=更深）|
| `is_vectorized` | 是否需向量化（= is_leaf）|
| `is_hierarchical` | 是否开启了层级模式 |

### 7.3 典型 chunk 元数据示例（叶子块）

```json
{
  "node_id": "b4c2-...",
  "parent_id": "a1b3-...",
  "child_ids": [],
  "section_id": "f0e1-...",
  "is_root": false,
  "is_leaf": true,
  "depth": 2,
  "is_vectorized": true,
  "chunk_strategy": "markdown",
  "chunk_type": "paragraph",
  "heading": "核心理念",
  "header_path": "快速开始/核心理念",
  "budget_header_text": "快速开始/核心理念",
  "prompt_header_text": "快速开始/核心理念",
  "prompt_header_paths": ["快速开始/核心理念"],
  "token_count": 320,
  "total_tokens": 356,
  "is_hierarchical": true,
  "is_independent_element": false,
  "has_code": false,
  "has_table": false,
  "has_formula": false
}
```

---

## 8. 前端过滤与展示

### 8.1 视图过滤参数（`chunk_role`）

前端通过 `chunk_role` 参数过滤，后端 `chunk_service.py` 将其转换为 JSONB 字段查询：

| `chunk_role` | 后端过滤条件 | 含义 |
|:---|:---|:---|
| `leaf` | `is_leaf = true` | 叶子块（检索单元），RAG 主力 |
| `root` | `is_root = true` | 根块（章节大纲） |
| `intermediate` | `is_root = false AND is_leaf = false` | 中间块（上下文层）|

### 8.2 Badge 标签说明

| 状态组合 | Badge 标签 | 颜色 |
|:---|:---|:---|
| `is_root=T, is_leaf=F` | 根块（章节大纲）| 蓝色 |
| `is_root=T, is_leaf=T` | 独立完整块 | 紫色 |
| `is_root=F, is_leaf=F` | 中间块（上下文层）| 琥珀色 |
| `is_root=F, is_leaf=T` | 叶子块（检索单元）| 绿色 |

---

## 9. 检索与 Prompt 拼接建议

### 9.1 检索阶段

- **向量检索以 `is_leaf=true` 的块为主**（不依赖 chunk_type 或 depth）。
- 过滤和聚合可优先用：
  - `header_path`
  - `chunk_type`（paragraph/code/table/…）
  - `has_code / has_table / has_formula`
  - `section_id`（聚合同一章节的块）

### 9.2 Parent-Child 上下文增强（可选）

检索到叶子块后，可通过 `parent_id` 向上回溯获取更大上下文：

```
叶子块 → parent_id → 中间块/根块（包含更多上下文）
```

### 9.3 Prompt 组装

- 标题优先使用 `prompt_header_text`。
- 预算控制优先使用 `budget_header_text`。
- 不强依赖 parent/child 回溯也可运行（开发阶段可扁平化使用）。

---

## 10. GeneralChunker 的对齐

`general/converter.py` 也已统一使用相同的拓扑字段体系：

- `_determine_topology()` 根据 `parent_id`/`child_ids` 关系推导 `(is_root, is_leaf, depth)`。
- `is_vectorized = is_leaf`。
- 无 `level` 字段。

---

## 11. 当前实现边界

- 当环境缺少 `llama_index` 时，自动走回退解析器，结构可能比主解析粗糙。
- `markdown-it` 解析依赖环境安装；不可用时退化到段落级拆分。
- `depth` 字段理论上无上限，但实际场景中通常 ≤ 3（section=0, parent=1, child=2）。
- `_finalize_topology_flags` 是最终兜底，不依赖各中间阶段完整设置正确值。

---

## 12. 变更记录

### v3.0（2026-02-24）

- **重大变更**：移除 `level` 整数字段（旧 L0/L1/L2 绝对层级），改用语义化三字段：
  - `is_root`（bool）
  - `is_leaf`（bool）
  - `depth`（int，从根算起深度，无上限）
- 新增全局终态修正 `_finalize_topology_flags()`，修正 is_leaf/is_vectorized/清理僵尸 child_ids。
- 前端过滤参数从 `level` 改为 `chunk_role`（root/leaf/intermediate）。
- `chunk_service.py` 支持 `is_root`/`is_leaf` JSONB 布尔字段过滤。
- `general/converter.py` 同步对齐，`_determine_level` 改为 `_determine_topology`。
- `_establish_two_level_hierarchy` 新增 `_fix_depths` 递归修正 split 孙子块的 depth。

### v2.0（2026-02）

- 新增并统一预算字段 `budget_header_text`。
- 修复相邻 section 合并后的 `header_path` 降级问题。
- 将 section 合并从单轮改为迭代收敛。
- 标题相关字段在 section/parent/child/拆分块中统一透传。
- 明确并实现"先保留完整独立块，再延迟拆分且挂子关系"的层级策略。
