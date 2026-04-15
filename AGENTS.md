# AGENTS Rules

## Encoding Rules (Mandatory)

- Repository default for source files with Chinese text is `UTF-8 (without BOM)`.
- Do not change encoding unless explicitly requested.
- When editing existing files, preserve line endings and encoding.
- For Python/TS/TSX files touched in this repo:
  - write as `utf-8` (without BOM)
  - then run syntax/type checks before finishing.
- If terminal output shows garbled Chinese, do not assume file corruption.
  - verify by file bytes and compiler checks.
- Any bulk text replacement involving Chinese must be followed by:
  1. encoding verification
  2. compile/typecheck verification

## Coding Rules

- 遵循良好的架构设计、代码要模块化、扩展性良好、未来方便维护
- 现阶段是开发阶段，代码要遵循最佳实践，不需要兼容旧数据
- 代码要有注释，且用中文写

## Python 环境规则

- 执行后端 Python 命令时，必须使用固定解释器：`genesis-ai-platform\.venv\Scripts\python.exe`
- 包括但不限于测试、脚本、类型检查、调试运行
- 不要默认使用系统 `python`、`py`、`uv run python`、`uv run pytest`
- 推荐命令示例：
  - `genesis-ai-platform\.venv\Scripts\python.exe -m pytest`
  - `genesis-ai-platform\.venv\Scripts\python.exe -m mypy .`
  - `genesis-ai-platform\.venv\Scripts\python.exe script.py`

## Chunk 协议规则

- 当前项目处于开发阶段，`chunk` / `content_blocks` / `metadata_info` 的结构不考虑历史兼容，必须优先遵循当前统一协议与最佳实践。
- 所有分块策略必须输出统一格式，至少包括：
  - `content_blocks: list`
  - `metadata_info.source_anchors: list`
  - `metadata_info.page_numbers: list`
  - `metadata_info.source_element_indices: list`
- `content_blocks[].source_refs` 是块级权威来源字段，用于表达“该内容块来自哪里”，必须与具体 block 对应；不能再把它设计成仅存在于 chunk 级元数据中的主定位字段。
- `metadata_info` 只承载 chunk 级聚合信息，例如：
  - `source_anchors`
  - `page_numbers`
  - `primary_page_number`
  - `source_element_indices`
  不能在 `metadata_info` 中重复塞入与 `content_blocks[].source_refs` 语义重叠的块级主来源数据。
- 非 PDF 分块策略也必须保持相同字段结构；当没有页码或定位信息时，使用空数组，不能各自发明不同字段或省略成不一致格式。
- 禁止随意新增语义重复或易混淆字段，例如再次引入与 `page_numbers`、`primary_page_number`、`content_blocks[].source_refs` 重叠的平级替代字段。
- 如果后续出现更好的结构设计，可以修改当前协议；但必须满足：
  1. 先基于最佳实践整体评估
  2. 前后端、分块器、落库、测试统一修改
  3. 修改前必须得到用户明确同意
- 对结构的调整必须是整体设计，不允许局部补丁式修改，不允许只改某一种分块策略而导致协议再次分裂。
