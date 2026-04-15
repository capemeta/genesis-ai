# Excel表格知识库设计方案

> 适用范围：将 Excel 作为结构化数据源处理，核心目标是**记录级管理、精确过滤、统计聚合、结构化查询与语义检索结合**。

> 当前开发主文档：后续实现以本文件为准。

> 共享能力说明：解析增强、超长内容拆分、父子关系、来源追溯等公共逻辑，请同时参考 [Excel共享能力设计方案](./Excel共享能力设计方案.md)。

> 前端工作台说明：关于多类型知识库统一工作台、二级视图与性能约束，请同时参考 [知识库工作台与多类型视图设计方案](./知识库工作台与多类型视图设计方案.md)。

---

## 一、定位

表格型 Excel 知识库适合：

- 政务事项库
- 产品目录
- 人员名册
- 结构化业务台账

它的核心不是“文件切片”，而是：

- 一行是一条业务记录
- 记录可过滤、可统计、可枚举
- 长文本字段仍可做语义问答

---

## 二、核心结论

### 2.1 配置模式

- 采用**知识库级全局配置为主**
- 文档级仅允许导入 override
- 当前阶段先基于现有知识库全局配置入口开发，不扩展文档级配置实现

### 2.2 视图模式

采用**三视图**：

- **数据视图**：主视图，直接展示真实记录行，面向记录查询、过滤、统计、使用；不能设计成 chunk 浏览页
- **文件视图**：辅视图，面向导入治理、预检、失败排查、重试
- **结构定义视图**：主流程配置视图，面向 schema、字段用途、关键字段、导入校验与映射规则

补充约束：

- 数据视图只围绕 `kb_table_rows` 展开：查看、筛选、编辑、新增、删除
- 分块、重解析、索引构建属于文件导入与治理流程，仍然放在文件视图处理
- 数据视图里不应再出现“重建索引 / 重新解析”这类文件治理动作
- 数据视图应直接基于 `kb_table_rows` 做服务端分页、搜索与字段过滤，避免大数据集时退化为“前端全量拉取再筛选”

### 2.3 底层对象模型

- `file`：导入来源对象
- `row`：结构化记录对象
- `chunk`：检索片段对象

职责边界：

- 过滤 / 统计 / 聚合 / 去重基于 `row`
- 语义召回 / 证据片段基于 `chunk`
- 导入生命周期 / 重试 / 删除来源文件基于 `file`

---

## 三、知识库级 Schema

### 3.1 字段定义

```python
{
    "schema": {
        "columns": [
            {
                "name": "地区",
                "type": "text",
                "nullable": False,
                "role": "dimension",
                "filterable": True,
                "aggregatable": True,
                "searchable": True
            },
            {
                "name": "事项名称",
                "type": "text",
                "nullable": False,
                "role": "entity",
                "filterable": True,
                "aggregatable": True,
                "searchable": True
            },
            {
                "name": "办理流程",
                "type": "text",
                "nullable": True,
                "role": "content",
                "filterable": False,
                "aggregatable": False,
                "searchable": True
            }
        ]
    }
}
```

### 3.2 字段角色

- `entity`：名称、地区、部门、类别、状态等基础检索字段
- `content`：办理流程、说明、备注、描述
- `identifier`：编码、证号、SKU、工号

前端交互建议：

- 当前阶段不建议再把“分类字段”和“主体字段”拆成两个用户可见概念
- 对用户来说，这两类字段在行为上都表现为：可过滤、可聚合、可检索
- 因此前端可以统一收敛成 `基础字段`
- 底层若未来仍需保留更细语义，也应作为内部实现细节，而不是第一期前端心智
- 推荐用更易懂的展示文案替代，例如：
  - `entity` -> 基础字段
  - `content` -> 详情内容
  - `identifier` -> 唯一标识

### 3.3 字段能力

- `filterable`
- `aggregatable`
- `searchable`

当前阶段不单独设计“是否前端展示该列”配置。

---

## 四、存储模型

### 4.1 Row 层

新增通用结构化行表 `kb_table_rows`，统一存 JSONB，不写死业务列。

设计原则：

