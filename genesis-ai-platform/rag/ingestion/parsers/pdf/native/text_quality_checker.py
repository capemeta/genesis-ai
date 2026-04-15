"""
文本质量检测器

用于判断 PDF 文本层质量，决定是否需要 OCR 增强
"""

import re
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class TextQualityChecker:
    """
    文本质量检测器
    
    检测策略：
    1. 文本长度检测（过短 → 可能是扫描版）
    2. 乱码检测（大量特殊字符 → 编码问题）
    3. 连贯性检测（文本顺序混乱 → 排版问题）
    4. 字符密度检测（字符间距异常 → 提取质量差）
    """
    
    # 阈值配置
    MIN_TEXT_LENGTH_PER_PAGE = 50  # 每页最少字符数
    MAX_GARBLED_RATIO = 0.1  # 最大乱码比例（10%）
    MIN_READABLE_RATIO = 0.35  # 中英数字可读字符最小比例
    
    # 乱码字符模式
    GARBLED_PATTERNS = [
        r'�',  # 替换字符
        r'□',  # 空白框
        r'\ufffd',  # Unicode 替换字符
        r'[\x00-\x08\x0b-\x0c\x0e-\x1f]',  # 控制字符
    ]
    
    @classmethod
    def check_page_quality(
        cls,
        text: str,
        page_width: float,
        page_height: float,
        char_count: int = 0
    ) -> Tuple[bool, str]:
        """
        检查单页文本质量
        
        Args:
            text: 提取的文本
            page_width: 页面宽度
            page_height: 页面高度
            char_count: 字符数量（可选，用于密度检测）
        
        Returns:
            (is_good_quality, reason): (质量是否良好, 原因说明)
        """
        text_stripped = text.strip()
        
        # 1. 长度检测
        if len(text_stripped) < cls.MIN_TEXT_LENGTH_PER_PAGE:
            return False, f"文本过短（{len(text_stripped)} < {cls.MIN_TEXT_LENGTH_PER_PAGE}），可能是扫描版"
        
        # 2. 乱码检测
        garbled_count = 0
        for pattern in cls.GARBLED_PATTERNS:
            garbled_count += len(re.findall(pattern, text))
        
        garbled_ratio = garbled_count / len(text) if len(text) > 0 else 0
        if garbled_ratio > cls.MAX_GARBLED_RATIO:
            return False, f"乱码比例过高（{garbled_ratio:.1%} > {cls.MAX_GARBLED_RATIO:.1%}）"
        
        # 3. 可读字符比例检测（中英数字统一）
        # 避免“中文比例”误杀中英混排技术文档。
        text_no_ws = re.sub(r"\s+", "", text)
        if len(text_no_ws) > 0:
            readable_chars = re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', text_no_ws)
            readable_ratio = len(readable_chars) / len(text_no_ws)
            if readable_ratio < cls.MIN_READABLE_RATIO:
                return False, f"可读字符比例过低（{readable_ratio:.1%} < {cls.MIN_READABLE_RATIO:.1%}），可能提取质量差"
        
        # 4. 字符密度检测（可选）
        if char_count > 0:
            page_area = page_width * page_height
            char_density = char_count / page_area if page_area > 0 else 0
            
            # 密度过低 → 可能是扫描版或提取不完整
            if char_density < 0.01:
                return False, f"字符密度过低（{char_density:.4f} < 0.01），可能提取不完整"
        
        # 5. 连贯性检测（简单版：检查是否有正常的句子结构）
        # 中文：检查是否有标点符号
        # 英文：检查是否有空格分隔的单词
        has_chinese_punctuation = bool(re.search(r'[，。！？；：、]', text))
        has_english_words = bool(re.search(r'\b[a-zA-Z]{2,}\b', text))
        
        if not has_chinese_punctuation and not has_english_words:
            return False, "缺少正常的句子结构（无标点或单词），可能是提取错误"
        
        # 通过所有检测
        return True, "文本质量良好"
    
    @classmethod
    def check_document_quality(
        cls,
        pages_text: list[str],
        sample_size: int = 3
    ) -> Tuple[bool, str, list[int]]:
        """
        检查整个文档的文本质量
        
        Args:
            pages_text: 每页的文本列表
            sample_size: 采样页数（检查前 N 页）
        
        Returns:
            (is_good_quality, reason, bad_page_indices): 
            (整体质量是否良好, 原因说明, 质量差的页码列表)
        """
        if not pages_text:
            return False, "文档为空", []
        
        # 采样检测（检查前 N 页）
        sample_pages = pages_text[:min(sample_size, len(pages_text))]
        bad_pages = []
        
        for i, text in enumerate(sample_pages):
            is_good, reason = cls.check_page_quality(text, 0, 0)
            if not is_good:
                bad_pages.append(i)
                logger.info(f"[TextQuality] 第 {i+1} 页质量差: {reason}")
        
        # 如果超过一半的采样页质量差 → 整体质量差
        bad_ratio = len(bad_pages) / len(sample_pages)
        if bad_ratio > 0.5:
            return False, f"采样页中 {bad_ratio:.1%} 质量差，建议使用 OCR", bad_pages
        
        # 整体质量良好
        return True, "文档质量良好，可直接使用文本层", bad_pages
    
    @classmethod
    def should_use_ocr(
        cls,
        text: str,
        page_width: float = 0,
        page_height: float = 0
    ) -> Tuple[bool, str]:
        """
        判断是否应该使用 OCR
        
        Args:
            text: 提取的文本
            page_width: 页面宽度
            page_height: 页面高度
        
        Returns:
            (should_ocr, reason): (是否应该 OCR, 原因说明)
        """
        is_good, reason = cls.check_page_quality(text, page_width, page_height)
        
        if is_good:
            return False, f"文本质量良好，无需 OCR: {reason}"
        else:
            return True, f"文本质量差，建议 OCR: {reason}"


# 便捷函数
def check_text_quality(text: str) -> bool:
    """
    快速检查文本质量
    
    Args:
        text: 提取的文本
    
    Returns:
        是否质量良好
    """
    is_good, _ = TextQualityChecker.check_page_quality(text, 0, 0)
    return is_good


def should_use_ocr(text: str) -> bool:
    """
    快速判断是否应该使用 OCR
    
    Args:
        text: 提取的文本
    
    Returns:
        是否应该使用 OCR
    """
    should_ocr, _ = TextQualityChecker.should_use_ocr(text)
    return should_ocr
