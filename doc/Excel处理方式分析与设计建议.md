# Excel知识库设计总览

> 说明：原《Excel处理方式分析与设计建议.md》已按知识库模式拆分。后续请按具体模式阅读对应文档，避免通用 Excel 与表格型 Excel 的设计混在一起。

---

## 一、文档拆分结果

- [Excel共享能力设计方案](./Excel共享能力设计方案.md)
- [Excel通用知识库设计方案](./Excel通用知识库设计方案.md)
- [Excel表格知识库设计方案](./Excel表格知识库设计方案.md)

---

## 二、如何选择

### 2.0 Excel 共享能力

适合阅读场景：

- 需要理解所有 Excel 模式共用的底层逻辑
- 关注解析增强、超长拆分、父子关系、来源追溯

请查看：

- [Excel共享能力设计方案](./Excel共享能力设计方案.md)

### 2.1 通用 Excel 知识库

适合：

- Excel 作为普通知识文档
- 重点是块级语义问答
- 不强调结构化过滤、统计、记录管理

请查看：

- [Excel通用知识库设计方案](./Excel通用知识库设计方案.md)

### 2.2 表格型 Excel 知识库

适合：

- Excel 作为结构化数据源
- 一行是一条记录
- 需要过滤、统计、聚合、记录视图

请查看：

- [Excel表格知识库设计方案](./Excel表格知识库设计方案.md)

---

## 三、当前开发主文档

当前阶段优先开发：

- [Excel表格知识库设计方案](./Excel表格知识库设计方案.md)

原因：

- 该模式承载了 schema、过滤、统计、批量导入、记录视图等核心能力
- 通用 Excel 可在后续作为通用文档处理能力增强项补齐

---

## 四、总原则

- 所有类型知识库均采用**知识库级全局配置为主，文档级仅做导入 override**
- 所有 Excel 模式的公共能力统一维护在 [Excel共享能力设计方案](./Excel共享能力设计方案.md)
- 表格型 Excel 采用 `file / row / chunk` 三层对象模型
- 表格型 Excel 的主使用体验应以“数据记录”为中心，而不是以“文件”为中心
- 通用 Excel 与表格型 Excel 必须分开设计、分开开发、分开维护

---

## 五、后续维护约定

- 新增与 Excel 共享底层能力相关的设计，写入 [Excel共享能力设计方案](./Excel共享能力设计方案.md)
- 新增与通用 Excel 相关的设计，写入 [Excel通用知识库设计方案](./Excel通用知识库设计方案.md)
- 新增与表格型 Excel 相关的设计，写入 [Excel表格知识库设计方案](./Excel表格知识库设计方案.md)
- 本文仅作为总览与导航，不再继续堆叠具体实现细节

### 4.1 解析阶段：改进 ExcelParser

**改进点 1：`read_only` 流式读取（参考 Dify）**

```python
# 流式读取，内存友好
wb = openpyxl.load_workbook(BytesIO(file_buffer), read_only=True, data_only=True)
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    for row in sheet.iter_rows(values_only=True):
        ...
```

注意：`read_only=True` 下无法访问 `merged_cells`。若文件 ≤50MB 且需要合并单元格处理，使用 `read_only=False`；若文件 >50MB，跳过合并单元格处理并记录 warning。

**改进点 2：智能表头检测（参考 Dify）**

```python
def _find_header_row(sheet, scan_rows: int = 10) -> int:
    """扫描前 scan_rows 行，选第一个有 >= 2 非空列的行（0-based）"""
    best_idx, best_count = 0, 0
    for row_idx, row in enumerate(sheet.iter_rows(max_row=scan_rows, values_only=True)):
        non_empty = sum(1 for cell in row if cell is not None and str(cell).strip())
        if non_empty >= 2:
            return row_idx  # 首选：第一个满足条件的行
        if non_empty > best_count:
            best_count, best_idx = non_empty, row_idx
    return best_idx  # 兜底：非空列数最多的行
```

**改进点 3：合并单元格回填（参考 MaxKB / KnowFlow）**

```python
# read_only=False 模式下处理合并单元格
for merge_range in sheet.merged_cells.ranges:
    top_left_value = sheet.cell(merge_range.min_row, merge_range.min_col).value
    for row in range(merge_range.min_row, merge_range.max_row + 1):
        for col in range(merge_range.min_col, merge_range.max_col + 1):
            sheet.cell(row, col).value = top_left_value
```

**改进点 4：超链接保留（参考 Dify）**

```python
# read_only=False 模式下才能访问 hyperlink
if hasattr(cell, "hyperlink") and cell.hyperlink and cell.hyperlink.target:
    value = f"[{cell.value}]({cell.hyperlink.target})"
```

**改进点 4b：日期 / 错误 / None 单元格规范化（参考 UltraRAG）**

```python
import datetime

def _normalize_cell_value(value) -> str:
    """规范化单元格值为字符串"""
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S") if value.hour or value.minute else value.strftime("%Y-%m-%d")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, bool):
        return "是" if value else "否"
    # xlrd/openpyxl 错误类型
    if hasattr(value, "error_code") or (isinstance(value, str) and value.startswith("#")):
        return ""  # 计算错误单元格静默置空
    return str(value).strip()
```

**改进点 4c：隐藏 Sheet 跳过（参考 UltraRAG）**

```python
# 默认跳过隐藏 Sheet，可通过 include_hidden_sheets=True 覆盖
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    if not include_hidden_sheets and sheet.sheet_state == "hidden":
        logger.debug(f"[ExcelParser] 跳过隐藏 Sheet: {sheet_name}")
        continue
```

**改进点 5：openpyxl → pandas 双重兜底（参考 KnowFlow）**

```python
try:
    result = self._parse_xlsx_openpyxl(file_buffer)
except Exception as e:
    logger.warning(f"[ExcelParser] openpyxl 解析失败，降级 pandas: {e}")
    result = self._parse_xlsx_pandas(file_buffer)
```

**改进点 6：结构化 metadata 输出**

```python
metadata = {
    "parse_method": "excel",
    "parser": "openpyxl",           # 或 "pandas_fallback"
    "sheets": [
        {
            "name": "Sheet1",
            "header_row": 0,        # 智能检测结果（0-based）
            "header": ["地区", "事项名称", "电话"],
            "row_count": 120,
            "col_count": 5,
            "column_types": {       # 列类型推断结果
                "地区": "text",
                "电话": "text",
                "行数": "int"
            },
            "has_merged_cells": True
        }
    ]
}
```

### 4.2 分块阶段：新增 ExcelGeneralChunker

- 策略名：`ChunkStrategy.EXCEL_GENERAL`，注册到 `factory.py`
- 核心逻辑：**表头 + 行累积** Markdown 块（参考 MaxKB）

**每块格式：**

```markdown
## Sheet1（第 1-30 行）

| 地区 | 事项名称 | 电话 |
| --- | --- | --- |
| 南康区 | 企业开办 | 002 |
| 上犹县 | 企业开办 | 003 |
...
```

