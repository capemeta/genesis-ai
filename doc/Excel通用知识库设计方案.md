# Excel通用知识库设计方案

> 适用范围：将 Excel 作为普通知识文档处理，核心目标是**块级语义检索**，而不是结构化过滤、统计或记录级管理。

> 共享能力说明：解析增强、超长内容拆分、父子关系、来源追溯等公共逻辑，请同时参考 [Excel共享能力设计方案](./Excel共享能力设计方案.md)。

---

## 一、定位

通用 Excel 知识库适合以下场景：

- Excel 主要承载说明性内容、配置表、宽表少行数据
- 用户更关心“文档里讲了什么”，而不是“某条记录是否精确命中”
- 不需要按字段做严格过滤、聚合、统计

不适合：

- 政务事项库、产品目录、名册类数据
- 需要按地区 / 事项名称 / 部门等字段精确过滤
- 需要 `count/group/distinct` 的场景

---

## 二、目标

- Excel 作为普通文档进入通用 RAG 流程
- 保留表头与行上下文，避免随机切断行
- 输出 `chunk_type=table` 与 `content_blocks`
- 兼容多 Sheet、合并单元格、超链接、日期规范化等常见问题

---

## 三、解析设计

### 3.1 解析器

沿用并增强 `ExcelParser`。

共享能力见 [Excel共享能力设计方案](./Excel共享能力设计方案.md)，本模式只强调其在通用知识库场景中的使用方式。

### 3.2 结构化 metadata

建议输出：

```python
{
    "parse_method": "excel",
    "parser": "openpyxl",
    "sheets": [
        {
            "name": "Sheet1",
            "header_row": 0,
            "header": ["地区", "事项名称", "电话"],
            "row_count": 120,
            "col_count": 5,
            "column_types": {
                "地区": "text",
                "电话": "text"
            },
            "has_merged_cells": True
        }
    ]
}
```

---

## 四、分块设计

### 4.1 分块器

新增 `ExcelGeneralChunker`。

核心策略：

- 表头 + N 行累积
- 每个 chunk 固定携带表头
- 不随机切断表格行

### 4.2 推荐输出格式

默认 `markdown`：

```markdown
## Sheet1（第 1-30 行）

| 地区 | 事项名称 | 电话 |
| --- | --- | --- |
| 南康区 | 企业开办 | 002 |
| 上犹县 | 企业开办 | 003 |
```

可选 `html`，用于部分模型表格推理场景。

### 4.3 关键参数

- `rows_per_chunk`
- `excel_mode`
- `include_sheets`
- `use_title_prefix`
- `include_hidden_sheets`

---

## 五、Chunk 结构建议

```python
{
    "content": "[Sheet1] | 地区 | 事项名称 | 电话 | ...",
    "content_blocks": [{
        "block_id": "b1",
        "type": "table",
        "text": "<表格 markdown>",
        "source_refs": [{
            "page_no": 0,
            "page_number": 1,
            "element_index": 1,
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

---

## 六、Token 超限处理

共享超限处理策略见 [Excel共享能力设计方案](./Excel共享能力设计方案.md)。

通用模式下进一步采取：

1. 自动减小 `rows_per_chunk`
2. 必要时生成 overflow chunk
3. `content_blocks` 始终保留完整展示内容

原则：

- `content` 可拆分
- `content_blocks` 不截断

---

## 七、适用边界

适合：

- 说明性表格
- 配置表
- 临时知识导入
- 不需要结构化过滤的场景

不适合：

- 记录型表格
- 需要精确过滤或统计的场景
- 需要面向“记录”而不是“文件”的使用体验

---

## 八、实现范围

建议实现文件：

- `rag/ingestion/parsers/excel/excel_parser.py`
- `rag/ingestion/chunkers/excel_general_chunker.py`
- `rag/ingestion/chunkers/excel_token_handler.py`
- `rag/ingestion/chunkers/factory.py`

---

## 九、开发建议

当前阶段优先级低于表格型 Excel 知识库。

开发顺序建议：

1. 先完成表格型 Excel 知识库
2. 再回头补通用 Excel 的 chunk 体验优化
