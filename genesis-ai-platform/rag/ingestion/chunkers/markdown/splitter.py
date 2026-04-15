"""
Markdown 元素拆分器 - 负责拆分超大元素（表格、代码、列表等）
"""

import logging
import re
from typing import List, Dict, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class MarkdownElementSplitter:
    """Markdown 元素拆分器"""
    
    def __init__(self, chunk_size: int, embedding_model_limit: int, count_tokens_fn):
        self.chunk_size = chunk_size
        self.embedding_model_limit = embedding_model_limit
        self.count_tokens = count_tokens_fn
    
    def split_large_element(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        拆分超大元素（table_1, table_2, ...）
        
        每个子块保留表头/上下文
        """
        elem_type = element['type']
        
        if elem_type == 'table':
            return self.split_table(element, section, metadata)
        elif elem_type == 'code':
            return self.split_code(element, section, metadata)
        elif elem_type == 'list':
            return self.split_list(element, section, metadata)
        elif elem_type == 'blockquote':
            return self.split_blockquote(element, section, metadata)
        elif elem_type == 'html':
            return self.split_html(element, section, metadata)
        else:
            # 其他类型：简单按行拆分
            return self.split_by_lines(element, section, metadata)
    
    def split_table(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        拆分表格，每个子块保留表头
        
        核心原则：
        1. 绝对不能超过 embedding_model_limit（硬性要求）
        2. 在不超限的前提下，尽可能保持表格的完整性
        
        格式：
        table_1: 完整标题路径 + 表头 + 前 N 行
        table_2: 完整标题路径（续）+ 表头 + 中间 N 行
        table_3: 完整标题路径（续）+ 表头 + 最后 N 行
        
        特殊处理：
        - 如果"标题路径 + 表头"本身就超限，按列拆分
        - 如果单行数据超限，截断该行
        """
        content = element['content']
        lines = content.split('\n')
        
        # 提取表头（前两行）
        if len(lines) < 2:
            return [self._create_element_chunk(element, section, metadata, is_split=False)]
        
        header_line = lines[0]
        separator_line = lines[1]
        data_lines = lines[2:]
        
        # 计算表头大小
        header_text = f"{header_line}\n{separator_line}"
        header_tokens = self.count_tokens(header_text)
        
        # 获取完整的标题路径（用于向量化）
        header_path = section.get("header_path", "")
        header_path_tokens = self.count_tokens(header_path) if header_path else 0
        
        # 检查"完整标题路径 + 表头"是否超过嵌入模型限制
        base_tokens = header_path_tokens + header_tokens
        
        if base_tokens >= self.embedding_model_limit:
            logger.warning(
                f"[MarkdownElementSplitter] 完整标题路径 + 表头超过嵌入模型限制 "
                f"({base_tokens} >= {self.embedding_model_limit})，"
                f"将按列拆分表格"
            )
            return self.split_wide_table(element, section, metadata)
        
        # 可用空间 = embedding_model_limit - 完整标题路径 - 表头 - 安全余量
        available_tokens = self.embedding_model_limit - base_tokens - 20
        
        if available_tokens <= 0:
            logger.error(
                f"[MarkdownElementSplitter] 标题路径和表头占用了所有空间，"
                f"无法添加数据行！将尝试按列拆分"
            )
            return self.split_wide_table(element, section, metadata)
        
        # 逐行检查并分组
        sub_tables: List[Dict[str, Any]] = []
        current_chunk_rows: List[str] = []
        current_chunk_tokens = 0
        
        for row in data_lines:
            row_tokens = self.count_tokens(row)
            
            # 检查单行是否超过可用空间
            if row_tokens > available_tokens:
                logger.warning(
                    f"[MarkdownElementSplitter] 单行表格数据超过嵌入模型限制！"
                    f"row_tokens={row_tokens}, available_tokens={available_tokens}"
                )
                
                # 先保存当前累积的块
                if current_chunk_rows:
                    sub_tables.append(self._create_table_chunk(
                        header_line,
                        separator_line,
                        current_chunk_rows,
                        section,
                        metadata,
                        len(sub_tables) + 1,
                        str(uuid4())
                    ))
                    current_chunk_rows = []
                    current_chunk_tokens = 0
                
                # 单行超限，说明这一行的列太多或内容太长
                # 应该按列拆分表格，而不是截断
                logger.warning(
                    f"[MarkdownElementSplitter] 单行表格数据超限，"
                    f"建议使用 split_wide_table 按列拆分"
                )
                # 跳过这一行（或者可以选择按列拆分整个表格）
                continue
            
            # 检查添加这一行后是否会超限
            if current_chunk_tokens + row_tokens > available_tokens:
                # 会超限，先保存当前块
                if current_chunk_rows:
                    sub_tables.append(self._create_table_chunk(
                        header_line,
                        separator_line,
                        current_chunk_rows,
                        section,
                        metadata,
                        len(sub_tables) + 1,
                        str(uuid4())
                    ))
                
                # 开始新块
                current_chunk_rows = [row]
                current_chunk_tokens = row_tokens
            else:
                # 不会超限，添加到当前块
                current_chunk_rows.append(row)
                current_chunk_tokens += row_tokens
        
        # 保存最后一块
        if current_chunk_rows:
            sub_tables.append(self._create_table_chunk(
                header_line,
                separator_line,
                current_chunk_rows,
                section,
                metadata,
                len(sub_tables) + 1,
                str(uuid4())
            ))
        
        # 更新 split_total
        total_parts = len(sub_tables)
        for sub_table in sub_tables:
            sub_table["metadata"]["split_total"] = total_parts
        
        logger.debug(
            f"[MarkdownElementSplitter] 表格拆分完成: "
            f"embedding_model_limit={self.embedding_model_limit}, "
            f"base_tokens={base_tokens}, "
            f"available_tokens={available_tokens}, "
            f"total_rows={len(data_lines)}, "
            f"total_chunks={total_parts}"
        )
        
        return sub_tables
    
    def _create_table_chunk(
        self,
        header_line: str,
        separator_line: str,
        data_rows: List[str],
        section: Dict[str, Any],
        metadata: Dict[str, Any],
        part_num: int,
        original_element_id: str
    ) -> Dict[str, Any]:
        """创建表格块"""
        section_heading = section.get("heading", "")
        
        # 构建完整的子表格内容（包含章节标题）
        if section_heading:
            # 如果有章节标题，添加到表格前面
            heading_suffix = f"（第 {part_num} 部分）" if part_num > 1 else ""
            full_heading = f"{section_heading}{heading_suffix}"
            
            # 根据章节级别添加对应数量的 #
            level = section.get("level", 2)
            heading_prefix = "#" * level
            
            sub_table_content = f"{heading_prefix} {full_heading}\n\n{header_line}\n{separator_line}\n" + '\n'.join(data_rows)
        else:
            # 没有章节标题，直接使用表格
            sub_table_content = f"{header_line}\n{separator_line}\n" + '\n'.join(data_rows)
        
        # 计算 token 数
        content_tokens = self.count_tokens(sub_table_content)
        header_path = section.get("header_path", "")
        header_path_tokens = self.count_tokens(header_path) if header_path else 0
        total_tokens = header_path_tokens + content_tokens
        
        return {
            "text": sub_table_content,
            "metadata": {
                **metadata,
                "node_id": str(uuid4()),  # 添加 node_id
                "parent_id": None,
                "child_ids": [],
                "chunk_strategy": "markdown",
                "chunk_type": "table",
                "heading": section.get("heading", ""),
                "header_path": header_path,
                "level": 2,  # 子块是原子级别
                "token_count": content_tokens,
                "total_tokens": total_tokens,
                "is_split": True,
                "split_part": part_num,
                "split_total": None,  # 稍后更新
                "element_type": "table",
                "has_table": True,
                "original_element_id": original_element_id,  # 用于检索后合并
                "is_smart": True,
                "is_hierarchical": False,
                "is_pruned": False,
            },
            "type": "text"
        }
    
    def split_wide_table(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        处理超宽表格（列数太多，表头本身就超限）
        
        策略：
        1. 保留第一列作为索引列
        2. 按列拆分：索引列 + 部分数据列
        3. 每个子块都是完整的表格
        """
        content = element['content']
        lines = content.split('\n')
        
        if len(lines) < 2:
            return [self._create_element_chunk(element, section, metadata, is_split=False)]
        
        header_line = lines[0]
        separator_line = lines[1]
        data_lines = lines[2:]
        
        # 解析表格列
        header_cols = [col.strip() for col in header_line.split('|')[1:-1]]
        
        if len(header_cols) < 2:
            # 列数太少，无法拆分
            return [self._create_element_chunk(element, section, metadata, is_split=False)]
        
        # 计算索引列（第一列）的 token 数
        index_col_text = f"| {header_cols[0]} |\n|---|\n"
        index_tokens = self.count_tokens(index_col_text)
        
        # 计算每个子块可容纳的列数
        available_tokens = self.embedding_model_limit - index_tokens - 100  # 留余量
        
        # 估算每列平均 token 数
        remaining_cols = header_cols[1:]
        if remaining_cols:
            avg_col_tokens = (self.count_tokens(header_line) - index_tokens) / len(remaining_cols)
            cols_per_chunk = max(1, int(available_tokens / avg_col_tokens))
        else:
            cols_per_chunk = 1
        
        # 按列拆分
        sub_tables: List[Dict[str, Any]] = []
        for i in range(1, len(header_cols), cols_per_chunk):
            # 选择列索引：第一列 + 当前批次的列
            chunk_col_indices = [0] + list(range(i, min(i + cols_per_chunk, len(header_cols))))
            
            # 构建子表格表头
            chunk_header_cols = [header_cols[idx] for idx in chunk_col_indices]
            chunk_header = '| ' + ' | '.join(chunk_header_cols) + ' |'
            chunk_separator = '|' + '|'.join(['---'] * len(chunk_header_cols)) + '|'
            
            # 构建子表格数据行
            chunk_data_lines = []
            for data_line in data_lines:
                data_cols = [col.strip() for col in data_line.split('|')[1:-1]]
                # 提取对应列的数据
                chunk_data_cols = []
                for idx in chunk_col_indices:
                    if idx < len(data_cols):
                        chunk_data_cols.append(data_cols[idx])
                    else:
                        chunk_data_cols.append('')  # 缺失的列用空字符串填充
                chunk_data_lines.append('| ' + ' | '.join(chunk_data_cols) + ' |')
            
            # 组装子表格
            sub_table_content = '\n'.join([chunk_header, chunk_separator] + chunk_data_lines)
            content_tokens = self.count_tokens(sub_table_content)
            header_path = section.get("header_path", "")
            header_path_tokens = self.count_tokens(header_path) if header_path else 0
            total_tokens = header_path_tokens + content_tokens
            
            part_num = len(sub_tables) + 1
            col_range = f"{i}-{min(i + cols_per_chunk - 1, len(header_cols) - 1)}"
            
            sub_tables.append({
                "text": sub_table_content,
                "metadata": {
                    **metadata,
                    "node_id": str(uuid4()),  # 添加 node_id
                    "parent_id": None,
                    "child_ids": [],
                    "chunk_strategy": "markdown",
                    "chunk_type": "table",
                    "heading": section.get("heading", "") + f"（列 {col_range}）",
                    "header_path": header_path,
                    "level": 2,  # 子块是原子级别
                    "token_count": content_tokens,
                    "total_tokens": total_tokens,
                    "is_split": True,
                    "split_part": part_num,
                    "split_total": None,
                    "split_by": "columns",
                    "original_cols": len(header_cols),
                    "chunk_cols": len(chunk_header_cols),
                    "element_type": "table",
                    "has_table": True,
                    "is_smart": True,
                    "is_hierarchical": False,
                    "is_pruned": False,
                },
                "type": "text"
            })
        
        # 更新 split_total
        total_parts = len(sub_tables)
        for sub_table in sub_tables:
            metadata_dict = sub_table.get("metadata")
            if isinstance(metadata_dict, dict):
                metadata_dict["split_total"] = total_parts
        
        return sub_tables
    
    def split_code(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        拆分代码块，每个子块保留语言标记和上下文注释
        
        格式：
        ## 标题（第 N 部分）
        
        ```python
        # 文件：xxx.py
        代码内容
        ```
        
        判断是否超限时，使用"完整标题路径 + 代码块"的格式
        """
        content = element['content']
        
        # 提取语言标记
        first_line = content.split('\n')[0]
        language = first_line.replace('```', '').strip()
        
        # 提取代码内容（去掉 ``` 标记）
        code_lines = content.split('\n')[1:-1]  # 去掉首尾的 ```
        
        # 获取完整的标题路径
        header_path = section.get("header_path", "")
        header_path_tokens = self.count_tokens(header_path) if header_path else 0
        
        # 计算代码块标记的 token
        code_marker_tokens = self.count_tokens(f"```{language}\n```")
        
        # 计算每个子块可以容纳多少行
        # 可用空间 = embedding_model_limit - 完整标题路径 - 代码块标记 - 安全余量
        available_tokens = self.embedding_model_limit - header_path_tokens - code_marker_tokens - 20
        
        if available_tokens <= 0:
            logger.warning(
                f"[MarkdownElementSplitter] 完整标题路径占用过多空间，"
                f"代码块只能容纳少量行"
            )
            lines_per_chunk = 5
        elif code_lines:
            avg_line_tokens = self.count_tokens('\n'.join(code_lines)) / len(code_lines)
            lines_per_chunk = max(5, int(available_tokens / avg_line_tokens)) if avg_line_tokens > 0 else len(code_lines)
        else:
            lines_per_chunk = 5
        
        # 拆分代码
        sub_codes: List[Dict[str, Any]] = []
        section_heading = section.get("heading", "")
        
        for i in range(0, len(code_lines), lines_per_chunk):
            chunk_lines = code_lines[i:i + lines_per_chunk]
            
            part_num = len(sub_codes) + 1
            
            # 添加上下文注释
            if part_num > 1:
                chunk_lines.insert(0, f"# ... 接上文")
            
            # 构建子代码块
            code_block = f"```{language}\n" + '\n'.join(chunk_lines) + "\n```"
            
            # 如果有章节标题，添加到代码块前面
            if section_heading:
                heading_suffix = f"（第 {part_num} 部分）" if part_num > 1 else ""
                full_heading = f"{section_heading}{heading_suffix}"
                
                level = section.get("level", 2)
                heading_prefix = "#" * level
                
                sub_code_content = f"{heading_prefix} {full_heading}\n\n{code_block}"
            else:
                sub_code_content = code_block
            
            content_tokens = self.count_tokens(sub_code_content)
            total_tokens = header_path_tokens + content_tokens
            
            sub_codes.append({
                "text": sub_code_content,
                "metadata": {
                    **metadata,
                    "node_id": str(uuid4()),  # 添加 node_id
                    "parent_id": None,
                    "child_ids": [],
                    "chunk_strategy": "markdown",
                    "chunk_type": "code",
                    "heading": section.get("heading", ""),
                    "header_path": header_path,
                    "level": 2,  # 子块是原子级别
                    "token_count": content_tokens,
                    "total_tokens": total_tokens,
                    "is_split": True,
                    "split_part": part_num,
                    "split_total": None,
                    "element_type": "code",
                    "language": language,
                    "has_code": True,
                    "is_smart": True,
                    "is_hierarchical": False,
                    "is_pruned": False,
                },
                "type": "text"
            })
        
        # 更新 split_total
        total_parts = len(sub_codes)
        for sub_code in sub_codes:
            metadata_dict = sub_code.get("metadata")
            if isinstance(metadata_dict, dict):
                metadata_dict["split_total"] = total_parts
        
        return sub_codes
    
    def split_list(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        拆分列表，按逻辑分组
        
        核心原则：
        1. 绝对不能超过 embedding_model_limit（硬性要求）
        2. 在不超限的前提下，尽可能保持列表项的完整性
        
        判断是否超限时，使用"完整标题路径 + 列表内容"的格式
        """
        content = element['content']
        items = self._split_list_items(content)

        if not items:
            return []
        
        # 获取完整的标题路径
        header_path = section.get("header_path", "")
        header_path_tokens = self.count_tokens(header_path) if header_path else 0
        
        # 可用空间 = embedding_model_limit - 完整标题路径 - 安全余量
        available_tokens = self.embedding_model_limit - header_path_tokens - 20
        
        if available_tokens <= 0:
            logger.error(
                f"[MarkdownElementSplitter] 完整标题路径本身就超过嵌入模型限制！"
                f"header_path_tokens={header_path_tokens}, "
                f"embedding_model_limit={self.embedding_model_limit}"
            )
            # 即使标题路径超限，也要尝试保存列表内容（截断标题路径）
            available_tokens = self.embedding_model_limit - 50
        
        # 逐项检查并分组
        sub_lists: List[Dict[str, Any]] = []
        current_chunk_lines: List[str] = []
        current_chunk_tokens = 0
        
        for item_text in items:
            line_tokens = self.count_tokens(item_text)
            
            # 检查单个列表项是否超过可用空间
            if line_tokens > available_tokens:
                # 单个列表项就超限了，需要特殊处理
                logger.warning(
                    f"[MarkdownElementSplitter] 单个列表项超过嵌入模型限制！"
                    f"line_tokens={line_tokens}, available_tokens={available_tokens}"
                )
                
                # 先保存当前累积的块
                if current_chunk_lines:
                    sub_lists.append(self._create_list_chunk(
                        current_chunk_lines,
                        section,
                        metadata,
                        len(sub_lists) + 1
                    ))
                    current_chunk_lines = []
                    current_chunk_tokens = 0
                
                # 单个列表项超限，说明这个列表项内容太长
                # 应该按行拆分这个列表项，而不是截断
                logger.warning(
                    f"[MarkdownElementSplitter] 单个列表项超限，"
                    f"将按行拆分该列表项"
                )
                # 按行拆分这个列表项
                item_lines = item_text.split('\n')
                if len(item_lines) > 1:
                    # 多行列表项，按行拆分
                    for item_line in item_lines:
                        item_line_tokens = self.count_tokens(item_line)
                        if item_line_tokens <= available_tokens:
                            sub_lists.append(self._create_list_chunk(
                                [item_line],
                                section,
                                metadata,
                                len(sub_lists) + 1
                            ))
                        else:
                            # 单行仍然超限，跳过（或记录警告）
                            logger.error(
                                f"[MarkdownElementSplitter] 单行列表项仍然超限，跳过: "
                                f"line_tokens={item_line_tokens}, available_tokens={available_tokens}"
                            )
                else:
                    # 单行列表项超限，跳过（或记录警告）
                    logger.error(
                        f"[MarkdownElementSplitter] 单行列表项超限，跳过: "
                        f"line_tokens={line_tokens}, available_tokens={available_tokens}"
                    )
                continue
            
            # 检查添加这一项后是否会超限
            if current_chunk_tokens + line_tokens > available_tokens:
                # 会超限，先保存当前块
                if current_chunk_lines:
                    sub_lists.append(self._create_list_chunk(
                        current_chunk_lines,
                        section,
                        metadata,
                        len(sub_lists) + 1
                    ))
                
                # 开始新块
                current_chunk_lines = [item_text]
                current_chunk_tokens = line_tokens
            else:
                # 不会超限，添加到当前块
                current_chunk_lines.append(item_text)
                current_chunk_tokens += line_tokens
        
        # 保存最后一块
        if current_chunk_lines:
            sub_lists.append(self._create_list_chunk(
                current_chunk_lines,
                section,
                metadata,
                len(sub_lists) + 1
            ))
        
        # 更新 split_total
        total_parts = len(sub_lists)
        for sub_list in sub_lists:
            metadata_dict = sub_list.get("metadata")
            if isinstance(metadata_dict, dict):
                metadata_dict["split_total"] = total_parts
        
        logger.debug(
                f"[MarkdownElementSplitter] 列表拆分完成: "
                f"embedding_model_limit={self.embedding_model_limit}, "
                f"header_path_tokens={header_path_tokens}, "
                f"available_tokens={available_tokens}, "
                f"total_items={len(items)}, "
                f"total_chunks={total_parts}"
            )
        
        return sub_lists
    
    def _create_list_chunk(
        self,
        lines: List[str],
        section: Dict[str, Any],
        metadata: Dict[str, Any],
        part_num: int
    ) -> Dict[str, Any]:
        """创建列表块"""
        list_content = '\n'.join(lines)
        content_tokens = self.count_tokens(list_content)
        header_path = section.get("header_path", "")
        header_path_tokens = self.count_tokens(header_path) if header_path else 0
        total_tokens = header_path_tokens + content_tokens
        
        return {
            "text": list_content,
            "metadata": {
                **metadata,
                "node_id": str(uuid4()),  # 添加 node_id
                "parent_id": None,
                "child_ids": [],
                "chunk_strategy": "markdown",
                "chunk_type": "list",
                "heading": section.get("heading", ""),
                "header_path": header_path,
                "level": 2,  # 子块是原子级别
                "token_count": content_tokens,
                "total_tokens": total_tokens,
                "is_split": True,
                "split_part": part_num,
                "split_total": None,  # 稍后更新
                "element_type": "list",
                "is_smart": True,
                "is_hierarchical": False,
                "is_pruned": False,
            },
            "type": "text"
        }

    def _split_list_items(self, content: str) -> List[str]:
        """按列表项边界切分，避免把同一条目里的换行误拆成多个独立项。"""
        lines = [line.rstrip() for line in str(content or "").strip().split('\n')]
        if not lines:
            return []

        item_start_re = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|[A-Za-z][.)]\s+)")
        items: List[str] = []
        current: List[str] = []

        for line in lines:
            if not line.strip():
                if current:
                    current.append(line)
                continue

            if item_start_re.match(line):
                if current:
                    items.append('\n'.join(current).strip())
                current = [line]
                continue

            if current:
                # 当前行没有新的列表标记时，视为上一条列表项的续行。
                current.append(line)
            else:
                current = [line]

        if current:
            items.append('\n'.join(current).strip())

        return [item for item in items if item]
    
    def _truncate_text_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        将文本截断到指定的 token 数
        
        使用二分查找来快速找到合适的截断点
        """
        if self.count_tokens(text) <= max_tokens:
            return text
        
        # 二分查找截断点
        left, right = 0, len(text)
        result = ""
        
        while left < right:
            mid = (left + right + 1) // 2
            truncated = text[:mid]
            
            if self.count_tokens(truncated) <= max_tokens:
                result = truncated
                left = mid
            else:
                right = mid - 1
        
        return result
    
    def split_blockquote(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        拆分引用块，保留 > 标记
        
        格式：
        > 引用内容第一部分
        
        > 引用内容第二部分（续）
        
        判断是否超限时，使用"完整标题路径 + 引用内容"的格式
        """
        content = element['content']
        lines = content.split('\n')
        
        # 获取完整的标题路径
        header_path = section.get("header_path", "")
        header_path_tokens = self.count_tokens(header_path) if header_path else 0
        
        # 计算每个子块可以容纳多少行
        # 可用空间 = embedding_model_limit - 完整标题路径 - 安全余量
        available_tokens = self.embedding_model_limit - header_path_tokens - 20
        
        if available_tokens <= 0:
            logger.warning(
                f"[MarkdownElementSplitter] 完整标题路径占用过多空间，"
                f"引用块只能容纳少量行"
            )
            lines_per_chunk = 3
        elif lines:
            avg_line_tokens = self.count_tokens(content) / len(lines)
            lines_per_chunk = max(3, int(available_tokens / avg_line_tokens)) if avg_line_tokens > 0 else len(lines)
        else:
            lines_per_chunk = 3
        
        # 拆分引用块
        sub_quotes: List[Dict[str, Any]] = []
        for i in range(0, len(lines), lines_per_chunk):
            chunk_lines = lines[i:i + lines_per_chunk]
            
            part_num = len(sub_quotes) + 1
            heading_suffix = f"（第 {part_num} 部分）" if part_num > 1 else ""
            
            sub_quote_content = '\n'.join(chunk_lines)
            content_tokens = self.count_tokens(sub_quote_content)
            header_path = section.get("header_path", "")
            header_path_tokens = self.count_tokens(header_path) if header_path else 0
            total_tokens = header_path_tokens + content_tokens
            
            sub_quotes.append({
                "text": sub_quote_content,
                "metadata": {
                    **metadata,
                    "node_id": str(uuid4()),  # 添加 node_id
                    "parent_id": None,
                    "child_ids": [],
                    "chunk_strategy": "markdown",
                    "chunk_type": "blockquote",
                    "heading": section.get("heading", "") + heading_suffix,
                    "header_path": header_path,
                    "level": 2,  # 子块是原子级别
                    "token_count": content_tokens,
                    "total_tokens": total_tokens,
                    "is_split": True,
                    "split_part": part_num,
                    "split_total": None,
                    "element_type": "blockquote",
                    "is_smart": True,
                    "is_hierarchical": False,
                    "is_pruned": False,
                },
                "type": "text"
            })
        
        # 更新 split_total
        total_parts = len(sub_quotes)
        for sub_quote in sub_quotes:
            metadata_dict = sub_quote.get("metadata")
            if isinstance(metadata_dict, dict):
                metadata_dict["split_total"] = total_parts
        
        return sub_quotes
    
    def split_html(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        拆分 HTML 块
        
        策略：
        1. 如果可以按内部标签拆分，则拆分
        2. 否则按行拆分，保留外层标签
        """
        content = element['content']
        tag = element.get('tag', 'div')
        
        # 简单策略：按行拆分，保留外层标签
        lines = content.split('\n')
        
        if len(lines) <= 2:
            # 太短，不拆分
            return [self._create_element_chunk(element, section, metadata, is_split=False)]
        
        # 提取开始和结束标签
        start_tag_line = lines[0]
        end_tag_line = lines[-1]
        content_lines = lines[1:-1]
        
        # 计算每个子块可以容纳多少行
        tag_tokens = self.count_tokens(start_tag_line + '\n' + end_tag_line)
        available_tokens = self.chunk_size - tag_tokens - 50
        
        if content_lines:
            avg_line_tokens = self.count_tokens('\n'.join(content_lines)) / len(content_lines)
            lines_per_chunk = max(3, int(available_tokens / avg_line_tokens)) if avg_line_tokens > 0 else len(content_lines)
        else:
            lines_per_chunk = 3
        
        # 拆分内容
        sub_htmls: List[Dict[str, Any]] = []
        for i in range(0, len(content_lines), lines_per_chunk):
            chunk_lines = content_lines[i:i + lines_per_chunk]
            
            part_num = len(sub_htmls) + 1
            heading_suffix = f"（第 {part_num} 部分）" if part_num > 1 else ""
            
            # 重新组装 HTML
            sub_html_content = start_tag_line + '\n' + '\n'.join(chunk_lines) + '\n' + end_tag_line
            content_tokens = self.count_tokens(sub_html_content)
            header_path = section.get("header_path", "")
            header_path_tokens = self.count_tokens(header_path) if header_path else 0
            total_tokens = header_path_tokens + content_tokens
            
            sub_htmls.append({
                "text": sub_html_content,
                "metadata": {
                    **metadata,
                    "node_id": str(uuid4()),  # 添加 node_id
                    "parent_id": None,
                    "child_ids": [],
                    "chunk_strategy": "markdown",
                    "chunk_type": "html",
                    "heading": section.get("heading", "") + heading_suffix,
                    "header_path": header_path,
                    "level": 2,  # 子块是原子级别
                    "token_count": content_tokens,
                    "total_tokens": total_tokens,
                    "is_split": True,
                    "split_part": part_num,
                    "split_total": None,
                    "element_type": "html",
                    "html_tag": tag,
                    "is_smart": True,
                    "is_hierarchical": False,
                    "is_pruned": False,
                },
                "type": "text"
            })
        
        # 更新 split_total
        total_parts = len(sub_htmls)
        for sub_html in sub_htmls:
            metadata_dict = sub_html.get("metadata")
            if isinstance(metadata_dict, dict):
                metadata_dict["split_total"] = total_parts
        
        return sub_htmls
    
    def split_by_lines(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """通用的按行拆分"""
        content = element['content']
        lines = content.split('\n')
        
        available_tokens = self.chunk_size - 50
        if lines:
            avg_line_tokens = self.count_tokens(content) / len(lines)
            lines_per_chunk = max(5, int(available_tokens / avg_line_tokens)) if avg_line_tokens > 0 else len(lines)
        else:
            lines_per_chunk = 5
        
        sub_chunks: List[Dict[str, Any]] = []
        for i in range(0, len(lines), lines_per_chunk):
            chunk_lines = lines[i:i + lines_per_chunk]
            sub_content = '\n'.join(chunk_lines)
            content_tokens = self.count_tokens(sub_content)
            header_path = section.get("header_path", "")
            header_path_tokens = self.count_tokens(header_path) if header_path else 0
            total_tokens = header_path_tokens + content_tokens
            
            sub_chunks.append({
                "text": sub_content,
                "metadata": {
                    **metadata,
                    "node_id": str(uuid4()),  # 添加 node_id
                    "parent_id": None,
                    "child_ids": [],
                    "chunk_strategy": "markdown",
                    "chunk_type": element['type'],
                    "heading": section.get("heading", ""),
                    "header_path": header_path,
                    "level": 2,  # 子块是原子级别
                    "token_count": content_tokens,
                    "total_tokens": total_tokens,
                    "is_split": True,
                    "split_part": len(sub_chunks) + 1,
                    "split_total": None,
                    "element_type": element['type'],
                    "is_smart": True,
                    "is_hierarchical": False,
                    "is_pruned": False,
                },
                "type": "text"
            })
        
        total_parts = len(sub_chunks)
        for sub_chunk in sub_chunks:
            metadata_dict = sub_chunk.get("metadata")
            if isinstance(metadata_dict, dict):
                metadata_dict["split_total"] = total_parts
        
        return sub_chunks
    
    def _create_element_chunk(
        self,
        element: Dict[str, Any],
        section: Dict[str, Any],
        metadata: Dict[str, Any],
        is_split: bool = False
    ) -> Dict[str, Any]:
        """创建元素块字典"""
        elem_type = element['type']
        
        # 提取语言（代码块）
        language = ""
        if elem_type == "code":
            first_line = element['content'].split('\n')[0]
            language = first_line.replace('```', '').strip()
        
        content_tokens = self.count_tokens(element['content'])
        header_path = section.get("header_path", "")
        header_path_tokens = self.count_tokens(header_path) if header_path else 0
        total_tokens = header_path_tokens + content_tokens
        
        return {
            "text": element['content'],
            "metadata": {
                **metadata,
                "node_id": str(uuid4()),  # 添加 node_id
                "parent_id": None,
                "child_ids": [],
                "chunk_strategy": "markdown",
                "chunk_type": elem_type,
                "heading": section.get("heading", ""),
                "header_path": header_path,
                "level": 2,  # 子块是原子级别
                "token_count": content_tokens,
                "total_tokens": total_tokens,
                "is_split": is_split,
                "element_type": elem_type,
                "language": language if language else None,
                f"has_{elem_type}": True,
                "is_smart": True,
                "is_hierarchical": False,
                "is_pruned": False,
            },
            "type": "text"
        }
