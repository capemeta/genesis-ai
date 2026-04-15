"""
Markdown 解析器 - 负责按标题预分块
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class MarkdownParser:
    """Markdown 标题解析器"""
    
    def __init__(self):
      pass
    
    def parse_by_heading(
        self,
        text: str,
        metadata: Dict[str, Any],
        count_tokens_fn,
        max_section_total_tokens: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        按标题预分块（使用 MarkdownNodeParser）
        
        Returns:
            List[Dict]: 章节列表，每个章节包含 text, heading, level, header_path
        """
        try:
            from llama_index.core import Document
            from llama_index.core.node_parser import MarkdownNodeParser
            
            parser = MarkdownNodeParser(
                include_metadata=True,
                include_prev_next_rel=False,
            )
            
            doc = Document(text=text)
            nodes = parser.get_nodes_from_documents([doc])
            
            sections = []
            for node in nodes:
                content = node.get_content()
                if not content or not content.strip():
                    continue
                
                node_meta = getattr(node, "metadata", {})
                header_path = self._normalize_header_path(node_meta.get("header_path", ""))
                
                # 提取标题级别
                level = self._extract_heading_level(content)
                heading = self._extract_heading_text(content)
                if not header_path and heading:
                    header_path = heading
                
                sections.append({
                    "text": content,
                    "heading": heading,
                    "level": level,
                    "header_path": header_path,
                    "budget_header_text": header_path or heading,
                    "token_count": count_tokens_fn(content),
                    "prompt_header_paths": [header_path] if header_path else [],
                    "prompt_header_text": header_path or heading,
                })

            return self._merge_adjacent_sections(
                sections,
                count_tokens_fn,
                max_section_total_tokens
            )
            
        except Exception as e:
            logger.error(f"[MarkdownParser] 标题解析失败: {e}")
            sections = self._simple_parse_by_heading(text, count_tokens_fn)
            return self._merge_adjacent_sections(
                sections,
                count_tokens_fn,
                max_section_total_tokens
            )
    
    
    def _simple_parse_by_heading(self, text: str, count_tokens_fn) -> List[Dict[str, Any]]:
        """简单的标题解析（回退方案）"""
        sections: List[Dict[str, Any]] = []
        lines = text.split('\n')
        current_section: List[str] = []
        current_heading = ""
        current_header_path = ""
        current_level = 0
        heading_by_level: Dict[int, str] = {}
        
        for line in lines:
            if line.startswith('#'):
                # 保存上一个章节
                if current_section:
                    section_text = '\n'.join(current_section)
                    if section_text.strip():
                        sections.append({
                            "text": section_text,
                            "heading": current_heading,
                            "level": current_level,
                            "header_path": current_header_path,
                            "budget_header_text": current_header_path or current_heading,
                            "token_count": count_tokens_fn(section_text),
                            "prompt_header_paths": [current_header_path] if current_header_path else [],
                            "prompt_header_text": current_header_path or current_heading,
                        })
                
                # 开始新章节
                current_level = len(line) - len(line.lstrip('#'))
                current_heading = line.lstrip('#').strip()
                if current_heading:
                    # 维护标题层级映射，构建完整 header_path
                    heading_by_level = {
                        lv: h for lv, h in heading_by_level.items() if lv < current_level
                    }
                    heading_by_level[current_level] = current_heading
                    current_header_path = "/".join(
                        heading_by_level[lv] for lv in sorted(heading_by_level.keys())
                    )
                else:
                    current_header_path = ""
                current_section = [line]
            else:
                current_section.append(line)
        
        # 保存最后一个章节
        if current_section:
            section_text = '\n'.join(current_section)
            if section_text.strip():
                sections.append({
                    "text": section_text,
                    "heading": current_heading,
                    "level": current_level,
                    "header_path": current_header_path,
                    "budget_header_text": current_header_path or current_heading,
                    "token_count": count_tokens_fn(section_text),
                    "prompt_header_paths": [current_header_path] if current_header_path else [],
                    "prompt_header_text": current_header_path or current_heading,
                })
        
        return sections if sections else [{
            "text": text,
            "heading": "",
            "level": 0,
            "header_path": "",
            "budget_header_text": "",
            "token_count": count_tokens_fn(text),
            "prompt_header_paths": [],
            "prompt_header_text": "",
        }]

    def _merge_adjacent_sections(
        self,
        sections: List[Dict[str, Any]],
        count_tokens_fn,
        max_section_total_tokens: Optional[int]
    ) -> List[Dict[str, Any]]:
        """
        分两个阶段进行迭代合并：
        阶段 1：层级优先合并 (Hierarchical First) - 确保父标题优先吸纳自己的子孙内容。
        阶段 2：同级碎片合并 (Sibling Compaction) - 在不破坏结构的前提下合并小块。
        """
        if len(sections) < 2:
            return sections

        working = sections

        # 阶段 1：层级吸收 (父吸纳子，stub 并入后续)
        # 这一步是保护语义结构的完整性，必须优先完成
        for _ in range(len(working)):
            changed = False
            hierarchical_merged: List[Dict[str, Any]] = []
            i = 0
            while i < len(working):
                current = working[i]
                if i + 1 >= len(working):
                    hierarchical_merged.append(current)
                    break
                
                # 仅执行层级合并
                if self._should_merge_sections(current, working[i+1], max_section_total_tokens, count_tokens_fn, hierarchical_only=True):
                    hierarchical_merged.append(self._merge_two_sections(current, working[i+1], count_tokens_fn))
                    i += 2
                    changed = True
                else:
                    hierarchical_merged.append(current)
                    i += 1
            working = hierarchical_merged
            if not changed:
                break

        # 阶段 2：同级碎块合并
        # 在层级已经稳固后，再把相邻的细碎同级块合在一起
        for _ in range(len(working)):
            changed = False
            sibling_merged: List[Dict[str, Any]] = []
            i = 0
            while i < len(working):
                current = working[i]
                if i + 1 >= len(working):
                    sibling_merged.append(current)
                    break
                
                # 执行同级合并（此时 hierarchical_only=False）
                if self._should_merge_sections(current, working[i+1], max_section_total_tokens, count_tokens_fn, hierarchical_only=False):
                    sibling_merged.append(self._merge_two_sections(current, working[i+1], count_tokens_fn))
                    i += 2
                    changed = True
                else:
                    sibling_merged.append(current)
                    i += 1
            working = sibling_merged
            if not changed:
                break

        return working

    def _should_merge_sections(
        self,
        sec1: Dict[str, Any],
        sec2: Dict[str, Any],
        max_section_total_tokens: Optional[int],
        count_tokens_fn,
        hierarchical_only: bool = False
    ) -> bool:
        sec1_total = sec1.get("token_count", 0) + self._count_budget_header_tokens(sec1, count_tokens_fn)
        sec2_total = sec2.get("token_count", 0) + self._count_budget_header_tokens(sec2, count_tokens_fn)

        # 如果后一个块本身已经超限，不做任何合并
        if max_section_total_tokens and sec2_total > max_section_total_tokens:
            return False

        l1, l2 = sec1.get("level", 0), sec2.get("level", 0)
        
        # 预计算合并后的预期 token
        merged_budget_header = self._merged_budget_header_text(sec1, sec2)
        merged_total = sec1.get("token_count", 0) + sec2.get("token_count", 0) + count_tokens_fn(merged_budget_header)
        
        if max_section_total_tokens and merged_total > max_section_total_tokens:
            return False

        # --- 规则 A：层级合并 (总是最优先) ---
        
        # A1: Stub 吸收 - 前块是空标题
        if self._is_heading_stub(sec1) and l2 >= l1:
            return True

        # A2: 结构合并 - 父吸收子
        if l2 > l1:
            return True

        # 如果当前只是层级合并阶段，到此为止
        if hierarchical_only:
            return False

        # --- 规则 B：同级合并 (仅作为结构稳固后的填充) ---
        if l1 == l2:
            # 只有细粒度末端标题 (Level 3+) 允许自动合并相邻兄弟
            if l1 >= 3:
                return True
            
            # Level 2 的大章节，由于是核心骨架，合并必须非常严苛
            if l1 == 2 and self._is_same_parent(sec1, sec2):
                # 只有两个都很小时才合并
                if sec1.get("token_count", 0) + sec2.get("token_count", 0) < 150:
                    return True

        return False

    def _merge_two_sections(self, sec1: Dict[str, Any], sec2: Dict[str, Any], count_tokens_fn) -> Dict[str, Any]:
        merged_text = f"{sec1['text'].rstrip()}\n\n{sec2['text'].lstrip()}"
        merged_header_path = self._merged_header_path(sec1, sec2)
        merged_budget_header = self._merged_budget_header_text(sec1, sec2)
        prompt_paths = []
        prompt_paths.extend(sec1.get("prompt_header_paths", []))
        prompt_paths.extend(sec2.get("prompt_header_paths", []))
        prompt_paths = [self._normalize_header_path(p) for p in prompt_paths]
        prompt_paths = list(dict.fromkeys([p for p in prompt_paths if p]))

        return {
            "text": merged_text,
            "heading": sec2.get("heading") or sec1.get("heading", ""),
            "level": min(sec1.get("level", 99) or 99, sec2.get("level", 99) or 99),
            "header_path": merged_header_path,
            "budget_header_text": merged_budget_header,
            "token_count": count_tokens_fn(merged_text),
            "prompt_header_paths": prompt_paths,
            "prompt_header_text": " | ".join(prompt_paths) if prompt_paths else merged_header_path,
        }

    def _is_heading_stub(self, section: Dict[str, Any]) -> bool:
        lines = [line for line in section.get("text", "").split("\n") if line.strip()]
        if not lines:
            return False
        first = lines[0].lstrip()
        is_heading = first.startswith("#")
        # RAG 优化：放宽判定条件（行数从 2->3，token 从 40->80）
        # 这样包含简短简介或引导语的标题块会被视作 stub 自动并入下一块
        return is_heading and len(lines) <= 3 and section.get("token_count", 0) <= 80

    def _is_same_parent(self, sec1: Dict[str, Any], sec2: Dict[str, Any]) -> bool:
        p1 = [p for p in self._normalize_header_path(sec1.get("header_path", "")).split("/") if p]
        p2 = [p for p in self._normalize_header_path(sec2.get("header_path", "")).split("/") if p]
        
        # 1. 明确的层级路径匹配 (Parent path matching)
        if len(p1) >= 2 and len(p2) >= 2:
            return p1[:-1] == p2[:-1]
            
        # 2. 如果路径只有一段，且是最高层级（如 ##），则认为它们是顶级独立章节，不属于“同一个父级”
        # 只有在路径只有一段，且级别较低（Level 3+）时，相邻才可能被视为兄弟
        if len(p1) == 1 and len(p2) == 1:
            if int(sec1.get("level") or 0) >= 3:
                return True
            
        return False

    def _merged_header_path(self, sec1: Dict[str, Any], sec2: Dict[str, Any]) -> str:
        # header_path 不降级：优先保持后一个块（更具体）的完整路径
        sec2_header = self._normalize_header_path(sec2.get("header_path", ""))
        if sec2_header:
            return sec2_header
        return self._normalize_header_path(sec1.get("header_path", ""))

    def _merged_budget_header_text(self, sec1: Dict[str, Any], sec2: Dict[str, Any]) -> str:
        # 预算标题统一：优先使用合并后 header_path
        merged_header_path = self._merged_header_path(sec1, sec2)
        if merged_header_path:
            return merged_header_path
        return (
            sec2.get("budget_header_text")
            or sec2.get("prompt_header_text")
            or sec1.get("budget_header_text")
            or sec1.get("prompt_header_text")
            or ""
        )

    def _common_header_path(self, sec1: Dict[str, Any], sec2: Dict[str, Any]) -> str:
        p1 = [p for p in self._normalize_header_path(sec1.get("header_path", "")).split("/") if p]
        p2 = [p for p in self._normalize_header_path(sec2.get("header_path", "")).split("/") if p]
        common = []
        for a, b in zip(p1, p2):
            if a == b:
                common.append(a)
            else:
                break
        if common:
            return "/".join(common)
        return self._normalize_header_path(sec1.get("header_path") or sec2.get("header_path", ""))

    def _count_budget_header_tokens(self, section: Dict[str, Any], count_tokens_fn) -> int:
        header = section.get("budget_header_text")
        if not header:
            header = self._normalize_header_path(section.get("header_path", ""))
        return count_tokens_fn(header) if header else 0

    @staticmethod
    def _normalize_header_path(path: str) -> str:
        if not path:
            return ""
        # 兼容 llama_index 可能输出的根路径占位（如 "/" 或 "/xxx/"）
        parts = [p.strip() for p in str(path).split("/") if p and p.strip()]
        return "/".join(parts)
    
    @staticmethod
    def _extract_heading_level(text: str) -> int:
        """提取标题级别"""
        first_line = text.split('\n')[0]
        if first_line.startswith('#'):
            return len(first_line) - len(first_line.lstrip('#'))
        return 0
    
    @staticmethod
    def _extract_heading_text(text: str) -> str:
        """提取标题文本"""
        first_line = text.split('\n')[0]
        if first_line.startswith('#'):
            return first_line.lstrip('#').strip()
        return ""
