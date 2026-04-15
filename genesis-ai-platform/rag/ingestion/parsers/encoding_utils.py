"""
编码检测工具

提供统一的文本编码检测功能
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def decode_with_encoding_detection(content: bytes) -> Tuple[str, str]:
    """
    自动检测编码并解码
    
    尝试编码顺序（参考 WeKnora）：
    1. utf-8（最常用，优先尝试）
    2. gb18030（中文国标，兼容 GBK 和 GB2312）
    3. gb2312（简体中文）
    4. gbk（简体中文扩展）
    5. big5（繁体中文）
    6. ascii（纯英文）
    7. latin-1（西欧语言，兜底方案，不会抛出异常）
    
    Args:
        content: 字节内容
    
    Returns:
        (解码后的文本, 使用的编码)
    """
    encodings = ["utf-8", "gb18030", "gb2312", "gbk", "big5", "ascii", "latin-1"]
    
    for encoding in encodings:
        try:
            text = content.decode(encoding)
            logger.debug(f"[EncodingUtils] 编码检测成功: {encoding}")
            return text, encoding
        except (UnicodeDecodeError, LookupError):
            continue
    
    # 理论上不会到这里（latin-1 不会抛出异常）
    logger.warning("[EncodingUtils] 所有编码尝试失败，使用 utf-8 并忽略错误")
    return content.decode("utf-8", errors="ignore"), "utf-8-fallback"
