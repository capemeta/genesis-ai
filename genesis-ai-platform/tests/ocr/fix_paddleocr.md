# PaddleOCR 安装问题修复指南

## 问题描述

PaddleOCR 新版本（2.8+）依赖 `langchain.docstore`，但这个模块在 langchain 0.3+ 中已经移到了 `langchain-community` 包。

错误信息：
```
ModuleNotFoundError: No module named 'langchain.docstore'
```

## 解决方案

### 方案 1：使用旧版本 PaddleOCR（推荐）

旧版本不依赖 langchain，更稳定：

```bash
# 卸载当前版本
uv remove paddleocr

# 安装旧版本（2.7.0.3 是最后一个不依赖 langchain 的版本）
uv add "paddleocr==2.7.0.3"
```

### 方案 2：安装兼容的 langchain 版本

如果必须使用新版 PaddleOCR：

```bash
# 安装旧版本的 langchain（包含 docstore）
uv add "langchain<0.3"
```

### 方案 3：手动修补（不推荐）

创建一个兼容层：

```python
# 在导入 paddleocr 之前执行
import sys
try:
    from langchain.docstore import document
except ImportError:
    from langchain_community import docstore
    sys.modules['langchain.docstore'] = docstore
```

### 方案 4：使用 Tesseract 代替

如果 PaddleOCR 问题无法解决，可以使用 Tesseract：

```bash
python tests/ocr/tesseract_ocr_demo_01.py
```

## 推荐配置

对于中文文档识别，推荐以下配置：

### 配置 1：PaddleOCR 2.7.0.3（稳定）

```bash
uv add "paddleocr==2.7.0.3"
```

优点：
- 不依赖 langchain
- 稳定可靠
- 中文识别效果好

缺点：
- 版本较旧
- 缺少新功能

### 配置 2：Tesseract（轻量）

优点：
- 轻量级
- 部署简单
- 支持多语言

缺点：
- 中文识别较弱
- 对图像质量要求高

## 验证安装

运行诊断脚本：

```bash
python tests/ocr/diagnose_paddleocr.py
```

如果看到 "✅ PaddleOCR 可以正常使用！"，说明安装成功。

## 测试识别效果

```bash
# 测试 PaddleOCR
python tests/ocr/paddleocr_ocr_demo_01.py

# 测试 Tesseract
python tests/ocr/tesseract_ocr_demo_01.py

# 对比两个引擎
python tests/ocr/compare_engines.py
```

## 常见问题

### Q1: 首次运行很慢？

A: PaddleOCR 首次运行会下载模型文件（~10MB），需要等待。后续运行会很快。

### Q2: 网络问题无法下载模型？

A: 设置环境变量跳过检查：
```bash
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

或在代码中设置：
```python
import os
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
```

### Q3: 内存占用高？

A: PaddleOCR 模型较大，建议：
- 使用 GPU 加速（如果有）
- 减少并发数
- 或使用 Tesseract（更轻量）

## 总结

**推荐方案**：使用 PaddleOCR 2.7.0.3

```bash
uv remove paddleocr
uv add "paddleocr==2.7.0.3"
python tests/ocr/paddleocr_ocr_demo_01.py
```

如果仍有问题，使用 Tesseract：

```bash
python tests/ocr/tesseract_ocr_demo_01.py
```