- `kb_table_rows` 是表格知识库入库后的**结构化事实源**
- `row_data` 只保存原始结构化记录，用于展示、追溯与结构化查询
- 不在 Row 层额外维护 `search_text`、`normalized_data` 一类派生文本字段
- 语义检索统一基于 Chunk 层 `content`
- 如后续确有字段级标准化需求，应作为独立能力设计，不在当前版本预埋半成品字段
- 所有行记录必须带 `tenant_id`，与知识库、文档、chunk 保持一致的租户隔离模型

建议结构：

```python
{
    "id": "...",
    "tenant_id": "...",
    "kb_id": "...",
    "kb_doc_id": "...",
    "doc_id": "...",
    "sheet_name": "Sheet1",
    "row_uid": "doc123:sheet1:row3",
    "row_index": 3,
    "source_row_number": 4,
    "source_type": "excel_import",
    "row_version": 1,
    "is_deleted": False,
    "row_data": {
        "地区": "南康区",
        "事项名称": "企业开办",
        "办理流程": "1.营业执照申请 2.刻章"
    },
    "source_meta": {
        "sheet_name": "Sheet1",
        "header_row_number": 1
    }
}
```

推荐字段说明：

- `tenant_id`：必须字段，保证租户隔离，与现有主业务表保持一致
- `kb_id` / `kb_doc_id` / `doc_id`：分别对应知识库、知识库文档挂载、物理文件来源，便于治理与追溯
- `row_uid`：行级稳定业务键；同一条记录即使被拆成多个 overflow chunk，也始终对应一个 `row_uid`
- `row_index`：相对于数据区的稳定行序号，用于当前展示排序与锚点定位
- `source_row_number`：Excel 原始物理行号（1-based，含表头偏移），用于回溯文件时给用户准确定位
- `source_type`：记录来源类型；当前阶段建议仅支持 `excel_import / manual`
- `row_version`：行数据版本号；每次用户编辑递增，后续可用于增量重建 chunk
- `is_deleted`：软删除标记，便于后续支持数据视图中的删除与恢复
- `source_meta`：保留轻量来源信息；仅承载追溯辅助字段，不重复存储大段派生文本

当前阶段不建议新增的字段：

- `search_text`
- `normalized_data`
- 大而全的字段级清洗结果缓存

### 4.1.1 事实源切换原则

表格知识库需要明确区分“导入来源”和“入库后的事实源”：

- 首次导入前，事实源是原始 Excel 文件
- 首次导入完成后，`kb_table_rows` 成为表格知识库的结构化事实源
- 原始 Excel 文件继续保留，但主要用于来源追溯、重新导入参考、校验对比
- 重新生成 chunk 时，不应再强依赖原始 Excel 文件重新解析，否则会覆盖用户对行数据的编辑结果

也就是说：

- `ExcelTableParser` 负责把 Excel 转成标准 `table_rows`
- `ExcelTableChunker` 负责把标准 `table_rows` 转成 chunk
- 后续若 `kb_table_rows` 支持编辑，应新增“`kb_table_rows` -> 标准 `table_rows`”的适配层
- 分块逻辑尽量继续复用现有 `ExcelTableChunker` 与超限父子分块能力，而不是重写一套编辑模式专用分块器

### 4.1.2 行可编辑与重解析原则

`kb_table_rows` 建议支持修改；但只要支持修改，就必须同步约束解析状态与旧 chunk 的生命周期。

规则如下：

- 用户修改任意行数据后，该 `kb_doc` 的表格数据立即视为“已变更”
- 旧 chunk 不应继续参与检索，否则会与最新 `row_data` 不一致
- 系统应清理或失效该 `kb_doc` 现有 chunk，并提示用户重新触发解析
- 重新解析时，输入应优先来自 `kb_table_rows`，而不是回到原始 Excel 文件

推荐状态处理：

- 对应 `knowledge_base_documents.parse_status` 置为 `pending`
- `knowledge_base_documents.runtime_stage` 置为 `edited_waiting_reparse`
- `chunk_count` 置为 `0`
- 前端明确提示“数据已修改，请重新触发解析后生效”

设计意图：

- 避免“用户改了行数据，但检索仍命中旧 chunk”
- 避免“重新解析后又从旧 Excel 覆盖用户修改”
- 为后续增量重建 chunk 预留演进空间，但当前先保证一致性优先

### 4.2 Chunk 层

一条 row 可对应一个或多个 chunk。

即使单行超长发生 overflow：

- `row` 仍只有一条
- `chunk` 可拆多条
- 统计仍按 `row_uid` 计算

