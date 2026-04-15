# Native PDF 解析器改进说明

## 改进概述

本次改进借鉴了 WeKnora 的 PDF 解析方案，增强了 native 模式的结构识别能力，特别是对标题、代码块和列表的识别。

## 主要改进点

### 1. 代码块识别（核心改进）

**借鉴 WeKnora 的方法**：
- 等宽字体检测（Courier, Consolas, Monaco 等）
- 缩进分析（相对于页面左边距）
- 代码特征模式匹配（关键字、符号、注释等）

**实现细节**：

```python
# 新增等宽字体列表
self.monospace_fonts = {
    "courier", "consolas", "monaco", "menlo", "dejavu sans mono",
    "liberation mono", "source code pro", "fira code", "inconsolata",
    "ubuntu mono", "droid sans mono", "roboto mono", "cascadia code"
}

# 代码行判断逻辑
def _is_code_line(content, font_name, bbox, page_left_margin, font_stats):
    # 1. 检查等宽字体
    is_monospace = self._is_monospace_font(font_name)
    
    # 2. 检查缩进
    indent = bbox[0] - page_left_margin
    has_indent = indent > 20
    
    # 3. 检查代码特征
    code_patterns = [
        r'^\s*(def|class|import|from|if|for|while|return)',  # 关键字
        r'[{}\[\]();]',  # 括号
        r'\s*=\s*',  # 赋值
        r'->\s*\w+',  # 箭头函数
        r'^\s*//|^\s*/\*|^\s*#',  # 注释
    ]
    
    # 综合判断
    return is_monospace and (has_indent or has_code_pattern) and not is_list
```

### 2. 字体统计分析

**新增功能**：
- 收集文档中所有字体的使用频率
- 识别主要正文字体和字体大小
- 检测文档中使用的等宽字体

**用途**：
- 辅助代码块识别
- 改进标题识别准确度
- 提供字体上下文信息

```python
def _collect_font_statistics(pages_dict):
    """
    返回：
    {
        "main_font": str,  # 主要字体名称
        "main_size": float,  # 主要字体大小
        "monospace_fonts": set,  # 文档中使用的等宽字体
        "font_usage": Counter  # 字体使用频率
    }
    """
```

### 3. 改进的结构类型识别

**优先级顺序**（避免误判）：
1. 列表项检测（最高优先级）
2. 代码块检测
3. 标题检测
4. 普通文本

**关键改进**：
- 列表项不会被误判为标题
- 代码块不会被误判为标题
- 章节编号（如 "1."）不会被误判为列表项

```python
# 改进前：可能将 "1." 误判为列表项
if re.match(r'^\d+\.\s+', text):
    return True

# 改进后：排除单独的章节编号
if re.match(r'^\d+\.$', text):
    return False  # 这是章节编号的一部分
if re.match(r'^\d+\.\s+[^\d]', text):
    return True  # 这才是列表项
```

### 4. 代码块合并

**新增功能**：`LayoutEngine.group_code_blocks()`

将连续的代码行合并为完整的代码块：

```python
# 输入：
[
    {"type": "text", "content": "def hello():", "structure_type": "code_block"},
    {"type": "text", "content": "    print('hello')", "structure_type": "code_block"},
    {"type": "text", "content": "    return True", "structure_type": "code_block"}
]

# 输出：
[
    {
        "type": "code",
        "content": "def hello():\n    print('hello')\n    return True",
        "metadata": {"language": "auto"}
    }
]
```

### 5. 元素类型标记

**新增元数据字段**：
- `structure_type`: "normal" | "list_item" | "code_block" | "table_cell"
- `is_monospace`: 是否使用等宽字体

**用途**：
- 后续分块时保持代码块完整性
- 改进段落重排逻辑
- 提供更丰富的结构信息

## 解析流程对比

### 改进前

```
PDF 字节流
  ↓
提取文本块
  ↓
字体分析（仅标题）
  ↓
段落重排
  ↓
输出元素列表
```

### 改进后

```
PDF 字节流
  ↓
提取文本块
  ↓
字体分析（标题 + 代码块）
  ↓
字体统计（新增）
  ↓
结构类型识别（新增）
  ├─ 列表项
  ├─ 代码块（新增）
  └─ 标题
  ↓
代码块合并（新增）
  ↓
段落重排
  ↓
输出元素列表
```

## WeKnora 方案对比

### WeKnora 的优势

1. **使用 MinerU API**：
   - 专业的 PDF 解析服务
   - 更好的表格、公式识别
   - 输出 Markdown 格式

2. **责任链模式**：
   - MinerU（主解析器）
   - Markitdown（兜底解析器）

3. **Markdown 后处理**：
   - 表格格式标准化
   - Base64 图片提取和上传
   - 图片路径替换

### 我们的改进（Native 模式）

1. **不依赖外部服务**：
   - 纯 PyMuPDF 实现
   - 无需额外部署
   - 更快的响应速度

2. **增强的结构识别**：
   - 借鉴 WeKnora 的字体分析方法
   - 代码块识别（等宽字体 + 缩进 + 模式匹配）
   - 改进的列表项识别

3. **保持原有优势**：
   - 目录优先处理（MaxKB 启发）
   - 页眉页脚过滤
   - 段落重排

## 使用示例

```python
from rag.ingestion.parsers.pdf.native import NativePDFParser

# 创建解析器
parser = NativePDFParser(
    extract_tables=True,
    extract_images=False
)

# 解析 PDF
with open("document.pdf", "rb") as f:
    elements = parser.parse(f.read())

# 查看结果
for el in elements:
    print(f"Type: {el['type']}")
    print(f"Content: {el['content'][:50]}...")
    print(f"Structure: {el['metadata'].get('structure_type')}")
    print(f"Is Monospace: {el['metadata'].get('is_monospace')}")
    print("---")
```

## 测试建议

建议使用以下类型的 PDF 进行测试：

1. **技术文档**：包含代码示例的编程书籍
2. **学术论文**：包含公式、表格、列表
3. **产品手册**：包含多级标题、列表、图片
4. **扫描件**：测试 OCR 降级逻辑

## 后续优化方向

1. **表格识别增强**：
   - 改进 PyMuPDF 的表格检测
   - 支持跨页表格
   - 表格格式标准化

2. **公式识别**：
   - 检测数学公式区域
   - 可选集成 LaTeX OCR

3. **图片处理**：
   - 图片 OCR（如果启用）
   - 图片描述生成（多模态）

4. **性能优化**：
   - 并行处理多页
   - 缓存字体统计信息

## 相关文件

- `parser.py`: 主解析器实现
- `layout.py`: 布局分析和结构识别
- `font_analysis.py`: 字体分析（标题识别）
- `reflow.py`: 段落重排

## 参考资料

- WeKnora PDF 解析流程：`doc/weknora/WeKnora_PDF处理细节.md`
- WeKnora 代码实现：`doc/weknora/code/docreader/parser/`
- MaxKB PDF 处理：`doc/maxkb/MaxKB_PDF处理细节.md`