**关键参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rows_per_chunk` | 30 | 每块包含的数据行数，可配置（1~100）|
| `excel_mode` | `"markdown"` | `"markdown"` 或 `"html"`（参考 KnowFlow）|
| `include_sheets` | `[]` | 空=全部 sheet；非空=只处理指定 sheet |
| `use_title_prefix` | `True` | 每块 content 前是否加 Sheet 名前缀（参考 UltraRAG）|
| `include_hidden_sheets` | `False` | 是否处理隐藏 Sheet（参考 UltraRAG）|

**`use_title_prefix` 效果（参考 UltraRAG）：**

开启时，每块 `content` 前自动加 Sheet 标题前缀：
```
[Sheet1] | 地区 | 事项名称 | 电话 |
| --- | --- | --- |
| 南康区 | 企业开办 | 002 |
...
```

多 Sheet 场景中不同 Sheet 的 chunk 在向量空间中有自然的语义区分，检索结果不会因内容相似而互相干扰。

**chunk 结构：**

```python
{
    "content": "[Sheet1] | 地区 | ... |\n| --- |\n| 南康区 | ...",
    "content_blocks": [{
        "block_id": "b1",
        "type": "table",
        "text": "<同 content>",
        "source_refs": [{
            "page_no": 0,
            "page_number": 1,
            "element_index": 1,       # row_start（1-based）
            "element_type": "table_block"
        }]
    }],
    "chunk_type": "table",
    "metadata_info": {
        "sheet_name": "Sheet1",
        "row_start": 1,
        "row_end": 30,
        "header": ["地区", "事项名称", "电话"],
        "chunk_strategy": "excel_general"
    }
}
```

### 4.3 Token 超限处理（通用模式）

通用模式下 token 超限触发场景：
- N 行累积后总文本超出 embedding 上限（减小 `rows_per_chunk` 可缓解）
- `rows_per_chunk=1` 时单行某列值极长（如"详细描述"列含数千字）

**降级策略：**

```
chunk content 超出 max_embed_tokens？
  ↓ 是
  第一步：自动减半 rows_per_chunk
    - 将当前块拆分为更小的块，直到 content 不超限
  ↓ 仍超（单行单列极长，即使 1 行/chunk 也超限）
  第二步：生成多个 overflow chunk
    - 按 token 预算拆分超长单元格值，产生多个子 chunk
    - 每个子 chunk 都复用同一份 Sheet 前缀和表头
    - metadata_info.is_row_overflow = true
    - metadata_info.overflow_part_index / overflow_part_total 标记分片顺序
    - content_blocks 始终保留完整原始行数据（展示不受影响）
```

**原则：`content_blocks`（展示层）始终不截断；`content`（向量化层）在超限时优先拆分为多个 overflow chunk，而不是硬截断吞掉尾部内容。**

### 4.4 可选：双表示配置（参考 KnowFlow / Dify）

知识库级别 `excel_display_mode` 配置：

| 值 | 说明 | 适用场景 |
|----|------|---------|
| `"markdown"`（默认）| 表头 + 行累积 Markdown，向量检索友好 | 大多数场景 |
| `"html"` | HTML 表格，每块 N 行 | 直接送 LLM 做表格推理时 |

---

## 五、模式二：表格知识库 Excel 设计建议

**目标**：Excel 是结构化数据源，"一行 = 一条记录"，支持精确过滤 + 行级召回。

### 5.0 解析器设计选择

表格模式采用**独立文件 `excel_table_parser.py`**，而非在 ExcelParser 中加 `table_mode=True` 参数。

理由：
- 两种模式输出结构完全不同（Markdown 文本 vs 结构化行列表），共用类代码分叉严重
- 表格模式需要列类型推断、`field_map` 回写等额外逻辑，独立文件更易维护和测试
- 两者仍可共享底层解析工具函数（智能表头检测、合并单元格回填、超链接处理）

### 5.1 知识库 Schema 管理（软约束）

```
首次导入 → 自动提取列名作为 KB Schema，写入 KB 配置

后续导入时校验：
  ├── 列名完全一致 → 正常导入
  ├── 是 Schema 子集（缺少某列）→ 警告提示 + 允许导入，缺失列填 null
  ├── 是 Schema 超集（多出新列）→ 提示用户"是否扩展 Schema"
  │     ├── 用户确认 → 更新 KB Schema，旧记录新列填 null
  │     └── 用户拒绝 → 多出的列被忽略，只导入已有列
  └── 列名完全不同 → 阻止导入 + 明确报错（"列结构与当前知识库不兼容"）