---

## 五、解析与分块

### 5.1 解析器

使用独立 `ExcelTableParser`：

```python
@dataclass
class ExcelRowData:
    row_uid: str
    sheet_name: str
    row_index: int
    header: list[str]
    values: list[str]
    column_types: dict[str, str]
```

解析流程：

1. 智能表头检测
2. 合并单元格回填
3. 列类型推断
4. 逐行产出 `ExcelRowData`

共享解析能力以 [Excel共享能力设计方案](./Excel共享能力设计方案.md) 为准。

补充约束：

- `ExcelTableParser` 主要服务于首次导入，将原始 Excel 转成标准 `table_rows`
- 若后续从 `kb_table_rows` 重新生成 chunk，应复用同一套 `table_rows` 输入协议
- 不建议把 overflow 父子分块逻辑绑死在“只能从 Excel 文件解析”的链路上

### 5.2 分块器

使用 `ExcelTableChunker`。

核心原则：

- 一行一条 row
- 一行可生成一个或多个 chunk
- `content` 用于检索
- `content_blocks` 用于展示
- 不提供“是否分块”配置；分块是系统内部机制，超长时必须自动拆分

推荐 `content`：

```text
事项名称: 企业开办; 办理流程: 1.营业执照申请 2.刻章
```

### 5.3 Chunk 结构

```python
{
    "content": "事项名称: 企业开办; 办理流程: ...",
    "chunk_type": "table",
    "content_blocks": [{
        "type": "table",
        "text": "| 地区 | 事项名称 | 办理流程 |\n|---|\n| 南康区 | 企业开办 | ... |"
    }],
    "metadata_info": {
        "chunk_strategy": "excel_table",
        "sheet_name": "Sheet1",
        "row_uid": "doc123:sheet1:row3",
        "row_index": 3,
        "filter_fields": {
            "地区": "南康区"
        }
    }
}
```

---

## 六、导入与校验

### 6.1 Schema 校验

上传时采用分级校验：

- 完全一致：直接导入
- 缺少非必填列：warning，可导入
- 多出新列：默认阻止
- 核心列缺失：阻止
- 字段类型冲突：warning 或阻止

### 6.2 上传交互

采用：

```text
上传文件
  -> 自动预检
  -> 文件进入待确认状态
  -> 用户查看校验结果
  -> 单条/批量确认导入
  -> 正式入库
```

不建议把所有配置都塞进上传弹窗。

当前实现约束：

- 表格知识库文件在“保存到知识库”后，应先立即完成轻解析并落库 `kb_table_rows`
- 这样数据视图可立即查看记录，不依赖后续 chunk/embedding 任务完成
- 若勾选“立即解析”，则在落库完成后继续走原有异步解析/分块链路
- 若未勾选“立即解析”，则上传到此结束；后续可通过界面继续触发解析分块流程

### 6.3 批量导入

批量导入时：

- 默认展示汇总
- 默认展示异常文件列表
- 单个文件按需展开样本预览

### 6.4 编辑后重解析

表格知识库一旦支持数据视图中的行编辑，就必须提供明确的“重解析”交互，而不是静默自动覆盖。

推荐流程：

```text
用户修改 kb_table_rows
  -> 系统标记文档为待重解析
  -> 清理该文档旧 chunk
  -> 前端提示“数据已变更，请重新触发解析”
  -> 用户触发重新解析
  -> 系统从 kb_table_rows 重建标准 table_rows
  -> 复用现有 ExcelTableChunker 重新生成 chunk
```

当前阶段建议：

- 先做“编辑后置脏 + 用户手动重解析”
- 不急于上“编辑后自动后台重建”
- 先保证数据一致性，再优化交互效率

补充实现原则：

- 对于 `table` 类型知识库，后续解析/分块不应再次把原始 Excel 当作唯一事实源
- 一旦 `kb_table_rows` 已经存在，解析链路应优先从 `kb_table_rows` 重建标准 `table_rows metadata`
- 通用知识库仍然保留“直接读取原始 Excel/CSV 解析”的方式，不受影响

---

## 七、前端设计

### 7.1 知识库详情页

建议三块：

- **数据视图**：记录列表、过滤、统计
- **文件视图**：导入文件、预检、确认、重试
- **结构配置**：schema、字段能力、导入规则、术语与同义词

补充原则：

