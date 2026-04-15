"""
Markdown 智能分块器（方案 C：按需边界保护）

核心策略：
1. 按标题预分块
2. 按段落边界累积分块（目标 chunk_size）
3. 检查分块边界是否截断独立元素
4. 只在截断时才特殊处理（回退 + 独立处理）
5. 可选：合并子块成父块（双层结构）

Chunk Overlap 规则：
- 如果启用分层（enable_hierarchy=True）：chunk_overlap 自动设为 0
- 如果不启用分层（enable_hierarchy=False）：使用传入的 chunk_overlap 参数

特点：
- 保持原始文本流，最小化干预
- 只在必要时才处理独立元素
- 元素完整性 100%（拆分时保留表头/上下文）
- 支持双层结构（子块 + 父块）
- 灵活的 overlap 策略
"""

import logging
import time
from typing import List, Dict, Any, Tuple, Optional
from uuid import uuid4

from rag.ingestion.chunkers.base import BaseChunker
from rag.utils.token_utils import count_tokens
from .config import MarkdownChunkerConfig
from .syntax_parser import MarkdownParser
from .detector import MarkdownElementDetector
from .splitter import MarkdownElementSplitter

logger = logging.getLogger(__name__)


class MarkdownChunker(BaseChunker):
    """
    Markdown 智能分块器（方案 C）
    
    核心思想：
    - 先按段落边界分块（自然流）
    - 只在边界截断独立元素时才特殊处理（按需处理）
    - 可选双层结构（子块 + 父块）
    - 灵活的 overlap 策略（分层时无 overlap，单层时可配置）
    """
    
    def __init__(
        self,
        chunk_size: int = MarkdownChunkerConfig.DEFAULT_CHUNK_SIZE,
        chunk_overlap: Optional[int] = None,
        embedding_model_limit: int = 512,
        enable_hierarchy: bool = True,
        parent_chunk_size: Optional[int] = None,
        min_chunk_size: int = 100,
        **kwargs
    ):
        """
        Args:
            chunk_size: 子块目标大小（tokens）
            chunk_overlap: 重叠大小（如果启用分层，自动设为 0；否则使用传入值或默认 15%）
            embedding_model_limit: 嵌入模型上下文限制（硬性要求）
            enable_hierarchy: 是否启用双层结构（子块 + 父块）
            parent_chunk_size: 父块目标大小（默认 chunk_size * 4）
            min_chunk_size: 最小块大小，小于此值会尝试合并
            **kwargs: 其他参数（兼容性）
        """
        # 如果启用分层，chunk_overlap 设为 0；否则使用传入值或默认 15%
        if enable_hierarchy:
            actual_overlap = 0
        else:
            actual_overlap = chunk_overlap if chunk_overlap is not None else int(chunk_size * MarkdownChunkerConfig.DEFAULT_OVERLAP_RATIO)
        
        super().__init__(chunk_size, actual_overlap, **kwargs)
        self.chunk_size = chunk_size
        self.chunk_overlap = actual_overlap
        self.embedding_model_limit = embedding_model_limit
        self.enable_hierarchy = enable_hierarchy
        self.parent_chunk_size = parent_chunk_size or (chunk_size * 4)
        self.min_chunk_size = min_chunk_size
        
        # Token 计算缓存
        self._token_cache: Dict[int, int] = {}
        
        # 检查依赖
        
        # 初始化子模块
        self.parser = MarkdownParser()
        self.detector = MarkdownElementDetector()
        self.splitter = MarkdownElementSplitter(
            chunk_size,
            embedding_model_limit,
            self._count_tokens_cached
        )
        self._md_parser = self._build_markdown_it_parser()
        
        logger.info(
            f"[MarkdownChunker] 初始化: chunk_size={chunk_size}, "
            f"overlap={actual_overlap} ({'分层模式，无overlap' if enable_hierarchy else '单层模式'}), "
            f"embedding_limit={embedding_model_limit}, "
            f"parent_chunk_size={self.parent_chunk_size}, "
            f"min_chunk_size={min_chunk_size}, "
            f"hierarchy={enable_hierarchy}, "
        )
    
    
    def chunk(self, text: str, metadata: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """
        分块主函数（三层结构：章节块 → 父块 → 子块）
        
        流程：
        1. 按标题预分块（MarkdownNodeParser）
        2. 对每个章节：
           - 小章节：只保留章节块，不拆分
           - 中等章节：章节块 + 子块
           - 大章节：章节块 + 父块 + 子块
        3. 返回所有块（章节块 + 父块 + 子块）
        
        向量化策略：
        - 章节块（L0）：不向量化，用于直接返回
        - 父块（L1）：不向量化，用于提供中等粒度上下文
        - 子块（L2）：向量化，用于检索
        """
        start_time = time.time()
        
        metadata = metadata or {}
        logger.info(f"[MarkdownChunker] 开始分块，文本长度: {len(text)}")
        
        try:
            # 步骤 1：按标题预分块
            sections = self.parser.parse_by_heading(
                text,
                metadata,
                self._count_tokens_cached,
                max_section_total_tokens=self.embedding_model_limit
            )
            
            if not sections:
                logger.warning("[MarkdownChunker] 标题解析失败，使用回退方案")
                return self._normalize_chunk_protocol(self._fallback_chunk(text, metadata))
            
            logger.info(f"[MarkdownChunker] 按标题分块完成，章节数: {len(sections)}")
            
            # 步骤 2：处理每个章节，生成三层结构
            all_section_chunks = []
            all_parent_chunks = []
            all_child_chunks = []
            
            for section in sections:
                section_chunks, parent_chunks, child_chunks = self._process_section(section, metadata)
                all_section_chunks.extend(section_chunks)
                all_parent_chunks.extend(parent_chunks)
                all_child_chunks.extend(child_chunks)
            
            logger.info(
                f"[MarkdownChunker] 分块完成: "
                f"章节块={len(all_section_chunks)}, "
                f"父块={len(all_parent_chunks)}, "
                f"子块={len(all_child_chunks)}"
            )
            
            # 步骤 3：返回所有块
            if self.enable_hierarchy:
                # 返回三层结构：章节块 + 父块 + 子块
                all_chunks = all_section_chunks + all_parent_chunks + all_child_chunks
            else:
                # 只返回章节块 + 子块（不生成父块）
                all_chunks = all_section_chunks + all_child_chunks

            # 步骤 4：全局终态修正（最终阶段确保 is_leaf / should_vectorize 准确）
            # 以实际 child_ids 是否为空为唯一判据，修正所有中间阶段可能遗留的错误值
            self._finalize_topology_flags(all_chunks)

            elapsed = time.time() - start_time
            logger.info(
                f"[MarkdownChunker] 分块完成，总块数: {len(all_chunks)}, "
                f"耗时: {elapsed:.2f}s"
            )
            return self._normalize_chunk_protocol(all_chunks)
            
        except Exception as e:
            logger.error(f"[MarkdownChunker] 分块失败: {e}", exc_info=True)
            return self._normalize_chunk_protocol(self._fallback_chunk(text, metadata))
    
    def _process_section(
        self,
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        处理单个章节，生成三层结构
        
        返回：(章节块列表, 父块列表, 子块列表)
        
        策略：
        1. 小章节（< chunk_size * 1.5）：只保留章节块，不拆分
        2. 中等章节（< chunk_size * 6）：章节块 + 子块
        3. 大章节（>= chunk_size * 6）：章节块 + 父块 + 子块
        """
        text = section["text"]
        heading = section.get("heading", "")
        header_path = section.get("header_path", "")
        section_tokens = section["token_count"]
        
        logger.debug(
            f"[MarkdownChunker] 处理章节 '{heading}' ({section_tokens} tokens)"
        )
        
        # 统一预算标题（用于 token 预算）
        budget_header_text = self._get_budget_header_text(section)
        budget_header_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
        
        # 可用空间 = embedding_model_limit - header_path - 安全余量
        available_tokens = self.embedding_model_limit - budget_header_tokens - 10
        
        if available_tokens <= 0:
            logger.error(
                f"[MarkdownChunker] 完整标题路径本身就超过嵌入模型限制！"
                f"header_tokens={budget_header_tokens}, "
                f"embedding_model_limit={self.embedding_model_limit}"
            )
            # 即使标题路径超限，也要尝试保存内容
            available_tokens = self.embedding_model_limit - 50

        section_total_tokens = section_tokens + budget_header_tokens

        # 策略 1：小章节且不超嵌入限制 - 只保留章节块，不拆分
        # 关键：只要内容+完整标题超限，就必须进入后续拆分流程
        if (
            section_tokens < self.chunk_size * 1.5
            and section_total_tokens <= self.embedding_model_limit
        ):
            logger.debug(
                f"[MarkdownChunker] 小章节且不超限，不拆分: {heading}, "
                f"section_total_tokens={section_total_tokens}"
            )
            section_chunk = self._create_section_chunk(section, metadata)
            return [section_chunk], [], []
        
        # 策略 2 & 3：需要拆分的章节
        # 阶段 1：拆成原子块并重组成子块
        atomic_blocks = self._build_atomic_blocks(text)
        child_chunks = self._reassemble_stage1_chunks(
            atomic_blocks,
            section,
            metadata,
            available_tokens
        )

        # 阶段 1.5：合并小块
        child_chunks = self._merge_small_chunks(child_chunks, section)
        child_chunks = self._handle_last_chunk(child_chunks)

        # 阶段 2：判断是否需要生成父块（按阶段1重组结果判断）
        parent_chunks: List[Dict[str, Any]] = []
        stage1_total_tokens = sum(
            c["metadata"].get("total_tokens", self._count_tokens_cached(c["text"]) + budget_header_tokens)
            for c in child_chunks
        )
        if self.enable_hierarchy and stage1_total_tokens >= self.chunk_size * 6:
            logger.debug(f"[MarkdownChunker] 大章节，生成父块: {heading}")
            parent_chunks = self._create_parent_chunks_with_target(
                child_chunks,
                metadata,
                self.chunk_size * 4
            )

        # 阶段 3：处理超限独立块
        child_chunks = self._split_oversized_independent_chunks(
            child_chunks,
            parent_chunks,
            section,
            metadata,
            available_tokens
        )
        if parent_chunks:
            self._refresh_parent_chunks(parent_chunks, child_chunks)

        # 如果最终没有真正拆开，就不要额外再生成一个重复的章节根块。
        if (
            not parent_chunks
            and len(child_chunks) == 1
            and str(child_chunks[0].get("text") or "").strip() == str(text).strip()
        ):
            logger.debug("[MarkdownChunker] 章节未实际拆分，折叠为单个根叶一体块")
            section_chunk = self._create_section_chunk(section, metadata)
            section_meta = section_chunk["metadata"]
            section_meta["child_ids"] = []
            section_meta["is_root"] = True
            section_meta["is_leaf"] = True
            section_meta["depth"] = 0
            section_meta["should_vectorize"] = True
            return [section_chunk], [], []

        # 创建章节块
        section_chunk = self._create_section_chunk(section, metadata)
        
        # 建立三层父子关系
        if parent_chunks:
            # 大章节：章节块 → 父块 → 子块
            self._establish_three_level_hierarchy(section_chunk, parent_chunks, child_chunks)
        else:
            # 中等章节：章节块 → 子块
            self._establish_two_level_hierarchy(section_chunk, child_chunks)

        return [section_chunk], parent_chunks, child_chunks

    def _build_markdown_it_parser(self):
        """构建 markdown-it 解析器（失败时返回 None）。"""
        try:
            from markdown_it import MarkdownIt
            return MarkdownIt("gfm-like", {"html": True})
        except Exception as e:
            logger.warning(f"[MarkdownChunker] markdown-it 初始化失败，回退段落模式: {e}")
            return None

    def _build_atomic_blocks(self, text: str) -> List[Dict[str, Any]]:
        """
        将章节拆成原子块：protected + plain，二者覆盖全文且无重叠。
        """
        if not text.strip():
            return []

        if self._md_parser is None:
            return self._build_atomic_blocks_fallback(text)

        try:
            lines = text.split("\n")
            tokens = self._md_parser.parse(text)
            intervals: List[Tuple[int, int]] = []

            for token in tokens:
                line_map = getattr(token, "map", None)
                if not line_map or len(line_map) != 2:
                    continue

                token_type = token.type
                if token_type in {
                    "fence", "code_block", "table_open", "table_close",
                    "bullet_list_open", "bullet_list_close",
                    "ordered_list_open", "ordered_list_close",
                    "blockquote_open", "blockquote_close",
                    "html_block", "hr", "front_matter"
                } or token_type.startswith("math_block"):
                    start, end = line_map[0], line_map[1]
                    if start < end:
                        intervals.append((max(0, start), min(len(lines), end)))

            if not intervals:
                content_tokens = self._count_tokens_cached(text)
                return [{
                    "type": "plain",
                    "content": text,
                    "token_count": content_tokens,
                }]

            intervals.sort(key=lambda x: (x[0], -x[1]))
            merged: List[Tuple[int, int]] = []
            for start, end in intervals:
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))

            blocks: List[Dict[str, Any]] = []
            cursor = 0
            for start, end in merged:
                if cursor < start:
                    plain_content = "\n".join(lines[cursor:start])
                    if plain_content.strip():
                        blocks.append({
                            "type": "plain",
                            "content": plain_content,
                            "token_count": self._count_tokens_cached(plain_content),
                        })
                protected_content = "\n".join(lines[start:end])
                if protected_content.strip():
                    blocks.append({
                        "type": "protected",
                        "content": protected_content,
                        "token_count": self._count_tokens_cached(protected_content),
                        "element_type": self.detector.detect_element_type(protected_content),
                    })
                cursor = end

            if cursor < len(lines):
                tail_content = "\n".join(lines[cursor:])
                if tail_content.strip():
                    blocks.append({
                        "type": "plain",
                        "content": tail_content,
                        "token_count": self._count_tokens_cached(tail_content),
                    })

            return blocks
        except Exception as e:
            logger.warning(f"[MarkdownChunker] 原子块构建失败，回退段落模式: {e}")
            return self._build_atomic_blocks_fallback(text)

    def _build_atomic_blocks_fallback(self, text: str) -> List[Dict[str, Any]]:
        """markdown-it 不可用时的保底方案。"""
        blocks: List[Dict[str, Any]] = []
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            elem_type = self.detector.detect_element_type(para)
            block_type = "protected" if elem_type != "paragraph" else "plain"
            block = {
                "type": block_type,
                "content": para,
                "token_count": self._count_tokens_cached(para),
            }
            if block_type == "protected":
                block["element_type"] = elem_type
            blocks.append(block)
        return blocks

    def _reassemble_stage1_chunks(
        self,
        atomic_blocks: List[Dict[str, Any]],
        section: Dict[str, Any],
        metadata: Dict[str, Any],
        available_tokens: int
    ) -> List[Dict[str, Any]]:
        """
        阶段1重组：
        - plain 块按 chunk_size/available_tokens 组装
        - protected 块先独立成块（即使超限也先不拆，延后到阶段3）
        - 所有超限判断统一按 total_tokens(内容+完整标题)
        """
        chunks: List[Dict[str, Any]] = []
        budget_header_text = self._get_budget_header_text(section)
        # available_tokens 已经在 _process_section 中扣除了标题预算，这里只需要再尊重 chunk_size。
        content_limit = max(1, min(int(self.chunk_size), int(available_tokens)))
        budget_header_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
        staged_segments: List[Dict[str, Any]] = []

        # 先把 plain/protected 都归一成可重组 segment
        for block in atomic_blocks:
            block_type = block.get("type", "plain")
            block_content = block.get("content", "")
            block_tokens = block.get("token_count", self._count_tokens_cached(block_content))
            element_type = block.get("element_type", "paragraph")

            if block_type == "protected":
                total_tokens = block_tokens + budget_header_tokens
                staged_segments.append({
                    "text": block_content,
                    "token_count": block_tokens,
                    "is_independent_element": True,
                    "element_type": element_type,
                    "pending_split": (total_tokens > self.embedding_model_limit),
                    "split_required": (total_tokens > self.chunk_size),
                    "force_independent": True,
                })
                continue

            # plain 块：超限则进一步细分，保证阶段1普通文本可参与重组
            plain_segments = self._split_plain_block_to_segments(block_content, content_limit)
            for seg in plain_segments:
                staged_segments.append({
                    "text": seg["text"],
                    "token_count": seg["token_count"],
                    "is_independent_element": False,
                    "element_type": "paragraph",
                    "pending_split": False,
                    "split_required": False,
                    "force_independent": False,
                })

        # 在 segment 边界上贪心重组。超限独立块强制单独成块，延后到阶段3拆分。
        current_segments: List[Dict[str, Any]] = []
        current_tokens = 0

        def flush_current():
            nonlocal current_segments, current_tokens
            if not current_segments:
                return
            if len(current_segments) == 1 and current_segments[0].get("is_independent_element", False):
                seg = current_segments[0]
                chunks.append(
                    self._create_stage1_independent_chunk(
                        seg["text"],
                        seg.get("element_type", "paragraph"),
                        section,
                        metadata
                    )
                )
            else:
                merged_text = "\n\n".join(seg["text"] for seg in current_segments if seg["text"].strip()).strip()
                if merged_text:
                    chunks.append(self._create_chunk_dict(merged_text, section, metadata))
            current_segments = []
            current_tokens = 0

        for seg in staged_segments:
            seg_tokens = seg["token_count"]
            if seg.get("force_independent", False):
                flush_current()
                independent_chunk = self._create_stage1_independent_chunk(
                    seg["text"],
                    seg.get("element_type", "paragraph"),
                    section,
                    metadata
                )
                independent_chunk["metadata"]["pending_split"] = seg.get("pending_split", False)
                independent_chunk["metadata"]["split_required"] = seg.get("split_required", False)
                chunks.append(independent_chunk)
                continue

            if seg.get("pending_split", False):
                flush_current()
                chunks.append(
                    self._create_stage1_independent_chunk(
                        seg["text"],
                        seg.get("element_type", "paragraph"),
                        section,
                        metadata
                    )
                )
                continue

            if current_tokens + seg_tokens <= content_limit:
                current_segments.append(seg)
                current_tokens += seg_tokens
            else:
                flush_current()
                current_segments = [seg]
                current_tokens = seg_tokens

        flush_current()
        return chunks

    def _split_plain_block_to_segments(self, text: str, content_limit: int) -> List[Dict[str, Any]]:
        """
        将普通文本块拆成 <= content_limit 的 segment 列表（内容 token）。
        """
        if not text.strip():
            return []

        segments: List[Dict[str, Any]] = []
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            token_count = self._count_tokens_cached(text)
            return [{"text": text, "token_count": token_count}]

        for para in paragraphs:
            para_tokens = self._count_tokens_cached(para)
            if para_tokens <= content_limit:
                segments.append({"text": para, "token_count": para_tokens})
                continue

            # 超限段落再按行拆，保证输出 segment 不超 content_limit
            line_buffer: List[str] = []
            line_tokens = 0
            for line in para.split("\n"):
                lt = self._count_tokens_cached(line)
                if lt > content_limit:
                    if line_buffer:
                        chunk_text = "\n".join(line_buffer).strip()
                        if chunk_text:
                            segments.append({
                                "text": chunk_text,
                                "token_count": self._count_tokens_cached(chunk_text)
                            })
                        line_buffer = []
                        line_tokens = 0

                    # 单行超限：按 token 上限截断成多个片段
                    remaining = line
                    while remaining.strip():
                        truncated = self._truncate_text_to_tokens(remaining, content_limit)
                        if not truncated:
                            break
                        segments.append({
                            "text": truncated,
                            "token_count": self._count_tokens_cached(truncated)
                        })
                        remaining = remaining[len(truncated):].lstrip()
                    continue

                if line_tokens + lt <= content_limit:
                    line_buffer.append(line)
                    line_tokens += lt
                else:
                    chunk_text = "\n".join(line_buffer).strip()
                    if chunk_text:
                        segments.append({
                            "text": chunk_text,
                            "token_count": self._count_tokens_cached(chunk_text)
                        })
                    line_buffer = [line]
                    line_tokens = lt

            if line_buffer:
                chunk_text = "\n".join(line_buffer).strip()
                if chunk_text:
                    segments.append({
                        "text": chunk_text,
                        "token_count": self._count_tokens_cached(chunk_text)
                    })

        return segments

    def _create_stage1_independent_chunk(
        self,
        text: str,
        element_type: str,
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        创建阶段1独立元素块。
        说明：该阶段允许超限块暂存为 pending_split，避免误报“严重错误”日志。
        """
        header_path = section.get("header_path", "")
        budget_header_text = self._get_budget_header_text(section)
        prompt_header_paths = section.get("prompt_header_paths", [header_path] if header_path else [])
        prompt_header_text = section.get(
            "prompt_header_text",
            " | ".join([p for p in prompt_header_paths if p]) if prompt_header_paths else header_path
        )
        budget_header_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
        content_tokens = self._count_tokens_cached(text)
        total_tokens = budget_header_tokens + content_tokens

        return {
            "text": text,
            "metadata": {
                **metadata,
                "node_id": str(uuid4()),
                "parent_id": None,
                "child_ids": [],
                # --- 拓扑角色字段（establish_hierarchy 中赋值）---
                "is_root": False,
                "is_leaf": True,
                "depth": 2,  # 默认叶子块 depth，建立层级关系后覆写
                # ---
                "chunk_strategy": "markdown",
                "chunk_type": element_type,
                "heading": section.get("heading", ""),
                "header_path": header_path,
                "budget_header_text": budget_header_text,
                "prompt_header_paths": prompt_header_paths,
                "prompt_header_text": prompt_header_text,
                "section_level": section.get("level", 0),
                "token_count": content_tokens,
                "total_tokens": total_tokens,
                "is_smart": True,
                "is_hierarchical": self.enable_hierarchy,
                "is_pruned": False,
                "should_vectorize": True,  # 独立元素块也向量化
                "has_code": "```" in text,
                "has_table": "|" in text and "---" in text,
                "has_formula": "$" in text,
                "is_independent_element": True,
                "element_type": element_type,
                "split_required": total_tokens > self.chunk_size,
                "pending_split": total_tokens > self.embedding_model_limit,
            },
            "type": "text"
        }

    def _merge_small_chunks(
        self,
        chunks: List[Dict[str, Any]],
        section: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        合并相邻小块（不限于最后一块）。
        规则：任一侧小于 min_chunk_size 且合并后不超限时合并。
        """
        if len(chunks) < 2:
            return chunks

        budget_header_text = self._get_budget_header_text(section)
        content_limit = self._get_effective_content_limit(
            budget_header_text,
            self.embedding_model_limit,
        )

        merged: List[Dict[str, Any]] = []
        for chunk in chunks:
            if not merged:
                merged.append(chunk)
                continue

            prev = merged[-1]
            prev_meta = prev.get("metadata", {})
            curr_meta = chunk.get("metadata", {})

            # 不可合并块：待拆分、已拆分父节点（有子节点）等
            prev_has_children = bool(prev_meta.get("child_ids")) or bool(prev_meta.get("has_split_children"))
            curr_has_children = bool(curr_meta.get("child_ids")) or bool(curr_meta.get("has_split_children"))
            if (
                prev_meta.get("pending_split")
                or curr_meta.get("pending_split")
                or prev_meta.get("split_required")
                or curr_meta.get("split_required")
                or prev_has_children
                or curr_has_children
            ):
                merged.append(chunk)
                continue

            prev_tokens = prev_meta.get("token_count", self._count_tokens_cached(prev["text"]))
            curr_tokens = curr_meta.get("token_count", self._count_tokens_cached(chunk["text"]))
            combined_tokens = prev_tokens + curr_tokens

            should_merge = (prev_tokens < self.min_chunk_size or curr_tokens < self.min_chunk_size)
            if should_merge and combined_tokens <= content_limit:
                merged_text = prev["text"] + "\n\n" + chunk["text"]
                merged_chunk = self._create_chunk_dict(
                    merged_text,
                    section,
                    prev_meta
                )
                # 合并后视为普通文本块，避免被后续当作独立元素处理
                merged_chunk["metadata"]["is_independent_element"] = False
                merged_chunk["metadata"]["element_type"] = "paragraph"
                merged_chunk["metadata"]["split_required"] = False
                merged_chunk["metadata"]["pending_split"] = False
                merged_chunk["metadata"]["has_split_children"] = False
                merged[-1] = merged_chunk
            else:
                merged.append(chunk)

        return merged

    def _refresh_parent_chunks(
        self,
        parent_chunks: List[Dict[str, Any]],
        child_chunks: List[Dict[str, Any]]
    ) -> None:
        """
        阶段3拆分后刷新父块内容与 token，避免 child_ids 与父块文本不一致。
        """
        if not parent_chunks:
            return

        child_map = {
            c.get("metadata", {}).get("node_id"): c
            for c in child_chunks
            if c.get("metadata", {}).get("node_id")
        }

        for parent in parent_chunks:
            p_meta = parent.get("metadata", {})
            child_ids = p_meta.get("child_ids", [])
            children = [child_map[cid] for cid in child_ids if cid in child_map]
            if not children:
                continue

            parent_text = "\n\n".join(c["text"] for c in children)
            budget_header_text = self._get_budget_header_text(p_meta)
            header_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
            content_tokens = self._count_tokens_cached(parent_text)

            parent["text"] = parent_text
            p_meta["token_count"] = content_tokens
            p_meta["total_tokens"] = header_tokens + content_tokens
            p_meta["child_count"] = len(children)
            p_meta["has_code"] = "```" in parent_text
            p_meta["has_table"] = "|" in parent_text and "---" in parent_text
            p_meta["has_formula"] = "$" in parent_text

    def _create_parent_chunks_with_target(
        self,
        child_chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        parent_target_size: int
    ) -> List[Dict[str, Any]]:
        """按指定目标大小构建父块，逻辑与现有父块组装一致。"""
        if not child_chunks:
            return []

        parent_chunks: List[Dict[str, Any]] = []
        current_parent_children: List[Dict[str, Any]] = []
        current_tokens = 0

        for child in child_chunks:
            child_tokens = child["metadata"].get("token_count")
            if child_tokens is None:
                child_tokens = self._count_tokens_cached(child["text"])
                child["metadata"]["token_count"] = child_tokens

            if current_tokens + child_tokens <= parent_target_size:
                current_parent_children.append(child)
                current_tokens += child_tokens
            else:
                if current_parent_children:
                    parent_chunks.append(
                        self._create_parent_chunk_dict(current_parent_children, metadata)
                    )
                current_parent_children = [child]
                current_tokens = child_tokens

        if current_parent_children:
            parent_chunks.append(self._create_parent_chunk_dict(current_parent_children, metadata))

        return parent_chunks

    def _split_oversized_independent_chunks(
        self,
        child_chunks: List[Dict[str, Any]],
        parent_chunks: List[Dict[str, Any]],
        section: Dict[str, Any],
        metadata: Dict[str, Any],
        available_tokens: int
    ) -> List[Dict[str, Any]]:
        """
        阶段3：仅处理阶段1标记的超限独立块，拆分后维护父子关系。
        """
        if not child_chunks:
            return child_chunks

        parent_map = {
            p["metadata"].get("node_id"): p
            for p in parent_chunks
            if p.get("metadata", {}).get("node_id")
        }

        new_children: List[Dict[str, Any]] = []
        for child in child_chunks:
            child_meta = child.get("metadata", {})
            need_split = child_meta.get("pending_split") or child_meta.get("split_required")
            if not need_split:
                new_children.append(child)
                continue

            element_type = child_meta.get("element_type", "paragraph")
            element_dict = {
                "type": element_type,
                "content": child["text"],
                "start": 0,
                "end": len(child["text"]),
            }

            split_children = self.splitter.split_large_element(element_dict, section, metadata)
            if not split_children:
                new_children.append(child)
                continue

            # 拆分后的块必须满足内容+完整标题不超过限制（按 available_tokens 校验内容）
            validated_split_children: List[Dict[str, Any]] = []
            for split_child in split_children:
                split_total = split_child.get("metadata", {}).get("total_tokens")
                if split_total is None:
                    content_tokens = self._count_tokens_cached(split_child["text"])
                    budget_header_text = self._get_budget_header_text(section)
                    header_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
                    split_total = content_tokens + header_tokens
                    split_child["metadata"]["total_tokens"] = split_total
                    split_child["metadata"]["token_count"] = content_tokens
                if split_total > self.embedding_model_limit:
                    logger.error(
                        f"[MarkdownChunker] 拆分后仍超限: element={element_type}, "
                        f"total_tokens={split_total}, limit={self.embedding_model_limit}, "
                        f"available_tokens={available_tokens}"
                    )
                split_child["metadata"]["pending_split"] = False
                split_child["metadata"]["is_independent_element"] = True
                split_child["metadata"]["element_type"] = element_type
                validated_split_children.append(split_child)

            old_child_id = child_meta.get("node_id")
            old_parent_id = child_meta.get("parent_id")
            old_section_id = child_meta.get("section_id")
            new_child_ids: List[str] = []
            for split_child in validated_split_children:
                # 显式记录拆分来源块，供后续位置锚点优先继承原始大元素的位置。
                split_child["metadata"]["origin_node_id"] = old_child_id
                split_child["metadata"]["parent_id"] = old_child_id
                split_child["metadata"]["section_id"] = old_section_id
                old_depth = child_meta.get("depth", 2)
                split_child["metadata"]["depth"] = old_depth + 1
                split_child["metadata"]["is_root"] = False
                split_child["metadata"]["is_leaf"] = True
                split_child["metadata"]["prompt_header_paths"] = child_meta.get(
                    "prompt_header_paths",
                    [child_meta.get("header_path")] if child_meta.get("header_path") else []
                )
                split_child["metadata"]["budget_header_text"] = child_meta.get(
                    "budget_header_text",
                    child_meta.get("header_path", "")
                )
                split_child["metadata"]["prompt_header_text"] = child_meta.get(
                    "prompt_header_text",
                    child_meta.get("header_path", "")
                )
                split_child["metadata"]["should_vectorize"] = True
                if "node_id" not in split_child["metadata"]:
                    split_child["metadata"]["node_id"] = str(uuid4())
                new_child_ids.append(split_child["metadata"]["node_id"])

            # 保留完整独立块，不删除；拆分块挂到完整块下
            child_meta["child_ids"] = new_child_ids
            child_meta["pending_split"] = False
            child_meta["split_required"] = False
            child_meta["has_split_children"] = True
            child_meta["should_vectorize"] = False

            # 若有父块，保持父块对子节点引用为“完整独立块”
            if old_parent_id and old_parent_id in parent_map and old_child_id:
                parent_meta = parent_map[old_parent_id]["metadata"]
                if old_child_id not in parent_meta.get("child_ids", []):
                    parent_meta.setdefault("child_ids", []).append(old_child_id)
                    parent_meta["child_count"] = len(parent_meta["child_ids"])

            new_children.append(child)
            new_children.extend(validated_split_children)

        return new_children
    
    def _handle_last_chunk(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        处理最后一块（如果太小，尝试合并到前一块）
        
        规则：
        - 如果最后一块 < min_chunk_size，尝试合并到前一块
        - 合并后不能超过 embedding_model_limit
        """
        if len(chunks) < 2:
            return chunks
        
        last_chunk = chunks[-1]
        # 安全获取 token_count，如果没有则计算
        last_tokens = last_chunk["metadata"].get("token_count")
        if last_tokens is None:
            last_tokens = self._count_tokens_cached(last_chunk["text"])
        
        if last_tokens >= self.min_chunk_size:
            # 大小合适，不需要合并
            return chunks
        
        # 尝试合并到前一块
        prev_chunk = chunks[-2]
        # 安全获取 token_count
        prev_tokens = prev_chunk["metadata"].get("token_count")
        if prev_tokens is None:
            prev_tokens = self._count_tokens_cached(prev_chunk["text"])
        
        # 检查合并后是否超过限制（按统一预算标题）
        budget_header_text = self._get_budget_header_text(prev_chunk["metadata"])
        available_tokens = self._get_effective_content_limit(
            budget_header_text,
            self.embedding_model_limit,
        )
        
        if prev_tokens + last_tokens <= available_tokens:
            # 可以合并
            merged_text = prev_chunk["text"] + "\n\n" + last_chunk["text"]
            merged_chunk = self._create_chunk_dict(
                merged_text,
                {
                    "heading": prev_chunk["metadata"]["heading"],
                    "header_path": prev_chunk["metadata"]["header_path"],
                    "budget_header_text": prev_chunk["metadata"].get("budget_header_text", prev_chunk["metadata"].get("header_path", "")),
                    "prompt_header_text": prev_chunk["metadata"].get("prompt_header_text", prev_chunk["metadata"].get("header_path", "")),
                    "prompt_header_paths": prev_chunk["metadata"].get("prompt_header_paths", []),
                },
                prev_chunk["metadata"]
            )
            
            logger.debug(
                f"[MarkdownChunker] 合并最后一块: "
                f"prev_tokens={prev_tokens}, last_tokens={last_tokens}, "
                f"merged_tokens={merged_chunk['metadata']['token_count']}"
            )
            
            # 替换最后两块
            return chunks[:-2] + [merged_chunk]
        else:
            # 无法合并，保持原样
            logger.debug(
                f"[MarkdownChunker] 最后一块太小但无法合并: "
                f"last_tokens={last_tokens}, min_chunk_size={self.min_chunk_size}"
            )
            return chunks

    def _get_effective_content_limit(
        self,
        budget_header_text: str,
        available_tokens: int,
        safety_margin: int = 20,
    ) -> int:
        """
        统一计算正文可用上限。

        设计原则：
        - `chunk_size` 是前端配置的目标大小，应该优先被尊重。
        - `available_tokens` / `embedding_model_limit` 是硬上限，不能突破。
        - 最终正文大小取两者较小值，避免 Markdown 分块悄悄忽略 chunk_size。
        """
        header_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
        hard_limit = max(1, int(available_tokens) - header_tokens - safety_margin)
        return max(1, min(int(self.chunk_size), hard_limit))
    
    def _create_section_chunk(
        self,
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        创建章节块（根节点）

        章节块特点：
        - depth = 0（根节点）
        - is_root = True
        - 不向量化（should_vectorize = False）
        - 用于直接返回完整章节内容
        """
        text = section["text"]
        heading = section.get("heading", "")
        header_path = section.get("header_path", "")
        budget_header_text = self._get_budget_header_text(section)
        prompt_header_paths = section.get("prompt_header_paths", [header_path] if header_path else [])
        prompt_header_text = section.get(
            "prompt_header_text",
            " | ".join([p for p in prompt_header_paths if p]) if prompt_header_paths else header_path
        )
        section_level = section.get("level", 0)
        
        # 计算 token
        header_path_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
        content_tokens = self._count_tokens_cached(text)
        total_tokens = header_path_tokens + content_tokens
        
        return {
            "text": text,
            "metadata": {
                **metadata,
                "node_id": str(uuid4()),
                "parent_id": None,  # 章节块没有父块
                "child_ids": [],    # 稍后填充
                # --- 拓扑角色字段 ---
                "is_root": True,    # 章节块是根节点
                "is_leaf": False,   # 稍后根据 child_ids 是否为空来动态修正
                "depth": 0,         # 根节点深度为 0
                # ---
                "chunk_strategy": "markdown",
                "chunk_type": "section",
                "heading": heading,
                "header_path": header_path,
                "budget_header_text": budget_header_text,
                "prompt_header_paths": prompt_header_paths,
                "prompt_header_text": prompt_header_text,
                "section_level": section_level,
                "token_count": content_tokens,
                "total_tokens": total_tokens,
                "is_smart": True,
                "is_hierarchical": self.enable_hierarchy,
                "is_pruned": False,
                "should_vectorize": False,  # 章节块不向量化
                "has_code": "```" in text,
                "has_table": "|" in text and "---" in text,
                "has_formula": "$" in text,
            },
            "type": "text"
        }
    
    def _establish_three_level_hierarchy(
        self,
        section_chunk: Dict[str, Any],
        parent_chunks: List[Dict[str, Any]],
        child_chunks: List[Dict[str, Any]]
    ) -> None:
        """
        建立三层父子关系：章节块(depth=0) → 父块(depth=1) → 子块(depth=2+)
        
        关系：
        - 章节块.child_ids = [父块1, 父块2, ...]
        - 父块.parent_id = 章节块.node_id
        - 父块.child_ids = [子块1, 子块2, ...]
        - 子块.parent_id = 父块.node_id
        - 子块.section_id = 章节块.node_id
        """
        section_id = section_chunk["metadata"]["node_id"]
        
        # 1. 章节块 → 父块
        section_chunk["metadata"]["child_ids"] = [
            p["metadata"]["node_id"] for p in parent_chunks
        ]
        section_chunk["metadata"]["is_leaf"] = False  # 有子节点，不是叶子
        
        # 2. 父块 → 章节块 & 子块（depth = 1，中间块）
        for parent in parent_chunks:
            parent["metadata"]["parent_id"] = section_id
            parent["metadata"]["section_id"] = section_id
            parent["metadata"]["should_vectorize"] = False  # 父块不向量化
            parent["metadata"]["is_root"] = False
            parent["metadata"]["is_leaf"] = False
            parent["metadata"]["depth"] = 1
            
            # 3. 子块 → 父块 & 章节块
            for child_id in parent["metadata"]["child_ids"]:
                child = self._find_chunk_by_id(child_chunks, child_id)
                if child:
                    child["metadata"]["parent_id"] = parent["metadata"]["node_id"]
                    child["metadata"]["section_id"] = section_id
                    child["metadata"]["is_root"] = False
                    child["metadata"]["depth"] = 2
                    has_grandchildren = bool(child["metadata"].get("child_ids"))
                    child["metadata"]["is_leaf"] = not has_grandchildren
                    if has_grandchildren:
                        child["metadata"]["should_vectorize"] = False
                    else:
                        child["metadata"]["should_vectorize"] = True
        
        # 所有后代都要带 section_id，但不覆盖其既有 parent_id
        for child in child_chunks:
            child["metadata"]["section_id"] = section_id
        
        logger.debug(
            f"[MarkdownChunker] 建立三层关系: "
            f"章节块 → {len(parent_chunks)} 个父块 → {len(child_chunks)} 个子块"
        )
    
    def _establish_two_level_hierarchy(
        self,
        section_chunk: Dict[str, Any],
        child_chunks: List[Dict[str, Any]]
    ) -> None:
        """
        建立两层父子关系：章节块 → 子块
        
        关系：
        - 章节块.child_ids = [子块1, 子块2, ...]
        - 子块.parent_id = 章节块.node_id
        - 子块.section_id = 章节块.node_id
        """
        section_id = section_chunk["metadata"]["node_id"]
        
        # 1. 章节块 → 仅一级子块（parent_id 尚为空的节点）
        root_children = [c for c in child_chunks if not c["metadata"].get("parent_id")]
        section_chunk["metadata"]["child_ids"] = [
            c["metadata"]["node_id"] for c in root_children
        ]
        
        # 2. 一级子块 → 章节块；更新拓扑角色
        for child in root_children:
            child["metadata"]["parent_id"] = section_id
            child["metadata"]["depth"] = 1
            has_children = bool(child["metadata"].get("child_ids"))
            child["metadata"]["is_root"] = False
            child["metadata"]["is_leaf"] = not has_children
            if has_children:
                child["metadata"]["should_vectorize"] = False
            else:
                child["metadata"]["should_vectorize"] = True

        # 3. 所有后代都带 section_id，不改变已有 parent_id
        descendant_map = {c["metadata"]["node_id"]: c for c in child_chunks}

        def _fix_depths(node_id: str, current_depth: int) -> None:
            """递归修正后代节点的 depth 字段"""
            child_chunk = descendant_map.get(node_id)
            if not child_chunk:
                return
            child_chunk["metadata"]["section_id"] = section_id
            # 仅修正 depth，不强制修改一级子块（已在上方处理）
            if child_chunk["metadata"].get("depth", -1) != current_depth:
                child_chunk["metadata"]["depth"] = current_depth
            for grandchild_id in child_chunk["metadata"].get("child_ids", []):
                _fix_depths(grandchild_id, current_depth + 1)

        for child in root_children:
            for grandchild_id in child["metadata"].get("child_ids", []):
                _fix_depths(grandchild_id, 2)  # root_children 是 depth=1，其子从 depth=2 开始

        # 未经由 root_children 覆盖的其余节点也补 section_id
        for child in child_chunks:
            child["metadata"].setdefault("section_id", section_id)

        # 4. 章节块自身：如果没有子块则它既是根也是叶
        has_section_children = bool(section_chunk["metadata"]["child_ids"])
        section_chunk["metadata"]["is_leaf"] = not has_section_children
        
        logger.debug(
            f"[MarkdownChunker] 建立两层关系: "
            f"章节块 → {len(child_chunks)} 个子块"
        )
    
    @staticmethod
    def _find_chunk_by_id(chunks: List[Dict[str, Any]], node_id: str) -> Dict[str, Any] | None:
        """根据 node_id 查找块"""
        for chunk in chunks:
            if chunk["metadata"].get("node_id") == node_id:
                return chunk
        return None
    
    def _create_parent_chunks(
        self,
        child_chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        合并子块成父块（无 overlap）
        
        策略：
        - 直接拼接相邻的子块
        - 目标大小：parent_chunk_size (通常是 chunk_size * 4)
        - 父块不受 embedding_model_limit 限制（只有子块需要遵守）
        - 父块用于提供更大的上下文，不用于向量化
        """
        if not child_chunks:
            return []
        
        parent_chunks = []
        current_parent_children = []
        current_tokens = 0
        
        for child in child_chunks:
            # 安全获取 token_count
            child_tokens = child["metadata"].get("token_count")
            if child_tokens is None:
                child_tokens = self._count_tokens_cached(child["text"])
                # 补充缺失的 token_count
                child["metadata"]["token_count"] = child_tokens
            
            # 检查是否超过父块大小
            if current_tokens + child_tokens <= self.parent_chunk_size:
                current_parent_children.append(child)
                current_tokens += child_tokens
            else:
                # 保存当前父块
                if current_parent_children:
                    parent_chunk = self._create_parent_chunk_dict(
                        current_parent_children,
                        metadata
                    )
                    parent_chunks.append(parent_chunk)
                
                # 开始新父块
                current_parent_children = [child]
                current_tokens = child_tokens
        
        # 保存最后一个父块
        if current_parent_children:
            parent_chunk = self._create_parent_chunk_dict(
                current_parent_children,
                metadata
            )
            parent_chunks.append(parent_chunk)
        
        return parent_chunks
    
    def _create_parent_chunk_dict(
        self,
        child_chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        创建父块字典（L1）
        
        父块特点：
        - level = 1（中间层）
        - parent_id = None（稍后在 _establish_three_level_hierarchy 中设置）
        - child_ids = [所有子块的 node_id]
        - 不向量化（should_vectorize = False）
        - 用于提供中等粒度上下文
        """
        # 拼接所有子块的文本
        parent_text = '\n\n'.join([child["text"] for child in child_chunks])
        
        # 使用第一个子块的章节信息
        first_child = child_chunks[0]
        heading = first_child["metadata"].get("heading", "")
        header_path = first_child["metadata"].get("header_path", "")
        budget_header_text = self._get_budget_header_text(first_child["metadata"])
        prompt_header_paths = first_child["metadata"].get("prompt_header_paths", [header_path] if header_path else [])
        prompt_header_text = first_child["metadata"].get(
            "prompt_header_text",
            " | ".join([p for p in prompt_header_paths if p]) if prompt_header_paths else header_path
        )
        section_level = first_child["metadata"].get("section_level", 0)
        
        # 生成父块 ID
        parent_node_id = str(uuid4())
        
        # 收集子块 ID，如果子块没有 node_id 则生成一个
        child_ids = []
        for child in child_chunks:
            if "node_id" not in child["metadata"]:
                child["metadata"]["node_id"] = str(uuid4())
            child_ids.append(child["metadata"]["node_id"])
        
        # 计算 token 数
        header_path_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
        content_tokens = self._count_tokens_cached(parent_text)
        total_tokens = header_path_tokens + content_tokens
        
        return {
            "text": parent_text,
            "metadata": {
                **metadata,
                "node_id": parent_node_id,
                "parent_id": None,  # 稍后在建立三层关系时设置
                "child_ids": child_ids,
                # --- 拓扑角色字段（depth 在 establish_hierarchy 中赋值）---
                "is_root": False,
                "is_leaf": False,
                "depth": 1,          # 父块默认 depth=1，若更深时由 establish 覆写
                # ---
                "chunk_strategy": "markdown",
                "chunk_type": "parent",
                "heading": heading,
                "header_path": header_path,
                "budget_header_text": budget_header_text,
                "prompt_header_paths": prompt_header_paths,
                "prompt_header_text": prompt_header_text,
                "section_level": section_level,
                "token_count": content_tokens,
                "total_tokens": total_tokens,
                "child_count": len(child_chunks),
                "is_smart": True,
                "is_hierarchical": True,
                "is_pruned": False,
                "should_vectorize": False,  # 父块不向量化
                "has_code": "```" in parent_text,
                "has_table": "|" in parent_text and "---" in parent_text,
                "has_formula": "$" in parent_text,
            },
            "type": "text"
        }
    
    def _truncate_text_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        将文本截断到指定的 token 数
        
        使用二分查找来快速找到合适的截断点
        """
        if self._count_tokens_cached(text) <= max_tokens:
            return text
        
        # 二分查找截断点
        left, right = 0, len(text)
        result = ""
        
        while left < right:
            mid = (left + right + 1) // 2
            truncated = text[:mid]
            
            if self._count_tokens_cached(truncated) <= max_tokens:
                result = truncated
                left = mid
            else:
                right = mid - 1
        
        return result

    @staticmethod
    def _get_budget_header_text(data: Dict[str, Any]) -> str:
        """
        统一预算标题字段。
        优先级：budget_header_text > header_path > prompt_header_text > heading
        """
        if not isinstance(data, dict):
            return ""
        return (
            data.get("budget_header_text")
            or data.get("header_path")
            or data.get("prompt_header_text")
            or data.get("heading")
            or ""
        )
    
    def _create_chunk_dict(
        self,
        text: str,
        section: Dict[str, Any],
        metadata: Dict[str, Any],
        node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建标准的子块字典（叶子节点）

        子块特点：
        - depth >= 1，默认 2（在 establish_hierarchy 中赋值）
        - is_leaf = True（establish 后如有子块则需改为 False）
        - 向量化（should_vectorize = True）
        - 用于检索

        重要：该方法用于最终可向量化的常规子块，调用前应满足
        total_tokens(内容 + 完整标题) <= embedding_model_limit。
        """
        header_path = section.get("header_path", "")
        budget_header_text = self._get_budget_header_text(section)
        prompt_header_paths = section.get("prompt_header_paths", [header_path] if header_path else [])
        prompt_header_text = section.get(
            "prompt_header_text",
            " | ".join([p for p in prompt_header_paths if p]) if prompt_header_paths else header_path
        )
        header_path_tokens = self._count_tokens_cached(budget_header_text) if budget_header_text else 0
        content_tokens = self._count_tokens_cached(text)
        total_tokens = header_path_tokens + content_tokens
        
        # 检查是否超过限制（理论上不应该发生）
        if total_tokens > self.embedding_model_limit:
            logger.error(
                f"[MarkdownChunker] 严重错误：子块超过嵌入模型限制！"
                f"header_path_tokens={header_path_tokens}, "
                f"content_tokens={content_tokens}, "
                f"total={total_tokens}, "
                f"limit={self.embedding_model_limit}"
            )
            logger.error(
                f"[MarkdownChunker] 这不应该发生！说明上层逻辑有问题。"
                f"available_tokens 应该在 _process_section 中正确计算，"
                f"并在阶段1重组逻辑中正确使用。"
            )
            # 不截断，保留原文，让问题暴露出来以便修复
        
        return {
            "text": text,
            "metadata": {
                **metadata,
                "node_id": node_id or str(uuid4()),
                "parent_id": None,  # 稍后在建立父子关系时设置
                "child_ids": [],    # 子块起始无子块
                # --- 拓扑角色字段（depth/is_root 在 establish_hierarchy 中赋值）---
                "is_root": False,
                "is_leaf": True,    # 默认叶子节点，若后续产生子块则改为 False
                "depth": 2,         # 常规子块默认 depth=2
                # ---
                "chunk_strategy": "markdown",
                "chunk_type": "paragraph",
                "heading": section.get("heading", ""),
                "header_path": header_path,
                "budget_header_text": budget_header_text,
                "prompt_header_paths": prompt_header_paths,
                "prompt_header_text": prompt_header_text,
                "section_level": section.get("level", 0),
                "token_count": content_tokens,
                "total_tokens": total_tokens,
                "is_smart": True,
                "is_hierarchical": self.enable_hierarchy,
                "is_pruned": False,
                "should_vectorize": True,  # 叶子块向量化
                "has_code": "```" in text,
                "has_table": "|" in text and "---" in text,
                "has_formula": "$" in text,
            },
            "type": "text"
        }
    
    def _count_tokens_cached(self, text: str) -> int:
        """
        带缓存的 token 计算
        
        使用 token_utils.count_tokens 进行准确计算
        """
        # 使用文本哈希作为缓存键
        text_hash = hash(text)
        
        if text_hash in self._token_cache:
            return self._token_cache[text_hash]
        
        # 使用 token_utils 的 count_tokens
        token_count = count_tokens(text)
        
        # 缓存结果
        self._token_cache[text_hash] = token_count
        
        # 限制缓存大小
        if len(self._token_cache) > MarkdownChunkerConfig.TOKEN_CACHE_SIZE:
            # 清理最旧的 50% 缓存
            items = list(self._token_cache.items())
            self._token_cache = dict(items[MarkdownChunkerConfig.TOKEN_CACHE_SIZE // 2:])
        
        return token_count
    
    def _finalize_topology_flags(self, all_chunks: List[Dict[str, Any]]) -> None:
        """
        全局终态修正：在所有中间处理阶段完成后，以最终实际状态重新校正拓扑标志。

        修正规则（以 child_ids 是否为空为唯一依据）：
        -  has_children  → is_leaf = False，should_vectorize = False
        - !has_children  → is_leaf = True，should_vectorize = True

        覆盖的错误场景：
        1. 小章节块（策略1直接返回），初始 is_leaf=False，但实际没有任何子块 → 修正为 is_leaf=True
        2. 经过 _split_oversized_independent_chunks 后，某些独立元素块新增了子块，
           但 is_leaf 未从 True 同步更新为 False → 修正
        3. _merge_small_chunks/_handle_last_chunk 导致某些 chunk 消失，
           其前一块的 child_ids 指向的 node_id 可能已不在 all_chunks 中 → 修正叶子状态
        """
        if not all_chunks:
            return

        # 收集所有实际存在的 node_id，用于验证 child_ids 的有效性
        existing_node_ids = {
            c["metadata"].get("node_id")
            for c in all_chunks
            if c["metadata"].get("node_id")
        }

        corrected = 0
        for chunk in all_chunks:
            meta = chunk["metadata"]

            # 过滤掉指向不存在节点的 child_ids（防止因合并/删除导致的僵尸引用）
            raw_child_ids = meta.get("child_ids", [])
            valid_child_ids = [cid for cid in raw_child_ids if cid in existing_node_ids]
            if valid_child_ids != raw_child_ids:
                meta["child_ids"] = valid_child_ids

            has_children = bool(valid_child_ids)
            current_is_leaf = meta.get("is_leaf", True)

            if current_is_leaf == has_children:
                # is_leaf 与实际状态矛盾：
                #   has_children=True  但 is_leaf=True  → 应改为 False
                #   has_children=False 但 is_leaf=False → 应改为 True
                meta["is_leaf"] = not has_children
                # 同步 should_vectorize：叶子才向量化
                meta["should_vectorize"] = not has_children
                corrected += 1

        if corrected:
            logger.debug(
                f"[MarkdownChunker] _finalize_topology_flags: "
                f"修正了 {corrected} 个 chunk 的 is_leaf/should_vectorize"
            )

    def _normalize_chunk_protocol(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """统一 MarkdownChunker 输出协议，避免依赖下游兜底。"""
        normalized_chunks: List[Dict[str, Any]] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue

            text = str(chunk.get("text") or "").strip()
            if not text:
                continue

            chunk_type = str(chunk.get("type") or "text").lower()
            metadata = chunk.get("metadata")
            metadata = dict(metadata) if isinstance(metadata, dict) else {}
            metadata.setdefault("source_anchors", [])
            metadata.setdefault("source_element_indices", [])
            metadata.setdefault("page_numbers", [])

            content_blocks = chunk.get("content_blocks")
            if not isinstance(content_blocks, list) or not content_blocks:
                block_type = "title" if metadata.get("chunk_type") == "section" else "text"
                content_blocks = [
                    {
                        "block_id": "b1",
                        "type": block_type,
                        "text": text,
                        "source_refs": [],
                    }
                ]
            else:
                normalized_blocks: List[Dict[str, Any]] = []
                for idx, block in enumerate(content_blocks, start=1):
                    if not isinstance(block, dict):
                        continue
                    normalized_block = dict(block)
                    normalized_block.setdefault("block_id", f"b{idx}")
                    normalized_block.setdefault("type", "text")
                    normalized_block.setdefault("source_refs", [])
                    normalized_blocks.append(normalized_block)
                content_blocks = normalized_blocks or [
                    {
                        "block_id": "b1",
                        "type": "text",
                        "text": text,
                        "source_refs": [],
                    }
                ]

            normalized_chunks.append(
                {
                    **chunk,
                    "text": text,
                    "type": chunk_type,
                    "metadata": metadata,
                    "content_blocks": content_blocks,
                }
            )

        return normalized_chunks

    def _fallback_chunk(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """回退方案：简单按段落分块"""
        chunks: List[Dict[str, Any]] = []
        paragraphs = text.split('\n\n')
        
        current_chunk: List[str] = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self._count_tokens_cached(para)
            
            if current_tokens + para_tokens <= self.chunk_size:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {
                            **metadata,
                            "chunk_index": len(chunks),
                            "chunk_strategy": "markdown_fallback",
                            "token_count": current_tokens,
                        }
                    })
                
                current_chunk = [para]
                current_tokens = para_tokens
        
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "chunk_index": len(chunks),
                    "chunk_strategy": "markdown_fallback",
                    "token_count": current_tokens,
                }
            })
        
        if not chunks:
            chunks.append({
                "text": text,
                "metadata": {
                    **metadata,
                    "chunk_index": 0,
                    "chunk_strategy": "markdown_fallback",
                    "token_count": self._count_tokens_cached(text),
                }
            })
        
        return chunks
