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


@pytest.mark.asyncio
async def test_readability_effect_with_real_url() -> None:
    """输入真实 URL，观察 readability-lxml 的正文提纯效果。"""
    url = get_test_url()
    if not url:
        pytest.skip("未设置 WEBSYNC_TEST_URL，跳过真实 URL 效果测试")

    timeout_seconds = get_timeout_seconds()
    async with extractor_module.httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text or ""
        final_url = str(response.url)

    extracted_text = extractor_module._extract_with_readability(html)
    quality = extractor_module._evaluate_extraction_quality(
        extracted_text,
        source_html=html,
        min_meaningful_chars=200,
    )

    report = render_report(
        title="Readability-LXML 提纯效果",
        url=url,
        final_url=final_url,
        details={
            "http_status": response.status_code,
            "html_length": len(html),
            "extracted_length": len(extracted_text),
            "quality": quality.as_log_payload(),
        },
        content=extracted_text,
    )
    output_path = build_output_path(prefix="readability_effect", url=final_url, extension="txt")
    write_text_output(output_path, report)

    assert html.strip(), "输入 HTML 不能为空"