```

**设计意图：** 保留 Schema 约束带来的跨文档过滤和精准检索价值（严格模式的优点），同时允许业务自然演化（宽松模式的优点），Schema 变更有明确的用户确认节点。

### 5.2 知识库级别配置

```python
{
    # Schema 软约束（首次导入自动生成，后续导入校验）
    "schema": {
        "columns": [
            {
                "name": "地区",
                "type": "text",
                "nullable": False,
                "role": "dimension",     # dimension / entity / content / identifier
                "filterable": True,
                "aggregatable": True,
                "searchable": True,
            },
            {
                "name": "事项名称",
                "type": "text",
                "nullable": False,
                "role": "entity",
                "filterable": True,
                "aggregatable": True,
                "searchable": True,
            },
            {
                "name": "办理流程",
                "type": "text",
                "nullable": True,
                "role": "content",
                "filterable": False,
                "aggregatable": False,
                "searchable": True,
            },
            {
                "name": "电话",
                "type": "text",
                "nullable": True,
                "role": "content",
                "filterable": False,
                "aggregatable": False,
                "searchable": False,
            },
        ]
    },

    # 向量化列：空=由 searchable=true 且 role in [entity, content] 自动推导；非空=只用这些列
    "key_columns": ["事项名称", "办理流程"],

    # 术语标准化：优先知识库级，适用于跨文档共享的稳定业务术语
    "kb_term_mappings": {
        "事项名称": {
            "企业开办": {
                "aliases": ["开公司", "开一家公司", "注册公司", "办营业执照"],
                "description": "企业设立开办相关事项"
            }
        }
    },

    # 字段描述映射，导入后自动回写，供前端展示列定义（用户可手动调整）
    "field_map": {"地区": "region", "事项名称": "item_name"},

    # 表头配置：None=智能检测，整数=强制指定（1-based）
    "table_header_row": None,
    "table_data_start_row": None,

    # Sheet 选择：空=全部 Sheet；非空=只处理指定 Sheet
    "include_sheets": [],

    # 行文本前缀模板（可选，如 "政务事项: "）
    "text_prefix_template": "",

    # Token 超限配置（max_embed_tokens 优先从 KB 绑定的 embedding 模型读取）
    "max_embed_tokens": 512,
    "token_count_method": "chars",      # "chars"（快速近似）| "tokenizer"（精准）
    "overflow_strategy": "key_columns_first"
}
```

**配置设计说明：**

- 不再单独引入 `locator_columns`。长期方案中，字段是否适合定位、过滤、聚合、搜索，统一由 `schema.columns[*]` 上的 `role/filterable/aggregatable/searchable` 描述
- 不建议让用户手工配置数值型权重。最佳实践是：用户只配置字段角色，系统按角色自动推导默认检索策略
- `searchable=true` 只是对外统一配置；内部实现可再细分为 exact / full-text / embedding 三种检索路径，但不建议直接暴露给普通用户
- 当前阶段不单独设计“前端是否展示该列”配置。前端展示应由页面场景决定，而不是与检索能力字段耦合

### 5.2.1 长期存储结构：Row 层与 Chunk 层分离

表格知识库若要同时支持**语义问答**与**统计/枚举/聚合**，长期最佳实践不是只存 chunk，而是分为两层：

- **Row 层（结构化记录层）**：用于过滤、`count/group/distinct`、去重、枚举
- **Chunk 层（语义检索层）**：用于 embedding、全文召回、证据片段展示

建议新增一张通用行表 `kb_table_rows`，但**不做业务固定列**，而是统一存 JSONB：

```python
{
    "id": "...",
    "kb_id": "...",
    "doc_id": "...",
    "sheet_name": "Sheet1",
    "row_uid": "doc123:sheet1:row3",  # 一条业务记录的稳定主标识
    "row_index": 3,
    "row_data": {
        "地区": "南康区",
        "事项名称": "企业开办",
        "办理流程": "1.营业执照申请 2.刻章",
        "电话": "002"
    },
    "normalized_data": {
        "地区": "南康区",
        "事项名称": "企业开办"
    },
    "search_text": "事项名称: 企业开办; 办理流程: 1.营业执照申请 2.刻章",
    "created_at": "..."
}
```

设计原则：

- `row_data` 存原始结构化记录，保证通用性，不写死“地区/事项名称/主管部门”为物理列
- `normalized_data` 存标准化后的过滤值，供精确过滤与聚合使用
- `row_uid` 是统计与去重的核心键，一行即使被拆成多个 chunk，也始终只对应一个 `row_uid`
- 短期可以先用现有 PG JSONB 实现 `count/group/distinct`；长期若性能不足，再按高频字段补表达式索引或物化视图

### 5.2.2 术语标准化范围：当前版本仅做知识库级

术语标准化当前建议**只做知识库级，不做文档级 override**。

原因：

- 你当前是通用知识库，主诉求是跨文档统一检索与统一术语归一化
- 文档级 override 会显著增加配置复杂度、维护成本和排查难度
- 在没有大量真实案例证明“文档级差异明显影响召回效果”之前，过早引入文档级层次，收益通常不如成本高

推荐结构：

```python
{
    "kb_term_mappings": {
        "事项名称": {
            "企业开办": {
                "aliases": ["开公司", "开一家公司", "注册公司"]
            }
        }
    }
}
```

当前版本最佳实践：

- 默认只维护**知识库级术语 / 同义词**，作为整个知识库共享的主词库
- “专业术语解释”更偏回答增强；“同义词 / 别名”更偏检索归一化。两者可以共用管理界面，但内部语义应区分
- 后续若真实场景中出现大量“某文档专属简称 / 历史命名 / 局部缩写”影响检索，再评估是否增加文档级 override
- 在未引入文档级配置前，所有术语标准化结果都应可追溯到知识库级配置，方便前后端调试与用户理解

**与现有数据库设计的关系：**

- 现有 `kb_glossaries`（专业术语）与 `kb_synonyms`（同义词）采用**知识库级独立表**设计，本身就是通用能力，不依赖 Excel/Word/PDF/QA 等具体知识库类型
- 这套设计可以直接复用到表格知识库，不需要为了 Excel 再新增一套“表格术语表”
- 当前阶段表格能力建设应优先聚焦在**schema / row / chunk / 检索路由**，而不是扩展术语表层级
- 术语与同义词能力属于知识库的通用增强项，不应成为表格知识库上线的前置阻塞

### 5.3 解析阶段：ExcelTableParser

`rag/ingestion/parsers/excel/excel_table_parser.py`

不走 Markdown 转换，直接输出结构化行列表：

```python
@dataclass
class ExcelRowData:
    row_uid: str                # 稳定业务记录 id，格式建议：doc_id:sheet_name:row_index
    sheet_name: str
    row_index: int              # 原始行号（1-based，相对于数据区域，含表头偏移）
    header: list[str]           # 表头列名
    values: list[str]           # 当前行各列值（已 str 化）
    column_types: dict[str, str]  # 列类型推断结果 {"列名": "int/float/text/datetime/bool"}
```

**解析流程：**
1. 智能表头检测（共用底层工具函数）
2. 合并单元格回填
3. 列类型推断（扫描前 100 行样本）
4. 逐行产出 `ExcelRowData`
5. 解析完成后将 `field_map` 回写 KB 配置

### 5.4 分块阶段：ExcelTableChunker

- 策略名：`ChunkStrategy.EXCEL_TABLE`，注册到 `factory.py`
- 核心逻辑：**一行一条 row 记录；一行可对应一个或多个 chunk**。统计基于 row，语义召回基于 chunk

**`content` 构建规则（`字段: 值` 展开，参考 MaxKB / WeKnora 风格）：**

```python
# 统一格式：字段: 值; 字段: 值（MaxKB/WeKnora 风格，可读性最好）
content = "事项名称: 企业开办; 办理流程: 1.营业执照申请 2.刻章; 电话: 002"

# 格式规则：
# - 数值型列不加引号（价格: 6999）
# - 文本型列保留原值（名称: 张三）
# - 空值字段过滤掉，不出现在 content 中
# - filter_columns 的列不出现在 content 中（单独存 metadata）
# - 可选前缀模板：若配置 text_prefix_template = "政务事项: "
#   则 content = "政务事项: 事项名称: 企业开办; ..."
```

**chunk 结构：**

```python
{
    "content": "事项名称: 企业开办; 办理流程: ...",  # 向量化，只含 key_columns
    "content_blocks": [{
        "block_id": "b1",
        "type": "table",
        "text": "| 地区 | 事项名称 | 办理流程 | 电话 |\n|---|\n| 南康区 | 企业开办 | ... | 002 |",
        # 展示用单行 Markdown 表格（含表头 + 当前行，含全部列含 filter_columns）
        "source_refs": [{
            "page_no": 0,
            "page_number": 1,
            "element_index": 3,       # row_index（1-based）
            "element_type": "table_row"
        }]
    }],
    "chunk_type": "table",
    "metadata_info": {
        "chunk_strategy": "excel_table",
        "sheet_name": "Sheet1",
        "row_uid": "doc123:sheet1:row3",
        "row_index": 3,
        "header": ["地区", "事项名称", "办理流程", "电话"],
        "column_types": {"地区": "text", "电话": "text"},
        "filter_fields": {"地区": "南康区", "事项类型": "商事登记"},
        # filter_fields：仅存 schema 中 filterable=true 的字段标准值，用于检索前精确过滤
        "source_anchors": [],
        "page_numbers": [1],
        "primary_page_number": 1,
        "source_element_indices": [3]
    }
}
```

### 5.5 大表任务分片（调度层，参考 KnowFlow）

在 `chunk_task.py` 调度层实现，**不在 Chunker 内部**（Chunker 不应感知任务管理）：

```
单 sheet 行数 > TABLE_BATCH_SIZE（建议 3000 行）？
  ↓ 是 → 拆分为多个子任务
          task_1: row_from=0,    row_to=3000
          task_2: row_from=3000, row_to=6000
          ...
  每个子任务：
    - 从 ExcelTableParser 读取指定行窗口
    - 独立生成行级 chunk，写入 DB
    - 第一个子任务（row_from=0）额外生成 summary chunk
  ↓ 否 → 单任务处理
