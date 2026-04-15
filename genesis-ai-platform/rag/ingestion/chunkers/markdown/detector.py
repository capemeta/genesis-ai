"""
Markdown 元素检测器 - 检测代码块、表格、列表、公式等特殊元素
"""

import re
import logging
from typing import List, Dict, Any

from .config import MarkdownChunkerConfig

logger = logging.getLogger(__name__)


class MarkdownElementDetector:
    """Markdown 特殊元素检测器"""
    
    @staticmethod
    def detect_all_elements(text: str) -> List[Dict[str, Any]]:
        """
        检测所有特殊元素（代码块、表格、列表、公式、引用块、HTML块）
        
        使用优化的正则表达式避免灾难性回溯
        
        检测优先级：
        1. 代码块（最高优先级）
        2. 数学公式（块级）
        3. 表格
        4. HTML 块
        5. 引用块
        6. 列表
        
        Returns:
            List[Dict]: 元素列表，每个元素包含 type, start, end, content
        """
        elements: List[Dict[str, Any]] = []
        
        # 1. 检测代码块（使用预编译的优化正则）
        for match in MarkdownChunkerConfig.CODE_BLOCK_PATTERN.finditer(text):
            elements.append({
                'type': 'code',
                'start': match.start(),
                'end': match.end(),
                'content': match.group(0),
            })
        
        # 2. 检测数学公式（块级，使用预编译的优化正则）
        for match in MarkdownChunkerConfig.FORMULA_PATTERN.finditer(text):
            elements.append({
                'type': 'formula',
                'start': match.start(),
                'end': match.end(),
                'content': match.group(0),
            })
        
        # 3. 检测表格（使用改进的方法）
        table_elements = MarkdownElementDetector._detect_tables(text)
        elements.extend(table_elements)
        
        # 4. 检测 HTML 块
        html_elements = MarkdownElementDetector._detect_html_blocks(text)
        elements.extend(html_elements)
        
        # 5. 检测引用块
        blockquote_elements = MarkdownElementDetector._detect_blockquotes(text)
        elements.extend(blockquote_elements)
        
        # 6. 检测列表（连续的列表项）
        list_pattern = re.compile(r'(?:^|\n)((?:[-*+]\s+.+\n?)+)', re.MULTILINE)
        for match in list_pattern.finditer(text):
            elements.append({
                'type': 'list',
                'start': match.start(),
                'end': match.end(),
                'content': match.group(0),
            })
        
        # 按位置排序
        elements.sort(key=lambda element: int(element['start']))
        return elements
    
    @staticmethod
    def _detect_tables(text: str) -> List[Dict[str, Any]]:
        """
        改进的表格检测方法
        
        验证表格格式的完整性，避免误匹配
        """
        tables: List[Dict[str, Any]] = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是表格行（包含 |）
            if '|' in line and line.strip():
                # 检查下一行是否是分隔符
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if MarkdownChunkerConfig.TABLE_SEPARATOR_PATTERN.match(next_line):
                        # 找到表格，收集所有行
                        table_start_line = i
                        table_lines = [lines[i], lines[i + 1]]
                        i += 2
                        
                        # 收集数据行
                        while i < len(lines) and '|' in lines[i] and lines[i].strip():
                            table_lines.append(lines[i])
                            i += 1
                        
                        # 验证表格格式
                        if MarkdownElementDetector._is_valid_table(table_lines):
                            table_content = '\n'.join(table_lines)
                            # 计算在原文中的位置
                            text_before = '\n'.join(lines[:table_start_line])
                            start_pos = len(text_before) + (1 if text_before else 0)
                            
                            tables.append({
                                'type': 'table',
                                'start': start_pos,
                                'end': start_pos + len(table_content),
                                'content': table_content,
                            })
                        continue
            
            i += 1
        
        return tables
    
    @staticmethod
    def _is_valid_table(lines: List[str]) -> bool:
        """
        验证表格格式
        
        检查：
        1. 至少有表头和分隔符
        2. 列数一致
        3. 分隔符格式正确
        """
        if len(lines) < 2:
            return False
        
        # 检查表头
        header_cols = lines[0].count('|')
        if header_cols < 2:  # 至少需要 |col1|col2|
            return False
        
        # 检查分隔符
        separator = lines[1]
        if not MarkdownChunkerConfig.TABLE_SEPARATOR_PATTERN.match(separator):
            return False
        
        separator_cols = separator.count('|')
        if separator_cols != header_cols:
            return False
        
        # 检查数据行（允许列数略有差异，但不能差太多）
        for line in lines[2:]:
            line_cols = line.count('|')
            if abs(line_cols - header_cols) > 1:  # 允许 ±1 的误差
                return False
        
        return True
    
    @staticmethod
    def _detect_html_blocks(text: str) -> List[Dict[str, Any]]:
        """
        检测 HTML 块
        
        策略：
        1. 检测成对的 HTML 标签（<div>...</div>）
        2. 支持嵌套标签
        3. 保持标签的完整性
        """
        html_elements: List[Dict[str, Any]] = []
        
        # 常见的块级 HTML 标签
        block_tags = ['div', 'section', 'article', 'aside', 'header', 'footer', 
                      'nav', 'main', 'figure', 'blockquote', 'pre', 'table', 
                      'ul', 'ol', 'dl']
        
        for tag in block_tags:
            # 匹配开始和结束标签
            pattern = re.compile(
                rf'<{tag}(?:\s+[^>]*)?>.*?</{tag}>',
                re.DOTALL | re.IGNORECASE
            )
            
            for match in pattern.finditer(text):
                html_elements.append({
                    'type': 'html',
                    'start': match.start(),
                    'end': match.end(),
                    'content': match.group(0),
                    'tag': tag,
                })
        
        return html_elements
    
    @staticmethod
    def _detect_blockquotes(text: str) -> List[Dict[str, Any]]:
        """
        检测引用块
        
        格式：
        > 这是一段引用
        > 可能有多行
        """
        blockquotes: List[Dict[str, Any]] = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是引用行
            if line.strip().startswith('>'):
                # 找到引用块的开始
                quote_start_line = i
                quote_lines = [lines[i]]
                i += 1
                
                # 收集连续的引用行（包括空引用行）
                while i < len(lines):
                    current_line = lines[i]
                    if (current_line.strip().startswith('>') or 
                        (current_line.strip() == '' and i + 1 < len(lines) and 
                         lines[i + 1].strip().startswith('>'))):
                        quote_lines.append(current_line)
                        i += 1
                    else:
                        break
                
                # 构建引用块内容
                quote_content = '\n'.join(quote_lines)
                
                # 计算在原文中的位置
                text_before = '\n'.join(lines[:quote_start_line])
                start_pos = len(text_before) + (1 if text_before else 0)
                
                blockquotes.append({
                    'type': 'blockquote',
                    'start': start_pos,
                    'end': start_pos + len(quote_content),
                    'content': quote_content,
                })
                continue
            
            i += 1
        
        return blockquotes
    
    @staticmethod
    def detect_element_type(text: str) -> str:
        """
        检测单个文本段落的元素类型
        
        Returns:
            元素类型：'code', 'table', 'list', 'blockquote', 'formula', 'html', 'paragraph'
        """
        text = text.strip()
        
        if not text:
            return 'paragraph'
        
        # 检查代码块
        if text.startswith('```') and text.endswith('```'):
            return 'code'
        
        # 检查公式块
        if text.startswith('$$') and text.endswith('$$'):
            return 'formula'
        
        # 检查表格
        lines = text.split('\n')
        if len(lines) >= 2 and '|' in lines[0] and '---' in lines[1]:
            return 'table'
        
        # 检查列表
        if re.match(r'^[-*+]\s+', text):
            return 'list'
        
        # 检查引用块
        if text.startswith('>'):
            return 'blockquote'
        
        # 检查 HTML 块
        if text.startswith('<') and '>' in text:
            # 简单检查是否是 HTML 标签
            block_tags = ['div', 'section', 'article', 'aside', 'header', 'footer', 
                          'nav', 'main', 'figure', 'blockquote', 'pre', 'table', 
                          'ul', 'ol', 'dl']
            for tag in block_tags:
                if text.startswith(f'<{tag}'):
                    return 'html'
        
        # 默认是普通段落
        return 'paragraph'
    
    @staticmethod
    def find_broken_elements(text: str, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        查找被截断的元素
        
        如果元素的开始或结束位置在文本边界附近，认为被截断
        """
        broken = []
        text_len = len(text)
        
        for elem in elements:
            # 检查元素是否在文本开头被截断（不完整）
            if elem['start'] == 0 and not MarkdownElementDetector._is_element_complete_at_start(elem, text):
                broken.append(elem)
                continue
            
            # 检查元素是否在文本结尾被截断（不完整）
            if elem['end'] >= text_len - 10 and not MarkdownElementDetector._is_element_complete_at_end(elem, text):
                broken.append(elem)
                continue
        
        return broken
    
    @staticmethod
    def _is_element_complete_at_start(elem: Dict[str, Any], text: str) -> bool:
        """检查元素在文本开头是否完整"""
        if elem['type'] == 'code':
            # 代码块必须以 ``` 开头
            return elem['content'].startswith('```')
        elif elem['type'] == 'table':
            # 表格必须有表头
            lines = elem['content'].split('\n')
            return len(lines) >= 2 and '|' in lines[0] and '---' in lines[1]
        elif elem['type'] == 'formula':
            # 公式必须以 $ 开头
            return elem['content'].startswith('$')
        elif elem['type'] == 'list':
            # 列表必须以 - * + 开头
            return bool(re.match(r'^[-*+]\s+', elem['content'].strip()))
        return True
    
    @staticmethod
    def _is_element_complete_at_end(elem: Dict[str, Any], text: str) -> bool:
        """检查元素在文本结尾是否完整"""
        if elem['type'] == 'code':
            # 代码块必须以 ``` 结尾
            return elem['content'].rstrip().endswith('```')
        elif elem['type'] == 'table':
            # 表格最后一行必须是表格行
            lines = elem['content'].split('\n')
            return len(lines) > 0 and '|' in lines[-1]
        elif elem['type'] == 'formula':
            # 公式必须以 $ 结尾
            return elem['content'].rstrip().endswith('$')
        elif elem['type'] == 'list':
            # 列表最后一行必须是列表项
            lines = elem['content'].strip().split('\n')
            return len(lines) > 0 and bool(re.match(r'^[-*+]\s+', lines[-1]))
        return True
