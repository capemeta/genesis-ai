"""
增强器工厂

管理和创建增强器实例
"""

from typing import Any, Dict, List, Type
from .base import BaseEnhancer
from .combined_enhancer import CombinedEnhancer
from .keyword_enhancer import KeywordEnhancer
from .question_enhancer import QuestionEnhancer
from .summary_enhancer import SummaryEnhancer


class EnhancerFactory:
    """
    增强器工厂
    
    负责：
    1. 注册增强器
    2. 创建增强器实例
    3. 批量创建增强器
    """
    
    _enhancers: Dict[str, Type[BaseEnhancer]] = {
        "keyword": KeywordEnhancer,
        "question": QuestionEnhancer,
        "summary": SummaryEnhancer,
    }
    
    @classmethod
    def create_enhancer(cls, enhancer_type: str, **kwargs) -> BaseEnhancer:
        """
        创建增强器实例
        
        Args:
            enhancer_type: 增强器类型
            **kwargs: 增强器配置参数
        
        Returns:
            BaseEnhancer: 增强器实例
        
        Raises:
            ValueError: 不支持的增强器类型
        """
        enhancer_class = cls._enhancers.get(enhancer_type)
        if not enhancer_class:
            raise ValueError(f"不支持的增强器类型: {enhancer_type}")
        
        return enhancer_class(**kwargs)
    
    @classmethod
    def create_enhancers(cls, config: dict, **runtime_kwargs: Any) -> List[BaseEnhancer]:
        """
        批量创建增强器
        
        Args:
            config: 增强器配置
                {
                    "keyword": {"topn": 5},
                    "question": {"topn": 3},
                    "summary": {"max_length": 100}
                }
        
        Returns:
            List[BaseEnhancer]: 增强器列表
        """
        summary_cfg = dict(config.get("summary") or {})
        keyword_cfg = dict(config.get("keyword") or {})
        question_cfg = dict(config.get("question") or {})

        enable_summary = bool(summary_cfg)
        enable_keywords = bool(keyword_cfg)
        enable_questions = bool(question_cfg)

        if any([enable_summary, enable_keywords, enable_questions]):
            return [
                CombinedEnhancer(
                    enable_summary=enable_summary,
                    enable_keywords=enable_keywords,
                    enable_questions=enable_questions,
                    summary_max_length=int(summary_cfg.get("max_length", 100) or 100),
                    keyword_topn=int(keyword_cfg.get("topn", 5) or 5),
                    question_topn=int(question_cfg.get("topn", 3) or 3),
                    **runtime_kwargs,
                )
            ]

        return []
    
    @classmethod
    def register_enhancer(cls, enhancer_type: str, enhancer_class: Type[BaseEnhancer]) -> None:
        """
        注册自定义增强器
        
        Args:
            enhancer_type: 增强器类型
            enhancer_class: 增强器类
        """
        cls._enhancers[enhancer_type] = enhancer_class
        print(f"[EnhancerFactory] 注册增强器: {enhancer_type} -> {enhancer_class.__name__}")