```

### 5.6 Token 超限处理（与通用模式共用 ExcelTokenHandler）

**问题根源：** chunk 级 token 超限，两种模式都会遇到。表格模式触发场景：宽表（列多）或含长文本列（备注/描述）时，单行 `字段: 值` 展开超限。

**三级降级策略（`ExcelTokenHandler` 统一实现）：**

```
行 content 超出 max_embed_tokens？
  ↓ 否 → 正常 embedding
  ↓ 是
  第一级：key_columns 过滤
    - 仅用 key_columns 列构建 content
    - filter_columns 始终存入 metadata_info.filter_fields，不受影响
    - content_blocks 始终保留全部列完整数据（展示不截断）
  ↓ 仍超
  第二级：按字段边界截列
    - 将 key_columns 逐字段累加到 content
    - 到达 token 上限时停止，不在字段值中间截断
    - 保留完整 "字段: 值" 颗粒
  ↓ 仍超（单个字段值本身极长，如"详细描述"列含数千字）
  第三级：字段值内拆分（最后兜底）
    - 对超长字段值做 RecursiveChunker 拆分
    - 拆出的多个 sub-chunk 共享同一 row_uid
    - metadata_info.is_row_overflow = true
    - 前端展示时需将同一 row_index 的多个 sub-chunk 合并回显
```

**Token 计量方式（`token_count_method` 配置）：**

| 方式 | 精度 | 性能 | 适用场景 |
|------|------|------|---------|
| `"chars"`（默认）| 近似（中文 1 字≈1.5token）| 快，无外部依赖 | 开发阶段，快速验证 |
| `"tokenizer"` | 精准 | 慢，需加载 tokenizer | 生产环境，与 embedding 模型对齐 |

### 5.7 可选增强：表语义 summary chunk（参考 WeKnora）

每个 sheet 在行级 chunk 之外额外生成 1 个 summary chunk：

```python
{
    "content": "表名: Sheet1，共 120 行，字段: 地区(text)、事项名称(text)、办理流程(text)、电话(text)，过滤列: 地区、事项类型",
    "chunk_type": "summary",
    "parent_id": None,  # 作为该文档分块树根节点
    "metadata_info": {
        "chunk_strategy": "excel_table_summary",
        "sheet_name": "Sheet1",
        "row_count": 120,
        "header": [...],
        "filter_columns": ["地区", "事项类型"]
    }
}
```

行级 chunk 的 `parent_id` 指向 summary chunk，通过现有 `path`（LTREE）字段建立父子关系。用途：回答"这张表是干什么的"类问题。

---

## 六、统一规范

### 6.1 `content` 字段键值对格式统一

7 个系统格式不一致，需要统一：

| 系统 | 格式 | 示例 |
|------|------|------|
| Dify | `"列名":"值"` | `"地区":"南康区";"事项":"企业开办"` |
| MaxKB / WeKnora | `字段: 值` | `地区: 南康区; 事项: 企业开办` |
| KnowFlow | `列名:值` | `地区:南康区;事项:企业开办` |

**统一采用 MaxKB / WeKnora 风格：`字段: 值; 字段: 值`（冒号后有空格，分号后有空格）**

理由：可读性最好，适合向量模型语义理解；中文列名不需要引号；与 `content_blocks.text` 的 Markdown 表格形成互补而非重复。

### 6.2 CSV 文件复用策略

两种模式均应兼容 CSV，不重复实现解析逻辑：

- CSV 通过 `BasicParser._parse_csv()` 输出与 ExcelParser 相同的结构化中间层（sheet_name 用文件名代替）
- 通用模式：CSV → ExcelGeneralChunker（天然无合并单元格，编码用 `charset_normalizer` 自动检测）
- 表格模式：CSV 更适合表格知识库，天然无合并单元格，建议优先推荐用户使用 CSV 导入

### 6.3 导入幂等性

表格模式下大表产生数千行 chunk，重新导入需保证安全：

- 重新解析前删除该 `kb_doc_id` 的所有旧 chunk（依赖现有 `kb_doc_id` 关联）
- 分片子任务需全部完成后再将文档状态改为 `complete`
- 若某子任务失败，整个文档标记为 `failed`，避免"部分行入库"的脏数据
- 任务日志记录每个子任务的 `row_from / row_to`，便于失败后重试指定分片

### 6.4 大表分片后 summary chunk 归属

- summary chunk 由**第一个子任务**（`row_from=0`）负责生成
- summary chunk 的 `parent_id = None`（文档分块树根节点）
- 后续子任务的行级 chunk 的 `parent_id` 指向 summary chunk 的 id
- summary chunk 的 `row_count` 在所有子任务完成后更新为实际总行数

### 6.5 前端交互设计：先定义结构，再上传文档

表格知识库与通用知识库最大的差异，不是上传后的解析细节，而是**建库阶段就要先定义结构化约束**。最佳实践是将前端流程拆成两步：

1. **新建知识库时定义表格 schema**
2. **上传文档时按 schema 校验**

不建议做成“先随便上传 Excel，再在解析后反推 schema”的交互，因为：

- 用户会在上传后才发现列不匹配，反馈太晚
- 前端无法在上传前明确展示哪些列可过滤、可聚合、可搜索
- 后端也难以判断这是“建库初始化导入”还是“向既有 schema 追加数据”

### 6.5.1 新建表格知识库前端建议流程

**步骤一：选择知识库模式**

- 通用知识库
- 表格知识库

当用户选择“表格知识库”后，创建表单应额外展示结构化配置区。

**步骤二：定义 schema**

前端建议提供“字段设计器”，每行一个字段，至少包含：

- 字段名
- 字段类型：`text / int / float / datetime / bool`
- 字段角色：`dimension / entity / content / identifier`
- 是否可过滤（`filterable`）
- 是否可聚合（`aggregatable`）
- 是否参与搜索（`searchable`）

交互原则：

- 普通用户优先通过“字段角色”完成配置，`filterable/aggregatable/searchable` 自动带出默认值
- 高级用户再允许手动微调开关
- 不建议让用户直接配置复杂检索权重；易用性差，且结果往往不可解释

**步骤三：配置导入规则**

- 表头行：自动检测 / 手动指定
- 允许的 Sheet：全部 / 指定 Sheet
- Schema 校验策略：
  - 完全一致
  - 允许缺列
  - 允许新增列但需确认

**步骤四：保存知识库**

建库成功后，知识库的 `schema.columns` 作为后续所有表格导入的校验依据。

### 6.5.2 上传文档时的前端交互建议

上传 Excel 到表格知识库时，前端不应只是显示上传进度，还应有一个**解析预检 / 校验确认**步骤。

建议流程：

```
选择文件
  ↓
