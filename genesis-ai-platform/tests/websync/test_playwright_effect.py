from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.websync._websync_test_utils import (
    build_output_path,
    get_test_url,
    get_timeout_seconds,
    load_extractor_module,
    render_report,
    write_text_output,
)


extractor_module = load_extractor_module()


def _build_preview_text(rendered_html: str) -> str:
    """将渲染后的 HTML 粗略转成可阅读文本，便于人工比对 Playwright 效果。"""
    preview_text = extractor_module._normalize_text(extractor_module._strip_html_tags(rendered_html))
    if len(preview_text) > 4000:
        return f"{preview_text[:4000]}\n\n[... 已截断，总长度 {len(preview_text)} 字符 ...]"
    return preview_text


def test_playwright_effect_with_real_url() -> None:
    """输入真实 URL，观察 Playwright 渲染后的 DOM 效果。"""
    url = get_test_url()
    if not url:
        pytest.skip("未设置 WEBSYNC_TEST_URL，跳过真实 URL 效果测试")

    timeout_seconds = get_timeout_seconds()
    try:
        rendered_html, final_url = extractor_module._run_playwright_sync(url, timeout_seconds)
    except ModuleNotFoundError as exc:
        pytest.skip(f"当前环境未安装 Playwright 依赖: {exc}")

    preview_text = _build_preview_text(rendered_html)
    report = render_report(
        title="Playwright 渲染效果",
        url=url,
        final_url=final_url,
        details={
            "rendered_html_length": len(rendered_html),
            "preview_text_length": len(preview_text),
        },
        content=preview_text,
    )
    output_path = build_output_path(prefix="playwright_effect", url=final_url, extension="md")
    write_text_output(output_path, report)

    assert rendered_html.strip(), "Playwright 渲染后的 HTML 不能为空"
