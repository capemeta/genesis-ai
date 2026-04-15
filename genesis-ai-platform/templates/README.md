# templates

与 `genesis-ai-platform` 一同版本化、随部署发布的**静态模板文件**目录（CSV 导入样例、未来可扩展其他模板）。

- 路径在代码中通过 `Path(__file__).resolve().parents[...]` 解析到本目录，不依赖仓库外层路径。
- 新增模板时请在此目录落盘，并在对应 API/服务里用常量引用，避免硬编码散落。

| 文件 | 说明 | 下载接口 |
|------|------|----------|
| `qa_import_template.csv` | QA 问答对固定列模板 | `GET /api/v1/knowledge-bases/qa-items/download-template` |
| `table_import_sample.csv` | 结构化表格导入样例（第 1 行表头 + 数据行） | `GET /api/v1/knowledge-bases/table-rows/download-template` |