后端快速预解析（仅表头、Sheet、少量样本与列差异，不做完整入库）
  ↓
返回预检结果
  - 检测到的 Sheet
  - 检测到的表头
  - 与 KB schema 的差异
  - 样本预览（单文件场景）
  - 批量导入汇总（批量场景）
  ↓
用户确认后再正式导入
```

前端应展示的关键信息：

- 检测出的表头行位置
- 列名映射结果
- 缺失列
- 多余列
- 类型疑似不一致列
- 是否存在空表 / 多 Sheet 结构不一致

批量导入时不建议为每个文件都默认展开“前几行样本”，否则前端会非常冗长。更合理的方式是：

- 默认展示批量预检汇总：成功数、警告数、阻塞数
- 默认展示异常文件列表：仅对有 warning / blocked 的文件重点提示
- 用户点击某个文件时，再懒加载该文件的表头与样本预览
- 对完全通过的文件，默认不展开样本，只显示“校验通过”

### 6.5.3 列一致性校验策略

上传时建议采用分级校验，而不是简单“能导就导”：

- **完全一致**：直接导入
- **缺少部分非必填列**：提示 warning，允许导入
- **多出新列**：提示用户“当前知识库 schema 未定义这些列”，默认阻止；后续若支持 schema 扩展，再提供确认入口
- **核心列缺失 / 列名完全不匹配**：阻止导入
- **字段类型明显冲突**：提示 warning 或阻止，视字段配置而定

这里前端要承担的重要职责不是做业务判断，而是把差异**可视化**给用户，让用户知道为什么不能导入。

### 6.5.4 建议的前端页面结构

表格知识库详情页建议至少包含以下区域：

- **结构定义**：查看和编辑 `schema.columns`
- **文档导入**：上传 Excel / CSV，并展示预检结果与导入历史
- **字段能力说明**：哪些列可过滤、可聚合、可搜索
- **术语与同义词**：直接复用现有知识库级能力，不单独为 Excel 再做一套入口

如果要做“创建知识库”弹窗，建议不要把所有高级配置都塞进一个弹窗；更适合做成**分步式创建**：

- 第一步：基础信息
- 第二步：字段结构
- 第三步：导入规则
- 第四步：首批文件上传（可选）

### 6.5.5 当前阶段最值得优先做的前端能力

为了尽快把表格 Excel 能力上线，前端优先级建议如下：

**P0**
- 新建表格知识库时支持定义 `schema.columns`
- 支持字段角色与基础能力开关
- 上传时支持预解析并校验列一致性
- 在导入结果中清晰展示“哪些列不一致”

**P1**
- 支持首批 Excel 作为“初始化 schema 来源”快速建库
- 支持单文件导入前样本预览；批量导入仅对异常文件按需展开样本
- 支持手动指定表头行 / Sheet

**P2**
- 支持图形化调整字段能力
- 支持更细的 schema 变更确认流程
- 支持导入历史与失败原因回放

### 6.6 前后端接口草案

为了让“先定义结构、再上传校验”真正落地，建议至少补齐四类接口：

1. 创建表格知识库
2. 获取 / 更新 schema
3. 上传前预解析校验
4. 确认导入

### 6.6.1 创建表格知识库

`POST /api/v1/knowledge-bases`

```json
{
  "name": "政务事项库",
  "description": "用于政务事项查询",
  "kb_mode": "table",
  "schema": {
    "columns": [
      {
        "name": "地区",
        "type": "text",
        "role": "dimension",
        "nullable": false,
        "filterable": true,
        "aggregatable": true,
        "searchable": true
      },
      {
        "name": "事项名称",
        "type": "text",
        "role": "entity",
        "nullable": false,
        "filterable": true,
        "aggregatable": true,
        "searchable": true
      },
      {
        "name": "办理流程",
        "type": "text",
        "role": "content",
        "nullable": true,
        "filterable": false,
        "aggregatable": false,
        "searchable": true
      }
    ],
    "header_policy": {
      "table_header_row": null,
      "include_sheets": [],
      "validation_mode": "strict"
    }
  }
}
```

响应建议返回：

- `kb_id`
- 最终保存的 `schema`
- 字段默认策略推导结果
- 是否允许立即上传首批文件

### 6.6.2 获取 / 更新 schema

`GET /api/v1/knowledge-bases/{kb_id}/table-schema`

返回当前知识库的表格 schema 与字段能力定义，供前端详情页编辑。

`PUT /api/v1/knowledge-bases/{kb_id}/table-schema`

用于修改字段结构。建议限制：

- 若知识库尚无数据，可自由编辑
- 若已有导入数据，只允许有限修改
  - 修改展示属性
  - 新增非必填字段
  - 调整部分字段能力开关
- 涉及破坏性变更（删除字段、重命名核心字段、改字段类型）时，应阻止或走单独确认流程

### 6.6.3 上传前预解析校验

`POST /api/v1/knowledge-bases/{kb_id}/documents/precheck-table-import`

用途：上传文件后，先做轻量预解析，不立即正式入库。

请求建议：

```json
{
  "document_id": "doc_xxx",
  "options": {
    "table_header_row": null,
    "include_sheets": [],
    "sample_rows": 5
  }
}
```

返回建议：

```json
{
  "ok": false,
  "summary": {
    "sheet_count": 2,
    "selected_sheets": ["Sheet1"],
    "detected_header_row": 2
  },
  "schema_check": {
    "status": "warning",
    "validation_mode": "strict",
    "matched_columns": ["地区", "事项名称", "办理流程"],
    "missing_columns": ["主管部门"],
    "extra_columns": ["联系电话"],
    "type_conflicts": [
      {
        "column": "办理时限",
        "expected": "int",
        "detected": "text"
      }
    ]
  },
  "sheet_previews": [
    {
      "sheet_name": "Sheet1",
      "header": ["地区", "事项名称", "办理流程", "联系电话"],
      "sample_rows": [
        ["南康区", "企业开办", "1.营业执照申请", "002"]
      ]
    }
  ],
  "blocking_issues": [
    "缺少核心字段：主管部门"
  ],
  "warnings": [
    "检测到新增列：联系电话"
  ]
}
```

接口目标不是完成导入，而是给前端足够信息做确认页。

### 6.6.4 确认正式导入

`POST /api/v1/knowledge-bases/{kb_id}/documents/confirm-table-import`

请求建议：

```json
{
  "document_id": "doc_xxx",
  "precheck_id": "precheck_xxx",
  "import_options": {
    "selected_sheets": ["Sheet1"],
    "table_header_row": 2,
    "ignore_extra_columns": true
  }
}
```

返回：

- `task_id`
- 导入任务状态
- 最终采用的 schema 映射结果

### 6.6.5 前端状态模型建议

前端为了支撑分步式交互，建议维护以下状态：

```ts
type TableSchemaColumn = {
  name: string
  type: 'text' | 'int' | 'float' | 'datetime' | 'bool'
  role: 'dimension' | 'entity' | 'content' | 'identifier'
  nullable: boolean
  filterable: boolean
  aggregatable: boolean
  searchable: boolean
}

