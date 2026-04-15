"""
PDF 解析器基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from .models import ParserElement


class BasePDFParser(ABC):
    """
    PDF 解析器基类
    
    所有 PDF 解析器都应该继承此类并实现 parse 方法。
    统一返回 List[ParserElement] 结构。
    """
    
    @abstractmethod
    def parse(self, file_buffer: bytes) -> List[ParserElement]:
        """
        解析 PDF 文件
        
        Args:
            file_buffer: PDF 文件的字节内容
        
        Returns:
            List[ParserElement]: 标准化的结构化元素列表
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查解析器是否可用"""
        pass
    
    def get_name(self) -> str:
        """获取解析器名称"""
        return self.__class__.__name__

    @staticmethod
    def to_markdown(elements: List[ParserElement]) -> str:
        """
        将 ParserElement 列表转换为纯净的 Markdown 字符串
        适用于：作为 LLM 上下文、全文索引预览、存储审计文件
        
        改进：正确处理列表、代码块、标题
        """
        def _merge_adjacent_titles(src: List[ParserElement]) -> List[ParserElement]:
            if not src:
                return []

            merged: List[ParserElement] = []
            i = 0
            while i < len(src):
                cur = src[i]
                if cur.get("type") != "title":
                    merged.append(cur)
                    i += 1
                    continue

                cur_level = (cur.get("metadata") or {}).get("level", 1)
                cur_page = cur.get("page_no")
                cur_bbox = cur.get("bbox") or [0, 0, 0, 0]
                cur_text = (cur.get("content") or "").strip()

                if not cur_text:
                    merged.append(cur)
                    i += 1
                    continue

                parts = [cur_text]
                new_bbox = list(cur_bbox)
                j = i + 1

                while j < len(src):
                    nxt = src[j]
                    if nxt.get("type") != "title":
                        break

                    nxt_level = (nxt.get("metadata") or {}).get("level", 1)
                    if nxt_level != cur_level:
                        break

                    if nxt.get("page_no") != cur_page:
                        break

                    nxt_bbox = nxt.get("bbox") or [0, 0, 0, 0]
                    try:
                        y_gap = float(nxt_bbox[1]) - float(new_bbox[3])
                        x_gap = abs(float(nxt_bbox[0]) - float(new_bbox[0]))
                    except Exception:
                        y_gap = 999
                        x_gap = 999

                    # 同一标题被拆成多块：通常 y 间距很小，且左对齐接近
                    if y_gap > 18 or x_gap > 60:
                        break

                    nxt_text = (nxt.get("content") or "").strip()
                    if nxt_text:
                        if not parts or parts[-1] != nxt_text:
                            parts.append(nxt_text)

                    new_bbox[0] = min(new_bbox[0], nxt_bbox[0])
                    new_bbox[1] = min(new_bbox[1], nxt_bbox[1])
                    new_bbox[2] = max(new_bbox[2], nxt_bbox[2])
                    new_bbox[3] = max(new_bbox[3], nxt_bbox[3])
                    j += 1

                merged_el = cur.copy()
                merged_text = " ".join(parts).strip()
                tokens = merged_text.split()
                if len(tokens) > 1:
                    compact: List[str] = []
                    for t in tokens:
                        if not compact or compact[-1] != t:
                            compact.append(t)
                    merged_text = " ".join(compact)
                merged_el["content"] = merged_text
                merged_el["bbox"] = new_bbox
                merged.append(merged_el)
                i = j

            return merged

        elements = _merge_adjacent_titles(elements)

        md_lines: List[str] = []
        in_code_block = False
        
        for el in elements:
            content = el["content"]
            el_type = el["type"]
            metadata = el.get("metadata", {})
            structure_type = metadata.get("structure_type", "normal")

            # 去掉紧邻重复行（常见于标题/页眉重复）
            if md_lines:
                prev = md_lines[-1].strip()
                cur = (content or "").strip()
                if prev and cur and prev == cur:
                    continue
            
            # 1. 标题处理
            if el_type == "title":
                level = metadata.get("level", 1)
                level = max(1, min(6, level))  # 限制在 H1-H6
                content = f"{'#' * level} {content}"
            
            # 2. 代码块处理
            elif el_type == "code":
                if not in_code_block:
                    md_lines.append("```")
                    in_code_block = True
                md_lines.append(content)
                md_lines.append("```")
                in_code_block = False
                continue
            
            # 3. 列表项处理
            elif structure_type == "list_item":
                # 保持原有的列表标记
                pass  # content 已经包含列表标记
            
            # 4. 表格处理（已经是 Markdown 格式）
            elif el_type == "table":
                pass  # content 已经是 Markdown 表格
            
            # 5. 图片处理
            elif el_type == "image":
                content = f"![Image]({content})"
            
            md_lines.append(content)
        
        return "\n\n".join(md_lines)


