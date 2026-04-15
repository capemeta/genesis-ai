# PDF 解析配置说明

## 配置结构

```json
{
  "parser": "native",           // PDF 解析器：native, mineru, docling, tcadp
  "enable_ocr": true,            // 是否启用 OCR（智能检测扫描页）
  "ocr_engine": "auto",          // OCR 引擎：auto, paddleocr, tesseract
  "ocr_languages": ["ch", "en"], // 识别语言列表
  "extract_images": false,       // 是否提取图片
  "extract_tables": true         // 是否提取表格
}
```

## 解析器对比

### 1. Native（原生）

**定位**：速度优先，适合数字化 PDF

**特点**：
- 使用 pdfplumber 直接提取文本层
- 速度极快（2-5秒/文档）
- 支持智能 OCR 降级（检测到扫描页自动启用 OCR）

**适用场景**：
- 纯文字 PDF（有文本层）
- 对速度要求高的场景
- 简单布局文档

**配置项**：
- `enable_ocr`: 是否启用 OCR（智能检测）
- `ocr_engine`: OCR 引擎选择
- `ocr_languages`: 识别语言

**不需要**：
- 视觉模型（不处理图像内容）

---

### 2. MinerU（高精度）

**定位**：高精度解析，适合复杂文档

**特点**：
- 内置 OCR（95%+ 准确率）
- 版面分析（Layout Analysis）
- 公式识别（LaTeX 输出）
- 表格结构化
- 可配合视觉模型增强图像理解

**适用场景**：
- 学术论文（含公式）
- 复杂布局文档
- 扫描件 PDF
- 图表密集文档

**配置项**：
- `extract_images`: 是否提取图片
- `extract_tables`: 是否提取表格

**可选配置**（知识库级别）：
- `vision_model`: 视觉模型（用于理解图像、图表内容）

**不需要配置**：
- OCR 相关（内置 OCR）

---

### 3. Docling（智能布局）

**定位**：表格还原专家，Markdown 输出

**特点**：
- 强大的表格还原能力
- 智能布局分析
- Markdown 格式输出
- 公式识别
- 可选 OCR（按需启用）
- 可配合视觉模型辅助图像识别

**适用场景**：
- 表格密集文档
- 需要 Markdown 输出
- 结构化文档

**配置项**：
- `enable_ocr`: 是否启用 OCR
- `ocr_engine`: OCR 引擎选择
- `ocr_languages`: 识别语言
- `extract_images`: 是否提取图片
- `extract_tables`: 是否提取表格

**可选配置**（知识库级别）：
- `vision_model`: 视觉模型（用于辅助表格和图像识别）

---

### 4. TCADP（云端）

**定位**：腾讯云服务，无需本地资源

**特点**：
- 云端处理（无需本地资源）
- 高并发支持
- 按量计费
- 内置 OCR + 视觉理解能力

**适用场景**：
- 高并发场景
- 本地资源有限
- 需要稳定的云端服务

**配置项**：
- `extract_images`: 是否提取图片
- `extract_tables`: 是否提取表格

**不需要配置**：
- OCR 相关（云端已集成）
- 视觉模型（云端已集成）

---

## OCR 引擎选择

### 自动选择（auto）

**策略**：
1. 检测可用内存
2. 内存 >= 4GB → PaddleOCR（高质量）
3. 内存 < 4GB → Tesseract（轻量级）

**实现**：
```python
from rag.ingestion.parsers.ocr_engine_selector import select_ocr_engine

# 自动选择
engine = select_ocr_engine("auto")
```

### PaddleOCR

**特点**：
- 高质量识别（95%+ 准确率）
- 支持多语言
- 需要较多内存（建议 4GB+）

**降级机制**：
- 如果 PaddleOCR 不可用或失败，自动降级到 Tesseract

### Tesseract

**特点**：
- 轻量级
- 内存占用小
- 识别准确率略低于 PaddleOCR

---

## 视觉模型的作用

### 什么是视觉模型？

视觉模型（Vision Model）是多模态大语言模型，能够理解图像内容。