type TableImportPrecheckResult = {
  ok: boolean
  batch_mode?: boolean
  summary: {
    file_count?: number
    pass_count?: number
    warning_count?: number
    blocked_count?: number
    sheet_count: number
    selected_sheets: string[]
    detected_header_row: number | null
  }
  schema_check: {
    status: 'pass' | 'warning' | 'blocked'
    validation_mode: 'strict' | 'allow_missing'
    matched_columns: string[]
    missing_columns: string[]
    extra_columns: string[]
    type_conflicts: Array<{
      column: string
      expected: string
      detected: string
    }>
  }
  sheet_previews: Array<{
    sheet_name: string
    header: string[]
    sample_rows: string[][]
  }>
  file_results?: Array<{
    document_id: string
    file_name: string
    status: 'pass' | 'warning' | 'blocked'
    blocking_issues: string[]
    warnings: string[]
  }>
  blocking_issues: string[]
  warnings: string[]
}
```

这样前端很容易拆成：

- 建库表单状态
- schema 编辑器状态
- 导入预检结果状态
- 导入确认页状态

### 6.6.6 校验结果的展示优先级

为了提升易用性，前端展示时建议按优先级排序：

1. 阻塞问题：必须先解决，否则不能导入
2. 风险告警：可导入，但结果可能不符合预期
3. 样本预览 / 异常文件明细：帮助用户快速确认是否识别对了表头与字段
4. 最终导入选项：Sheet、表头行、是否忽略新增列

这样用户看到页面时，能第一眼知道“能不能导、为什么不能导、改哪里能导”。

---

## 七、检索层配套设计（摄入完成后需实现）

过滤列在摄入侧落地后，检索侧需要配套实现才能发挥作用：

```
用户问：南康区 企业开办 怎么办理？

传统向量检索（有问题）：
  所有文档向量相似度排序 → 章贡区结果排在南康区前面

有过滤列的检索（正确）：
  Step 1：从问题提取过滤条件（实体识别 or 用户显式指定）
          filter = {"地区": "南康区"}
  Step 2：先精确过滤 WHERE metadata->>'地区' = '南康区'
  Step 3：再在过滤结果内做向量相似度排序
  结果：只在南康区的记录里召回，彻底隔离其他地区
```

**具体实现方向：**
- `metadata_info.filter_fields` 存入向量数据库的 metadata 字段，建立索引
- 检索 API 支持 `metadata_filter` 参数：`{"地区": "南康区"}`
- 可选：NER 实体识别自动提取过滤条件（高级功能）
- 可选：前端对话框提供"过滤列"下拉选择器（快捷过滤）

### 7.1 设计原则：不要把“精确过滤”建立在一次性 NER 成功之上

对于表格类知识库，**精确过滤确实不好做**，如果方案只有“先从用户问题里提取专业词，再去过滤”，上线后会很脆弱，原因有三类：

- 用户经常说口语，不直接说表里的标准值，例如表内术语是“企业开办”，用户会说“我要开一家公司”“注册公司怎么办”
- 多轮对话里，过滤条件常常分布在上下文中，本轮只说“那南康区呢”“这个要多久”，不能只看当前一句
- 有些过滤值不是开放语义，而是强结构化值，例如事项编码、统一社会信用代码、产品 SKU、员工工号，这类值不应该交给向量语义去“猜”

因此，检索层应设计成**结构化检索规划（retrieval planning）**，而不是单一步骤的“query 改写 + 实体提取”。

### 7.2 建议的四阶段检索规划

```
用户问题 + 对话历史
  ↓
Stage 1：上下文改写（只补全省略，不做术语定稿）
  ↓
Stage 2：槽位提取（地区 / 事项名称 / 部门 / 时间 / 编码等）
  ↓
Stage 3：术语标准化（口语 -> 标准术语；别名 -> canonical value）
  ↓
Stage 4：路由检索
    ├── 命中 identifier 字段   → 精确直查
    ├── 命中 filterable 字段   → 先 metadata / row 过滤，再向量召回
    ├── 命中 aggregatable 字段 + 统计意图 → 走 row 层聚合查询
    └── 未命中过滤条件          → 常规语义召回
```

核心原则：

- **改写**只负责补全省略指代，不负责拍脑袋生成标准术语
- **提取**输出的是候选槽位，不要求一步到位命中最终库内值
- **标准化**负责把“开公司”映射为“企业开办”这类 canonical value
- **检索路由**根据字段角色选择“直查 / 过滤后召回 / row 聚合 / 普通召回”，不要所有问题都走同一条链路

### 7.3 口语词与专业术语的转换设计

建议在知识库配置层引入**术语标准化字典**，不要完全依赖大模型临场发挥：

```python
{
    "kb_term_mappings": {
        "事项名称": {
            "企业开办": {
                "aliases": ["开公司", "开一家公司", "注册公司", "新办营业执照"],
                "description": "企业设立开办相关事项"
            },
            "企业变更登记": {
                "aliases": ["公司信息变更", "改营业执照", "法人变更", "公司变更"]
            }
        }
    }
}
```

执行时分三层：

1. **规则层**：先做完全匹配、同义词词典匹配、编辑距离匹配，成本低且稳定
2. **模型层**：规则层未命中时，再让模型做“候选标准术语归一化”
3. **确认层**：若命中多个可能术语（如“开公司”可能对应“企业开办”或“个体工商户设立”），返回澄清问题，而不是静默误过滤

示例：

```
用户问：我要开一家公司，需要准备什么材料？

改写后：用户想咨询开公司的办理材料
槽位提取：{"事项名称": "开一家公司"}
标准化后：{"事项名称": "企业开办"}
检索执行：metadata_filter={"事项名称": "企业开办"} + 向量召回“办理材料/流程”相关列
```

### 7.4 多轮对话下的过滤槽位记忆

表格知识库检索必须引入**会话级槽位状态**，不能每轮都从零提取。

建议为每个会话维护：

```python
{
    "retrieval_slots": {
        "地区": "南康区",
        "事项名称": "企业开办",
        "事项类型": None,
        "事项编码": None
    },
    "slot_sources": {
        "地区": "turn_3",
        "事项名称": "turn_2"
    }
}
```

更新规则：

- 当前轮显式给出新值，则覆盖旧槽位
- 当前轮只有代词/省略（如“那这个怎么办”“南康区呢”），先结合历史槽位补全
- 当前轮与历史冲突时，以当前轮显式值优先
- 长时间未使用或主题切换后，可衰减或清空槽位，避免脏继承

示例：

```
第 1 轮：我要开一家公司
  -> 事项名称标准化为 企业开办

第 2 轮：南康区呢
  -> 从历史继承 事项名称=企业开办
  -> 当前轮补充 地区=南康区

最终检索条件：
  {"事项名称": "企业开办", "地区": "南康区"}
