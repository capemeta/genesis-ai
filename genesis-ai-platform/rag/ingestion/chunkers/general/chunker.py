"""
通用分块器 (也称为智能文本分块器)

特点：
- 自动探测文档复杂度 (适用于 txt, log, json 等纯文本)
- 简单文档：使用 SentenceSplitter (递归分块)
- 复杂文档：使用 HierarchicalNodeParser (Parent-Child 结构)
- 针对中文优化了切分正则
- 保护 Markdown 图片语法不被分割

适用场景：
- 通用文本、txt等
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Pattern

from rag.ingestion.chunkers.base import BaseChunker
from .config import GeneralChunkerConfig
from .detector import ComplexityDetector
from .converter import NodeConverter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SplitRule:
    """自定义切分规则。"""

    pattern: str
    is_regex: bool
    compiled: Pattern[str]
    keep_with: str = "previous"

try:
    from llama_index.core.node_parser import SentenceSplitter, HierarchicalNodeParser
    from llama_index.core.schema import Document as LlamaDocument
    HAS_LLAMA_INDEX = True
except ImportError:
    HAS_LLAMA_INDEX = False
    logger.warning("[GeneralChunker] LlamaIndex 未安装，通用分块器将不可用")


class GeneralChunker(BaseChunker):
    """
    通用分块器
    
    特点：
    - 自动探测文档复杂度 (适用于 txt, log, json 等纯文本)
    - 简单文档：使用 SentenceSplitter (递归分块)
    - 复杂文档：使用 HierarchicalNodeParser (Parent-Child 结构)
    - 针对中文优化了切分正则
    
    适用场景：
    - 通用文本、txt等
    """
    
    def __init__(
        self, 
        chunk_size: int = GeneralChunkerConfig.DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = GeneralChunkerConfig.DEFAULT_CHUNK_OVERLAP,
        complexity_threshold: int = GeneralChunkerConfig.DEFAULT_COMPLEXITY_THRESHOLD,
        **kwargs
    ):
        super().__init__(chunk_size, chunk_overlap, **kwargs)
        self.complexity_threshold = complexity_threshold
        
        # 优化后的中文标点正则
        self.secondary_chunking_regex = kwargs.get(
            "secondary_chunking_regex", 
            GeneralChunkerConfig.DEFAULT_SECONDARY_CHUNKING_REGEX
        )
        
        self.chunking_mode = str(kwargs.get("chunking_mode") or "")
        self.separator = self._normalize_separator(str(kwargs.get("separator") or "\n\n"))
        self.separators = [
            self._normalize_separator(str(item))
            for item in (kwargs.get("separators") or [])
            if str(item)
        ]
        self.regex_separators = [
            str(item).strip()
            for item in (kwargs.get("regex_separators") or [])
            if str(item).strip()
        ]
        self.is_regex = bool(kwargs.get("is_regex", False))
        self.split_rules = self._build_split_rules(kwargs.get("split_rules") or [])
        self.use_custom_separator = self.chunking_mode == "custom" and (
            bool(self.split_rules)
            or
            self.is_regex
            or bool(self.separators)
            or bool(self.regex_separators)
            or "separator" in kwargs
        )

        # 初始化子模块
        self.detector = ComplexityDetector(complexity_threshold)
        self.converter = NodeConverter()
        
        if not HAS_LLAMA_INDEX:
            logger.error("[GeneralChunker] LlamaIndex 未安装，通用分块器无法使用")
        
        logger.info(
            f"[GeneralChunker] 初始化: chunk_size={chunk_size}, "
            f"overlap={chunk_overlap}, "
            f"complexity_threshold={complexity_threshold}"
        )

    def chunk(self, text: str, metadata: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """
        同步智能分块
        
        Args:
            text: 待分块的文本
            metadata: 元数据
            
        Returns:
            分块结果列表
        """
        if not HAS_LLAMA_INDEX:
            logger.error("[GeneralChunker] LlamaIndex 未安装，无法执行分块")
            return []

        normalized_metadata = metadata if isinstance(metadata, dict) else {}

        if self.use_custom_separator:
            return self._custom_separator_chunk(text, normalized_metadata)

        # 1. 结构探测
        is_complex = self.detector.is_complex(text)
        
        # 2. 选择并执行策略
        if is_complex:
            return self._hierarchical_chunk(text, normalized_metadata)
        else:
            return self._simple_chunk(text, normalized_metadata)

    def _build_split_rules(self, raw_rules: List[Dict[str, Any]]) -> List[SplitRule]:
        """优先使用新的有序规则列表，未配置时回退到旧字段组合。"""
        compiled_rules: List[SplitRule] = []

        for raw_rule in raw_rules[:12]:
            if not isinstance(raw_rule, dict):
                continue
            pattern = str(raw_rule.get("pattern") or "")
            if not pattern:
                continue
            normalized_pattern = pattern if bool(raw_rule.get("is_regex")) else self._normalize_separator(pattern)
            compiled_rules.append(self._compile_split_rule(normalized_pattern, bool(raw_rule.get("is_regex"))))

        if compiled_rules:
            return compiled_rules

        if self.is_regex and self.separator:
            compiled_rules.append(self._compile_split_rule(self.separator, True))
        else:
            literal_rules = self.separators or ([self.separator] if self.separator else [])
            for separator in literal_rules:
                if separator:
                    compiled_rules.append(self._compile_split_rule(separator, False))

        for separator in self.regex_separators:
            if separator:
                compiled_rules.append(self._compile_split_rule(separator, True))

        deduplicated: List[SplitRule] = []
        seen = set()
        for rule in compiled_rules:
            key = (rule.pattern, rule.is_regex)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(rule)
        return deduplicated

    @staticmethod
    def _compile_split_rule(pattern: str, is_regex: bool) -> SplitRule:
        """编译单条切分规则，并防御空匹配。

        说明：
        - 普通文本里的正则规则主要面向“按行识别边界”的使用方式
        - 因此这里默认开启 MULTILINE，让 ^ / $ 可以匹配每一行
        - 对于 ^ 开头的行级正则，通常语义是“从这行开始新的片段”
          因此命中的文本应保留在后一段，而不是前一段
        - 非正则规则仍然按字面量处理，不受该行为影响
        """
        compiled = re.compile(
            pattern if is_regex else re.escape(pattern),
            re.MULTILINE if is_regex else 0,
        )
        if compiled.search("") is not None:
            raise ValueError("自定义分隔符正则不能匹配空字符串")
        keep_with = "next" if is_regex and GeneralChunker._is_line_start_rule(pattern) else "previous"
        return SplitRule(pattern=pattern, is_regex=is_regex, compiled=compiled, keep_with=keep_with)

    @staticmethod
    def _is_line_start_rule(pattern: str) -> bool:
        """判断规则是否表达“从命中行开始新的片段”。

        这里不尝试完整解析正则语法，只覆盖当前产品里最常见的写法：
        - ^### 标题
        - (?m)^1\\.1 标题
        - (?im)^Q:
        """
        normalized = pattern.lstrip()
        if normalized.startswith("^"):
            return True
        return normalized.startswith("(?m)^") or normalized.startswith("(?im)^") or normalized.startswith("(?mi)^")

    @staticmethod
    def _normalize_separator(separator: str) -> str:
        """只转换常见转义字符，避免 unicode_escape 误伤用户正则。"""
        return (
            separator
            .replace("\\r", "\r")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
        )

    def _custom_separator_chunk(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """按用户自定义规则递归切分，仅在 custom 模式下启用。"""
        if not text:
            return []

        split_rules = self.split_rules or self._build_split_rules([])
        chunks = self._split_text_recursively(text, split_rules)
        return [
            self._build_custom_chunk(chunk_text, metadata, index)
            for index, chunk_text in enumerate(chunks)
            if chunk_text.strip()
        ]

    def _split_text_recursively(self, text: str, rules: List[SplitRule]) -> List[str]:
        """只有文本超长时才继续按后续规则递归切分。

        注意：
        - 这里只判断“是否为空”时使用 strip
        - 真正参与递归和合并的文本要保留原始前后换行
        - 否则像“标题行 + 空行 + 正文”这类结构会在后续合并时被错误粘连
        """
        if not text or not text.strip():
            return []

        if len(text.strip()) <= self.chunk_size:
            return [text]

        if not rules:
            return self._slice_text_with_overlap(text)

        first_rule, remaining_rules = rules[0], rules[1:]
        segments = self._split_with_rule_preserving_match(text, first_rule)
        if len(segments) <= 1:
            return self._split_text_recursively(text, remaining_rules)

        resolved_segments: List[str] = []
        for segment in segments:
            if not segment or not segment.strip():
                continue
            if len(segment.strip()) <= self.chunk_size:
                resolved_segments.append(segment)
                continue
            resolved_segments.extend(self._split_text_recursively(segment, remaining_rules))

        return self._merge_segments_with_overlap(resolved_segments)

    def _split_with_rule_preserving_match(self, text: str, rule: SplitRule) -> List[str]:
        """按单条规则切分，并保留命中的分隔文本，避免内容丢失。"""
        matches = list(rule.compiled.finditer(text))
        if not matches:
            return [text]

        units: List[str] = []
        start = 0
        for match in matches:
            boundary = match.start() if rule.keep_with == "next" else match.end()
            if rule.keep_with == "next":
                # 对“从本行开始新片段”的规则，把命中行前连续的换行也一起带到后一段。
                # 这样在后续 overlap 回拼时，标题前的空行不会丢失，避免出现
                # “正文尾巴### 标题” 被粘成一行而破坏标题语义。
                while boundary > start and text[boundary - 1] in ("\n", "\r"):
                    boundary -= 1
            if boundary > start:
                units.append(text[start:boundary])
            start = boundary
        if start < len(text):
            units.append(text[start:])
        return units or [text]

    def _merge_segments_with_overlap(self, segments: List[str]) -> List[str]:
        """把递归拆出的片段重新合并成接近 chunk_size 的块。"""
        if not segments:
            return []

        limit = max(1, int(self.chunk_size or GeneralChunkerConfig.DEFAULT_CHUNK_SIZE))
        overlap = max(0, min(int(self.chunk_overlap or 0), max(limit - 1, 0)))
        chunks: List[str] = []
        current = ""

        def append_chunk(value: str) -> None:
            stripped_value = value.strip()
            if stripped_value:
                chunks.append(stripped_value)

        def overlap_tail(value: str) -> str:
            return value[-overlap:] if overlap > 0 and len(value) > overlap else ""

        for segment in segments:
            if not segment:
                continue
            if len(segment) > limit:
                if current:
                    append_chunk(current)
                    current = ""
                chunks.extend(self._slice_text_with_overlap(segment))
                continue

            candidate = f"{current}{segment}"
            if len(candidate) <= limit:
                current = candidate
                continue

            if current:
                append_chunk(current)
                current = overlap_tail(current)
                candidate = f"{current}{segment}"
                if len(candidate) <= limit:
                    current = candidate
                    continue

            chunks.extend(self._slice_text_with_overlap(segment))
            current = ""

        if current:
            append_chunk(current)

        return chunks

    def _slice_text_with_overlap(self, text: str) -> List[str]:
        """所有规则都无法继续拆分时，按字符窗口兜底，确保不超限。"""
        limit = max(1, int(self.chunk_size or GeneralChunkerConfig.DEFAULT_CHUNK_SIZE))
        overlap = max(0, min(int(self.chunk_overlap or 0), max(limit - 1, 0)))
        step = max(1, limit - overlap)
        chunks: List[str] = []
        position = 0
        while position < len(text):
            piece = text[position:position + limit].strip()
            if piece:
                chunks.append(piece)
            if position + limit >= len(text):
                break
            position += step
        return chunks

    @staticmethod
    def _build_custom_chunk(
        chunk_text: str,
        metadata: Dict[str, Any],
        index: int,
    ) -> Dict[str, Any]:
        """构造统一 chunk 协议字段，避免自定义分隔符输出和智能分块协议分裂。"""
        chunk_metadata = {
            **metadata,
            "chunk_index": index,
            "chunk_strategy": "general",
            "is_smart": False,
            "is_hierarchical": False,
            "source_anchors": [],
            "source_element_indices": [],
            "page_numbers": [],
        }
        return {
            "text": chunk_text,
            "metadata": chunk_metadata,
            "type": "text",
            "content_blocks": [
                {
                    "block_id": "b1",
                    "type": "text",
                    "text": chunk_text,
                    "source_refs": [],
                }
            ],
        }

    def _shrink_metadata(self, metadata: Dict[str, Any] | None) -> Dict[str, Any]:
        if not isinstance(metadata, dict):
            return {}

        # LlamaIndex 会将 metadata 也计入 chunk_size；这里必须做瘦身，避免 elements 等大字段导致直接报错。
        heavy_keys = {
            "elements",
            "pdf_embedded_images",
            "image_assets",
            "image_document_ids",
            "docx_embedded_images",
            "docx_image_placeholders",
        }

        slim: Dict[str, Any] = {}
        for k, v in metadata.items():
            if k in heavy_keys:
                continue

            if v is None:
                continue

            # 只保留小体积标量；复杂结构不传给 LlamaIndex
            if isinstance(v, (int, float, bool)):
                slim[k] = v
                continue

            if isinstance(v, str):
                slim[k] = v if len(v) <= 512 else v[:512]
                continue

            if isinstance(v, (list, tuple)):
                # 允许保留小列表（例如 document_ids），但截断长度
                if len(v) <= 20 and all(isinstance(x, (str, int, float, bool)) for x in v):
                    slim[k] = list(v)
                continue

            # dict / bytes / 其他对象全部跳过
            continue

        return slim

    def _simple_chunk(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        简单递归分块 (SentenceSplitter)
        
        Args:
            text: 待分块的文本
            metadata: 元数据
            
        Returns:
            分块结果列表
        """
        logger.info(f"[GeneralChunker] 采用简单模式 (SentenceSplitter), 长度: {len(text)}")
        
        splitter = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            paragraph_separator="\n\n",
            secondary_chunking_regex=self.secondary_chunking_regex
        )

        safe_metadata = self._shrink_metadata(metadata)
        doc = LlamaDocument(text=text, metadata=safe_metadata)
        nodes = splitter.get_nodes_from_documents([doc])
        
        return self.converter.convert_nodes_to_chunks(nodes, is_hierarchical=False)

    def _hierarchical_chunk(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        层级分块 (Parent-Child)
        
        Args:
            text: 待分块的文本
            metadata: 元数据
            
        Returns:
            分块结果列表
        """
        logger.info(f"[GeneralChunker] 采用复杂模式 (Hierarchical), 长度: {len(text)}")
        
        # 定义层级：通常是 [父块, 中间块, 子块]
        # 这里动态根据 self.chunk_size 设置
        chunk_sizes = [self.chunk_size * 4, self.chunk_size * 2, self.chunk_size]
        
        parser = HierarchicalNodeParser.from_defaults(
            chunk_sizes=chunk_sizes,
            chunk_overlap=self.chunk_overlap
        )

        safe_metadata = self._shrink_metadata(metadata)
        doc = LlamaDocument(text=text, metadata=safe_metadata)
        nodes = parser.get_nodes_from_documents([doc])
        
        return self.converter.convert_nodes_to_chunks(nodes, is_hierarchical=True)
