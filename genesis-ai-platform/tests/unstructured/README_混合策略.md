# Markdown 混合分块策略

## 环境安装（仅本目录测试需要）

`unstructured` 已从项目主依赖移除，因此运行本目录脚本前请单独安装：

```powershell
cd genesis-ai-platform
uv sync
.\.venv\Scripts\python.exe -m pip install "unstructured[md]>=0.18.32"
```

安装后可先做快速验证：

```powershell
.\.venv\Scripts\python.exe -c "from unstructured.partition.md import partition_md; print('unstructured md ok')"
```

## 策略概述

这是一个两层混合分块策略，结合了 LlamaIndex 的 MarkdownNodeParser 和 Unstructured 的优势：

1. **第一层（MarkdownNodeParser）**：按 Markdown 标题层级分块，保留文档结构
2. **第二层（Unstructured）**：对超过 512 token 的章节进行二次分块

## 核心优势

### ✅ 保留文档结构
- 使用 MarkdownNodeParser 按标题分块，保留完整的章节结构
- 每个块都有清晰的 `header_path`（标题路径）

### ✅ 确保 Token 限制
- 自动检测每个章节的 token 数
- 超过限制的章节使用 Unstructured 进一步分块
- 确保所有块都不超过嵌入模型限制（512 tokens）

### ✅ 智能回退
- Unstructured 处理失败时，自动回退到简单段落分割
- 保证分块过程的鲁棒性

## 使用方法

### 运行测试

```bash
# Windows
cd genesis-ai-platform
tests\unstructured\test_hybrid_strategy.bat

# 或直接运行 Python 脚本
.\.venv\Scripts\python.exe tests\unstructured\分块策略_markdown_unstructured.py
```

### 代码示例

```python
from tests.unstructured.分块策略_markdown_专用解析器 import hybrid_chunk_markdown

# 对 Markdown 文件进行混合策略分块
chunks = hybrid_chunk_markdown(
    file_path="doc/增删改查指南.md",
    max_tokens=512
)

# 查看分块结果
for chunk in chunks:
    print(f"来源: {chunk['source']}")
    print(f"标题: {chunk['header_path']}")
    print(f"Token 数: {chunk['token_count']}")
    print(f"内容: {chunk['text'][:100]}...")
    print("-" * 80)
```

## 输出格式

每个块包含以下信息：

```python
{
    "text": "块的文本内容",
    "header_path": "完整的标题路径",
    "token_count": 实际的 token 数,
    "source": "markdown_parser" 或 "unstructured",
    
    # 如果是 unstructured 处理的子块
    "parent_chunk_index": 父章节索引,
    "sub_chunk_index": 子块索引
}
```

## 处理流程

```
输入 Markdown 文件
    ↓
第一层：MarkdownNodeParser 按标题分块
    ↓
检查每个章节的 token 数
    ↓
    ├─ ≤ 512 tokens → 直接使用
    │
    └─ > 512 tokens → 使用 Unstructured 二次分块
                        ↓
                    生成多个子块（每个 ≤ 512 tokens）
    ↓
输出最终分块结果
```

## 配置参数

### `max_tokens`
- 默认值：512
- 说明：每个块的最大 token 数
- 建议：根据嵌入模型的上下文限制设置

### Unstructured 参数
- `max_characters`: `max_tokens * 4`（粗略估算：1 token ≈ 4 字符）
- `new_after_n_chars`: `max_tokens * 3`
- `overlap`: 50 字符

## 与现有 MarkdownChunker 的集成

这个混合策略可以集成到现有的 `MarkdownChunker` 中：

```python
# 在 MarkdownChunker._process_section 中
def _process_section(self, section: Dict[str, Any], metadata: Dict[str, Any]):
    text = section["text"]
    token_count = section["token_count"]
    
    # 如果章节不超过限制，使用现有逻辑
    if token_count <= self.chunk_size:
        return self._chunk_by_paragraph_with_protection(...)
    
    # 如果章节超过限制，使用 unstructured 处理
    else:
        return self._process_with_unstructured(text, section, metadata)
```

## 测试结果

测试文件：`doc/增删改查指南.md`

### 输出文件

测试会生成两个文件：

1. **完整结果文件**：`分块结果-混合策略-YYYYMMDD_HHMMSS.txt`
   - 包含所有块（markdown_parser + unstructured）
   - 显示每个块的来源、标题路径、token 数等
   - 用于查看完整的分块结果

2. **Unstructured 专用文件**：`分块结果-混合策略__Unstructured-YYYYMMDD_HHMMSS.txt`
   - 只包含 unstructured 处理的块
   - 显示哪些章节超过了 512 token 限制
   - 显示这些章节如何被二次分块
   - 用于分析和调试 unstructured 的处理效果

### 统计信息
- 第一层分块（MarkdownNodeParser）：X 个章节
- 直接使用的章节：Y 个
- 需要二次分块的章节：Z 个
- 最终块数：N 个
- 平均 token 数：~400 tokens
- 最大 token 数：≤ 512 tokens

### 文件位置
- 完整结果：`tests/unstructured/output/分块结果-混合策略-YYYYMMDD_HHMMSS.txt`
- Unstructured 块：`tests/unstructured/output/分块结果-混合策略__Unstructured-YYYYMMDD_HHMMSS.txt`

## 注意事项

1. **依赖安装**：`unstructured` 不属于主安装依赖，请按上文单独安装

2. **Token 计算**：使用项目的 `count_tokens` 函数，确保准确性

3. **性能考虑**：Unstructured 处理较慢，只在必要时使用

4. **错误处理**：Unstructured 失败时自动回退到简单分割

## 未来优化

1. **缓存机制**：缓存 Unstructured 的处理结果
2. **并行处理**：对多个大章节并行使用 Unstructured
3. **更智能的阈值**：根据内容类型动态调整 token 限制
4. **元素保护**：在 Unstructured 分块时保护表格、代码块等完整性
