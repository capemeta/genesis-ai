# Native PDF Parser

## 概述

`NativePDFParser` 是一个基于 pypdfium2 和 pdfplumber 的 PDF 解析器，提供以下核心能力：

1. **动态标题引擎**：基于全文权重统计识别标题
2. **图形感知**：使用 pdfplumber 识别矢量图和位图
3. **空间隔离**：彻底解决表格文本重复噪音
4. **语义自愈**：智能处理断行、连字符及中英文排版
5. **页码过滤**：自动识别和过滤各种格式的页码
6. **无版权风险**：采用 Apache/BSD & MIT 协议库

## 使用方式

### 1. 测试环境（本地文件）

```python
from rag.ingestion.parsers.pdf.native import NativePDFParser

parser = NativePDFParser(enable_ocr=False)

# 解析本地文件
elements = parser.parse("path/to/file.pdf")

# 保存图片到本地
for el in elements:
    if el["type"] == "image":
        metadata = el.get("metadata", {})
        image_bytes = metadata.get("blob")
        if image_bytes:
            with open(f"output/{el['content']}", "wb") as f:
                f.write(image_bytes)
```

### 2. 生产环境（通过 PDFRouter）

```python
from rag.ingestion.parsers.pdf import PDFRouter

router = PDFRouter(config={"parser": "native"})

# 解析 bytes 数据
with open("file.pdf", "rb") as f:
    pdf_bytes = f.read()

# 返回 Markdown 文本和元数据
markdown_text, metadata = router.route(pdf_bytes)

# 图片数据在 metadata 中
pdf_embedded_images = metadata.get("pdf_embedded_images", [])
for img in pdf_embedded_images:
    image_id = img["id"]
    image_blob = img["blob"]
    # 存储到 MinIO/S3/本地
    # ...
```

## 图片处理流程

### 测试环境

1. `NativePDFParser.parse()` 返回元素列表
2. 图片元素包含 `metadata["blob"]` 字段（图片二进制数据）
3. 测试代码将图片保存到本地文件系统
4. Markdown 中使用相对路径引用图片

### 生产环境

1. `NativePDFParser.parse()` 返回元素列表
2. `PDFRouter.route()` 提取图片数据到 `pdf_embedded_images`
3. `parse_task.py` 中的 `_persist_pdf_images_and_rewrite_markdown()` 将图片存储到存储驱动
4. 创建 Document 记录并生成公开 URL
5. Markdown 中的占位符 `pdf://embedded/{image_id}` 被替换为实际 URL

## 图片元数据格式

```python
{
    "image_id": "image_5_1",           # 唯一图片ID
    "blob": b"...",                     # 图片二进制数据
    "content_type": "image/png",        # MIME类型
    "ext": ".png",                      # 文件扩展名
    "is_vector": False,                 # 是否为矢量图
    "page_no": 4,                       # 所在页码
    "bbox": [x0, y0, x1, y1]           # 边界框坐标
}
```

## 页码过滤

自动识别和过滤以下格式的页码：

- 纯数字：`1`, `2`, `3`
- 带前后缀：`- 1 -`, `第1页`, `Page 1`
- 分数格式：`1/10`
- 括号格式：`[1]`, `(1)`

## 配置选项

```python
parser = NativePDFParser(
    enable_ocr=False,                    # 是否启用 OCR
    ocr_engine="auto",                   # OCR 引擎（auto/tesseract/paddleocr）
    ocr_languages=["ch", "en"],          # OCR 语言
    extract_images=False,                # 是否提取图片（已废弃，始终提取）
    extract_tables=True                  # 是否提取表格
)
```

## 注意事项

1. **输入格式**：支持文件路径（str）或文件内容（bytes）
2. **图片数据**：通过 `metadata["blob"]` 传递，不使用 `metadata["image_bytes"]`
3. **图片ID**：必须包含 `metadata["image_id"]`，供 PDFRouter 识别
4. **兼容性**：与 PDFRouter 和 parse_task.py 完全兼容

## 相关文件

- `parser.py` - 主解析器
- `font_analysis.py` - 字体分析和标题识别
- `layout.py` - 布局分析和图形识别
- `reflow.py` - 文本重排和语义修复
- `../pdf_router.py` - PDF 路由器（生产环境入口）
- `../../tasks/parse_task.py` - 解析任务（图片持久化）