**常见模型**：
- GPT-4o
- GPT-4 Vision Preview
- Gemini Pro Vision
- Claude 3 Opus

### 视觉模型的用途

**不是**：
- ❌ PDF 解析器本身
- ❌ OCR 引擎

**是**：
- ✅ 理解 PDF 中的图像、图表、复杂布局
- ✅ 提取图表中的数据和趋势
- ✅ 理解公式的含义
- ✅ 描述图片内容

### 哪些解析器需要视觉模型？

| 解析器 | 是否需要 | 用途 |
|--------|---------|------|
| Native | ❌ 不需要 | 只提取文本层，不处理图像 |
| MinerU | ✅ 可选 | 增强图像理解能力 |
| Docling | ✅ 可选 | 辅助表格和图像识别 |
| TCADP | ❌ 不需要 | 云端已集成视觉能力 |

### 配置位置

视觉模型配置在**知识库级别**，而不是 PDF 解析器配置中：

```python
# 知识库配置
{
  "vision_model": "gpt-4o",  # 全局视觉模型
  "pdf_parser_config": {
    "parser": "mineru",      # 解析器选择
    # ... 其他配置
  }
}
```

---

## 配置示例

### 场景 1：纯文字 PDF（速度优先）

```json
{
  "parser": "native",
  "enable_ocr": true,        // 智能检测扫描页
  "ocr_engine": "auto",      // 自动选择 OCR 引擎
  "ocr_languages": ["ch", "en"],
  "extract_images": false,
  "extract_tables": true
}
```

### 场景 2：学术论文（含公式）

```json
{
  "parser": "mineru",
  "extract_images": true,
  "extract_tables": true
}
```

知识库配置：
```json
{
  "vision_model": "gpt-4o"  // 用于理解图表和公式
}
```

### 场景 3：表格密集文档

```json
{
  "parser": "docling",
  "enable_ocr": true,
  "ocr_engine": "paddleocr",
  "ocr_languages": ["ch", "en"],
  "extract_images": false,
  "extract_tables": true
}
```

知识库配置：
```json
{
  "vision_model": "gpt-4o"  // 辅助表格识别
}
```

### 场景 4：扫描件 PDF

```json
{
  "parser": "native",
  "enable_ocr": true,
  "ocr_engine": "paddleocr",  // 强制使用 PaddleOCR
  "ocr_languages": ["ch", "en"],
  "extract_images": false,
  "extract_tables": true
}
```

### 场景 5：云端处理（高并发）

```json
{
  "parser": "tcadp",
  "extract_images": true,
  "extract_tables": true
}
```

---

## 性能对比

| 解析器 | 速度 | 准确率 | 资源占用 | 成本 |
|--------|------|--------|---------|------|
| Native | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 低 | 免费 |
| MinerU | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 高 | 免费（本地）+ 视觉模型费用（可选） |
| Docling | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 中 | 免费（本地）+ 视觉模型费用（可选） |
| TCADP | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 无（云端） | 按量计费 |

---

## 最佳实践

### 1. 根据文档类型选择解析器

- **纯文字 PDF** → Native（速度快）
- **学术论文** → MinerU（公式识别）
- **表格文档** → Docling（表格还原）
- **扫描件** → Native + OCR 或 MinerU
- **高并发场景** → TCADP（云端）

### 2. OCR 引擎选择

- **默认** → auto（自动选择）
- **高质量要求** → paddleocr（需要 4GB+ 内存）
- **资源受限** → tesseract（轻量级）

### 3. 视觉模型使用

- **不需要图像理解** → 不配置视觉模型
- **需要理解图表** → 配置 GPT-4o 或 Gemini Pro Vision
- **成本敏感** → 只在必要时使用视觉模型

### 4. 性能优化

- **批量处理** → 使用 Celery Worker 并行处理
- **内存优化** → 根据可用内存选择合适的 OCR 引擎
- **成本优化** → 优先使用本地解析器，云端作为备选

---

## 相关文档

- [OCR 引擎选择器实现](../ingestion/parsers/ocr_engine_selector.py)
- [PDF 解析器实现](../ingestion/parsers/)
- [Celery 任务配置](../../tasks/)