- 表格工作区顶部可采用并排切换：
  - 文件列表
  - 数据视图
  - 结构定义
- 其中“结构定义”是表格知识库主流程的一部分，适合与文件列表、数据视图并排
- 但这不等于把整个“全局配置”都并入工作区；全局配置仍保留一级导航入口
- 既然“结构定义”已经进入表格工作区，就不应再在“全局配置”里重复提供一套表格结构入口
- “结构配置”应作为表格知识库的一等配置入口，而不是挂在“解析分块”的下级子栏里
- 代码层应通过“类型专属配置注册”接入，而不是把 `table` 逻辑硬编码到全局配置骨架中
- 当知识库尚未定义 `schema.columns` 时，引导用户进入结构配置或上传首个 Excel 自动生成草稿
- 一旦用户已经进入结构配置页，不应继续重复显示首屏引导卡片
- 结构配置页本身也应提供“上传首个 Excel 生成草稿”的快捷入口，避免用户在配置页和文件视图之间反复跳转
- 若用户通过上传自动生成了结构草稿，系统应优先把用户带到“结构定义”视图做确认，而不是让草稿默默写入后停留在文件列表
- 对首次手工定义场景，可提供轻量的字段角色/类型推荐，降低配置门槛，但推荐结果应允许用户继续人工调整
- 当知识库仍存在已接入文件时，原有字段结构应视为已生效规则：
  - 不允许直接修改既有字段定义
  - 仅允许在原结构基础上新增字段
- 当用户已经移除全部文件后，应允许清空当前结构定义，并重新从空白状态定义字段

### 7.2 创建知识库

创建表格知识库时配置：

- 字段结构
- 字段角色
- `filterable / aggregatable / searchable`
- 表头策略
- 校验策略

### 7.3 文件视图中的操作

- 预检结果查看
- 单条确认导入
- 批量确认导入
- 重试
- 指定表头行
- 指定 Sheet

### 7.4 数据视图展示原则

- 数据视图应直接呈现 `kb_table_rows` 的真实表格形态，而不是记录卡片列表
- 必须明确看到：
  - 表头
  - 行号
  - 列值
- 默认展示列应优先按 schema 顺序展开，尽量保证用户一眼能看到“像表格”的行列关系
- 对列很多、单元格内容很长的场景，应通过横向滚动、固定表头、列显示控制解决，而不是退化成 chunk 式摘要浏览

---

## 八、检索与统计

### 8.1 检索路由

根据字段角色分流：

- `identifier`：精确直查
- `filterable`：先 row 过滤，再语义召回
- `aggregatable` + 统计意图：走 row 层聚合查询
- 其他：常规语义召回

### 8.2 统计原则

`count/group/distinct` 一律基于 row 层，而不是 chunk 层。

原因：

- overflow 会导致一行多个 chunk
- summary chunk 会污染统计
- 向量召回不是全量集合

---

## 九、术语与同义词

当前阶段：

- 仅做知识库级术语 / 同义词
- 直接复用现有 `kb_glossaries` / `kb_synonyms`
- 不做文档级 override
- 不做表格专属的“逐行配置 canonical value”前端交互
- 不把字段级标准值映射作为当前版本阻塞项

设计说明：

- 知识库级同义词主要用于检索侧 query 理解与术语归一化
- `kb_table_rows` 当前只维护原始 `row_data`，不因术语能力额外增加派生存储字段
- 若后续真实业务中出现大量脏枚举值、且明显影响过滤或聚合，再单独设计字段级标准化能力及对应前端界面

术语能力不是当前表格知识库上线的阻塞项。

---

## 十、接口方向

建议至少具备：

- `POST /api/v1/knowledge-bases`
- `GET /api/v1/knowledge-bases/{kb_id}/table-schema`
- `PUT /api/v1/knowledge-bases/{kb_id}/table-schema`
- `POST /api/v1/knowledge-bases/{kb_id}/documents/precheck-table-import`
- `POST /api/v1/knowledge-bases/{kb_id}/documents/confirm-table-import`

---

## 十一、开发优先级

### P0

- 知识库级 schema 配置
- 表格导入预检
- 列一致性校验
- 文件视图确认导入

### P1

- 数据视图（记录列表）
- 基础过滤
- 基础统计

### P2

- 批量操作
- 更细的 schema 变更控制
- 检索归一化增强
