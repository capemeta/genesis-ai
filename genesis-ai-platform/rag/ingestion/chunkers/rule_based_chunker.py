"""
用户规则分块器。

该分块器只负责把前端配置的标题规则识别成结构化 section，
真正的章节拆分、父子块构建与独立元素保护继续复用 MarkdownChunker。
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Pattern

from .base import BaseChunker
from .markdown import MarkdownChunker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompiledHeadingRule:
    """已编译的标题规则。"""

    name: str
    level: int
    pattern: str
    regex: Pattern[str]
    keep_heading: bool = True


class RuleBasedChunker(BaseChunker):
    """
    用户规则分块器。

    设计原则：
    - 后端不内置法律、制度等业务规则，完全按前端传入的 heading_rules 执行。
    - 默认推荐使用 1-3 级标题，但能力上支持到 6 级，兼顾 Markdown 与技术规范文档。
    - 标题结构识别后复用 MarkdownChunker，避免重复实现复杂层级分块逻辑。
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 0,
        heading_rules: Optional[List[Dict[str, Any]]] = None,
        fallback_separators: Optional[List[str]] = None,
        preserve_headings: bool = True,
        max_heading_level: int = 3,
        heading_max_chars: int = 200,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunk_size, chunk_overlap, **kwargs)
        # 前端默认展示 3 级，这里保留到 6 级能力，便于更深层级文档按需扩展。
        self.max_heading_level = max(1, min(int(max_heading_level or 3), 6))
        self.preserve_headings = bool(preserve_headings)
        self.heading_max_chars = max(20, min(int(heading_max_chars or 200), 500))
        self.fallback_separators = [
            str(item) for item in (fallback_separators or []) if str(item)
        ] or ["\n\n", "\n", "。", "；", " "]
        self.heading_rules = self._compile_heading_rules(heading_rules or [])
        self.markdown_chunker = MarkdownChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            **kwargs,
        )

        logger.info(
            "[RuleBasedChunker] 初始化: chunk_size=%s, overlap=%s, rules=%s, max_heading_level=%s",
            chunk_size,
            chunk_overlap,
            len(self.heading_rules),
            self.max_heading_level,
        )

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行规则分块。"""
        normalized_metadata = dict(metadata or {})
        if not text or not text.strip():
            return []

        if not self.heading_rules:
            logger.warning("[RuleBasedChunker] 未配置 heading_rules，降级为 MarkdownChunker")
            return self._mark_rule_based_chunks(
                self.markdown_chunker.chunk(text, normalized_metadata),
                matched_heading_count=0,
                fallback_reason="empty_heading_rules",
            )

        sections, matched_heading_count = self._split_sections_by_heading_rules(text)
        if matched_heading_count <= 0:
            logger.warning("[RuleBasedChunker] 标题规则未命中，降级为 MarkdownChunker")
            return self._mark_rule_based_chunks(
                self.markdown_chunker.chunk(text, normalized_metadata),
                matched_heading_count=0,
                fallback_reason="no_heading_matched",
            )

        # 复用 MarkdownParser 的层级合并能力，避免父级标题被切成孤立 stub。
        sections = self.markdown_chunker.parser._merge_adjacent_sections(
            sections,
            self.markdown_chunker._count_tokens_cached,
            self.markdown_chunker.embedding_model_limit,
        )

        all_chunks: List[Dict[str, Any]] = []
        for section in sections:
            section_metadata = {
                **normalized_metadata,
                "heading_rule_name": section.get("heading_rule_name"),
                "heading_rule_level": section.get("heading_rule_level"),
            }
            section_chunks, parent_chunks, child_chunks = self.markdown_chunker._process_section(
                section,
                section_metadata,
            )
            all_chunks.extend(section_chunks)
            all_chunks.extend(parent_chunks)
            all_chunks.extend(child_chunks)

        self.markdown_chunker._finalize_topology_flags(all_chunks)
        normalized_chunks = self.markdown_chunker._normalize_chunk_protocol(all_chunks)
        return self._mark_rule_based_chunks(
            normalized_chunks,
            matched_heading_count=matched_heading_count,
            fallback_reason=None,
        )

    def _compile_heading_rules(self, raw_rules: List[Dict[str, Any]]) -> List[CompiledHeadingRule]:
        """编译前端传入的标题规则，并做任务侧防御性校验。"""
        compiled_rules: List[CompiledHeadingRule] = []
        for index, raw_rule in enumerate(raw_rules[:10], start=1):
            if not isinstance(raw_rule, dict):
                continue

            pattern = str(raw_rule.get("pattern") or "").strip()
            if not pattern or len(pattern) > 512:
                continue

            level = int(raw_rule.get("level") or 1)
            if level < 1 or level > self.max_heading_level:
                continue

            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"标题规则正则无效: {pattern}, error={exc}") from exc

            if compiled.search("") is not None:
                raise ValueError(f"标题规则不能匹配空字符串: {pattern}")

            compiled_rules.append(
                CompiledHeadingRule(
                    name=str(raw_rule.get("name") or f"level_{level}_{index}").strip()[:64],
                    level=level,
                    pattern=pattern,
                    regex=compiled,
                    keep_heading=bool(raw_rule.get("keep_heading", self.preserve_headings)),
                )
            )

        return compiled_rules

    def _match_heading_rule(self, line: str) -> Optional[CompiledHeadingRule]:
        """按配置顺序匹配标题规则，命中第一条即返回。"""
        stripped_line = line.strip()
        if not stripped_line or len(stripped_line) > self.heading_max_chars:
            return None

        for rule in self.heading_rules:
            if rule.regex.match(stripped_line):
                return rule
        return None

    def _split_sections_by_heading_rules(self, text: str) -> tuple[List[Dict[str, Any]], int]:
        """按前端配置的标题规则切分为 MarkdownChunker 可消费的 section。"""
        sections: List[Dict[str, Any]] = []
        heading_stack: Dict[int, str] = {}
        current_lines: List[str] = []
        current_heading = ""
        current_header_path = ""
        current_level = 0
        current_rule_name: Optional[str] = None
        matched_heading_count = 0

        def flush_current_section() -> None:
            nonlocal current_lines, current_heading, current_header_path, current_level, current_rule_name
            section_text = "\n".join(current_lines).strip()
            if not section_text and current_heading:
                section_text = current_heading
            if section_text:
                sections.append(
                    {
                        "text": section_text,
                        "heading": current_heading,
                        "level": current_level,
                        "header_path": current_header_path,
                        "budget_header_text": current_header_path or current_heading,
                        "token_count": self.markdown_chunker._count_tokens_cached(section_text),
                        "prompt_header_paths": [current_header_path] if current_header_path else [],
                        "prompt_header_text": current_header_path or current_heading,
                        "heading_rule_name": current_rule_name,
                        "heading_rule_level": current_level,
                    }
                )
            current_lines = []

        for line in text.splitlines():
            matched_rule = self._match_heading_rule(line)
            if matched_rule is None:
                current_lines.append(line)
                continue

            flush_current_section()
            matched_heading_count += 1
            heading = line.strip()
            level = matched_rule.level
            heading_stack = {
                existing_level: existing_heading
                for existing_level, existing_heading in heading_stack.items()
                if existing_level < level
            }
            heading_stack[level] = heading
            header_path = "/".join(
                heading_stack[existing_level]
                for existing_level in sorted(heading_stack.keys())
                if existing_level <= level
            )

            current_heading = heading
            current_header_path = header_path
            current_level = level
            current_rule_name = matched_rule.name
            current_lines = [line] if matched_rule.keep_heading else []

        flush_current_section()

        return sections, matched_heading_count

    @staticmethod
    def _mark_rule_based_chunks(
        chunks: List[Dict[str, Any]],
        matched_heading_count: int,
        fallback_reason: Optional[str],
    ) -> List[Dict[str, Any]]:
        """把复用 MarkdownChunker 的输出标记为 rule_based 策略。"""
        for chunk in chunks:
            metadata = chunk.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                chunk["metadata"] = metadata
            metadata.setdefault("source_chunk_strategy", metadata.get("chunk_strategy") or "markdown")
            metadata["chunk_strategy"] = "rule_based"
            metadata["rule_based_heading_match_count"] = matched_heading_count
            if fallback_reason:
                metadata["rule_based_fallback_reason"] = fallback_reason
        return chunks
