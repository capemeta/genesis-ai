from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.websync._websync_test_utils import (
    build_output_path,
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
async def test_current_websync_pipeline_with_real_url() -> None:
    """输入真实 URL，测试当前 websync 统一抽取链路的最终效果。"""
    url = get_test_url()
    if not url:
        pytest.skip("未设置 WEBSYNC_TEST_URL，跳过真实 URL 效果测试")

    fetch_mode = get_fetch_mode()
    timeout_seconds = get_timeout_seconds()
    min_meaningful_chars = get_min_meaningful_chars()

    result = await extractor_module.extract_web_content(
        url=url,
        fetch_mode=fetch_mode,
        timeout_seconds=timeout_seconds,
        min_meaningful_chars=min_meaningful_chars,
    )
    quality = extractor_module._evaluate_extraction_quality(
        result.extracted_text,
        source_html=result.raw_html,
        min_meaningful_chars=min_meaningful_chars,
    )

    report = render_report(
        title="当前 WebSync 抽取链路效果",
        url=url,
        final_url=result.final_url,
        details={
            "fetch_mode": fetch_mode,
            "timeout_seconds": timeout_seconds,
            "min_meaningful_chars": min_meaningful_chars,
            "extractor": result.extractor,
            "http_status": result.http_status,
            "etag": result.etag,
            "last_modified": result.last_modified,
            "quality": quality.as_log_payload(),
        },
        content=result.extracted_text,
    )
    output_path = build_output_path(prefix="websync_pipeline", url=result.final_url, extension="md")
    write_text_output(output_path, report)

    assert result.extracted_text.strip(), "统一抽取链路应返回非空正文"
