"""
网页内容抽取工具

统一抽取链路：
- httpx + trafilatura
- Playwright fallback（在独立子进程中运行，彻底绕开 Windows asyncio 子进程限制）
- readability-lxml fallback
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import platform
import re
import ssl
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass

import httpx
import trafilatura
from lxml import html as lxml_html  # type: ignore[import-untyped]
from readability import Document as ReadabilityDocument

# 全局复用的进程池，最多 2 个 worker，避免频繁创建/销毁进程开销。
# Playwright 在子进程中运行，完全隔离父进程的 asyncio 事件循环。
_playwright_executor: ProcessPoolExecutor | None = None
logger = logging.getLogger(__name__)

# 这些标记通常意味着页面正文尚未正确暴露，或当前抽取结果更接近壳页面/拦截页。
_SUSPICIOUS_TEXT_MARKERS = (
    "enable javascript",
    "please enable javascript",
    "javascript is required",
    "requires javascript",
    "verify you are human",
    "access denied",
    "just a moment",
    "checking your browser",
    "please wait",
    "loading",
    "sign in",
    "log in",
    "cookie",
    "subscribe",
)


def _get_playwright_executor() -> ProcessPoolExecutor:
    """惰性初始化 Playwright 专用进程池。"""
    global _playwright_executor
    if _playwright_executor is None:
        import os
        from pathlib import Path

        # 在 Windows spawn 模式下，子进程是全新的解释器，默认 sys.path 可能不包含项目根目录。
        # 通过在创建进程池前将项目根目录添加到 PYTHONPATH 环境，确保 spawned 子进程能够正确导入项目模块。
        # 这对于子进程在 unpickle 任务函数时能够成功导入定义该函数的模块至关重要。
        project_root = str(Path(__file__).resolve().parent.parent)
        current_pythonpath = os.environ.get("PYTHONPATH", "")
        if project_root not in current_pythonpath.split(os.pathsep):
            new_pythonpath = f"{project_root}{os.pathsep}{current_pythonpath}" if current_pythonpath else project_root
            os.environ["PYTHONPATH"] = new_pythonpath

        # Windows 上必须使用 spawn 上下文，回避 SelectorEventLoop 不支持子进程的问题。
        if platform.system() == "Windows":
            mp_context = multiprocessing.get_context("spawn")
            _playwright_executor = ProcessPoolExecutor(max_workers=2, mp_context=mp_context)
        else:
            # Linux 上默认使用 fork，此时直接继承父进程内存空间和 sys.path。
            _playwright_executor = ProcessPoolExecutor(max_workers=2)
    return _playwright_executor


def _reset_playwright_executor() -> None:
    """重置损坏的 Playwright 进程池，避免后续任务持续命中 broken pool。"""
    global _playwright_executor
    executor = _playwright_executor
    _playwright_executor = None
    if executor is not None:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception:  # noqa: BLE001
            logger.warning("关闭损坏的 Playwright 进程池失败", exc_info=True)


@dataclass
class WebExtractResult:
    """网页抽取结果。"""

    extracted_text: str
    raw_html: str
    extraction_html: str  # 新增：经过选择器裁剪后的 HTML 片段
    final_url: str
    http_status: int | None
    etag: str | None
    last_modified: str | None
    extractor: str
    quality_summary: dict[str, object]
    structured_sections: list[dict[str, object]]


@dataclass(frozen=True)
class ExtractionQuality:
    """抽取质量评估结果。"""

    meaningful_chars: int
    paragraph_count: int
    link_line_ratio: float
    html_text_chars: int
    suspicious_markers: tuple[str, ...]
    score: int

    @property
    def is_meaningful(self) -> bool:
        """是否可以认为当前结果足够接近正文。"""
        return self.score >= 2 and self.meaningful_chars >= 50

    def as_log_payload(self) -> dict[str, object]:
        """将质量评估转换为便于日志检索的结构。"""
        return {
            "meaningful_chars": self.meaningful_chars,
            "paragraph_count": self.paragraph_count,
            "link_line_ratio": round(self.link_line_ratio, 4),
            "html_text_chars": self.html_text_chars,
            "suspicious_markers": list(self.suspicious_markers),
            "score": self.score,
            "is_meaningful": self.is_meaningful,
        }


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"\r\n?", "\n", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized.strip()


def _strip_html_tags(html: str) -> str:
    text = re.sub(r"<script.*?>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _markdown_to_plain_text(text: str) -> str:
    """将 Markdown 粗略转为纯文本，便于做质量评估。"""
    normalized = text or ""
    normalized = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", normalized)
    normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized)
    normalized = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", normalized)
    normalized = re.sub(r"^[>#*\-\d\.\)\s]+", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"[*_~#]+", "", normalized)
    return _normalize_text(normalized)


def _count_meaningful_chars(text: str) -> int:
    """统计字母、数字和中日韩文字，避免纯空白或符号误判为正文。"""
    return len(re.findall(r"[0-9A-Za-z\u4e00-\u9fff]", text or ""))


def _count_link_lines(text: str) -> int:
    """统计明显以链接为主的行，用于识别导航/目录型结果。"""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    link_line_count = 0
    for line in lines:
        markdown_links = len(re.findall(r"\[[^\]]+\]\([^)]+\)", line))
        urls = len(re.findall(r"https?://", line, flags=re.IGNORECASE))
        meaningful_chars = _count_meaningful_chars(line)
        if markdown_links >= 2 or (markdown_links >= 1 and meaningful_chars <= 40) or (urls >= 1 and meaningful_chars <= 30):
            link_line_count += 1
    return link_line_count


def _evaluate_extraction_quality(
    extracted_text: str,
    *,
    source_html: str,
    min_meaningful_chars: int,
) -> ExtractionQuality:
    """
    评估当前抽取结果质量。

    这里不只看字符数，而是综合正文长度、段落密度、链接占比和可疑模板词，
    避免把“抽到了少量噪声”误判成成功。
    """
    plain_text = _markdown_to_plain_text(extracted_text)
    html_text = _normalize_text(_strip_html_tags(source_html))
    meaningful_chars = _count_meaningful_chars(plain_text)
    paragraphs = [
        line.strip()
        for line in plain_text.splitlines()
        if _count_meaningful_chars(line.strip()) >= 20
    ]
    paragraph_count = len(paragraphs)
    non_empty_lines = [line.strip() for line in plain_text.splitlines() if line.strip()]
    link_line_count = _count_link_lines(extracted_text)
    link_line_ratio = (link_line_count / len(non_empty_lines)) if non_empty_lines else 0.0

    lowered_plain = plain_text.casefold()
    lowered_html = html_text.casefold()
    suspicious_markers = tuple(
        marker for marker in _SUSPICIOUS_TEXT_MARKERS if marker in lowered_plain or marker in lowered_html
    )
    html_text_chars = _count_meaningful_chars(html_text)

    score = 0
    if meaningful_chars >= max(80, min_meaningful_chars // 2):
        score += 1
    if meaningful_chars >= min_meaningful_chars:
        score += 2
    if meaningful_chars >= max(500, min_meaningful_chars * 2):
        score += 1
    if paragraph_count >= 2:
        score += 1
    if paragraph_count >= 4:
        score += 1
    if meaningful_chars < 50:
        score -= 2
    if link_line_ratio >= 0.5:
        score -= 2
    if html_text_chars >= max(800, min_meaningful_chars * 4) and meaningful_chars < max(120, min_meaningful_chars // 2):
        score -= 2
    if suspicious_markers:
        score -= min(3, len(suspicious_markers))

    return ExtractionQuality(
        meaningful_chars=meaningful_chars,
        paragraph_count=paragraph_count,
        link_line_ratio=link_line_ratio,
        html_text_chars=html_text_chars,
        suspicious_markers=suspicious_markers,
        score=score,
    )


def _should_fallback_to_browser(quality: ExtractionQuality, *, min_meaningful_chars: int) -> bool:
    """判断是否值得进入浏览器渲染阶段。"""
    if not quality.is_meaningful:
        if quality.meaningful_chars < min_meaningful_chars:
            return True
        if quality.suspicious_markers:
            return True
        if quality.link_line_ratio >= 0.5:
            return True
        if quality.html_text_chars >= max(1200, min_meaningful_chars * 6) and quality.paragraph_count <= 1:
            return True
    return False


def _should_try_readability(quality: ExtractionQuality, *, min_meaningful_chars: int) -> bool:
    """判断是否应该尝试 readability 兜底。"""
    if quality.is_meaningful:
        return False
    if quality.meaningful_chars == 0:
        return True
    if quality.suspicious_markers:
        return True
    if quality.link_line_ratio >= 0.5:
        return True
    if quality.meaningful_chars < max(120, min_meaningful_chars // 2):
        return True
    return quality.html_text_chars >= max(1000, min_meaningful_chars * 5)


def _extract_with_trafilatura(html: str) -> str:
    """统一封装 trafilatura 抽取和归一化。"""
    extracted = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        include_tables=True,
    ) or ""
    return _normalize_text(extracted)


def _extract_with_readability(html: str) -> str:
    """使用 readability 做纯文本兜底抽取。"""
    summary_html = ReadabilityDocument(html).summary() or ""
    return _normalize_text(_strip_html_tags(summary_html))


def _normalize_inline_text(text: str) -> str:
    """归一化行内文本，避免 DOM 文本节点拼接过脏。"""
    return re.sub(r"\s{2,}", " ", str(text or "")).strip()


def _is_html_element(node) -> bool:
    """过滤注释、文本节点等非标准 HTML Element。"""
    return isinstance(getattr(node, "tag", None), str)


def _extract_element_text(element) -> str:
    """从 DOM 元素提取纯文本。"""
    if element is None or not _is_html_element(element):
        return ""
    return _normalize_text(_normalize_inline_text(element.text_content()))


def _is_simple_table(table_element) -> bool:
    """判断表格是否适合安全转换为 Markdown。"""
    rows = table_element.xpath(".//tr")
    if len(rows) < 2:
        return False
    if table_element.xpath(".//*[@rowspan or @colspan]"):
        return False

    parsed_rows: list[list[str]] = []
    header_row_count = 0
    for row in rows:
        th_cells = row.xpath("./th")
        td_cells = row.xpath("./td")
        cells = th_cells or td_cells
        if not cells:
            continue
        if th_cells:
            header_row_count += 1
        parsed_row = [_normalize_inline_text(cell.text_content()) for cell in cells]
        if not any(parsed_row):
            continue
        parsed_rows.append(parsed_row)

    if len(parsed_rows) < 2:
        return False
    if header_row_count > 1:
        return False

    col_count = len(parsed_rows[0])
    if col_count <= 1 or col_count > 8:
        return False
    if any(len(row) != col_count for row in parsed_rows):
        return False
    if any(any("\n" in cell or len(cell) > 120 for cell in row) for row in parsed_rows):
        return False
    return True


def _escape_markdown_table_cell(text: str) -> str:
    """转义 Markdown 表格单元格中的分隔符。"""
    return str(text or "").replace("|", "\\|").replace("\n", "<br>")


def _table_to_markdown(table_element) -> str:
    """将简单 HTML 表格转为 Markdown 表格。"""
    rows = table_element.xpath(".//tr")
    parsed_rows: list[list[str]] = []
    for row in rows:
        cells = row.xpath("./th|./td")
        if not cells:
            continue
        parsed_row = [_escape_markdown_table_cell(_normalize_inline_text(cell.text_content())) for cell in cells]
        if any(parsed_row):
            parsed_rows.append(parsed_row)
    if len(parsed_rows) < 2:
        return ""

    header = parsed_rows[0]
    body = parsed_rows[1:]
    separator = ["---"] * len(header)
    lines = [
        f"| {' | '.join(header)} |",
        f"| {' | '.join(separator)} |",
    ]
    lines.extend(f"| {' | '.join(row)} |" for row in body)
    return "\n".join(lines)


def _table_to_preserved_markup(table_element) -> tuple[str, str]:
    """简单表格转 Markdown，复杂表格保留 HTML table。"""
    if _is_simple_table(table_element):
        markdown_table = _table_to_markdown(table_element)
        if markdown_table:
            return markdown_table, "markdown"
    html_table = lxml_html.tostring(table_element, encoding="unicode", method="html")
    return _normalize_text(html_table), "html"


def _apply_content_selector(html: str, selector: str | None, *, url: str | None = None) -> str:
    """按可选 CSS 选择器裁剪正文范围，并可选补全相对路径链接为绝对路径。"""
    if not html:
        return ""
    try:
        root = lxml_html.fromstring(html)
        if url:
            root.make_links_absolute(url)
    except Exception as exc:
        logger.warning("解析 HTML 失败或补全链接失败 url=%s error=%s", url, exc)
        return html

    normalized_selector = str(selector or "").strip()
    if not normalized_selector:
        # 即使没有选择器，我们也返回补全过链接的整个 HTML 情况。
        return lxml_html.tostring(root, encoding="unicode", method="html")

    try:
        matched_elements = root.cssselect(normalized_selector)
    except Exception as exc:
        logger.warning("网页内容选择器语法无效，已回退到全页抽取 selector=%s error=%s", normalized_selector, exc)
        return lxml_html.tostring(root, encoding="unicode", method="html")

    if not matched_elements:
        logger.info("网页内容选择器未命中任何节点，已回退到全页抽取 selector=%s", normalized_selector)
        return lxml_html.tostring(root, encoding="unicode", method="html")

    wrapper = lxml_html.Element("div")
    for element in matched_elements:
        wrapper.append(lxml_html.fragment_fromstring(lxml_html.tostring(element, encoding="unicode", method="html")))
    selected_html = lxml_html.tostring(wrapper, encoding="unicode", method="html")
    return _normalize_text(selected_html) or html


def _score_dom_container(element) -> float:
    """对候选正文容器打分，倾向文本密集、链接噪声少、包含表格的区域。"""
    text = _extract_element_text(element)
    meaningful_chars = _count_meaningful_chars(text)
    links = element.xpath(".//a")
    link_text_chars = sum(_count_meaningful_chars(_extract_element_text(link)) for link in links)
    table_count = len(element.xpath(".//table"))
    heading_count = len(element.xpath(".//h1|.//h2|.//h3"))
    return float(meaningful_chars - link_text_chars * 0.4 + table_count * 80 + heading_count * 40)


def _pick_main_container(root):
    """选择最可能的正文主容器。"""
    candidates = [element for element in root.xpath("//main | //article | //section | //div[@role='main'] | //body") if _is_html_element(element)]
    if not candidates:
        return root
    best_element = candidates[-1]
    best_score = float("-inf")
    for element in candidates:
        score = _score_dom_container(element)
        if score > best_score:
            best_score = score
            best_element = element
    return best_element


def _iter_section_roots(main_element) -> list:
    """枚举一级区块，尽量保留页面分区。"""
    children = [child for child in main_element if _is_html_element(child)]
    section_roots = []
    for child in children:
        text = _extract_element_text(child)
        if _count_meaningful_chars(text) < 30 and not child.xpath(".//table"):
            continue
        section_roots.append(child)
    return section_roots or [main_element]


def _infer_section_type(section_element, section_title: str, markdown: str) -> str:
    """基于通用语义线索推断区块类型，不对具体站点写死。"""
    tag_name = str(getattr(section_element, "tag", "") or "").lower()
    low_title = str(section_title or "").strip().lower()
    low_markdown = markdown.lower()
    if tag_name == "aside":
        return "sidebar"
    if "<table" in low_markdown or "\n| " in markdown:
        return "table_section"
    if any(token in low_title for token in {"咨询", "contact", "help", "服务窗口"}):
        return "sidebar"
    if any(token in low_title for token in {"流程", "步骤", "guide", "faq", "常见问题"}):
        return "content_section"
    if any(token in low_markdown for token in {"在线办理", "立即办理", "查看评价", "下载办事指南"}):
        return "summary"
    return "section"


def _render_section_markdown(
    section_element,
    *,
    url: str,
    canonical_url: str,
    starting_dom_index: int,
) -> tuple[str, str, list[dict[str, object]], int]:
    """将区块 DOM 渲染为 Markdown/HTML 混合文本，并保留 block 级结构。"""
    markdown_blocks: list[str] = []
    structured_blocks: list[dict[str, object]] = []
    title = ""
    dom_index = starting_dom_index
    nodes = section_element.xpath(
        ".//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6 or self::p or self::li or self::dt or self::dd or self::table]"
    )
    for node in nodes:
        if node.xpath("ancestor::table") and str(getattr(node, "tag", "")).lower() != "table":
            continue
        tag_name = str(getattr(node, "tag", "") or "").lower()
        source_ref = {
            "ref_type": "web_anchor",
            "url": url,
            "canonical_url": canonical_url,
            "heading_path": [title] if title else [],
            "anchor_text": title,
            "dom_index": dom_index,
        }
        if tag_name.startswith("h") and len(tag_name) == 2 and tag_name[1].isdigit():
            heading_level = min(6, max(1, int(tag_name[1])))
            heading_text = _extract_element_text(node)
            if not heading_text:
                continue
            if not title:
                title = heading_text
                source_ref["heading_path"] = [title]
                source_ref["anchor_text"] = title
            heading_markdown = f"{'#' * heading_level} {heading_text}"
            markdown_blocks.append(heading_markdown)
            structured_blocks.append(
                {
                    "block_id": f"b{dom_index}",
                    "type": "heading",
                    "text": heading_markdown,
                    "dom_index": dom_index,
                    "source_refs": [dict(source_ref)],
                }
            )
            dom_index += 1
            continue
        if tag_name == "table":
            table_markup, table_format = _table_to_preserved_markup(node)
            if table_markup:
                markdown_blocks.append(table_markup)
                structured_blocks.append(
                    {
                        "block_id": f"b{dom_index}",
                        "type": "table",
                        "text": table_markup,
                        "table_format": table_format,
                        "dom_index": dom_index,
                        "source_refs": [dict(source_ref)],
                    }
                )
                dom_index += 1
            continue
        text = _extract_element_text(node)
        if not text:
            continue
        if tag_name == "li":
            rendered_text = f"- {text}"
        elif tag_name == "dd":
            rendered_text = f"  {text}"
        else:
            rendered_text = text
        markdown_blocks.append(rendered_text)
        structured_blocks.append(
            {
                "block_id": f"b{dom_index}",
                "type": "text",
                "text": rendered_text,
                "dom_index": dom_index,
                "source_refs": [dict(source_ref)],
            }
        )
        dom_index += 1

    if not markdown_blocks:
        fallback_text = _extract_element_text(section_element)
        if fallback_text:
            markdown_blocks.append(fallback_text)
            structured_blocks.append(
                {
                    "block_id": f"b{dom_index}",
                    "type": "text",
                    "text": fallback_text,
                    "dom_index": dom_index,
                    "source_refs": [
                        {
                            "ref_type": "web_anchor",
                            "url": url,
                            "canonical_url": canonical_url,
                            "heading_path": [title] if title else [],
                            "anchor_text": title,
                            "dom_index": dom_index,
                        }
                    ],
                }
            )
            dom_index += 1
    return _normalize_text("\n\n".join(markdown_blocks)), title, structured_blocks, dom_index


def _extract_structured_sections(html: str) -> tuple[list[dict[str, object]], str]:
    """基于通用 DOM 结构提取页面区块，并在表格处尽量保真。"""
    raw_html = str(html or "").strip()
    if not raw_html:
        return [], ""
    try:
        root = lxml_html.fromstring(raw_html)
    except Exception:
        return [], ""

    for bad_node in root.xpath("//script | //style | //noscript | //template"):
        parent = bad_node.getparent()
        if parent is not None:
            parent.remove(bad_node)

    main_element = _pick_main_container(root)
    section_roots = _iter_section_roots(main_element)
    sections: list[dict[str, object]] = []
    merged_markdown_parts: list[str] = []
    canonical_url = ""
    dom_index = 0

    for idx, section_root in enumerate(section_roots, start=1):
        markdown, title, structured_blocks, dom_index = _render_section_markdown(
            section_root,
            url="",
            canonical_url=canonical_url,
            starting_dom_index=dom_index,
        )
        if not markdown:
            continue
        section_type = _infer_section_type(section_root, title, markdown)
        section_payload: dict[str, object] = {
            "section_id": f"s{idx}",
            "section_type": section_type,
            "title": title,
            "heading_path": [title] if title else [],
            "markdown": markdown,
            "blocks": structured_blocks,
            "text_length": len(markdown),
        }
        sections.append(section_payload)
        merged_markdown_parts.append(markdown)

    merged_markdown = _normalize_text("\n\n".join(merged_markdown_parts))
    return sections, merged_markdown


def _log_stage_decision(
    *,
    stage: str,
    url: str,
    fetch_mode: str,
    extractor: str,
    quality: ExtractionQuality,
    decision: str,
) -> None:
    """记录抽取阶段决策，便于后续基于真实站点调优阈值。"""
    logger.info(
        "网页内容抽取阶段决策 stage=%s decision=%s fetch_mode=%s extractor=%s url=%s quality=%s",
        stage,
        decision,
        fetch_mode,
        extractor,
        url,
        quality.as_log_payload(),
    )


async def extract_web_content(
    *,
    url: str,
    fetch_mode: str = "auto",
    timeout_seconds: int = 20,
    min_meaningful_chars: int = 200,
    content_selector: str | None = None,
) -> WebExtractResult:
    """
    执行网页正文抽取。

    返回值中的 `raw_html` 会尽量保留用于快照存档。
    """
    html = ""
    final_url = url
    http_status = None
    etag = None
    last_modified = None
    extractor = "trafilatura"
    selector = str(content_selector or "").strip() or None

    # 创建定制的 SSL 上下文以允许旧版重协商 (unsafe legacy renegotiation)
    # 这对于抓取一些 SSL 配置较旧的政府或机构网站是必要的。
    ssl_context = ssl.create_default_context()
    ssl_context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT

    async with httpx.AsyncClient(
        timeout=timeout_seconds,
        follow_redirects=True,
        verify=ssl_context,
    ) as client:
        resp = await client.get(url)
        http_status = resp.status_code
        final_url = str(resp.url)
        etag = resp.headers.get("etag")
        last_modified = resp.headers.get("last-modified")
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}")
        html = resp.text or ""

    extracted = ""
    if html:
        extraction_html = _apply_content_selector(html, selector, url=final_url)
        extracted = _extract_with_trafilatura(extraction_html)
        # 阶梯式回退抽取：
        if not extracted and selector:
            # 1. 尝试使用 readability 强行抽取。
            extracted = _extract_with_readability(extraction_html)
            if not extracted:
                # 2. 如果算法层都失败了，则直接暴力剥离所有标签拿到纯文本，满足用户明确指定区域的意愿。
                extracted = _normalize_text(_strip_html_tags(extraction_html))
    quality = _evaluate_extraction_quality(
        extracted,
        source_html=extraction_html if html else html,
        min_meaningful_chars=min_meaningful_chars,
    )
    _log_stage_decision(
        stage="static_trafilatura",
        url=final_url,
        fetch_mode=fetch_mode,
        extractor=extractor,
        quality=quality,
        decision="fallback_to_browser" if fetch_mode in {"auto", "browser"} and _should_fallback_to_browser(
            quality,
            min_meaningful_chars=min_meaningful_chars,
        ) else "accept",
    )

    should_use_browser = fetch_mode in {"auto", "browser"} and _should_fallback_to_browser(
        quality,
        min_meaningful_chars=min_meaningful_chars,
    )
    if should_use_browser:
        # fetch_mode="static" 时则不走 Playwright，适用于不需要 JS 渲染的静态页面。
        extractor = "playwright"
        # Playwright 需在独立子进程中运行（ProcessPoolExecutor），彻底隔离父进程 asyncio 事件循环。
        # Windows 上父进程 SelectorEventLoop 不支持子进程，子进程默认 ProactorEventLoop 与 Playwright 完全兼容。
        # asyncio.get_running_loop() 是在协程内获取当前 loop 的正确 API（Python 3.10+ 不再推荐 get_event_loop）
        loop = asyncio.get_running_loop()
        try:
            rendered_html, rendered_url = await loop.run_in_executor(
                _get_playwright_executor(), _run_playwright_sync, url, timeout_seconds
            )
        except BrokenProcessPool:
            # 某个浏览器子进程异常退出后，旧进程池会进入 broken 状态；
            # 这里主动重建一次，并仅重试当前页面一次，避免单站点故障污染整个 worker。
            logger.warning("Playwright 进程池已损坏，准备重建后重试 url=%s", url, exc_info=True)
            _reset_playwright_executor()
            rendered_html, rendered_url = await loop.run_in_executor(
                _get_playwright_executor(), _run_playwright_sync, url, timeout_seconds
            )
        final_url = rendered_url or final_url
        html = rendered_html or html
        extraction_html = _apply_content_selector(html, selector, url=final_url)
        rendered_extracted = _extract_with_trafilatura(extraction_html)
        rendered_quality = _evaluate_extraction_quality(
            rendered_extracted,
            source_html=extraction_html,
            min_meaningful_chars=min_meaningful_chars,
        )
        extracted = rendered_extracted
        quality = rendered_quality
        _log_stage_decision(
            stage="browser_trafilatura",
            url=final_url,
            fetch_mode=fetch_mode,
            extractor=extractor,
            quality=quality,
            decision="fallback_to_readability" if _should_try_readability(
                rendered_quality,
                min_meaningful_chars=min_meaningful_chars,
            ) else "accept",
        )

        should_use_readability = _should_try_readability(
            rendered_quality,
            min_meaningful_chars=min_meaningful_chars,
        )
        if should_use_readability:
            extractor = "playwright+readability"
            readability_extracted = _extract_with_readability(extraction_html)
            readability_quality = _evaluate_extraction_quality(
                readability_extracted,
                source_html=extraction_html,
                min_meaningful_chars=min_meaningful_chars,
            )
            if readability_quality.score >= rendered_quality.score:
                extracted = readability_extracted
                quality = readability_quality
                _log_stage_decision(
                    stage="readability",
                    url=final_url,
                    fetch_mode=fetch_mode,
                    extractor=extractor,
                    quality=quality,
                    decision="accept",
                )
            else:
                extractor = "playwright"
                _log_stage_decision(
                    stage="readability",
                    url=final_url,
                    fetch_mode=fetch_mode,
                    extractor=extractor,
                    quality=readability_quality,
                    decision="reject_keep_browser_result",
                )

    # 最终结果校验：
    # 如果用户显式指定了选择器，且抽取到了内容，则无论质量评分如何都视为成功。
    # 否则，必须满足最小质量要求。
    is_valid_extraction = bool(extracted) and (bool(selector) or quality.is_meaningful)

    if not is_valid_extraction:
        _log_stage_decision(
            stage="final",
            url=final_url,
            fetch_mode=fetch_mode,
            extractor=extractor,
            quality=quality,
            decision="raise_failure",
        )
        raise ValueError("网页正文抽取失败：未能在页面中找到有效正文或指定区域的内容过少。")

    structured_html = _apply_content_selector(html, selector, url=final_url)
    structured_sections, structured_markdown = _extract_structured_sections(structured_html)
    if structured_sections:
        for section in structured_sections:
            raw_blocks = section.get("blocks") if isinstance(section, dict) else []
            for block in raw_blocks if isinstance(raw_blocks, list) else []:
                if not isinstance(block, dict):
                    continue
                raw_refs = block.get("source_refs") or []
                refs = list(raw_refs) if isinstance(raw_refs, list) else []
                for ref in refs:
                    if not isinstance(ref, dict):
                        continue
                    if not ref.get("url"):
                        ref["url"] = final_url
                    if not ref.get("canonical_url"):
                        ref["canonical_url"] = final_url
    if structured_markdown:
        structured_quality = _evaluate_extraction_quality(
            structured_markdown,
            source_html=structured_html,
            min_meaningful_chars=min_meaningful_chars,
        )
        # 通用 DOM 分区结果在质量不差于正文抽取时优先采用，
        # 这样可以补上摘要区/侧栏信息，并在复杂表格处保留 HTML table。
        if structured_quality.score >= quality.score:
            extracted = structured_markdown
            quality = structured_quality

    _log_stage_decision(
        stage="final",
        url=final_url,
        fetch_mode=fetch_mode,
        extractor=extractor,
        quality=quality,
        decision="success",
    )

    return WebExtractResult(
        extracted_text=extracted,
        raw_html=html,
        extraction_html=structured_html if structured_html else html,
        final_url=final_url,
        http_status=http_status,
        etag=etag,
        last_modified=last_modified,
        extractor=extractor,
        quality_summary=quality.as_log_payload(),
        structured_sections=structured_sections,
    )


def _run_playwright_sync(url: str, timeout_seconds: int) -> tuple[str, str]:
    """
    在独立子进程中运行 Playwright，由 ProcessPoolExecutor 调度。

    返回 (rendered_html, final_url)，失败时直接抛出异常。

    跨平台兼容说明：
    - 此函数运行在独立子进程中，子进程在 Windows 上默认使用 ProactorEventLoop，
      支持 create_subprocess_exec，Playwright async API 可正常启动浏览器进程。
    - 父进程的 asyncio 事件循环类型不影响子进程，彻底隔离冲突。
    - Linux/macOS 子进程同样正常工作。
    """
    import asyncio
    import sys
    from pathlib import Path

    # spawn 模式下子进程是全新解释器，需要手动添加项目根目录到 Python 路径
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    async def _inner() -> tuple[str, str]:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
                # 先等待文档可操作，再尽量等待网络静默，兼顾 SPA 首屏渲染和整体超时控制。
                try:
                    await page.wait_for_load_state("networkidle", timeout=min(timeout_seconds * 1000, 5000))
                except Exception:
                    pass
                # 某些页面在 networkidle 前后仍会延迟挂载正文，补一个很短的稳定窗口。
                await page.wait_for_timeout(800)
                rendered_html = await page.content()
                final_url = page.url or url
                return rendered_html, final_url
            finally:
                await browser.close()

    # 子进程中直接用 asyncio.run()，它会创建新 loop（Windows 默认 ProactorEventLoop），
    # 支持子进程创建，与 Playwright 完全兼容。
    return asyncio.run(_inner())
