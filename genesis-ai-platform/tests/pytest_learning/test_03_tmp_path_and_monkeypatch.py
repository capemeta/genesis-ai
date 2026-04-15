from __future__ import annotations

import os
import sys
from pathlib import Path

from pytest import MonkeyPatch


def read_app_mode() -> str:
    """演示从环境变量中读取配置。"""

    return os.getenv("APP_MODE", "dev")


def load_text(path: Path) -> str:
    """演示读取文件内容的简单函数。"""

    return path.read_text(encoding="utf-8")


def get_now_label() -> str:
    """演示 monkeypatch 替换函数返回值。"""

    return "real-time"


def build_message() -> str:
    """组合内部函数，便于观察 monkeypatch 的效果。"""

    return f"current:{get_now_label()}"


def test_workspace_tmp_path_can_create_temp_file(workspace_tmp_path: Path) -> None:
    """在当前仓库环境中演示“临时目录”测试模式。"""

    demo_file = workspace_tmp_path / "demo.txt"
    demo_file.write_text("pytest 学习示例", encoding="utf-8")

    assert load_text(demo_file) == "pytest 学习示例"


def test_monkeypatch_can_override_env(monkeypatch: MonkeyPatch) -> None:
    """monkeypatch 很适合安全地改环境变量。"""

    monkeypatch.setenv("APP_MODE", "test")
    assert read_app_mode() == "test"


def test_monkeypatch_can_replace_function(monkeypatch: MonkeyPatch) -> None:
    """monkeypatch 也可以替换当前模块里的函数实现。"""

    monkeypatch.setattr(sys.modules[__name__], "get_now_label", lambda: "mocked")
    assert build_message() == "current:mocked"
