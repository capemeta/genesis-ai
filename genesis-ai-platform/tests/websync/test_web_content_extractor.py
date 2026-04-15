from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.websync._websync_test_utils import load_extractor_module


extractor_module = load_extractor_module()


@dataclass
class _FakeResponse:
    status_code: int
    text: str
    url: str = "https://example.com/final"
    headers: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {}


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str) -> _FakeResponse:
        return self._response


class _FakeLoop:
    def __init__(self, rendered_html: str, rendered_url: str = "https://example.com/rendered") -> None:
        self.rendered_html = rendered_html
        self.rendered_url = rendered_url
        self.calls = 0

    async def run_in_executor(self, executor, func, url: str, timeout_seconds: int) -> tuple[str, str]:
        self.calls += 1
        return self.rendered_html, self.rendered_url


def _install_http_client(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    """安装假的 httpx.AsyncClient，避免测试访问真实网络。"""

    def _client_factory(*args, **kwargs) -> _FakeAsyncClient:
        return _FakeAsyncClient(response)

    monkeypatch.setattr(extractor_module.httpx, "AsyncClient", _client_factory)


@pytest.mark.asyncio
async def test_static_trafilatura_success_without_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """静态 HTML 已能稳定抽正文时，不应进入浏览器回退。"""
    html = "<html><body><article>静态正文</article></body></html>"
    response = _FakeResponse(status_code=200, text=html)
    _install_http_client(monkeypatch, response)

    monkeypatch.setattr(
        extractor_module,
        "_extract_with_trafilatura",
        lambda source_html: "这是一段足够长的静态正文。" * 20 if source_html == html else "",
    )

    fake_loop = _FakeLoop("<html><body>浏览器正文</body></html>")
    monkeypatch.setattr(extractor_module.asyncio, "get_running_loop", lambda: fake_loop)

    result = await extractor_module.extract_web_content(url="https://example.com/source", fetch_mode="auto")

    assert result.extractor == "trafilatura"
    assert "静态正文" in result.extracted_text
    assert result.final_url == "https://example.com/final"
    assert fake_loop.calls == 0


@pytest.mark.asyncio
async def test_auto_mode_falls_back_to_browser_when_static_quality_is_poor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """静态抽取质量差时，auto 模式应回退到浏览器阶段。"""
    static_html = "<html><body><div>Loading...</div></body></html>"
    rendered_html = "<html><body><article>浏览器渲染后的正文</article></body></html>"
    response = _FakeResponse(status_code=200, text=static_html)
    _install_http_client(monkeypatch, response)

    def _fake_trafilatura(source_html: str) -> str:
        if source_html == static_html:
            return "Loading... sign in cookie"
        if source_html == rendered_html:
            return "浏览器渲染后的正文。" * 30
        return ""

    monkeypatch.setattr(extractor_module, "_extract_with_trafilatura", _fake_trafilatura)

    fake_loop = _FakeLoop(rendered_html)
    monkeypatch.setattr(extractor_module, "_get_playwright_executor", lambda: object())
    monkeypatch.setattr(extractor_module.asyncio, "get_running_loop", lambda: fake_loop)

    result = await extractor_module.extract_web_content(url="https://example.com/source", fetch_mode="auto")

    assert result.extractor == "playwright"
    assert "浏览器渲染后的正文" in result.extracted_text
    assert result.raw_html == rendered_html
    assert fake_loop.calls == 1


@pytest.mark.asyncio
async def test_readability_fallback_is_used_when_browser_trafilatura_is_still_poor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """浏览器渲染后 trafilatura 仍然很差时，应启用 readability 兜底。"""
    static_html = "<html><body><div>loading...</div></body></html>"
    rendered_html = "<html><body><main><p>readability body</p></main></body></html>"
    response = _FakeResponse(status_code=200, text=static_html)
    _install_http_client(monkeypatch, response)

    def _fake_trafilatura(source_html: str) -> str:
        if source_html == static_html:
            return ""
        if source_html == rendered_html:
            return "Home\n[Login](https://example.com/login)\nCookie"
        return ""

    monkeypatch.setattr(extractor_module, "_extract_with_trafilatura", _fake_trafilatura)
    monkeypatch.setattr(
        extractor_module,
        "_extract_with_readability",
        lambda source_html: "这是 readability 提取出的正文内容。" * 20,
    )

    fake_loop = _FakeLoop(rendered_html)
    monkeypatch.setattr(extractor_module, "_get_playwright_executor", lambda: object())
    monkeypatch.setattr(extractor_module.asyncio, "get_running_loop", lambda: fake_loop)

    result = await extractor_module.extract_web_content(url="https://example.com/source", fetch_mode="auto")

    assert result.extractor == "playwright+readability"
    assert "readability 提取出的正文内容" in result.extracted_text
    assert fake_loop.calls == 1


@pytest.mark.asyncio
async def test_raise_when_all_strategies_fail_quality_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """所有阶段都只返回噪声内容时，应明确抛出抽取失败。"""
    static_html = "<html><body><div>loading...</div></body></html>"
    rendered_html = "<html><body><nav>home login cookie</nav></body></html>"
    response = _FakeResponse(status_code=200, text=static_html)
    _install_http_client(monkeypatch, response)

    monkeypatch.setattr(
        extractor_module,
        "_extract_with_trafilatura",
        lambda source_html: "Login Cookie Loading" if source_html in {static_html, rendered_html} else "",
    )
    monkeypatch.setattr(
        extractor_module,
        "_extract_with_readability",
        lambda source_html: "Sign in Cookie Subscribe",
    )

    fake_loop = _FakeLoop(rendered_html)
    monkeypatch.setattr(extractor_module, "_get_playwright_executor", lambda: object())
    monkeypatch.setattr(extractor_module.asyncio, "get_running_loop", lambda: fake_loop)

    with pytest.raises(RuntimeError, match="网页正文抽取失败"):
        await extractor_module.extract_web_content(url="https://example.com/source", fetch_mode="auto")

    assert fake_loop.calls == 1


def test_structured_sections_keep_simple_and_complex_tables_differently() -> None:
    """简单表格应转 Markdown，复杂表格应保留 HTML table。"""
    html = """
    <html>
      <body>
        <main>
          <section>
            <h2>简单表格</h2>
            <table>
              <tr><th>字段</th><th>值</th></tr>
              <tr><td>事项类型</td><td>行政许可</td></tr>
            </table>
          </section>
          <section>
            <h2>复杂表格</h2>
            <table>
              <tr><th rowspan="2">字段</th><th colspan="2">值</th></tr>
              <tr><th>甲</th><th>乙</th></tr>
              <tr><td>办理方式</td><td>网上</td><td>窗口</td></tr>
            </table>
          </section>
        </main>
      </body>
    </html>
    """

    sections, merged_markdown = extractor_module._extract_structured_sections(html)

    assert sections
    assert "| 字段 | 值 |" in merged_markdown
    assert "<table" in merged_markdown


def test_content_selector_can_scope_extraction_region() -> None:
    """配置 CSS 选择器时，应优先抽取命中的正文区域。"""
    html = """
    <html>
      <body>
        <main class="layout">
          <div class="noise">导航与广告</div>
          <article class="article-body">
            <h1>正文标题</h1>
            <p>这是需要保留的正文内容。</p>
          </article>
        </main>
      </body>
    </html>
    """

    selected_html = extractor_module._apply_content_selector(html, ".article-body")
    fallback_html = extractor_module._apply_content_selector(html, ".not-found")

    assert "正文标题" in selected_html
    assert "导航与广告" not in selected_html
    assert "导航与广告" in fallback_html


def test_structured_sections_ignore_html_comment_children() -> None:
    """DOM 分区阶段应忽略 HtmlComment，避免 text_content 异常。"""
    html = """
    <html>
      <body>
        <main>
          <!-- 这是注释 -->
          <section>
            <h2>正文区域</h2>
            <p>这里是正文。</p>
          </section>
        </main>
      </body>
    </html>
    """

    sections, merged_markdown = extractor_module._extract_structured_sections(html)

    assert sections
    assert "正文区域" in merged_markdown
