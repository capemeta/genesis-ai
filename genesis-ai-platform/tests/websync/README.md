# WebSync 测试说明

本目录包含两类测试：

- 真实 URL 效果测试
  - `test_trafilatura_effect.py`
  - `test_playwright_effect.py`
  - `test_readability_effect.py`
  - `test_websync_pipeline_effect.py`
- 稳定单元测试
  - `test_web_content_extractor.py`

## 一、真实 URL 效果测试

先设置环境变量：

```powershell
$env:WEBSYNC_TEST_URL="https://example.com"
```

可选环境变量：

```powershell
$env:WEBSYNC_TIMEOUT_SECONDS="20"
$env:WEBSYNC_FETCH_MODE="auto"
$env:WEBSYNC_MIN_MEANINGFUL_CHARS="200"
```

分别执行：

```powershell
genesis-ai-platform\.venv\Scripts\python.exe -m pytest genesis-ai-platform/tests/websync/test_trafilatura_effect.py -q -s
genesis-ai-platform\.venv\Scripts\python.exe -m pytest genesis-ai-platform/tests/websync/test_playwright_effect.py -q -s
genesis-ai-platform\.venv\Scripts\python.exe -m pytest genesis-ai-platform/tests/websync/test_readability_effect.py -q -s
genesis-ai-platform\.venv\Scripts\python.exe -m pytest genesis-ai-platform/tests/websync/test_websync_pipeline_effect.py -q -s
```

输出文件会写到：

```text
genesis-ai-platform/tests/websync/out/
```

文件名包含：

- 提取器前缀
- 域名
- 年月日时分秒时间戳

例如：

```text
trafilatura_effect_example_com_20260331_213000.md
playwright_effect_example_com_20260331_213015.md
readability_effect_example_com_20260331_213030.txt
websync_pipeline_example_com_20260331_213045.md
```

## 二、当前 WebSync 回归测试

这个测试不依赖真实网络，适合日常回归：

```powershell
genesis-ai-platform\.venv\Scripts\python.exe -m pytest genesis-ai-platform/tests/websync/test_web_content_extractor.py -q
```

## 三、一次性跑完整个 websync 目录

```powershell
genesis-ai-platform\.venv\Scripts\python.exe -m pytest genesis-ai-platform/tests/websync -q
```
