# pytest 学习示例

这个目录专门用于学习 `pytest` 的常见用法，所有示例都尽量保持简单、可直接运行、容易改造到业务代码中。

## 推荐运行方式

请始终使用项目固定解释器：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\pytest_learning -v
```

## 常见命令

运行整个学习目录：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\pytest_learning -v
```

只运行某一个文件：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\pytest_learning\test_01_basic_assertions.py -v
```

只运行某一个测试函数：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\pytest_learning\test_01_basic_assertions.py -k string_join -v
```

显示 `print` 输出：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\pytest_learning -s -v
```

失败后立即停止：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\pytest_learning -x -v
```

只看简洁结果：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\pytest_learning -q
```

## 文件说明

- `conftest.py`: 放公共 fixture，测试目录下的用例会自动加载
- `test_01_basic_assertions.py`: 最基础的断言、异常断言
- `test_02_parametrize_and_fixture.py`: 参数化和 fixture 的典型用法
- `test_03_tmp_path_and_monkeypatch.py`: 临时目录、环境变量、替换函数
- `test_04_async_examples.py`: 异步函数测试

说明：

- 标准 `pytest` 项目里，临时目录通常优先使用内建 `tmp_path`
- 但当前这台 Windows 环境对 `pytest` 默认临时目录清理存在权限冲突
- 所以示例里额外提供了 `workspace_tmp_path` fixture，效果接近 `tmp_path`，但更适合当前仓库直接学习和运行

## 学习建议

推荐顺序：

1. 先看 `test_01_basic_assertions.py`
2. 再看 `test_02_parametrize_and_fixture.py`
3. 然后看 `test_03_tmp_path_and_monkeypatch.py`
4. 最后看 `test_04_async_examples.py`

如果你要把这些写法迁移到业务测试里，优先记住这几个点：

- 测试函数名用 `test_` 开头
- 用 `assert` 直接表达预期
- 重复准备逻辑优先抽成 fixture
- 多组输入输出优先用 `@pytest.mark.parametrize`
- 涉及文件和环境变量时，优先用 `tmp_path` 和 `monkeypatch`
