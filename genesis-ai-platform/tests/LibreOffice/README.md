# LibreOffice DOCX 转 PDF 测试

## 📁 文件说明

- `test_docx_to_pdf.py` - 完整的测试套件（包含 pytest 测试用例）
- `test_specific_file.py` - 针对特定文件的测试脚本
- `convert_manual.py` - 最简单的手动转换脚本

## 🚀 快速开始

### 方法 1: 使用最简单的转换脚本（推荐）

```bash
cd genesis-ai-platform/tests/libreoffice
python convert_manual.py
```

这个脚本会：
1. 转换指定的 DOCX 文件
2. 输出转换结果
3. 自动打开生成的 PDF

### 方法 2: 使用详细测试脚本

```bash
cd genesis-ai-platform/tests/libreoffice
python test_specific_file.py
```

这个脚本会：
1. 检查文件是否存在
2. 验证 LibreOffice 安装
3. 执行转换
4. 显示详细统计信息
5. 自动打开 PDF

### 方法 3: 使用 pytest 运行完整测试

```bash
cd genesis-ai-platform
pytest tests/libreoffice/test_docx_to_pdf.py -v
```

## ⚙️ 配置

### 修改 LibreOffice 路径

如果你的 LibreOffice 安装在其他位置，修改脚本中的路径：

```python
# 在 convert_manual.py 中
LIBREOFFICE_PATH = r"D:\Software\system\LibreOffice\program\soffice.exe"
```

### 修改要转换的文件

```python
# 在 convert_manual.py 中
DOCX_FILE = r"C:\Users\csl2021\Downloads\云视频视频客服（客服端）操作手册V1.0.docx"
```

## 📋 测试内容

测试脚本会验证以下内容：

1. ✅ LibreOffice 是否正确安装
2. ✅ DOCX 文件是否存在
3. ✅ 转换是否成功
4. ✅ PDF 文件是否生成
5. ✅ 文件大小是否合理
6. ✅ 转换速度统计

## 🔍 检查转换质量

转换完成后，请手动检查 PDF 文件：

- [ ] 页码是否正确递增（不是所有页都显示 2）
- [ ] 版本记录和目录是否在正确的页面
- [ ] 页眉页脚是否正确显示
- [ ] 图片和表格是否正常
- [ ] 文字格式是否保留
- [ ] 分页位置是否合理

## 📊 预期结果

### 转换质量对比

| 项目 | docx-preview | LibreOffice PDF |
|------|--------------|-----------------|
| 页码 | ❌ 所有页显示 2 | ✅ 正确递增 |
| 分页 | ❌ 内容重叠 | ✅ 正确分页 |
| 目录 | ❌ 位置错误 | ✅ 位置正确 |
| 整体还原度 | 60-70% | 80-85% |

### 性能指标

- 转换速度: 2-10 秒（取决于文档复杂度）
- 文件大小: PDF 约为 DOCX 的 1.5-2 倍
- 内存占用: 200-500 MB

## 🐛 常见问题

### 问题 1: LibreOffice 未找到

```
FileNotFoundError: LibreOffice 未找到: D:\Software\system\LibreOffice\program\soffice.exe
```

**解决方法**:
1. 检查 LibreOffice 是否已安装
2. 确认安装路径是否正确
3. 修改脚本中的 `LIBREOFFICE_PATH`

### 问题 2: 转换超时

```
TimeoutError: 转换超时（120秒）
```

**解决方法**:
1. 增加超时时间（在代码中修改 `timeout` 参数）
2. 检查文档是否过大或过于复杂
3. 尝试简化文档内容

### 问题 3: PDF 文件未生成

```
RuntimeError: PDF 文件未生成
```

**解决方法**:
1. 检查 DOCX 文件是否损坏
2. 尝试用 Word 打开并重新保存
3. 查看 LibreOffice 的错误输出

## 📝 下一步

如果测试成功，可以：

1. 集成到后端 API
2. 添加 Celery 异步任务
3. 实现缓存机制
4. 添加前端预览界面

## 🔗 相关文档

- [LibreOffice 官网](https://www.libreoffice.org/)
- [LibreOffice 命令行参数](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)
