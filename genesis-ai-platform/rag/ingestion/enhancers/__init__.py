"""
增强器模块

支持多种增强功能：
- KeywordEnhancer: 关键词提取
- QuestionEnhancer: 问题提取
- SummaryEnhancer: 摘要生成
"""

from .base import BaseEnhancer
from .combined_enhancer import CombinedEnhancer
from .factory import EnhancerFactory
from .keyword_enhancer import KeywordEnhancer
from .question_enhancer import QuestionEnhancer
from .selector import EnhancementDecision, build_enhancer_runtime_config, decide_chunk_enhancement, normalize_enhancement_config
from .summary_enhancer import SummaryEnhancer

__all__ = [
    "BaseEnhancer",
    "CombinedEnhancer",
    "EnhancerFactory",
    "EnhancementDecision",
    "KeywordEnhancer",
    "QuestionEnhancer",
    "SummaryEnhancer",
    "build_enhancer_runtime_config",
    "decide_chunk_enhancement",
    "normalize_enhancement_config",
]