```

### 7.5 `identifier` 字段要走独立通道

你提到的“类似数据库主键这种过滤”，本质上不只是过滤，更像**精确定位**，应该由字段角色 `identifier` 单独处理：

- `identifier` 型字段：事项编码、统一社会信用代码、证照编号、产品 SKU、员工工号等
- 命中这类字段时，优先走 `WHERE primary_key = ?` 的直查路径
- 直查失败时，再考虑别名映射或降级到普通过滤
- 这条路径应绕过 query rewrite 的语义生成，避免把编码值改坏

示例：

```
用户问：344201001 这个事项怎么办？

槽位提取：{"事项编码": "344201001"}
检索路由：命中 identifier 字段
执行：先按 事项编码=344201001 精确直查
结果：直接定位到唯一记录，再回答办理流程/材料/时限
```

### 7.6 检索接口建议升级

当前检索接口若只有 `query + metadata_filter` 还不够，建议扩展为：

```python
{
    "query": "我要开一家公司，南康区怎么办",
    "rewritten_query": "咨询南康区企业开办的办理方式",
    "retrieval_slots": {
        "事项名称": {
            "raw": "开一家公司",
            "canonical": "企业开办",
            "match_type": "synonym_dict"
        },
        "地区": {
            "raw": "南康区",
            "canonical": "南康区",
            "match_type": "exact"
        }
    },
    "metadata_filter": {
        "事项名称": "企业开办",
        "地区": "南康区"
    },
    "lookup_keys": {},
    "retrieval_route": "filter_then_vector"
}
```

这样做的价值：

- 方便排查“为什么这次命中了企业开办”
- 方便前端展示“已识别筛选条件”
- 方便多轮对话继承 canonical 槽位，而不是反复从自然语言重算

### 7.7 实施优先级建议

为了降低实现复杂度，建议分三期落地：

**第一期（必须）**
- 支持 `schema.columns[*].role/filterable/aggregatable/searchable`
- 支持知识库级 `kb_term_mappings`
- 支持 `row_uid` 与 row/chunk 分层
- 支持会话级 retrieval slots 记忆

**第二期（增强）**
- 增加 LLM 归一化兜底
- 增加歧义澄清
- 前端展示当前识别出的过滤条件

**第三期（高级）**
- 基于历史问答自动扩充别名词典
- 对不同字段采用不同归一化器（地区/事项/机构/时间）
- 加入规则 + 模型融合的 retrieval planner 评估集

---

## 八、两种模式对比与选型建议

| 维度 | 通用知识库（ExcelGeneralChunker）| 表格知识库（ExcelTableChunker）|
|------|--------------------------------|-------------------------------|
| 分块粒度 | 表头 + N 行（默认 30 行）| 每行 1 chunk |
| `content` 语义 | Markdown 表格文本 | `字段: 值` 自然语言展开 |
| `content_blocks` | 完整 N 行表格（块级展示）| 单行 Markdown 表格含表头（行级回显）|
| 过滤列支持 | 无 | 有（`filter_fields` 存 metadata）|
| Schema 管理 | 无 | 有（软约束，首次导入定义）|
| 适合场景 | 说明性表格 / 配置表 / 宽表少行 / 临时知识 | 记录型表格 / 产品库 / 政务事项库 / 大数据量 |
| 检索精度 | 中（块内含多行，可能混入相邻记录）| 高（精确到行，支持精确过滤）|
| chunk 数量 | 少（行数 / rows_per_chunk）| 多（= 数据行数）|
| Token 超限风险 | 低（rows_per_chunk 可调）| 中（宽表 + 长文本列时触发）|
| 大表处理 | rows_per_chunk 调小即可 | 需调度层分片（>3000 行）|
| 实现复杂度 | 低 | 高（Schema 管理 + 过滤列 + 分片）|

**选型建议：**
- 用户想上传 Excel 做语义问答、不关心具体某行 → 通用知识库
- 用户有结构化记录数据，需要精确召回某条记录、按某列过滤 → 表格知识库
- 政务事项、产品目录、人员名册等场景 → 强烈推荐表格知识库

---

## 九、设计反思与遗漏点

### 9.1 `read_only` 与合并单元格的根本矛盾

openpyxl 的 `read_only=True` 节省内存（大文件必须），但无法访问 `merged_cells`；而合并单元格回填需要此信息。两个功能无法同时满足。

**解决方案（按文件大小分策略）：**

```python
if file_size <= 50 * 1024 * 1024:  # <= 50MB
    # full load，支持合并单元格回填
    wb = load_workbook(read_only=False, data_only=True)
    # ... 处理 merged_cells
else:
    # 流式读取，跳过合并单元格处理
    wb = load_workbook(read_only=True, data_only=True)
    logger.warning("文件过大，跳过合并单元格处理")
