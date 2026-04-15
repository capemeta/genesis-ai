"""
文档复杂度检测器
"""

import re
import logging

logger = logging.getLogger(__name__)


class ComplexityDetector:
    """文档复杂度检测器"""
    
    def __init__(self, complexity_threshold: int = 4000):
        self.complexity_threshold = complexity_threshold
        
        # 结构探测模式
        self.structure_patterns = [
            r"^\d\.",           # 1. 2. 3.
            r"^第.*[章节级]",    # 第一章, 第一节
            r"^[一二三四五六七八九十]+\.", # 一. 二.
            r"^\([1-9]\)",      # (1) (2)
        ]
    
    def is_complex(self, text: str) -> bool:
        """
        判断文档是否复杂
        依据：长度、段落密度、标题/列表序号
        """
        # 长度判定
        if len(text) > self.complexity_threshold:
            return True
            
        # 结构探测：是否有明显的章节或列表序号
        pattern_count = 0
        for p in self.structure_patterns:
            pattern_count += len(re.findall(p, text, re.MULTILINE))
            
        if pattern_count > 5:
            return True
            
        return False
