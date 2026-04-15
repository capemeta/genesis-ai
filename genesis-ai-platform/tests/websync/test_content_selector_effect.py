from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.websync._websync_test_utils import (
    build_output_path,
    get_content_selector,
    get_fetch_mode,
    get_min_meaningful_chars,
    get_test_url,
    get_timeout_seconds,
    load_extractor_module,
    render_report,
    write_text_output,
)


extractor_module = load_extractor_module()


@pytest.mark.asyncio
async def test_content_selector_effect_with_real_url() -> None:
    """对比全页抽取与 selector 抽取效果，并分别输出结果文件。"""
    url = get_test_url()
    selector = get_content_selector()
    if not url:
        pytest.skip("未设置 WEBSYNC_TEST_URL，跳过真实 URL 效果测试")
    if not selector:
        pytest.skip("未设置 WEBSYNC_CONTENT_SELECTOR，跳过 selector 效果测试")

    fetch_mode = get_fetch_mode()
    timeout_seconds = get_timeout_seconds()
    min_meaningful_chars = get_min_meaningful_chars()

    default_result = await extractor_module.extract_web_content(
        url=url,
        fetch_mode=fetch_mode,
        timeout_seconds=timeout_seconds,
        min_meaningful_chars=min_meaningful_chars,
    )
    selector_result = await extractor_module.extract_web_content(
        url=url,
        fetch_mode=fetch_mode,
        timeout_seconds=timeout_seconds,
        min_meaningful_chars=min_meaningful_chars,
        content_selector=selector,
    )

    default_report = render_report(
        title="全页 WebSync 抽取效果",
        url=url,
        final_url=default_result.final_url,
        details={
            "fetch_mode": fetch_mode,
            "timeout_seconds": timeout_seconds,
            "min_meaningful_chars": min_meaningful_chars,
            "content_selector": "（未指定）",
            "extractor": default_result.extractor,
            "http_status": default_result.http_status,
            "quality_summary": default_result.quality_summary,
        },
        content=default_result.extracted_text,
    )
    selector_report = render_report(
        title="Selector WebSync 抽取效果",
        url=url,
        final_url=selector_result.final_url,
        details={
            "fetch_mode": fetch_mode,
            "timeout_seconds": timeout_seconds,
            "min_meaningful_chars": min_meaningful_chars,
            "content_selector": selector,
            "extractor": selector_result.extractor,
            "http_status": selector_result.http_status,
            "quality_summary": selector_result.quality_summary,
        },
        content=selector_result.extracted_text,
    )

    default_output_path = build_output_path(prefix="websync_default_effect", url=default_result.final_url, extension="md")
    selector_output_path = build_output_path(prefix="websync_selector_effect", url=selector_result.final_url, extension="md")
    write_text_output(default_output_path, default_report)
    write_text_output(selector_output_path, selector_report)

    assert selector_result.extracted_text.strip(), "selector 抽取结果不能为空"
