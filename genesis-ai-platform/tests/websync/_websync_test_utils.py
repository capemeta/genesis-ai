from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path(__file__).resolve().parent
OUT_DIR = TEST_ROOT / "out"


def load_extractor_module():
    """按文件路径加载抽取模块，避免导入 services 包时触发其他配置副作用。"""
    module_name = "tests_websync_web_content_extractor"
    module_path = PROJECT_ROOT / "services" / "web_content_extractor.py"
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"无法加载模块: {module_path}")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = module
    module_spec.loader.exec_module(module)
    return module


def get_test_url() -> str | None:
    """读取真实 URL 测试输入。未提供时由调用方决定是否跳过。"""
    value = os.getenv("WEBSYNC_TEST_URL", "").strip()
    return value or None


def get_timeout_seconds(default: int = 20) -> int:
    """读取测试超时秒数。"""
    raw_value = os.getenv("WEBSYNC_TIMEOUT_SECONDS", "").strip()
    if not raw_value:
        return default
    try:
        return max(1, int(raw_value))
    except ValueError:
        return default


def get_fetch_mode(default: str = "auto") -> str:
    """读取当前 websync 测试使用的抓取模式。"""
    fetch_mode = os.getenv("WEBSYNC_FETCH_MODE", "").strip().lower()
    if fetch_mode in {"auto", "static", "browser"}:
        return fetch_mode
    return default


def get_min_meaningful_chars(default: int = 200) -> int:
    """读取正文最小有效字符阈值。"""
    raw_value = os.getenv("WEBSYNC_MIN_MEANINGFUL_CHARS", "").strip()
    if not raw_value:
        return default
    try:
        return max(1, int(raw_value))
    except ValueError:
        return default


def get_content_selector() -> str | None:
    """读取可选的 CSS 正文选择器。"""
    value = os.getenv("WEBSYNC_CONTENT_SELECTOR", "").strip()
    return value or None


def build_output_path(*, prefix: str, url: str, extension: str) -> Path:
    """为输出文件生成带域名和时间戳的稳定文件名。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    host = parsed.netloc or "unknown-host"
    safe_host = "".join(ch if ch.isalnum() else "_" for ch in host).strip("_") or "unknown_host"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OUT_DIR / f"{prefix}_{safe_host}_{timestamp}.{extension}"


def write_text_output(path: Path, content: str) -> None:
    """写出 UTF-8 文本结果。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_report(*, title: str, url: str, final_url: str, details: dict[str, object], content: str) -> str:
    """生成统一的 Markdown 报告，方便人工比对不同提取器效果。"""
    detail_lines = "\n".join(f"- {key}: {value}" for key, value in details.items())
    body = content.strip() or "（空内容）"
    return (
        f"# {title}\n\n"
        f"- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 输入 URL: {url}\n"
        f"- 最终 URL: {final_url}\n"
        f"{detail_lines}\n\n"
        f"## 输出内容\n\n"
        f"{body}\n"
    )
