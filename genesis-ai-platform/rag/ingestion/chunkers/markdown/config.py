"""
Markdown 分块器配置常量
"""

import re


class MarkdownChunkerConfig:
    """Markdown 分块器配置常量"""
    DEFAULT_CHUNK_SIZE = 512
    DEFAULT_OVERLAP_RATIO = 0.15
    DEFAULT_HIERARCHY_THRESHOLD = 4.0
    DEFAULT_ELEMENT_SPLIT_RATIO = 1.5
    MAX_RECURSION_DEPTH = 5
    TOKEN_CACHE_SIZE = 1000
    
    # 优化后的正则表达式（避免灾难性回溯）
    CODE_BLOCK_PATTERN = re.compile(r'```(?:[^`]|`(?!``))*?```', re.DOTALL)
    FORMULA_PATTERN = re.compile(r'\$\$(?:[^\$]|\$(?!\$))*?\$\$', re.DOTALL)
    INLINE_CODE_PATTERN = re.compile(r'`[^`]+`')
    # 修复表格分隔符模式：支持多列（多个 |）
    TABLE_SEPARATOR_PATTERN = re.compile(r'^\s*\|[\s:-]+(\|[\s:-]+)+\|\s*$', re.MULTILINE)