```

### 9.2 max_embed_tokens 不应硬编码

`max_embed_tokens` 应从 KB 绑定的 embedding 模型配置动态读取，而非写死在 KB 配置中。不同模型上限差异极大（text-embedding-3-small: 8191 token；BGE-small: 512 token）。知识库配置中的值仅作为兜底默认值。

### 9.3 第三级降级打破"一行一chunk"语义

第三级（字段值内拆分）是最后兜底方案，会产生多个 sub-chunk 共享同一 `row_index`。前端展示时需要将同一 `row_index` 的多个 sub-chunk 合并回显，否则用户会看到"半条记录"。建议在 chunk 列表接口中增加 `is_row_overflow` 过滤条件，方便前端处理。

### 9.4 智能表头检测的误判场景

当 Excel 前几行是说明文字（在政府数据 Excel 中极为常见，如"本表格由xxx部门发布，请勿修改"）时，算法可能误判表头位置。`table_header_row` 手动覆盖配置项是必要的兜底手段。

### 9.5 多 Sheet 下表格模式的语义问题

多个 Sheet 应各自独立处理（每个 Sheet 视为独立的"数据表"）：
- 各自生成独立的 summary chunk 和行级 chunk
- `metadata_info.sheet_name` 作为区分标识
- 若多个 Sheet 结构不同，Schema 软约束以第一个非空 Sheet 的列名为准

### 9.6 Schema 列名模糊匹配

同一列名可能因导出版本不同而有细微差异（"地区" vs "所在地区"，"事项名称" vs "事项"），严格字符串匹配会误判为"列名完全不同"而拒绝导入。可考虑：计算 Levenshtein 相似度，相似度 >0.8 时给出警告而非直接拒绝，让用户决策。

### 9.7 列类型推断的精度问题

日期格式多样（`2024/1/1` vs `2024-01-01` vs `20240101` vs Excel 日期序列号），简单字符串匹配容易误判。建议：
- 对 datetime 类型：先尝试 `pandas.to_datetime(errors='coerce')`，成功率高
- 扫描前 100 行作为推断样本，而非整列
- 推断结果存 metadata 供参考，不做强约束（用户可手动覆盖）

### 9.8 通用模式下 `rows_per_chunk` 最小值问题

`rows_per_chunk=1` 时，通用模式退化为类似表格模式（一行一块），但缺少表格模式的 filter_fields 和精确过滤能力。如果用户将 `rows_per_chunk` 设为 1，应在前端提示"建议改用表格知识库模式以获得更好的检索效果"。

### 9.9 `use_title_prefix` 带来的 content 膨胀

为每块 `content` 加 Sheet 名前缀（参考 UltraRAG）是低成本操作，但如果 Sheet 名称本身很长或存在大量相同 Sheet 名（如"数据1"、"数据2"），前缀的区分价值会降低。建议：
- 前缀格式保持简洁：`[{sheet_name}]`，而非 `Title:\n{sheet_name}\n\nContent:\n`（UltraRAG 的格式对 token 消耗偏多）
- 若知识库只有单 Sheet，可关闭 `use_title_prefix`（默认开启，自动检测）

### 9.10 公式缓存值 None 的静默行为

`data_only=True` 时公式格缓存 None 会被替换为空字符串（参考 UltraRAG），这是正确行为，但可能导致"某列数据大量为空"的假象，误导用户以为数据有问题。建议：
- 在解析结果 metadata 中统计 `formula_none_cells: int`（公式缓存为 None 的单元格数量）
- 当该值超过数据行数的 10% 时，向解析结果追加 warning：`"部分公式单元格无缓存值（建议先在 Excel 中打开保存后再上传）"`

### 9.11 精确过滤对“术语标准化”的依赖不可低估

表格知识库的精确过滤，不难在数据库层实现，难点主要在**检索前语义规划**：

- 用户说的是自然语言，表里存的是标准值
- 多轮对话里当前轮常常没有完整条件
- 不同字段的标准化方式完全不同：地区像枚举，事项名称像术语词典，事项编码像主键直查

因此不能把所有字段都交给统一的“query rewrite + NER”处理。更合理的方式是：

- 枚举/字典型字段：走 canonical 映射
- 主键/编号型字段：走精确直查
- 自由文本字段：走向量召回

也就是说，**真正难的不是 filter 本身，而是 filter 前的 query understanding 分层设计。**

### 9.12 长期统计能力不能建立在 chunk 层上

`count(*) / group by / distinct` 这类统计类问题，不能建立在 chunk 层结果上，否则会遇到：

- 一行超长被拆成多个 chunk，统计重复
- summary chunk 混入统计，结果污染
- 向量召回天然不是全量集合，无法保证统计正确

长期最佳实践：

- 统计、枚举、去重、存在性判断一律基于 **row 层**
- 语义问答、证据召回、片段展示一律基于 **chunk 层**
- 同一业务记录通过 `row_uid` 连接 row 与 chunk

也就是说，表格知识库本质上应是**结构化查询 + 语义检索双引擎**，而不是“所有问题都交给 RAG”

### 9.13 产品交互定稿（当前阶段）

基于当前讨论，表格知识库的产品交互与对象模型先定为以下方案，后续开发按此执行：

**1. 配置层级**

- 所有类型知识库都采用**知识库级全局配置为主，文档级仅做导入 override** 的思路
- 当前阶段不展开文档级配置实现，先复用现有知识库全局配置入口完成表格知识库能力建设
- 表格知识库相关配置统一放在知识库详情中的全局配置区域，不额外新开独立配置体系

**2. 表格知识库的核心配置内容**

- `schema.columns`
- 字段角色：`dimension / entity / content / identifier`
- 字段能力：`filterable / aggregatable / searchable`
- 表头识别策略
- 导入校验策略
- 知识库级术语 / 同义词

也就是说，当前阶段的重点不是扩展术语体系层级，而是把表格 schema 与导入校验流程先落地。

**3. 视图模型**

- 表格知识库不能只按文件管理，也不能只按记录管理
- 最终采用**双视图**：
  - **数据视图**：作为主视图，面向记录查询、筛选、统计、使用
  - **文件视图**：作为辅视图，面向导入治理、失败排查、重试、删除来源文件

设计原则：

- 底层仍保留文件对象，保证导入链路、追溯、重试、删除来源文件等能力
- 前端主使用体验以“数据记录”为中心，而不是以“文件”为中心

**4. 上传与导入交互**

- 上传动作保持轻量，不在上传弹窗中塞入过多高级配置
- 上传完成后，文件进入“待校验 / 待确认导入”状态
- 系统先按知识库全局配置自动预检
- 用户在文件视图中进行单条或批量确认

推荐流程：

```text
上传文件
  -> 自动预检
  -> 文件进入待确认状态
  -> 用户查看校验结果
  -> 单条/批量确认导入
  -> 正式入库
```

**5. 预检结果展示原则**

- 单文件导入：可展示表头、字段差异、少量样本预览
- 批量导入：默认展示汇总与异常文件，不默认展开每个文件的样本
- 只有用户点开某个异常文件时，再按需展示该文件的表头和样本

这样既兼顾批量导入效率，也保留排查问题所需的可解释性。

**6. 底层对象模型**

- **file**：导入来源与治理对象
- **row**：结构化记录对象，承担过滤、统计、聚合
- **chunk**：检索片段对象，承担全文 / 向量召回

职责边界：

- 过滤、计数、分组、枚举、去重基于 `row`
- 语义问答、证据召回、分块展示基于 `chunk`
- 文件导入、失败重试、来源追溯基于 `file`

**结论：**

当前阶段已经可以进入开发，不需要再继续扩散讨论。开发顺序建议为：

1. 先补表格知识库的知识库级全局配置能力
2. 再补上传后的预检与列一致性校验
3. 再补文件视图中的确认导入与批量操作
4. 最后补数据视图中的记录查看、过滤与统计能力

---

## 十、实现文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `rag/ingestion/parsers/excel/excel_parser.py` | 修改 | 增加智能表头检测、合并单元格回填（按文件大小分策略）、超链接转 Markdown、日期/错误/None 单元格规范化、隐藏 Sheet 跳过（可配置）、openpyxl→pandas 降级兜底、列类型推断、结构化 metadata 输出 |
| `rag/ingestion/parsers/excel/excel_table_parser.py` | 新增 | 表格模式专用解析器，输出结构化 `ExcelRowData` 列表，含列类型推断和 field_map 回写 KB 配置 |
| `rag/ingestion/chunkers/excel_general_chunker.py` | 新增 | 表头 + 行累积 Markdown 块，支持 markdown/html 双表示，chunk_type=table |
| `rag/ingestion/chunkers/excel_table_chunker.py` | 新增 | 一行一 chunk，filter_fields 存 metadata_info，生成 summary chunk（可选）|
| `rag/ingestion/chunkers/excel_token_handler.py` | 新增 | 两种 Chunker 共用的 token 超限三级降级工具类（ExcelTokenHandler）|
| `rag/ingestion/chunkers/factory.py` | 修改 | 注册 `ChunkStrategy.EXCEL_GENERAL` 和 `ChunkStrategy.EXCEL_TABLE` 两个新策略 |
| `rag/ingestion/tasks/chunk_task.py` | 修改 | 表格模式大表行窗口分片调度逻辑（3000 行/批）；excel chunk 的 source_refs 填充 |
